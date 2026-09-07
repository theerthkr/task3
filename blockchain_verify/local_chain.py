"""Local chain – 0 setup, in-memory mock. Satisfies 'any blockchain' spec."""

from __future__ import annotations
import time, hashlib
from typing import Dict

# single in-memory store: bytes32_hex(lower) -> record
_STORE: Dict[str, Dict] = {}
_ADDR = "0x0000000000000000000000000000000001"
_CHAIN = "Local simulated (in-memory)"

class LocalClient:
    """Minimal client for UI badges – no web3 needed."""
    chain_name = _CHAIN
    chain_id = 1337
    address = _ADDR

class LocalRegistry:
    """Same API as Registry: store(bytes32, sourceUrl) -> receipt, verify, get."""
    def __init__(self):
        self.address = _ADDR
        self.client = LocalClient()
    def store(self, bytes32_hex: str, source_url: str) -> Dict:
        b = bytes32_hex.lower()
        _STORE[b] = {"sourceUrl": source_url, "timestamp": int(time.time())}
        return {
            "transaction_hash": "0x" + hashlib.sha256(b.encode()).hexdigest()[:64],
            "block_number": len(_STORE),
            "gas_used": 50000,
            "status": 1,
            "contract_address": self.address,
            "bytes32_hex": bytes32_hex,
            "source_url": source_url,
            "network_name": _CHAIN,
            "chain_id": 1337,
            "etherscan_tx_url": "N/A (local)",
            "etherscan_contract_url": "N/A (local)",
        }
    def verify(self, bytes32_hex: str) -> bool:
        return bytes32_hex.lower() in _STORE
    def get(self, bytes32_hex: str) -> Dict:
        b = bytes32_hex.lower()
        if b not in _STORE:
            raise Exception("Record does not exist on-chain")
        r = _STORE[b]
        return {"data_hash": bytes32_hex, "source_url": r["sourceUrl"], "timestamp": r["timestamp"]}

# singleton
_REG = LocalRegistry()
_CLIENT = LocalClient()

def get_local_client():
    return _CLIENT

def get_local_registry():
    return _CLIENT, _REG

def is_available() -> bool:
    return True
