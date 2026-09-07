"""Ranking: threshold filter, dedupe, social boost. Pure functions, no I/O."""

from urllib.parse import urlparse

from face_search import config

_PLATFORM_BY_DOMAIN = {
    "linkedin.com": "linkedin",
    "x.com": "x",
    "twitter.com": "twitter",
    "instagram.com": "instagram",
    "github.com": "github",
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
