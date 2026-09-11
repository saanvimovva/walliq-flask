"""Normalize multiple wallet intelligence sources into one UI response."""


def build_lookup_response(address, network, rpc_result, ens_result, alchemy_result, coingecko_result, opensea_result):
    """Create the single response consumed by the presentation-only UI."""
    rpc_data = rpc_result.get("data") or {}
    ens_data = ens_result.get("data") or {}
    alchemy_data = alchemy_result.get("data") or {}
    coingecko_data = coingecko_result.get("data") or {}
    opensea_data = opensea_result.get("data") or {}
    owner = choose_owner(rpc_data, ens_data)

    return {
        "address": address,
        "network": network,
        "summary": build_summary(owner, rpc_data),
        "owner": owner,
        "signals": rpc_data,
        "ens": ens_data,
        "alchemy": alchemy_data,
        "coingecko": coingecko_data,
        "opensea": opensea_data,
        "transactions": alchemy_data.get("recentTransfers", []),
        "warnings": build_warnings(rpc_result, ens_result, alchemy_result, coingecko_result, opensea_result, owner),
        "dataSources": [
            source_status("RPC", rpc_result),
            source_status("ENS", ens_result),
            source_status("Alchemy", alchemy_result),
            source_status("CoinGecko", coingecko_result),
            source_status("OpenSea", opensea_result),
        ],
    }


def source_status(name, result):
    """Return a compact status object for source badges."""
    return {"name": name, "status": result.get("status", "unknown"), "error": result.get("error")}


def choose_owner(rpc_data, ens_data):
    """Pick the strongest available ownership/identity signal."""
    local_label = rpc_data.get("knownLabel")
    if local_label:
        return {
            "status": "known",
            "label": local_label.get("label"),
            "type": local_label.get("type"),
            "source": local_label.get("source", "Local label list"),
            "confidence": "high",
            "detail": "Matched a known address maintained by WalliQ.",
        }

    ens_name = ens_data.get("name")
    if ens_name:
        return {
            "status": "named",
            "label": ens_name,
            "type": "ENS reverse name",
            "source": "ENS Universal Resolver",
            "confidence": "verified public identity clue",
            "detail": "ENS reverse resolution is useful context, but it is not legal ownership proof.",
        }

    if rpc_data.get("isContract"):
        return {
            "status": "contract",
            "label": "Unlabeled smart contract",
            "type": "Smart contract",
            "source": "RPC",
            "confidence": "high",
            "detail": "The address has deployed contract code, but no owner label was found.",
        }

    return {
        "status": "unknown",
        "label": "Unknown owner",
        "type": "Externally owned wallet",
        "source": "No label source",
        "confidence": "not available",
        "detail": "No local label or ENS reverse name was found.",
    }


def owner_detail(candidate):
    """Create a readable explanation for an Arkham candidate."""
    bits = []
    if candidate.get("label"):
        bits.append(f"Label: {candidate['label']}")
    if candidate.get("entityId"):
        bits.append(f"Entity ID: {candidate['entityId']}")
    if candidate.get("chain"):
        bits.append(f"Chain: {candidate['chain']}")
    return " - ".join(bits) or "Arkham returned an address intelligence candidate."


def build_warnings(rpc_result, ens_result, alchemy_result, coingecko_result, opensea_result, owner):
    """Create plain-language warnings without overstating certainty."""
    warnings = []
    for result in [rpc_result, ens_result, alchemy_result, coingecko_result, opensea_result]:
        status = result.get("status")
        if status == "not_configured":
            warnings.append(f"{result['source']} is not configured.")
        elif status == "account_limited":
            warnings.append(f"{result['source']} account setup is blocking access: {result.get('error')}")
        elif status == "auth_failed":
            warnings.append(f"{result['source']} authentication failed: {result.get('error')}")
        elif status == "failed":
            warnings.append(f"{result['source']} failed: {result.get('error')}")
        elif status == "partial":
            warnings.append(f"{result['source']} returned partial data.")

    if owner.get("status") == "unknown":
        warnings.append("Owner identity is unknown from the configured sources.")
    elif owner.get("status") == "contract":
        warnings.append("This is a smart contract, not a normal payment wallet.")
    return warnings


def build_summary(owner, rpc_data):
    """Create the top-line conclusion shown above the panels."""
    network = (rpc_data.get("network") or {}).get("name", "selected network")
    return {
        "title": owner.get("label", "Lookup complete"),
        "detail": f"{owner.get('type', 'Wallet')} on {network}. Source: {owner.get('source', 'unknown')}.",
    }
