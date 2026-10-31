"""PoV-R verify path: decompose AI text into micro-claims and check each one.
Methods: arithmetic (exact), source (fetch cited URL, quote substring), heuristic (keyword, low conf)."""
import hashlib, os, re, urllib.request

FALSE_MARKERS = ["flat", "sun orbits", "always", "never", "100% guaranteed", "cure"]
URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")
QUOTE_RE = re.compile(r"[\"\u201c\u201e]([^\"\u201c\u201d\u201e]{4,})[\"\u201d\u201c]")
ARITH_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*([+\-*/x×])\s*(-?\d+(?:\.\d+)?)\s*=\s*(-?\d+(?:\.\d+)?)")
UA = "AegisAI-PoV/0.1"

def _id(s): return hashlib.sha256(s.encode()).hexdigest()[:12]

LIST_RE = re.compile(r"^\s*(?:[-*\u2022\u2013]|\d{1,3}[.)]|\(\d{1,3}\)|[a-zA-Z][.)])\s+")
URL_GUARD = re.compile(r"https?://\S+?(?=[.,;:!?)\]]*(?:\s|$))")

def split_sentences(text):
    """Split into micro-claims: lines first (handles numbered / bulleted lists), then sentences.
    URLs are protected so their dots don't split a sentence."""
    out = []
    for line in text.strip().splitlines():
        line = LIST_RE.sub("", line).strip()
        if not line: continue
        urls = []
        g = URL_GUARD.sub(lambda m: urls.append(m.group(0)) or f"\x00{len(urls)-1}\x00", line)
        for p in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"\u201c\u201eА-Я])", g):
            p = re.sub(r"\x00(\d+)\x00", lambda m: urls[int(m[1])], p).strip()
            if p: out.append(p)
    return out

def decompose(text):
    out = []
    for s in split_sentences(text):
        c = {"claim_id": _id(s), "text": s}
        u = URL_RE.search(s)
        if u: c["url"] = u.group(0).rstrip(".,;:")
        q = QUOTE_RE.search(s)
        if q: c["quote"] = q.group(1).strip()
        out.append(c)
    return out

def tiny_check(text):
    """Returns (bool, confidence). Arithmetic exact; else keyword heuristic."""
    m = ARITH_RE.search(text)
    if m:
        a, op, b, r = float(m[1]), m[2], float(m[3]), float(m[4])
        try: v = {"+": a + b, "-": a - b, "*": a * b, "x": a * b, "×": a * b, "/": a / b if b else None}[op]
        except Exception: v = None
        if v is not None: return abs(v - r) < 1e-9, 0.99
    bad = any(k in text.lower() for k in FALSE_MARKERS)
    return (not bad), (0.8 if bad else 0.65)

def norm(s): return re.sub(r"\s+", " ", s).strip()

def _html_text(raw):
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    import html; return html.unescape(raw)

TITLE_RE = re.compile(r"(?is)<title[^>]*>(.*?)</title>")

def _guard_url(url):
    """SSRF guard: only public http(s) hosts may be fetched by the coordinator."""
    import ipaddress, socket, urllib.parse
    if not url.startswith(("http://", "https://")): raise ValueError("only http(s) URLs")
    host = urllib.parse.urlsplit(url).hostname or ""
    for info in socket.getaddrinfo(host, None):
        ip = ipaddress.ip_address(info[4][0])
        # Some sandboxes/proxies resolve every host to fake-IP 198.18.0.0/15; opt in explicitly.
        if os.environ.get("AEGIS_ALLOW_FAKEIP") and ip in ipaddress.ip_network("198.18.0.0/15"): continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("refusing non-public host")

MAX_REDIRECTS = 5
MULTI_TLD = {"co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "net.au", "org.au", "co.jp", "co.nz", "com.br", "co.in", "github.io", "here.now"}

class CitationPolicyError(ValueError):
    """Citation refused by Proof-of-Source policy (scheme, downgrade, cross-site redirect)."""

def site_of(host):
    """Naive registrable domain (eTLD+1) without external PSL download."""
    labels = (host or "").lower().rstrip(".").split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in MULTI_TLD: return ".".join(labels[-3:])
    return ".".join(labels[-2:])

def citation_policy(url):
    """HTTPS-only citations. Set AEGIS_ALLOW_HTTP=1 only for local dev."""
    import urllib.parse
    sch = urllib.parse.urlsplit(url).scheme.lower()
    if sch == "https": return
    if sch == "http" and os.environ.get("AEGIS_ALLOW_HTTP") == "1": return
    raise CitationPolicyError("citation must be https:// (got %s)" % (sch or "none"))

def redirect_verdict(chain):
    """Inspect a redirect chain [url0, url1, ...]. Returns (refuse_reason|None, flags)."""
    import urllib.parse
    flags = []
    for a, b in zip(chain, chain[1:]):
        ua, ub = urllib.parse.urlsplit(a), urllib.parse.urlsplit(b)
        if ua.scheme == "https" and ub.scheme != "https": return "https->http downgrade redirect", flags
        if ua.scheme == "http" and ub.scheme == "https": flags.append("http_to_https_upgrade")
        if site_of(ua.hostname) != site_of(ub.hostname): return "cross-domain redirect %s -> %s" % (ua.hostname, ub.hostname), flags
        if ua.hostname != ub.hostname: flags.append("same_site_host_change")
    if len(chain) - 1 > MAX_REDIRECTS: return "too many redirects", flags
    return None, flags

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None

def fetch_page(url, timeout=8, opener=None):
    """Returns (title, normalized_text, meta). Follows redirects manually: every hop is SSRF-guarded,
    https-only, same-site; meta carries final_url + redirect_chain for the receipt fingerprint."""
    import html, urllib.parse, urllib.error
    citation_policy(url)
    opener = opener or urllib.request.build_opener(_NoRedirect)
    chain, cur = [url], url
    while True:
        _guard_url(cur)
        try:
            r = opener.open(urllib.request.Request(cur, headers={"User-Agent": UA}), timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                nxt = urllib.parse.urljoin(cur, e.headers["Location"]); chain.append(nxt)
                bad, _ = redirect_verdict(chain)
                if bad: raise CitationPolicyError(bad)
                cur = nxt; continue
            raise
        with r:
            raw = r.read(2_000_000).decode(r.headers.get_content_charset() or "utf-8", "replace")
        break
    _, flags = redirect_verdict(chain)
    t = TITLE_RE.search(raw)
    meta = {"final_url": cur, "redirect_chain": chain, "redirect_flags": flags}
    return (norm(html.unescape(t.group(1)))[:200] if t else ""), norm(_html_text(raw)), meta

def fetch(url, timeout=8): return fetch_page(url, timeout)[1]

def _unpack(res):
    return (res[0], res[1], res[2] if len(res) > 2 else {})

STOP = set("""a an the and or but of to in on at for with by from as is are was were be been being this that these those it its
which who whom whose what when where how than then so such per via into over under about after before also not no
says say said according see study page source docs report states stated shows show i we you they he she our their""".split())
WORD_RE = re.compile(r"[a-z\u0400-\u04ff][a-z0-9\u0400-\u04ff'-]{2,}")
NUM_RE = re.compile(r"(?<![\w.])-?\d+(?:[.,]\d+)?%?")

def _terms(t):
    return {w for w in WORD_RE.findall(t.casefold()) if w not in STOP}

def _nums(t): return {n.replace(",", ".") for n in NUM_RE.findall(t)}

def claim_core(text):
    """Claim text minus URLs — the assertion we must find support for."""
    return norm(URL_RE.sub(" ", text))

def _passages(body, size=3):
    sents = [x for x in re.split(r"(?<=[.!?])\s+", body) if x.strip()]
    for k in range(len(sents)):
        yield " ".join(sents[k:k + size])

NEG_RE = re.compile(r"\b(not|no|never|none|neither|nor|cannot|can't|won't|isn't|aren't|wasn't|weren't|doesn't|don't|didn't|hasn't|haven't|hadn't|without|false|denied|denies|fails?|failed|lacks?|не|няма|никога)\b", re.I)
SYN = [  # tiny paraphrase lexicon: each group collapses to one concept id
    "launch launched launches launching release released releases debut debuted start started began begin introduced introduce went live",
    "buy buys bought purchase purchased acquire acquired acquisition",
    "increase increased increases rise rose risen grow grew grown growth raise raised up higher",
    "decrease decreased decreases fall fell fallen drop dropped decline declined reduce reduces reduced lower cut cuts",
    "big large huge major",  "small little minor tiny",
    "secure secures securing protect protects protected safeguard",
    "use uses used utilize utilizes employ employs", "fast quick rapid speedy", "allow allows allowed permit permits enable enables",
    "create created creates build built make made founded found established",
    "ceo chief executive", "company firm corporation business", "price cost costs priced",
]
ANT = [("increase", "decrease"), ("big", "small"), ("true", "false"), ("win", "lose"), ("open", "closed"), ("before", "after")]
_C = {}
for g in SYN:
    ws = g.split(); [_C.setdefault(w, ws[0]) for w in ws]
for a, b in [("won", "win"), ("wins", "win"), ("lost", "lose"), ("loses", "lose"), ("closes", "closed"), ("opens", "open")]: _C[a] = b

def _stem(w):
    if w in _C: return _C[w]
    for suf in ("ings", "ing", "edly", "ed", "es", "s", "ly"):
        if len(w) > len(suf) + 3 and w.endswith(suf): w = w[:-len(suf)]; break
    return _C.get(w, w)

def _concepts(t): return {_stem(w) for w in _terms(t)}
def _neg(t): return len(NEG_RE.findall(t)) % 2 == 1  # double negation cancels

def meaning_score(claim_text, passage):
    """Lightweight local entailment heuristic (no paid APIs, no model downloads).
    coverage = share of claim concepts (stemmed + synonym-collapsed) in the passage;
    polarity: claim vs passage negation parity; antonym flip (claim 'increase' vs page 'decrease')."""
    c, p = _concepts(claim_text), _concepts(passage)
    if not c: return 0.0, False
    cov = len(c & p) / len(c)
    flip = _neg(claim_text) != _neg(passage)
    for a, b in ANT:
        if (a in c and b in p and a not in p) or (b in c and a in p and b not in p): flip = not flip
    return cov, flip

def support_check(claim_text, body):
    """Find the passage in `body` that best supports `claim_text` by meaning, not raw words.
    SUPPORTED: concept coverage >=0.7, same polarity, all claim numbers present.
    CONTRADICTED: matching passage but opposite polarity (negation/antonym) or number mismatch."""
    terms, nums = _terms(claim_text), _nums(claim_text)
    if not terms: return {"support": 0.0, "verdict": "NO_CONTENT", "evidence": ""}
    best, best_p, best_flip = -1.0, "", False
    for size in (1, 3):
        for p in _passages(body, size):
            sc, flip = meaning_score(claim_text, p)
            sc -= 0.01 * size  # prefer the tightest passage on ties
            if sc > best: best, best_p, best_flip = sc, p, flip
    best = max(best, 0.0) + (0.03 if best > 0 else 0)
    best = min(best, 1.0)
    missing = sorted(nums - _nums(best_p)) if nums else []
    if best >= 0.7 and (missing or best_flip): v = "CONTRADICTED"
    elif best >= 0.7: v = "SUPPORTED"
    elif best >= 0.4: v = "PARTIAL"
    else: v = "NOT_FOUND"
    r = {"support": round(best, 2), "verdict": v, "evidence": best_p[:300], "scorer": "meaning-v1"}
    if missing: r["numbers_missing"] = missing
    if best_flip and best >= 0.7: r["polarity"] = "opposite"
    return r

def _fingerprint(url, title, body, meta=None):
    import time
    meta = meta or {}
    final = meta.get("final_url", url)
    fp = {"source_hash": hashlib.sha256(body[:50_000].encode()).hexdigest(), "page_title": title,
          "content_chars": len(body), "fetched_at": int(time.time()), "source_url": url, "final_url": final,
          "redirect_chain": meta.get("redirect_chain", [url]), "redirect_flags": meta.get("redirect_flags", [])}
    fp["url_fingerprint"] = hashlib.sha256((url + "\n" + final + "\n" + fp["source_hash"]).encode()).hexdigest()[:32]
    return fp

SUPPORT_VOTE = {"SUPPORTED": ("TRUE", 0.8), "CONTRADICTED": ("FALSE", 0.75), "NOT_FOUND": ("FALSE", 0.7),
                "PARTIAL": ("UNSURE", 0.5), "NO_CONTENT": ("UNSURE", 0.5)}

def check_url_only(url, page_fetcher=fetch_page, claim_text=""):
    """URL cited without a quote: prove the page exists, fingerprint it, then check the claim's
    assertion against the retrieved text (Proof-of-Source support check)."""
    try: citation_policy(url); title, body, meta = _unpack(page_fetcher(url))
    except CitationPolicyError as e:
        return {"vote": "UNSURE", "confidence": 0.0, "method": "source", "policy": "refused", "error": str(e)[:120]}
    except Exception as e:
        return {"vote": "FALSE", "confidence": 0.7, "method": "source", "error": "cited URL unreachable: " + str(e)[:100]}
    r = {"method": "source", **_fingerprint(url, title, body, meta)}
    if r["redirect_flags"]: r["policy"] = "flagged"
    core = claim_core(claim_text)
    if not _terms(core):
        return dict(r, vote="UNSURE", confidence=0.5, note="no quote to match", support={"verdict": "NO_CONTENT", "support": 0.0})
    sup = support_check(core, body); vote, conf = SUPPORT_VOTE[sup["verdict"]]
    return dict(r, vote=vote, confidence=conf, support=sup, note="claim " + sup["verdict"].lower().replace("_", " ") + " by cited page")

CANARY_POOL = [("7 + 5 = 12"), ("9 * 8 = 72"), ("100 - 37 = 63"), ("144 / 12 = 12"), ("15 + 27 = 42")]
# canaries-v2: hidden patterns with known answers. FALSE traps catch "always TRUE" yes-miners;
# big-number and division traps catch lazy/approximate miners. Never disclosed per-request.
CANARY_POOL_V2 = [("6 * 7 = 41", "FALSE"), ("50 - 8 = 40", "FALSE"), ("1000 / 8 = 125", "TRUE"),
                  ("12345 + 67890 = 80235", "TRUE"), ("81 / 9 = 8", "FALSE")]
CANARY_KINDS = {"v1-true": len(CANARY_POOL), "v2": len(CANARY_POOL_V2)}

def make_canary(seed=None, v2=True):
    import random
    pool = [(t, "TRUE") for t in CANARY_POOL] + (CANARY_POOL_V2 if v2 else [])
    t, exp = random.Random(seed).choice(pool)
    return {"claim_id": "canary-" + _id(t + str(seed)), "text": t, "canary": True, "expected": exp}

def make_canaries(seed=None, n=2):
    """n distinct canaries; at least one FALSE trap when n>=2 so a yes-miner can't pass."""
    import random
    r = random.Random(seed); out = []
    if n >= 2:
        t, e = r.choice([c for c in CANARY_POOL_V2 if c[1] == "FALSE"])
        out.append({"claim_id": "canary-" + _id(t + str(seed) + "f"), "text": t, "canary": True, "expected": e})
    while len(out) < n:
        c = make_canary(f"{seed}-{len(out)}-{r.random()}")
        if c["text"] not in {o["text"] for o in out}: out.append(c)
    return out

def canary_ok(claims, client_votes=None):
    """Calibration: every canary must be voted TRUE (by the server and, if given, by the client/miner)."""
    bad = []
    for c in claims:
        if not c.get("canary"): continue
        if c.get("vote") != c["expected"]: bad.append(c["claim_id"])
        if client_votes and c["claim_id"] in client_votes and str(client_votes[c["claim_id"]]).upper() != c["expected"]:
            bad.append(c["claim_id"])
    return not bad, bad

def check_source(url, quote, fetcher=fetch):
    """Quoted citation: exact (normalized) match, else fuzzy best-passage match (>=0.9 term overlap)."""
    try: citation_policy(url); body = fetcher(url)
    except CitationPolicyError as e:
        return {"vote": "UNSURE", "confidence": 0.0, "method": "source", "policy": "refused", "error": str(e)[:120]}
    except Exception as e:
        return {"vote": "UNSURE", "confidence": 0.0, "method": "source", "error": str(e)[:120]}
    h = hashlib.sha256(body[:50_000].encode()).hexdigest()
    if norm(quote).casefold() in body.casefold():
        return {"vote": "TRUE", "confidence": 0.9, "method": "source", "source_hash": h,
                "support": {"verdict": "EXACT_QUOTE", "support": 1.0}}
    sup = support_check(quote, body)
    if sup["verdict"] == "SUPPORTED" and sup["support"] >= 0.9:
        return {"vote": "TRUE", "confidence": 0.75, "method": "source", "source_hash": h,
                "support": dict(sup, verdict="NEAR_QUOTE"), "note": "quote paraphrased, not verbatim"}
    return {"vote": "FALSE", "confidence": 0.75, "method": "source", "source_hash": h, "support": sup,
            "note": "quote not found on cited page"}

def check_claim(claim, fetcher=fetch, page_fetcher=fetch_page):
    if claim.get("url") and claim.get("quote"):
        return check_source(claim["url"], claim["quote"], fetcher)
    if claim.get("url"):
        return check_url_only(claim["url"], page_fetcher, claim.get("text", ""))
    if ARITH_RE.search(claim["text"]):
        ok, c = tiny_check(claim["text"])
        return {"vote": "TRUE" if ok else "FALSE", "confidence": c, "method": "arithmetic"}
    ok, c = tiny_check(claim["text"])
    if c < 0.7: return {"vote": "UNSURE", "confidence": c, "method": "heuristic"}
    return {"vote": "TRUE" if ok else "FALSE", "confidence": c, "method": "heuristic"}
