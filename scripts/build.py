#!/usr/bin/env python3
"""Build the viewer pages for one edition.

Usage:
  python3 scripts/build.py YYYY-MM-DD                 # writes dist/live.html and dist/offline-YYYY-MM-DD.html
  python3 scripts/build.py YYYY-MM-DD --email-body    # prints the email HTML body to stdout

live.html is the claude.ai Artifact page (no doctype: the Artifact tool adds the skeleton).
offline-*.html is a complete standalone document for the email attachment.
"""
import glob
import html
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOPIC_LABELS = {
    "industry": "Industry", "uk_politics": "UK Politics", "ukraine": "Ukraine War", "nato": "NATO & Defence",
    "china": "China", "ai": "AI in Practice", "us_politics": "US Politics", "wildcard": "Wildcard",
}


def p(*parts):
    return os.path.join(ROOT, *parts)


def read(path, default=""):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return default


def load_edition(date):
    with open(p("data", "editions", f"{date}.json"), encoding="utf-8") as f:
        return json.load(f)


def archive_for(date, days):
    files = sorted(glob.glob(p("data", "editions", "*.json")), reverse=True)
    older = [f for f in files if os.path.basename(f)[:10] < date][: max(0, days - 1)]
    out = []
    for f in older:
        with open(f, encoding="utf-8") as fh:
            out.append(json.load(fh))
    return out


def payload(date, mode, config):
    ed = load_edition(date)
    issue = len([f for f in glob.glob(p("data", "editions", "*.json")) if os.path.basename(f)[:10] <= date])
    data = {
        "mode": mode,
        "edition": ed,
        "archive": archive_for(date, config.get("archive_days", 7)) if mode == "live" else [],
        "issue_number": issue,
        "learned": read(p("profile", "learned.md")),
        "standing": read(p("profile", "standing-instructions.md")),
        "stats": json.loads(read(p("data", "stats.json"), "{}") or "{}"),
        "trigger_id": config.get("routine_trigger_id"),
        "viewer_url": config.get("viewer_artifact_url"),
    }
    # Escape "</" so article text can never close the <script> tag.
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def render(date, mode, config):
    template = read(p("viewer", "template.html"))
    if "__BRIEF_DATA__" not in template:
        sys.exit("template.html is missing the __BRIEF_DATA__ placeholder")
    return template.replace("__BRIEF_DATA__", payload(date, mode, config))


def offline_document(body):
    head = ('<!doctype html><html lang="en-GB"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            "<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
            "body{margin:0;font:14px system-ui,sans-serif}img{max-width:100%}[hidden]{display:none!important}</style>"
            "</head><body>")
    return head + body + "</body></html>"


def email_body(date, config):
    ed = load_edition(date)
    e = html.escape
    mins = sum(a["read_minutes"] for a in ed["articles"])
    url = config.get("viewer_artifact_url")
    out = ['<div style="font-family:Georgia,serif;max-width:640px;margin:0 auto;color:#161b2e;line-height:1.5">',
           '<div style="background:#1d2a4d;color:#eef0f7;padding:18px 20px;border-bottom:3px solid #c8611e">',
           '<div style="font:700 12px Arial,sans-serif;letter-spacing:.14em;text-transform:uppercase;color:#aab3d1">Daily <span style="color:#c8611e">Brief</span></div>',
           f'<div style="font:700 26px Arial,sans-serif;margin-top:6px">{e(ed["date"])}</div>',
           f'<div style="font:13px monospace;color:#aab3d1;margin-top:4px">{len(ed["articles"])} articles · {mins} min reading</div></div>',
           '<div style="padding:16px 20px">']
    if url:
        out.append(f'<p style="font:600 14px Arial,sans-serif"><a href="{e(url)}" style="color:#c8611e">Open the live brief to read and rate</a>. '
                   'The attached file works offline.</p>')
    else:
        out.append('<p style="font:600 14px Arial,sans-serif">The attached file has every article and works offline.</p>')
    if ed.get("changes"):
        out.append('<div style="border-left:3px solid #c8611e;padding:6px 12px;margin:12px 0;background:#fbeee3">'
                   '<b style="font:700 12px Arial,sans-serif;text-transform:uppercase;letter-spacing:.08em;color:#c8611e">Changed because of your feedback</b><ul style="margin:4px 0 0;padding-left:18px">')
        out += [f"<li>{e(c)}</li>" for c in ed["changes"]]
        out.append("</ul></div>")
    current = None
    for a in ed["articles"]:
        if a["topic"] != current:
            current = a["topic"]
            out.append(f'<h3 style="font:700 12px Arial,sans-serif;text-transform:uppercase;letter-spacing:.1em;color:#7a8098;margin:22px 0 6px;border-bottom:1px solid #dfe2ea;padding-bottom:4px">{e(TOPIC_LABELS.get(current, current))}</h3>')
        kind = "" if a["kind"] == "news" else f' <span style="font:11px Arial,sans-serif;color:#c8611e">{"OPINION" if a["kind"] == "opinion" else "ANALYSIS"}</span>'
        out.append(f'<div style="margin:10px 0 14px"><div style="font:700 17px Arial,sans-serif;line-height:1.25">{e(a["title"])}{kind}</div>'
                   f'<div style="font:12px monospace;color:#7a8098">{a["read_minutes"]} min</div>'
                   '<ul style="margin:4px 0 0;padding-left:18px;color:#4a5068">' + "".join(f"<li>{e(t)}</li>" for t in a["tldr"]) + "</ul></div>")
    out.append("</div></div>")
    return "".join(out)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        sys.exit(2)
    date = args[0]
    config = json.loads(read(p("config.json"), "{}"))
    if "--email-body" in sys.argv:
        print(email_body(date, config))
        return
    os.makedirs(p("dist"), exist_ok=True)
    with open(p("dist", "live.html"), "w", encoding="utf-8") as f:
        f.write(render(date, "live", config))
    with open(p("dist", f"offline-{date}.html"), "w", encoding="utf-8") as f:
        f.write(offline_document(render(date, "offline", config)))
    print(f"Built dist/live.html and dist/offline-{date}.html")


if __name__ == "__main__":
    main()
