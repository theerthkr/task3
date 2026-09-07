"""Candidate image downloading. Protocol: try, validate, clean up on failure."""

import os

import requests
from PIL import Image

from face_search import config


def download_image(url: str, save_path: str) -> bool:
    if not url or not url.startswith("http"):
        return False
    try:
        response = requests.get(
            url,
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.DOWNLOAD_TIMEOUT,
            stream=True,
        )
        if response.status_code != 200:
            return False
        size = 0
        with open(save_path, "wb") as handle:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    size += len(chunk)
                    if size > config.MAX_DOWNLOAD_BYTES:
                        raise ValueError("Download exceeded size cap.")
                    handle.write(chunk)
        with Image.open(save_path) as image:
            image.verify()
        return True
    except Exception:
        if os.path.exists(save_path):
            try:
                os.remove(save_path)
            except OSError:
                pass
        return False


def fetch_query_image(image: str = "", image_url: str = "", save_path: str = "") -> str:
    """Resolve the query to a local file. Returns its path."""
    if bool(image) == bool(image_url):
        raise ValueError("Pass exactly one of image or image_url.")
    if image:
        if not os.path.exists(image):
            raise FileNotFoundError(f"Query image not found: {image!r}")
        return image
    if not save_path:
        raise ValueError("save_path is required when resolving an image URL.")
    if not download_image(image_url, save_path):
        raise RuntimeError(f"Could not download query image: {image_url}")
    return save_path
