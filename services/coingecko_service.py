"""CoinGecko token pricing integration.

CoinGecko is used after Alchemy token discovery. Alchemy tells WalliQ which
token contracts a wallet holds; CoinGecko adds market price, market cap, volume,
and 24-hour change where the token is listed.
"""

import json
import os

import requests


ASSET_PLATFORMS = {
    "base": "base",
    "ethereum": "ethereum",
}


def source_result(status, data=None, error=None):
    """Return a consistent service wrapper."""
    return {"source": "coingecko", "status": status, "data": data, "error": error}


def get_coingecko_prices(network_id, token_balances):
    """Return CoinGecko USD price data for Alchemy token balances."""
    api_key = os.environ.get("COINGECKO_API_KEY")
    if not api_key:
        return source_result("not_configured", error="CoinGecko API key is not configured.")

    platform = ASSET_PLATFORMS.get(network_id)
    if not platform:
        return source_result("failed", error=f"CoinGecko does not support network '{network_id}' in this app.")

    tokens = token_balances or []
    contracts = [token.get("contractAddress", "").lower() for token in tokens if token.get("contractAddress")]
    contracts = list(dict.fromkeys(contracts))[:25]
    if not contracts:
        return source_result(
            "available",
            data={"platform": platform, "prices": {}, "portfolioValueUsd": 0, "pricedTokenCount": 0, "tokens": []},
        )

    try:
        prices = coingecko_get(
            f"/simple/token_price/{platform}",
            {
                "contract_addresses": ",".join(contracts),
                "vs_currencies": "usd",
                "include_market_cap": "true",
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
                "include_last_updated_at": "true",
                "precision": "full",
            },
        )
        priced_tokens = enrich_tokens(tokens, prices)
        return source_result(
            "available",
            data={
                "platform": platform,
                "prices": prices,
                "portfolioValueUsd": sum(token.get("valueUsd") or 0 for token in priced_tokens),
                "pricedTokenCount": sum(1 for token in priced_tokens if token.get("priceUsd") is not None),
                "tokens": priced_tokens,
            },
        )
    except Exception as exc:
        message = str(exc)
        return source_result(classify_coingecko_error(message), error=message)


def coingecko_get(path, params=None):
    """Call CoinGecko using the configured Demo or Pro API key."""
    api_base = os.environ.get("COINGECKO_API_BASE", "https://api.coingecko.com/api/v3").rstrip("/")
    api_key = os.environ["COINGECKO_API_KEY"]
    header_name = "x-cg-pro-api-key" if "pro-api.coingecko.com" in api_base else "x-cg-demo-api-key"
    response = requests.get(
        f"{api_base}{path}",
        params=params or {},
        headers={header_name: api_key, "accept": "application/json"},
        timeout=25,
    )
    body = parse_response_body(response)
    if not response.ok:
        raise RuntimeError(provider_error_message(body, response.status_code))
    return body


def enrich_tokens(tokens, prices):
    """Attach CoinGecko pricing to Alchemy token balances."""
    enriched = []
    for token in tokens:
        contract = (token.get("contractAddress") or "").lower()
        price = prices.get(contract) or {}
        balance = parse_float(token.get("balanceFormatted"))
        price_usd = price.get("usd")
        value_usd = balance * price_usd if balance is not None and price_usd is not None else None
        enriched.append(
            {
                **token,
                "priceUsd": price_usd,
                "valueUsd": value_usd,
                "marketCapUsd": price.get("usd_market_cap"),
                "volume24hUsd": price.get("usd_24h_vol"),
                "change24hPct": price.get("usd_24h_change"),
                "lastUpdatedAt": price.get("last_updated_at"),
            }
        )
    return enriched


def parse_float(value):
    """Parse formatted numeric strings such as '1,234.5'."""
    if value in {None, ""}:
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def parse_response_body(response):
    """Parse JSON responses, preserving plain text provider errors."""
    try:
        return response.json()
    except json.JSONDecodeError:
        return {"message": response.text}


def provider_error_message(body, status_code):
    """Read a CoinGecko provider error without exposing secrets."""
    if isinstance(body, dict):
        error = body.get("error") or body.get("message") or body.get("status", {}).get("error_message")
        if error:
            return str(error)
    return f"CoinGecko returned HTTP {status_code}"


def classify_coingecko_error(message):
    """Map provider messages to app-level source statuses."""
    lowered = (message or "").lower()
    if any(term in lowered for term in ["api key", "unauthorized", "forbidden", "invalid authentication"]):
        return "auth_failed"
    if any(term in lowered for term in ["rate limit", "too many requests", "plan", "credits", "billing"]):
        return "account_limited"
    return "failed"
