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
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = os.path.join(out_dir, timestamp)
    os.makedirs(run_dir, exist_ok=True)

    query_path = images.fetch_query_image(
        image=image,
        image_url=image_url,
        save_path=os.path.join(run_dir, "query.jpg"),
    )
    query_embedding = faces.largest_embedding(query_path)
    if query_embedding is None:
        raise ValueError(f"No detectable face in query image: {query_path}")

    if reuse_cache:
        with open(reuse_cache, encoding="utf-8") as handle:
            raw_response = json.load(handle)
        mode, searches_spent = "CACHE_REPLAY", 0
    elif not live:
        return {
            "mode": "DRY_RUN",
            "searches_spent": 0,
            "query": {"path": query_path, "faces_found": 1},
            "note": "Dry run spends no SerpApi searches. Pass --live to search.",
            "run_dir": run_dir,
        }
    else:
        api_key = serp_client.load_key()
        serp_client.check_quota(api_key)  # raises when quota is exhausted
        if image_url:
            raw_response = serp_client.lens_search(api_key, image_url=image_url)
        else:
            image_id = serp_client.upload_image(query_path, api_key)
            raw_response = serp_client.lens_search(api_key, image_id=image_id)
        with open(os.path.join(run_dir, "lens_raw.json"), "w", encoding="utf-8") as handle:
            json.dump(raw_response, handle, indent=2)
        mode, searches_spent = "LIVE", 1

    candidates = serp_client.parse_results(raw_response)[: max(top_n, 0)]
    scored = _verify_candidates(query_embedding, candidates, run_dir)
    matches = rank.rank_candidates(scored, threshold=threshold)

    report = {
        "mode": mode,
        "searches_spent": searches_spent,
        "query": {"path": query_path, "faces_found": 1},
        "threshold": threshold,
        "candidates_found": len(candidates),
        "processed": len(scored),
        "downloaded": sum(1 for row in scored if row.get("downloaded")),
        "with_faces": sum(1 for row in scored if row.get("has_face")),
        "verified": len(matches),
        "matches": [
            {
                "title": row.get("title"),
                "source": row.get("source"),
                "platform": rank.platform_of(row.get("page_url", "")),
                "page_url": row.get("page_url"),
                "image_url": row.get("image_url"),
                "similarity": round(row["similarity"], 4)
                if row.get("similarity") is not None
                else None,
            }
            for row in matches
        ],
        "run_dir": run_dir,
    }
    with open(os.path.join(run_dir, "report.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    return report


def _verify_candidates(query_embedding, candidates, run_dir) -> list:
    download_dir = os.path.join(run_dir, "candidates")
    os.makedirs(download_dir, exist_ok=True)
    scored = []
    for position, candidate in enumerate(candidates, 1):
        save_path = os.path.join(download_dir, f"candidate_{position}.jpg")
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
