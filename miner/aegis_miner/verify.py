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

def fetch_page(url, timeout=8):
    """Returns (title, normalized_text)."""
    _guard_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(2_000_000).decode(r.headers.get_content_charset() or "utf-8", "replace")
    import html
    t = TITLE_RE.search(raw)
    return (norm(html.unescape(t.group(1)))[:200] if t else ""), norm(_html_text(raw))

def fetch(url, timeout=8): return fetch_page(url, timeout)[1]

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

def support_check(claim_text, body):
    """Find the passage in `body` that best supports `claim_text`.
    Score = share of claim content-terms present in the passage; numbers in the claim must appear
    in that passage (a number mismatch on an otherwise matching passage = contradiction)."""
    terms, nums = _terms(claim_text), _nums(claim_text)
    if not terms: return {"support": 0.0, "verdict": "NO_CONTENT", "evidence": ""}
    best, best_p = -1.0, ""
    for p in _passages(body):
        sc = len(terms & _terms(p)) / len(terms)
        if sc > best: best, best_p = sc, p
    missing = sorted(nums - _nums(best_p)) if nums else []
    if best >= 0.7 and not missing: v = "SUPPORTED"
    elif best >= 0.7 and missing: v = "CONTRADICTED"
    elif best >= 0.4: v = "PARTIAL"
    else: v = "NOT_FOUND"
    r = {"support": round(max(best, 0.0), 2), "verdict": v, "evidence": best_p[:300]}
    if missing: r["numbers_missing"] = missing
    return r

def _fingerprint(url, title, body):
    import time
    return {"source_hash": hashlib.sha256(body[:50_000].encode()).hexdigest(), "page_title": title,
            "content_chars": len(body), "fetched_at": int(time.time()), "source_url": url}

SUPPORT_VOTE = {"SUPPORTED": ("TRUE", 0.8), "CONTRADICTED": ("FALSE", 0.75), "NOT_FOUND": ("FALSE", 0.7),
                "PARTIAL": ("UNSURE", 0.5), "NO_CONTENT": ("UNSURE", 0.5)}

def check_url_only(url, page_fetcher=fetch_page, claim_text=""):
    """URL cited without a quote: prove the page exists, fingerprint it, then check the claim's
    assertion against the retrieved text (Proof-of-Source support check)."""
    try: title, body = page_fetcher(url)
    except Exception as e:
        return {"vote": "FALSE", "confidence": 0.7, "method": "source", "error": "cited URL unreachable: " + str(e)[:100]}
    r = {"method": "source", **_fingerprint(url, title, body)}
    core = claim_core(claim_text)
    if not _terms(core):
        return dict(r, vote="UNSURE", confidence=0.5, note="no quote to match", support={"verdict": "NO_CONTENT", "support": 0.0})
    sup = support_check(core, body); vote, conf = SUPPORT_VOTE[sup["verdict"]]
    return dict(r, vote=vote, confidence=conf, support=sup, note="claim " + sup["verdict"].lower().replace("_", " ") + " by cited page")

CANARY_POOL = [("7 + 5 = 12"), ("9 * 8 = 72"), ("100 - 37 = 63"), ("144 / 12 = 12"), ("15 + 27 = 42")]

def make_canary(seed=None):
    import random
    t = random.Random(seed).choice(CANARY_POOL)
    return {"claim_id": "canary-" + _id(t + str(seed)), "text": t, "canary": True, "expected": "TRUE"}

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
    try: body = fetcher(url)
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
