import pytest
from aegis_miner.consensus import PeerHealth

def test_window_fades_old_votes():
    h = PeerHealth(agreement_window=4)
    for a in [False]*4 + [True]*4: h.observe_vote("e", a)
    r = h.agreement_rates(["e"])["peer0"]
    assert r["rate"] == 0.5 and r["window_rate"] == 1.0 and r["window_votes"] == 4 and r["window"] == 4

def test_no_votes_none():
    r = PeerHealth().agreement_rates(["e"])["peer0"]
    assert r["window_rate"] is None and r["factor"] == 1.0

def test_penalty_off_by_default():
    h = PeerHealth(disagree_cap=0)
    for _ in range(10): h.observe_vote("e", False)
    assert h.agreement_factor("e") == 1.0 and h.weight("e") == 1.0

def test_penalty_formula_linear_and_bounded():
    h = PeerHealth(disagree_cap=0, agreement_window=10, agreement_threshold=0.8, agreement_min_votes=5)
    for a in [True]*4 + [False]*6: h.observe_vote("e", a)   # rate 0.4 -> 0.4/0.8 = 0.5
    assert h.agreement_factor("e") == pytest.approx(0.5)
    assert h.breakdown("e")["agreement"] == pytest.approx(0.5) and h.weight("e") == pytest.approx(0.5)
    for _ in range(10): h.observe_vote("e", False)          # rate 0 -> clamped 0.25
    assert h.agreement_factor("e") == 0.25

def test_at_or_above_threshold_no_penalty():
    h = PeerHealth(disagree_cap=0, agreement_threshold=0.5, agreement_min_votes=2)
    for a in [True, False]: h.observe_vote("e", a)
    assert h.agreement_factor("e") == 1.0

def test_min_votes_guard():
    h = PeerHealth(disagree_cap=0, agreement_threshold=0.9, agreement_min_votes=5)
    for _ in range(4): h.observe_vote("e", False)
    assert h.agreement_factor("e") == 1.0
    h.observe_vote("e", False); assert h.agreement_factor("e") == 0.25

def test_floor_and_dead_interplay():
    h = PeerHealth(disagree_cap=0, agreement_threshold=1.0, agreement_min_votes=1, weight_floor=0.5, fail_threshold=1)
    h.observe_vote("e", False); assert h.weight("e") == 0.5
    h.observe("e", False); assert h.weight("e") == 0.0

@pytest.mark.parametrize("kw", [dict(agreement_window=0), dict(agreement_window=True), dict(agreement_threshold=1.5),
    dict(agreement_threshold=float("nan")), dict(agreement_threshold=-0.1), dict(agreement_min_votes=0)])
def test_validation(kw):
    with pytest.raises(ValueError): PeerHealth(**kw)

def test_summary_exposes_settings():
    s = PeerHealth(agreement_window=7, agreement_threshold=0.6, agreement_min_votes=3).summary(["e"])
    assert (s["agreement_window"], s["agreement_threshold"], s["agreement_min_votes"]) == (7, 0.6, 3)
