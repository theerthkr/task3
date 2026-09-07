"""Dry run: parse a saved Lens response into candidate rows. Zero searches."""

import json
from pathlib import Path

from face_search.serp_client import _CANDIDATE_FIELDS, parse_results


def main() -> None:
    raw = json.loads(Path("tests/fixtures/lens_sample.json").read_text())
    rows = parse_results(raw)
    print(f"schema: {', '.join(_CANDIDATE_FIELDS)}")
    print(f"candidates: {len(rows)}")
    for row in rows:
        print(f"- [{row['match_kind']}/{row['engine']}] {row['title']}")
        print(f"  page: {row['page_url']}")
        print(f"  image: {row['image_url']}")


if __name__ == "__main__":
    main()
