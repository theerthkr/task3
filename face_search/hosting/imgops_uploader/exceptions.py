"""
exceptions.py — Domain-specific errors.

Why separate file (SoC): callers can catch precise failures without parsing strings.
All ImgOps errors inherit from ImgOpsError for broad `except ImgOpsError` handling.
"""

class ImgOpsError(RuntimeError):
    """Base — all ImgOps failures."""


class ImgOpsValidationError(ImgOpsError, ValueError):
    """Input file invalid (missing, empty, too large, wrong type)."""


class ImgOpsNetworkError(ImgOpsError):
    """Transport failure (timeout, DNS, connection reset)."""


class ImgOpsUploadError(ImgOpsError):
    """Server returned unexpected response (non-2xx, missing Location/body, bad prefix)."""

    def __init__(self, message: str, *, status_code: int | None = None, body_preview: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body_preview = body_preview
