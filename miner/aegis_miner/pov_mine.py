"""Desktop PoV-R mine path: fetch wallet-bound batch → solve → claim message.

No keys, no RPC. Signing stays in the wallet (browser Phantom or a local signer).
Mirrors site/js/pov-solver.js against the live claim server.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

from . import pov_tasks as pt

CLAIM_DOMAIN = "AEGIS/mine-claim/v2"
DEFAULT_CLAIM_BASE = "https://agis-claim.onrender.com"
DEFAULT_N = 120
FETCH_TIMEOUT_SEC = 75
CLAIM_TIMEOUT_SEC = 90


def build_claim_msg(
    *,
    wallet: str,
    batch_id: str,
    answers_hex: str,
    from_iso: str,
    to_iso: str,
    claim_uuid: str,
    tier: str,
    cores: int,
    bench_ms: int,
) -> str:
    fields = [wallet, batch_id, answers_hex, from_iso, to_iso, claim_uuid, tier, str(cores), str(bench_ms)]
    if any(x is None or "|" in str(x) for x in fields):
        raise ValueError("bad claim field")
    return "|".join([CLAIM_DOMAIN, *fields])


def work_window(issued_at_iso: str, elapsed_ms: float) -> dict[str, str]:
    t0 = _parse_iso_ms(issued_at_iso)
    return {
        "from": _iso_ms(t0),
        "to": _iso_ms(t0 + max(1000, int(round(elapsed_ms)))),
    }


def _parse_iso_ms(s: str) -> int:
    # Accept Z or +00:00; return unix ms.
    from datetime import datetime, timezone

    raw = str(s or "").strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _iso_ms(ms: int) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def fetch_batch(base: str, wallet: str, n: int = DEFAULT_N, timeout_sec: float = FETCH_TIMEOUT_SEC) -> dict[str, Any]:
    if not wallet or not str(wallet).strip():
        raise ValueError("wallet required")
    if not isinstance(n, int) or isinstance(n, bool) or not (1 <= n <= pt.MAX_TASKS):
        raise ValueError("bad task count")
    q = urllib.parse.urlencode({"wallet": wallet, "n": n})
    url = f"{base.rstrip('/')}/api/mine/tasks?{q}"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "Cache-Control": "no-store"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as r:
            body = r.read().decode()
            status = r.status
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        status = e.code
    except Exception as e:
        raise RuntimeError(f"claim server unreachable: {e}") from e
    try:
        j = json.loads(body)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"bad claim response {status}") from e
    if status >= 400 or not j.get("ok"):
        raise RuntimeError(j.get("error") or f"claim server error {status}")
    if j.get("domain") != CLAIM_DOMAIN or not j.get("batchId") or not isinstance(j.get("tasks"), list) or not j["tasks"]:
        raise RuntimeError("unexpected task batch format")
    return j


def solve_batch(tasks: list[str]) -> tuple[list[bool], str, float]:
    t0 = time.perf_counter()
    answers = [pt.solve_task(t) for t in tasks]
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return answers, pt.encode_answers(answers), elapsed_ms


def prepare_claim(
    *,
    wallet: str,
    batch: dict[str, Any],
    answers_hex: str,
    elapsed_ms: float,
    tier: str = "laptop",
    cores: int = 4,
    bench_ms: int | None = None,
    claim_uuid: str | None = None,
) -> dict[str, Any]:
    window = work_window(batch["issuedAt"], elapsed_ms)
    uid = claim_uuid or str(uuid.uuid4())
    ms = max(1, int(round(bench_ms if bench_ms is not None else elapsed_ms)))
    msg = build_claim_msg(
        wallet=wallet,
        batch_id=batch["batchId"],
        answers_hex=answers_hex,
        from_iso=window["from"],
        to_iso=window["to"],
        claim_uuid=uid,
        tier=tier,
        cores=cores,
        bench_ms=ms,
    )
    return {
        "wallet": wallet,
        "batchId": batch["batchId"],
        "n": len(batch["tasks"]),
        "answersHex": answers_hex,
        "msg": msg,
        "issuedAt": batch["issuedAt"],
        "elapsedMs": round(elapsed_ms, 2),
        "tier": tier,
        "cores": cores,
        "benchMs": ms,
        "uuid": uid,
        "postBody": {"wallet": wallet, "msg": msg, "sig": None},
        "note": "Sign msg with the wallet (ed25519), then POST postBody with sig to /api/claim. No keys here.",
    }


def run_once(
    wallet: str,
    *,
    base: str = DEFAULT_CLAIM_BASE,
    n: int = DEFAULT_N,
    tier: str = "laptop",
    cores: int = 4,
) -> dict[str, Any]:
    """Fetch → solve → prepare unsigned claim. Does not post or sign."""
    batch = fetch_batch(base, wallet, n=n)
    answers, answers_hex, elapsed_ms = solve_batch(batch["tasks"])
    out = prepare_claim(
        wallet=wallet,
        batch=batch,
        answers_hex=answers_hex,
        elapsed_ms=elapsed_ms,
        tier=tier,
        cores=cores,
        bench_ms=elapsed_ms,
    )
    out["answers"] = answers
    return out


def local_demo(secret: bytes, wallet: str, n: int = 12, iat_sec: int | None = None, nonce_hex: str = "0123456789abcdef") -> dict[str, Any]:
    """Offline parity path: issue with the same HMAC rules, solve, grade. No network."""
    iat = int(time.time()) if iat_sec is None else iat_sec
    issued = pt.issue_batch(secret, wallet, n, iat, nonce_hex)
    answers, answers_hex, elapsed_ms = solve_batch(issued["tasks"])
    grade = pt.grade_answers(secret, issued["batchId"], answers_hex)
    from datetime import datetime, timezone

    issued_at = datetime.fromtimestamp(iat, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    batch = {"batchId": issued["batchId"], "tasks": issued["tasks"], "issuedAt": issued_at}
    out = prepare_claim(wallet=wallet, batch=batch, answers_hex=answers_hex, elapsed_ms=elapsed_ms)
    out["grade"] = grade
    out["answers"] = answers
    out["local"] = True
    return out
