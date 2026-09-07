"""LLM judge (OpenRouter): is this match an actual social media profile of a person?

Opt-in: only runs when OPENROUTER_API_KEY is set. Any failure (no key,
network, bad JSON) returns a deterministic fallback so the pipeline never
breaks. The key is never logged.
"""

import json
import os

import requests

from face_search import config, rank

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
TIMEOUT = 30

# SSOT for model choice (UI selectbox + docs). Free :free models rotate —
# confirm live at https://openrouter.ai/models. Our verdict call is tiny
# (~600 in / ~150 out tokens), so any of these is plenty.
FREE_MODELS = (
    {"id": "meta-llama/llama-3.3-70b-instruct:free", "context": "128K",
     "note": "Default. Strong instruction-following, reliable JSON."},
    {"id": "google/gemini-2.0-flash-exp:free", "context": "1M",
     "note": "Huge context for long page excerpts; fast."},
    {"id": "deepseek/deepseek-r1:free", "context": "163K",
     "note": "Reasoning model; slower but good on ambiguous pages."},
)

SYSTEM_PROMPT = (
    "You verify reverse-image-search matches. Given a web page that contains a "
    "photo matching the query face, decide whether the page is an ACTUAL social "
    "media profile/page belonging to a person (e.g. linkedin.com/in/*, "
    "github.com/<user>, x.com/<user>, instagram.com/<user>, bebee.com people "
    "profiles, devfolio cards are NOT profiles). A profile shows the person's "
    "own account (posts, bio, handle). A company page, aggregator, article "
    "mentioning them, or photo gallery is NOT a profile even if their face "
    "appears. Famous people: prefer the official/verified account over fan pages. "
    "Reply with JSON only: {\"is_social_profile\": bool, \"confidence\": 0-1, "
    "\"display_name\": str|null, \"handle\": str|null, \"reason\": str (short)}."
)


def verdict_for_match(match: dict, model: str = DEFAULT_MODEL, snippet: str = "") -> dict:
    """LLM verdict for one ranked row. Falls back deterministically without a key."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return _fallback(match, reason="no OPENROUTER_API_KEY; deterministic fallback")
    page_url = match.get("page_url", "")
    user_text = (
        f"title: {match.get('title')}\nsource: {match.get('source')}\n"
        f"platform: {match.get('platform')}\npage_url: {page_url}\n"
        f"face similarity: {match.get('similarity')}\n"
    )
    if snippet:
        user_text += f"page excerpt: {snippet[:2000]}\n"
    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0,
            },
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return _fallback(match, reason=f"openrouter HTTP {resp.status_code}")
        content = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        return {
            "is_social_profile": bool(data.get("is_social_profile", False)),
            "confidence": float(data.get("confidence", 0) or 0),
            "display_name": data.get("display_name"),
            "handle": data.get("handle"),
            "reason": str(data.get("reason", ""))[:300],
            "model": model,
            "llm_used": True,
        }
    except Exception as err:
        return _fallback(match, reason=f"llm error: {type(err).__name__}")


def _fallback(match: dict, reason: str) -> dict:
    platform = match.get("platform") or rank.platform_of(match.get("page_url", ""))
    return {
        "is_social_profile": platform != "web",
        "confidence": 0.5,
        "display_name": None,
        "handle": None,
        "reason": reason,
        "model": None,
        "llm_used": False,
    }


def judge_matches(matches: list, model: str = DEFAULT_MODEL, limit: int = 5) -> list:
    """Attach `llm` verdict to up to `limit` matches. Never raises."""
    judged = []
    for row in matches[:limit]:
        try:
            verdict = verdict_for_match(row, model=model)
        except Exception:
            verdict = _fallback(row, reason="unexpected judge error")
        judged.append({**row, "llm": verdict})
    return judged
