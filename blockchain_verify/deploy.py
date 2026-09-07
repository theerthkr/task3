"""Compile + deploy VerificationRegistry. Works with Sepolia or any local chain.

Usage:
  python -m blockchain_verify.deploy                 # uses env (SEPOLIA_RPC_URL etc.)
  python -m blockchain_verify.deploy --local         # forces local chain (http://127.0.0.1:8545)
  python -m blockchain_verify.deploy --rpc https://... --private-key 0x... --no-env-write

Separation: this module owns compilation + deployment only. It does NOT know
hashing; it just deploys whatever is in contract/VerificationRegistry.sol.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

from dotenv import load_dotenv

from . import config as cfg
from .exceptions import ConfigurationError, DeploymentError

# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------

def compile_contract(solc_version: str | None = None) -> Tuple[list[Dict[str, Any]], str]:
    """Compile VerificationRegistry.sol via py-solc-x.

    Returns:
        (abi, bytecode_hex_without_0x)
    Raises:
        DeploymentError if solc not installed / compile fails.
    """
    version = solc_version or cfg.SOLC_VERSION
    src_path = cfg.CONTRACT_SOL_PATH
    if not src_path.exists():
        raise DeploymentError(f"Contract source not found: {src_path}")

    try:
        from solcx import compile_standard, install_solc, set_solc_version  # type: ignore
    except ImportError as exc:
        raise ConfigurationError(
            "py-solc-x is not installed. Run: pip install -r blockchain_verify/requirements.txt"
        ) from exc

    try:
        install_solc(version)
        set_solc_version(version)
    except Exception as exc:
        # already installed is fine, but surface unexpected errors
        print(f"[!] solc setup notice: {exc}", file=sys.stderr)

    source = src_path.read_text(encoding="utf-8")

    try:
        compiled = compile_standard(
            {
                "language": "Solidity",
                "sources": {src_path.name: {"content": source}},
                "settings": {
                    "outputSelection": {"*": {"*": ["abi", "metadata", "evm.bytecode", "evm.sourceMap"]}}
                },
            },
            solc_version=version,
        )
    except Exception as exc:
        raise DeploymentError(f"Compilation failed: {exc}") from exc

    try:
        data = compiled["contracts"][src_path.name][cfg.CONTRACT_NAME]
        abi = data["abi"]
        bytecode = data["evm"]["bytecode"]["object"]
    except KeyError as exc:
        raise DeploymentError(f"Compilation output missing expected keys: {exc}\n{json.dumps(compiled, indent=2)[:2000]}") from exc

    if not bytecode:
        raise DeploymentError("Compilation produced empty bytecode.")
    return abi, bytecode


# ---------------------------------------------------------------------------
# Deployment
# ---------------------------------------------------------------------------

def _update_env_contract_address(contract_address: str, env_path: Path | None = None) -> None:
    """Upsert SEPOLIA_CONTRACT_ADDRESS in .env (project root .env preferred)."""
    # Search: blockchain_verify/.env, project root .env, cwd .env
    candidates = []
    if env_path:
        candidates.append(Path(env_path))
    candidates.extend([
        cfg.PACKAGE_ROOT / ".env",
        cfg.PACKAGE_ROOT.parent / ".env",
        Path.cwd() / ".env",
    ])
    target: Path | None = None
    for p in candidates:
        if p.exists():
            target = p
            break
    if target is None:
        target = cfg.PACKAGE_ROOT.parent / ".env"
        # don't create if no env at all? we will create only if SEPOLIA_RPC_URL already present elsewhere
        if not target.exists():
            return

    try:
        lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    except Exception:
        lines = []

    updated = False
    new_lines: list[str] = []
    for line in lines:
        if line.startswith(f"{cfg.ENV_CONTRACT_ADDRESS}="):
            new_lines.append(f"{cfg.ENV_CONTRACT_ADDRESS}={contract_address}\n")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(f"{cfg.ENV_CONTRACT_ADDRESS}={contract_address}\n")

    try:
        target.write_text("".join(new_lines), encoding="utf-8")
        print(f"[+] Updated {cfg.ENV_CONTRACT_ADDRESS} in {target}")
    except Exception as exc:
        print(f"[!] Could not update .env at {target}: {exc}", file=sys.stderr)


def deploy(
    rpc_url: str | None = None,
    private_key: str | None = None,
    *,
    solc_version: str | None = None,
    write_env: bool = True,
    json_out: Path | None = None,
    expected_chain_id: int | None = None,
) -> Dict[str, Any]:
    """Compile and deploy to the RPC resolved from args/env.

    Args:
        rpc_url: explicit RPC; if None, resolves from SEPOLIA_RPC_URL / BLOCKCHAIN_RPC_URL / default local.
        private_key: explicit hex; if None, resolves from env.
        expected_chain_id: if set, asserts chain_id matches (e.g. 11155111 for Sepolia).
        write_env: if True, upserts SEPOLIA_CONTRACT_ADDRESS in .env.
        json_out: path for contract_data.json; defaults to config location.

    Returns:
        metadata dict (network, chain_id, contract_address, tx_hash, block_number, abi, ...)

    Raises:
        ConfigurationError / DeploymentError / ConnectionError
    """
    load_dotenv()

    # Lazy web3 import
    try:
        from web3 import Web3  # type: ignore
    except ImportError as exc:
        raise ConfigurationError("web3 not installed. Run: pip install -r blockchain_verify/requirements.txt") from exc

    # Resolve RPC + key with same priority as client.py but allow explicit override
    env_rpc = os.getenv(cfg.ENV_RPC_URL) or os.getenv(cfg.ENV_LOCAL_RPC)
    env_key = os.getenv(cfg.ENV_PRIVATE_KEY) or os.getenv(cfg.ENV_LOCAL_KEY)
    rpc = (rpc_url or env_rpc or cfg.DEFAULT_LOCAL_RPC).strip()
    key = (private_key or env_key or "").strip()
    if not key:
        raise ConfigurationError(f"No private key found. Set {cfg.ENV_PRIVATE_KEY} (or {cfg.ENV_LOCAL_KEY}) in .env or pass --private-key.")
    if not key.startswith("0x"):
        key = "0x" + key

    if not rpc:
        raise ConfigurationError(f"No RPC URL found. Set {cfg.ENV_RPC_URL} in .env or pass --rpc.")

    print(f"[*] Connecting to RPC: {rpc[:55]}...")
    w3 = Web3(Web3.HTTPProvider(rpc))  # type: ignore[arg-type]
    if not w3.is_connected():
        from .exceptions import ConnectionError as ConnErr
        raise ConnErr(f"Could not connect to RPC at '{rpc}'.")

    chain_id = w3.eth.chain_id  # type: ignore[attr-defined]
    network_name = "Ethereum Sepolia" if chain_id == cfg.SEPOLIA_CHAIN_ID else ("Local Chain" if chain_id in cfg.LOCAL_CHAIN_IDS else f"Chain {chain_id}")
    print(f"[+] Connected: {network_name} (chainId={chain_id})")

    if expected_chain_id is not None and chain_id != expected_chain_id:
        raise DeploymentError(f"Connected chainId {chain_id} != expected {expected_chain_id}.")

    # Check balance
    acct = w3.eth.account.from_key(key)  # type: ignore[attr-defined]
    addr = acct.address
    bal_wei = w3.eth.get_balance(addr)  # type: ignore[attr-defined]
    bal_eth = float(w3.from_wei(bal_wei, "ether"))  # type: ignore[attr-defined]
    print(f"[*] Deployer: {addr}  balance={bal_eth:.6f} ETH")
    if bal_wei == 0:
        # Local chains can be funded automatically; remote chains must error clearly
        if chain_id == cfg.SEPOLIA_CHAIN_ID:
            raise DeploymentError(
                f"Deployer {addr} has 0 Sepolia ETH. Fund via https://sepoliafaucet.com or https://www.alchemy.com/faucets/ethereum-sepolia"
            )
        print("[!] Warning: deployer has 0 ETH – local chain may fund accounts differently.", file=sys.stderr)

    abi, bytecode = compile_contract(solc_version=solc_version)
    Factory = w3.eth.contract(abi=abi, bytecode=bytecode)  # type: ignore[attr-defined]

    nonce = w3.eth.get_transaction_count(addr)  # type: ignore[attr-defined]

    # EIP-1559 vs legacy handling: try EIP-1559 for Sepolia, fallback for local
    try:
        latest = w3.eth.get_block("latest")  # type: ignore[attr-defined]
        base_fee = latest.get("baseFeePerGas")
        if base_fee is not None:
            try:
                pri = w3.eth.max_priority_fee  # type: ignore[attr-defined]
            except Exception:
                pri = w3.to_wei(cfg.DEFAULT_PRIORITY_FEE_GWEI, "gwei")  # type: ignore[attr-defined]
            max_fee = int(base_fee * cfg.BASE_FEE_MULTIPLIER) + int(pri)
            tx_params: Dict[str, Any] = {
                "from": addr,
                "nonce": nonce,
                "chainId": chain_id,
                "gas": cfg.GAS_LIMIT_DEPLOY,
                "maxFeePerGas": max_fee,
                "maxPriorityFeePerGas": int(pri),
            }
        else:
            raise ValueError("no baseFee – legacy")
    except Exception:
        tx_params = {
            "from": addr,
            "nonce": nonce,
            "chainId": chain_id,
            "gas": cfg.GAS_LIMIT_DEPLOY,
            "gasPrice": int(w3.eth.gas_price * 1.2),  # type: ignore[attr-defined]
        }

    print("[*] Building deployment transaction...")
    tx = Factory.constructor().build_transaction(tx_params)  # type: ignore[attr-defined]
    signed = w3.eth.account.sign_transaction(tx, key)  # type: ignore[attr-defined]
    raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
    print("[*] Broadcasting...")
    tx_hash = w3.eth.send_raw_transaction(raw)  # type: ignore[attr-defined]
    tx_hex = tx_hash.hex()
    print(f"[*] Tx hash: {tx_hex}  waiting for confirmation (up to {cfg.TX_TIMEOUT_SEC}s)...")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=cfg.TX_TIMEOUT_SEC)  # type: ignore[attr-defined]
    contract_address = getattr(receipt, "contractAddress", None) or receipt.get("contractAddress")  # type: ignore[union-attr]
    block_number = getattr(receipt, "blockNumber", receipt.get("blockNumber"))  # type: ignore[union-attr]
    gas_used = getattr(receipt, "gasUsed", receipt.get("gasUsed"))  # type: ignore[union-attr]
    status = getattr(receipt, "status", receipt.get("status", 1))  # type: ignore[union-attr]
    if status != 1:
        raise DeploymentError(f"Deployment tx reverted: {tx_hex}")

    etherscan_contract = f"https://sepolia.etherscan.io/address/{contract_address}" if chain_id == cfg.SEPOLIA_CHAIN_ID else "N/A (Local Chain)"
    etherscan_tx = f"https://sepolia.etherscan.io/tx/{tx_hex}" if chain_id == cfg.SEPOLIA_CHAIN_ID else "N/A (Local Chain)"

    print("\n" + "=" * 58)
    print("  DEPLOYMENT SUCCESSFUL")
    print("=" * 58)
    print(f"Network          : {network_name}")
    print(f"Chain ID         : {chain_id}")
    print(f"Contract Address : {contract_address}")
    print(f"Tx Hash          : {tx_hex}")
    print(f"Block            : {block_number}  Gas used: {gas_used}")
    print(f"Etherscan Addr   : {etherscan_contract}")
    print(f"Etherscan Tx     : {etherscan_tx}")
    print("=" * 58)

    # redact RPC key before persisting (avoid committing secrets)
    rpc_redacted = rpc
    if "/v2/" in rpc and len(rpc.split("/v2/")[-1]) > 8:
        rpc_redacted = rpc.split("/v2/")[0] + "/v2/***REDACTED***"
    meta: Dict[str, Any] = {
        "network": network_name,
        "chain_id": chain_id,
        "contract_address": contract_address,
        "tx_hash": tx_hex,
        "block_number": block_number,
        "gas_used": gas_used,
        "rpc_url": rpc_redacted,
        "deployer": addr,
        "etherscan_contract_url": etherscan_contract,
        "etherscan_tx_url": etherscan_tx,
        "solc_version": solc_version or cfg.SOLC_VERSION,
        "abi": abi,
    }

    out_path = Path(json_out) if json_out else (cfg.SEPOLIA_DATA_PATH if chain_id == cfg.SEPOLIA_CHAIN_ID else cfg.CONTRACT_DATA_PATH)
    # Prefer Sepolia file for Sepolia, local file for everything else
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[+] Wrote metadata to {out_path}")

    if write_env and chain_id == cfg.SEPOLIA_CHAIN_ID:
        _update_env_contract_address(contract_address)

    return meta


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Deploy VerificationRegistry to Sepolia or local chain.")
    p.add_argument("--rpc", dest="rpc_url", default=None, help="RPC URL (else SEPOLIA_RPC_URL / BLOCKCHAIN_RPC_URL)")
    p.add_argument("--private-key", dest="private_key", default=None, help="Deployer private key hex (else env)")
    p.add_argument("--local", action="store_true", help="Force local chain (no chainId assertion, no Etherscan links)")
    p.add_argument("--expect-sepolia", action="store_true", help="Assert chainId == 11155111")
    p.add_argument("--no-env-write", action="store_true", help="Do not update SEPOLIA_CONTRACT_ADDRESS in .env")
    p.add_argument("--out", dest="out", default=None, help="JSON output path (else auto)")
    p.add_argument("--solc-version", dest="solc_version", default=None, help=f"solc version (default {cfg.SOLC_VERSION})")
    return p


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    expected = cfg.SEPOLIA_CHAIN_ID if args.expect_sepolia else None
    # --local overrides expect check (local chains have varied ids)
    if args.local:
        expected = None
    try:
        deploy(
            rpc_url=args.rpc_url,
            private_key=args.private_key,
            solc_version=args.solc_version,
            write_env=not args.no_env_write,
            json_out=Path(args.out) if args.out else None,
            expected_chain_id=expected,
        )
    except Exception as exc:
        print(f"\n[-] DEPLOYMENT ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
