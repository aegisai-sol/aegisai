import pytest
from aegis_miner import consensus as c

def test_env_flag():
    for v in ("1","true","YES"," on "): assert c.weighted_quorum_enabled({"AEGIS_WEIGHTED_QUORUM": v})
    for v in ("","0","false","no","x"): assert not c.weighted_quorum_enabled({"AEGIS_WEIGHTED_QUORUM": v})
    assert not c.weighted_quorum_enabled({})

def test_resolve_override():
    assert c.resolve_weighted(None, {"AEGIS_WEIGHTED_QUORUM": "1"}) is True
    assert c.resolve_weighted(False, {"AEGIS_WEIGHTED_QUORUM": "1"}) is False
    assert c.resolve_weighted(True, {}) is True
    for bad in (1, "true", 0.5, []):
        with pytest.raises(ValueError): c.resolve_weighted(bad, {})

def test_idle_fade():
    t = [0.0]; h = c.PeerHealth(half_life=100, clock=lambda: t[0])
    for _ in range(10): h.observe("a", True)
    assert h.weight("a") == 2.0
    t[0] = 100; assert h.weight("a") == pytest.approx(1.5)
    t[0] = 200; assert h.weight("a") == pytest.approx(1.25)
    h.observe("a", True); assert h.weight("a") == 2.0
    t[0] = 1e9; assert 1.0 <= h.weight("a") < 1.0001

def test_fade_off_default_and_validation():
    t = [0.0]; h = c.PeerHealth(clock=lambda: t[0])
    for _ in range(5): h.observe("a", True)
    t[0] = 1e6; assert h.weight("a") == 1.5
    for bad in (-1, float("nan"), float("inf")):
        with pytest.raises(ValueError): c.PeerHealth(half_life=bad)
    assert h.summary(["a"])["weight_half_life"] == 0.0

def test_env_resolves_from_os(monkeypatch):
    monkeypatch.setenv("AEGIS_WEIGHTED_QUORUM", "true"); assert c.resolve_weighted(None) is True
    monkeypatch.delenv("AEGIS_WEIGHTED_QUORUM"); assert c.resolve_weighted(None) is False
