"""LLM judge (OpenRouter): is this match an actual social media profile of a person?

Opt-in: only runs when OPENROUTER_API_KEY is set. Any failure (no key,
network, bad JSON) returns a deterministic fallback so the pipeline never
breaks. The key is never logged.
"""

import json
import os

import requests

from face_search import config, rank

DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
TIMEOUT = 30
FETCH_TIMEOUT = 10

def _llm_base() -> str:
    for k in ("OPENROUTER_BASE_URL", "LLM_BASE_URL", "OPENAI_BASE_URL"):
        v = os.getenv(k, "").strip()
        if v:
            return v.rstrip("/")
    return "https://openrouter.ai/api/v1"

def _chat_url() -> str:
    return f"{_llm_base()}/chat/completions"

def _models_url() -> str:
    return f"{_llm_base()}/models"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

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

# Cache for fetched models (module-level)
_CACHED_MODELS: list[dict] | None = None
_CACHED_TS: float = 0

SYSTEM_PROMPT = (
    "You verify reverse-image-search matches. Given a web page that contains a "
    "photo matching the query face, decide whether the page is an ACTUAL person "
    "profile/page belonging to a person. PASS IMMEDIATELY if it is any profile URL "
    "like linkedin.com/in/*, github.com/<user>, x.com/<user>, instagram.com/<user>, "
    "bebee.com/in/people/*, bold.pro/*, devfolio.co/@*, medium.com/@*, kaggle.com/<user>, "
    "or any URL where the path clearly indicates a person (e.g. /people/, /profile/, /user/, /in/, /@). "
    "Also PASS article/post pages that clearly show the person's own profile card, bio, or handle – "
    "even if not classic social media, if the website is clearly a profile/post of the person, count it as profile. "
    "For famous people, prefer the official/verified account but still PASS any matching fan/official profile – "
    "show all similar matching profiles, do not filter to one. A company page, aggregator, or generic photo gallery "
    "with no person handle is NOT a profile. Reply with JSON only: {\"is_social_profile\": bool, \"confidence\": 0-1, "
    "\"display_name\": str|null, \"handle\": str|null, \"reason\": str (short)}."
)


def verdict_for_match(match: dict, model: str = DEFAULT_MODEL, snippet: str = "") -> dict:
    """LLM verdict for one ranked row. Falls back deterministically without a key."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip() or os.environ.get("OPENAI_API_KEY", "").strip()
    base = _llm_base()
    is_local = "localhost" in base or "127.0.0.1" in base
    if not api_key and not is_local:
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
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        resp = requests.post(
            _chat_url(),
            headers=headers,
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
            try:
                body = resp.text[:300] if hasattr(resp, "text") else ""
            except Exception:
                body = ""
            body_l = body.lower()
            is_paid = ":free" not in model and "free" not in model.lower()
            if resp.status_code == 401:
                return _fallback(match, reason=f"openrouter HTTP 401 invalid key — check OPENROUTER_API_KEY (not SERPAPI_KEY). {body[:120]}")
            if resp.status_code == 402:
                return _fallback(match, reason=f"openrouter HTTP 402 payment required — you selected a PAID model '{model}' but have no credits. Pick a :free model in UI. {body[:120]}")
            if resp.status_code == 404:
                return _fallback(match, reason=f"openrouter HTTP 404 model not found '{model}' — free models rotate, change model in UI (try google/gemini-2.0-flash-exp:free). {body[:120]}")
            if resp.status_code == 429:
                return _fallback(match, reason=f"openrouter HTTP 429 rate-limited — free tier throttled, wait 60s or switch model/add credits. {body[:120]}")
            if is_paid and ("free" in body_l or "credit" in body_l or "payment" in body_l):
                return _fallback(match, reason=f"openrouter HTTP {resp.status_code} paid model '{model}' needs credits — pick a :free model. {body[:120]}")
            return _fallback(match, reason=f"openrouter HTTP {resp.status_code} — {body[:120]}")
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
        name = type(err).__name__
        if "Timeout" in name or "timeout" in str(err).lower():
            return _fallback(match, reason=f"llm error: timeout after {TIMEOUT}s — OpenRouter overloaded, retry SEARCH")
        if "JSON" in name or "json" in str(err).lower():
            return _fallback(match, reason=f"llm error: bad JSON from model '{model}' — try another FREE_MODEL")
        return _fallback(match, reason=f"llm error: {name} — {str(err)[:120]}")


def _fallback(match: dict, reason: str) -> dict:
    platform = match.get("platform") or rank.platform_of(match.get("page_url", ""))
    page_url = (match.get("page_url") or "").lower()
    title = (match.get("title") or "").lower()
    source = (match.get("source") or "").lower()
    is_profile_hint = any(h in page_url for h in config.PROFILE_PATH_HINTS) or any(d in page_url for d in config.PROFILE_DOMAINS)
    is_profile_text = any(k in title or k in source for k in ("profile", "people", "github", "bebee", "bold.pro", "devfolio"))
    is_social = platform != "web" or is_profile_hint or is_profile_text
    return {
        "is_social_profile": is_social,
        "confidence": 0.65 if is_social else 0.35,
        "display_name": None,
        "handle": None,
        "reason": reason,
        "model": None,
        "llm_used": False,
    }


def fetch_models(force: bool = False) -> list[dict]:
    """Fetch all models from OpenRouter API (public, no key needed). Falls back to FREE_MODELS.

    Returns list of dicts: {id, name, context_length, pricing, is_free}
    Cached for 10 min.
    """
    global _CACHED_MODELS, _CACHED_TS
    import time
    now = time.time()
    if not force and _CACHED_MODELS is not None and now - _CACHED_TS < 600:
        return _CACHED_MODELS
    try:
        headers = {}
        ak = os.environ.get("OPENROUTER_API_KEY", "").strip() or os.environ.get("OPENAI_API_KEY", "").strip()
        if ak:
            headers["Authorization"] = f"Bearer {ak}"
        resp = requests.get(_models_url(), headers=headers, timeout=FETCH_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            raw = data.get("data", []) if isinstance(data, dict) else []
            models = []
            for m in raw:
                mid = m.get("id") or m.get("name") or ""
                if not mid:
                    continue
                pricing = m.get("pricing") or {}
                prompt_p = str(pricing.get("prompt", ""))
                comp_p = str(pricing.get("completion", ""))
                is_free = (prompt_p == "0" and comp_p == "0") or ":free" in mid
                models.append({
                    "id": mid,
                    "name": m.get("name") or mid,
                    "context_length": m.get("context_length") or m.get("context") or 0,
                    "pricing": pricing,
                    "is_free": is_free,
                    "raw": m,
                })
            models.sort(key=lambda x: (0 if x["is_free"] else 1, x["id"]))
            if models:
                _CACHED_MODELS = models
                _CACHED_TS = now
                return models
    except Exception:
        pass
    fallback = []
    for m in FREE_MODELS:
        fallback.append({"id": m["id"], "name": m["id"], "context_length": m["context"], "pricing": {"prompt": "0", "completion": "0"}, "is_free": True, "raw": m})
    _CACHED_MODELS = fallback
    _CACHED_TS = now
    return fallback


def judge_matches(matches: list, model: str = DEFAULT_MODEL, limit: int = 10) -> list:
    """Attach `llm` verdict to up to `limit` matches. Never raises. Judge all verified + top web."""
    judged = []
    for row in matches[:limit]:
        try:
            verdict = verdict_for_match(row, model=model)
        except Exception:
            verdict = _fallback(row, reason="unexpected judge error")
        judged.append({**row, "llm": verdict})
    return judged
