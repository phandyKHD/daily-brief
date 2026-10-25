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


def check_visual(v):
    errs = []
    if not isinstance(v, dict):
        return ["must be an object or null"]
    if v.get("type") not in ("bar", "line", "stats"):
        errs.append("type must be bar, line or stats")
    for f in ("title", "source"):
        if not (isinstance(v.get(f), str) and v[f].strip()):
            errs.append(f"needs a {f}")
    data = v.get("data")
    if not isinstance(data, list):
        return errs + ["data must be a list"]
    lo, hi = {"bar": (2, 10), "line": (4, 24), "stats": (1, 4)}.get(v.get("type"), (1, 24))
    if not lo <= len(data) <= hi:
        errs.append(f"{v.get('type')} needs {lo}-{hi} data points, has {len(data)}")
    for d in data:
        if not (isinstance(d, dict) and isinstance(d.get("label"), str) and d["label"].strip()):
            errs.append("every data point needs a label")
            break
        ok = isinstance(d.get("value"), (int, float)) and not isinstance(d.get("value"), bool)
        if v.get("type") == "stats":
            ok = ok or (isinstance(d.get("value"), str) and 0 < len(d["value"]) <= 12)
        if not ok:
            errs.append(f"bad value for '{d['label']}' (numbers only; stats may use a short string)")
    if v.get("highlight") and v["highlight"] not in [d.get("label") for d in data if isinstance(d, dict)]:
        errs.append("highlight must match a data label")
    return errs


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
        if a.get("visual") is not None:
            errors += [f"{where}: visual: {e}" for e in check_visual(a["visual"])]
        per_round_topic.setdefault(a["round"], {}).setdefault(a["topic"], 0)
        per_round_topic[a["round"]][a["topic"]] += 1

    seen_b = set()
    for i, b in enumerate(ed.get("briefs") or []):
        where = f"brief {b.get('id', i)}"
        missing = {"id", "round", "topic", "title", "summary", "sources", "tags"} - b.keys()
        if missing:
            errors.append(f"{where}: missing {sorted(missing)}")
            continue
        if not re.fullmatch(r"b\d{2,3}", b["id"]) or b["id"] in seen_b:
            errors.append(f"{where}: id must be unique and look like b01")
        seen_b.add(b["id"])
        if b["topic"] not in TOPICS:
            errors.append(f"{where}: unknown topic '{b['topic']}'")
        wc = len(str(b["summary"]).split())
        if not 20 <= wc <= 100:
            errors.append(f"{where}: summary is {wc} words (20-100)")
        if not (isinstance(b["sources"], list) and 1 <= len(b["sources"]) <= 3 and all(isinstance(x, dict) and x.get("outlet") and str(x.get("url", "")).startswith("http") for x in b["sources"])):
            errors.append(f"{where}: needs 1-3 sources with outlet and url")
        if b["title"].strip().lower() in seen_titles:
            errors.append(f"{where}: repeats a full article's title")
        if not (isinstance(b["tags"], list) and 1 <= len(b["tags"]) <= 6):
            errors.append(f"{where}: needs 1-6 tags")
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
    print(f"OK: {len(ed['articles'])} articles, {mins} min reading, {len(ed.get('briefs') or [])} briefs")


if __name__ == "__main__":
    main()
