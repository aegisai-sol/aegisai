"""PoV-R verify path: decompose AI text into micro-claims and check each one.
Methods: arithmetic (exact), source (fetch cited URL, quote substring), heuristic (keyword, low conf)."""
import hashlib, re, urllib.request

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

def fetch_page(url, timeout=8):
    """Returns (title, normalized_text)."""
    if not url.startswith(("http://", "https://")): raise ValueError("only http(s) URLs")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(2_000_000).decode(r.headers.get_content_charset() or "utf-8", "replace")
    import html
    t = TITLE_RE.search(raw)
    return (norm(html.unescape(t.group(1)))[:200] if t else ""), norm(_html_text(raw))

def fetch(url, timeout=8): return fetch_page(url, timeout)[1]

def check_url_only(url, page_fetcher=fetch_page):
    """URL cited without a quote: prove the page exists (title + hash) but can't confirm the claim."""
    try: title, body = page_fetcher(url)
    except Exception as e:
        return {"vote": "FALSE", "confidence": 0.7, "method": "source", "error": "cited URL unreachable: " + str(e)[:100]}
    return {"vote": "UNSURE", "confidence": 0.5, "method": "source", "page_title": title,
            "source_hash": hashlib.sha256(body[:50_000].encode()).hexdigest(), "note": "no quote to match"}

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
    try: body = fetcher(url)
    except Exception as e:
        return {"vote": "UNSURE", "confidence": 0.0, "method": "source", "error": str(e)[:120]}
    h = hashlib.sha256(body[:50_000].encode()).hexdigest()
    ok = norm(quote).casefold() in body.casefold()
    return {"vote": "TRUE" if ok else "FALSE", "confidence": 0.9 if ok else 0.75, "method": "source", "source_hash": h}

def check_claim(claim, fetcher=fetch, page_fetcher=fetch_page):
    if claim.get("url") and claim.get("quote"):
        return check_source(claim["url"], claim["quote"], fetcher)
    if claim.get("url"):
        return check_url_only(claim["url"], page_fetcher)
    if ARITH_RE.search(claim["text"]):
        ok, c = tiny_check(claim["text"])
        return {"vote": "TRUE" if ok else "FALSE", "confidence": c, "method": "arithmetic"}
    ok, c = tiny_check(claim["text"])
    if c < 0.7: return {"vote": "UNSURE", "confidence": c, "method": "heuristic"}
    return {"vote": "TRUE" if ok else "FALSE", "confidence": c, "method": "heuristic"}
