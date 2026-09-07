"""Streamlit UI — cyber black, minimal, strictly separate from face_search core.

Only imports inward: face_search.*. No core file imports ui.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make project root importable when Streamlit runs as `streamlit run ui/app.py`
# Streamlit adds the script dir (ui/) to sys.path, not the project root, so
# `import face_search` would fail without this.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import io
import os
import tempfile

import streamlit as st
from PIL import Image, ImageDraw

from face_search.hosting.imgops_uploader.config import DEFAULT_MAX_SIZE_BYTES as HOST_MAX_BYTES
from face_search import faces
from face_search.hosting.imgops_uploader.exceptions import ImgOpsValidationError

from ui.theme import CYBER_CSS

# ── page ─────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="FACE SEARCH — CYBER", page_icon="◉", layout="centered", initial_sidebar_state="collapsed")
st.markdown(CYBER_CSS, unsafe_allow_html=True)

st.markdown("""
<div class="cyber-panel cyber-grid" style="text-align:center; margin-bottom:14px;">
  <div style="font-family:'Share Tech Mono'; font-size:22px; letter-spacing:0.18em;" class="cyber-title">◉ FACE SEARCH — CYBER</div>
  <div style="color:#7a8a9e; font-size:11px; letter-spacing:0.12em; margin-top:4px;">URL-ONLY · SERP LENS · INSIGHTFACE · TOP 10 · 1H HOST</div>
</div>
""", unsafe_allow_html=True)

# ── session ──────────────────────────────────────────────────────────────────
if "query_path" not in st.session_state:
    st.session_state.query_path = None
if "query_bboxes" not in st.session_state:
    st.session_state.query_bboxes = []
if "hosted_url" not in st.session_state:
    st.session_state.hosted_url = None
if "report" not in st.session_state:
    st.session_state.report = None

# ── settings row: 2 key fields + headless toggle ────────────────────────────
st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
c1, c2, c3 = st.columns([1, 1, 0.55])
with c1:
    serp_key = st.text_input("SERP API Key", type="password", placeholder="serpapi key", help="Used as SERPAPI_KEY for Lens")
with c2:
    openrouter_key = st.text_input("OpenRouter API Key", type="password", placeholder="openrouter key", help="For future LLM enrichment")
with c3:
    st.markdown('<div style="height:22px"></div>', unsafe_allow_html=True)
    headless = st.toggle("Headless browser", value=True, help="When browser automation exists, headless vs headed. Stored, no-op today (core is requests-only).")

if serp_key:
    os.environ["SERPAPI_KEY"] = serp_key.strip()
if openrouter_key:
    os.environ["OPENROUTER_API_KEY"] = openrouter_key.strip()
st.session_state["headless"] = headless

# ── helpers ──────────────────────────────────────────────────────────────────
def _face_bboxes_for_preview(img_path: str):
    """Return list of bboxes [x1,y1,x2,y2] using InsightFace without full pipeline."""
    try:
        from insightface.app import FaceAnalysis
        # reuse faces._get_app but also get raw faces with bbox
        app = faces._get_app()
        import cv2
        img = cv2.imread(img_path)
        if img is None:
            return []
        raw = app.get(img)
        return [f.bbox for f in raw]
    except Exception:
        return []

def _draw_facebox(pil_img: Image.Image, bboxes) -> Image.Image:
    if not bboxes:
        return pil_img
    draw = ImageDraw.Draw(pil_img)
    w, h = pil_img.size
    for (x1, y1, x2, y2) in bboxes:
        # map from original cv2 coords: assume pil size == cv2 size (we saved same file)
        x1, y1, x2, y2 = map(int, (x1, y1, x2, y2))
        # cyber neon box
        for off, color, width in [(0, "#00E5FF", 2), (1, "rgba(0,229,255,0.25)", 6)]:
            pad = off
            # need rgba for outer glow if using RGBA image
        draw.rectangle([x1, y1, x2, y2], outline="#00E5FF", width=3)
        # corner ticks
        tick = 14
        for (x, y, dx, dy) in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
            draw.line([x, y, x+dx*tick, y], fill="#00E5FF", width=2)
            draw.line([x, y, x, y+dy*tick], fill="#00E5FF", width=2)
    return pil_img

def _validate_and_stage_file(uploaded) -> tuple[str | None, str | None]:
    """Return (temp_path, error)."""
    if uploaded is None:
        return None, None
    data = uploaded.getvalue()
    if len(data) > HOST_MAX_BYTES:
        return None, f"File exceeds 5 MB ({len(data)/1024/1024:.2f} MB) — compress or reduce size."
    # keep extension
    suffix = Path(uploaded.name).suffix or ".png"
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tf.write(data)
    tf.close()
    return tf.name, None

def _validate_link(url: str) -> tuple[str | None, str | None]:
    url = (url or "").strip()
    if not url:
        return None, None
    if not url.startswith("http"):
        return None, "Link must start with http(s)://"
    # use images.download_image to temp to validate reachability + is image
    from face_search import images
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    tf.close()
    ok = images.download_image(url, tf.name)
    if not ok:
        try:
            os.unlink(tf.name)
        except Exception:
            pass
        return None, "Link unreachable or not an image — check URL."
    return tf.name, None

# ── input: browse + paste (mutually exclusive, link takes precedence if both) ─
st.markdown('<div class="cyber-panel">', unsafe_allow_html=True)
st.markdown('<div style="font-family:Share Tech Mono; font-size:12px; letter-spacing:0.12em; color:#00E5FF;">⚡ INPUT — BROWSE OR PASTE LINK</div>', unsafe_allow_html=True)
tab_browse, tab_link = st.tabs(["▣ Browse image", "↗ Paste link"])
browse_path, link_path = None, None
browse_err, link_err = None, None

with tab_browse:
    up = st.file_uploader("Drop PNG/JPG/WEBP (≤5 MB)", type=["png","jpg","jpeg","webp"], label_visibility="collapsed")
    if up is not None:
        browse_path, browse_err = _validate_and_stage_file(up)
        if browse_err:
            st.markdown(f'<div class="cyber-badge cyber-err">{browse_err}</div>', unsafe_allow_html=True)
with tab_link:
    link_in = st.text_input("Image URL", placeholder="https://...", label_visibility="collapsed")
    if link_in.strip():
        with st.spinner("Checking link…"):
            link_path, link_err = _validate_link(link_in)
        if link_err:
            st.markdown(f'<div class="cyber-badge cyber-err">{link_err}</div>', unsafe_allow_html=True)
        elif link_path:
            st.markdown('<div class="cyber-badge cyber-ok">Link OK — image reachable</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# decide query path (link precedence)
query_path = None
input_error = None
if link_path and browse_path:
    # both provided — prefer link, warn
    st.warning("Both browse and link provided — using link. Clear one to avoid confusion.")
    query_path = link_path
elif link_path:
    query_path = link_path
    input_error = link_err
elif browse_path:
    query_path = browse_path
    input_error = browse_err

can_proceed = query_path is not None and input_error is None

# ── preview + facebox ────────────────────────────────────────────────────────
if query_path:
    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
    st.markdown('<div class="cyber-panel">', unsafe_allow_html=True)
    st.markdown('<div style="font-family:Share Tech Mono; font-size:11px; color:#7a8a9e;">PREVIEW — FACE CHECK</div>', unsafe_allow_html=True)
    try:
        pil = Image.open(query_path).convert("RGB")
        # keep preview reasonably sized
        pil.thumbnail((560, 560))
        # bboxes need original scale — use the staged file (same dims as thumbnail after mapping? use pil size)
        # For simplicity map bbox from cv2 original (same file) to thumbnail scale
        import cv2
        orig = cv2.imread(query_path)
        h0, w0 = orig.shape[:2] if orig is not None else pil.size[::-1]
        bboxes = _face_bboxes_for_preview(query_path)
        # scale bboxes to thumbnail
        if bboxes and pil.size != (w0, h0):
            sx = pil.size[0] / w0
            sy = pil.size[1] / h0
            bboxes = [[b[0]*sx, b[1]*sy, b[2]*sx, b[3]*sy] for b in bboxes]
            st.session_state.query_bboxes = bboxes
        else:
            st.session_state.query_bboxes = bboxes
        st.session_state.query_path = query_path
        boxed = _draw_facebox(pil.copy(), bboxes)
        st.image(boxed, caption=f"Faces detected: {len(bboxes)}", width=420)
        if bboxes:
            st.markdown('<div class="cyber-badge cyber-ok">● FACE DETECTED — APPROVED ✓</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="cyber-badge cyber-err">○ NO FACE DETECTED — cannot search</div>', unsafe_allow_html=True)
            can_proceed = False
    except Exception as e:
        st.markdown(f'<div class="cyber-badge cyber-err">Preview failed: {e}</div>', unsafe_allow_html=True)
        can_proceed = False
    st.markdown('</div>', unsafe_allow_html=True)
else:
    if input_error:
        st.markdown(f'<div class="cyber-badge cyber-err">{input_error}</div>', unsafe_allow_html=True)

# ── search ───────────────────────────────────────────────────────────────────
st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
col_go, col_info = st.columns([0.38, 0.62])
with col_go:
    go = st.button("▶ SEARCH — TOP 10", type="primary", disabled=not can_proceed, use_container_width=True)
with col_info:
    st.markdown('<div style="color:#7a8a9e; font-size:11px; padding-top:8px;">URL-only · Serp Lens · 1 search credit · Top 10 ranked</div>', unsafe_allow_html=True)

if go:
    if not can_proceed:
        st.error("Fix input errors before searching.")
    else:
        # prefer link url directly if user pasted link, else host the staged file
        from face_search.pipeline import run as pipeline_run
        try:
            with st.spinner("Hosting → Lens → verifying 10 candidates…"):
                # if link was used, pass image_url directly (no re-host)
                if link_path and query_path == link_path:
                    report = pipeline_run(image="", image_url=link_in.strip(), top_n=10, live=True)
                else:
                    report = pipeline_run(image=query_path, image_url="", top_n=10, live=True)
            st.session_state.report = report
            st.session_state.hosted_url = report.get("query", {}).get("hosted_url")
        except ImgOpsValidationError as e:
            st.error(f"Image too large for host (5 MB limit): {e}")
        except Exception as e:
            st.error(f"Search failed: {e}")

# ── results ──────────────────────────────────────────────────────────────────
report = st.session_state.get("report")
if report:
    hosted = report.get("query", {}).get("hosted_url")
    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
    st.markdown('<div class="cyber-panel">', unsafe_allow_html=True)
    st.markdown(f'<div style="font-family:Share Tech Mono; font-size:11px; color:#7a8a9e;">RESULTS — {report.get("mode")} · Candidates {report.get("candidates_found")} · Ranked {len(report.get("ranked",[]))} · Verified {report.get("verified")} · searches {report.get("searches_spent")}</div>', unsafe_allow_html=True)
    if hosted:
        st.caption(f"Hosted URL (1h): {hosted}")
    ranked = report.get("ranked") or []
    if not ranked:
        st.info("No ranked results.")
    else:
        for i, row in enumerate(ranked[:10], 1):
            sim = row.get("similarity")
            sim_txt = f"{sim:.4f}" if sim is not None else "—"
            verified = "✓" if row.get("verified") else "·"
            has_face = "●" if row.get("has_face") else "○"
            color = "#00FF88" if row.get("verified") else ("#7a8a9e" if not row.get("has_face") else "#00E5FF")
            st.markdown(f"""
<div class="rank-card">
  <div style="display:flex; justify-content:space-between; align-items:center;">
    <div style="font-family:Share Tech Mono; font-size:12px; color:{color};">[{i}] {verified} {has_face} sim {sim_txt} — {row.get('platform')} — {row.get('source')}</div>
    <div style="font-size:11px; color:#7a8a9e;">{row.get('match_kind')}</div>
  </div>
  <div style="font-size:13px; color:#E6F0FF; margin-top:4px;">{row.get('title')}</div>
  <div style="font-size:11px; margin-top:4px;"><a href="{row.get('page_url')}" target="_blank">{row.get('page_url')}</a></div>
  <div style="font-size:11px; color:#7a8a9e;">thumb: <a href="{row.get('thumbnail_url')}" target="_blank">thumb</a> · image: <a href="{row.get('image_url')}" target="_blank">image</a></div>
</div>
""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    # downloads
    import json
    cdl1, cdl2 = st.columns(2)
    with cdl1:
        st.download_button("⬇ report.json", data=json.dumps(report, indent=2), file_name="report.json", mime="application/json", use_container_width=True)
    with cdl2:
        # lens_raw lives in run_dir
        raw_path = Path(report.get("run_dir", "")) / "lens_raw.json"
        if raw_path.exists():
            st.download_button("⬇ lens_raw.json", data=raw_path.read_bytes(), file_name="lens_raw.json", use_container_width=True)
        else:
            st.caption("lens_raw.json in run dir")
    st.caption(f"Run dir: {report.get('run_dir')}")

st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
st.caption("Cyber theme · URL-only · 5 MB host limit · Top 10 default · Headless toggle stored (no-op until browser fetcher exists)")
