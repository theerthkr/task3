# CODE — how this codebase works

SerpApi Google Lens (URL-only) + ImgOps temp hosting + InsightFace verification.
Pipeline ingests **all** SerpApi hits at once, verifies every candidate, ranks everyone by similarity, and writes a single ranked JSON document.

## Principles applied

- Separation of concerns: `cli` parses/prints, `pipeline` orchestrates, `hosting` owns file→URL, `serp_client` owns quota/search, `faces` owns embeddings, `rank` owns ranking.
- Single source of truth: `face_search/config.py` for pipeline constants (`DEFAULT_TOP_N=0` = no limit, `DEFAULT_THRESHOLD=0.45`); `hosting/imgops_uploader/config.py` for ImgOps URLs/limits; candidate schema `_CANDIDATE_FIELDS` enforced by tests.
- URL-only contract: SerpApi `image_id` path removed; every live search is `url=<public URL>` (local files hosted to `https://imgops.com/1hr-tempcache/...`).
- Testability: pure functions (`rank`, `parse_results`, `format_report`) mocked-tested; `hosting` validated without network.

## Modules

| Module | Owns | Key functions |
|---|---|---|
| `config.py` | Pipeline constants, thresholds, filenames, model pack, host TTL (re-exported from hosting config) | (data) |
| `key_store.py` | Secret loading (env/`api_key.json` raw/NAME=value/JSON), never logs | `load_key(search_dir, env) -> str` |
| `hosting/imgops_uploader/` | **Vendored** from `/Default Project/image to url` — file→1h temp URL | `upload_image(path) -> UploadResult`, `upload_image_bytes`, `config.STORE_URL` |
| `hosting/__init__.py` | Facade re-export for `from face_search.hosting import upload_image` | — |
| `serp_client.py` | Quota gate + URL-only Lens search + parsing (all hits at once) | `check_quota(key)`, `lens_search(key, image_url)`, `parse_results(raw, engine)`, `load_key()` |
| `images.py` | Candidate downloads (20 MB cap, PIL verify, cleanup) + query resolve | `download_image(url, save_path) -> bool`, `fetch_query_image(...)` |
| `faces.py` | Lazy InsightFace `buffalo_l` (CPU), FutureWarning patch | `detect(path)`, `largest_embedding(path)`, `cosine(a,b)`, `_reset_engine()` |
| `rank.py` | Ranking everyone + verified subset (threshold + dedupe) | `platform_of(url)`, `rank_candidates(items, threshold)`, `rank_all(items)` |
| `pipeline.py` | Orchestration, `searches_spent`, hosted_url tracking, ranked JSON | `run(image/image_url, top_n, threshold, live, reuse_cache) -> report`, `_host_local_image`, `_verify_candidates` |
| `cli.py` | Argparse + `format_report` | `build_parser()`, `format_report(report) -> str` |

Candidate row: `position, title, source, page_url, image_url, thumbnail_url, image_width, image_height, match_kind, engine`.
Ranked row adds: `platform, downloaded, has_face, similarity, verified`.

## Data flow (URL-only, all hits, ranked JSON)

```
--image local.jpg  ->  hosting.upload_image -> https://imgops.com/1hr-tempcache/... (1h)
                                          \
--image-url https://...  -----------------> lens_search(url=public URL) [1 search, quota-gated]
                                          -> save lens_raw.json + hosted_url.txt
-> parse ALL visual_matches+exact_matches (no limit unless --top N) -> download -> embed -> cosine
-> rank_all (everyone by similarity, deduped by page_url) + rank_candidates (verified >=0.45, social first)
-> report.json { ranked: [...], matches: verifiedSubset, candidates_found, verified, ... }
--reuse-cache FILE -> parse ALL -> verify -> rank (0 searches)
default (no --live, no cache) -> detect query face -> DRY_RUN (0 searches)
```

## Verified facts

- 16 tests pass (`pytest tests/ -v`), no network, no searches.
- Hosting: 5 MB limit (`hosting_demo.txt`), pure `_build_urls` unit-tested.
- Faces: same 1.0 / cross 0.0187 → threshold 0.45 (`faces.txt`).
- Live example `chandu.png` (0-limit run): 60 returned, top 10 verified ranking shows `Bebee 0.9944` as #1, 9 other LinkedIn/FB below threshold — full `ranked` list in `runs/<ts>/report.json`.

## Runbook

```bash
.venv/bin/python -m pytest tests/ -v                 # 16 tests, $0
bash dryruns/run_all.sh                               # 6 demos, $0, outputs in dryruns/output/
.venv/bin/python -m face_search.cli --image a.jpg                 # dry run
.venv/bin/python -m face_search.cli --image a.jpg --live            # hosts → 1 search, ranks ALL (default top 0 = no limit)
.venv/bin/python -m face_search.cli --image a.jpg --live --top 10   # cap to 10 if you want
.venv/bin/python -m face_search.cli --image a.jpg --reuse-cache runs/<ts>/lens_raw.json --top 0  # rank all from cache, $0
cat runs/<ts>/report.json | head -n 80               # ranked JSON document (source + similarity + verified flag per row)
```

`HHGOA-FACE-BLOCKCHAIN/` read-only reference (untracked). `api_key.json` / `.env` gitignored — never logged.
Hosting URLs expire in ~1h; `runs/<ts>/hosted_url.txt` preserves the exact URL used.
