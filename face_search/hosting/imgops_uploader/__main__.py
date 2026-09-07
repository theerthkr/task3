"""
CLI: python -m imgops_uploader <file>
Modularity: thin CLI wrapper around client.upload_image — no duplicated logic.
"""
from __future__ import annotations

import argparse
import sys

from .client import upload_image


def main() -> None:
    p = argparse.ArgumentParser(description="Upload an image to ImgOps temp cache (1-hour URL)")
    p.add_argument("file", help="path to image (png/jpg/webp, <=5 MB)")
    p.add_argument("--timeout", type=int, default=30, help="seconds")
    args = p.parse_args()

    try:
        res = upload_image(args.file, timeout=args.timeout)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"resp_path : {res.resp_path}")
    print(f"direct_url: {res.direct_url}")
    print(f"ops_url   : {res.ops_url}")
    print(f"filename  : {res.filename}")
    print("\n# expires in ~1 hour, do not use for permanent hosting")


if __name__ == "__main__":
    main()
