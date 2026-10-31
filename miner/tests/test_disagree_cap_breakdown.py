import json, pytest
from aegis_miner import consensus as c
from aegis_miner.consensus import PeerHealth, _env_cap

def test_cap_ctor_and_validation():
    h = PeerHealth(disagree_cap=1)
    for _ in range(5): h.observe_vote("a", False)
    assert h.disagree_factor("a") == 0.5
    h0 = PeerHealth(disagree_cap=0); h0.observe_vote("a", False); assert h0.weight("a") == 1.0
    for bad in (-1, True, 1.5, "4"):
        with pytest.raises(ValueError): PeerHealth(disagree_cap=bad)
    assert PeerHealth().disagree_cap == 4

def test_env_cap():
    assert _env_cap("X", 4, {}) == 4
    assert _env_cap("X", 4, {"X": "2"}) == 2
    assert _env_cap("X", 4, {"X": "0"}) == 0
    assert _env_cap("X", 4, {"X": "-3"}) == 4
    assert _env_cap("X", 4, {"X": "abc"}) == 4
    assert _env_cap("X", 4, {"X": "99"}) == 16

def test_breakdown_product():
    t = [0.0]; h = PeerHealth(half_life=10, clock=lambda: t[0])
    for _ in range(10): h.observe("a", True)
    h.observe_vote("a", False); t[0] = 10
    b = h.breakdown("a")
    assert (b["bonus"], b["fade"], b["dissent"]) == (1.0, 0.5, 0.5)
    assert b["weight"] == pytest.approx((1 + 1.0 * 0.5) * 0.5) == h.weight("a")
    assert h.breakdown("unknown")["weight"] == 1.0
    for _ in range(3): h.observe("a", False)
    assert h.breakdown("a")["weight"] == 0.0 and h.breakdown("a")["alive"] is False

def test_attach_ids_only():
    h = PeerHealth(); eps = ["https://secret.example/x"]
    res = c.attach_breakdowns(h, eps, [{"id": "peer0", "ok": True}])
    assert res[0]["weight"]["weight"] == 1.0
    assert "secret" not in json.dumps(res) and "secret" not in json.dumps(h.breakdowns(eps))
    assert list(h.breakdowns(eps)) == ["peer0"]
