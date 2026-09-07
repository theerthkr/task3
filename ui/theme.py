CYBER_CSS = r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Share+Tech+Mono&display=swap');
:root{
  --bg:#070A0F;
  --panel:#0F1420;
  --panel-2:#0B1020;
  --border:#1a2a3a;
  --border-glow:rgba(0,229,255,0.35);
  --text:#E6F0FF;
  --muted:#7a8a9e;
  --cyan:#00E5FF;
  --magenta:#FF2E93;
  --ok:#00FF88;
  --warn:#FFB800;
  --err:#FF3B30;
}
html, body, [class*="stApp"]{ background: var(--bg) !important; color: var(--text) !important; }
[data-testid="stAppViewContainer"]{ background: radial-gradient(1200px 600px at 50% -10%, rgba(0,229,255,0.08), transparent 60%), var(--bg) !important; }
section[data-testid="stSidebar"]{ background: var(--panel) !important; border-right:1px solid var(--border) !important; }
h1,h2,h3{ font-family:"Share Tech Mono", monospace !important; letter-spacing:0.06em; color: var(--text) !important; text-transform: uppercase; }
p, label, span, div{ font-family:"JetBrains Mono", monospace; }
.stTextInput input, .stTextArea textarea{
  background: var(--panel) !important; color: var(--text) !important;
  border:1px solid var(--border) !important; border-radius:10px !important;
}
.stFileUploader [data-testid="stFileUploaderDropzone"]{
  background: var(--panel) !important; border:1px dashed var(--border) !important; border-radius:12px !important;
}
div[data-testid="stFileUploaderDropzone"]:hover{ border-color: var(--cyan) !important; box-shadow: 0 0 0 1px var(--border-glow), 0 0 18px rgba(0,229,255,0.15) !important; }
.stButton>button{
  background: linear-gradient(180deg, #0f1f33, #0a1426) !important;
  color: var(--cyan) !important; border:1px solid var(--border) !important;
  border-radius:10px !important; font-family:"Share Tech Mono" !important; letter-spacing:0.05em;
  text-transform: uppercase; transition: all 0.15s;
}
.stButton>button:hover{ border-color: var(--cyan) !important; box-shadow: 0 0 14px rgba(0,229,255,0.35) !important; transform: translateY(-1px); }
.stButton>button[kind="primary"]{
  background: var(--cyan) !important; color:#001018 !important; border-color: var(--cyan) !important; font-weight:700;
}
.cyber-panel{
  background: var(--panel); border:1px solid var(--border); border-radius:14px; padding:14px 16px;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.02), 0 8px 24px rgba(0,0,0,0.35);
}
.cyber-grid{ background-image: linear-gradient(rgba(0,229,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(0,229,255,0.04) 1px, transparent 1px); background-size: 28px 28px; }
.cyber-title{ color: var(--cyan) !important; text-shadow: 0 0 10px rgba(0,229,255,0.6); }
.cyber-badge{ display:inline-block; padding:2px 8px; border:1px solid var(--border); border-radius:999px; font-size:11px; color:var(--muted); }
.cyber-ok{ color: var(--ok) !important; border-color: rgba(0,255,136,0.35) !important; }
.cyber-err{ color: var(--err) !important; border-color: rgba(255,59,48,0.35) !important; }
.cyber-warn{ color: var(--warn) !important; }
.rank-card{ background: var(--panel-2); border:1px solid var(--border); border-radius:12px; padding:12px; margin-bottom:10px; }
.rank-card:hover{ border-color: rgba(0,229,255,0.4); box-shadow: 0 0 12px rgba(0,229,255,0.12); }
a{ color: var(--cyan) !important; }
hr{ border-color: var(--border) !important; }
</style>
"""
