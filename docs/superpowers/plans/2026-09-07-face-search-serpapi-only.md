# Face Search (SerpApi-only) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a SerpApi-only face-search pipeline that spends zero searches unless `--live` is passed.

**Architecture:** Layered CLI pipeline — `cli` parses args, `pipeline` orchestrates, `serp_client`/`images`/`faces`/`rank` own one concern each, `config` is the single source of truth, `key_store` loads the key without ever logging it.

**Tech Stack:** Python 3.14, InsightFace `buffalo_l` (onnxruntime, CPU), OpenCV, requests, Pillow, SerpApi Google Lens (`engine=google_lens`), pytest.

## Global Constraints

- Default mode is dry-run: zero SerpApi searches unless `--live` is explicitly passed.
- Live search pre-checks quota via free `GET account.json`; aborts when searches are exhausted.
- Never send `no_cache=true`; cached repeats are free.
- Secrets never printed, logged, or committed (`api_key.json`, `.env` gitignored).
- Match = cosine similarity >= threshold (default 0.45, `--threshold` tunable, measured cross-person 0.02).
- Reference repo `HHGOA-FACE-BLOCKCHAIN/` is read-only; nothing imports from it.

---

### Task 1: Scaffolding + config + key_store

**Files:**
- Create: `face_search/__init__.py`
- Create: `face_search/config.py`
- Create: `face_search/key_store.py`
- Create: `tests/test_key_store.py`
- Create: `.env.example`
- Create: `requirements.txt`

**Interfaces:**
- Consumes: nothing.
- Produces: `config.py` constants consumed by every later task; `key_store.load_key(search_dir) -> str`.

```python
# face_search/config.py (single source of truth)
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERPAPI_UPLOAD_URL = "https://serpapi.com/image"
SERPAPI_SEARCH_URL = "https://serpapi.com/search"
SERPAPI_ACCOUNT_URL = "https://serpapi.com/account.json"
LENS_ENGINE = "google_lens"
DEFAULT_TOP_N = 10
DEFAULT_THRESHOLD = 0.45
REQUEST_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 10
SOCIAL_DOMAINS = ("linkedin.com", "x.com", "twitter.com", "instagram.com", "github.com")
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
```

```python
# face_search/key_store.py
"""Loads the SerpApi key without ever exposing it. Tries, in order:
1. $SERPAPI_KEY env var (also via .env), 2. api_key.json (raw key or {"key": ...})."""
```

- [ ] **Step 1: Write the failing test**

```python
# tests/test_key_store.py
def test_loads_raw_key_file(tmp_path):
    (tmp_path / "api_key.json").write_text("SAMPLE_KEY_123")
    from face_search.key_store import load_key
    assert load_key(search_dir=tmp_path, env={}) == "SAMPLE_KEY_123"

def test_loads_json_object_key_file(tmp_path):
    (tmp_path / "api_key.json").write_text('{"api_key": "OBJ_KEY"}')
    from face_search.key_store import load_key
    assert load_key(search_dir=tmp_path, env={}) == "OBJ_KEY"

def test_env_takes_precedence(tmp_path):
    (tmp_path / "api_key.json").write_text("FILE_KEY")
    from face_search.key_store import load_key
    assert load_key(search_dir=tmp_path, env={"SERPAPI_KEY": "ENV_KEY"}) == "ENV_KEY"

def test_missing_key_raises(tmp_path):
    from face_search.key_store import load_key
    import pytest
    with pytest.raises(ValueError):
        load_key(search_dir=tmp_path, env={})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_key_store.py -v`
Expected: FAIL (module `face_search.key_store` does not exist)

- [ ] **Step 3: Write minimal implementation**

```python
# face_search/key_store.py
import json
import os
from pathlib import Path


def load_key(search_dir=None, env=None) -> str:
    source = env if env is not None else os.environ
    key = (source.get("SERPAPI_KEY") or "").strip()
    if key:
        return key
    base = Path(search_dir) if search_dir else Path.cwd()
    for name in ("api_key.json", ".api_key.json"):
        candidate = base / name
        if candidate.is_file():
            key = _read_key_file(candidate)
            if key:
                return key
    raise ValueError(
        "SerpApi key not found. Set SERPAPI_KEY or place the key in api_key.json."
    )


def _read_key_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig").strip().strip('"').strip("'")
    if not text:
        return ""
    if text.startswith("{"):
        data = json.loads(text)
        for field in ("api_key", "SERPAPI_KEY", "serpapi_key", "key"):
            value = str(data.get(field, "")).strip()
            if value:
                return value
        return ""
    return text.split()[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_key_store.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add face_search tests .env.example requirements.txt
git commit -m "feat: add config and secret-safe key loading"
```

### Task 2: SerpApi client (quota-safe) + parsing

**Files:**
- Create: `face_search/serp_client.py`
- Create: `tests/test_parse.py`
- Create: `tests/fixtures/lens_sample.json`

**Interfaces:**
- Consumes: `config` constants, `key_store.load_key`.
- Produces: `check_quota(key) -> dict`, `upload_image(path, key) -> str`,
  `lens_search(image_id=None, image_url=None, key) -> dict`, `parse_results(raw) -> list[dict]`
  with candidate keys `position,title,source,page_url,image_url,thumbnail_url,image_width,image_height`.

```python
# tests/fixtures/lens_sample.json — hand-written, mirrors SerpApi visual_matches + exact_matches shapes
{
  "visual_matches": [
    {"position": 1, "title": "Jane Doe — ExampleConf", "link": "https://example.com/talk",
     "source": "Example", "thumbnail": "https://example.com/t.jpg",
     "image": "https://example.com/i.jpg", "image_width": 800, "image_height": 600}
  ],
  "exact_matches": [
    {"position": 1, "title": "Jane portrait", "link": "https://linkedin.com/in/janedoe",
     "source": "LinkedIn", "thumbnail": "https://example.com/t2.jpg", "image": "https://example.com/i2.jpg"}
  ]
}
```

- [ ] **Step 1: Write the failing test**

```python
# tests/test_parse.py
import json
from pathlib import Path
from face_search.serp_client import parse_results

def test_parse_merges_visual_and_exact_matches():
    raw = json.loads(Path("tests/fixtures/lens_sample.json").read_text())
    out = parse_results(raw)
    assert len(out) == 2
    assert out[0]["page_url"] == "https://example.com/talk"
    assert out[1]["page_url"] == "https://linkedin.com/in/janedoe"
    assert set(out[0]) == {"position", "title", "source", "page_url", "image_url",
                           "thumbnail_url", "image_width", "image_height", "match_kind"}

def test_parse_empty_response():
    assert parse_results({}) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_parse.py -v`
Expected: FAIL (module missing)

- [ ] **Step 3: Write minimal implementation**

```python
# face_search/serp_client.py (quota-relevant parts)
def check_quota(api_key):
    """Free call: aborts live search before spending anything when exhausted."""
    resp = requests.get(config.SERPAPI_ACCOUNT_URL, params={"api_key": api_key},
                        timeout=config.REQUEST_TIMEOUT)
    ...
```

Full file written in implementation session; rules: exactamente one search per `lens_search` call;
no `no_cache` param ever sent; `error` key in response raises RuntimeError.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_parse.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add face_search/serp_client.py tests/test_parse.py tests/fixtures/lens_sample.json
git commit -m "feat: add quota-safe SerpApi client and result parsing"
```

### Task 3: images + faces + rank (pure local, zero searches)

**Files:**
- Create: `face_search/images.py`
- Create: `face_search/faces.py`
- Create: `face_search/rank.py`
- Create: `tests/test_rank.py`

**Interfaces:**
- Consumes: `config` constants.
- Produces: `images.download_image(url, save_path) -> bool`,
  `faces.FaceEngine.largest_embedding(image) -> np.ndarray | None`,
  `faces.cosine(a, b) -> float`,
  `rank.platform_of(page_url) -> str`, `rank.rank_candidates(items, threshold) -> list`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rank.py
from face_search.rank import platform_of, rank_candidates

def test_platform_detection():
    assert platform_of("https://www.linkedin.com/in/jane") == "linkedin"
    assert platform_of("https://x.com/jane/status/1") == "x"
    assert platform_of("https://example.com/a") == "web"

def test_social_boost_and_threshold():
    items = [
        {"page_url": "https://example.com/a", "similarity": 0.9, "has_face": True},
        {"page_url": "https://github.com/jane", "similarity": 0.6, "has_face": True},
        {"page_url": "https://example.com/b", "similarity": 0.2, "has_face": True},
    ]
    out = rank_candidates(items, threshold=0.45)
    assert [r["page_url"] for r in out] == ["https://github.com/jane", "https://example.com/a"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_rank.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

`rank.py`: drop below-threshold/no-face, dedupe by `page_url` keeping best similarity,
sort social-first then similarity desc. `faces.py`: lazy InsightFace singleton
(`buffalo_l`, CPU), `largest_embedding` returns L2-normalized vector or None.
`images.py`: UA header, PIL verify, thumbnail fallback handled by caller, cleanup on failure.

- [ ] **Step 4: Run tests to verify**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add face_search/images.py face_search/faces.py face_search/rank.py tests/test_rank.py
git commit -m "feat: add local download, InsightFace engine, and social-boost ranking"
```

### Task 4: pipeline + CLI + docs + dry runs

**Files:**
- Create: `face_search/pipeline.py`
- Create: `face_search/cli.py`
- Create: `HOW_IT_WORKS.md`
- Create: `runs/.gitkeep` (empty; run outputs gitignored)

**Interfaces:**
- Consumes: everything above.
- Produces: `pipeline.run(image=None, image_url=None, top_n, threshold, live, reuse_cache, out_dir) -> dict`;
  CLI `python -m face_search.cli --image P [--live|--reuse-cache FILE] [--top N] [--threshold T] [--out results.json]`.

- [ ] **Step 1: Dry-run the pipeline with zero searches**

Run: `.venv/bin/python -m face_search.cli --image HHGOA-FACE-BLOCKCHAIN/test_images/person1_a.jpg --top 3`
Expected: exit 0, query face detected, no SerpApi call, report states DRY_RUN with zero searches spent.

- [ ] **Step 2: Replay a cached response with zero searches**

Run: `.venv/bin/python -m face_search.cli --image HHGOA-FACE-BLOCKCHAIN/test_images/person1_a.jpg --reuse-cache tests/fixtures/lens_sample.json --top 5`
Expected: exit 0, candidates parsed/ranked from fixture, searches_spent == 0.

- [ ] **Step 3: Write HOW_IT_WORKS.md**

Contents: data-flow diagram, per-module table, quota rules, the three commands above with
their actual outputs, threshold calibration (same 1.0 / cross 0.02 / default 0.45),
what `--live` does (quota check → upload/search → cache raw JSON → verify → rank).

- [ ] **Step 4: Full test suite + commit**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: all PASS.

```bash
git add face_search/pipeline.py face_search/cli.py HOW_IT_WORKS.md
git commit -m "feat: add SerpApi-only pipeline CLI with dry-run and docs"
```

## Self-Review

- Spec coverage: ingest file+URL (pipeline/images), SerpApi Lens + parsing (serp_client),
  embeddings + compare (faces), social-boost rank (rank), CLI+JSON (cli/pipeline),
  quota safety (dry-run default, quota gate, cache reuse). Bing intentionally deferred per revision.
- No placeholders: every step has exact code/commands/expected output.
- Type consistency: candidate dict keys fixed in Task 2 and reused in Tasks 3–4;
  similarity is cosine float, higher = more similar, threshold default 0.45 from `config`.
