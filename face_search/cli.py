"""CLI: dry-run by default (spends nothing), --live spends one search.

URL-only workflow: local files are hosted to a 1-hour public URL via
face_search.hosting (ImgOps) before SerpApi is called.
"""

import argparse
import json
import sys

from face_search import config, pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SerpApi face search (URL-only: local files are hosted to a 1h URL, then Lens). Default is dry run (zero searches)."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", default="", help="Path to a local face image (will be hosted to a temp 1h URL)")
    source.add_argument("--image-url", default="", help="Public URL of a face image")
    parser.add_argument("--top", type=int, default=config.DEFAULT_TOP_N)
    parser.add_argument("--threshold", type=float, default=config.DEFAULT_THRESHOLD)
    parser.add_argument("--live", action="store_true", help="Spend one SerpApi search")
    parser.add_argument("--reuse-cache", default="", help="Replay a saved lens_raw.json")
    parser.add_argument("--out", default="", help="Write report JSON here as well")
    return parser


def format_report(report: dict) -> str:
    lines = [f"Mode: {report['mode']} (searches spent: {report['searches_spent']})"]
    hosted = report.get("query", {}).get("hosted_url")
    if hosted:
        lines.append(f"Hosted URL (1h): {hosted}")
    if report["mode"] == "DRY_RUN":
        lines.append(f"Query face: detected in {report['query']['path']}")
        lines.append("No matches yet — rerun with --live or --reuse-cache.")
    else:
        ranked = report.get("ranked") or report.get("matches") or []
        lines.append(
            f"Candidates: {report['candidates_found']} | Ranked: {len(ranked)} | Verified: {report['verified']}"
        )
        for position, row in enumerate(ranked[:10], 1):
            lines.append(
                f"[{position}] sim={row.get('similarity')} has_face={row.get('has_face')} verified={row.get('verified')} {row.get('platform')} | {row.get('title')}"
            )
            lines.append(f"    source: {row.get('source')} | {row.get('page_url')}")
            llm = row.get("llm") or {}
            if llm.get("llm_used"):
                handle = f" @{llm['handle']}" if llm.get("handle") else ""
                lines.append(
                    f"    LLM: social_profile={llm.get('is_social_profile')} conf={llm.get('confidence')}{handle} — {llm.get('reason')}"
                )
        if ranked and report["verified"] == 0:
            lines.append("Note: ranked list shows all candidates sorted by similarity — none crossed threshold.")
    lines.append(f"Run dir: {report['run_dir']}")
    return "\n".join(lines)


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
    print(format_report(report))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        print(f"Report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
