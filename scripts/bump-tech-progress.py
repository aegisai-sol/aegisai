#!/usr/bin/env python3
"""Update site/tech-progress.json ONLY after a milestone's code is committed and tests are green.
Usage:
  scripts/bump-tech-progress.py --done ID [--note "..."] [--commit SHA]
  scripts/bump-tech-progress.py --active ID --pct N --now "text" [--detail "..."]
  scripts/bump-tech-progress.py --check
"""
import argparse, json, sys, datetime, pathlib
P = pathlib.Path(__file__).resolve().parent.parent / "site" / "tech-progress.json"
STATUSES = {"done", "active", "next", "blocked"}

def now(): return datetime.datetime.now().astimezone().isoformat(timespec="seconds")

def validate(d):
    errs = []
    ms = d.get("milestones")
    if not isinstance(ms, list) or not ms: errs.append("milestones missing")
    ids = set()
    for m in ms or []:
        for k in ("id", "title", "status", "updated_at"):
            if not m.get(k): errs.append(f"{m.get('id')}: missing {k}")
        if m.get("status") not in STATUSES: errs.append(f"{m.get('id')}: bad status {m.get('status')}")
        if m.get("id") in ids: errs.append(f"duplicate id {m['id']}")
        ids.add(m.get("id"))
    if sum(m.get("status") == "active" for m in ms or []) > 1: errs.append("more than one active")
    if not 0 <= int(d.get("active_progress", 0)) <= 100: errs.append("active_progress out of range")
    return errs

def recompute(d):
    ms = d["milestones"]
    for m in ms: m["detail"] = m.get("note", "")  # UI reads 'detail'
    d["counts"] = {s: sum(m["status"] == s for m in ms) for s in sorted(STATUSES)}
    d["counts"]["total"] = len(ms)
    if not any(m["status"] == "active" for m in ms): d["active_progress"] = 0

def main():
    a = argparse.ArgumentParser()
    a.add_argument("--done"); a.add_argument("--active"); a.add_argument("--pct", type=int)
    a.add_argument("--now"); a.add_argument("--detail"); a.add_argument("--note"); a.add_argument("--commit")
    a.add_argument("--check", action="store_true")
    o = a.parse_args()
    d = json.loads(P.read_text())
    byid = {m["id"]: m for m in d["milestones"]}
    t = now()
    for mid in filter(None, [o.done, o.active]):
        if mid not in byid: sys.exit(f"unknown id {mid}; known: {', '.join(byid)}")
    if o.done:
        m = byid[o.done]; m["status"] = "done"; m["updated_at"] = t
        if o.note: m["note"] = o.note
        if o.commit: m["commit"] = o.commit
    if o.active:
        for m in d["milestones"]:
            if m["status"] == "active" and m["id"] != o.active: m["status"] = "next"
        m = byid[o.active]; m["status"] = "active"; m["updated_at"] = t
        if o.note: m["note"] = o.note
        d["active_progress"] = o.pct or 0
    if o.now: d["now"] = o.now
    if o.detail: d["now_detail"] = o.detail
    if not o.check: d["updated_at"] = t
    recompute(d)
    e = validate(d)
    if e: sys.exit("INVALID: " + "; ".join(e))
    if not o.check: P.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
    print(f"ok: {d['counts']}")
main()
