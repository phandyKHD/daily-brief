#!/usr/bin/env python3
"""Move one reader's state between their brief (artifact) and a local working folder.

Each reader's brief keeps everything the agent needs, so runs never push to GitHub:
  db  profile/setup         what the reader asked for (written by the Setup tab)
  db  state/<stamp>         one document per run: learned, standing, feedback log, stats, meta
  db  ratings/*, requests/*, control/refresh   written by the page
  files editions/<date>.json                    past editions, published with the page

Usage (BRIEF_HOME=work/<reader>):
  python3 scripts/state.py unpack <export dir>   fill BRIEF_HOME from an export folder
  python3 scripts/state.py pack                  write dist/state-doc.json; prints its doc id
  python3 scripts/state.py init <setup.json>     start a brand-new reader folder

<export dir> is where the run saved ArtifactData / Artifact reads for this reader, e.g.
  <dir>/profile/setup.json      (ArtifactData get profile/setup, out_dir <dir>)
  <dir>/state/<id>.json         (ArtifactData query state, order_by saved_at desc, limit 1)
  <dir>/editions/<date>.json    (Artifact read paths editions/<date>.json, out_dir <dir>)
"""
import datetime as dt
import glob
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

H = common.home

LEARNED_TEMPLATE = """# What the agent has learned

Maintained by the morning agent. Each point cites the dates of the ratings or notes it is based on.

## Likes
- (nothing learned yet)

## Dislikes
- (nothing learned yet)

## Style and length
- (nothing learned yet)

## Leads to follow
- (nothing yet)
"""
STANDING_TEMPLATE = """# Standing instructions

Lasting preferences taken from the reader's own notes. These outrank everything else.
Format: `- YYYY-MM-DD: instruction (source: article title or "general")`

- (none yet)
"""


def write(rel, text):
    path = H(*rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def dump(rel, obj):
    write(rel, json.dumps(obj, indent=2, ensure_ascii=False))


def ensure_dirs():
    for d in ("profile", "data/editions", "dist"):
        os.makedirs(H(*d.split("/")), exist_ok=True)


def unpack(src):
    ensure_dirs()
    setup = common.load_json(os.path.join(src, "profile", "setup.json"))
    if setup:
        dump("profile/setup.json", setup.get("data", setup) if "data" in setup and isinstance(setup["data"], dict) else setup)
    states = []
    for f in glob.glob(os.path.join(src, "state", "*.json")):
        d = common.load_json(f, {})
        d = d.get("data", d) if isinstance(d.get("data"), dict) else d
        states.append(d)
    state = max(states, key=lambda d: d.get("saved_at", "")) if states else {}
    write("profile/learned.md", state.get("learned") or LEARNED_TEMPLATE)
    write("profile/standing-instructions.md", state.get("standing") or STANDING_TEMPLATE)
    write("data/feedback-log.md", state.get("feedback_log") or "# Feedback log\n")
    dump("data/stats.json", state.get("stats") or {"updated": None, "topics": {}, "tags": {}, "sources": {}, "read_time": {}, "quick_tags": {}})
    dump("profile/meta.json", state.get("meta") or {"last_ingest": ""})
    n = 0
    for f in glob.glob(os.path.join(src, "editions", "*.json")):
        shutil.copy(f, H("data", "editions", os.path.basename(f)))
        n += 1
    print(f"Unpacked into {common.HOME}: setup {'yes' if setup else 'MISSING'}, "
          f"state {'from ' + state.get('saved_at', '?') if state else 'new'}, {n} edition file(s)")
    if not setup:
        print("No setup yet: this reader has not filled in the Setup tab. Skip them this run.")


def pack():
    now = dt.datetime.now(dt.timezone.utc)
    read = lambda rel: open(H(*rel.split("/")), encoding="utf-8").read()
    log = read("data/feedback-log.md")
    # Keep the stored log bounded: the newest ~400 notes are plenty for learning.
    head, _, rest = log.partition("\n\n")
    lines = rest.splitlines()
    if len(lines) > 400:
        log = head + "\n\n" + "\n".join(lines[:400]) + "\n"
    doc = {
        "saved_at": now.isoformat(timespec="seconds"),
        "learned": read("profile/learned.md"),
        "standing": read("profile/standing-instructions.md"),
        "feedback_log": log,
        "stats": common.load_json(H("data", "stats.json"), {}),
        "meta": common.load_json(H("profile", "meta.json"), {}),
    }
    os.makedirs(H("dist"), exist_ok=True)
    with open(H("dist", "state-doc.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    size = os.path.getsize(H("dist", "state-doc.json"))
    doc_id = "s" + now.strftime("%Y%m%dT%H%M%S")
    print(f"{doc_id}  ({size // 1024} KB) -> ArtifactData set collection=state doc_id={doc_id} file_path={H('dist', 'state-doc.json')}")
    if size > 240 * 1024:
        print("WARNING: close to the 256 KB document limit; trim feedback_log or stats.tags")


def init(setup_path):
    ensure_dirs()
    setup = common.load_json(setup_path)
    if setup is None:
        sys.exit(f"Cannot read {setup_path}")
    dump("profile/setup.json", setup)
    write("profile/learned.md", LEARNED_TEMPLATE)
    write("profile/standing-instructions.md", STANDING_TEMPLATE)
    write("data/feedback-log.md", "# Feedback log\n")
    dump("data/stats.json", {"updated": None, "topics": {}, "tags": {}, "sources": {}, "read_time": {}, "quick_tags": {}})
    dump("profile/meta.json", {"last_ingest": ""})
    print(f"Initialised {common.HOME}")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "unpack" and len(sys.argv) == 3:
        unpack(sys.argv[2])
    elif sys.argv[1:] == ["pack"]:
        pack()
    elif len(sys.argv) == 3 and sys.argv[1] == "init":
        init(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(2)
