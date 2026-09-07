"""RPC connection + account resolution. No contract ABI logic here (SOC)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

from . import config as cfg
from .exceptions import ConfigurationError, ConnectionError


def _norm_key(key: str | None) -> str | None:
    if not key:
        return None
    k = key.strip()
    if k and not k.startswith("0x"):
        k = "0x" + k
    return k if k else None


def _resolve_env() -> tuple[str | None, str | None, str | None]:
    """Return (rpc_url, private_key, contract_address) from env per priority."""
    load_dotenv()  # safe if .env missing
    sepolia_rpc = os.getenv(cfg.ENV_RPC_URL) or os.getenv(cfg.ENV_LOCAL_RPC) or None
    sepolia_key = os.getenv(cfg.ENV_PRIVATE_KEY) or os.getenv(cfg.ENV_LOCAL_KEY) or None
    sepolia_addr = os.getenv(cfg.ENV_CONTRACT_ADDRESS) or None
    # strip blanks -> None
    if sepolia_rpc and not sepolia_rpc.strip():
        sepolia_rpc = None
    if sepolia_key and not sepolia_key.strip():
        sepolia_key = None
    if sepolia_addr and not sepolia_addr.strip():
        sepolia_addr = None
    return sepolia_rpc, sepolia_key, sepolia_addr


@dataclass(frozen=True)
class ChainInfo:
    chain_id: int
    network_name: str
    rpc_url: str


def _network_name(chain_id: int) -> str:
    if chain_id == cfg.SEPOLIA_CHAIN_ID:
        return "Ethereum Sepolia"
    if chain_id in cfg.LOCAL_CHAIN_IDS:
        return "Local Chain"
    return f"Ethereum Network (Chain ID {chain_id})"


def connect(
    rpc_url: str | None = None,
    private_key: str | None = None,
    *,
    timeout: int = 10,
    require_account: bool = True,
) -> "ConnectedClient":
    """Connect to an RPC and resolve signing account.

    Priority for rpc_url/private_key:
      1. explicit args
      2. env (SEPOLIA_RPC_URL / BLOCKCHAIN_RPC_URL, SEPOLIA_PRIVATE_KEY)
      3. DEFAULT_LOCAL_RPC

    Returns:
        ConnectedClient with .w3, .chain, .account, .account_address
    Raises:
        ConnectionError if RPC unreachable.
        ConfigurationError if no signing account available and require_account=True.
        If require_account=False, returns client with account=None and dummy address for read-only calls.
    """
    # lazy import so hashing-only users don't need web3 installed
    try:
        from web3 import Web3  # type: ignore
    except ImportError as exc:
        raise ConfigurationError(
            "web3 is not installed. Run: pip install -r blockchain_verify/requirements.txt"
        ) from exc

    env_rpc, env_key, _ = _resolve_env()
    rpc = (rpc_url or env_rpc or cfg.DEFAULT_LOCAL_RPC).strip()
    key = _norm_key(private_key or env_key)

    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": timeout}))  # type: ignore[arg-type]
    if not w3.is_connected():
        raise ConnectionError(
            f"Could not connect to RPC at '{rpc}'. "
            "Check SEPOLIA_RPC_URL / BLOCKCHAIN_RPC_URL in .env, or start local node."
        )

    chain_id = w3.eth.chain_id  # type: ignore[attr-defined]
    chain = ChainInfo(chain_id=chain_id, network_name=_network_name(chain_id), rpc_url=rpc)

    # Resolve account
    account = None
    account_address: str | None = None
    if key:
        account = w3.eth.account.from_key(key)  # type: ignore[attr-defined]
        account_address = account.address
    else:
        # Use first unlocked node account (Ganache/Hardhat)
        accounts: list[str] = w3.eth.accounts  # type: ignore[attr-defined]
        if accounts:
            account_address = accounts[0]
            account = None
        else:
            if require_account:
                raise ConfigurationError(
                    "No private key and no unlocked node accounts available for signing. "
                    f"Set {cfg.ENV_PRIVATE_KEY} in .env or use a local node with unlocked accounts."
                )
            # read-only mode – dummy address, no signing
            account = None
            account_address = "0x0000000000000000000000000000000000000000"

    return ConnectedClient(w3=w3, chain=chain, account=account, account_address=account_address)  # type: ignore[arg-type]


@dataclass
class ConnectedClient:
    """Thin wrapper around Web3 + signing identity. No ABI knowledge."""

    w3: Any  # Web3
    chain: ChainInfo
    account: Any | None  # LocalAccount or None (unlocked node)
    account_address: str

    # helpers ---------------------------------------------------------------

    def etherscan_tx_url(self, tx_hash: str) -> str:
        if self.chain.chain_id == cfg.SEPOLIA_CHAIN_ID:
            clean = tx_hash if tx_hash.startswith("0x") else "0x" + tx_hash
            return f"https://sepolia.etherscan.io/tx/{clean}"
        return "N/A (Local Chain)"

    def etherscan_address_url(self, address: str) -> str:
        if self.chain.chain_id == cfg.SEPOLIA_CHAIN_ID:
            return f"https://sepolia.etherscan.io/address/{address}"
        return "N/A (Local Chain)"

    def wait_for_receipt(self, tx_hash: Any, timeout: int = cfg.TX_TIMEOUT_SEC) -> Any:
        return self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
