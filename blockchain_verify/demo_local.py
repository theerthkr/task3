"""Local simulated-chain demo – no Sepolia needed, no faucet.

Uses eth-tester + py-evm for an in-process EVM. Requires:
  pip install \"eth-tester[py-evm]\"

Run:
  python -m blockchain_verify.demo_local

Fall back:
  If py-evm missing, prints instructions for Ganache / Sepolia flow.
"""

import sys


def main() -> None:
    print("=" * 62)
    print(" blockchain_verify – LOCAL CHAIN DEMO (eth-tester)")
    print("=" * 62)

    try:
        from eth_tester import EthereumTester, PyEVMBackend
        from web3 import Web3
        from web3.providers.eth_tester import EthereumTesterProvider
    except ImportError as exc:
        print("\n[!] eth-tester[py-evm] not installed.")
        print("    Install: pip install \"eth-tester[py-evm]\"")
        print("    Or run Ganache and use:")
        print("      python -m blockchain_verify.deploy --local")
        print(f"\n    Detail: {exc}")
        sys.exit(0)

    sys.path.insert(0, ".")
    import blockchain_verify as bv
    from blockchain_verify.client import ChainInfo, ConnectedClient
    from blockchain_verify.deploy import compile_contract

    # Spin ephemeral chain
    tester = EthereumTester(PyEVMBackend())
    w3 = Web3(EthereumTesterProvider(tester))
    acct = w3.eth.accounts[0]
    print(f"\n[*] Ephemeral chain – chainId={w3.eth.chain_id}  deployer={acct}")

    # Compile & deploy
    abi, bytecode = compile_contract()
    Factory = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx_hash = Factory.constructor().transact({"from": acct})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    addr = receipt.contractAddress
    print(f"[+] Deployed VerificationRegistry at {addr} (block {receipt.blockNumber})")

    # Wrap client + registry (bypass RPC dial – inject in-memory w3)
    client = ConnectedClient(
        w3=w3,
        chain=ChainInfo(chain_id=w3.eth.chain_id, network_name="Local (eth-tester)", rpc_url="eth-tester"),
        account=None,
        account_address=acct,
    )
    reg = bv.Registry.attach(client, contract_address=addr, abi=abi)
    print(f"[+] Registry attached at {reg.address}")

    # Hash a post (image / text / metadata agnostic)
    post = {
        "title": "Match found on Reddit r/programming",
        "source": "Reddit",
        "source_url": "https://www.reddit.com/r/programming/comments/dobz8s/lenajpg_now/",
        "image_url": "https://example.com/candidate.jpg",
        "face_match": True,
        "face_distance": 0.0202,
    }
    fp = bv.create_fingerprint(post)
    print("\n[*] Fingerprint")
    print("    canonical_json:", fp["canonical_json"])
    print("    bytes32_hex   :", fp["bytes32_hex"])

    # Store on-chain
    print("\n[*] Storing fingerprint on-chain...")
    r1 = reg.store(fp["bytes32_hex"], post["source_url"])
    print(f"    tx hash : {r1['transaction_hash']}")
    print(f"    block   : {r1['block_number']}  gas {r1['gas_used']}")
    print(f"    etherscan: {r1['etherscan_tx_url']}  (N/A on local)")

    # Verify
    print("\n[*] Verifying on-chain...")
    print("    verify(original) ->", reg.verify(fp["bytes32_hex"]), "✓ VERIFIED" if reg.verify(fp["bytes32_hex"]) else "✗")
    rec = reg.get(fp["bytes32_hex"])
    print(f"    getRecord -> source_url={rec['source_url']} timestamp={rec['timestamp']}")

    # Tamper: flip one field -> new hash -> verify fails
    tampered = dict(post)
    tampered["face_distance"] = 0.5
    fp_tamp = bv.create_fingerprint(tampered)
    print("\n[*] Tamper check (face_distance 0.0202 -> 0.5)")
    print("    tampered bytes32_hex:", fp_tamp["bytes32_hex"])
    print("    verify(tampered) ->", reg.verify(fp_tamp["bytes32_hex"]), "(expected False – TAMPER DETECTED)")

    # Also demo generic primitives on-chain
    fp2 = bv.hash_text("post body text example")
    r2 = reg.store(fp2["bytes32_hex"], "https://example.com/post/2")
    print("\n[*] Stored text hash", fp2["bytes32_hex"], "in tx", r2["transaction_hash"])
    print("    verify(text) ->", reg.verify(fp2["bytes32_hex"]))

    print("\n" + "=" * 62)
    print(" LOCAL DEMO PASSED – store + re-verify + tamper detection ✓")
    print(" For Sepolia (public proof), run:")
    print("   1. Fill SEPOLIA_RPC_URL + SEPOLIA_PRIVATE_KEY in .env")
    print("   2. python -m blockchain_verify.deploy --expect-sepolia")
    print("   3. python -c \"import blockchain_verify as bv; fp=bv.hash_text('hello'); print(bv.Registry.attach(bv.connect()).store(fp['bytes32_hex'], 'https://...'))\"")
    print("=" * 62)


if __name__ == "__main__":
    main()
