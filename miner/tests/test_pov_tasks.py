"""PoV-R wallet-bound batches: Python miner matches claim-server / browser rules."""
import pytest
from aegis_miner import pov_tasks as p

S = b"test-secret"
W = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
T0 = 1_800_000_000
N = "0123456789abcdef"


def test_node_fixture_parity():
    b = p.issue_batch(S, W, 5, T0, N)
    assert b["batchId"] == "1800000000.0123456789abcdef.5.d06f405b5d557888d8b7e77d59cd3bda"
    assert b["tasks"] == [
        "543*473=256843",
        "prime(23500)",
        "sha256(agis:83071ab642ce)^82",
        "168*783=131544",
        "819*576=471744",
    ]
    ans = p.encode_answers(p.solve_task(t) for t in b["tasks"])
    assert ans == "18"
    g = p.grade_answers(S, b["batchId"], ans)
    assert g["correct"] == 5 and g["pass"] is True


def test_honest_solver_scores_100():
    b = p.issue_batch(S, W, 60, T0, N)
    g = p.grade_answers(S, b["batchId"], p.encode_answers(p.solve_task(t) for t in b["tasks"]))
    assert g["correct"] == 60 and g["pass"] is True


def test_solver_agrees_all_kinds():
    kinds = set()
    for k in range(20):
        bid = p.issue_batch(S, W, 120, T0 + k, N)["batchId"]
        for t in p.derive_tasks(S, bid):
            assert p.solve_task(t["text"]) is t["truth"]
            kinds.add(t["text"][0])
    assert len(kinds) >= 3


def test_guessing_fails_accuracy_gate():
    passes = 0
    for k in range(50):
        bid = p.issue_batch(S, W, 60, T0 + k, N)["batchId"]
        guess = [((k * 7 + i * 13) % 5) < 2 for i in range(60)]
        if p.grade_answers(S, bid, p.encode_answers(guess))["pass"]:
            passes += 1
        if p.grade_answers(S, bid, p.encode_answers([True] * 60))["pass"]:
            passes += 1
    assert passes == 0


def test_batch_bound_to_wallet_secret_time():
    bid = p.issue_batch(S, W, 10, T0, N)["batchId"]
    assert p.parse_batch(S, W, bid, T0 + 60)["n"] == 10
    with pytest.raises(ValueError, match="not issued"):
        p.parse_batch(S, "OtherWallet1111111111111111111111111111111", bid, T0)
    with pytest.raises(ValueError, match="not issued"):
        p.parse_batch(b"x", W, bid, T0)
    with pytest.raises(ValueError, match="expired"):
        p.parse_batch(S, W, bid, T0 + 25 * 3600)
    with pytest.raises(ValueError, match="not issued"):
        p.parse_batch(S, W, bid.replace(".10.", ".11."), T0)
    with pytest.raises(ValueError, match="bad batch"):
        p.parse_batch(S, W, "junk", T0)


def test_bad_inputs_fail_closed():
    with pytest.raises(ValueError):
        p.issue_batch(S, W, p.MAX_TASKS + 1, T0, N)
    with pytest.raises(ValueError):
        p.issue_batch(S, W, 0, T0, N)
    bid = p.issue_batch(S, W, 10, T0, N)["batchId"]
    with pytest.raises(ValueError, match="bad answers"):
        p.grade_answers(S, bid, "zz00")
    with pytest.raises(ValueError, match="bad answers"):
        p.grade_answers(S, bid, "ff")
    with pytest.raises(ValueError, match="unknown task"):
        p.solve_task("rm -rf")
