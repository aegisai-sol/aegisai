import io, urllib.error, pytest
from email.message import Message
from aegis_miner import verify

class FakeResp(io.BytesIO):
    def __init__(self, body):
        super().__init__(body.encode()); self.headers = Message(); self.headers["Content-Type"] = "text/html; charset=utf-8"

class FakeOpener:
    """routes: url -> ("redirect", location) | ("page", html)"""
    def __init__(self, routes): self.routes, self.seen = routes, []
    def open(self, req, timeout=None):
        u = req.full_url; self.seen.append(u); kind, val = self.routes[u]
        if kind == "redirect":
            h = Message(); h["Location"] = val
            raise urllib.error.HTTPError(u, 302, "Found", h, None)
        return FakeResp(val)

@pytest.fixture(autouse=True)
def no_dns(monkeypatch): monkeypatch.setattr(verify, "_guard_url", lambda u: None)

def test_http_citation_refused():
    r = verify.check_claim({"text": "x", "url": "http://example.com/a"}, page_fetcher=lambda u: ("t", "b"))
    assert r["policy"] == "refused" and r["vote"] == "UNSURE" and r["confidence"] == 0.0
    r = verify.check_claim({"text": "x", "url": "http://example.com/a", "quote": "hi there"}, fetcher=lambda u: "hi there")
    assert r["policy"] == "refused"

def test_http_allowed_in_dev(monkeypatch):
    monkeypatch.setenv("AEGIS_ALLOW_HTTP", "1"); verify.citation_policy("http://example.com")

def test_non_web_scheme_refused():
    with pytest.raises(verify.CitationPolicyError): verify.citation_policy("ftp://example.com/x")

def test_same_site_redirect_fingerprinted():
    op = FakeOpener({"https://example.com/a": ("redirect", "https://www.example.com/b"),
                     "https://www.example.com/b": ("page", "<title>B</title>Solana launched mainnet in 2020.")})
    title, body, meta = verify.fetch_page("https://example.com/a", opener=op)
    assert meta["final_url"] == "https://www.example.com/b" and meta["redirect_chain"] == ["https://example.com/a", "https://www.example.com/b"]
    assert "same_site_host_change" in meta["redirect_flags"]
    r = verify.check_url_only("https://example.com/a", page_fetcher=lambda u: verify.fetch_page(u, opener=op), claim_text="Solana launched mainnet in 2020")
    assert r["final_url"] == "https://www.example.com/b" and r["policy"] == "flagged" and len(r["url_fingerprint"]) == 32

def test_cross_domain_redirect_refused():
    op = FakeOpener({"https://docs.example.com/x": ("redirect", "https://evil.example.net/x")})
    with pytest.raises(verify.CitationPolicyError, match="cross-domain"): verify.fetch_page("https://docs.example.com/x", opener=op)
    r = verify.check_url_only("https://docs.example.com/x", page_fetcher=lambda u: verify.fetch_page(u, opener=op), claim_text="x y z")
    assert r["policy"] == "refused" and r["vote"] == "UNSURE"

def test_https_downgrade_refused():
    op = FakeOpener({"https://example.com/a": ("redirect", "http://example.com/a")})
    with pytest.raises(verify.CitationPolicyError, match="downgrade"): verify.fetch_page("https://example.com/a", opener=op)

def test_http_to_https_upgrade_flagged(monkeypatch):
    monkeypatch.setenv("AEGIS_ALLOW_HTTP", "1")
    op = FakeOpener({"http://example.com/a": ("redirect", "https://example.com/a"), "https://example.com/a": ("page", "ok page")})
    assert "http_to_https_upgrade" in verify.fetch_page("http://example.com/a", opener=op)[2]["redirect_flags"]

def test_redirect_loop_capped():
    routes = {f"https://example.com/{i}": ("redirect", f"https://example.com/{i+1}") for i in range(10)}
    with pytest.raises(verify.CitationPolicyError, match="too many"): verify.fetch_page("https://example.com/0", opener=FakeOpener(routes))

def test_site_of_multi_tld():
    assert verify.site_of("a.b.bbc.co.uk") == "bbc.co.uk" and verify.site_of("www.example.com") == "example.com"
    assert verify.site_of("alice.github.io") != verify.site_of("bob.github.io")

def test_fingerprint_changes_with_final_url():
    a = verify._fingerprint("https://e.com", "t", "body", {"final_url": "https://e.com"})
    b = verify._fingerprint("https://e.com", "t", "body", {"final_url": "https://www.e.com"})
    assert a["source_hash"] == b["source_hash"] and a["url_fingerprint"] != b["url_fingerprint"]
