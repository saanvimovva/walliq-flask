# WalliQ Wallet Lookup - Flask Version

WalliQ is a read-only wallet intelligence prototype. The app checks an EVM wallet address on Base or Ethereum and returns a normalized intelligence view using backend integrations.

## Architecture

```text
Browser UI
  -> Flask /api/lookup
      -> RPC service
      -> ENS reverse lookup service
      -> Alchemy service, optional
      -> CoinGecko service, optional
      -> OpenSea service, optional
      -> response normalizer
      -> OpenAI analysis service, optional
  -> normalized JSON response
```

The browser is only the presentation layer. It does not contain RPC URLs, USDC contract addresses, vendor API keys, AI prompts, or blockchain integration logic.

## Project Structure

```text
walliq-flask/
  app.py
  services/
    rpc_service.py
    ens_service.py
    alchemy_service.py
    coingecko_service.py
    opensea_service.py
    ai_service.py
  utils/
    validation.py
    lookup_response.py
  templates/
    index.html
  static/
    script.js
    styles.css
  requirements.txt
  .env.example
```

## What Works

- One backend lookup endpoint: `/api/lookup`
- Ethereum/Base wallet address validation
- Flask-backed public RPC wallet signals
- Native ETH balance
- Outgoing transaction count
- USDC balance
- Recent USDC transfer log scan
- Contract vs normal wallet detection
- Local known-address labels for USDC contracts
- ENS reverse lookup via Ethereum RPC
- Optional Alchemy token balances, recent transfers, and NFT samples
- Optional CoinGecko token pricing for Alchemy-discovered ERC-20 holdings
- Optional OpenSea NFT holdings and collection samples
- Optional OpenAI analyst summary over the normalized source data
- AI guardrail: ownership is reported as unknown unless a configured source provides a real label
- Source status badges: available, partial, failed, not configured
- Sample address buttons for demos

## Setup

Create a `.env` file:

```env
ALCHEMY_API_KEY=your_alchemy_api_key_here
COINGECKO_API_KEY=your_coingecko_api_key_here
COINGECKO_API_BASE=https://api.coingecko.com/api/v3
OPENSEA_API_KEY=your_opensea_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-5.6-luna
PORT=8788
```

Alchemy, CoinGecko, OpenSea, and OpenAI are optional enrichments. ENS uses public Ethereum RPC and does not need its own API key. The app still returns basic RPC wallet signals without enrichment keys.

Install dependencies:

```powershell
cd C:\saanvi\walliq-flask
python -m pip install -r requirements.txt
```

Start the Flask app:

```powershell
python app.py
```

Open:

```text
http://127.0.0.1:8788
```

## Demo Addresses

Base sample:

```text
0x742d35Cc6634C0532925a3b844Bc454e4438f44e
```

Base USDC contract:

```text
0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
```

Ethereum sample:

```text
0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045
```

Ethereum USDC contract:

```text
0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48
```

## Security

Do not commit `.env`. API keys are read only by the Flask backend.

## AI Analysis

The OpenAI service receives a compact version of the normalized lookup response. It does not decide legal ownership. It turns the available source facts into:

- A concise decision
- Risk level and confidence
- Key findings
- Red flags
- Missing data
- Recommended next steps
- An ownership caveat

This makes the project more useful as a showcase because WalliQ is no longer only displaying raw blockchain fields; it is explaining what the combined signals mean and what data is still missing.
