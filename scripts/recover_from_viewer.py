#!/usr/bin/env python3
"""Recover editions and profile from the published viewer page.

Every published viewer embeds the current edition, the archive, learned.md,
standing-instructions.md and stats.json. If a run published the viewer but its
git push failed, this puts that state back into the repo.

Usage:
  1. Artifact read of config.viewer_artifact_url (the result names the saved HTML file)
  2. python3 scripts/recover_from_viewer.py <saved.html>

Only writes an edition when the page has a date the repo lacks, or more articles
for a date than the repo has. Profile files are replaced only when the page's
edition is at least as new as the newest edition in the repo.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

ROOT = common.HOME


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    html = open(sys.argv[1], encoding="utf-8").read()
    m = re.search(r'<script id="brief-data" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        sys.exit("No brief-data block found in that file.")
    data = json.loads(m.group(1).replace("<\\/", "</"))
    eds_dir = os.path.join(ROOT, "data", "editions")
    have = {os.path.basename(f)[:10]: f for f in glob.glob(os.path.join(eds_dir, "*.json"))}
    newest_repo = max(have) if have else ""
    changed = []
    for ed in [data["edition"]] + data.get("archive", []):
        path = os.path.join(eds_dir, f"{ed['date']}.json")
        if ed["date"] in have:
            with open(path, encoding="utf-8") as f:
                if len(json.load(f)["articles"]) >= len(ed["articles"]):
                    continue
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ed, f, indent=2, ensure_ascii=False)
        changed.append(f"data/editions/{ed['date']}.json")
    if data["edition"]["date"] >= newest_repo:
        for rel, text in (("profile/learned.md", data.get("learned")), ("profile/standing-instructions.md", data.get("standing"))):
            if text:
                p = os.path.join(ROOT, rel)
                if open(p, encoding="utf-8").read() != text:
                    open(p, "w", encoding="utf-8").write(text)
                    changed.append(rel)
        if data.get("stats"):
            p = os.path.join(ROOT, "data", "stats.json")
            new = json.dumps(data["stats"], indent=2, ensure_ascii=False)
            if open(p, encoding="utf-8").read() != new:
                open(p, "w", encoding="utf-8").write(new)
                changed.append("data/stats.json")
    print("Recovered: " + ", ".join(changed) if changed else "Nothing to recover: the repo is up to date with the viewer.")
    if changed:
        print("Re-run scripts/ingest_ratings.py after this so ratings.jsonl and feedback-log.md catch up.")


if __name__ == "__main__":
    main()
