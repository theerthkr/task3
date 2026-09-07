# CODE — how this codebase works

SerpApi-only reverse face search. Google Lens finds where a photo appears on
the public web, InsightFace verifies each candidate shows the same face,
social profiles rank first. Default mode spends zero searches.

## Principles applied

- Separation of concerns: each module owns one job (`cli` parses/prints,
  `pipeline` orchestrates, the rest do single tasks).
- Single source of truth: `config.py` owns every constant, filename, and
  default. The candidate dict schema is defined once as
  `serp_client._CANDIDATE_FIELDS` and enforced by tests.
- Testability: pure functions (`rank`, `parse_results`, `format_report`) are
  unit-tested without network or models; the model singleton has a reset hook.
- Repairability: small modules, explicit errors, per-run artifact dirs.

## Modules

| Module | Owns | Key functions |
|---|---|---|
| `config.py` | All constants: endpoints, thresholds, filenames, model pack | (data only) |
| `key_store.py` | Secret loading, never logs the key. Env (incl. `.env`) → `api_key.json` (raw, `NAME=value`, or JSON object) | `load_key(search_dir, env) -> str` |
| `serp_client.py` | SerpApi I/O + quota gate. Never sends `no_cache` (repeats are free) | `check_quota(key)`, `upload_image(path, key) -> image_id`, `lens_search(key, image_id / image_url)`, `parse_results(raw, engine) -> [candidate]`, `load_key()` |
| `images.py` | Downloads: browser UA, 20 MB cap, image validation, partial-file cleanup; query resolution | `download_image(url, save_path) -> bool`, `fetch_query_image(image / image_url, save_path) -> path` |
| `faces.py` | Lazy InsightFace `buffalo_l` (CPU); largest-face-first embeddings | `detect(path) -> [embedding]`, `largest_embedding(path)`, `cosine(a, b) -> float`, `_reset_engine()` |
| `rank.py` | Pure ranking: threshold filter, dedupe by page URL, social first | `platform_of(url)`, `is_social(url)`, `rank_candidates(items, threshold)` |
| `pipeline.py` | Orchestration + `searches_spent` accounting + uniform report schema | `run(image / image_url, top_n, threshold, live, reuse_cache, out_dir) -> report` |
| `cli.py` | Argparse + printing only | `build_parser()`, `format_report(report) -> str`, `main(argv) -> int` |

Candidate row: `position, title, source, page_url, image_url, thumbnail_url,
image_width, image_height, match_kind, engine`.

## Data flow

```
face file (--image) or URL (--image-url)
 -> fetch_query_image -> faces.detect -> largest = query vector
 -> DRY_RUN (default): stop, 0 searches
 -> --reuse-cache FILE: parse saved JSON, 0 searches
 -> --live: check_quota (free) -> upload (local) -> lens_search (1 search)
            -> save runs/<ts>/lens_raw.json
 -> download top-N (thumbnail fallback) -> embed -> cosine vs query
 -> rank (threshold 0.45, dedupe, social first) -> runs/<ts>/report.json
```

## Verified facts

- Tests: 16 passed, no network, no searches (`pytest tests/ -v`).
- Calibration (`dryruns/output/faces.txt`): same-photo 1.0000, cross-person
  0.0187 → default threshold 0.45.
- Live proof (earlier run, 1 search): 10/10 downloaded with faces, 1 verified
  at 0.9727 (Devfolio page). Lens returned 60 visual matches total.
- Honest scope: a social hit appears only if the photo is publicly indexed;
  unpublished photos correctly return no match.

## Runbook

```bash
.venv/bin/python -m pytest tests/ -v        # 16 tests, $0
bash dryruns/run_all.sh                      # 5 demos, $0, outputs in dryruns/output/
.venv/bin/python -m face_search.cli --image <face.jpg> --top 10            # dry run
.venv/bin/python -m face_search.cli --image <face.jpg> --live --out r.json # 1 search
.venv/bin/python -m face_search.cli --image <f> --reuse-cache runs/<ts>/lens_raw.json --top 60  # $0
```

`HHGOA-FACE-BLOCKCHAIN/` is the read-only reference clone (untracked);
tests borrow three of its photos. `api_key.json` / `.env` hold secrets and
are gitignored — the key value never appears in code, logs, or commits.
