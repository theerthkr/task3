"""Isolated cryptographic hashing – no blockchain dependencies.

Edit this file freely to change how fingerprints are derived.
All other modules consume only its output (hex / bytes32_hex), so hashing
logic can evolve without touching chain code.

Design:
  - Pure stdlib: hashlib + json + pathlib only. No web3 import.
  - Deterministic: sorted keys + compact separators + float rounding.
  - Generic + opinionated: low-level primitives (hash_bytes/hash_text/hash_file)
    plus canonical JSON helpers and a backwards-compat `create_fingerprint`
    that mirrors HH Goa's evidence schema.

Usage:
  from blockchain_verify.hashing import hash_bytes, hash_file, hash_json, create_fingerprint

  fp = hash_json({"title": "hello", "source": "x.com"})
  # fp == {"canonical_json": "...", "hex_hash": "abc...", "bytes32_hex": "0xabc...", "bytes32_raw": b"..."}
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from .config import DEFAULT_RECORD_KEYS

# ---------------------------------------------------------------------------
# EDITABLE: which keys to include when hashing a "verification record" dict.
# Change this list to add/remove fields from the fingerprint. Keys are sorted
# before serialisation, so order here does not affect output.
# ---------------------------------------------------------------------------
ALLOWED_RECORD_KEYS = list(DEFAULT_RECORD_KEYS)

__all__ = [
    "ALLOWED_RECORD_KEYS",
    "canonical_json",
    "canonicalize_record",
    "sha256_hex",
    "sha256_bytes32",
    "hash_bytes",
    "hash_text",
    "hash_file",
    "hash_json",
    "create_fingerprint",
    "fingerprint_from_bytes",
]


# ---------------------------------------------------------------------------
# Low-level primitives – work on raw bytes, no JSON involved.
# ---------------------------------------------------------------------------

def sha256_hex(data: bytes) -> str:
    """64-char lowercase hex SHA-256 of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_bytes32(data: bytes) -> str:
    """0x-prefixed bytes32 hex suitable for Solidity bytes32."""
    return f"0x{sha256_hex(data)}"


def fingerprint_from_bytes(data: bytes, *, canonical_json_str: str | None = None) -> Dict[str, Any]:
    """Build uniform fingerprint dict from raw bytes.

    Returns:
        canonical_json: str | None  (pass-through if supplied)
        hex_hash:       64-char hex
        bytes32_hex:    0x-prefixed hex
        bytes32_raw:    32-byte raw
    """
    hex_hash = sha256_hex(data)
    return {
        "canonical_json": canonical_json_str,
        "hex_hash": hex_hash,
        "bytes32_hex": f"0x{hex_hash}",
        "bytes32_raw": bytes.fromhex(hex_hash),
    }


def hash_bytes(data: bytes) -> Dict[str, Any]:
    """Hash arbitrary bytes (e.g. image file bytes, raw post bytes)."""
    return fingerprint_from_bytes(data, canonical_json_str=None)


def hash_text(text: str, *, encoding: str = "utf-8") -> Dict[str, Any]:
    """Hash a unicode string (text/metadata)."""
    return fingerprint_from_bytes(text.encode(encoding), canonical_json_str=text)


def hash_file(path: str | Path, *, chunk_size: int = 8192) -> Dict[str, Any]:
    """Stream-hash a file (image, text, any binary) via SHA-256.

    Raises:
        FileNotFoundError if path does not exist.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"File not found: {p}")
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    hex_hash = h.hexdigest()
    return {
        "canonical_json": None,
        "hex_hash": hex_hash,
        "bytes32_hex": f"0x{hex_hash}",
        "bytes32_raw": bytes.fromhex(hex_hash),
        "file_path": str(p.resolve()),
        "file_size": p.stat().st_size,
    }


# ---------------------------------------------------------------------------
# Canonical JSON helpers – deterministic serialisation for dicts.
# ---------------------------------------------------------------------------

def canonical_json(
    obj: Dict[str, Any],
    *,
    sort_keys: bool = True,
    float_precision: int = 4,
) -> str:
    """Deterministic JSON: sorted keys, compact separators, rounded floats.

    Floats are rounded to `float_precision` to avoid 0.1 + 0.2 style drift
    across platforms. Non-float numerics are left untouched.
    """
    # normalise floats recursively at top level only (shallow) – deep walk optional
    def _normalise(value: Any) -> Any:
        if isinstance(value, float):
            return round(value, float_precision)
        if isinstance(value, dict):
            return {k: _normalise(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_normalise(v) for v in value]
        return value

    clean = _normalise(obj)
    return json.dumps(clean, sort_keys=sort_keys, separators=(",", ":"))


def canonicalize_record(
    record: Dict[str, Any],
    *,
    allowed_keys: list[str] | None = None,
) -> str:
    """Whitelist + canonicalise a verification record dict.

    Only keys in `allowed_keys` (default ALLOWED_RECORD_KEYS) are kept.
    Floats are rounded to 4 decimals. Output is deterministic JSON.
    Edit ALLOWED_RECORD_KEYS at the top of this file to change the schema.
    """
    keys = allowed_keys if allowed_keys is not None else ALLOWED_RECORD_KEYS
    # include only present keys, sorted for determinism inside canonical_json
    filtered: Dict[str, Any] = {}
    for k in sorted(keys):
        if k in record:
            val = record[k]
            if isinstance(val, float):
                val = round(val, 4)
            filtered[k] = val
    return json.dumps(filtered, sort_keys=True, separators=(",", ":"))


def hash_json(
    obj: Dict[str, Any],
    *,
    sort_keys: bool = True,
    float_precision: int = 4,
) -> Dict[str, Any]:
    """Hash any dict via canonical JSON. Use for post metadata / evidence records.

    Example:
        fp = hash_json({"source_url": "https://...", "title": "hello", "face_distance": 0.12})
    """
    cjson = canonical_json(obj, sort_keys=sort_keys, float_precision=float_precision)
    return fingerprint_from_bytes(cjson.encode("utf-8"), canonical_json_str=cjson)


def create_fingerprint(record: Dict[str, Any]) -> Dict[str, Any]:
    """Backwards-compat alias for HH Goa pipeline – whitelist then hash.

    Uses ALLOWED_RECORD_KEYS. Prefer hash_json() for generic payloads.
    """
    cjson = canonicalize_record(record)
    return fingerprint_from_bytes(cjson.encode("utf-8"), canonical_json_str=cjson)
