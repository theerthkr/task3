# blockchain_verify — isolated evidence anchoring module

Tamper-evident anchoring for any post (image / text / metadata) on Ethereum Sepolia (or a local chain). Deterministic SHA-256 fingerprinting + Solidity `VerificationRegistry` + Web3.py client. No UI coupling, no face-search imports.

**Principles**: Separation of concerns, Single Source of Truth (`config.py`), modularity. Hashing is pure-stdlib and freely editable.

```
blockchain_verify/
  config.py                 # SSOT: chain ids, gas, env names, allowed record keys
  hashing.py                # EDIT HERE – pure hashlib/json, zero chain deps
  contract/
    VerificationRegistry.sol
    contract_data.json          # auto-written cache (gitignored if you add to ignore)
  client.py                 # RPC + account (no ABI)
  registry.py               # store / verify / get (needs client)
  deploy.py                 # compile + deploy (CLI)
  __init__.py               # facade: `import blockchain_verify as bv`
```

---

## QUICK START — 5 minutes to on-chain proof

### 1. Install deps (one-time)

```bash
# from project root
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r blockchain_verify/requirements.txt
```

### 2. Get free Sepolia RPC + wallet + faucet

1. **RPC** — pick one free provider:
   - **Alchemy** (recommended): https://dashboard.alchemy.com → *Create App* → Network *Sepolia* → copy **HTTPS URL**
   - **Infura**: https://app.infura.io → *Create key* → *Sepolia endpoint*
   - **Public (rate-limited fallback)**: `https://ethereum-sepolia-rpc.publicnode.com`

2. **Wallet** — MetaMask → *Create account* → *Account details* → *Export Private Key* (or `cast wallet new`).

3. **Faucet** — fund the wallet (need ~0.05 SepoliaETH):
   - https://sepoliafaucet.com (Alchemy)
   - https://www.alchemy.com/faucets/ethereum-sepolia

4. **Env** — copy and fill:
   ```bash
   cp blockchain_verify/.env.example .env
   # edit .env:
   # SEPOLIA_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/XXXX
   # SEPOLIA_PRIVATE_KEY=0xabc...   (with or without 0x)
   ```

### 3. Compile + deploy (one-time, ~15s + 12s confirmation)

```bash
# Deploys VerificationRegistry.sol to Sepolia; writes address + ABI to
# blockchain_verify/contract/contract_sepolia_data.json and updates .env
python -m blockchain_verify.deploy --expect-sepolia

# Or for local Ganache/Hardhat (no faucet needed):
# python -m blockchain_verify.deploy --local
```

Verify on Etherscan: printed `https://sepolia.etherscan.io/address/0x...`

### 4. Use it (3 lines)

```python
import blockchain_verify as bv

# ---- hashing (no chain needed, fully editable in hashing.py) ----
fp = bv.hash_json({"title": "Found face at https://...", "source": "reddit", "source_url": "https://...", "face_distance": 0.12})
# or: fp = bv.hash_file("candidate.jpg")
# or: fp = bv.hash_text("post body text")
print(fp["bytes32_hex"])   # 0x...  – what goes on-chain

# ---- store on-chain ----
client = bv.connect()                     # reads SEPOLIA_RPC_URL / SEPOLIA_PRIVATE_KEY
reg = bv.Registry.attach(client)          # reads SEPOLIA_CONTRACT_ADDRESS / JSON
receipt = reg.store(fp["bytes32_hex"], "https://reddit.com/r/.../post")
print(receipt["etherscan_tx_url"])
print(receipt["etherscan_contract_url"])

# ---- re-verify (tamper detection) ----
assert reg.verify(fp["bytes32_hex"]) is True

# tamper: change one char -> new hash -> verify fails
tampered = bv.hash_json({"title": "Found face at https://...X", "source": "reddit", "source_url": "https://...", "face_distance": 0.12})
assert reg.verify(tampered["bytes32_hex"]) is False  # TAMPER DETECTED
```

### 5. Local offline demo (no Sepolia needed)

```bash
pip install "eth-tester[py-evm]"   # in-process EVM, no Ganache
python -m pytest blockchain_verify/tests -v  # if you add tests, or run manual:
python - << 'PY'
import blockchain_verify as bv
from eth_tester import EthereumTester
from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider

# spin ephemeral chain
w3 = Web3(EthereumTesterProvider(EthereumTester()))
acct = w3.eth.accounts[0]
# deploy via deploy.py passing w3's provider URL? For demo, use direct compile:
from blockchain_verify.deploy import compile_contract
abi, bin = compile_contract()
Factory = w3.eth.contract(abi=abi, bytecode=bin)
tx = Factory.constructor().transact({"from": acct})
rcpt = w3.eth.wait_for_transaction_receipt(tx)
addr = rcpt.contractAddress
from blockchain_verify.client import ConnectedClient, ChainInfo
client = ConnectedClient(w3=w3, chain=ChainInfo(chain_id=w3.eth.chain_id, network_name="Local", rpc_url="eth-tester"), account=None, account_address=acct)
reg = bv.Registry.attach(client, contract_address=addr)
fp = bv.hash_text("hello world")
print(reg.store(fp["bytes32_hex"], "https://example.com"))
print("verify:", reg.verify(fp["bytes32_hex"]))
PY
```

---

## API surface (import from `blockchain_verify`)

### Hashing (`hashing.py`) — zero chain deps, edit freely

| Function | Input | Output `fingerprint` dict |
|---|---|---|
| `hash_bytes(data: bytes)` | raw bytes | `{hex_hash, bytes32_hex, bytes32_raw}` |
| `hash_text(text)` | str | same |
| `hash_file(path)` | `Path` | same + `file_path`, `file_size` |
| `hash_json(obj: dict)` | any dict (canonical JSON) | same + `canonical_json` |
| `create_fingerprint(record: dict)` | whitelist dict (HH Goa schema) | same + `canonical_json` |
| `canonicalize_record(record, allowed_keys=...)` | dict | canonical JSON str |
| `sha256_hex(data: bytes)` | bytes | `str` 64-hex |
| `sha256_bytes32(data: bytes)` | bytes | `str` 0x-prefixed |

Edit `ALLOWED_RECORD_KEYS` at top of `hashing.py` (or pass `allowed_keys=` to `canonicalize_record`) to change which fields affect the hash. `hash_json` is generic; `create_fingerprint` enforces the face-match allowlist (`face_distance`, `face_match`, `image_url`, `source`, `source_url`, `title`).

### Chain (`client.py` + `registry.py`)

```python
from blockchain_verify import connect, Registry

client = connect(rpc_url=None, private_key=None)  # None -> env -> defaults
reg = Registry.attach(client, contract_address=None, abi=None)  # None -> env/JSON
# or one-liner:
reg = Registry.attach_from_env()

reg.store(bytes32_hex, source_url) -> receipt dict {transaction_hash, block_number, gas_used, etherscan_tx_url, ...}
reg.verify(bytes32_hex) -> bool
reg.get(bytes32_hex) -> {data_hash, source_url, timestamp}
# functional sugar (auto-connect):
from blockchain_verify import store_record, verify_record, get_record
store_record(bytes32_hex, source_url)
verify_record(bytes32_hex)
```

`receipt["etherscan_tx_url"]` and `receipt["etherscan_contract_url"]` are Sepolia Etherscan links when on chain 11155111, else `"N/A (Local Chain)"`.

### Deploy (`deploy.py`)

```bash
python -m blockchain_verify.deploy --help
python -m blockchain_verify.deploy --expect-sepolia       # assert chain 11155111
python -m blockchain_verify.deploy --local                # any local chain
python -m blockchain_verify.deploy --rpc URL --private-key 0x... --no-env-write --out /tmp/meta.json
```

---

## Separation of concerns map

| File | Owns | Imports |
|---|---|---|
| `config.py` | All constants, env names, paths | nothing project-specific |
| `hashing.py` | Canonicalisation + SHA-256 | `config` only for default keys |
| `contract/VerificationRegistry.sol` | On-chain storage schema | — |
| `client.py` | RPC dial + account resolution + chain detection | `config`, `web3`, `dotenv` |
| `registry.py` | `store/verify/get` + ABI loading + gas strategy | `client`, `config` |
| `deploy.py` | `solc` compile + deploy tx + env/JSON write | `config`, `web3`, `solcx` |
| `__init__.py` | Re-exports public API | above |

Zero imports from `face_search` or `HHGOA-FACE-BLOCKCHAIN`. Other programs use this module by depending only on `blockchain_verify`.

---

## Integration with big app (for judges)

`face_search/blockchain_anchor.py:1` is the only bridge. `face_search/pipeline.py:88` calls `anchor_report(report, top_k)` when `--anchor` is passed, `face_search/cli.py:24` exposes `--anchor` + `--verify-anchor`.

**Judge modes (see `JUDGE_GUIDE.md`):**

* `python -m face_search.cli --image chandu.png --live --anchor` -> needs `SERPAPI_KEY` + `SEPOLIA_RPC_URL` + `SEPOLIA_PRIVATE_KEY` + `SEPOLIA_CONTRACT_ADDRESS=0x21bD1360C5bc74713EbFf45e83411A63Cde2D03d` (already deployed, `contract/contract_sepolia_data.json:4`). Stores `bytes32` -> receipt `etherscan_tx_url` in `runs/<ts>/report.json: blockchain` and re-verifies `verify==True`.
* `python -m face_search.cli --image chandu.png --verify-anchor runs/<ts>/report.json` -> needs only `SEPOLIA_RPC_URL` + `SEPOLIA_CONTRACT_ADDRESS` (read-only, no private key), prints `VERIFIED`/`TAMPER`.
* With 0 SepoliaETH, `--anchor` still computes `bytes32_hex`/`canonical_json` but returns `insufficient funds` per item (hash-only, correct). Fund via https://sepoliafaucet.com then rerun. Local no-faucet: `python -m blockchain_verify.demo_local`.

Pre-deployed contract Etherscan: `https://sepolia.etherscan.io/address/0x21bD1360C5bc74713EbFf45e83411A63Cde2D03d` (tx `0x747a401507e8652a20e781117e3181141a5becf3a6396e8b35b4c6fe0dde04bc` block `11640957`).

---

## Troubleshooting

- `web3 is not installed` → `pip install -r blockchain_verify/requirements.txt`
- `Could not connect to RPC` → check `SEPOLIA_RPC_URL` (Alchemy URL must include `/v2/YOUR_KEY`, not truncated).
- `has 0 Sepolia ETH` → fund wallet via faucet, wait ~30s, retry.
- `solc` compile fails → `pip install py-solc-x` and ensure internet for `install_solc`.
- Local `eth-tester` demo needs `pip install "eth-tester[py-evm]"`.

---

## What the chain proves (and does not)

On-chain `verifyRecord(0xabc...) -> true` proves that *someone who held the deployer key* registered *that exact 32-byte fingerprint* at *that block timestamp*, and that the bytes have not been altered since. It does not prove web content truthfulness or real-world identity — same scope note as HH Goa's README.
