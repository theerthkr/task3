# How face_search works

SerpApi-only reverse face search: Google Lens finds where a photo appears on the
public web, InsightFace verifies each candidate actually shows the same face,
and social profiles (LinkedIn / X / Instagram / GitHub) float to the top.

Scope honesty: a social hit appears only if that photo (or near-duplicate) is
publicly indexed with the face visible. An unpublished private photo correctly
returns no match. This is verification, not identity proof.

## Layout

```
face_search/
  config.py       single source of truth: endpoints, thresholds, social domains
  key_store.py    loads the key (env, then api_key.json raw-or-JSON); never logs it
  serp_client.py  quota check (free), image upload, Lens search (1 search), parsing
  images.py       downloads with browser UA + image validation + cleanup
  faces.py        lazy InsightFace buffalo_l; largest-face embedding; cosine
  rank.py         threshold filter, dedupe by page URL, social-first sort
  pipeline.py     orchestration + searches_spent accounting + report.json
  cli.py          argparse; dry-run default; --live opts into spending
tests/
  test_key_store.py / test_parse.py / test_rank.py / test_verify_flow.py
  fixtures/lens_sample.json   hand-written Lens response shape (no API spent)
runs/<timestamp>/             per-run artifacts (gitignored): report.json, lens_raw.json
```

## Data flow

```
face.jpg (or --image-url)
  -> images.fetch_query_image -> faces.largest_embedding (query vector)
  -> DRY_RUN: stop, 0 searches
  -> CACHE_REPLAY: parse saved lens_raw.json, 0 searches
  -> LIVE: check_quota (free) -> upload (local file) -> lens_search (1 search)
           -> save lens_raw.json
  -> download top-N candidates (thumbnail fallback) -> embed -> cosine vs query
  -> rank: threshold 0.45, dedupe, social first -> report.json
```

## Quota rules (SerpApi free plan, per official docs)

- Default is dry-run: zero searches, always safe.
- `--live` first calls free `account.json`; aborts when nothing is left.
- `no_cache` is never sent, so identical repeats serve free cache (1h expiry).
- `--reuse-cache` replays a saved response with zero searches.
- Key lives in `api_key.json` (raw key, as you provided) or `SERPAPI_KEY`;
  both are gitignored and never printed.

## Dry runs (actual output, 0 searches spent)

```
$ .venv/bin/python -m face_search.cli --image HHGOA-FACE-BLOCKCHAIN/test_images/person1_a.jpg --top 3
Mode: DRY_RUN (searches spent: 0)
Query face: detected in HHGOA-FACE-BLOCKCHAIN/test_images/person1_a.jpg
No matches yet — rerun with --live or --reuse-cache.
```

```
$ .venv/bin/python -m face_search.cli --image HHGOA-FACE-BLOCKCHAIN/test_images/person1_a.jpg \
    --reuse-cache tests/fixtures/lens_sample.json --top 5
Mode: CACHE_REPLAY (searches spent: 0)
Candidates: 2 | Verified: 0
```

Replay shows 0 verified because the fixture URLs are illustrative, not
downloadable — downloads fail gracefully and are counted, not crashed on.
The real verify path is covered by tests (below) with real face images.

## Threshold calibration (measured, not guessed)

InsightFace `buffalo_l` cosine similarity on the reference test images:

| pair | similarity |
|---|---|
| person1_a vs person1_b (same photo bytes) | 1.0000 |
| person1_a vs person2_a (different people) | 0.0187 |

Default threshold 0.45 sits far from the measured cross-person 0.02.
Tune per case with `--threshold`. (`person2.jpg` contains no detectable face
and is therefore excluded from calibration.)

## Tests (12 passed, no network, no searches)

```
.venv/bin/python -m pytest tests/ -v
test_key_store.py .... | test_parse.py .. | test_rank.py ... | test_verify_flow.py ...
12 passed
```

## Going live (spends exactly 1 search)

```
.venv/bin/python -m face_search.cli --image face.jpg --top 10 --out results.json
```

Checks quota → uploads → Lens search → caches `runs/<ts>/lens_raw.json` →
downloads/verifies/ranks → prints top 5 + writes report. Re-running analysis
later costs nothing: `--reuse-cache runs/<ts>/lens_raw.json`.

## What came from HHGOA-FACE-BLOCKCHAIN (reference only, nothing imports it)

- Reused: upload-then-`google_lens` flow, `visual_matches` field mapping,
  UA-header download + PIL verify + thumbnail fallback, verified-first ranking.
- Changed: DeepFace+TensorFlow → InsightFace (TF has no Python 3.14 wheels);
  dropped Sepolia anchoring (out of scope); added dry-run/cache-replay modes,
  quota pre-check, exact-matches parsing, social boost, secret-safe key loading.
