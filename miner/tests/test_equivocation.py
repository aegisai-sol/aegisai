import json
from aegis_miner import card_attest as ca, offline_verify as ov

A, B, X = "11" * 32, "22" * 32, "44" * 32
PA, PB, PX = (ca.pubkey_from_seed(s) for s in (A, B, X))

def _fork():
    honest = ca.make_bundle(A, 7, 100, 900, [], [ca.make_revocation(B, "compromised", 0)])
    hiding = ca.make_bundle(A, 7, 100, 900, [], [])  # same seq, revocation withheld from this audience
    return honest, hiding

def test_same_seq_fork_proven():
    r = ca.check_equivocation(ca.make_equivocation(*_fork()), [PA])
    assert r["ok"] and r["kind"] == "same-seq fork" and r["signer"] == PA and r["seq"] == 7

def test_identical_bundle_is_refetch_not_fraud():
    b, _ = _fork()
    r = ca.check_equivocation(ca.make_equivocation(b, b), [PA])
    assert not r["ok"] and r["reason"] == "same bundle (re-fetch)"
    reordered = dict(b, revocations=list(reversed(b["revocations"])))
    assert not ca.check_equivocation(ca.make_equivocation(b, reordered), [PA])["ok"]

def test_non_monotonic_seq_proven_and_consistent_history_not():
    a = ca.make_bundle(A, 5, 300, 900); b = ca.make_bundle(A, 6, 200, 900)
    r = ca.check_equivocation(ca.make_equivocation(a, b), [PA])
    assert r["ok"] and r["kind"] == "non-monotonic seq" and r["seq"] == 5
    good = ca.make_bundle(A, 6, 400, 900)
    assert ca.check_equivocation(ca.make_equivocation(a, good), [PA])["reason"] == "consistent history"

def test_forged_or_untrusted_bundle_cannot_frame_signer():
    honest, hiding = _fork()
    tampered = dict(hiding, revocations=[ca.make_revocation(X, "retired", 5)])
    assert not ca.check_equivocation(ca.make_equivocation(honest, tampered), [PA])["ok"]
    stranger = ca.make_bundle(X, 7, 100, 900)
    assert not ca.check_equivocation(ca.make_equivocation(honest, stranger), [PA])["ok"]
    assert not ca.check_equivocation(ca.make_equivocation(ca.make_bundle(X, 1, 1, 9), ca.make_bundle(X, 1, 1, 8)), [PA])["ok"]

def test_different_signers_not_equivocation():
    a = ca.make_bundle(A, 3, 150, 900, [ca.make_rotation(A, B, 100)])  # A rotated out at 100 -> invalid at 150
    assert not ca.check_equivocation(ca.make_equivocation(a, ca.make_bundle(A, 3, 50, 900)), [PA])["ok"]
    rot = ca.make_rotation(A, B, 100)
    x = ca.make_bundle(A, 3, 50, 900, [rot]); y = ca.make_bundle(B, 3, 150, 900, [rot])
    assert ca.check_equivocation(ca.make_equivocation(x, y), [PA])["reason"] == "different signers"

def test_expired_bundles_still_count_as_evidence():
    honest, hiding = _fork()
    assert ca.check_bundle(honest, [PA], now=10_000)["reason"] == "bundle expired"
    assert ca.check_equivocation(ca.make_equivocation(honest, hiding), [PA])["ok"]

def test_check_bundle_rejects_equivocating_signer():
    honest, hiding = _fork()
    proof = ca.make_equivocation(honest, hiding)
    assert ca.check_bundle(hiding, [PA], now=150)["ok"]
    r = ca.check_bundle(hiding, [PA], now=150, equivocations=[proof])
    assert not r["ok"] and r["reason"] == "bundle signer equivocated"
    assert ca.check_bundle(honest, [PA], equivocations=[{"junk": 1}, None, "x"])["ok"]

def test_malformed_never_raises():
    for bad in (None, 1, "x", [], {}, {"scheme": ca.EQUIVOCATION_SCHEME}, {"scheme": ca.EQUIVOCATION_SCHEME, "a": 1, "b": []}):
        assert ca.check_equivocation(bad, [PA])["ok"] is False
    assert ca.check_equivocation(ca.make_equivocation(*_fork()), None)["ok"] is False

def test_offline_cli_equivocation_flag(tmp_path, capsys):
    honest, hiding = _fork()
    (tmp_path / "b.json").write_text(json.dumps(hiding))
    (tmp_path / "e.json").write_text(json.dumps(ca.make_equivocation(honest, hiding)))
    (tmp_path / "d.json").write_text("{}")
    rc = ov.main([str(tmp_path / "d.json"), "--pubkey", PA, "--bundle", str(tmp_path / "b.json"),
                  "--equivocation", str(tmp_path / "e.json")])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and "equivocated" in out["reason"]
