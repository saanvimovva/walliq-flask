"""OpenSea NFT holdings integration."""

import json
import os
from collections import Counter

import requests


OPENSEA_BASE = "https://api.opensea.io/api/v2"
CHAIN_MAP = {
    "ethereum": "ethereum",
    "base": "base",
}


def source_result(status, data=None, error=None):
    """Return a consistent service wrapper."""
    return {"source": "opensea", "status": status, "data": data, "error": error}


def get_opensea_nfts(address, network_id):
    """Return NFT holdings and notable collection counts from OpenSea."""
    api_key = os.environ.get("OPENSEA_API_KEY")
    if not api_key:
        return source_result("not_configured", error="OpenSea API key is not configured.")

    chain = CHAIN_MAP.get(network_id)
    if not chain:
        return source_result("failed", error=f"OpenSea does not support network '{network_id}' in this app.")

    try:
        response = requests.get(
            f"{OPENSEA_BASE}/chain/{chain}/account/{address}/nfts",
            params={"limit": 20},
            headers={"X-API-KEY": api_key, "accept": "application/json"},
            timeout=25,
        )
        body = parse_response_body(response)
        if not response.ok:
            raise RuntimeError(provider_error_message(body, response.status_code))

        nfts = compact_nfts(body.get("nfts") or [])
        collections = summarize_collections(nfts)
        return source_result(
            "available",
            data={
                "chain": chain,
                "nftCountShown": len(nfts),
                "notableCollections": collections,
                "nfts": nfts,
            },
        )
    except Exception as exc:
        message = str(exc)
        return source_result(classify_opensea_error(message), error=message)


def compact_nfts(nfts):
    """Normalize OpenSea NFTs for a concise UI sample."""
    compacted = []
    for item in nfts[:20]:
        collection = item.get("collection") or ""
        compacted.append(
            {
                "name": item.get("name") or item.get("identifier") or "Unnamed NFT",
                "collection": collection,
                "contract": item.get("contract") or "",
                "tokenStandard": item.get("token_standard") or "",
                "imageUrl": item.get("image_url") or "",
                "openseaUrl": item.get("opensea_url") or "",
            }
        )
    return compacted


def summarize_collections(nfts):
    """Count NFT sample items by collection slug."""
    counts = Counter(item.get("collection") or "unknown" for item in nfts)
    return [{"collection": collection, "count": count} for collection, count in counts.most_common(6)]


def parse_response_body(response):
    """Parse JSON responses, preserving plain text provider errors."""
    try:
        return response.json()
    except json.JSONDecodeError:
        return {"message": response.text}


def provider_error_message(body, status_code):
    """Read an OpenSea provider error without exposing secrets."""
    if isinstance(body, dict):
        errors = body.get("errors")
        if isinstance(errors, list) and errors:
            return "; ".join(str(error) for error in errors)
        if body.get("detail"):
            return str(body["detail"])
        if body.get("message"):
            return str(body["message"])
    return f"OpenSea returned HTTP {status_code}"


def classify_opensea_error(message):
    """Map provider messages to app-level source statuses."""
    lowered = (message or "").lower()
    if any(term in lowered for term in ["api key", "unauthorized", "forbidden", "invalid"]):
        return "auth_failed"
    if any(term in lowered for term in ["rate limit", "too many requests", "upgrade"]):
        return "account_limited"
    return "failed"
