"""Shared paths for the Daily Brief scripts.

CODE is the repo (templates, topic library). HOME is one reader's working folder:
set BRIEF_HOME=work/<reader> to run a script for that reader. Without it, HOME is
the repo itself (the original single-reader layout).
"""
import json
import os

CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.abspath(os.environ.get("BRIEF_HOME") or CODE)

DEFAULT_TOPICS = [
    ("industry", "Industry"), ("uk_politics", "UK Politics"), ("ukraine", "Ukraine War"),
    ("nato", "NATO & Defence"), ("china", "China"), ("ai", "AI in Practice"),
    ("us_politics", "US Politics"), ("wildcard", "Wildcard"),
]


def home(*parts):
    return os.path.join(HOME, *parts)


def code(*parts):
    return os.path.join(CODE, *parts)


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def setup():
    """The reader's setup (written from the viewer's Setup tab), or None."""
    return load_json(home("profile", "setup.json"))


def topics():
    """Ordered [(id, label)] for this reader: their setup's topics, else the original list."""
    s = setup()
    if s and s.get("topics"):
        lib = {t["id"]: t for t in library()}
        out = []
        for t in s["topics"]:
            if not t.get("count", 1) and not t.get("personal"):
                continue
            label = t.get("label") or lib.get(t["id"], {}).get("label") or t["id"]
            out.append((t["id"], label))
        return out
    return list(DEFAULT_TOPICS)


def library():
    return load_json(code("topics.json"), {"topics": []})["topics"]


# Topic colours (light, dark). Library topics keep fixed colours; other topics
# take the next free colour in EXTRA, in the order they appear in the setup.
KNOWN_COLOURS = {
    "industry": ("#8a5a12", "#d9a65a"), "uk_politics": ("#6b3fa0", "#b994ea"), "ukraine": ("#2a6f86", "#6cc2db"),
    "nato": ("#2c4f9e", "#86a6f0"), "china": ("#b0322a", "#ef7a70"), "ai": ("#217a5b", "#62c99f"),
    "us_politics": ("#5e6372", "#a9aebd"), "wildcard": ("#a63d78", "#ea86bf"),
}
EXTRA_COLOURS = [("#9a4a14", "#f0a060"), ("#3d6b1f", "#9ccf6e"), ("#7a3a8c", "#cf94e0"), ("#1f6f6a", "#6fd0c8"),
                 ("#8c2f4f", "#ef8fae"), ("#5a5a14", "#cfcf6e"), ("#2f4f8c", "#8fb0ef"), ("#6b4a2a", "#d0a882")]


def topic_meta():
    """[{id, label, light, dark}] in reader order."""
    out, used = [], 0
    for tid, label in topics():
        if tid in KNOWN_COLOURS:
            light, dark = KNOWN_COLOURS[tid]
        else:
            light, dark = EXTRA_COLOURS[used % len(EXTRA_COLOURS)]
            used += 1
        out.append({"id": tid, "label": label, "light": light, "dark": dark})
    return out


def labels():
    return {t["id"]: t["label"] for t in topic_meta()}
