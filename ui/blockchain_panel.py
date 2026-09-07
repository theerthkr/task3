"""Row 2 — Blockchain, super simple. Local chain only."""

import streamlit as st
from pathlib import Path

def render_blockchain_config_panel() -> dict:
    st.markdown('<div class="cyber-panel" style="padding:10px 12px;">', unsafe_allow_html=True)
    st.markdown('<div style="display:flex; justify-content:space-between; align-items:center;"><span style="font-family:Share Tech Mono; font-size:11px; color:#00E5FF;">⛓ BLOCKCHAIN — LOCAL SIMULATED</span><span class="cyber-badge cyber-ok">● Ready</span></div>', unsafe_allow_html=True)
    st.caption("Top verified post → SHA-256 `bytes32` → local chain (in-memory, 0 RPC/key). Check `Anchor` before SEARCH. Sepolia: `python -m blockchain_verify.deploy`.")
    st.markdown('</div>', unsafe_allow_html=True)
    return {}

def render_blockchain_result_panel(report: dict) -> None:
    ranked = report.get("ranked") or []
    verified = [r for r in ranked if r.get("verified")]
    is_anchored = report.get("blockchain") is not None
    # Always show top post hash (what would/was anchored) — so user sees what blockchain does
    top = verified[0] if verified else (ranked[0] if ranked else None)
    if not top:
        st.markdown('<div class="cyber-panel" style="border:1px solid #00E5FF; opacity:0.8;">', unsafe_allow_html=True)
        st.markdown('<div style="font-family:Share Tech Mono; font-size:11px; color:#00E5FF;">⛓ BLOCKCHAIN — AWAITING VERIFIED POST</div>', unsafe_allow_html=True)
        st.caption("No verified post yet — hash appears after SEARCH finds a face match ≥0.45.")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    from face_search.blockchain_anchor import fingerprint_for_row
    try:
        fp = fingerprint_for_row(top)
    except Exception as e:
        st.warning(f"Hash error: {e}")
        return
    bc = report.get("blockchain")
    st.markdown('<div class="cyber-panel" style="border:1px solid #00E5FF; padding:12px;">', unsafe_allow_html=True)
    st.markdown('<div style="display:flex; justify-content:space-between; align-items:center;"><span style="font-family:Share Tech Mono; font-size:11px; color:#00E5FF;">⛓ BLOCKCHAIN</span><span class="cyber-badge cyber-ok">Local</span></div>', unsafe_allow_html=True)
    st.caption(f"Top verified → `{top.get('title','')[:38]}…`")
    # Hash box — compact, copyable
    st.markdown('<div style="font-size:10px; color:#7a8a9e; margin-top:6px;">SHA-256 bytes32 (what is stored)</div>', unsafe_allow_html=True)
    st.code(fp['bytes32_hex'], language="text")
    with st.expander("Canonical JSON (hashed)", expanded=False):
        st.code(fp['canonical_json'], language="json")
        st.caption("Deterministic: sorted keys + compact + round(4) → sha256 → bytes32. Edit `blockchain_verify/hashing.py:ALLOWED_RECORD_KEYS` to change.")
    if bc is None:
        st.info("Not anchored yet — check **⛓ Anchor** before SEARCH, then it will store & verify automatically.")
        if st.button("Tamper demo", key="t0", use_container_width=True):
            _tamper(fp, top)
        st.markdown('</div>', unsafe_allow_html=True)
        return
    # Anchored state
    st.caption(f"Contract `0x000…0001` · {bc.get('network','Local')}")
    it = (bc.get("items") or [{}])[0]
    rec = it.get("receipt") if it else None
    if rec:
        st.success(f"✓ Anchored block {rec['block_number']} — verify={it.get('verify')}")
        # hash that was anchored
        st.code(f"{it.get('bytes32_hex')}", language="text")
        c1, c2 = st.columns(2)
        with c1:
            st.caption(f"Tx `{rec['transaction_hash'][:16]}…`")
        with c2:
            st.caption(f"Gas {rec['gas_used']}")
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
    elif it and it.get("error"):
        st.warning(f"Store note: {str(it['error'])[:120]}")
    # Actions
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Re-verify", key="rv", use_container_width=True, help="Reads on-chain verifyRecord(bytes32) — no key needed"):
            with st.spinner("Verifying…"):
                try:
                    import json, tempfile
                    from face_search.blockchain_anchor import verify_report_file
                    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
                        json.dump(report, tf)
                        p = tf.name
                    res = verify_report_file(p)
                    for it2 in res["items"]:
                        ok = it2.get('verify')
                        st.write(f"`{it2['bytes32_hex'][:10]}…` → {'✓ VERIFIED' if ok else '✗ TAMPER'}")
                        if ok and it2.get("on_chain_record"):
                            st.caption(f"On-chain: {it2['on_chain_record']['source_url'][:40]}…")
                        elif not ok:
                            st.caption("Change 1 char → different hash → False")
                    Path(p).unlink(missing_ok=True)
                except Exception as e:
                    st.error(str(e))
    with c2:
        if st.button("Tamper demo (+X)", key="td", use_container_width=True, help="Appends X to title → different bytes32 → verify False"):
            _tamper(fp, top)
    # Etherscan note for Sepolia if they deploy
    st.caption("Local mock — no faucet. For Sepolia Etherscan: `python -m blockchain_verify.deploy --expect-sepolia`")
    st.markdown('</div>', unsafe_allow_html=True)

def _tamper(fp, top):
    from face_search.blockchain_anchor import build_anchor_record
    from blockchain_verify.hashing import create_fingerprint
    tamp = dict(build_anchor_record(top))
    tamp["title"] = (tamp.get("title") or "") + "X"
    ft = create_fingerprint(tamp)
    c1, c2 = st.columns(2)
    with c1: st.code(f"original\n{fp['bytes32_hex']}", language="text")
    with c2: st.code(f"tampered\n{ft['bytes32_hex']}", language="text")
    st.caption("Different hash → verify(tampered)=False → TAMPER DETECTED")
