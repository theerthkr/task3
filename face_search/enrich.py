"""Enrichment: turn a verified match into a human-actionable lead.

Pure functions, no I/O/network. Extracts:
- handle / username (from platform URL)
- display_name / company hint (from title/source)
- profile_type (social_profile vs web_page)
Separated from pipeline/rank so it can be tested and fixed in isolation.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from face_search import config

# Reuse platform detection for SSOT.
from face_search.rank import platform_of

_SOCIAL = set(config.SOCIAL_DOMAINS)

# Title splitters most sites use: "Name | Company" or "Name - Company"
_TITLE_SPLIT = re.compile(r"\s*[|\-–—]\s*")


def extract_handle(page_url: str) -> str | None:
    """Best-effort handle/username from a social page_url.

    github.com/<user>[/...] -> <user>
    x.com/<user>/...      -> <user>
    twitter.com/<user>     -> <user>
    instagram.com/<user>   -> <user>
    linkedin.com/in/<user> -> <user>  (also /pub/<user>)
    Returns None for non-social or unparseable URLs.
    """
    parsed = urlparse(page_url or "")
    host = (parsed.netloc or "").lower().removeprefix("www.")
    path = (parsed.path or "").strip("/")
    if not host or not path:
        return None
    parts = [p for p in path.split("/") if p]

    if host in ("github.com",) and parts:
        return parts[0]
    if host in ("x.com", "twitter.com", "instagram.com") and parts:
        # x/twitter/instagram: first path segment is the handle
        handle = parts[0]
        # filter obvious non-profile paths
        if handle.lower() in ("home", "explore", "search", "hashtag", "p"):
            return None
        return handle
    if host == "linkedin.com" and parts:
        # /in/<handle> or /pub/<handle> or /company/<handle>
        if parts[0].lower() in ("in", "pub") and len(parts) >= 2:
            return parts[1].split("?")[0]
        if parts[0].lower() == "company" and len(parts) >= 2:
            return parts[1].split("?")[0]
        # sometimes linkedin directly is /in/... so covered; fallback: first segment
        return None
    # subdomains like sub.linkedin.com are already normalized via platform_of, but handle host suffix
    for domain in _SOCIAL:
        if host == domain or host.endswith("." + domain):
            # generic: first segment as handle if we haven't matched above
            return parts[0].split("?")[0] if parts else None
    return None


def extract_display_name(title: str) -> tuple[str | None, str | None]:
    """Split a title like 'Chandraveer Singh Solanki | Find professionals …' into (name, company_hint)."""
    if not title or title == "N/A":
        return None, None
    # Take the first segment before | - etc as the likely name.
    head = _TITLE_SPLIT.split(title, maxsplit=1)
    name = head[0].strip() if head and head[0].strip() else None
    company = head[1].strip() if len(head) > 1 and head[1].strip() else None
    # Heuristic: if name is too long (>60 chars) it's probably not a person name.
    if name and len(name) > 60:
        name = None
    if company and len(company) > 80:
        company = company[:80]
    return name, company


def enrich_match(match: dict) -> dict:
    """Enrich a single rank-ranked match (from _present_match shape).

    Input expects keys: title, source, platform, page_url, image_url, similarity.
    Output adds: handle, profile_type, display_name, company_hint, is_social.
    Pure — returns a new dict, does not mutate input.
    """
    page_url = match.get("page_url", "")
    title = match.get("title", "")
    platform = match.get("platform") or platform_of(page_url)
    is_social = platform != "web"
    handle = extract_handle(page_url) if is_social else None
    display_name, company_hint = extract_display_name(title)

    enriched = dict(match)
    enriched.update(
        {
            "handle": handle,
            "profile_type": "social_profile" if is_social else "web_page",
            "is_social": is_social,
            "display_name": display_name,
            "company_hint": company_hint,
        }
    )
    return enriched


def enrich_matches(matches: list[dict]) -> list[dict]:
    """Enrich a list of matches. Thin wrapper over enrich_match."""
    return [enrich_match(m) for m in matches]
