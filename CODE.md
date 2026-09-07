# CODE — how this codebase works

SerpApi Google Lens (URL-only) + ImgOps temp hosting + InsightFace verification + enrichment.
Default mode spends zero searches; `--live` hosts local files to a 1h public URL, then Lens searches that URL.

## Principles applied

- Separation of concerns: `cli` parses/prints, `pipeline` orchestrates, `hosting` owns file→URL, `serp_client` owns quota/search, `faces` owns embeddings, `rank` owns threshold/dedupe, `enrich` owns handle/name extraction.
- Single source of truth: `face_search/config.py` for pipeline constants; `hosting/imgops_uploader/config.py` for ImgOps URLs/limits; candidate schema `_CANDIDATE_FIELDS` enforced by tests.
- URL-only contract: SerpApi `image_id` path removed; every live search is `url=<public URL>`.
- Testability: pure functions (`rank`, `parse_results`, `enrich`, `format_report`) mocked-tested; `hosting` validated without network.

## Modules

| Module | Owns | Key functions |
|---|---|---|
| `config.py` | Pipeline constants, thresholds, filenames, model pack, host TTL note | (data) |
| `key_store.py` | Secret loading (env/`api_key.json` raw/NAME=value/JSON), never logs | `load_key(search_dir, env) -> str` |
| `hosting/imgops_uploader/` | **Vendored** from `/Default Project/image to url` — file→1h temp URL | `upload_image(path) -> UploadResult`, `upload_image_bytes`, `config.STORE_URL`, `models.UploadResult` |
| `hosting/__init__.py` | Facade re-export for clean `from face_search.hosting import upload_image` | — |
| `serp_client.py` | Quota gate + URL-only Lens search + parsing | `check_quota(key)`, `lens_search(key, image_url)`, `parse_results(raw, engine)`, `load_key()` |
| `images.py` | Candidate downloads (20 MB cap, PIL verify, cleanup) + query resolve | `download_image(url, save_path) -> bool`, `fetch_query_image(...)` |
| `faces.py` | Lazy InsightFace `buffalo_l` (CPU), FutureWarning patch | `detect(path)`, `largest_embedding(path)`, `cosine(a,b)`, `_reset_engine()` |
| `rank.py` | Threshold filter, dedupe by URL, social-first | `platform_of(url)`, `rank_candidates(items, threshold)` |
| `enrich.py` | **New**: actionable leads from verified matches — handle, display_name, company_hint, profile_type | `extract_handle(url)`, `extract_display_name(title)`, `enrich_match(m)`, `enrich_matches(list)` |
| `pipeline.py` | Orchestration, `searches_spent`, hosted_url tracking, `hosted_url.txt` | `run(image/image_url, top_n, threshold, live, reuse_cache) -> report`, `_host_local_image`, `_load_candidates`, `_verify_candidates`, `_present_match` |
| `cli.py` | Argparse + `format_report` | `build_parser()`, `format_report(report) -> str` |

Candidate row: `position, title, source, page_url, image_url, thumbnail_url, image_width, image_height, match_kind, engine`.
Enriched match adds: `platform, handle, profile_type, is_social, display_name, company_hint, similarity`.

## Data flow (URL-only)

```
--image local.jpg  ->  hosting.upload_image -> https://imgops.com/1hr-tempcache/... (1h)
                                          \
--image-url https://...  -----------------> lens_search(url=public URL) [1 search, quota-gated]
                                          -> save lens_raw.json + hosted_url.txt
-> parse -> download top-N -> embed -> cosine -> rank (0.45, dedupe, social first)
-> enrich (handle/name/company) -> report.json
--reuse-cache FILE -> parse -> verify -> rank -> enrich (0 searches)
default (no --live, no cache) -> detect query face -> DRY_RUN (0 searches)
```

## Verified facts

- 23 tests pass (`pytest tests/ -v`), no network, no searches.
- Hosting: 5 MB page limit (`hosting_demo.txt`), pure `_build_urls` unit-tested.
- Enrichment: github/x/linkedin handles extracted, `display_name` split on `|/-`, `profile_type` set (`enrich_demo.txt`).
- Faces: same 1.0 / cross 0.0187 → threshold 0.45 (`faces.txt`).
- Live example (chandu.png): hosted → Lens → 10/10 faces, 1 verified 0.9944 (bebee profile) — enriched with `display_name=Chandraveer Singh Solanki`, `company_hint`.

## Runbook

```bash
.venv/bin/python -m pytest tests/ -v                 # 23 tests, $0
bash dryruns/run_all.sh                               # 7 demos, $0, outputs in dryruns/output/
.venv/bin/python -m face_search.cli --image a.jpg --top 10              # dry run
.venv/bin/python -m face_search.cli --image a.jpg --live --out r.json   # hosts -> 1 search -> enrich
.venv/bin/python -m face_search.cli --image-url https://... --live         # no hosting hop
.venv/bin/python -m face_search.cli --image a.jpg --reuse-cache runs/<ts>/lens_raw.json --top 60  # $0
```

`HHGOA-FACE-BLOCKCHAIN/` read-only reference (untracked). `api_key.json` / `.env` gitignored — never logged.
Hosting URLs expire in ~1h (per ImgOps config); `runs/<ts>/hosted_url.txt` preserves the exact URL used.
