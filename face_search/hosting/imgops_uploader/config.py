"""
config.py — Single Source of Truth for all ImgOps constants.

Separation of Concerns: no I/O, no logic here. All other modules import from this file.
If ImgOps ever changes domain/path, edit ONE place.
"""

# Base
IMGOPS_BASE_URL = "https://imgops.com"
STORE_ENDPOINT = "/store"
STORE_URL = f"{IMGOPS_BASE_URL}{STORE_ENDPOINT}"

# Upload constraints (from site + dropper.js)
# Page says 5 MB, JS allows 10 MB for ajax; we enforce the stricter 5 MB by default
# but expose both so caller can choose.
MAX_SIZE_BYTES_PAGE = 5 * 1024 * 1024        # 5 MB (documented)
MAX_SIZE_BYTES_JS = 10 * 1024 * 1024         # 10 MB (dropper.js check)
DEFAULT_MAX_SIZE_BYTES = MAX_SIZE_BYTES_PAGE

# Form field names — SSOT so client + tests share them
FIELD_PHOTO = "photo"
FIELD_IS_AJAX = "isAjax"
VALUE_IS_AJAX_TRUE = "true"

# Response expectations
EXPECTED_PREFIX_NON_AJAX = "/imgops.com/1hr-tempcache/"  # redirect Location
EXPECTED_PREFIX_AJAX = "/imgops.com/1hr-tempcache/"      # body

# Networking
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_USER_AGENT = "imgops-uploader/1.0 (+personal project)"

# Expiry
CACHE_TTL_HOURS = 1
