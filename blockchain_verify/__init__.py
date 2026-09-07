"""blockchain_verify – modular evidence anchoring.

Public facade: import everything you need from here.

    import blockchain_verify as bv

    # Hashing (no web3 needed)
    fp = bv.hash_json({"title": "hello", "source_url": "https://..."})
    fp2 = bv.hash_file("image.jpg")
    fp3 = bv.hash_text("some post text")

    # Chain
    client = bv.connect()                      # env-driven Sepolia / local
    reg = bv.Registry.attach(client)           # ABI/address from env or JSON
    receipt = reg.store(fp["bytes32_hex"], "https://example.com/post")
    assert reg.verify(fp["bytes32_hex"]) is True

    # One-shot helpers
    bv.store_record(fp["bytes32_hex"], "https://...")
    bv.verify_record(fp["bytes32_hex"])

Separation-of-concerns:
  hashing.py  -> pure crypto (editable, no deps)
  client.py   -> RPC + account (no ABI)
  registry.py -> contract calls (calls client)
  deploy.py   -> compiles + deploys (standalone CLI)
"""

from .client import ConnectedClient, ChainInfo, connect
from .hashing import (
    ALLOWED_RECORD_KEYS,
    canonical_json,
    canonicalize_record,
    create_fingerprint,
    hash_bytes,
    hash_file,
    hash_json,
    hash_text,
    sha256_bytes32,
    sha256_hex,
)
from .registry import Registry, get_record, store_record, verify_record

__all__ = [
    # connection
    "connect",
    "ConnectedClient",
    "ChainInfo",
    # hashing
    "hash_bytes",
    "hash_text",
    "hash_file",
    "hash_json",
    "create_fingerprint",
    "canonical_json",
    "canonicalize_record",
    "sha256_hex",
    "sha256_bytes32",
    "ALLOWED_RECORD_KEYS",
    # registry
    "Registry",
    "store_record",
    "verify_record",
    "get_record",
]

__version__ = "1.0.0"
