from aegis_miner import consensus as C, embed_scorer as E
PAGE = ("Solana", "Solana uses proof of history to order transactions quickly.")
CLAIM = "Solana uses proof of history"
def n(i, page=PAGE): return C.local_node(f"n{i}", page_fetcher=lambda u, p=page: p)
def test_valid_all_agree():
    r = C.consensus("https://x", CLAIM, [n(1), n(2), n(3)])
    assert r["status"] == "VALID" and r["valid"] and r["hash_agree"] == 3 and r["consensus_vote"] == "TRUE"
def test_dynamic_page_verdict_agree():
    pages = [("S", PAGE[1] + f" ad{i}") for i in range(3)]
    r = C.consensus("https://x", CLAIM, [n(i, p) for i, p in enumerate(pages)])
    assert r["status"] == "VALID_VERDICT" and r["consensus_hash"] is None
def test_tampered_node_outvoted():
    r = C.consensus("https://x", CLAIM, [n(1), n(2), n(3, ("S", "Totally unrelated cooking recipe text."))])
    assert r["valid"] and r["hash_agree"] == 2
def test_no_consensus_when_nodes_down():
    def boom(u): raise OSError("down")
    r = C.consensus("https://x", CLAIM, [n(1), C.local_node("n2", boom), C.local_node("n3", boom)])
    assert r["status"] == "NO_CONSENSUS" and not r["valid"]
def test_needs_quorum_nodes():
    import pytest
    with pytest.raises(ValueError): C.consensus("https://x", CLAIM, [n(1)])
def test_digest_stable():
    a = C.consensus("https://x", CLAIM, [n(1), n(2)]); b = C.consensus("https://x", CLAIM, [n(3), n(4)])
    assert a["receipt_digest"] == b["receipt_digest"]
def test_embed_stub():
    assert E.similarity("solana proof of history", "proof of history solana") > 0.99
    assert E.similarity("solana proof of history", "banana bread recipe") < 0.2
