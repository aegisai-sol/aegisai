import json, os
from aegis_miner.consensus import receipt_digest

def test_js_python_digest_match():
    v = json.load(open(os.path.join(os.path.dirname(__file__), "receipt_digest_vectors.json")))
    assert len(v) == 3
    for k, x in v.items():
        assert receipt_digest(x["body"]) == x["digest"], k
        assert x["digest"].startswith("sha256:") and len(x["digest"]) == 71

def test_digest_key_order_independent():
    assert receipt_digest({"a": 1, "b": [1, {"y": 2, "x": 1}]}) == receipt_digest({"b": [1, {"x": 1, "y": 2}], "a": 1})
