"""Secret-safe SerpApi key loading.

Lookup order: $SERPAPI_KEY, then api_key.json beside the project root.
The file may hold the raw key or a small JSON object naming it.
The key value is returned but never printed or logged anywhere.
"""

import json
import os
from pathlib import Path

_KEY_FIELDS = ("api_key", "SERPAPI_KEY", "serpapi_key", "key")


def load_key(search_dir=None, env=None) -> str:
    source = env if env is not None else os.environ
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
    text = path.read_text(encoding="utf-8-sig").strip().strip('"').strip("'")
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
    return text.split()[0]
