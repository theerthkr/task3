"""CLI: dry-run by default (spends nothing), --live spends one search."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from face_search import config, pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SerpApi-only face search. Default is a dry run (zero searches)."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", default="", help="Path to a local face image")
    source.add_argument("--image-url", default="", help="Public URL of a face image")
    parser.add_argument("--top", type=int, default=config.DEFAULT_TOP_N)
    parser.add_argument("--threshold", type=float, default=config.DEFAULT_THRESHOLD)
    parser.add_argument("--live", action="store_true", help="Spend one SerpApi search")
    parser.add_argument("--reuse-cache", default="", help="Replay a saved lens_raw.json")
    parser.add_argument("--out", default="", help="Write report JSON here as well")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = pipeline.run(
            image=args.image,
            image_url=args.image_url,
            top_n=args.top,
            threshold=args.threshold,
            live=args.live,
            reuse_cache=args.reuse_cache,
        )
    except Exception as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1
    print(f"Mode: {report['mode']} (searches spent: {report['searches_spent']})")
    if report["mode"] == "DRY_RUN":
        print(f"Query face: detected in {report['query']['path']}")
        print("No matches yet — rerun with --live or --reuse-cache.")
    else:
        print(f"Candidates: {report['candidates_found']} | Verified: {report['verified']}")
        for position, match in enumerate(report["matches"][:5], 1):
            print(f"[{position}] {match['similarity']} {match['platform']} {match['title']}")
            print(f"    {match['page_url']}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        print(f"Report: {args.out}")
    print(f"Run dir: {report['run_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
