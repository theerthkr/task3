"""
models.py — Pure data containers. No logic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UploadResult:
    """
    Represents a successful temp upload.

    Attributes:
        resp_path: raw server value, e.g. "/imgops.com/1hr-tempcache/..._chandu.png"
        direct_url: raw image URL, e.g. "https://imgops.com/1hr-tempcache/...png"
        ops_url: human/viewer page, e.g. "https://imgops.com/imgops.com/1hr-tempcache/...png"
        filename: basename from server (useful for logging)
    """
    resp_path: str
    direct_url: str
    ops_url: str
    filename: str

    def __str__(self) -> str:
        return f"UploadResult(direct_url={self.direct_url!r})"
