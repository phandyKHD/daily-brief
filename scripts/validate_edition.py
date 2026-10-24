#!/usr/bin/env python3
"""Validate an edition JSON file before it is built and published.

Usage: python3 scripts/validate_edition.py data/editions/YYYY-MM-DD.json [--check-links]
Exits 1 and prints every problem if the edition is invalid.
"""
import json
import re
import sys
import urllib.request

TOPICS = {"industry", "china", "nato", "ukraine", "uk_politics", "us_politics", "ai", "wildcard"}
KINDS = {"news", "analysis", "opinion"}
HARD_CAPS = {"us_politics": 2}
# Allowed body word counts per read_minutes (slightly wider than the desk brief targets).
WORD_RANGES = {2: (340, 560), 3: (520, 780), 4: (720, 1000)}
ARTICLE_FIELDS = {"id", "round", "topic", "title", "kind", "read_minutes", "tldr", "body",
                  "why_it_matters", "sources", "tags", "update_of"}


def word_count(paragraphs):
    return sum(len(p.split()) for p in paragraphs)


def check_link(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0 DailyBrief"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status < 400
    except urllib.error.HTTPError as e:
        # Many news sites refuse HEAD or bots (403/405) even though the page exists.
        return e.code in (401, 403, 405, 429)
    except Exception:
        return False


def validate(ed, check_links=False):
    errors, warnings = [], []
    for f in ("date", "generated_at", "changes", "rounds", "articles", "run"):
        if f not in ed:
            errors.append(f"edition: missing field '{f}'")
    if errors:
        return errors, warnings
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ed["date"]):
        errors.append("edition: date must be YYYY-MM-DD")
    if not isinstance(ed["changes"], list):
        errors.append("edition: changes must be a list")

    rounds = {r.get("round") for r in ed["rounds"]}
    seen_ids, seen_titles, per_round_topic = set(), set(), {}
    for i, a in enumerate(ed["articles"]):
        where = f"article {a.get('id', i)}"
        missing = ARTICLE_FIELDS - a.keys()
        if missing:
            errors.append(f"{where}: missing {sorted(missing)}")
            continue
        if not re.fullmatch(r"a\d{2,3}", a["id"]):
            errors.append(f"{where}: id must look like a01")
        if a["id"] in seen_ids:
            errors.append(f"{where}: duplicate id")
        seen_ids.add(a["id"])
        if a["round"] not in rounds:
            errors.append(f"{where}: round {a['round']} has no entry in rounds")
        if a["topic"] not in TOPICS:
            errors.append(f"{where}: unknown topic '{a['topic']}'")
        if a["kind"] not in KINDS:
            errors.append(f"{where}: kind must be one of {sorted(KINDS)}")
        if a["title"].strip().lower() in seen_titles:
            errors.append(f"{where}: duplicate title")
        seen_titles.add(a["title"].strip().lower())
        if not (isinstance(a["tldr"], list) and len(a["tldr"]) == 3 and all(isinstance(t, str) and t.strip() for t in a["tldr"])):
            errors.append(f"{where}: tldr must be exactly 3 non-empty strings")
        if not (isinstance(a["body"], list) and a["body"] and all(isinstance(p, str) for p in a["body"])):
            errors.append(f"{where}: body must be a non-empty list of strings")
        elif a["read_minutes"] not in WORD_RANGES:
            errors.append(f"{where}: read_minutes must be 2, 3 or 4")
        else:
            lo, hi = WORD_RANGES[a["read_minutes"]]
            wc = word_count(a["body"])
            if not lo <= wc <= hi:
                errors.append(f"{where}: {wc} words is outside {lo}-{hi} for a {a['read_minutes']}-minute read")
        if a["topic"] == "industry" and not a["why_it_matters"]:
            errors.append(f"{where}: industry articles need why_it_matters")
        srcs = a["sources"]
        if not isinstance(srcs, list) or len(srcs) < 2:
            errors.append(f"{where}: needs at least 2 sources")
        else:
            for s in srcs:
                if not (isinstance(s, dict) and s.get("outlet") and str(s.get("url", "")).startswith("http")):
                    errors.append(f"{where}: each source needs outlet and an http(s) url")
                elif check_links and not check_link(s["url"]):
                    warnings.append(f"{where}: link may be broken: {s['url']}")
            if len({s.get("url") for s in srcs if isinstance(s, dict)}) < len(srcs):
                errors.append(f"{where}: duplicate source urls")
        if not (isinstance(a["tags"], list) and 3 <= len(a["tags"]) <= 6):
            errors.append(f"{where}: needs 3-6 tags")
        elif any(t != t.lower() for t in a["tags"]):
            errors.append(f"{where}: tags must be lowercase")
        per_round_topic.setdefault(a["round"], {}).setdefault(a["topic"], 0)
        per_round_topic[a["round"]][a["topic"]] += 1

    totals = {}
    for counts in per_round_topic.values():
        for t, n in counts.items():
            totals[t] = totals.get(t, 0) + n
    for topic, cap in HARD_CAPS.items():
        if per_round_topic.get(1, {}).get(topic, 0) > cap:
            errors.append(f"edition: {topic} has {per_round_topic[1][topic]} articles in the morning edition; hard cap is {cap}")
    n1 = sum(per_round_topic.get(1, {}).values())
    if n1 and not 8 <= n1 <= 18:
        warnings.append(f"edition: morning edition has {n1} articles (target 12-16)")
    return errors, warnings


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        sys.exit(2)
    with open(args[0], encoding="utf-8") as f:
        ed = json.load(f)
    errors, warnings = validate(ed, check_links="--check-links" in sys.argv)
    for w in warnings:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        sys.exit(1)
    mins = sum(a["read_minutes"] for a in ed["articles"])
    print(f"OK: {len(ed['articles'])} articles, {mins} min reading")


if __name__ == "__main__":
    main()
