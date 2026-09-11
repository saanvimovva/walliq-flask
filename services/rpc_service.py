"""Public blockchain RPC integration for WalliQ."""

import json

import requests


TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

NETWORKS = {
    "base": {
        "id": "base",
        "name": "Base Mainnet",
        "rpc_url": "https://mainnet.base.org",
        "chain_id": "0x2105",
        "currency": "ETH",
        "explorer_address": "https://basescan.org/address/",
        "explorer_tx": "https://basescan.org/tx/",
        "usdc": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "log_window_blocks": 1000,
    },
    "ethereum": {
        "id": "ethereum",
        "name": "Ethereum Mainnet",
        "rpc_url": "https://ethereum-rpc.publicnode.com",
        "chain_id": "0x1",
        "currency": "ETH",
        "explorer_address": "https://etherscan.io/address/",
        "explorer_tx": "https://etherscan.io/tx/",
        "usdc": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "log_window_blocks": 1000,
    },
}

KNOWN_LABELS = {
    "base": {
        "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": {
            "label": "Circle native USDC contract",
            "type": "Token contract",
            "source": "Local label list",
        },
    },
    "ethereum": {
        "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": {
            "label": "Circle USDC contract",
            "type": "Token contract",
            "source": "Local label list",
        },
    },
}


def source_result(status, data=None, error=None):
    """Return a consistent service wrapper."""
    return {"source": "rpc", "status": status, "data": data, "error": error}


def rpc_post(network, method, params=None):
    """Call one JSON-RPC method and return the result field."""
    response = requests.post(
        network["rpc_url"],
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []},
        timeout=20,
    )

    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {"message": response.text}

    if not response.ok:
        raise RuntimeError(f"{network['name']} RPC returned HTTP {response.status_code}")
    if body.get("error"):
        error = body["error"]
        raise RuntimeError(error.get("message") if isinstance(error, dict) else str(error))
    return body.get("result")


def pad_address_topic(address):
    """Pad an address for use as an indexed ERC-20 Transfer topic."""
    return "0x" + address.lower().replace("0x", "").rjust(64, "0")


def topic_to_address(topic):
    """Extract an EVM address from a padded log topic."""
    return "0x" + topic[-40:]


def wei_to_eth(hex_value):
    """Convert hex wei to ETH."""
    return int(hex_value or "0x0", 16) / 10**18


def usdc_units_to_decimal(value):
    """Convert USDC base units to decimal USDC."""
    units = value if isinstance(value, int) else int(value or "0x0", 16)
    return units / 10**6


def erc20_balance_of(network, token, address):
    """Read ERC-20 balanceOf(address) using eth_call."""
    selector = "0x70a08231"
    data = selector + address.lower().replace("0x", "").rjust(64, "0")
    return rpc_post(network, "eth_call", [{"to": token, "data": data}, "latest"])


def get_usdc_logs(network, address, latest_block):
    """Fetch recent USDC Transfer logs where the wallet is sender or receiver."""
    from_block = hex(max(0, latest_block - network["log_window_blocks"]))
    wallet_topic = pad_address_topic(address)
    base_filter = {
        "address": network["usdc"],
        "fromBlock": from_block,
        "toBlock": "latest",
    }
    filters = {
        "sent": [TRANSFER_TOPIC, wallet_topic],
        "received": [TRANSFER_TOPIC, None, wallet_topic],
    }
    results = {}
    errors = []

    for label, topics in filters.items():
        try:
            results[label] = rpc_post(network, "eth_getLogs", [{**base_filter, "topics": topics}]) or []
        except Exception as exc:
            results[label] = []
            errors.append(str(exc))

    return {
        "sent": results["sent"],
        "received": results["received"],
        "partial": bool(errors),
        "errors": errors,
    }


def get_wallet_signals(address, network_id):
    """Return live wallet signals from public blockchain RPC."""
    try:
        network = NETWORKS[network_id]
        chain_id = rpc_post(network, "eth_chainId")
        if str(chain_id).lower() != network["chain_id"]:
            raise RuntimeError(f"Connected to unexpected chain {chain_id}; expected {network['chain_id']}")

        latest_hex = rpc_post(network, "eth_blockNumber")
        native_balance_hex = rpc_post(network, "eth_getBalance", [address, "latest"])
        tx_count_hex = rpc_post(network, "eth_getTransactionCount", [address, "latest"])
        usdc_balance_hex = erc20_balance_of(network, network["usdc"], address)
        contract_code = rpc_post(network, "eth_getCode", [address, "latest"])

        latest_block = int(latest_hex, 16)
        logs = get_usdc_logs(network, address, latest_block)
        all_logs = [*logs["sent"], *logs["received"]]
        counterparties = set()
        usdc_window_volume = 0
        wallet = address.lower()

        for log in all_logs:
            topics = log.get("topics", [])
            if len(topics) < 3:
                continue
            from_address = topic_to_address(topics[1]).lower()
            to_address = topic_to_address(topics[2]).lower()
            counterparties.add(to_address if from_address == wallet else from_address)
            usdc_window_volume += int(log.get("data") or "0x0", 16)

        data = {
            "network": {
                "id": network["id"],
                "name": network["name"],
                "currency": network["currency"],
                "explorerAddress": network["explorer_address"],
                "explorerTx": network["explorer_tx"],
            },
            "latestBlock": latest_block,
            "nativeBalance": wei_to_eth(native_balance_hex),
            "txCount": int(tx_count_hex, 16),
            "usdcBalance": usdc_units_to_decimal(usdc_balance_hex),
            "recentUsdcTransfers": len(all_logs),
            "recentUsdcVolume": usdc_units_to_decimal(usdc_window_volume),
            "counterparties": len(counterparties),
            "logWindowBlocks": network["log_window_blocks"],
            "partialLogs": logs["partial"],
            "logErrors": logs["errors"],
            "isContract": bool(contract_code and contract_code != "0x"),
            "knownLabel": KNOWN_LABELS.get(network_id, {}).get(address.lower()),
        }
        return source_result("available", data=data)
    except Exception as exc:
        return source_result("failed", error=str(exc))
