"""OpenAI-powered wallet analysis service.

This service receives the already-normalized WalliQ lookup response and asks
OpenAI for a concise analyst-style interpretation. It is intentionally kept on
the backend so API keys and raw source payloads never go to the browser.
"""

import json
import os
from copy import deepcopy

import requests


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-5.6-luna"


ANALYSIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "decision": {"type": "string"},
        "riskLevel": {"type": "string", "enum": ["low", "medium", "high", "unknown"]},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "summary": {"type": "string"},
        "keyFindings": {"type": "array", "items": {"type": "string"}},
        "redFlags": {"type": "array", "items": {"type": "string"}},
        "missingData": {"type": "array", "items": {"type": "string"}},
        "recommendedNextSteps": {"type": "array", "items": {"type": "string"}},
        "ownershipCaveat": {"type": "string"},
    },
    "required": [
        "decision",
        "riskLevel",
        "confidence",
        "summary",
        "keyFindings",
        "redFlags",
        "missingData",
        "recommendedNextSteps",
        "ownershipCaveat",
    ],
}


def get_ai_analysis(lookup_response):
    """Return AI analysis for a normalized lookup response."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {
            "source": "OpenAI",
            "status": "not_configured",
            "error": "OPENAI_API_KEY is not configured.",
            "data": None,
        }

    compact_lookup = compact_lookup_payload(lookup_response)
    prompt = build_prompt(compact_lookup)

    try:
        response = requests.post(
            OPENAI_RESPONSES_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": os.environ.get("OPENAI_MODEL", DEFAULT_MODEL),
                "input": [
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    "You are a crypto wallet intelligence analyst. "
                                    "Use only the supplied JSON facts. Do not infer legal ownership. "
                                    "If owner evidence is absent, say owner unknown. "
                                    "Keep the output concise, practical, and useful for a product demo."
                                ),
                            }
                        ],
                    },
                    {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
                ],
                "store": False,
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "wallet_analysis",
                        "schema": ANALYSIS_SCHEMA,
                        "strict": True,
                    }
                },
            },
            timeout=25,
        )
        response.raise_for_status()
        analysis = json.loads(extract_output_text(response.json()))
        return {"source": "OpenAI", "status": "available", "error": None, "data": analysis}
    except requests.HTTPError as exc:
        return {"source": "OpenAI", "status": classify_openai_http_status(exc), "error": format_openai_http_error(exc), "data": None}
    except Exception as exc:
        return {"source": "OpenAI", "status": "failed", "error": f"OpenAI analysis failed: {exc}", "data": None}


def compact_lookup_payload(lookup_response):
    """Keep only facts the model needs, avoiding oversized transaction payloads."""
    payload = deepcopy(lookup_response)
    payload.pop("aiAnalysis", None)

    moralis = payload.get("moralis") or {}
    if isinstance(moralis.get("recentHistory"), list):
        moralis["recentHistory"] = moralis["recentHistory"][:12]
    if isinstance(moralis.get("tokens"), list):
        moralis["tokens"] = moralis["tokens"][:12]

    if isinstance(payload.get("transactions"), list):
        payload["transactions"] = payload["transactions"][:12]

    return payload


def build_prompt(compact_lookup):
    """Build a stable prompt from the normalized wallet facts."""
    return (
        "Analyze this WalliQ wallet lookup JSON. Return only JSON matching the schema. "
        "Focus on: identity evidence, contract-vs-wallet classification, transaction behavior, "
        "risk clues, missing sources, and next data integrations.\n\n"
        f"{json.dumps(compact_lookup, ensure_ascii=True)}"
    )


def extract_output_text(response_body):
    """Extract text from the Responses API body across common response shapes."""
    if response_body.get("output_text"):
        return response_body["output_text"]

    chunks = []
    for item in response_body.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                chunks.append(text)
    if not chunks:
        raise ValueError("OpenAI response did not include output text.")
    return "".join(chunks)


def format_openai_http_error(exc):
    """Convert common OpenAI HTTP failures into user-actionable messages."""
    status_code = exc.response.status_code if exc.response is not None else None
    provider_message = read_openai_error_message(exc)
    if status_code == 401:
        return provider_message or "OpenAI rejected the API key. Check OPENAI_API_KEY in .env."
    if status_code == 403:
        return provider_message or "OpenAI denied access. Check project permissions or selected OPENAI_MODEL."
    if status_code == 404:
        return provider_message or "OpenAI could not find the selected model. Try changing OPENAI_MODEL in .env."
    if status_code == 429:
        return provider_message or "OpenAI returned HTTP 429. Check usage limits, billing, or try again later."
    return provider_message or f"OpenAI returned HTTP {status_code or 'error'}. Check the API key, model, and account limits."


def classify_openai_http_status(exc):
    """Map OpenAI HTTP errors to app-level source statuses."""
    status_code = exc.response.status_code if exc.response is not None else None
    provider_code = read_openai_error_code(exc)
    if status_code == 401:
        return "auth_failed"
    if status_code in {402, 429} and provider_code in {"insufficient_quota", "credit_balance_exhausted"}:
        return "account_limited"
    if status_code == 403:
        return "auth_failed"
    if status_code == 404:
        return "not_configured"
    return "failed"


def read_openai_error_message(exc):
    """Read the provider error message without exposing request headers or keys."""
    if exc.response is None:
        return ""
    try:
        body = exc.response.json()
    except ValueError:
        return ""
    error = body.get("error") or {}
    message = error.get("message") or ""
    code = error.get("code")
    return f"{message} Code: {code}." if message and code else message


def read_openai_error_code(exc):
    """Read the provider error code without exposing secrets."""
    if exc.response is None:
        return ""
    try:
        body = exc.response.json()
    except ValueError:
        return ""
    error = body.get("error") or {}
    return error.get("code") or error.get("type") or ""
