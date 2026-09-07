"""Dry run: key_store loads every supported file format. Zero searches."""

import tempfile
from pathlib import Path

from face_search.key_store import load_key


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "api_key.json").write_text("RAW_KEY_ABC")
        print("raw file          ->", _masked(load_key(search_dir=base, env={})))
        (base / "api_key.json").write_text('{"api_key": "JSON_KEY_DEF"}')
        print("json object       ->", _masked(load_key(search_dir=base, env={})))
        (base / "api_key.json").write_text('SERP_API_KEY="ASSIGN_KEY_GHI"')
        print("name=value        ->", _masked(load_key(search_dir=base, env={})))
        print(
            "env precedence    ->",
            _masked(load_key(search_dir=base, env={"SERPAPI_KEY": "ENV_KEY_JKL"})),
        )


def _masked(key: str) -> str:
    return f"len={len(key)} value ends with …{key[-3:]}"


if __name__ == "__main__":
    main()
