"""Offline demo – no RPC needed. Proves hashing determinism + tamper detection.

Run:
  python -m blockchain_verify.demo_offline
"""

import blockchain_verify as bv


def main() -> None:
    print("=" * 62)
    print(" blockchain_verify – OFFLINE DEMO (no chain needed)")
    print("=" * 62)

    # 1. Generic post metadata (what you'd hash after a face-match)
    record = {
        "title": "lena.jpg now : r/programming",
        "source": "Reddit",
        "source_url": "https://www.reddit.com/r/programming/comments/dobz8s/lenajpg_now/",
        "image_url": "https://external-preview.redd.it/image.jpg",
        "face_match": True,
        "face_distance": 0.0202,
    }
    fp = bv.create_fingerprint(record)
    print("\n[1] Canonical evidence record hash")
    print("  canonical_json :", fp["canonical_json"])
    print("  hex_hash       :", fp["hex_hash"])
    print("  bytes32_hex    :", fp["bytes32_hex"])

    # 2. Determinism: same record, different key order -> same hash
    shuffled = {
        "face_distance": 0.0202,
        "image_url": "https://external-preview.redd.it/image.jpg",
        "title": "lena.jpg now : r/programming",
        "face_match": True,
        "source_url": "https://www.reddit.com/r/programming/comments/dobz8s/lenajpg_now/",
        "source": "Reddit",
    }
    assert bv.create_fingerprint(shuffled)["bytes32_hex"] == fp["bytes32_hex"]
    print("\n[2] Determinism: shuffled keys -> SAME hash  ✓")

    # 3. Tamper: one field changed -> different hash
    tampered = dict(record)
    tampered["face_distance"] = 0.5000
    fp_tamp = bv.create_fingerprint(tampered)
    print("\n[3] Tampered record (face_distance 0.0202 -> 0.5000)")
    print("  tampered bytes32_hex:", fp_tamp["bytes32_hex"])
    print("  match?", fp["bytes32_hex"] == fp_tamp["bytes32_hex"], "-> TAMPER DETECTED" if fp["bytes32_hex"] != fp_tamp["bytes32_hex"] else "SAME")

    # 4. Other primitives (image bytes, file, text)
    print("\n[4] Other hashing primitives")
    print("  hash_text('hello'):", bv.hash_text("hello")["hex_hash"])
    print("  hash_bytes(b'hello'):", bv.hash_bytes(b"hello")["hex_hash"])
    print("  hash_json({'a':1,'b':2}):", bv.hash_json({"a": 1, "b": 2})["bytes32_hex"])

    # 5. Editable allowlist demo
    print("\n[5] Hashing is editable – ALLOWED_RECORD_KEYS lives at hashing.py:12")
    print(f"  current allowlist = {bv.ALLOWED_RECORD_KEYS}")
    print("  -> edit that list to include/exclude fields; no chain code changes needed.")

    print("\n" + "=" * 62)
    print(" Offline checks passed. For on-chain demo, run:")
    print("   python -m blockchain_verify.demo_local   # needs eth-tester or Ganache")
    print("=" * 62)


if __name__ == "__main__":
    main()
