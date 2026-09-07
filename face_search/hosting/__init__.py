"""Hosting package facade — re-export vendored imgops_uploader.

This package is vendored from /home/loser/Documents/Default Project/image to url
and kept modular: all ImgOps constants live in imgops_uploader.config (SSOT).
We only re-export here for a clean import path:
    from face_search.hosting import upload_image
"""

from .imgops_uploader import (
    ImgOpsError,
    ImgOpsNetworkError,
    ImgOpsUploadError,
    ImgOpsValidationError,
    UploadResult,
    upload_image,
    upload_image_bytes,
)

__all__ = [
    "upload_image",
    "upload_image_bytes",
    "UploadResult",
    "ImgOpsError",
    "ImgOpsValidationError",
    "ImgOpsNetworkError",
    "ImgOpsUploadError",
]
