# Judge Guide – What to put in .env to make blockchain verification work

This is the **big app** integration: face search + deterministic hash + Sepolia anchor. All code is modular, no secrets committed.

## 1. What judges need for each mode

| Mode | Command | Needs `.env` | What it proves |
|------|---------|--------------|----------------|
| **Dry run** (no cost) | `python -m face_search.cli --image chandu.png` | *nothing* | Face detection only, no blockchain |
| **Live search** (no blockchain) | `python -m face_search.cli --image chandu.png --live` | `SERPAPI_KEY=` | Real Google Lens + ranking, `report.json` |
| **Live + anchor (write)** | `python -m face_search.cli --image chandu.png --live --anchor` | `SERPAPI_KEY` + `SEPOLIA_RPC_URL` + `SEPOLIA_PRIVATE_KEY` + `SEPOLIA_CONTRACT_ADDRESS` | Hash verified match -> store `bytes32` on Sepolia, receipt + Etherscan link in `report.json: blockchain` |
| **Verify existing report (read-only)** | `python -m face_search.cli --image chandu.png --verify-anchor runs/<ts>/report.json` | `SEPOLIA_RPC_URL` + `SEPOLIA_CONTRACT_ADDRESS` (no private key) | `verifyRecord(bytes32) -> True/False` vs on-chain state, tamper detection |

## 2. Get the 3 blockchain values (free, 5 min)

**Contract is already deployed for you** at `0x21bD1360C5bc74713EbFf45e83411A63Cde2D03d` (Sepolia, `blockchain_verify/contract/contract_sepolia_data.json:4`). You do **not** need to redeploy unless you want your own.

a) **RPC URL** – free Sepolia endpoint:
- Alchemy (recommended): https://dashboard.alchemy.com -> Create App -> Network `Sepolia` -> copy `HTTPS URL` (`https://eth-sepolia.g.alchemy.com/v2/<KEY>`)
- Infura: https://app.infura.io -> Create key -> Sepolia
- Public fallback (rate-limited): `https://ethereum-sepolia-rpc.publicnode.com`

b) **Private key** – *only needed for `--anchor` write*:
- MetaMask -> Account details -> Export Private Key (or `cast wallet new`)
- **Never commit** – keeps in `.env` only. With 0 SepoliaETH, `--anchor` will still compute hash but store will fail `insufficient funds` (hash-only mode, correct behavior).

c) **Contract address** – already set:
```
SEPOLIA_CONTRACT_ADDRESS=0x21bD1360C5bc74713EbFf45e83411A63Cde2D03d
```
If you deploy your own: `python -m blockchain_verify.deploy --expect-sepolia` (needs ~0.05 SepoliaETH from https://sepoliafaucet.com or https://www.alchemy.com/faucets/ethereum-sepolia). It auto-writes `contract_sepolia_data.json` + updates `.env`.

## 3. Setup

```bash
cp .env.example .env
# edit .env:
SERPAPI_KEY=...
SEPOLIA_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/...
# for --anchor write:
SEPOLIA_PRIVATE_KEY=0xabc...  # with or without 0x
SEPOLIA_CONTRACT_ADDRESS=0x21bD1360C5bc74713EbFf45e83411A63Cde2D03d
SEPOLIA_CHAIN_ID=11155111

pip install -r blockchain_verify/requirements.txt
pip install -r requirements.txt
```

`.env` is `gitignored` (`.gitignore:2`), `deploy.py:280` redacts `/v2/<KEY>` -> `/v2/***REDACTED***` in JSON.

## 4. Run the hackathon flow

```bash
# 1. Find matching post (live search, no limit)
python -m face_search.cli --image chandu.png --live --anchor
# -> Mode: LIVE ... Verified: 1 ... Blockchain: enabled=True contract=0x21bD... network=Ethereum Sepolia
#    anchored 0x275b4036... -> tx 0xabc... block 11655 verify=True | https://sepolia.etherscan.io/tx/0xabc...

# 2. Verify later (or on another machine, no private key needed)
python -m face_search.cli --image chandu.png --verify-anchor runs/20260907T171142Z/report.json
# -> Verify runs/.../report.json
#    Contract 0x21bD... (Ethereum Sepolia) -> https://sepolia.etherscan.io/address/0x21bD...
#      0x275b4036... https://bebee.com/... -> verify=True VERIFIED
#      on-chain source_url=https://bebee.com/... ts=...

# 3. Tamper detection (change one char in report.json's canonical_json and re-verify -> False)
```

If you have 0 SepoliaETH, step 1 still prints `hash 0x275b... | error: insufficient funds` - hash is deterministic and ready to store once funded. Fund via faucet then rerun `--anchor` or use local demo:

```bash
pip install "eth-tester[py-evm]"  # no faucet needed
python -m blockchain_verify.demo_local  # deploys ephemeral chain, stores, verifies, tamper -> False
python -m blockchain_verify.demo_offline # no chain, hash + tamper only
```

## 5. What judges actually need to put

- **To just verify your submitted proof:** `SEPOLIA_RPC_URL` (any Sepolia RPC, even `https://ethereum-sepolia-rpc.publicnode.com`) + `SEPOLIA_CONTRACT_ADDRESS` (committed in `contract_sepolia_data.json`). No private key, no SERPAPI_KEY.
- **To reproduce live search + anchor:** add `SERPAPI_KEY` (your SerpApi account, free 100 searches) + `SEPOLIA_PRIVATE_KEY` (their own wallet, funded via faucet). Never paste your private key in chat/code.

See `blockchain_verify/README.md` for 3-line Python API (`hash_json`/`Registry.attach`/`store`/`verify`) and `face_search/blockchain_anchor.py:1` for integration SOC.
