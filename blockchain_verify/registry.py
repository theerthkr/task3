"""On-chain registry ops: store / verify / get. Depends on client.py for connection.

Single responsibility: knows the VerificationRegistry ABI surface, not RPC plumbing.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from dotenv import load_dotenv

from . import config as cfg
from .client import ConnectedClient, connect
from .exceptions import ConfigurationError, RecordNotFoundError, TransactionError


def _load_abi_and_address(
    contract_address: str | None = None,
) -> tuple[list[Dict[str, Any]], str | None]:
    """Load ABI + address from env or JSON files (SOC: only ABI resolution)."""
    load_dotenv()
    env_addr = os.getenv(cfg.ENV_CONTRACT_ADDRESS)
    if env_addr and not env_addr.strip():
        env_addr = None

    abi: list[Dict[str, Any]] | None = None
    addr: str | None = contract_address or env_addr

    # JSON files are optional cache from deploy.py – check both locations
    for path in (cfg.SEPOLIA_DATA_PATH, cfg.CONTRACT_DATA_PATH):
        if path.exists():
            try:
                meta = json.loads(path.read_text(encoding="utf-8"))
                if abi is None and meta.get("abi"):
                    abi = meta["abi"]
                if addr is None and meta.get("contract_address"):
                    addr = meta["contract_address"]
            except Exception:
                continue

    return abi, addr  # type: ignore[return-value]


def _to_bytes32(w3: Any, hex_str: str) -> bytes:
    # normalise 0x prefix, validate length
    h = hex_str.strip()
    if not h.startswith("0x"):
        h = "0x" + h
    if len(h) != 66:  # 0x + 64 hex chars
        raise ValueError(f"bytes32_hex must be 0x + 64 hex chars, got '{hex_str}' ({len(h)} chars)")
    return w3.to_bytes(hexstr=h)  # type: ignore[attr-defined]


class Registry:
    """Bound contract handle. Create via Registry.attach(client, address).

    Example:
        client = connect()
        reg = Registry.attach(client)  # address from env/json
        receipt = reg.store(bytes32_hex, source_url)
        assert reg.verify(bytes32_hex) is True
    """

    def __init__(self, client: ConnectedClient, contract: Any, address: str, abi: list[Dict[str, Any]]):
        self.client = client
        self.contract = contract
        self.address = address
        self.abi = abi

    # ------------------------------------------------------------------ attach

    @classmethod
    def attach(
        cls,
        client: ConnectedClient,
        contract_address: str | None = None,
        abi: list[Dict[str, Any]] | None = None,
    ) -> "Registry":
        """Attach to a deployed VerificationRegistry."""
        from web3 import Web3  # type: ignore

        loaded_abi, loaded_addr = _load_abi_and_address(contract_address)
        final_abi = abi or loaded_abi
        final_addr = contract_address or loaded_addr

        if final_abi is None or final_addr is None:
            raise ConfigurationError(
                "Contract ABI/address not found. "
                "Set SEPOLIA_CONTRACT_ADDRESS in .env, pass contract_address explicitly, "
                "or run: python -m blockchain_verify.deploy"
            )

        checksum = Web3.to_checksum_address(final_addr)
        contract = client.w3.eth.contract(address=checksum, abi=final_abi)  # type: ignore[attr-defined]
        return cls(client=client, contract=contract, address=checksum, abi=final_abi)

    @classmethod
    def attach_from_env(cls, rpc_url: str | None = None, private_key: str | None = None, contract_address: str | None = None) -> "Registry":
        """Convenience: connect + attach in one call."""
        client = connect(rpc_url=rpc_url, private_key=private_key)
        return cls.attach(client, contract_address=contract_address)

    # ------------------------------------------------------------------ ops

    def verify(self, bytes32_hex: str) -> bool:
        """Call verifyRecord(bytes32) -> bool (read-only, no gas)."""
        b = _to_bytes32(self.client.w3, bytes32_hex)
        return bool(self.contract.functions.verifyRecord(b).call())

    def get(self, bytes32_hex: str) -> Dict[str, Any]:
        """Call getRecord(bytes32) -> {data_hash, source_url, timestamp}."""
        b = _to_bytes32(self.client.w3, bytes32_hex)
        try:
            data_hash, source_url, timestamp = self.contract.functions.getRecord(b).call()
        except Exception as exc:
            # sol revert "Record does not exist on-chain" -> map to typed error
            msg = str(exc)
            if "Record does not exist" in msg or "execution reverted" in msg:
                raise RecordNotFoundError(f"Record not found for {bytes32_hex}") from exc
            raise
        # data_hash is bytes; convert to 0x hex
        hex_hash = self.client.w3.to_hex(data_hash)  # type: ignore[attr-defined]
        return {"data_hash": hex_hash, "source_url": source_url, "timestamp": timestamp}

    def store(self, bytes32_hex: str, source_url: str) -> Dict[str, Any]:
        """Send storeRecord(bytes32, string) tx. Waits for receipt and returns metadata.

        Handles both EIP-1559 (Sepolia) and legacy (local) gas pricing.
        If client has a private_key, signs locally; otherwise uses unlocked node account.
        """
        w3 = self.client.w3
        b = _to_bytes32(w3, bytes32_hex)
        acct = self.client.account
        from_addr = self.client.account_address
        chain_id = self.client.chain.chain_id

        # Build tx params with EIP-1559 fallback
        try:
            latest = w3.eth.get_block("latest")  # type: ignore[attr-defined]
            base_fee = latest.get("baseFeePerGas", w3.eth.gas_price)  # type: ignore[attr-defined]
            try:
                priority_fee = w3.eth.max_priority_fee  # type: ignore[attr-defined]
            except Exception:
                priority_fee = w3.to_wei(cfg.DEFAULT_PRIORITY_FEE_GWEI, "gwei")  # type: ignore[attr-defined]
            max_fee = int(base_fee * cfg.BASE_FEE_MULTIPLIER) + int(priority_fee)
            tx_params: Dict[str, Any] = {
                "from": from_addr,
                "nonce": w3.eth.get_transaction_count(from_addr, "pending"),  # type: ignore[attr-defined]
                "gas": cfg.GAS_LIMIT_STORE,
                "maxFeePerGas": max_fee,
                "maxPriorityFeePerGas": int(priority_fee),
                "chainId": chain_id,
            }
        except Exception:
            tx_params = {
                "from": from_addr,
                "nonce": w3.eth.get_transaction_count(from_addr, "pending"),  # type: ignore[attr-defined]
                "gas": cfg.GAS_LIMIT_STORE,
                "gasPrice": int(w3.eth.gas_price * 1.5),  # type: ignore[attr-defined]
                "chainId": chain_id,
            }

        # Send
        if acct is not None:
            tx = self.contract.functions.storeRecord(b, source_url).build_transaction(tx_params)
            signed = w3.eth.account.sign_transaction(tx, acct.key)  # type: ignore[attr-defined]
            # web3.py v6: signed.raw_transaction, v5: signed.rawTransaction
            raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
            tx_hash = w3.eth.send_raw_transaction(raw)  # type: ignore[attr-defined]
        else:
            # unlocked node
            tx_hash = self.contract.functions.storeRecord(b, source_url).transact({"from": from_addr})

        tx_hex: str = tx_hash.hex()  # type: ignore[attr-defined]
        try:
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=cfg.TX_TIMEOUT_SEC)  # type: ignore[attr-defined]
        except Exception as exc:
            raise TransactionError(f"Timeout waiting for tx {tx_hex}") from exc

        status = getattr(receipt, "status", receipt.get("status", 1)) if isinstance(receipt, dict) else receipt.status  # type: ignore[union-attr]
        if status != 1:
            raise TransactionError(f"Transaction reverted: {tx_hex} (status {status})")

        block_number = getattr(receipt, "blockNumber", receipt.get("blockNumber")) if isinstance(receipt, dict) else receipt.blockNumber  # type: ignore[union-attr]
        gas_used = getattr(receipt, "gasUsed", receipt.get("gasUsed")) if isinstance(receipt, dict) else receipt.gasUsed  # type: ignore[union-attr]

        return {
            "transaction_hash": tx_hex,
            "block_number": block_number,
            "gas_used": gas_used,
            "status": status,
            "contract_address": self.address,
            "bytes32_hex": bytes32_hex if bytes32_hex.startswith("0x") else "0x" + bytes32_hex,
            "source_url": source_url,
            "network_name": self.client.chain.network_name,
            "chain_id": chain_id,
            "etherscan_tx_url": self.client.etherscan_tx_url(tx_hex),
            "etherscan_contract_url": self.client.etherscan_address_url(self.address),
        }

    # sugar ---------------------------------------------------------------

    def etherscan_tx_url(self, tx_hash: str) -> str:
        return self.client.etherscan_tx_url(tx_hash)

    def etherscan_contract_url(self) -> str:
        return self.client.etherscan_address_url(self.address)


# ---------------------------------------------------------------------------
# Functional sugar for one-shot use without instantiating Registry explicitly
# ---------------------------------------------------------------------------

def store_record(bytes32_hex: str, source_url: str, *, client: ConnectedClient | None = None, contract_address: str | None = None) -> Dict[str, Any]:
    """One-shot store: connect if needed, attach, store."""
    c = client or connect()
    reg = Registry.attach(c, contract_address=contract_address)
    return reg.store(bytes32_hex, source_url)


def verify_record(bytes32_hex: str, *, client: ConnectedClient | None = None, contract_address: str | None = None) -> bool:
    c = client or connect()
    reg = Registry.attach(c, contract_address=contract_address)
    return reg.verify(bytes32_hex)


def get_record(bytes32_hex: str, *, client: ConnectedClient | None = None, contract_address: str | None = None) -> Dict[str, Any]:
    c = client or connect()
    reg = Registry.attach(c, contract_address=contract_address)
    return reg.get(bytes32_hex)
