#!/usr/bin/env python3
"""Merge ratings exported from the viewer's Artifact database into the repo.

Usage: python3 scripts/ingest_ratings.py dist/ratings-export.json   (or a directory written by ArtifactData out_dir)

The export is a JSON array of {"id": "<date>_<articleId>", "data": {...}} objects
(the documents in the `ratings` collection; a bare list of rating bodies also works).

- Appends new or changed ratings to data/ratings.jsonl (append-only; the latest line per id wins)
- Adds new or changed notes to data/feedback-log.md
- Recomputes data/stats.json
- Prints a summary for the agent, including every new note in full
"""
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RATINGS = os.path.join(ROOT, "data", "ratings.jsonl")
FEEDBACK = os.path.join(ROOT, "data", "feedback-log.md")
STATS = os.path.join(ROOT, "data", "stats.json")
HALF_LIFE_DAYS = 7  # EWMA weight halves every 7 days, so ~14 days dominate
COMPARE = ("relevance", "quality", "summary_vote", "requested", "quick_tags", "feedback")
# A thumbs vote from the summary stands in for relevance when no stars were given.
VOTE_RELEVANCE = {"up": 4.0, "mid": 3.0, "down": 1.5}


def load_existing():
    latest = {}
    if os.path.exists(RATINGS):
        with open(RATINGS, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    latest[r["key"]] = r
    return latest


def normalise(doc):
    body = doc.get("data", doc) if isinstance(doc, dict) else {}
    key = doc.get("id") or f"{body.get('date')}_{body.get('article_id')}"
    r = dict(body)
    r["key"] = key
    r["relevance"] = int(r.get("relevance") or 0)
    r["quality"] = int(r.get("quality") or 0)
    v = r.get("summary_vote")
    r["summary_vote"] = {1: "up", -1: "down"}.get(v, v if v in VOTE_RELEVANCE else "")  # old ratings used 1 / -1
    r["quick_tags"] = sorted(r.get("quick_tags") or [])
    r["feedback"] = (r.get("feedback") or "").strip()
    return r


def is_empty(r):
    return not (r["relevance"] or r["quality"] or r.get("summary_vote") or r.get("requested") or r["quick_tags"] or r["feedback"])


def stats_from(latest, today):
    acc = {"topics": {}, "tags": {}, "sources": {}, "read_time": {}, "kind": {}}
    quick = {}

    def add(bucket, name, r, w):
        b = acc[bucket].setdefault(name, {"n": 0, "rel_sum": 0, "rel_n": 0, "q_sum": 0, "q_n": 0, "ew_sum": 0.0, "ew_w": 0.0})
        b["n"] += 1
        # Stars win; then a "Write this up" request (strongest signal); then a summary vote.
        rel = r["relevance"] or (4.5 if r.get("requested") else 0) or VOTE_RELEVANCE.get(r.get("summary_vote") or "", 0)
        if rel:
            b["rel_sum"] += rel; b["rel_n"] += 1
            b["ew_sum"] += rel * w; b["ew_w"] += w
        if r["quality"]:
            b["q_sum"] += r["quality"]; b["q_n"] += 1

    for r in latest.values():
        if is_empty(r):
            continue
        try:
            age = (today - dt.date.fromisoformat(r.get("date", ""))).days
        except ValueError:
            age = 0
        w = 0.5 ** (max(age, 0) / HALF_LIFE_DAYS)
        if r.get("topic"):
            add("topics", r["topic"], r, w)
        for t in r.get("tags") or []:
            add("tags", t, r, w)
        for o in set(r.get("outlets") or []):
            add("sources", o, r, w)
        if r.get("read_minutes"):
            add("read_time", str(r["read_minutes"]), r, w)
        if r.get("kind"):
            add("kind", r["kind"], r, w)
        for q in r["quick_tags"]:
            quick.setdefault(q, {"n": 0, "by_topic": {}})
            quick[q]["n"] += 1
            quick[q]["by_topic"][r.get("topic", "?")] = quick[q]["by_topic"].get(r.get("topic", "?"), 0) + 1

    out = {"updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "quick_tags": quick}
    for bucket, items in acc.items():
        out[bucket] = {}
        for name, b in sorted(items.items()):
            out[bucket][name] = {
                "n": b["n"],
                "avg_relevance": round(b["rel_sum"] / b["rel_n"], 2) if b["rel_n"] else None,
                "avg_quality": round(b["q_sum"] / b["q_n"], 2) if b["q_n"] else None,
                "ewma_relevance": round(b["ew_sum"] / b["ew_w"], 2) if b["ew_w"] else None,
            }
    return out


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    src = sys.argv[1]
    if os.path.isdir(src):
        # ArtifactData read with out_dir: one JSON file per document, named <doc_id>.json
        raw = []
        for root, _, files in os.walk(src):
            for name in sorted(files):
                if name.endswith(".json"):
                    with open(os.path.join(root, name), encoding="utf-8") as f:
                        d = json.load(f)
                    if "data" not in d or not isinstance(d["data"], dict):
                        d = {"data": d}
                    d.setdefault("id", name[:-5])
                    raw.append(d)
    else:
        with open(src, encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            raw = raw.get("docs") or raw.get("documents") or raw.get("items") or []
    latest = load_existing()
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    new, changed, notes = 0, 0, []
    appended = []
    for doc in raw:
        r = normalise(doc)
        if is_empty(r) and r["key"] not in latest:
            continue
        prev = latest.get(r["key"])
        if prev and all(prev.get(c) == r.get(c) for c in COMPARE):
            continue
        if prev:
            changed += 1
        else:
            new += 1
        if r["feedback"] and (not prev or prev.get("feedback") != r["feedback"]):
            notes.append(r)
        r["ingested_at"] = now
        latest[r["key"]] = r
        appended.append(r)

    if appended:
        with open(RATINGS, "a", encoding="utf-8") as f:
            for r in appended:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if notes:
        existing = open(FEEDBACK, encoding="utf-8").read() if os.path.exists(FEEDBACK) else "# Feedback log\n"
        head, _, rest = existing.partition("\n\n")
        block = "\n".join(
            f"- **{r.get('date')}** · {r.get('topic')} · \"{r.get('title')}\" (R{r['relevance'] or '-'} Q{r['quality'] or '-'}): {r['feedback']}"
            for r in notes)
        with open(FEEDBACK, "w", encoding="utf-8") as f:
            f.write(head + "\n\n" + block + ("\n" + rest if rest else "\n"))

    today = dt.date.today()
    stats = stats_from(latest, today)
    with open(STATS, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    print(f"Ingested {new} new and {changed} changed ratings ({len(latest)} total).")
    for name, s in stats["topics"].items():
        print(f"  topic {name:12s} n={s['n']:3d} rel={s['avg_relevance']} q={s['avg_quality']} ewma={s['ewma_relevance']}")
    votes = {k: sum(1 for r in latest.values() if r.get("summary_vote") == k) for k in VOTE_RELEVANCE}
    if any(votes.values()):
        print(f"  summary votes: {votes['up']} up, {votes['mid']} OK, {votes['down']} down (counted as relevance 4 / 3 / 1.5 where no stars were given)")
    if stats["quick_tags"]:
        print("  quick tags:", ", ".join(f"{k}×{v['n']}" for k, v in stats["quick_tags"].items()))
    if notes:
        print(f"\n{len(notes)} new note(s) from Peter. Read every one:")
        for r in notes:
            print(f"- [{r.get('date')} {r.get('topic')}] \"{r.get('title')}\" R{r['relevance'] or '-'} Q{r['quality'] or '-'}: {r['feedback']}")
    else:
        print("No new notes.")


if __name__ == "__main__":
    main()
