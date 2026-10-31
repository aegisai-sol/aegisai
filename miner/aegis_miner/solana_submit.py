"""Optional real Solana submit: one SPL Memo tx per vote digest (devnet default).
Enabled only when AEGIS_SOLANA_SUBMIT=1 and a keypair file exists. Requires: pip install solders"""
import base64, json, os, urllib.request

MEMO_PROGRAM_ID = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"  # SPL Memo v2 (official)
RPCS = {"devnet": "https://api.devnet.solana.com", "mainnet-beta": "https://api.mainnet-beta.solana.com"}

def _rpc(url, method, params):
    req = urllib.request.Request(url, json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                                 {"Content-Type": "application/json"})
    out = json.load(urllib.request.urlopen(req, timeout=20))
    if "error" in out: raise RuntimeError(out["error"])
    return out["result"]

class SolanaSubmitter:
    def __init__(self):
        from solders.keypair import Keypair
        if os.environ.get("MAINNET") == "1":
            raise RuntimeError("mainnet anchoring disabled in PoV-R phase 1 (devnet only)")
        self.cluster = "devnet"
        self.url = os.environ.get("SOLANA_RPC", RPCS["devnet"])
        if "mainnet" in self.url: raise RuntimeError("mainnet RPC refused")
        path = os.environ.get("SOLANA_KEYPAIR", "../aegisai-token/.keys/devnet.json")
        if not os.path.exists(path): raise FileNotFoundError(f"keypair not found: {path}")
        self.kp = Keypair.from_bytes(bytes(json.load(open(path))))

    def build(self, memo, blockhash):
        from solders.pubkey import Pubkey
        from solders.hash import Hash
        from solders.instruction import Instruction, AccountMeta
        from solders.message import Message
        from solders.transaction import Transaction
        ix = Instruction(Pubkey.from_string(MEMO_PROGRAM_ID), memo.encode(),
                         [AccountMeta(self.kp.pubkey(), True, False)])
        return Transaction([self.kp], Message([ix], self.kp.pubkey()), Hash.from_string(blockhash))

    def submit(self, memo):
        if len(memo.encode()) > 566: raise ValueError("memo too long")
        if os.environ.get("AEGIS_ANCHOR_DRYRUN") == "1":  # build+sign, never send
            tx = self.build(memo, "11111111111111111111111111111111")
            return "DRYRUN:" + str(tx.signatures[0])
        bh = _rpc(self.url, "getLatestBlockhash", [{"commitment": "confirmed"}])["value"]["blockhash"]
        tx = self.build(memo, bh)
        return _rpc(self.url, "sendTransaction", [base64.b64encode(bytes(tx)).decode(), {"encoding": "base64"}])
