"""Devnet memo anchoring tests. RPC is mocked; keypair is an EPHEMERAL TEST-ONLY key in tmp (never committed)."""
import json, base64, pytest
from solders.keypair import Keypair
from solders.transaction import Transaction
from aegis_miner import solana_submit as S

@pytest.fixture
def kp(tmp_path, monkeypatch):
    k = Keypair(); f = tmp_path / "test-only-devnet.json"; f.write_text(json.dumps(list(bytes(k))))
    monkeypatch.setenv("SOLANA_KEYPAIR", str(f)); monkeypatch.delenv("MAINNET", raising=False)
    monkeypatch.delenv("SOLANA_RPC", raising=False); return k

def test_mocked_rpc_sends_signed_memo(kp, monkeypatch):
    calls = []
    def fake(url, method, params):
        calls.append((url, method, params))
        if method == "getLatestBlockhash": return {"value": {"blockhash": "11111111111111111111111111111111"}}
        tx = Transaction.from_bytes(base64.b64decode(params[0])); assert tx.verify() is None
        assert bytes(tx.message.instructions[0].data) == b"AGIS|PoV-R|r1|abc"
        assert str(tx.message.account_keys[-1]) == S.MEMO_PROGRAM_ID
        return str(tx.signatures[0])
    monkeypatch.setattr(S, "_rpc", fake)
    sig = S.SolanaSubmitter().submit("AGIS|PoV-R|r1|abc")
    assert calls[0][0] == S.RPCS["devnet"] and calls[1][1] == "sendTransaction" and len(sig) > 80

def test_dryrun_never_touches_rpc(kp, monkeypatch):
    monkeypatch.setenv("AEGIS_ANCHOR_DRYRUN", "1")
    monkeypatch.setattr(S, "_rpc", lambda *a: pytest.fail("RPC called in dry-run"))
    assert S.SolanaSubmitter().submit("AGIS|x").startswith("DRYRUN:")

def test_mainnet_refused(kp, monkeypatch):
    monkeypatch.setenv("MAINNET", "1")
    with pytest.raises(RuntimeError): S.SolanaSubmitter()
    monkeypatch.delenv("MAINNET"); monkeypatch.setenv("SOLANA_RPC", "https://api.mainnet-beta.solana.com")
    with pytest.raises(RuntimeError): S.SolanaSubmitter()

def test_missing_keypair(monkeypatch, tmp_path):
    monkeypatch.setenv("SOLANA_KEYPAIR", str(tmp_path / "nope.json"))
    with pytest.raises(FileNotFoundError): S.SolanaSubmitter()

def test_memo_size_limit(kp, monkeypatch):
    monkeypatch.setenv("AEGIS_ANCHOR_DRYRUN", "1")
    with pytest.raises(ValueError): S.SolanaSubmitter().submit("x" * 600)
