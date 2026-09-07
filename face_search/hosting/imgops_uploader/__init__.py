"""
imgops_uploader — public surface.

Single entry-point: consumers should import from here, not submodules.
This keeps the package boundary clean (facade pattern / SSOT for exports).
"""

from .client import upload_image, upload_image_bytes
from .config import (
    DEFAULT_MAX_SIZE_BYTES,
    IMGOPS_BASE_URL,
    STORE_URL,
)
from .exceptions import ImgOpsError, ImgOpsNetworkError, ImgOpsUploadError, ImgOpsValidationError
from .models import UploadResult

__all__ = [
    "upload_image",
    "upload_image_bytes",
    "UploadResult",
    "ImgOpsError",
    "ImgOpsValidationError",
    "ImgOpsNetworkError",
    "ImgOpsUploadError",
    "IMGOPS_BASE_URL",
    "STORE_URL",
    "DEFAULT_MAX_SIZE_BYTES",
]

__version__ = "1.0.0"
