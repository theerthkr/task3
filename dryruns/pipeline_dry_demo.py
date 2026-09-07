"""Dry run: full pipeline in DRY_RUN mode plus cache replay. Zero searches."""

from face_search.cli import format_report
from face_search.pipeline import run

QUERY = "HHGOA-FACE-BLOCKCHAIN/test_images/person1_a.jpg"
CACHE = "tests/fixtures/lens_sample.json"


def main() -> None:
    print(format_report(run(image=QUERY, top_n=3)))
    print("-" * 60)
    print(format_report(run(image=QUERY, reuse_cache=CACHE, top_n=5)))


if __name__ == "__main__":
    main()
