# task3 — Face Search + Reverse Image + LLM Profiles + Local Blockchain

Cyber-themed face search: upload a face, find where it appears on the web (SerpApi Google Lens), verify matches with InsightFace, rank social profiles with LLM, anchor the top verified post on a local simulated blockchain.

> **Clone & run in 2 minutes — no Sepolia/faucet needed**

```bash
git clone https://github.com/theerthkr/task3.git
cd task3
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt               # SerpApi, Pillow, InsightFace, Streamlit
pip install -r blockchain_verify/requirements.txt  # web3, py-solc-x (local chain is mock, no py-evm needed)
streamlit run ui/app.py
# open http://localhost:8501
```

No `.env` needed for demo. For live features, add keys in the website (top row) or `.env` (see `.env.example`).

---

## What to put where (website → same as `.env`)

| Field in website (Row 1) | Needs key? | What to do |
|---|---|---|
| **SERP API Key** | **Optional** | **Already bundled** (`api_key.json` ships with a working key). **Leave empty** to use it. Only paste your own if you hit `429 / quota` or it stops working. Get free at `serpapi.com` → Dashboard → API Key. |
| **OpenRouter API Key** | **Required for LLM** | **LLM uses ONLY OpenRouter.** Get free at `openrouter.ai/keys` → Create Key → paste as `sk-or-…`. Pick any model in the dropdown. Without it, deterministic fallback still passes `github / bebee / bold.pro` but is weaker, especially for famous people. |
| **LLM model** | Searchable dropdown | Live from `https://openrouter.ai/api/v1/models` — `✓ FREE` = free (`:free` suffix), `PAID` needs credits (else `402`). Search `free`, `llama`, `gemini`. If you get `404 model not found`, free models rotated — pick another. |

> ⏳ **LLM takes a lot of time (20-40s)** — it judges 8-10 profiles × ~600 tokens each. Keep the tab open after clicking **SEARCH**. Face search itself is instant; only LLM is slow. Shown as `LLM fallback` badge when no key, and `⚠️ Important: LLM failing — change model` banner if `404/401/429`.

| Field in Row 2 | Needs key? |
|---|---|
| **Blockchain (Row 2)** | **0 setup** — local simulated chain (in-memory mock). No RPC, no private key, no faucet. Check `⛓ Anchor verified match` before SEARCH to store the top verified post. |

---

## Quick use (website)

1. **Row 1 → Data** — leave `SERP API Key` empty (bundled) unless `429`. Paste `OpenRouter API Key` (`sk-or-…`) and pick a `✓ FREE` model. `🔍 Search models` filters 400+ models.
2. **Browse** PNG/JPG/WEBP ≤5 MB or paste image URL → preview shows `● FACE DETECTED ✓`.
3. **Check** `⛓ Anchor verified match` if you want blockchain (no keys needed).
4. **SEARCH** → wait ~40s (hosting → Lens → InsightFace → LLM). Results appear in two columns:
   - **Left:** `FINALIZED PROFILES` (LLM `is_social_profile=true`, shows all similar — famous people prefer official but also shows fan pages) + `RANKED TOP 10`
   - **Right:** `⛓ BLOCKCHAIN` — `bytes32` + `canonical JSON` + `Anchored block 1 ✓` + `Re-verify` (reads chain) + `Tamper (+X)` demo
5. Download `report.json` / `lens_raw.json`.

CLI alternative:
```bash
# dry run (0 searches, no LLM)
python -m face_search.cli --image chandu.png
# live + LLM + anchor (uses bundled SERP key if SERPAPI_KEY not set)
python -m face_search.cli --image chandu.png --live --anchor
# verify a saved report on local chain
python -m face_search.cli --image chandu.png --verify-anchor runs/<ts>/report.json
# local chain demo (no SERP/LLM needed)
python -m blockchain_verify.demo_local
```

---

## LLM — ONLY OpenRouter

* **Only OpenRouter is supported** (`openrouter.ai/api/v1/chat/completions`). No OpenAI/Bedrock/Anthropic direct.
* Get key: `openrouter.ai/keys` → free `:free` models are free, paid need credits. All models from `https://openrouter.ai/api/v1/models` are searchable in the dropdown (live 400+). 
* If you see `404 model not found` → free model rotated, pick another `:free`. `401` → bad key, `429` → rate-limited, `402` → picked `PAID` without credits.
* Takes time: 10 profiles × LLM = 20-40s. Face verification is fast, LLM is not.

`.env.example`:
```
SERPAPI_KEY=            # leave empty → bundled api_key.json
OPENROUTER_API_KEY=sk-or-...   # required for real LLM
```

---

## SerpApi — bundled, only if needed

`api_key.json` already contains a working SERPAPI key (`f1338a1ff04dacba445d162c5f69f76c148712bfc266aa8aa6a0b7255b156e59` pattern). The website will use it automatically if you leave `SERP API Key` empty. Only paste your own if you see `429`/`quota` or `Search failed: check SERPAPI_KEY`.

---

## Blockchain — how it works (brief)

* **What:** When a matching post is found, its metadata (`title, source, source_url, image_url, face_match, face_distance` → canonical JSON `sorted_keys + round(4)` → `SHA-256` → `bytes32_hex 0x…`) is stored.
* **Where:** **Local simulated chain** (`blockchain_verify/local_chain.py` in-memory mock, `0x000...0001`, no RPC). Satisfies spec “any blockchain may be used — local/simulated”. *Not in depth.*
* **Why:** `storeRecord(bytes32, sourceUrl)` + `verifyRecord(bytes32) → bool` + `getRecord` gives tamper-evident proof. `Re-verify` reads chain, `Tamper (+X)` appends `X` to title → different hash → `✗ NOT FOUND`.

Want Sepolia Etherscan? `python -m blockchain_verify.deploy --expect-sepolia` (needs `SEPOLIA_RPC_URL` free Alchemy `https://dashboard.alchemy.com` + `SEPOLIA_PRIVATE_KEY` + faucet `https://sepoliafaucet.com`).

---

## Replicable / clonable

- **Single source of truth:** `face_search/config.py` (thresholds, model packs), `blockchain_verify/config.py` (chain, gas), `face_search/hosting/imgops_uploader/config.py` (ImgOps)
- **Separation of concerns:** `cli.py` parses, `pipeline.py` orchestrates, `faces.py` embeddings, `serp_client.py` search, `rank.py` ranking, `llm_judge.py` LLM, `blockchain_anchor.py` bridge, `blockchain_verify/*` chain (hashing isolated, stdlib only)
- **Tests:** `pytest tests/ -q` → `22 passed`
- **Runs:** `runs/<ts>/report.json` + `candidates/` + `lens_raw.json` (gitignored except `.gitkeep`)

---

## Structure

```
face_search/        # pipeline, keys, hosting, ranking
ui/app.py           # Streamlit — Row 1 Data, Row 2 Blockchain (side column for results)
ui/blockchain_panel.py  # Anchor/verify/tamper UI
blockchain_verify/  # hashing.py (editable), local_chain.py, deploy.py, VerificationRegistry.sol
tests/  dryruns/  runs/
```

License: MIT
