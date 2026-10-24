#!/usr/bin/env python3
"""Make PDFs for one edition with reportlab (preinstalled in the cloud image).

Usage: python3 scripts/make_pdf.py YYYY-MM-DD

Writes:
  dist/pdf/YYYY-MM-DD/daily-brief-YYYY-MM-DD.pdf   whole edition (email attachment)
  dist/pdf/YYYY-MM-DD/<articleId>.pdf             one per article (Share → Save PDF in the viewer)

Uses the PDF standard fonts (Helvetica, Times) so nothing is embedded and files stay
small enough to pass through the Gmail tool as base64.
"""
import datetime as dt
import json
import os
import sys

from reportlab import rl_config
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, KeepTogether, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rl_config.useA85 = 0  # binary Flate streams: about 20% smaller than ASCII85
INK, INK2, INK3 = HexColor("#161b2e"), HexColor("#4a5068"), HexColor("#7a8098")
SKY, SKY2, ACCENT, ACCENT_SOFT, RULE = HexColor("#1d2a4d"), HexColor("#aab3d1"), HexColor("#c8611e"), HexColor("#fbeee3"), HexColor("#dfe2ea")
TOPIC = {
    "industry": ("Industry", "#8a5a12"), "uk_politics": ("UK Politics", "#6b3fa0"), "ukraine": ("Ukraine War", "#2a6f86"),
    "nato": ("NATO & Defence", "#2c4f9e"), "china": ("China", "#b0322a"), "ai": ("AI in Practice", "#217a5b"),
    "us_politics": ("US Politics", "#5e6372"), "wildcard": ("Wildcard", "#a63d78"),
}
# Characters outside the standard fonts' WinAnsi set, mapped to safe equivalents.
SAFE = {"≈": "~", "→": "->", "←": "<-", "−": "-", " ": " ", " ": " ", "‑": "-",
        "′": "'", "″": '"', "≤": "<=", "≥": ">=", "×": "x"}

S = {
    "topic": ParagraphStyle("topic", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=INK3),
    "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=16, leading=19.5, textColor=INK, spaceBefore=3, spaceAfter=4),
    "meta": ParagraphStyle("meta", fontName="Helvetica", fontSize=8.5, leading=11, textColor=INK3, spaceAfter=6),
    "tldr": ParagraphStyle("tldr", fontName="Helvetica", fontSize=9.5, leading=13, textColor=INK2, leftIndent=10, bulletIndent=0),
    "body": ParagraphStyle("body", fontName="Times-Roman", fontSize=11, leading=15.2, textColor=INK, spaceAfter=6.5, alignment=TA_LEFT),
    "whyh": ParagraphStyle("whyh", fontName="Helvetica-Bold", fontSize=7.5, leading=10, textColor=ACCENT),
    "why": ParagraphStyle("why", fontName="Times-Roman", fontSize=10.5, leading=14, textColor=INK),
    "srch": ParagraphStyle("srch", fontName="Helvetica-Bold", fontSize=7.5, leading=10, textColor=INK3, spaceBefore=6, spaceAfter=2),
    "src": ParagraphStyle("src", fontName="Helvetica", fontSize=8.5, leading=11.5, textColor=INK2),
    "toch": ParagraphStyle("toch", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=INK3, spaceBefore=8, spaceAfter=2),
    "toc": ParagraphStyle("toc", fontName="Helvetica-Bold", fontSize=10.5, leading=13.5, textColor=INK, leftIndent=0),
    "tocsub": ParagraphStyle("tocsub", fontName="Helvetica", fontSize=8.5, leading=11, textColor=INK3, spaceAfter=4),
    "changes": ParagraphStyle("changes", fontName="Helvetica", fontSize=9.5, leading=13, textColor=INK),
}


def clean(text):
    text = "".join(SAFE.get(c, c) for c in str(text))
    text = text.encode("cp1252", "replace").decode("cp1252").replace("?", "?")
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt_date(iso, long=True):
    d = dt.date.fromisoformat(iso)
    return d.strftime("%A %-d %B %Y") if long else d.strftime("%a %-d %b")


def article_flowables(a):
    label, colour = TOPIC.get(a["topic"], (a["topic"], "#7a8098"))
    kind = {"opinion": "  ·  OPINION", "analysis": "  ·  ANALYSIS"}.get(a["kind"], "")
    out = [Paragraph(f'<a name="{a["id"]}"/><font color="{colour}">■</font> <font color="{colour}">{clean(label.upper())}</font>{kind}', S["topic"]),
           Paragraph(clean(a["title"]), S["title"])]
    meta = f'{a["read_minutes"]} min read'
    if a.get("update_of"):
        meta += f'  ·  Update to: {clean(a["update_of"])}'
    out.append(Paragraph(meta, S["meta"]))
    tl = Table([[Paragraph(clean(t), S["tldr"], bulletText="•")] for t in a["tldr"]], colWidths=["100%"])
    tl.setStyle(TableStyle([("LINEBEFORE", (0, 0), (0, -1), 2, ACCENT), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                            ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    out += [tl, Spacer(1, 8)]
    out += [Paragraph(clean(p), S["body"]) for p in a["body"]]
    if a.get("why_it_matters"):
        head = "WHY IT MATTERS FOR KHD" if a["topic"] == "industry" else "WHY IT MATTERS"
        box = Table([[Paragraph(head, S["whyh"])], [Paragraph(clean(a["why_it_matters"]), S["why"])]], colWidths=["100%"])
        box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT_SOFT), ("LEFTPADDING", (0, 0), (-1, -1), 9),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (0, 0), 7),
                                 ("BOTTOMPADDING", (0, -1), (-1, -1), 8), ("TOPPADDING", (0, 1), (-1, -1), 1)]))
        out += [Spacer(1, 2), box]
    srcs = [Paragraph("SOURCES", S["srch"])]
    for s in a["sources"]:
        title = clean(s.get("title") or s["url"])
        srcs.append(Paragraph(f'<b>{clean(s["outlet"])}</b>  <link href="{clean(s["url"])}" color="#4a5068"><u>{title}</u></link>', S["src"]))
    out.append(KeepTogether(srcs))
    return out


class Doc(BaseDocTemplate):
    def __init__(self, path, date, subtitle):
        super().__init__(path, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=34 * mm, bottomMargin=18 * mm,
                         title=f"Daily Brief {date}", author="Daily Brief", pageCompression=1)
        self.date, self.subtitle = date, subtitle
        w, h = A4
        first = Frame(self.leftMargin, self.bottomMargin, w - 40 * mm, h - 46 * mm - self.bottomMargin, id="first")
        later = Frame(self.leftMargin, self.bottomMargin, w - 40 * mm, h - 20 * mm - self.bottomMargin, id="later")
        self.addPageTemplates([PageTemplate("first", [first], onPage=self.first_page, autoNextPageTemplate="later"),
                               PageTemplate("later", [later], onPage=self.later_page)])

    def first_page(self, c, doc):
        w, h = A4
        c.saveState()
        c.setFillColor(SKY)
        c.rect(0, h - 38 * mm, w, 38 * mm, stroke=0, fill=1)
        c.setFillColor(ACCENT)
        c.rect(0, h - 38 * mm - 1.2 * mm, w, 1.2 * mm, stroke=0, fill=1)
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColor(SKY2)
        c.drawString(20 * mm, h - 12 * mm, "DAILY")
        c.setFillColor(ACCENT)
        c.drawString(20 * mm + c.stringWidth("DAILY ", "Helvetica-Bold", 8.5), h - 12 * mm, "BRIEF")
        c.setFillColor(HexColor("#eef0f7"))
        c.setFont("Helvetica-Bold", 22)
        c.drawString(20 * mm, h - 24 * mm, fmt_date(self.date))
        c.setFont("Helvetica", 9)
        c.setFillColor(SKY2)
        c.drawString(20 * mm, h - 31 * mm, self.subtitle)
        self.footer(c)
        c.restoreState()

    def later_page(self, c, doc):
        w, h = A4
        c.saveState()
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(INK3)
        c.drawString(20 * mm, h - 12 * mm, f"DAILY BRIEF  ·  {fmt_date(self.date, long=False).upper()}")
        c.setStrokeColor(RULE)
        c.line(20 * mm, h - 14 * mm, w - 20 * mm, h - 14 * mm)
        self.footer(c)
        c.restoreState()

    def footer(self, c):
        w, _ = A4
        c.setFont("Helvetica", 7.5)
        c.setFillColor(INK3)
        c.drawRightString(w - 20 * mm, 10 * mm, str(c.getPageNumber()))
        c.drawString(20 * mm, 10 * mm, "Original summaries written for Peter. Facts and quotes come from the sources listed.")


def divider():
    t = Table([[""]], colWidths=["100%"], rowHeights=[1])
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), 0.6, RULE)]))
    return [Spacer(1, 10), t, Spacer(1, 12)]


def edition_pdf(ed, path):
    mins = sum(a["read_minutes"] for a in ed["articles"])
    doc = Doc(path, ed["date"], f'{len(ed["articles"])} articles  ·  {mins} min reading')
    story = []
    if ed.get("changes"):
        rows = [[Paragraph("CHANGED BECAUSE OF YOUR FEEDBACK", S["whyh"])]] + [[Paragraph("• " + clean(c), S["changes"])] for c in ed["changes"]]
        box = Table(rows, colWidths=["100%"])
        box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT_SOFT), ("LEFTPADDING", (0, 0), (-1, -1), 9),
                                 ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, -1), (-1, -1), 7), ("TOPPADDING", (0, 0), (0, 0), 7)]))
        story += [box, Spacer(1, 6)]
    current = None
    for a in ed["articles"]:
        if a["topic"] != current:
            current = a["topic"]
            story.append(Paragraph(clean(TOPIC.get(current, (current,))[0].upper()), S["toch"]))
        story.append(Paragraph(f'<link href="#{a["id"]}" color="#161b2e">{clean(a["title"])}</link>', S["toc"]))
        story.append(Paragraph(f'{a["read_minutes"]} min  ·  {clean(a["tldr"][0])}', S["tocsub"]))
    for a in ed["articles"]:
        story += divider() if story and not isinstance(story[-1], CondPageBreak) else []
        story.append(CondPageBreak(60 * mm))
        story += article_flowables(a)
    doc.build(story)


def article_pdf(ed, a, path):
    doc = Doc(path, ed["date"], f'{TOPIC.get(a["topic"], (a["topic"],))[0]}  ·  {a["read_minutes"]} min read')
    doc.title = a["title"]
    doc.build(article_flowables(a))


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    date = sys.argv[1]
    with open(os.path.join(ROOT, "data", "editions", f"{date}.json"), encoding="utf-8") as f:
        ed = json.load(f)
    out = os.path.join(ROOT, "dist", "pdf", date)
    os.makedirs(out, exist_ok=True)
    edition_pdf(ed, os.path.join(out, f"daily-brief-{date}.pdf"))
    for a in ed["articles"]:
        article_pdf(ed, a, os.path.join(out, f'{a["id"]}.pdf'))
    size = os.path.getsize(os.path.join(out, f"daily-brief-{date}.pdf"))
    print(f"Built dist/pdf/{date}/: edition PDF {size // 1024} KB and {len(ed['articles'])} article PDFs")


if __name__ == "__main__":
    main()
