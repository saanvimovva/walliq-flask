"""Validation helpers for WalliQ."""


def is_evm_address(address):
    """Return True when the input is a valid Ethereum/Base-style address."""
    if not isinstance(address, str):
        return False
    if len(address) != 42 or not address.startswith("0x"):
        return False
    try:
        int(address[2:], 16)
        return True
    except ValueError:
        return False
