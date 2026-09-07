"""Social leads: extract outbound social profile links from a verified match page.

Pure extraction + thin fetcher, no LLM, no SerpApi spend. Reuses rank.platform_of
as the single source of truth for what counts as social.
"""

import re

import requests

from face_search import config, rank

_HREF = re.compile(r'''href\s*=\s*["']([^"'#]+)["']''', re.IGNORECASE)
_MAX_HTML_BYTES = 2 * 1024 * 1024


def extract_social_links(page_url: str, html: str = "") -> list:
    """Outbound social links found in html. Returns [{platform, url, handle}]."""
    leads, seen = [], set()
    for href in _HREF.findall(html or ""):
        href = href.strip()
        if not href.startswith("http"):
            continue
        platform = rank.platform_of(href)
        if platform == "web":
            continue
        handle = _handle_from_url(platform, href)
        key = (platform, handle or href)
        if key in seen:
            continue
        seen.add(key)
        leads.append({"platform": platform, "url": href, "handle": handle, "from_page": page_url})
    # social-first ordering matching rank.py convention
    order = {"linkedin": 0, "github": 1, "x": 2, "twitter": 2, "instagram": 3}
    return sorted(leads, key=lambda l: order.get(l["platform"], 9))


def fetch_page_html(page_url: str) -> str:
    """Best-effort HTML fetch. Returns '' on any failure (never raises)."""
    try:
        resp = requests.get(
            page_url,
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.DOWNLOAD_TIMEOUT,
            stream=True,
        )
        if resp.status_code != 200:
            return ""
        chunks, size = [], 0
        for chunk in resp.iter_content(chunk_size=8192, decode_unicode=True):
            if not chunk:
                continue
            if isinstance(chunk, bytes):
                chunk = chunk.decode("utf-8", errors="replace")
            size += len(chunk)
            if size > _MAX_HTML_BYTES:
                break
            chunks.append(chunk)
        return "".join(chunks)
    except Exception:
        return ""


def leads_for_match(match: dict, html: str = "") -> list:
    """Social leads for one ranked row. Pass html to skip fetching (tests)."""
    page_url = match.get("page_url", "")
    if not page_url:
        return []
    if not html:
        html = fetch_page_html(page_url)
    if not html:
        return []
    return extract_social_links(page_url, html)


def _handle_from_url(platform: str, url: str) -> str:
    from urllib.parse import urlparse

    parts = [p for p in urlparse(url).path.strip("/").split("/") if p]
    if not parts:
        return ""
    if platform == "linkedin" and parts[0].lower() in ("in", "company") and len(parts) > 1:
        return parts[1].split("?")[0]
    return parts[0].split("?")[0]
