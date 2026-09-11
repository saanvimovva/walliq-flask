"""
WalliQ Flask application.

The browser is intentionally presentation-only. It sends a wallet address and
network to one backend endpoint:

    GET /api/lookup?address=...&network=base

Flask gathers and normalizes data from public blockchain RPC, Moralis, optional
Alchemy, CoinGecko, OpenSea, ENS, local known-address labels, and optional OpenAI analysis.
Private API keys stay in .env and are never exposed to the browser.
"""

import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from services.ai_service import get_ai_analysis
from services.alchemy_service import get_alchemy_intel
from services.coingecko_service import get_coingecko_prices
from services.ens_service import get_ens_reverse
from services.opensea_service import get_opensea_nfts
from services.rpc_service import get_wallet_signals
from utils.lookup_response import build_lookup_response
from utils.validation import is_evm_address


ROOT = Path(__file__).resolve().parent
app = Flask(__name__)


def load_env():
    """Load .env values without overriding variables already set by the shell."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_env()


@app.get("/")
def home():
    """Render the WalliQ lookup page."""
    return render_template("index.html")


@app.get("/api/lookup")
def lookup():
    """Return one normalized wallet intelligence response for the UI."""
    address = request.args.get("address", "").strip()
    network = request.args.get("network", "base").strip().lower()

    if not is_evm_address(address):
        return jsonify({"error": "Invalid EVM wallet address."}), 400
    if network not in {"base", "ethereum"}:
        return jsonify({"error": "Unsupported network. Use base or ethereum."}), 400

    rpc_result = get_wallet_signals(address, network)
    ens_result = get_ens_reverse(address, network)
    alchemy_result = get_alchemy_intel(address, network)
    alchemy_tokens = (alchemy_result.get("data") or {}).get("tokenBalances", [])
    coingecko_result = get_coingecko_prices(network, alchemy_tokens)
    opensea_result = get_opensea_nfts(address, network)
    lookup_response = build_lookup_response(
        address=address,
        network=network,
        rpc_result=rpc_result,
        ens_result=ens_result,
        alchemy_result=alchemy_result,
        coingecko_result=coingecko_result,
        opensea_result=opensea_result,
    )

    ai_result = get_ai_analysis(lookup_response)
    lookup_response["aiAnalysis"] = ai_result.get("data")
    lookup_response["dataSources"].append(source_status("OpenAI", ai_result))
    if ai_result.get("status") in {"not_configured", "account_limited", "auth_failed", "failed"}:
        lookup_response["warnings"].append(ai_result.get("error") or "OpenAI analysis is unavailable.")

    return jsonify(lookup_response)


def source_status(name, result):
    """Return a compact status object for source badges."""
    return {"name": name, "status": result.get("status", "unknown"), "error": result.get("error")}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8788"))
    print(f"WalliQ Flask running at http://127.0.0.1:{port}")
    print("Alchemy API key loaded." if os.environ.get("ALCHEMY_API_KEY") else "Alchemy API key missing. Add it to .env.")
    print("CoinGecko API key loaded." if os.environ.get("COINGECKO_API_KEY") else "CoinGecko API key missing. Add it to .env.")
    print("OpenSea API key loaded." if os.environ.get("OPENSEA_API_KEY") else "OpenSea API key missing. Add it to .env.")
    print("OpenAI API key loaded." if os.environ.get("OPENAI_API_KEY") else "OpenAI API key missing. Add it to .env to enable AI analysis.")
    app.run(host="127.0.0.1", port=port, debug=True, use_reloader=False)
