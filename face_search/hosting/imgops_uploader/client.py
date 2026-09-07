"""
client.py — Core upload logic. Depends on config/models/exceptions, owns I/O.

Design principles applied:
- Single Responsibility: only does "file -> temp URL"
- Single Source of Truth: all URLs/thresholds imported from config.py
- Dependency Inversion: accepts path/bytes, returns domain model (UploadResult)
- Fail-fast validation before network
- No hidden side-effects: no global state, no print inside library code
"""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path

import requests

from .config import (
    DEFAULT_MAX_SIZE_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_USER_AGENT,
    EXPECTED_PREFIX_AJAX,
    FIELD_IS_AJAX,
    FIELD_PHOTO,
    IMGOPS_BASE_URL,
    STORE_URL,
    VALUE_IS_AJAX_TRUE,
)
from .exceptions import ImgOpsNetworkError, ImgOpsUploadError, ImgOpsValidationError
from .models import UploadResult

# ---------------------------------------------------------------------------
# internal helpers (not exported)
# ---------------------------------------------------------------------------

def _validate_file(path: Path, *, max_bytes: int) -> Path:
    """Raise ImgOpsValidationError if file is missing/empty/too large."""
    if not path.exists():
        raise ImgOpsValidationError(f"file not found: {path}")
    if not path.is_file():
        raise ImgOpsValidationError(f"not a file: {path}")
    size = path.stat().st_size
    if size == 0:
        raise ImgOpsValidationError(f"file is empty (0 bytes): {path}")
    if size > max_bytes:
        raise ImgOpsValidationError(
            f"file too large: {size} bytes > {max_bytes} bytes "
            f"({max_bytes/1024/1024:.1f} MB limit). "
            f"ImgOps temp cache is only 5 MB per the upload page."
        )
    return path


def _guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def _build_urls(resp_path: str) -> tuple[str, str, str]:
    """
    Turn server resp_path into (direct_url, ops_url, filename).
    resp_path is like "/imgops.com/1hr-tempcache/..._chandu.png"
    direct_url strips the leading "/imgops.com" segment.
    """
    if not resp_path.startswith("/"):
        raise ImgOpsUploadError(f"unexpected resp_path (no leading '/'): {resp_path!r}")
    if EXPECTED_PREFIX_AJAX not in resp_path:
        raise ImgOpsUploadError(f"unexpected resp_path prefix: {resp_path!r}")

    # direct: https://imgops.com/1hr-tempcache/...
    direct_url = f"{IMGOPS_BASE_URL}{resp_path.removeprefix('/imgops.com')}"
    # ops: https://imgops.com/imgops.com/1hr-tempcache/...
    ops_url = f"{IMGOPS_BASE_URL}{resp_path}"
    filename = resp_path.rsplit("/", 1)[-1]
    return direct_url, ops_url, filename


def _parse_ajax_body(body: str) -> str:
    """Ajax mode returns plain text path. Strip whitespace and validate."""
    p = body.strip()
    if not p:
        raise ImgOpsUploadError("empty response body from /store (expected path)")
    if not p.startswith("/"):
        # sometimes Cloudflare returns HTML on error — surface preview
        raise ImgOpsUploadError(
            f"unexpected body (expected '/imgops.com/1hr-tempcache/...'): {p[:400]!r}",
            body_preview=p[:800],
        )
    return p


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def upload_image(
    file_path: str | os.PathLike,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = DEFAULT_MAX_SIZE_BYTES,
    mime_type: str | None = None,
    session: requests.Session | None = None,
) -> UploadResult:
    """
    Upload a local image to ImgOps temp cache and return usable URLs.

    Flow:
        1. validate file (exists, size)
        2. POST multipart/form-data to STORE_URL with fields:
               photo=<file>, isAjax=true
        3. parse plain-text body -> resp_path
        4. derive direct_url + ops_url

    Args:
        file_path: path to png/jpg/webp/etc
        timeout: seconds for the POST
        max_bytes: reject files larger than this (default 5 MB)
        mime_type: override guessed mime (e.g. "image/png")
        session: optional requests.Session for connection reuse/tests

    Returns: UploadResult (frozen dataclass)

    Raises:
        ImgOpsValidationError | ImgOpsNetworkError | ImgOpsUploadError

    Example:
        >>> res = upload_image("/home/loser/Pictures/chandu.png")
        >>> res.direct_url  # for <img src> or hotlinking (1 hour)
        'https://imgops.com/1hr-tempcache/..._chandu.png'
        >>> res.ops_url     # for browser with all tool links
        'https://imgops.com/imgops.com/1hr-tempcache/..._chandu.png'
    """
    path = _validate_file(Path(file_path), max_bytes=max_bytes)
    mime = mime_type or _guess_mime(path)

    # Use provided session or a one-off request; always set a UA so Cloudflare doesn't block
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    files = {FIELD_PHOTO: (path.name, path.open("rb"), mime)}
    data = {FIELD_IS_AJAX: VALUE_IS_AJAX_TRUE}

    close_files = True  # we opened the file handle above; ensure cleanup
    try:
        try:
            if session is not None:
                resp = session.post(STORE_URL, files=files, data=data, headers=headers, timeout=timeout)
            else:
                resp = requests.post(STORE_URL, files=files, data=data, headers=headers, timeout=timeout)
        except requests.RequestException as e:
            raise ImgOpsNetworkError(f"network error posting to {STORE_URL}: {e}") from e

        # Ajax endpoint always returns 200 + body on success; any non-2xx is failure
        if not (200 <= resp.status_code < 300):
            raise ImgOpsUploadError(
                f"upload failed: HTTP {resp.status_code} from {STORE_URL}",
                status_code=resp.status_code,
                body_preview=resp.text[:800] if hasattr(resp, "text") else None,
            )

        # Body is the path; decode as text
        body = resp.text if isinstance(resp.text, str) else resp.content.decode("utf-8", errors="replace")
        resp_path = _parse_ajax_body(body)
        direct_url, ops_url, filename = _build_urls(resp_path)
        return UploadResult(
            resp_path=resp_path,
            direct_url=direct_url,
            ops_url=ops_url,
            filename=filename,
        )
    finally:
        # close file handle opened in `files`
        if close_files:
            try:
                files[FIELD_PHOTO][1].close()
            except Exception:
                pass


def upload_image_bytes(
    data: bytes,
    filename: str = "upload.png",
    *,
    mime_type: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> UploadResult:
    """
    Variant that uploads raw bytes without a file on disk.
    Useful for in-memory images (PIL save to BytesIO, etc).

    Same server contract as upload_image.
    """
    if not data:
        raise ImgOpsValidationError("data is empty (0 bytes)")
    if len(data) > DEFAULT_MAX_SIZE_BYTES:
        raise ImgOpsValidationError(
            f"data too large: {len(data)} > {DEFAULT_MAX_SIZE_BYTES}"
        )
    mime = mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    files = {FIELD_PHOTO: (filename, data, mime)}
    payload = {FIELD_IS_AJAX: VALUE_IS_AJAX_TRUE}

    try:
        resp = requests.post(STORE_URL, files=files, data=payload, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        raise ImgOpsNetworkError(f"network error posting bytes to {STORE_URL}: {e}") from e

    if not (200 <= resp.status_code < 300):
        raise ImgOpsUploadError(
            f"upload failed: HTTP {resp.status_code}",
            status_code=resp.status_code,
            body_preview=resp.text[:800] if hasattr(resp, "text") else None,
        )

    resp_path = _parse_ajax_body(resp.text if isinstance(resp.text, str) else resp.content.decode())
    direct_url, ops_url, out_name = _build_urls(resp_path)
    return UploadResult(resp_path=resp_path, direct_url=direct_url, ops_url=ops_url, filename=out_name)
