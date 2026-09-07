"""Streamlit UI — two clean rows: ROW 1 Data, ROW 2 Blockchain. Strictly separate from face_search core."""

from __future__ import annotations
import sys
from pathlib import Path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(_PROJECT_ROOT))

import io, os, tempfile, json
import streamlit as st
from PIL import Image, ImageDraw
from face_search.hosting.imgops_uploader.config import DEFAULT_MAX_SIZE_BYTES as HOST_MAX_BYTES
from face_search import faces
from face_search.hosting.imgops_uploader.exceptions import ImgOpsValidationError
from ui.theme import CYBER_CSS
from ui.blockchain_panel import render_blockchain_config_panel

st.set_page_config(page_title="FACE SEARCH — CYBER", page_icon="◉", layout="centered", initial_sidebar_state="collapsed")
st.markdown(CYBER_CSS, unsafe_allow_html=True)
st.markdown('<div class="cyber-panel cyber-grid" style="text-align:center; margin-bottom:14px;"><div style="font-family:Share Tech Mono; font-size:22px; letter-spacing:0.18em;" class="cyber-title">◉ FACE SEARCH — CYBER</div><div style="color:#7a8a9e; font-size:11px; letter-spacing:0.12em; margin-top:4px;">URL-ONLY · SERP LENS · INSIGHTFACE · TOP 10 · 1H HOST</div></div>', unsafe_allow_html=True)

if "report" not in st.session_state: st.session_state.report=None

# ── ROW 1 — DATA ───────────────────────────────────────────────────────────────
st.markdown('<div class="cyber-panel">', unsafe_allow_html=True)
st.markdown('<div style="font-family:Share Tech Mono; font-size:12px; letter-spacing:0.12em; color:#00E5FF;">━━ ROW 1 — DATA (SEARCH) ━━</div>', unsafe_allow_html=True)

# Keys: SERP (required) + OpenRouter (optional, needed for LLM)
c1, c2, c3 = st.columns([1,1,0.7])
with c1:
    serp_key = st.text_input("SERP API Key (optional)", type="password", placeholder="leave empty — bundled key will be used", help="SERP API is already bundled in the codebase (api_key.json). Leave empty to use it. Only paste your own if you hit quota/429 or it stops working. Stored as SERPAPI_KEY.")
with c2:
    openrouter_key = st.text_input("OpenRouter API Key *", type="password", placeholder="sk-or-… required for LLM", help="LLM uses ONLY OpenRouter (openrouter.ai/keys — free :free models). Pick any model below. Without this, fallback heuristics still work but are weaker.")
with c3:
    st.markdown('<div style="height:22px"></div>', unsafe_allow_html=True)
    if openrouter_key and openrouter_key.strip(): st.markdown('<div class="cyber-badge cyber-ok">LLM ON</div>', unsafe_allow_html=True)
    else: st.markdown('<div class="cyber-badge cyber-warn">LLM needs key</div>', unsafe_allow_html=True); st.caption("⚠️ LLM takes 20-40s — leave page open after SEARCH.")
if serp_key and serp_key.strip(): os.environ["SERPAPI_KEY"]=serp_key.strip()
# else: keep bundled api_key.json — no env override, SerpApi will use bundled key
if openrouter_key and openrouter_key.strip(): os.environ["OPENROUTER_API_KEY"]=openrouter_key.strip()
# Highlight: LLM time warning (top)
st.info("⏳ **LLM takes a lot of time (20-40s) when it works** — OpenRouter judges 8-10 profiles ×600 tokens. Keep tab open after SEARCH. If no `OPENROUTER_API_KEY`, fallback still passes `github/bebee/bold.pro`. SerpApi: leave empty to use bundled key, only add yours if 429.", icon="⚠️")

# LLM model — searchable, fetches all from OpenRouter
from face_search.llm_judge import FREE_MODELS, fetch_models, DEFAULT_MODEL
try:
    _all_models = fetch_models()
except Exception:
    _all_models = [{"id": m["id"], "name": m["id"], "is_free": True, "context_length": m["context"], "raw": m} for m in FREE_MODELS]

# Search filter
m_search = st.text_input("🔍 Search models (type to filter, e.g. llama, gemini, free, 128k)", placeholder="leave empty for free top picks", help="Fetches live from https://openrouter.ai/api/v1/models — all models, free first.")
if m_search.strip():
    q = m_search.strip().lower()
    _filtered = [m for m in _all_models if q in m["id"].lower() or q in m["name"].lower()]
else:
    _filtered = _all_models

def _m_label(m):
    free = "✓ FREE" if m.get("is_free") else "PAID"
    ctx = m.get("context_length") or "?"
    return f"{m['id']} · {free} · ctx {ctx}"

try:
    _def_idx = next(i for i, m in enumerate(_filtered) if m["id"] == DEFAULT_MODEL)
except StopIteration:
    _def_idx = 0

llm_model = st.selectbox(
    f"LLM model ({len(_filtered)}/{len(_all_models)} shown — live from OpenRouter) — ONLY OpenRouter",
    options=[m["id"] for m in _filtered],
    index=_def_idx if _filtered else 0,
    format_func=lambda mid: next((_m_label(m) for m in _filtered if m["id"] == mid), mid),
    help="ONLY OpenRouter — pick any :free model (free) or paid if you have credits. Free models rotate; if 404 pick another. ~600 tokens per profile, so 8-10 profiles = 20-40s.",
)
st.caption("⏳ LLM takes a lot of time (20-40s for 10 profiles) — keep tab open after SEARCH. Works ONLY via OpenRouter.")
_selected_is_free = next((m.get("is_free") for m in _filtered if m["id"] == llm_model), True)
if not _selected_is_free:
    st.warning("⚠️ You selected a PAID model — needs OpenRouter credits or 402 error. For free, pick a :free model or search 'free'.")

st.divider()
# Image input
st.markdown('<div style="font-family:Share Tech Mono; font-size:12px; color:#00E5FF;">⚡ INPUT — BROWSE OR PASTE LINK</div>', unsafe_allow_html=True)

def _validate_and_stage_file(uploaded):
    if uploaded is None: return None, None
    data=uploaded.getvalue()
    if len(data)>HOST_MAX_BYTES: return None, f"File exceeds 5 MB ({len(data)/1024/1024:.2f} MB)"
    suffix=Path(uploaded.name).suffix or ".png"
    tf=tempfile.NamedTemporaryFile(delete=False, suffix=suffix); tf.write(data); tf.close(); return tf.name, None
def _thumb_html(run_dir, row):
    import base64
    local=Path(run_dir or "")/"candidates"/f"candidate_{row.get('position')}.jpg"
    try:
        if local.is_file():
            img=Image.open(local).convert("RGB"); img.thumbnail((72,72)); buf=io.BytesIO(); img.save(buf, format="JPEG"); return f'<img src="data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}" width="72" style="border-radius:8px; border:1px solid #1a2a3a;" />'
    except: pass
    hotlink=row.get("thumbnail_url") or ""
    return f'<img src="{hotlink}" width="72" style="border-radius:8px; border:1px solid #1a2a3a;" />' if hotlink.startswith("http") else ""

up=st.file_uploader("Drop PNG/JPG/WEBP (≤5 MB)", type=["png","jpg","jpeg","webp"], label_visibility="collapsed")
browse_path, browse_err=None,None
if up is not None:
    browse_path,browse_err=_validate_and_stage_file(up)
    if browse_err: st.markdown(f'<div class="cyber-badge cyber-err">{browse_err}</div>', unsafe_allow_html=True)

link_in=st.text_input("Or paste image URL", placeholder="https://…", label_visibility="collapsed")
link_path, link_err=None,None
if link_in.strip():
    from face_search import images
    tf=tempfile.NamedTemporaryFile(delete=False, suffix=".jpg"); tf.close()
    ok=images.download_image(link_in.strip(), tf.name)
    if not ok: link_err="Link unreachable or not an image"
    else: link_path=tf.name
    if link_err: st.markdown(f'<div class="cyber-badge cyber-err">{link_err}</div>', unsafe_allow_html=True)
    elif link_path: st.markdown('<div class="cyber-badge cyber-ok">Link OK</div>', unsafe_allow_html=True)

query_path=None; input_error=None
if link_path and browse_path: st.warning("Both provided – using link."); query_path=link_path
elif link_path: query_path=link_path; input_error=link_err
elif browse_path: query_path=browse_path; input_error=browse_err
can_proceed=query_path is not None and input_error is None

# Preview — face models download on first run (~90MB buffalo_l, 20-30s)
if query_path:
    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    # First-run warning: InsightFace downloads to .insightface_cache
    _model_dir = Path(".insightface_cache/models/buffalo_l")
    if not _model_dir.exists() or not any(_model_dir.glob("*.onnx")):
        st.warning("⏳ First run: face models (~90MB `buffalo_l`) downloading in background — preview will take 20-30s. Keep tab open, do NOT reload.", icon="⚠️")
        st.caption("Models cache to `.insightface_cache/` — next runs are instant.")
    try:
        pil=Image.open(query_path).convert("RGB"); pil.thumbnail((560,560))
        import cv2
        orig=cv2.imread(query_path)
        from face_search import faces as _faces
        with st.spinner("Loading face models (first run 20-30s)…"):
            app=_faces._get_app()
        bboxes=[f.bbox for f in app.get(orig)] if orig is not None else []
        # scale to thumbnail
        if bboxes:
            h0,w0=orig.shape[:2]; sx=pil.size[0]/w0; sy=pil.size[1]/h0
            bboxes=[[b[0]*sx,b[1]*sy,b[2]*sx,b[3]*sy] for b in bboxes]
        # draw
        draw=ImageDraw.Draw(pil)
        for x1,y1,x2,y2 in bboxes: draw.rectangle([int(x1),int(y1),int(x2),int(y2)], outline="#00E5FF", width=3)
        st.image(pil, caption=f"Faces: {len(bboxes)}", width=380)
        if bboxes: st.markdown('<div class="cyber-badge cyber-ok">● FACE DETECTED ✓</div>', unsafe_allow_html=True)
        else: st.markdown('<div class="cyber-badge cyber-err">○ NO FACE – cannot search</div>', unsafe_allow_html=True); can_proceed=False
    except Exception as e: st.markdown(f'<div class="cyber-badge cyber-err">Preview: {e}</div>', unsafe_allow_html=True); can_proceed=False

st.markdown('</div>', unsafe_allow_html=True)  # end ROW 1

# ── ROW 2 — BLOCKCHAIN ────────────────────────────────────────────────────────
render_blockchain_config_panel()

# ── SEARCH ────────────────────────────────────────────────────────────────────
st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
anchor_wanted=st.checkbox("⛓ Anchor verified match on-chain (needs RPC + contract, private key for write; no key = hash-only)", value=False, help="When checked, top verified post is hashed (canonical JSON) -> bytes32 and stored via VerificationRegistry.storeRecord. Without key, hash still computed for tamper demo.")
col_go,col_info=st.columns([0.35,0.65])
with col_go: go=st.button("▶ SEARCH", type="primary", disabled=not can_proceed, use_container_width=True)
with col_info: st.caption("URL-only · 1 search credit · Top 10 · LLM passes github/bebee/bold.pro immediately, shows all similar")

if go:
    if not can_proceed: st.error("Fix input first")
    else:
        from face_search.pipeline import run as pipeline_run
        try:
            # Highlight long wait
            if openrouter_key and openrouter_key.strip():
                st.warning("⏳ LLM is ON — this will take 20-40s (judging 10 profiles) — **do NOT close tab**. Face search is instant, LLM is slow.", icon="⚠️")
            with st.spinner("Hosting → Lens → verifying 10… → LLM judging (20-40s if key set) — please wait…"):
                if link_path and query_path==link_path: report=pipeline_run(image="", image_url=link_in.strip(), top_n=10, live=True, llm_model=llm_model, anchor=anchor_wanted)
                else: report=pipeline_run(image=query_path, image_url="", top_n=10, live=True, llm_model=llm_model, anchor=anchor_wanted)
            st.session_state.report=report
            # Post-search highlight
            if report.get("llm_status","ok").startswith("error"):
                st.error(f"⚠️ LLM took time but failed — {report.get('llm_note')} — showing fallback profiles. Try another :free model.")
            elif report.get("llm_status")=="fallback_no_key":
                st.info("LLM was fallback (no key) — still passed github/bebee/bold.pro via heuristics. Add OpenRouter key for better famous-people verdicts.")
            else:
                st.success("✓ Search done — LLM finished (if key was set, check FINALIZED PROFILES).")
            bc=report.get("blockchain")
            if anchor_wanted and bc and bc.get("items") and bc["items"][0].get("receipt"): st.toast(f"Anchored {bc['items'][0]['bytes32_hex'][:10]}…", icon="⛓")
        except ImgOpsValidationError as e: st.error(f"Image too large: {e}")
        except Exception as e: st.error(f"Search failed: {e} – check SERPAPI_KEY / .env")

# ── RESULTS — two columns: LEFT data, RIGHT blockchain ─────────────────────────
report=st.session_state.get("report")
if report:
    # header bar
    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-family:Share Tech Mono; font-size:11px; color:#7a8a9e;">RESULTS — {report.get("mode")} · Candidates {report.get("candidates_found")} · Ranked {len(report.get("ranked",[]))} · Verified {report.get("verified")} · searches {report.get("searches_spent")} · model {report.get("llm_model","")[:22]}</div>', unsafe_allow_html=True)
    if report.get("query",{}).get("hosted_url"): st.caption(f"Hosted URL (1h): {report['query']['hosted_url']}")
    llm_status=report.get("llm_status","ok")
    llm_note=report.get("llm_note","")
    if llm_status.startswith("error"):
        st.error(f"⚠️ LLM failing — {llm_note} — face search is perfect, outputs are fallback. Change model above.")
    elif llm_status=="fallback_no_key":
        st.warning(f"LLM fallback — {llm_note}")

    col_data, col_chain = st.columns([1.35, 0.85], gap="medium")

    with col_data:
        st.markdown('<div class="cyber-panel">', unsafe_allow_html=True)
        st.markdown('<div style="font-family:Share Tech Mono; font-size:11px; color:#00E5FF;">━━ DATA — FINALIZED PROFILES ━━</div>', unsafe_allow_html=True)
        finalized=report.get("finalized_profiles") or []
        if finalized:
            for i,row in enumerate(finalized[:10],1):
                llm=row.get("llm",{}); sim=row.get("similarity"); simt=f"{sim:.4f}" if sim is not None else "—"
                st.markdown(f"<div class='rank-card' style='border-color: rgba(0,255,136,0.5);'><div style='font-family:Share Tech Mono; font-size:11px; color:#00FF88;'>[{i}] ✓ {simt} — {row.get('platform')} — {row.get('source')}</div><div style='font-size:12px; color:#E6F0FF;'>{row.get('title')}</div><div style='font-size:11px;'><a href='{row.get('page_url')}' target='_blank'>{row.get('page_url')}</a></div><div style='font-size:10px; color:#7a8a9e;'>{llm.get('reason','')[:110]}</div></div>", unsafe_allow_html=True)
        else:
            if report.get("verified")==0: st.info("No verified faces — try another image or lower threshold.")
            else: st.caption("No finalized — showing ranked below. Add OpenRouter key for better LLM.")
        st.markdown('<div style="font-family:Share Tech Mono; font-size:11px; color:#7a8a9e; margin-top:10px;">RANKED TOP 10</div>', unsafe_allow_html=True)
        ranked=report.get("ranked") or []
        run_dir=report.get("run_dir","")
        if not ranked: st.info("No ranked.")
        else:
            for i,row in enumerate(ranked[:8],1):
                sim=row.get("similarity"); simt=f"{sim:.4f}" if sim is not None else "—"
                verified="✓" if row.get("verified") else "·"; has_face="●" if row.get("has_face") else "○"
                llm=row.get("llm",{}); badge=" ✓ profile" if llm.get("is_social_profile") else ""; bcol="#00FF88" if llm.get("is_social_profile") else "#7a8a9e"
                reason=llm.get("reason","no verdict")
                if "404" in reason: reason="⚠️ 404 change model | "+reason
                elif "401" in reason: reason="⚠️ 401 check key | "+reason
                color="#00FF88" if row.get("verified") else ("#7a8a9e" if not row.get("has_face") else "#00E5FF")
                thumb=_thumb_html(run_dir,row)
                st.markdown(f"<div class='rank-card' style='padding:8px;'><div style='display:flex; gap:8px;'><div>{thumb}</div><div style='flex:1;'><div style='font-size:11px; color:{color};'>[{i}] {verified}{has_face} {simt}<span style='color:{bcol}'>{badge}</span> {row.get('platform')}</div><div style='font-size:11px; color:#E6F0FF;'>{row.get('title')[:70]}</div><div style='font-size:10px;'><a href='{row.get('page_url')}' target='_blank'>link</a> <span style='color:#7a8a9e;'>{reason[:90]}</span></div></div></div></div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        # downloads inside left col
        import json
        c1,c2=st.columns(2)
        with c1: st.download_button("⬇ report.json", data=json.dumps(report, indent=2), file_name="report.json", mime="application/json", use_container_width=True)
        with c2:
            raw=Path(report.get("run_dir",""))/"lens_raw.json"
            if raw.exists(): st.download_button("⬇ lens_raw.json", data=raw.read_bytes(), file_name="lens_raw.json", use_container_width=True)

    with col_chain:
        # Blockchain column — fixed, clean, beside data
        try:
            from ui.blockchain_panel import render_blockchain_result_panel
            # need to ensure it renders inside this column
            render_blockchain_result_panel(report)
        except Exception as e:
            st.error(f"Chain error: {e}")
        st.caption(f"Run dir: {report.get('run_dir')}")
        st.caption("Local simulated chain — no Sepolia/faucet needed. Sepolia: `python -m blockchain_verify.deploy --expect-sepolia`")

st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
st.caption("Row 1 = data (search + finalized profiles). Row 2 = blockchain (hash + anchor + re-verify). URL-only · 5 MB · Top 10")
