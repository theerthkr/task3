"""Single source of truth for the SerpApi-only face-search pipeline.

Every tunables lives here so behaviour can be audited in one place.
Nothing in this module holds secrets.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SERPAPI_SEARCH_URL = "https://serpapi.com/search"
SERPAPI_ACCOUNT_URL = "https://serpapi.com/account.json"
LENS_ENGINE = "google_lens"

DEFAULT_TOP_N = 0  # 0 = no limit: ingest all SerpApi hits at once
DEFAULT_THRESHOLD = 0.45
REQUEST_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 10
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024

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

# Hosting (vendored ImgOps — SSOT lives in hosting/imgops_uploader/config.py)
try:
    from face_search.hosting.imgops_uploader.config import CACHE_TTL_HOURS as _HOST_TTL

    HOST_TTL_HOURS = _HOST_TTL
except Exception:
    HOST_TTL_HOURS = 1
HOST_PROVIDER = "imgops.com"

QUERY_FILENAME = "query.jpg"
RAW_FILENAME = "lens_raw.json"
REPORT_FILENAME = "report.json"
CANDIDATE_DIR = "candidates"
CANDIDATE_PATTERN = "candidate_{position}.jpg"
