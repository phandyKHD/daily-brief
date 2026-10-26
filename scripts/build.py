#!/usr/bin/env python3
"""Build the viewer pages for one edition.

Usage:
  python3 scripts/build.py YYYY-MM-DD                 # writes dist/live.html and dist/offline-YYYY-MM-DD.html
  python3 scripts/build.py YYYY-MM-DD --email-body    # prints the email HTML body to stdout
  python3 scripts/build.py YYYY-MM-DD --placeholder   # page for a new reader: Setup tab, no edition

live.html is the claude.ai Artifact page (no doctype: the Artifact tool adds the skeleton).
offline-*.html is a complete standalone document for the email attachment.
"""
import glob
import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import geo  # noqa: E402

ROOT = common.HOME
TOPIC_LABELS = common.labels()


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


def payload(date, mode, config, placeholder=False):
    ed = ({"date": date, "placeholder": True, "generated_at": None, "changes": [], "rounds": [{"round": 1, "mode": "daily"}],
           "articles": [], "briefs": [], "run": {}} if placeholder else load_edition(date))
    setup = common.setup()
    geo.attach(ed)
    issue = len([f for f in glob.glob(p("data", "editions", "*.json")) if os.path.basename(f)[:10] <= date])
    data = {
        "mode": mode,
        "edition": ed,
        "archive": [geo.attach(e) for e in archive_for(date, config.get("archive_days", 7))] if mode == "live" else [],
        "issue_number": issue,
        "learned": read(p("profile", "learned.md")),
        "standing": read(p("profile", "standing-instructions.md")),
        "stats": json.loads(read(p("data", "stats.json"), "{}") or "{}"),
        "trigger_id": config.get("routine_trigger_id"),
        "viewer_url": config.get("viewer_artifact_url"),
        "reader_id": config.get("reader_id"),
        "reader_name": (setup or {}).get("name") or config.get("reader_name"),
        "topics": common.topic_meta(),
        "library": common.library(),
        "setup": setup,
        "has_setup": bool(setup),
    }
    # Escape "</" so article text can never close the <script> tag.
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def render(date, mode, config, placeholder=False):
    template = read(common.code("viewer", "template.html"))
    if "__BRIEF_DATA__" not in template:
        sys.exit("template.html is missing the __BRIEF_DATA__ placeholder")
    return template.replace("__BRIEF_DATA__", payload(date, mode, config, placeholder))


def offline_document(body):
    head = ('<!doctype html><html lang="en-GB"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            "<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
            "body{margin:0;font:14px system-ui,sans-serif}img{max-width:100%}[hidden]{display:none!important}</style>"
            "</head><body>")
    return head + body + "</body></html>"


def fmt_num(v, vis):
    if isinstance(v, str):
        return v
    d = vis.get("decimals")
    if d is None:
        d = 1 if (v % 1 and abs(v) < 10) else 0
    return ("−" if v < 0 else "") + (vis.get("prefix") or "") + f"{abs(v):,.{d}f}" + (vis.get("unit") or "")


def email_figure(vis):
    """Charts as plain HTML tables: mail apps strip SVG and scripts."""
    e = html.escape
    out = ['<div style="border-top:1px solid #dfe2ea;border-bottom:1px solid #dfe2ea;padding:10px 0;margin:12px 0">',
           f'<div style="font:700 14px Arial,sans-serif">{e(vis["title"])}</div>']
    if vis.get("note"):
        out.append(f'<div style="font:13px Arial,sans-serif;color:#4a5068">{e(vis["note"])}</div>')
    if vis["type"] == "map":
        out.append('<ol style="margin:6px 0 0;padding-left:20px;font:13px Arial,sans-serif">' + "".join(
            f'<li><b>{e(p["label"])}</b>{(" – " + e(p["detail"])) if p.get("detail") else ""}</li>' for p in vis["points"]) + "</ol>")
        out.append(f'<div style="font:11px Arial,sans-serif;color:#7a8098;margin-top:4px">Map in the live brief. Source: {e(vis["source"])}</div></div>')
        return "".join(out)
    if vis["type"] == "stats":
        out.append('<table cellpadding="0" cellspacing="6" style="width:100%"><tr>' + "".join(
            f'<td style="background:#f4f5f8;padding:8px 10px;vertical-align:top"><div style="font:700 20px Arial,sans-serif">{e(fmt_num(d["value"], vis))}</div>'
            f'<div style="font:12px Arial,sans-serif;color:#4a5068">{e(d["label"])}</div></td>' for d in vis["data"]) + "</tr></table>")
    else:
        # Line charts become a compact bar list too: every value stays readable without images.
        top = max(abs(d["value"]) for d in vis["data"]) or 1
        out.append('<table cellpadding="0" cellspacing="0" style="width:100%;margin-top:6px;font:12px Arial,sans-serif">')
        for d in vis["data"]:
            pct = max(1, round(abs(d["value"]) / top * 100))
            colour = "#c8611e" if vis.get("highlight") == d["label"] else "#2c4f9e"
            out.append(f'<tr><td style="width:34%;padding:3px 8px 3px 0;color:#4a5068">{e(d["label"])}</td>'
                       f'<td style="padding:3px 0"><div style="background:{colour};height:12px;width:{pct}%;border-radius:0 3px 3px 0"></div></td>'
                       f'<td style="width:70px;padding:3px 0 3px 8px;font-weight:700;white-space:nowrap">{e(fmt_num(d["value"], vis))}</td></tr>')
        out.append("</table>")
    out.append(f'<div style="font:11px Arial,sans-serif;color:#7a8098;margin-top:4px">Source: {e(vis["source"])}</div></div>')
    return "".join(out)


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
                   'Headlines and key points below. For the full articles offline, tap <b>Save edition as PDF</b> in the live brief.</p>')
    else:
        out.append('<p style="font:600 14px Arial,sans-serif">Headlines and key points below; full articles are in the live brief.</p>')
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
        out.append(f'<div style="margin:10px 0 14px"><a href="#{a["id"]}" style="font:700 16px Arial,sans-serif;line-height:1.25;color:#161b2e;text-decoration:none">{e(a["title"])}</a>{kind}'
                   f' <span style="font:12px monospace;color:#7a8098">{a["read_minutes"]} min</span>'
                   '<ul style="margin:4px 0 0;padding-left:18px;color:#4a5068;font-size:15px">' + "".join(f"<li>{e(t)}</li>" for t in a["tldr"]) + "</ul></div>")
    # Full article text is no longer included: a 120 KB body took two hours to send
    # through the Gmail tool. Offline reading uses "Save edition as PDF" in the brief.
    if ed.get("briefs"):
        out.append('<h2 style="font:800 13px Arial,sans-serif;text-transform:uppercase;letter-spacing:.14em;color:#c8611e;margin:34px 0 4px;border-top:3px solid #c8611e;padding-top:10px">'
                   f'More stories ({len(ed["briefs"])})</h2>')
        out.append('<p style="font:13px Arial,sans-serif;color:#4a5068;margin:0 0 8px">Headlines only. Summaries are in the live brief and the edition PDF; press "Write this up" there on any you want in full.</p>')
        current = None
        for b in ed["briefs"]:
            if b["topic"] != current:
                current = b["topic"]
                out.append(f'<h3 style="font:700 11px Arial,sans-serif;text-transform:uppercase;letter-spacing:.1em;color:#7a8098;margin:16px 0 4px">{e(TOPIC_LABELS.get(current, current))}</h3>')
            src = " · ".join(f'<a href="{e(x["url"])}" style="color:#7a8098">{e(x["outlet"])}</a>' for x in b["sources"])
            # Headlines only: keeps the email small enough to send reliably. Summaries are in the live brief and PDF.
            out.append(f'<div style="margin:3px 0;font:14px Arial,sans-serif">• {e(b["title"])} <span style="font-size:11px">{src}</span></div>')
    if url:
        out.append(f'<p style="font:600 14px Arial,sans-serif;text-align:center"><a href="{e(url)}" style="color:#c8611e">Rate today\'s articles in the live brief</a></p>')
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
    if "--placeholder" in sys.argv:
        # A new reader with no edition yet: the page opens on the Setup tab.
        with open(p("dist", "live.html"), "w", encoding="utf-8") as f:
            f.write(render(date, "live", config, placeholder=True))
        print("Built dist/live.html (placeholder: Setup only)")
        return
    with open(p("dist", "live.html"), "w", encoding="utf-8") as f:
        f.write(render(date, "live", config))
    with open(p("dist", f"offline-{date}.html"), "w", encoding="utf-8") as f:
        f.write(offline_document(render(date, "offline", config)))
    print(f"Built dist/live.html and dist/offline-{date}.html")


if __name__ == "__main__":
    main()
