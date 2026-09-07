"""Blockchain anchor – ONLY importer of blockchain_verify. Local chain, 0 setup."""

from __future__ import annotations
from typing import Any, Dict

def _distance(sim: float | None) -> float | None:
    return round(1.0 - float(sim), 4) if sim is not None else None

def build_anchor_record(row: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic record: uses ALLOWED_RECORD_KEYS (hashing.py). Edit there to change hash."""
    return {
        "title": row.get("title") or "",
        "source": row.get("source") or row.get("platform") or "",
        "source_url": row.get("page_url") or "",
        "image_url": row.get("image_url") or "",
        "face_match": bool(row.get("verified")),
        "face_distance": _distance(row.get("similarity")),
    }

def fingerprint_for_row(row: Dict[str, Any]) -> Dict[str, Any]:
    from blockchain_verify.hashing import create_fingerprint
    return create_fingerprint(build_anchor_record(row))

def anchor_report(report: Dict[str, Any], top_k: int = 1, source_url: str | None = None) -> Dict[str, Any]:
    """Hash top verified post -> store on LOCAL chain (no RPC/key). Always works."""
    ranked = report.get("ranked") or []
    verified = [r for r in ranked if r.get("verified")]
    targets = verified[:top_k] if verified else []

    info: Dict[str, Any] = {"enabled": True, "contract_address": "0x0000000000000000000000000000000001", "network": "Local simulated (in-memory)", "items": [], "note": "Local chain — 0 setup, hash stored in-memory. Sepolia available via `python -m blockchain_verify.deploy --expect-sepolia`."}

    if report.get("mode") == "DRY_RUN":
        info["note"] = "DRY_RUN — run SEARCH to get a verified post to anchor."
        report["blockchain"] = info
        return report
    if not targets:
        info["note"] = "No verified post (similarity < 0.45) — nothing to anchor."
        report["blockchain"] = info
        return report

    from blockchain_verify.local_chain import get_local_registry
    _, reg = get_local_registry()

    for row in targets:
        fp = fingerprint_for_row(row)
        receipt = reg.store(fp["bytes32_hex"], source_url or row.get("page_url") or "")
        ok = reg.verify(fp["bytes32_hex"])
        info["items"].append({"page_url": row.get("page_url"), "bytes32_hex": fp["bytes32_hex"], "canonical_json": fp["canonical_json"], "receipt": receipt, "verify": ok, "error": None})
    report["blockchain"] = info
    return report

def verify_report_file(report_path: str) -> Dict[str, Any]:
    """Re-verify report.json items on local chain (no key needed)."""
    import json
    from blockchain_verify.local_chain import get_local_registry
    with open(report_path, encoding="utf-8") as fh:
        report = json.load(fh)
    items = (report.get("blockchain") or {}).get("items") or []
    if not items:
        # hash anew from ranked verified
        ranked = report.get("ranked") or []
        verified = [r for r in ranked if r.get("verified")]
        if not verified:
            return {"path": report_path, "error": "No verified post", "items": []}
        items = []
        for r in verified[:1]:
            fp = fingerprint_for_row(r)
            items.append({"bytes32_hex": fp["bytes32_hex"], "canonical_json": fp["canonical_json"], "page_url": r.get("page_url")})
    _, reg = get_local_registry()
    out = []
    for it in items:
        b32 = it.get("bytes32_hex")
        if not b32: continue
        ok = reg.verify(b32)
        rec = reg.get(b32) if ok else None
        out.append({"bytes32_hex": b32, "page_url": it.get("page_url"), "verify": ok, "on_chain_record": rec, "canonical_json": it.get("canonical_json")})
    return {"path": report_path, "contract_address": "0x0000000000000000000000000000000001", "network": "Local simulated (in-memory)", "etherscan_contract": "N/A (local)", "items": out}
