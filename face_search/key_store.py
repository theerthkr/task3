"""Secret-safe SerpApi key loading.

Lookup order: $SERPAPI_KEY (including .env), then api_key.json beside the
project root. The file may hold the raw key, a NAME="value" assignment
(SERPAPI_KEY or SERP_API_KEY), or a small JSON object naming the key.
The key value is returned but never printed or logged anywhere.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

_KEY_FIELDS = ("api_key", "SERPAPI_KEY", "SERP_API_KEY", "serpapi_key", "key")


def load_key(search_dir=None, env=None) -> str:
    if env is None:
        load_dotenv()
        source = os.environ
    else:
        source = env
    key = (source.get("SERPAPI_KEY") or "").strip()
    if key:
        return key
    base = Path(search_dir) if search_dir is not None else Path.cwd()
    for name in ("api_key.json", ".api_key.json"):
        candidate = base / name
        if candidate.is_file():
            key = _read_key_file(candidate)
            if key:
                return key
    raise ValueError(
        "SerpApi key not found. Set SERPAPI_KEY or place the key in api_key.json."
    )


def _read_key_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return ""
    if text.startswith("{"):
        data = json.loads(text)
        if not isinstance(data, dict):
            return ""
        for field in _KEY_FIELDS:
            value = str(data.get(field, "")).strip()
            if value:
                return value
        return ""
    assignments = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        assignments[name.strip()] = value.strip().strip('"').strip("'")
    for field in _KEY_FIELDS:
        if assignments.get(field):
            return assignments[field]
    if len(assignments) == 1:
        single = next(iter(assignments.values()))
        if single:
            return single
    first = text.split()[0].strip('"').strip("'")
    if "=" in first:
        return ""
    return first
