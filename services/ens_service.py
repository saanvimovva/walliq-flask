"""ENS reverse lookup through Ethereum RPC.

ENS reverse records are public onchain data. This service calls the ENS
Universal Resolver from the backend and does not require an ENS-specific API key.
"""

import json

import requests


ETH_RPC_URL = "https://ethereum-rpc.publicnode.com"
UNIVERSAL_RESOLVER = "0xeEeEEEeE14D718C2B47D9923Deab1335E144EeEe"
REVERSE_SELECTOR = "5d78a217"
COIN_TYPES = {
    "ethereum": 60,
    "base": int("80002105", 16),
}


def source_result(status, data=None, error=None):
    """Return a consistent service wrapper."""
    return {"source": "ens", "status": status, "data": data, "error": error}


def get_ens_reverse(address, network_id):
    """Return the verified primary ENS name for an address when available."""
    coin_type = COIN_TYPES.get(network_id, 60)
    try:
        result = eth_call(UNIVERSAL_RESOLVER, encode_reverse_call(address, coin_type))
        decoded = decode_reverse_result(result)
        return source_result(
            "available",
            data={
                "name": decoded["name"],
                "resolver": decoded["resolver"],
                "reverseResolver": decoded["reverseResolver"],
                "coinType": coin_type,
                "detail": "ENS Universal Resolver reverse lookup. A blank name means no primary ENS name was found.",
            },
        )
    except Exception as exc:
        message = str(exc)
        if any(term in message.lower() for term in ["resolvernotfound", "reverseaddressmismatch", "execution reverted"]):
            return source_result(
                "available",
                data={
                    "name": "",
                    "resolver": "",
                    "reverseResolver": "",
                    "coinType": coin_type,
                    "detail": "No verified primary ENS name was found.",
                },
            )
        return source_result("failed", error=message)


def eth_call(to_address, data):
    """Execute one Ethereum JSON-RPC eth_call."""
    response = requests.post(
        ETH_RPC_URL,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_call",
            "params": [{"to": to_address, "data": data}, "latest"],
        },
        timeout=20,
    )
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {"message": response.text}

    if not response.ok:
        raise RuntimeError(f"ENS RPC returned HTTP {response.status_code}")
    if body.get("error"):
        error = body["error"]
        raise RuntimeError(error.get("message") if isinstance(error, dict) else str(error))
    return body.get("result") or "0x"


def encode_reverse_call(address, coin_type):
    """ABI-encode reverse(bytes lookupAddress, uint256 coinType)."""
    clean = address.lower().replace("0x", "")
    address_bytes = clean.ljust(64, "0")
    return (
        "0x"
        + REVERSE_SELECTOR
        + encode_uint(64)
        + encode_uint(coin_type)
        + encode_uint(20)
        + address_bytes
    )


def decode_reverse_result(hex_result):
    """ABI-decode (string primary, address resolver, address reverseResolver)."""
    data = hex_result.replace("0x", "")
    if len(data) < 192:
        return {"name": "", "resolver": "", "reverseResolver": ""}

    string_offset = int(data[0:64], 16) * 2
    resolver = decode_address(data[64:128])
    reverse_resolver = decode_address(data[128:192])
    name = decode_string(data, string_offset)
    return {"name": name, "resolver": resolver, "reverseResolver": reverse_resolver}


def decode_address(word):
    """Decode an ABI address word."""
    address = "0x" + word[-40:]
    return "" if address == "0x0000000000000000000000000000000000000000" else address


def decode_string(data, offset):
    """Decode an ABI string from a byte offset."""
    if offset + 64 > len(data):
        return ""
    length = int(data[offset : offset + 64], 16)
    start = offset + 64
    end = start + length * 2
    if end > len(data):
        return ""
    return bytes.fromhex(data[start:end]).decode("utf-8", errors="replace")


def encode_uint(value):
    """ABI-encode a uint256."""
    return hex(int(value)).replace("0x", "").rjust(64, "0")
