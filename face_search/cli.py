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
    parser.add_argument("--anchor", action="store_true", help="Anchor verified match hash on-chain (needs SEPOLIA_RPC_URL + SEPOLIA_PRIVATE_KEY + contract; else hash-only)")
    parser.add_argument("--anchor-top-k", type=int, default=1, help="How many verified matches to anchor (default 1 = best)")
    parser.add_argument("--verify-anchor", default="", help="Verify a saved report.json against on-chain state (read-only, needs SEPOLIA_RPC_URL + contract address)")
    parser.add_argument("--llm-model", default="", help="OpenRouter model for social-profile verdicts (default: free llama-3.3-70b). Needs OPENROUTER_API_KEY, else deterministic fallback.")
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
    # Blockchain anchoring summary
    bc = report.get("blockchain")
    if bc:
        lines.append(f"Blockchain: enabled={bc.get('enabled')} contract={bc.get('contract_address') or 'n/a'} network={bc.get('network') or 'n/a'}")
        if bc.get("note"):
            lines.append(f"  note: {bc['note']}")
        for it in bc.get("items", [])[:3]:
            if it.get("receipt"):
                lines.append(f"  anchored {it['bytes32_hex'][:10]}... -> tx {it['receipt']['transaction_hash'][:10]}... block {it['receipt']['block_number']} verify={it.get('verify')} | {it['receipt'].get('etherscan_tx_url')}")
            elif it.get("bytes32_hex"):
                lines.append(f"  hash {it['bytes32_hex'][:10]}... page {it.get('page_url')} | error: {it.get('error') or 'hash-only (no chain)'}")
        if bc.get("error"):
            lines.append(f"  blockchain error: {bc['error']}")
    lines.append(f"Run dir: {report['run_dir']}")
    return "\n".join(lines)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    # --verify-anchor is standalone read-only verification (no search)
    if args.verify_anchor:
        try:
            from face_search.blockchain_anchor import verify_report_file

            res = verify_report_file(args.verify_anchor)
            print(f"Verify {res['path']}")
            print(f"Contract {res.get('contract_address')} ({res.get('network')}) -> {res.get('etherscan_contract')}")
            for it in res.get("items", []):
                if it.get("error"):
                    print(f"  {it['bytes32_hex'][:10]}... error: {it['error']}")
                else:
                    print(f"  {it['bytes32_hex'][:10]}... {it.get('page_url')} -> verify={it.get('verify')} {'VERIFIED' if it.get('verify') else 'TAMPER/NOT_FOUND'}")
                    if it.get("on_chain_record"):
                        print(f"    on-chain source_url={it['on_chain_record']['source_url']} ts={it['on_chain_record']['timestamp']}")
        except Exception as err:
            print(f"ERROR verify: {err}", file=sys.stderr)
            return 1
        return 0
    try:
        report = pipeline.run(
            image=args.image,
            image_url=args.image_url,
            top_n=args.top,
            threshold=args.threshold,
            live=args.live,
            reuse_cache=args.reuse_cache,
            anchor=args.anchor,
            anchor_top_k=args.anchor_top_k,
            llm_model=args.llm_model,
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
