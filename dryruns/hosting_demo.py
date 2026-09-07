"""Dry run: hosting wrapper (vendored ImgOps). Zero network for validation/mocking."""

from pathlib import Path
import tempfile

from face_search.hosting.imgops_uploader.client import _build_urls, _validate_file
from face_search.hosting.imgops_uploader.config import DEFAULT_MAX_SIZE_BYTES


def main() -> None:
    # pure validation
    print(f"5 MB limit: {DEFAULT_MAX_SIZE_BYTES}")
    p = Path(tempfile.NamedTemporaryFile(delete=False, suffix=".png").name)
    p.write_bytes(b"fake")
    try:
        _validate_file(p, max_bytes=DEFAULT_MAX_SIZE_BYTES)
        print("validate: OK for small file")
    finally:
        p.unlink(missing_ok=True)

    # URL building (pure)
    resp = "/imgops.com/1hr-tempcache/a_chandu.png"
    direct, ops, fname = _build_urls(resp)
    print(f"resp_path -> direct: {direct}")
    print(f"resp_path -> ops: {ops}")
    print("hosting is URL-only: local files are uploaded to ImgOps -> direct_url -> SerpApi url=")


if __name__ == "__main__":
    main()
