# Face Search Pipeline — Design (2026-09-07)

## 1. Goal
Take a query face (local file or public URL), reverse-image-search it via SerpApi (Google Lens) and Bing Visual Search, download candidate images, verify each with local face embeddings, and return ranked matches with emphasis on LinkedIn / X-Twitter / Instagram / GitHub and the originating page.

## 2. Non-goal / expectation
This is **reverse-image + local face verification**, not a PimEyes/FaceCheck-style identity database search. A social-profile hit is returned **only if that photo (or near-duplicate) is publicly indexed** with the face visible. Private/unpublished photos will correctly return no match. Only query images the user has rights to use; only public web results are consumed.

## 3. Decisions (user-confirmed)
- Input: both local file and public URL.
- Stack: Python + InsightFace (`buffalo_l`, ArcFace embeddings, cosine similarity).
- Output: all matches above threshold, social/profile domains boosted; CLI + ranked JSON.
- Approach A: dual-source (SerpApi Google Lens + Bing Visual Search v7) with graceful single-source fallback.
- User task: create SerpApi account (SERPAPI_API_KEY) and Azure Bing Visual Search resource (BING_VISUAL_SEARCH_KEY); provide a test photo with usage rights.

## 4. Architecture + data flow
```
[face.jpg | image URL]
 -> ingest: detect faces, largest face = query, query embedding
 -> reverse-search in parallel:
      SerpApi Google Lens (needs public image URL; local files need temp public host)
      Bing Visual Search v7 (binary upload or URL)
 -> normalize -> [{page_url, image_url, title, engine}]
 -> per candidate: download -> detect faces -> embed each -> max cosine vs query
 -> rank: threshold filter (default 0.45, tunable), dedupe by page_url,
    boost linkedin.com, x.com, twitter.com, instagram.com, github.com
 -> out: ranked.json + terminal table (score, platform, page_url, image_url, title)
```

## 5. Components
- `config.py` — env/`.env` keys: `SERPAPI_API_KEY`, `BING_VISUAL_SEARCH_KEY`. Runs with either; warns if one missing.
- `ingest.py` — file/URL load, InsightFace detection, largest-face selection, query embedding. Fail-fast on no face.
- `search_serpapi.py` — Google Lens adapter; explicit handling of local-file-needs-public-URL limitation.
- `search_bing.py` — Visual Search adapter; parses `tags -> actions -> visuallySimilarImages/pagesIncluding`.
- `faces.py` — InsightFace `buffalo_l` embeddings + cosine similarity; clear error if `onnxruntime` missing.
- `rank.py` — threshold filter, platform detection, social boost, dedupe.
- `cli.py` — `python -m face_pipeline.search --image <path|url> [--threshold 0.45] [--top-k 20] [--out results.json]`.

## 6. Error handling
- No face in query: fail fast with clear message.
- Missing keys: clear setup message, run with available source if possible.
- Candidate download failure / no face in candidate: skip with counts in summary, not a crash.
- Zero matches above threshold: valid "no match" output.

## 7. Testing
- Unit (no keys): cosine similarity, threshold filter, platform detect + social boost, dedupe, normalizers with mock payloads.
- Integration (mock fixtures): adapter parsing, end-to-end pipeline with stubbed search + real local face comparison.
- Live (needs user keys + rights-cleared photo): SerpApi + Bing recall check, threshold calibration.

## 8. Setup the user must do (outside assistant expertise)
1. SerpApi account -> `SERPAPI_API_KEY`.
2. Azure AI Vision / Bing Visual Search resource -> `BING_VISUAL_SEARCH_KEY`.
3. `pip install insightface onnxruntime opencv-python requests python-dotenv` (plus ` serpapi` client or plain HTTP).
4. Provide test image (file or URL) with usage rights.
5. `cp .env.example .env`, paste keys, run CLI.

## 10. Revision 2026-09-07 — SerpApi-only scope (user decision)
- Bing Visual Search deferred; SerpApi Google Lens is the single search source.
- Reference repo cloned to `HHGOA-FACE-BLOCKCHAIN/` (read-only reference, not a dependency).
  Reused from it: upload-then-`google_lens`-search flow, `visual_matches` parsing shape,
  UA-header download + PIL verify + thumbnail fallback, verified-first ranking.
  Dropped: DeepFace/TensorFlow (incompatible with Python 3.14) → InsightFace `buffalo_l`;
  blockchain anchoring (out of scope).
- `api_key.json` holds the raw SerpApi key (not a JSON object); loader supports both.
- Quota rules (SerpApi free plan, from official docs): default dry-run (zero searches);
  live search only with explicit `--live`; quota pre-check via free `account.json`;
  never `no_cache=true` (cached repeats are free); `--reuse-cache` replays saved JSON.

## 9. Self-review
- No TBD/TODO placeholders; thresholds and defaults explicit.
- Consistent: single-source fallback matches error-handling section; social-boost matches output decision.
- Scope: single pipeline, no web UI/API service (deferred).
- Ambiguity resolved: "match" = cosine >= threshold on largest query face; "social" = 5 listed domains.
