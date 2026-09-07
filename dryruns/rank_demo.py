"""Dry run: threshold filter, dedupe, social boost. Zero searches."""

from face_search.rank import platform_of, rank_candidates


def main() -> None:
    items = [
        {"page_url": "https://example.com/a", "similarity": 0.9, "has_face": True},
        {"page_url": "https://github.com/jane", "similarity": 0.6, "has_face": True},
        {"page_url": "https://example.com/a", "similarity": 0.5, "has_face": True},
        {"page_url": "https://example.com/b", "similarity": 0.2, "has_face": True},
        {"page_url": "https://example.com/c", "similarity": 0.8, "has_face": False},
    ]
    print("input: 5 rows (duplicate, below-threshold, faceless included)")
    ordered = rank_candidates(items, threshold=0.45)
    print(f"output: {len(ordered)} rows")
    for row in ordered:
        print(f"- {row['similarity']} {platform_of(row['page_url'])} {row['page_url']}")


if __name__ == "__main__":
    main()
