"""Alchemy wallet intelligence integration.

Alchemy is used as a free-tier-friendly backend source for token balances,
recent transfers, and NFT ownership samples. It does not prove real-world wallet
ownership; it enriches the wallet activity picture.
"""

import json
import os

import requests


NETWORKS = {
    "base": {"alchemy": "base-mainnet", "name": "Base Mainnet"},
    "ethereum": {"alchemy": "eth-mainnet", "name": "Ethereum Mainnet"},
}


def source_result(status, data=None, error=None):
    """Return a consistent service wrapper."""
    return {"source": "alchemy", "status": status, "data": data, "error": error}


def get_alchemy_intel(address, network_id):
    """Return normalized Alchemy wallet intelligence."""
    api_key = os.environ.get("ALCHEMY_API_KEY")
    if not api_key:
        return source_result("not_configured", error="Alchemy API key is not configured.")

    network = NETWORKS.get(network_id)
    if not network:
        return source_result("failed", error=f"Alchemy does not support network '{network_id}' in this app.")

    calls = [
        optional_call("tokenBalances", lambda: get_token_balances(api_key, network, address)),
        optional_call("recentTransfers", lambda: get_recent_transfers(api_key, network, address)),
        optional_call("nfts", lambda: get_nfts_for_owner(api_key, network, address)),
    ]

    successes = {item["label"]: item["data"] for item in calls if item["ok"]}
    failures = [{"source": item["label"], "status": item.get("status", "failed"), "error": item["error"]} for item in calls if not item["ok"]]

    if not successes:
        return source_result(primary_failure_status(failures), error=primary_failure_message(failures), data={"failures": failures})

    data = {
        "network": network["alchemy"],
        "tokenBalances": successes.get("tokenBalances", []),
        "recentTransfers": successes.get("recentTransfers", []),
        "nfts": successes.get("nfts", []),
        "failures": failures,
    }
    return source_result("partial" if failures else "available", data=data)


def optional_call(label, callback):
    """Run one Alchemy request and preserve partial failures."""
    try:
        return {"label": label, "ok": True, "data": callback()}
    except Exception as exc:
        message = str(exc)
        return {"label": label, "ok": False, "status": classify_alchemy_error(message), "error": message}


def alchemy_rpc(api_key, network, method, params=None):
    """Call an Alchemy JSON-RPC endpoint."""
    response = requests.post(
        f"https://{network['alchemy']}.g.alchemy.com/v2/{api_key}",
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []},
        headers={"content-type": "application/json"},
        timeout=25,
    )
    body = parse_response_body(response)
    if not response.ok:
        raise RuntimeError(provider_error_message(body, response.status_code))
    if body.get("error"):
        raise RuntimeError(provider_error_message(body, response.status_code))
    return body.get("result") or {}


def get_token_balances(api_key, network, address):
    """Fetch ERC-20 balances and enrich the first non-zero tokens with metadata."""
    result = alchemy_rpc(api_key, network, "alchemy_getTokenBalances", [address, "erc20"])
    balances = result.get("tokenBalances") or []
    nonzero = [item for item in balances if int(item.get("tokenBalance") or "0x0", 16) > 0]
    enriched = []

    for item in nonzero[:8]:
        contract = item.get("contractAddress")
        metadata = {}
        try:
            metadata = alchemy_rpc(api_key, network, "alchemy_getTokenMetadata", [contract])
        except Exception:
            metadata = {}
        enriched.append(
            {
                "contractAddress": contract,
                "rawBalance": item.get("tokenBalance"),
                "name": metadata.get("name") or "",
                "symbol": metadata.get("symbol") or "TOKEN",
                "decimals": metadata.get("decimals"),
                "logo": metadata.get("logo") or "",
                "balanceFormatted": format_token_balance(item.get("tokenBalance"), metadata.get("decimals")),
            }
        )
    return enriched


def get_recent_transfers(api_key, network, address):
    """Fetch recent inbound and outbound transfers for the wallet."""
    transfers = []
    for direction, field in [("outbound", "fromAddress"), ("inbound", "toAddress")]:
        result = alchemy_rpc(
            api_key,
            network,
            "alchemy_getAssetTransfers",
            [
                {
                    field: address,
                    "category": ["external", "erc20", "erc721", "erc1155"],
                    "withMetadata": True,
                    "excludeZeroValue": False,
                    "maxCount": "0x8",
                    "order": "desc",
                }
            ],
        )
        for item in result.get("transfers", [])[:8]:
            transfers.append(compact_transfer(item, direction))
    return transfers[:12]


def get_nfts_for_owner(api_key, network, address):
    """Fetch a small NFT ownership sample for the wallet."""
    response = requests.get(
        f"https://{network['alchemy']}.g.alchemy.com/nft/v3/{api_key}/getNFTsForOwner",
        params=[
            ("owner", address),
            ("withMetadata", "true"),
            ("pageSize", "6"),
        ],
        timeout=25,
    )
    body = parse_response_body(response)
    if not response.ok:
        raise RuntimeError(provider_error_message(body, response.status_code))

    nfts = []
    for item in (body.get("ownedNfts") or [])[:6]:
        contract = item.get("contract") or {}
        nfts.append(
            {
                "name": item.get("name") or "Unnamed NFT",
                "tokenType": item.get("tokenType") or contract.get("tokenType") or "",
                "contractAddress": contract.get("address") or "",
                "collectionName": (contract.get("openSeaMetadata") or {}).get("collectionName") or contract.get("name") or "",
                "imageUrl": ((item.get("image") or {}).get("cachedUrl") or (item.get("image") or {}).get("pngUrl") or ""),
            }
        )
    return nfts


def compact_transfer(item, direction):
    """Normalize one Alchemy transfer item for the UI."""
    metadata = item.get("metadata") or {}
    return {
        "direction": direction,
        "category": item.get("category") or "transfer",
        "asset": item.get("asset") or "",
        "value": item.get("value"),
        "from": item.get("from") or "",
        "to": item.get("to") or "",
        "hash": item.get("hash") or "",
        "blockNum": item.get("blockNum") or "",
        "blockTimestamp": metadata.get("blockTimestamp") or "",
    }


def parse_response_body(response):
    """Parse JSON responses, preserving plain text provider errors."""
    try:
        return response.json()
    except json.JSONDecodeError:
        return {"message": response.text}


def provider_error_message(body, status_code):
    """Read an Alchemy provider error without exposing secrets."""
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        return error.get("message") or f"Alchemy returned HTTP {status_code}"
    return body.get("message") or body.get("error") or f"Alchemy returned HTTP {status_code}"


def classify_alchemy_error(message):
    """Map provider messages to app-level source statuses."""
    lowered = (message or "").lower()
    if any(term in lowered for term in ["invalid api key", "access key", "unauthorized", "forbidden"]):
        return "auth_failed"
    if any(term in lowered for term in ["rate limit", "too many requests", "compute units", "payment", "billing"]):
        return "account_limited"
    return "failed"


def primary_failure_message(failures):
    """Use the provider's most useful failure when every Alchemy call fails."""
    if not failures:
        return "All Alchemy calls failed."
    first_error = failures[0].get("error") or "All Alchemy calls failed."
    return f"All Alchemy calls failed. First provider error: {first_error}"


def primary_failure_status(failures):
    """Return a status that explains why the integration is unavailable."""
    statuses = {failure.get("status") for failure in failures}
    if "account_limited" in statuses:
        return "account_limited"
    if "auth_failed" in statuses:
        return "auth_failed"
    return "failed"


def format_token_balance(raw_balance, decimals):
    """Convert a hex token balance into a display string."""
    if decimals is None:
        return ""
    try:
        value = int(raw_balance or "0x0", 16) / (10 ** int(decimals))
    except (TypeError, ValueError):
        return ""
    return f"{value:,.6f}".rstrip("0").rstrip(".")
