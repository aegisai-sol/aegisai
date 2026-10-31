"""Site demo (site/js/receipt-demo.js) must mirror reservoir.SPLIT_BPS and consensus status names."""
import pathlib, re
from aegis_miner import reservoir
JS = (pathlib.Path(__file__).resolve().parents[2] / "site" / "js" / "receipt-demo.js").read_text()

def test_split_bps_match():
    m = dict((k, int(v)) for k, v in re.findall(r"(\w+): (\d+)", re.search(r"SPLIT_BPS = \{([^}]*)\}", JS).group(1)))
    assert m == reservoir.SPLIT_BPS

def test_status_names():
    for s in ("VALID", "VALID_VERDICT", "HASH_ONLY", "NO_CONSENSUS"): assert f"'{s}'" in JS

def test_flagged_routes_miner_share_to_reservoir():
    r = reservoir.split_fee(1_000_000, {"self": 1, "peer0": 1}, flagged=True)
    assert r["parts"]["miners"] == 0 and r["parts"]["reservoir"] == 900_000
