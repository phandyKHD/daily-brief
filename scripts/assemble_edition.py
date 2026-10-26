#!/usr/bin/env python3
"""Merge desk outputs into an edition file (the mechanical part of the editor step).

Usage:
  python3 scripts/assemble_edition.py YYYY-MM-DD daily   [--lead "exact title"] [--changes "sentence" ...]
  python3 scripts/assemble_edition.py YYYY-MM-DD refresh
  python3 scripts/assemble_edition.py YYYY-MM-DD briefs     # add briefs to today's file, no new round

Desk files (dist/desk-*.json, dist/briefs-*.json) are either {"articles": [...], "briefs": [...]}
or a plain list of articles.

Reads every dist/desk-*.json, orders articles by topic (optionally putting one lead
story first), assigns ids and the round number, and writes data/editions/YYYY-MM-DD.json.
In refresh mode the new articles are appended to today's file as the next round.
The editorial judgement (dedupe, fact checks, cutting weak pieces) happens before this:
edit or delete desk files first.
"""
import datetime as dt
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

ROOT = common.HOME
ORDER = [t for t, _ in common.topics()]
FIELDS = ["topic", "title", "kind", "read_minutes", "tldr", "body", "why_it_matters", "sources", "tags", "update_of", "visual", "from_brief", "request_focus"]
BRIEF_FIELDS = ["topic", "title", "summary", "sources", "tags"]


def opt(name, multi=False):
    vals = [sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a == name]
    return vals if multi else (vals[0] if vals else None)


def main():
    pos = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith("--") and sys.argv[i - 1] not in ("--lead", "--changes")]
    if len(pos) != 2 or pos[1] not in ("daily", "refresh", "briefs"):
        print(__doc__)
        sys.exit(2)
    date, mode = pos
    lead = opt("--lead")
    changes = opt("--changes", multi=True)

    new, briefs = [], []
    paths = sorted(glob.glob(os.path.join(ROOT, "dist", "desk-*.json")) + glob.glob(os.path.join(ROOT, "dist", "briefs-*.json")))
    for path in paths:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        arts = doc if isinstance(doc, list) else doc.get("articles", [])
        new += [{k: a.get(k) for k in FIELDS} for a in arts]
        if not isinstance(doc, list):
            briefs += [{k: b.get(k) for k in BRIEF_FIELDS} for b in doc.get("briefs", [])]
    if mode == "briefs":
        new = []
    if not new and not briefs:
        sys.exit("No desk files found in dist/")
    for b in briefs:
        b["tags"] = [t.lower() for t in (b.get("tags") or [])]
    briefs.sort(key=lambda b: ORDER.index(b["topic"]) if b["topic"] in ORDER else 99)
    for a in new:
        a["tags"] = [t.lower() for t in (a.get("tags") or [])]
        a["update_of"] = a.get("update_of") or None
        a["visual"] = a.get("visual") or None
        a["from_brief"] = a.get("from_brief") or None
        a["request_focus"] = a.get("request_focus") or None
        # The viewer adds its own "Why it matters" heading, so drop one the desk wrote into the text.
        a["why_it_matters"] = re.sub(r"^\s*why it matters[^:]{0,20}:\s*", "", a.get("why_it_matters") or "", flags=re.I) or None
        if a["why_it_matters"]:
            a["why_it_matters"] = a["why_it_matters"][0].upper() + a["why_it_matters"][1:]
    # Lead first, then stories Peter asked for, then the usual topic order.
    new.sort(key=lambda a: (0 if lead and a["title"] == lead else 1, 0 if a["from_brief"] else 1,
                            ORDER.index(a["topic"]) if a["topic"] in ORDER else 99))
    if lead and new[0]["title"] != lead:
        sys.exit(f"--lead title not found: {lead}")

    out_path = os.path.join(ROOT, "data", "editions", f"{date}.json")
    now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    if mode in ("refresh", "briefs"):
        with open(out_path, encoding="utf-8") as f:
            ed = json.load(f)
        ed.setdefault("briefs", [])
    if mode == "briefs":
        rnd, start = max(r["round"] for r in ed["rounds"]), len(ed["articles"]) + 1
    elif mode == "refresh":
        rnd = max(r["round"] for r in ed["rounds"]) + 1
        start = len(ed["articles"]) + 1
        ed["rounds"].append({"round": rnd, "mode": "refresh", "generated_at": now})
        if changes:
            ed["changes"] = list(ed.get("changes") or []) + changes
    else:
        rnd, start = 1, 1
        ed = {"date": date, "generated_at": now, "changes": changes or [],
              "rounds": [{"round": 1, "mode": "daily", "generated_at": now}],
              "articles": [], "briefs": [], "run": {"mode": "daily", "duration_minutes": 0, "fetches": 0, "notes": []}}
    for i, a in enumerate(new):
        ed["articles"].append({"id": f"a{start + i:02d}", "round": rnd, **a})
    seen = {b["title"].strip().lower() for b in ed["briefs"]} | {a["title"].strip().lower() for a in ed["articles"]}
    bstart = len(ed["briefs"]) + 1
    added = 0
    for b in briefs:
        if b["title"].strip().lower() in seen:
            continue
        seen.add(b["title"].strip().lower())
        ed["briefs"].append({"id": f"b{bstart + added:02d}", "round": rnd, **b})
        added += 1
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(ed, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_path}: {len(new)} new article(s) and {added} brief(s) in round {rnd}; "
          f"{len(ed['articles'])} articles and {len(ed['briefs'])} briefs in total")


if __name__ == "__main__":
    main()
