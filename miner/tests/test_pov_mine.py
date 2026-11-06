"""Desktop PoV mine path: claim message + local solve/grade (no keys)."""
import json
from urllib.error import URLError
from urllib.request import Request

import pytest

from aegis_miner import pov_mine as m
from aegis_miner import pov_tasks as p

S = b"test-secret"
W = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
T0 = 1_800_000_000
N = "0123456789abcdef"


def test_build_claim_msg_shape():
    msg = m.build_claim_msg(
        wallet=W,
        batch_id="1800000000.0123456789abcdef.5.deadbeefdeadbeefdeadbeefdeadbeef",
        answers_hex="18",
        from_iso="2026-11-06T22:00:00.000Z",
        to_iso="2026-11-06T22:00:05.000Z",
        claim_uuid="11111111-1111-1111-1111-111111111111",
        tier="laptop",
        cores=4,
        bench_ms=42,
    )
    parts = msg.split("|")
    assert parts[0] == m.CLAIM_DOMAIN
    assert parts[1] == W and parts[3] == "18" and parts[7] == "laptop"
    assert parts[8] == "4" and parts[9] == "42"
    with pytest.raises(ValueError):
        m.build_claim_msg(
            wallet="bad|wallet",
            batch_id="x",
            answers_hex="00",
            from_iso="a",
            to_iso="b",
            claim_uuid="c",
            tier="t",
            cores=1,
            bench_ms=1,
        )


def test_work_window_uses_server_clock():
    w = m.work_window("2026-11-06T22:00:00.000Z", 2500)
    assert w["from"] == "2026-11-06T22:00:00.000Z"
    assert w["to"] == "2026-11-06T22:00:02.500Z"
    w2 = m.work_window("2026-11-06T22:00:00.000Z", 100)
    assert w2["to"] == "2026-11-06T22:00:01.000Z"  # floor 1000ms


def test_local_demo_passes_grade():
    out = m.local_demo(S, W, n=5, iat_sec=T0, nonce_hex=N)
    assert out["local"] is True
    assert out["grade"]["pass"] is True and out["grade"]["correct"] == 5
    assert out["answersHex"] == "18"
    assert out["msg"].startswith(m.CLAIM_DOMAIN + "|" + W + "|")
    assert out["postBody"]["sig"] is None


def test_solve_batch_matches_truth():
    issued = p.issue_batch(S, W, 30, T0, N)
    answers, hx, ms = m.solve_batch(issued["tasks"])
    assert ms >= 0
    g = p.grade_answers(S, issued["batchId"], hx)
    assert g["correct"] == 30 and g["pass"] is True
    assert answers == [p.solve_task(t) for t in issued["tasks"]]


def test_fetch_batch_validates_wallet(monkeypatch):
    with pytest.raises(ValueError, match="wallet"):
        m.fetch_batch(m.DEFAULT_CLAIM_BASE, "")
    with pytest.raises(ValueError, match="task count"):
        m.fetch_batch(m.DEFAULT_CLAIM_BASE, W, n=0)

    class FakeResp:
        status = 200
        def read(self):
            return json.dumps({
                "ok": True,
                "domain": m.CLAIM_DOMAIN,
                "batchId": "1.2.3.4",
                "tasks": ["prime(2)"],
                "issuedAt": "2026-11-06T22:00:00.000Z",
            }).encode()
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(m.urllib.request, "urlopen", lambda *a, **k: FakeResp())
    j = m.fetch_batch("https://example.test", W, n=1)
    assert j["tasks"] == ["prime(2)"]


def test_run_once_wires_prepare(monkeypatch):
    batch = {
        "ok": True,
        "domain": m.CLAIM_DOMAIN,
        "batchId": "1800000000.0123456789abcdef.3.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "tasks": ["2*3=6", "prime(4)", "sha256(agis:ab)^00"],
        "issuedAt": "2026-11-06T22:00:00.000Z",
    }
    # Force known tasks via solve that won't match HMAC grade — only wiring matters here.
    monkeypatch.setattr(m, "fetch_batch", lambda *a, **k: batch)
    # Use tasks the solver understands
    batch["tasks"] = ["2*3=6", "prime(4)", "2*2=5"]
    out = m.run_once(W, n=3)
    assert out["n"] == 3 and out["answers"] == [True, False, False]
    assert out["msg"].startswith(m.CLAIM_DOMAIN)
    assert "Sign msg" in out["note"]
