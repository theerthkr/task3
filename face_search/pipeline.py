"""Orchestration only: ingest, search (or replay), verify, rank, report.

Search-spend accounting is explicit: the returned report always carries
searches_spent (0 for dry-run and cache replay, 1 for a live search).
"""

import json
import os
from datetime import datetime, timezone

from face_search import config, faces, images, rank, serp_client


def run(
    image: str = "",
    image_url: str = "",
    top_n: int = config.DEFAULT_TOP_N,
    threshold: float = config.DEFAULT_THRESHOLD,
    live: bool = False,
    reuse_cache: str = "",
    out_dir: str = "runs",
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
        return _build_report(
            mode="DRY_RUN",
            searches_spent=0,
            query_path=query_path,
            faces_found=len(query_faces),
            threshold=threshold,
            candidates=[],
            scored=[],
            matches=[],
            run_dir=run_dir,
        )

    raw_response, mode, searches_spent = _load_candidates(
        query_path=query_path,
        image_url=image_url,
        live=live,
        reuse_cache=reuse_cache,
        run_dir=run_dir,
    )
    candidates = serp_client.parse_results(raw_response)[:top_n]
    scored = _verify_candidates(query_embedding, candidates, run_dir)
    matches = rank.rank_candidates(scored, threshold=threshold)
    return _build_report(
        mode=mode,
        searches_spent=searches_spent,
        query_path=query_path,
        faces_found=len(query_faces),
        threshold=threshold,
        candidates=candidates,
        scored=scored,
        matches=matches,
        run_dir=run_dir,
    )


def _make_run_dir(out_dir: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = os.path.join(out_dir, timestamp)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def _load_candidates(query_path, image_url, live, reuse_cache, run_dir):
    if reuse_cache:
        with open(reuse_cache, encoding="utf-8") as handle:
            return json.load(handle), "CACHE_REPLAY", 0
    api_key = serp_client.load_key()
    serp_client.check_quota(api_key)  # raises when quota is exhausted
    if image_url:
        raw_response = serp_client.lens_search(api_key, image_url=image_url)
    else:
        image_id = serp_client.upload_image(query_path, api_key)
        raw_response = serp_client.lens_search(api_key, image_id=image_id)
    raw_path = os.path.join(run_dir, config.RAW_FILENAME)
    with open(raw_path, "w", encoding="utf-8") as handle:
        json.dump(raw_response, handle, indent=2)
    return raw_response, "LIVE", 1


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


def _present_match(row: dict) -> dict:
    return {
        "title": row.get("title"),
        "source": row.get("source"),
        "platform": rank.platform_of(row.get("page_url", "")),
        "page_url": row.get("page_url"),
        "image_url": row.get("image_url"),
        "similarity": round(row["similarity"], 4)
        if row.get("similarity") is not None
        else None,
    }


def _build_report(
    mode, searches_spent, query_path, faces_found, threshold,
    candidates, scored, matches, run_dir,
) -> dict:
    report = {
        "mode": mode,
        "searches_spent": searches_spent,
        "query": {"path": query_path, "faces_found": faces_found},
        "threshold": threshold,
        "candidates_found": len(candidates),
        "processed": len(scored),
        "downloaded": sum(1 for row in scored if row.get("downloaded")),
        "with_faces": sum(1 for row in scored if row.get("has_face")),
        "verified": len(matches),
        "matches": [_present_match(row) for row in matches],
        "run_dir": run_dir,
    }
    if mode != "DRY_RUN":
        with open(os.path.join(run_dir, config.REPORT_FILENAME), "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
    return report
