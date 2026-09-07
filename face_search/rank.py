"""Ranking: threshold filter, dedupe, social boost. Pure functions, no I/O."""

from urllib.parse import urlparse

from face_search import config

_PLATFORM_BY_DOMAIN = {
    "linkedin.com": "linkedin",
    "x.com": "x",
    "twitter.com": "twitter",
    "instagram.com": "instagram",
    "github.com": "github",
    "bebee.com": "bebee",
    "bold.pro": "bold.pro",
    "devfolio.co": "devfolio",
    "medium.com": "medium",
    "kaggle.com": "kaggle",
    "dribbble.com": "dribbble",
    "behance.net": "behance",
}


def platform_of(page_url: str) -> str:
    host = urlparse(page_url or "").netloc.lower().removeprefix("www.")
    for domain, platform in _PLATFORM_BY_DOMAIN.items():
        if host == domain or host.endswith("." + domain):
            return platform
    return "web"


def is_social(page_url: str) -> bool:
    return platform_of(page_url) != "web"


def rank_candidates(items: list, threshold: float = config.DEFAULT_THRESHOLD) -> list:
    """Keep face-bearing matches at/above threshold, social profiles first."""
    best_by_url = {}
    for item in items:
        if not item.get("has_face"):
            continue
        similarity = item.get("similarity")
        if similarity is None or similarity < threshold:
            continue
        url = item.get("page_url", "")
        current = best_by_url.get(url)
        if current is None or similarity > current["similarity"]:
            best_by_url[url] = item
    return sorted(
        best_by_url.values(),
        key=lambda item: (not is_social(item.get("page_url", "")), -item["similarity"]),
    )


def rank_all(items: list) -> list:
    """Rank everyone by similarity (verified first, then rest), no threshold filter.

    Returns a new list sorted by:
      1. has_face (true first)
      2. similarity descending (None last)
      3. social profiles first within equal similarity
    Deduplicates by page_url keeping best similarity.
    """
    best_by_url: dict = {}
    for item in items:
        url = item.get("page_url", "")
        cur = best_by_url.get(url)
        sim = item.get("similarity")
        cur_sim = cur.get("similarity") if cur else None
        # keep the entry with highest similarity (None is lowest)
        if cur is None:
            best_by_url[url] = item
        elif sim is not None and (cur_sim is None or sim > cur_sim):
            best_by_url[url] = item
    def _key(row):
        has_face = 0 if row.get("has_face") else 1
        sim = row.get("similarity")
        sim_key = -(sim if sim is not None else -1.0)
        social_key = 0 if is_social(row.get("page_url", "")) else 1
        return (has_face, sim_key, social_key)
    return sorted(best_by_url.values(), key=_key)
