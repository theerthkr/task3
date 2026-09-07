"""SerpApi Google Lens client with quota safety built in.

Cost model (from SerpApi docs): one lens_search call spends one search.
The account check and cached repeats are free, and this module never
sends no_cache=true so identical repeats serve free cache.
"""

import os

import requests

from face_search import config

_CANDIDATE_FIELDS = (
    "position",
    "title",
    "source",
    "page_url",
    "image_url",
    "thumbnail_url",
    "image_width",
    "image_height",
    "match_kind",
    "engine",
)


def check_quota(api_key: str) -> dict:
    """Free call. Raises when the account has no searches left."""
    response = requests.get(
        config.SERPAPI_ACCOUNT_URL,
        params={"api_key": api_key},
        timeout=config.REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        raise RuntimeError(f"SerpApi account check failed: HTTP {response.status_code}")
    data = response.json()
    if "error" in data:
        raise RuntimeError(f"SerpApi account error: {data['error']}")
    searches_left = data.get("total_searches_left")
    if isinstance(searches_left, int) and searches_left <= 0:
        raise RuntimeError("SerpApi quota exhausted: no searches left this period.")
    return data


def upload_image(image_path: str, api_key: str) -> str:
    """Upload a local file to SerpApi, returning the image_id for Lens."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Local image file not found: {image_path!r}")
    with open(image_path, "rb") as handle:
        response = requests.post(
            config.SERPAPI_UPLOAD_URL,
            params={"api_key": api_key},
            files={"image": handle},
            timeout=config.REQUEST_TIMEOUT,
        )
    if response.status_code != 200:
        raise RuntimeError(f"SerpApi upload failed: HTTP {response.status_code}")
    image_id = response.json().get("image_id")
    if not image_id:
        raise RuntimeError("SerpApi upload response did not contain image_id.")
    return image_id


def lens_search(api_key: str, image_id: str = "", image_url: str = "") -> dict:
    """One Google Lens search = one billed search. Exactly one of the two inputs."""
    if bool(image_id) == bool(image_url):
        raise ValueError("Pass exactly one of image_id or image_url.")
    params = {"engine": config.LENS_ENGINE, "api_key": api_key}
    if image_id:
        params["image_id"] = image_id
    else:
        params["url"] = image_url
    response = requests.get(
        config.SERPAPI_SEARCH_URL, params=params, timeout=config.REQUEST_TIMEOUT
    )
    if response.status_code != 200:
        raise RuntimeError(f"Google Lens search failed: HTTP {response.status_code}")
    data = response.json()
    if "error" in data:
        raise RuntimeError(f"SerpApi error: {data['error']}")
    return data


def parse_results(raw_response: dict, engine: str = config.LENS_ENGINE) -> list:
    """Flatten visual_matches + exact_matches into one candidate list.

    Every row carries exactly _CANDIDATE_FIELDS, tagged with its engine.
    """
    candidates = []
    for kind in ("visual_matches", "exact_matches"):
        for position, match in enumerate(raw_response.get(kind, []), 1):
            values = {
                "position": match.get("position", position),
                "title": match.get("title", "N/A"),
                "source": match.get("source", "N/A"),
                "page_url": match.get("link", "N/A"),
                "image_url": match.get("image", "N/A"),
                "thumbnail_url": match.get("thumbnail", "N/A"),
                "image_width": match.get("image_width"),
                "image_height": match.get("image_height"),
                "match_kind": kind,
                "engine": engine,
            }
            candidates.append({field: values[field] for field in _CANDIDATE_FIELDS})
    return candidates


def load_key() -> str:
    from face_search.key_store import load_key as _load

    return _load(search_dir=config.PROJECT_ROOT)
