"""PoV-R work proof for mining claims (pure; no keys, no RPC).

Mirrors agis-claim pov-tasks.mjs + browser docs/js/pov-solver.js:
  - server issues a wallet-bound batch of true/false verify tasks
  - tasks re-derived from HMAC(batch id) so nothing is stored until claim
  - only CORRECT answers become work units; below MIN_ACCURACY the claim fails
"""
from __future__ import annotations

import hashlib
import hmac
import re
from typing import Iterable

POV_DOMAIN = "AEGIS/pov-batch/v1"
MAX_TASKS = 120
MIN_ACCURACY = 0.9
BATCH_TTL_SEC = 24 * 3600

_BATCH_RE = re.compile(r"^(\d{9,11})\.([0-9a-f]{16})\.(\d{1,3})\.([0-9a-f]{32})$")
_MUL_RE = re.compile(r"^(\d+)\*(\d+)=(-?\d+)$")
_HASH_RE = re.compile(r"^sha256\((agis:[0-9a-f]+)\)\^([0-9a-f]{2})$")
_PRIME_RE = re.compile(r"^prime\((\d+)\)$")


def _mac(secret: bytes, s: str) -> bytes:
    return hmac.new(secret, s.encode(), hashlib.sha256).digest()


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _u16be(b: bytes, off: int) -> int:
    return (b[off] << 8) | b[off + 1]


def is_prime(x: int) -> bool:
    if not isinstance(x, int) or isinstance(x, bool) or x < 2:
        return False
    d = 2
    while d * d <= x:
        if x % d == 0:
            return False
        d += 1
    return True


def issue_batch(secret: bytes, wallet: str, n: int, iat_sec: int, nonce_hex: str) -> dict:
    if not isinstance(n, int) or isinstance(n, bool) or not (1 <= n <= MAX_TASKS):
        raise ValueError("bad task count")
    if not re.fullmatch(r"[0-9a-f]{16}", nonce_hex or ""):
        raise ValueError("bad nonce")
    tag = _mac(secret, f"{POV_DOMAIN}|{wallet}|{iat_sec}|{nonce_hex}|{n}")[:16].hex()
    batch_id = f"{iat_sec}.{nonce_hex}.{n}.{tag}"
    return {"batchId": batch_id, "tasks": [t["text"] for t in derive_tasks(secret, batch_id)]}


def parse_batch(secret: bytes, wallet: str, batch_id: str, now_sec: int) -> dict:
    m = _BATCH_RE.match(str(batch_id or ""))
    if not m:
        raise ValueError("bad batch")
    iat, n = int(m.group(1)), int(m.group(3))
    if not (1 <= n <= MAX_TASKS):
        raise ValueError("bad batch")
    want = _mac(secret, f"{POV_DOMAIN}|{wallet}|{iat}|{m.group(2)}|{n}")[:16]
    got = bytes.fromhex(m.group(4))
    if not hmac.compare_digest(want, got):
        raise ValueError("batch not issued to this wallet")
    if iat > now_sec + 120 or now_sec - iat > BATCH_TTL_SEC:
        raise ValueError("batch expired")
    return {"iat": iat, "n": n, "tag": m.group(4)}


def derive_tasks(secret: bytes, batch_id: str) -> list[dict]:
    n = int(str(batch_id).split(".")[2])
    out = []
    for i in range(n):
        r = _mac(secret, f"{POV_DOMAIN}|task|{batch_id}|{i}")
        kind = r[0] % 3
        flip = (r[1] & 1) == 1
        if kind == 0:
            a = 100 + _u16be(r, 2) % 900
            b = 100 + _u16be(r, 4) % 900
            d = 1 + r[6] % 9
            c = a * b + (0 if flip else (d if (r[7] & 1) else -d))
            out.append({"text": f"{a}*{b}={c}", "truth": flip})
        elif kind == 1:
            s = "agis:" + r[8:14].hex()
            h = _sha(s)[:2]
            p = h if flip else f"{(int(h, 16) + 1 + r[14] % 254) % 256:02x}"
            out.append({"text": f"sha256({s})^{p}", "truth": flip})
        else:
            x = 1001 + _u16be(r, 16) % 60000
            out.append({"text": f"prime({x})", "truth": is_prime(x)})
    return out


def solve_task(text: str) -> bool:
    m = _MUL_RE.match(text or "")
    if m:
        return int(m.group(1)) * int(m.group(2)) == int(m.group(3))
    m = _HASH_RE.match(text or "")
    if m:
        return _sha(m.group(1)).startswith(m.group(2))
    m = _PRIME_RE.match(text or "")
    if m:
        return is_prime(int(m.group(1)))
    raise ValueError("unknown task")


def encode_answers(bools: Iterable[bool]) -> str:
    bools = list(bools)
    raw = bytearray((len(bools) + 7) // 8)
    for i, b in enumerate(bools):
        if b:
            raw[i >> 3] |= 0x80 >> (i & 7)
    return raw.hex()


def grade_answers(secret: bytes, batch_id: str, answers_hex: str) -> dict:
    tasks = derive_tasks(secret, batch_id)
    n = len(tasks)
    if not re.fullmatch(r"[0-9a-f]*", str(answers_hex or "")) or len(answers_hex) != ((n + 7) // 8) * 2:
        raise ValueError("bad answers")
    raw = bytes.fromhex(answers_hex)
    correct = 0
    for i, t in enumerate(tasks):
        bit = (raw[i >> 3] & (0x80 >> (i & 7))) != 0
        if bit == t["truth"]:
            correct += 1
    accuracy = correct / n
    return {"n": n, "correct": correct, "accuracy": accuracy, "pass": accuracy >= MIN_ACCURACY}
