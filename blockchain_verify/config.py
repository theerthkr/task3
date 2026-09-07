"""Single Source of Truth for blockchain_verify.

All tunable constants live here. No secrets, no side-effects.
Import this module anywhere instead of hard-coding values.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PACKAGE_ROOT = Path(__file__).resolve().parent
CONTRACT_DIR = PACKAGE_ROOT / "contract"
CONTRACT_SOL_PATH = CONTRACT_DIR / "VerificationRegistry.sol"
CONTRACT_DATA_PATH = CONTRACT_DIR / "contract_data.json"
SEPOLIA_DATA_PATH = CONTRACT_DIR / "contract_sepolia_data.json"  # alt location for Sepolia

# ---------------------------------------------------------------------------
# Chain / Network
# ---------------------------------------------------------------------------
SEPOLIA_CHAIN_ID = 11155111
LOCAL_CHAIN_IDS = (1337, 5777, 31337)  # Ganache / Hardhat / Anvil
SOLC_VERSION = "0.8.20"
CONTRACT_NAME = "VerificationRegistry"

# ---------------------------------------------------------------------------
# Gas
# ---------------------------------------------------------------------------
GAS_LIMIT_STORE = 300_000
GAS_LIMIT_DEPLOY = 2_000_000
# EIP-1559: baseFee * multiplier + priorityFee
BASE_FEE_MULTIPLIER = 2.5
DEFAULT_PRIORITY_FEE_GWEI = 2

# ---------------------------------------------------------------------------
# Env var names (SSOT for key resolution)
# ---------------------------------------------------------------------------
ENV_RPC_URL = "SEPOLIA_RPC_URL"
ENV_PRIVATE_KEY = "SEPOLIA_PRIVATE_KEY"
ENV_CONTRACT_ADDRESS = "SEPOLIA_CONTRACT_ADDRESS"
ENV_CHAIN_ID = "SEPOLIA_CHAIN_ID"

# Fallback (local chain) env names
ENV_LOCAL_RPC = "BLOCKCHAIN_RPC_URL"
ENV_LOCAL_KEY = "BLOCKCHAIN_PRIVATE_KEY"
DEFAULT_LOCAL_RPC = "http://127.0.0.1:8545"

# ---------------------------------------------------------------------------
# Hashing – edit this list to change what fields are included in the
# canonical evidence record. Keep sorted handling inside hashing.py.
# ---------------------------------------------------------------------------
# For generic face-match use case (HH Goa pipeline):
DEFAULT_RECORD_KEYS = [
    "face_distance",
    "face_match",
    "image_url",
    "source",
    "source_url",
    "title",
]

# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------
TX_TIMEOUT_SEC = 180
