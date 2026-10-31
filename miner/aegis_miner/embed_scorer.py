"""Optional embedding scorer stub. Pluggable: if sentence-transformers is installed and
AEGIS_EMBED=1, uses a real model; otherwise a deterministic hashed bag-of-words vector
(no network, no deps) so the interface and tests are stable."""
import hashlib, math, os, re
DIM = 256
def _hash_vec(t):
    v = [0.0] * DIM
    for w in re.findall(r"[a-z0-9]+", t.lower()):
        v[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]
_model = None
def embed(t):
    global _model
    if os.environ.get("AEGIS_EMBED") == "1":
        try:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer("all-MiniLM-L6-v2")
            return list(_model.encode(t, normalize_embeddings=True))
        except ImportError: pass
    return _hash_vec(t)
def backend(): return "minilm" if _model is not None else "hash-bow"
def similarity(a, b): return round(sum(x * y for x, y in zip(embed(a), embed(b))), 4)
