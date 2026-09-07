"""Single source of truth for the SerpApi-only face-search pipeline.

Every tunables lives here so behaviour can be audited in one place.
Nothing in this module holds secrets.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SERPAPI_UPLOAD_URL = "https://serpapi.com/image"
SERPAPI_SEARCH_URL = "https://serpapi.com/search"
SERPAPI_ACCOUNT_URL = "https://serpapi.com/account.json"
LENS_ENGINE = "google_lens"

DEFAULT_TOP_N = 10
DEFAULT_THRESHOLD = 0.45
REQUEST_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 10

SOCIAL_DOMAINS = (
    "linkedin.com",
    "x.com",
    "twitter.com",
    "instagram.com",
    "github.com",
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

FACE_MODEL_PACK = "buffalo_l"
FACE_DET_SIZE = (640, 640)
