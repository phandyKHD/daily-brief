#!/usr/bin/env python3
"""Multi-reader newsroom helpers. Run from the repo root.

  python3 scripts/newsroom.py prepare <reader>            make work/<reader>/ and its config.json
  python3 scripts/newsroom.py plan                        shared desk plan from every reader's setup
  python3 scripts/newsroom.py merge-pool                  dist/pool/desk-*.json -> pool.json + index.txt
  python3 scripts/newsroom.py select <reader> <sel.json>  build work/<reader>/dist/desk-edition.json
  python3 scripts/newsroom.py files <reader> <date>       the `files` list for the Artifact publish

Shared topics (from topics.json) are researched once into dist/pool/. Personal topics
are researched per reader into work/<reader>/dist/desk-personal-*.json. Each reader's
editor picks from the pool with a small selection file:

  {"lead": "P004",
   "articles": [{"id": "P004", "why_it_matters": "…or null"}, …],
   "briefs": ["B012", "B013", …],
   "changes": ["sentence", …]}

and `select` writes the reader's desk file (pool picks + all their personal desk output),
ready for assemble_edition.py.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

C = common.code
POOL = C("dist", "pool")


def readers(active_only=True):
    regs = common.load_json(C("readers.json"), {"readers": []})["readers"]
    return [r for r in regs if r.get("active", True) or not active_only]


def reader(rid):
    for r in readers(False):
        if r["id"] == rid:
            return r
    sys.exit(f"Unknown reader {rid}; see readers.json")


def work(rid, *parts):
    return C("work", rid, *parts)


def prepare(rid):
    r = reader(rid)
    cfg = common.load_json(C("config.json"), {})
    os.makedirs(work(rid, "dist"), exist_ok=True)
    os.makedirs(work(rid, "export"), exist_ok=True)
    conf = {
        "reader_id": rid,
        "reader_name": r.get("name"),
        "viewer_artifact_url": r["artifact_url"],
        "routine_trigger_id": cfg.get("refresh_trigger_id"),
        "recipient": r.get("email") if r.get("send_email") else None,
        "archive_days": 7,
    }
    with open(work(rid, "config.json"), "w", encoding="utf-8") as f:
        json.dump(conf, f, indent=2)
    print(f"work/{rid}/ ready. Export folder: {work(rid, 'export')}")


def setups():
    out = {}
    for r in readers():
        s = common.load_json(work(r["id"], "profile", "setup.json"))
        if s:
            out[r["id"]] = s
    return out


def plan():
    lib = {t["id"]: t for t in common.library()}
    shared, personal = {}, []
    for rid, s in setups().items():
        for t in s.get("topics", []):
            n = int(t.get("count") or 0)
            if not n:
                continue
            if t.get("personal") or t["id"] not in lib:
                personal.append((rid, t))
                continue
            e = shared.setdefault(t["id"], {"count": 0, "readers": [], "angles": []})
            e["count"] = max(e["count"], n)
            e["readers"].append(rid)
            if t.get("angle"):
                e["angles"].append(f"{rid}: {t['angle']}")
    print("SHARED DESKS (research once; write one more article than the largest quota so editors can choose):")
    for tid, e in shared.items():
        lt = lib[tid]
        cap = lt.get("max")
        n = e["count"] + 1 if not cap else min(e["count"] + 1, cap)
        print(f"- {tid} ({lt['label']}): {n} articles, ~{max(6, 3 * len(e['readers']) + 3)} briefs, lookback {lt.get('lookback_hours', 36)}h; "
              f"readers {', '.join(e['readers'])}" + (f"; angles: {' | '.join(e['angles'])}" if e["angles"] else ""))
    print("\nPERSONAL DESKS (one per reader topic; write to work/<reader>/dist/desk-personal-<topic>.json):")
    for rid, t in personal:
        print(f"- {rid} / {t['id']} ({t.get('label')}): {t['count']} articles + ~6 briefs, lookback {t.get('lookback_hours', 72)}h. "
              f"Brief: {t.get('description', '').strip()}")
    missing = [r["id"] for r in readers() if r["id"] not in setups()]
    if missing:
        print(f"\nNO SETUP YET (skip, keep their placeholder page): {', '.join(missing)}")


def merge_pool():
    arts, briefs = [], []
    for path in sorted(glob.glob(os.path.join(POOL, "desk-*.json"))):
        doc = common.load_json(path, {})
        arts += doc.get("articles", []) if isinstance(doc, dict) else doc
        briefs += doc.get("briefs", []) if isinstance(doc, dict) else []
    for i, a in enumerate(arts, 1):
        a["pool_id"] = f"P{i:03d}"
    for i, b in enumerate(briefs, 1):
        b["pool_id"] = f"B{i:03d}"
    with open(os.path.join(POOL, "pool.json"), "w", encoding="utf-8") as f:
        json.dump({"articles": arts, "briefs": briefs}, f, indent=1, ensure_ascii=False)
    lines = ["ARTICLES"]
    for a in arts:
        lines.append(f"{a['pool_id']} [{a['topic']}] {a['title']} ({a.get('read_minutes')} min, {a.get('kind')}) | tags: {', '.join(a.get('tags', []))}")
        lines.append(f"     tl;dr: {' / '.join(a.get('tldr', []))}")
    lines.append("\nBRIEFS")
    for b in briefs:
        lines.append(f"{b['pool_id']} [{b['topic']}] {b['title']}")
    with open(os.path.join(POOL, "index.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Pool: {len(arts)} articles, {len(briefs)} briefs -> dist/pool/pool.json and dist/pool/index.txt")


def select(rid, sel_path):
    pool = common.load_json(os.path.join(POOL, "pool.json"), {"articles": [], "briefs": []})
    sel = common.load_json(sel_path)
    if sel is None:
        sys.exit(f"Cannot read {sel_path}")
    pa = {a["pool_id"]: a for a in pool["articles"]}
    pb = {b["pool_id"]: b for b in pool["briefs"]}
    arts, briefs, lead = [], [], None
    for pick in sel.get("articles", []):
        a = dict(pa[pick["id"]])
        if "why_it_matters" in pick:
            a["why_it_matters"] = pick["why_it_matters"]
        a.pop("pool_id", None)
        arts.append(a)
        if pick["id"] == sel.get("lead"):
            lead = a["title"]
    for bid in sel.get("briefs", []):
        b = dict(pb[bid])
        b.pop("pool_id", None)
        briefs.append(b)
    with open(work(rid, "dist", "desk-edition.json"), "w", encoding="utf-8") as f:
        json.dump({"articles": arts, "briefs": briefs}, f, indent=1, ensure_ascii=False)
    personal = glob.glob(work(rid, "dist", "desk-personal-*.json"))
    np = sum(len((common.load_json(p, {}) or {}).get("articles", [])) for p in personal)
    print(f"{rid}: {len(arts)} pool articles + {np} personal articles, {len(briefs)} pool briefs")
    if not lead and sel.get("lead") and sel["lead"] not in pa:
        lead = sel["lead"]  # a personal-desk article, given by its exact title
    if lead:
        print(f"LEAD: {lead}")
    for c in sel.get("changes", []):
        print(f"CHANGE: {c}")


def files(rid, date):
    out = [{"path": f"editions/{date}.json"}]
    pdf_dir = work(rid, "dist", "pdf", date)
    for p in sorted(glob.glob(os.path.join(pdf_dir, "*.pdf"))):
        out.append({"path": f"pdf/{date}/{os.path.basename(p)}"})
    # Publish the edition JSON from the working folder alongside the PDFs.
    os.makedirs(work(rid, "dist", "editions"), exist_ok=True)
    src = work(rid, "data", "editions", f"{date}.json")
    if os.path.exists(src):
        with open(src, encoding="utf-8") as f, open(work(rid, "dist", "editions", f"{date}.json"), "w", encoding="utf-8") as g:
            g.write(f.read())
    print(json.dumps(out))
    print(f"(root: {work(rid, 'dist')})")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["prepare"] and len(a) == 2:
        prepare(a[1])
    elif a == ["plan"]:
        plan()
    elif a == ["merge-pool"]:
        merge_pool()
    elif a[:1] == ["select"] and len(a) == 3:
        select(a[1], a[2])
    elif a[:1] == ["files"] and len(a) == 3:
        files(a[1], a[2])
    else:
        print(__doc__)
        sys.exit(2)
