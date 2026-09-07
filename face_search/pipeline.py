"""Orchestration only: ingest, host to URL, search (or replay), verify, rank, report.

URL-only contract: local files are hosted via imgops_uploader to a 1-hour
public URL; SerpApi is always called with url= (never image_id).

This pipeline takes ALL SerpApi hits at once — no top_n slicing by default —
runs face extraction + cosine comparison on every candidate, and ranks
everyone (full list + verified subset) into a single JSON document.
"""

import json
import os
from datetime import datetime, timezone

from face_search import config, faces, images, llm_judge, rank, serp_client


def run(
    image: str = "",
    image_url: str = "",
    top_n: int = config.DEFAULT_TOP_N,
    threshold: float = config.DEFAULT_THRESHOLD,
    live: bool = False,
    reuse_cache: str = "",
    out_dir: str = "runs",
    anchor: bool = False,
    anchor_top_k: int = 1,
    llm_model: str = "",
) -> dict:
    if top_n < 0:
        raise ValueError(f"top_n must be 0 or more, got {top_n}.")
    run_dir = _make_run_dir(out_dir)

    query_path = images.fetch_query_image(
        image=image,
        image_url=image_url,
        save_path=os.path.join(run_dir, config.QUERY_FILENAME),
    )
    query_faces = faces.detect(query_path)
    if not query_faces:
        raise ValueError(f"No detectable face in query image: {query_path}")
    query_embedding = query_faces[0]

    if not live and not reuse_cache:
        report = _build_report(
            mode="DRY_RUN",
            searches_spent=0,
            query_path=query_path,
            hosted_url=None,
            faces_found=len(query_faces),
            threshold=threshold,
            candidates=[],
            scored=[],
            ranked_all=[],
            verified=[],
            run_dir=run_dir,
        )
        if anchor:
            try:
                from face_search.blockchain_anchor import anchor_report

                report = anchor_report(report, top_k=anchor_top_k)
                # persist enriched DRY_RUN if anchor was requested (for judge demo)
                import json

                with open(os.path.join(report["run_dir"], config.REPORT_FILENAME), "w", encoding="utf-8") as handle:
                    json.dump(report, handle, indent=2)
            except Exception as exc:
                report.setdefault("blockchain", {})["error"] = str(exc)
        return report

    raw_response, mode, searches_spent, hosted_url = _load_candidates(
        query_path=query_path,
        image_url=image_url,
        live=live,
        reuse_cache=reuse_cache,
        run_dir=run_dir,
    )
    # Take ALL hits at once (top_n == 0 means no limit; otherwise cap).
    all_candidates = serp_client.parse_results(raw_response)
    candidates = all_candidates if top_n == 0 else all_candidates[:top_n]

    scored = _verify_candidates(query_embedding, candidates, run_dir)

    # Rank everyone (no threshold) + verified subset (threshold + social boost).
    ranked_all = rank.rank_all(scored)
    verified = rank.rank_candidates(scored, threshold=threshold)

    # Present ranked_all as the main ranked document (source + similarity for each).
    ranked_presented = [_present_ranked(row) for row in ranked_all]
    verified_presented = [_present_ranked(row) for row in verified]

    # LLM judge: pass ANY profile-like link immediately (github/bebee/bold.pro etc), show all similar
    # Judge verified hits + top ranked (covers famous + non-famous profile pages)
    to_judge = verified_presented + [r for r in ranked_presented if r not in verified_presented][:5]
    to_judge = to_judge[:10]  # show up to 10 profiles if multiple similar
    verdicts = {v["page_url"]: v["llm"] for v in llm_judge.judge_matches(to_judge, model=llm_model or llm_judge.DEFAULT_MODEL)}
    for row in ranked_presented + verified_presented:
        if row.get("page_url") in verdicts:
            row["llm"] = verdicts[row["page_url"]]
    # Also attach fallback for any ranked that looks like profile but wasn't judged (so UI can still show)
    for row in ranked_presented:
        if "llm" not in row:
            # deterministic fallback: if platform is profile domain, mark as profile even without LLM
            plat = row.get("platform") or rank.platform_of(row.get("page_url", ""))
            page_url = (row.get("page_url") or "").lower()
            is_profile = plat != "web" or any(h in page_url for h in config.PROFILE_PATH_HINTS) or any(d in page_url for d in config.PROFILE_DOMAINS)
            if is_profile:
                row["llm"] = llm_judge._fallback(row, reason="profile domain fallback")

    # Finalized profiles: ONLY verified face matches (standard threshold, default 0.45) that LLM/fallback says is profile
    # 0.28 must NOT be approved — strict threshold kept
    finalized = [r for r in verified_presented if r.get("llm", {}).get("is_social_profile")]
    if not finalized and verified_presented:
        finalized = verified_presented[:5]
    finalized = finalized[:10]

    # Aggregate LLM errors for visible pipeline warning (not silent)
    llm_errors = [r.get("llm", {}) for r in ranked_presented + verified_presented if not r.get("llm", {}).get("llm_used", True) and r.get("llm")]
    real_fails = [e for e in llm_errors if any(k in (e.get("reason") or "") for k in ("HTTP 401", "HTTP 404", "HTTP 429", "HTTP 402", "timeout", "bad JSON", "llm error"))]
    _base_for_key = os.getenv("OPENROUTER_BASE_URL", "").strip() or os.getenv("LLM_BASE_URL", "").strip() or os.getenv("OPENAI_BASE_URL", "").strip()
    _is_local = "localhost" in _base_for_key or "127.0.0.1" in _base_for_key
    has_key = bool(os.getenv("OPENROUTER_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip() or _is_local)
    llm_status = "ok"
    llm_note = ""
    if has_key and real_fails:
        # important pipeline failing -> visible
        sample = real_fails[0].get("reason", "")
        if "404" in sample:
            llm_status = "error_404"
            llm_note = f"LLM judge failing: {sample} — free models rotate, change model in UI (try google/gemini-2.0-flash-exp:free)"
        elif "401" in sample:
            llm_status = "error_401"
            llm_note = f"LLM judge failing: {sample} — check OPENROUTER_API_KEY (not SERPAPI_KEY) at openrouter.ai/keys"
        elif "429" in sample:
            llm_status = "error_429"
            llm_note = f"LLM judge rate-limited (429) — wait 60s or switch model/add credits"
        elif "timeout" in sample.lower():
            llm_status = "error_timeout"
            llm_note = f"LLM judge timeout — OpenRouter overloaded, retry SEARCH"
        elif "bad JSON" in sample:
            llm_status = "error_json"
            llm_note = f"LLM bad JSON — model returned invalid JSON, switch model"
        else:
            llm_status = "error"
            llm_note = f"LLM judge failing: {sample} — results are fallback heuristic only"
    elif not has_key and llm_errors:
        llm_status = "fallback_no_key"
        llm_note = "LLM disabled — no OPENROUTER_API_KEY, deterministic fallback active (still passes github/bebee/bold.pro immediately). Add free key at openrouter.ai/keys for better verdicts."

    # If LLM errored, do NOT show below-threshold as finalized — keep strict threshold
    # (previous fallback that showed 0.28 as finalized is removed)

    report = _build_report(
        mode=mode,
        searches_spent=searches_spent,
        query_path=query_path,
        hosted_url=hosted_url,
        faces_found=len(query_faces),
        threshold=threshold,
        candidates=candidates,
        scored=scored,
        ranked_all=ranked_presented,
        verified=verified_presented,
        run_dir=run_dir,
    )
    report["finalized_profiles"] = finalized
    report["llm_model"] = llm_model or llm_judge.DEFAULT_MODEL
    report["llm_status"] = llm_status
    report["llm_note"] = llm_note
    report["llm_fallback_count"] = len(llm_errors)

    # Blockchain anchoring (opt-in --anchor): hash verified match -> store on Sepolia/local
    # Lazy, isolated in face_search.blockchain_anchor so hashing SOC stays separate.
    if anchor:
        try:
            from face_search.blockchain_anchor import anchor_report

            report = anchor_report(report, top_k=anchor_top_k)
            # persist enriched report (with blockchain receipts) back to disk
            if report.get("mode") != "DRY_RUN":
                import json

                with open(os.path.join(report["run_dir"], config.REPORT_FILENAME), "w", encoding="utf-8") as handle:
                    json.dump(report, handle, indent=2)
        except Exception as exc:
            # never fail pipeline on anchor error – attach error note
            report.setdefault("blockchain", {})["error"] = str(exc)

    return report


def _make_run_dir(out_dir: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = os.path.join(out_dir, timestamp)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def _host_local_image(local_path: str) -> str:
    """Host a local file to a 1-hour public URL via vendored ImgOps. Returns direct_url."""
    from face_search.hosting import upload_image as host_upload

    result = host_upload(local_path)
    return result.direct_url


def _load_candidates(query_path, image_url, live, reuse_cache, run_dir):
    hosted_url: str | None = None
    if reuse_cache:
        with open(reuse_cache, encoding="utf-8") as handle:
            return json.load(handle), "CACHE_REPLAY", 0, None
    api_key = serp_client.load_key()
    serp_client.check_quota(api_key)  # raises when quota is exhausted

    # URL-only: resolve the public URL to search with.
    if image_url:
        search_url = image_url
    else:
        hosted_url = _host_local_image(query_path)
        search_url = hosted_url

    raw_response = serp_client.lens_search(api_key, image_url=search_url)
    raw_path = os.path.join(run_dir, config.RAW_FILENAME)
    with open(raw_path, "w", encoding="utf-8") as handle:
        json.dump(raw_response, handle, indent=2)
    # Persist hosting trace for the 1h expiry window.
    if hosted_url:
        with open(os.path.join(run_dir, "hosted_url.txt"), "w", encoding="utf-8") as handle:
            handle.write(hosted_url + "\n")
    return raw_response, "LIVE", 1, hosted_url


def _verify_candidates(query_embedding, candidates, run_dir) -> list:
    download_dir = os.path.join(run_dir, config.CANDIDATE_DIR)
    os.makedirs(download_dir, exist_ok=True)
    scored = []
    for position, candidate in enumerate(candidates, 1):
        filename = config.CANDIDATE_PATTERN.format(position=position)
        save_path = os.path.join(download_dir, filename)
        downloaded = images.download_image(
            candidate.get("image_url", ""), save_path
        ) or images.download_image(candidate.get("thumbnail_url", ""), save_path)
        row = dict(candidate)
        row["downloaded"] = downloaded
        row["has_face"] = False
        row["similarity"] = None
        if downloaded:
            embedding = faces.largest_embedding(save_path)
            if embedding is not None:
                row["has_face"] = True
                row["similarity"] = faces.cosine(query_embedding, embedding)
        scored.append(row)
    return scored


def _present_ranked(row: dict) -> dict:
    """One row of the ranked document — includes source + similarity + flags."""
    return {
        "position": row.get("position"),
        "title": row.get("title"),
        "source": row.get("source"),
        "platform": rank.platform_of(row.get("page_url", "")),
        "page_url": row.get("page_url"),
        "image_url": row.get("image_url"),
        "thumbnail_url": row.get("thumbnail_url"),
        "match_kind": row.get("match_kind"),
        "engine": row.get("engine"),
        "downloaded": row.get("downloaded"),
        "has_face": row.get("has_face"),
        "similarity": round(row["similarity"], 4) if row.get("similarity") is not None else None,
        "verified": bool(row.get("has_face") and row.get("similarity") is not None and row.get("similarity") >= 0),  # placeholder, real verified derived from rank_candidates
    }


def _build_report(
    mode, searches_spent, query_path, hosted_url, faces_found, threshold,
    candidates, scored, ranked_all, verified, run_dir,
) -> dict:
    # Recompute verified flag per threshold for the ranked rows
    for row in ranked_all:
        sim = row.get("similarity")
        row["verified"] = bool(row.get("has_face") and sim is not None and sim >= threshold)

    report = {
        "mode": mode,
        "searches_spent": searches_spent,
        "query": {"path": query_path, "hosted_url": hosted_url, "faces_found": faces_found},
        "threshold": threshold,
        "candidates_found": len(candidates),
        "processed": len(scored),
        "downloaded": sum(1 for row in scored if row.get("downloaded")),
        "with_faces": sum(1 for row in scored if row.get("has_face")),
        "verified": len(verified),
        "ranked": ranked_all,
        "matches": verified,  # backwards-compat alias for verified subset
        "run_dir": run_dir,
    }
    if mode != "DRY_RUN":
        with open(os.path.join(run_dir, config.REPORT_FILENAME), "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
    return report
