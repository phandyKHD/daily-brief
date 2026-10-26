# Daily Brief newsroom playbook

The Daily Brief is a personal morning news brief for several readers, all run from Peter's account. Each reader has their own brief page (a claude.ai artifact Peter owns and shares with them). Every morning one newsroom run researches the shared topics once, then writes each reader their own edition from that shared pool, plus their personal topics. Readers rate articles, leave notes, request write-ups and edit their **Setup** tab; the next run learns from all of it.

**Nothing at run time is saved to GitHub and nothing needs the Gmail connector.** Each reader's state lives in their own brief (artifact database and published files). The repo holds the code and is only read. Do not `git push` from a run.

Modes (the trigger text says which; default `daily`):
- **`daily`**: 04:00 Europe/London, a fresh session. All active readers.
- **`refresh`**: every 2 hours 07:00–21:00, a fresh session, and when Peter presses Refresh (text `mode=refresh reader=peter`). Only readers with a refresh flag or pending "Write this up" requests.
- **`mail`**: runs in Peter's own long-lived chat session (the only one with Gmail) after the daily run. Sends Peter his headlines email.

Today's date: `TZ=Europe/London date +%F`.

---

## Where things live

| What | Where |
|---|---|
| Code, viewer template, topic library (`topics.json`), reader registry (`readers.json`) | GitHub repo (read-only at run time) |
| Reader's setup (topics, counts, angles, about, stance, length, avoid) | Their artifact db `profile/setup` (written by the Setup tab) |
| Learned profile, standing instructions, feedback log, stats, last-ingest time | Their artifact db, collection `state`, one new doc per run (`s<YYYYMMDDTHHMMSS>`); the newest `saved_at` wins |
| Ratings, notes, thumbs, requests, refresh flag | Their artifact db: `ratings/*`, `requests/*`, `control/refresh` |
| Editions | Their artifact's published files `editions/<date>.json`, plus `pdf/<date>/*.pdf` |
| Working copy during a run | `work/<reader>/` (git-ignored), same layout as before: `profile/`, `data/`, `dist/` |

Scripts take the reader from the environment: prefix every script call with `BRIEF_HOME=work/<reader>`.

## 0. Start of every run

1. `cd /home/user/daily-brief && git pull origin main` (if the folder is missing, clone `https://github.com/phandyKHD/daily-brief` there). `rm -rf work dist/pool && mkdir -p dist/pool`.
2. Load tools: ToolSearch `select:ArtifactData`. The Artifact tool is built in.
3. Read `readers.json` and `topics.json`.

## 1. Load each reader (daily mode: every active reader; refresh mode: see section 7)

For reader `<r>` with brief `<url>`:

1. `python3 scripts/newsroom.py prepare <r>`
2. `Artifact` read `<url>` (any read counts; this lets you publish to it later).
3. `ArtifactData` get `profile/setup` with `out_dir` `work/<r>/export`.
4. `ArtifactData` query collection `state`, `query` `{"order_by": {"field": "saved_at", "direction": "desc"}, "limit": 1}`, `out_dir` `work/<r>/export`.
5. `Artifact` list `scope: "files"` on `<url>`; then `Artifact` read with `paths` set to the newest 7 `editions/<date>.json`, `out_dir` `work/<r>/export`.
6. `BRIEF_HOME=work/<r> python3 scripts/state.py unpack work/<r>/export`. If it says **No setup yet**, skip this reader for the rest of the run (their page stays on Setup).
7. `ArtifactData` list `ratings` (`query.limit` 1000, `out_dir` `work/<r>/export`), then `BRIEF_HOME=work/<r> python3 scripts/ingest_ratings.py work/<r>/export/ratings`. Keep the printed summary (notes!) for the reader's editor.
8. `ArtifactData` query `requests` where `status == "pending"`, `out_dir` `work/<r>/export`. Note each request's id and `version`.

## 2. Plan

`python3 scripts/newsroom.py plan` prints the shared desks (topic, article count, brief count, which readers, their angles) and the personal desks. Also list `dist/pool/recent.txt`: titles and tags of every reader's last 7 days of articles and briefs, for dedupe:

```
for r in work/*/; do for f in $r/data/editions/*.json; do python3 -c "import json,sys;e=json.load(open(sys.argv[1]));[print(e['date'],'['+a['topic']+']',a['title']) for a in e['articles']+e.get('briefs',[])]" $f; done; done | sort -u > dist/pool/recent.txt
```

## 3. Research (subagents, in parallel)

Spawn all desks in one message so they run in parallel (group small shared topics so there are at most about 8 subagents):

- **Shared desks** write `{"articles": [...], "briefs": [...]}` to `dist/pool/desk-<topic>.json`. Give them the topic's library description, the article and brief counts from the plan, the readers' angles, the dedupe file, and the Desk brief below.
- **Personal desks** (one per reader topic, or one per reader covering all their personal topics) write to `work/<r>/dist/desk-personal-<topic>.json`. Give them that reader's `profile/setup.json` (about, stance, avoid, the topic's description), their `profile/standing-instructions.md`, the dedupe file and the Desk brief.
- **Request desks**: each reader's pending requests go to a personal desk for that reader (requests come first; see Desk brief), written to `work/<r>/dist/desk-personal-requests.json`.

### Desk brief (copy this into every desk prompt)

> Research the news for your topics from the last `lookback_hours` hours using web search and by reading the actual articles. Pick the most important and interesting stories for the readers you are given (shared desks: every reader listed for your topic, plus their angles; personal desks: that one reader's setup). Prefer stories with real consequences over noise.
>
> For each slot write one **original** article. Do not copy paragraphs from sources; short attributed quotes are fine. Rules:
> - At least 2 independent sources you actually read, and all facts must come from them. Never invent quotes, figures or events. If you can't verify something, leave it out.
> - Follow the reader's `stance` for commentary and framing (shared desks: be factual and balanced, and use wires and specialists for facts; each reader's editor adds their angle).
> - Plain, direct British English. No clickbait titles. No filler.
> - `read_minutes` 2 → 380–500 words of body; 3 → 580–720; 4 → 780–950. Mostly 2. Use the reader's `length_minutes` as the default. Use 1 (200–330 words, dense with facts) when they ask for a quick read or when hard facts are scarce.
> - `kind`: `news` (reporting), `analysis` (explains why or what next), or `opinion` (built mainly on a commentator's argument; say whose in the body).
> - On contested stories add one line with the strongest counter-argument.
> - Personal desks write `why_it_matters` for their reader (required when the topic's description asks for it, e.g. Peter's industry topic). Shared desks leave `why_it_matters` null: each reader's editor writes it.
> - 3–6 lowercase `tags` naming the main entities and themes (e.g. `taiwan`, `reform uk`, `drones`, `listeria`, `ai agents`).
> - If a story continues one from the last 7 days, set `update_of` to that article's title and focus on what is new.
>
> - **Visuals.** Add a `visual` when the story turns on numbers or places that a picture makes clearer: a comparison, a trend, two or three headline figures, or a map. Aim for 4–6 per edition, never forced. Every number must appear in the article body and come from a source you read; never estimate, interpolate or add data points. Choose the form by the job:
>   - `bar`: compare 2–10 values in the same unit (before/after, countries, categories). Negative values are fine.
>   - `line`: a trend over time with 4–24 points, in order (only if a source gives the whole series).
>   - `map`: **whenever a story is about places: strikes, attacks, troop movements, routes, plants, outbreaks, elections by region.** Readers have asked for maps of strike locations; always use one for strike stories. Shape: `{"type": "map", "title": "…", "note": "Town locations, not exact impact points.", "points": [{"label": "Berezniki", "lat": 59.41, "lon": 56.82, "kind": "strike", "detail": "Avisma titanium works, drones, ~1,500 km from Ukraine"}], "highlight": ["Ukraine"], "source": "…"}`. `kind`: `strike`/`target` (hit), `base`/`origin` (launched from), `place` (for reference, e.g. Kyiv). Every point must be a place named in your sources. Use the coordinates of that town, city or facility from your general knowledge (this is the one exception to "numbers from sources"), and say in `note` that locations are approximate. Use `highlight` for the countries involved. 1–12 points; add one reference city if it helps orientation.
>   - `stats`: 1–4 headline figures that don't share a scale (e.g. "7+" ships hit, "~30" sailors missing). Values may be short strings.
>   Shape: `{"type": "bar"|"line"|"stats", "title": "…", "note": "what is measured, period, unit" (optional), "data": [{"label": "…", "value": 4.5}], "prefix": "£" (optional), "unit": "%" (optional), "decimals": 1 (optional), "highlight": "<one data label to emphasise>" (optional), "source": "outlet(s)"}`. One unit per chart: never mix £ and %, or two scales, in one chart. Otherwise `visual` is `null`.
>
> **Requested stories.** If you were given requests (the reader pressed "Write this up" on a summary), write each one as a full article first, using the request's summary and sources as the starting point and researching further. Set `from_brief` to the request's id (e.g. `"2026-10-25_b07"`). If the request has a `focus` note, build the article around it (answer their question, take their angle) and set `request_focus` to that note. Requests come before your normal slots and do not count against them.
>
> **More stories (briefs).** After the full articles, collect your brief count of further stories for the "More stories" tab: real, current stories that did not make your full articles, so readers can scan widely and ask for the ones he wants. Each brief: a plain headline `title`, a `summary` of 2–3 sentences (30–80 words) saying what happened and why it matters, 1–2 `sources` you actually opened or whose search result clearly states the facts, 2–5 lowercase `tags`, and the `topic`. Same accuracy rules as articles: nothing you cannot source. Cast wider than the articles (smaller stories, trade press, specialist outlets) and never repeat a story already covered by a full article in the last 7 days (unless there is a real new development).
>
> Output a JSON object `{"articles": [...], "briefs": [...]}`. Each article has exactly these fields:
> `topic, title, kind, read_minutes, tldr (3 short strings), body (array of paragraph strings), why_it_matters (string or null), sources (array of {outlet, title, url}), tags (array), update_of (string or null), visual (object or null), from_brief (string or null), request_focus (string or null)`.
> Each brief has exactly: `topic, title, summary, sources (array of {outlet, title, url}), tags`.
> Write it to the given file path, then reply with one line per article (title and word count) and the number of briefs.


## 4. Pool, then one editor per reader

1. `python3 scripts/newsroom.py merge-pool` writes `dist/pool/pool.json` and `dist/pool/index.txt`.
2. Spawn one **editor subagent per reader**, in parallel. Each editor:
   - reads `work/<r>/profile/setup.json`, `profile/standing-instructions.md`, `profile/learned.md`, `data/stats.json`, the ingest summary you pass it (with every new note), and `dist/pool/index.txt`;
   - **learns** (rules below) and edits `work/<r>/profile/learned.md` and `standing-instructions.md`;
   - **selects** from the pool for this reader: about `articles_per_day` articles in total including their personal desk articles. It follows the topic counts in their setup, adjusted by learning, and picks the best stories for this person. Briefs come to about `briefs_per_day` from their topics;
   - writes a **`why_it_matters`** line for each picked article where there is a genuine angle for this reader, or null. Industry or personal-context angles come from their `about`;
   - writes `work/<r>/dist/selection.json` in the format in `scripts/newsroom.py` (lead, articles with why_it_matters, briefs, 1–3 `changes` sentences about what changed because of their feedback).
   It must not change article text or facts.

### Learning rules (for editors)
- **Notes have the highest priority.** A lasting preference becomes a dated line in `standing-instructions.md`; a one-off request is acted on today only.
- **Topic weight**: `count × clamp(ewma_relevance / 3.5, 0.5, 1.5)`, rounded, once a topic has 3+ ratings. Never above a library `max` (US politics max 2). Never drop a topic the reader set to 1+ below 1.
- **Thumbs** on a summary count as relevance 4 / 3 / 1.5 (up / OK / down). A **request** ("Write this up") counts as 4.5 and is the strongest signal.
- **Tags** averaging 4+ become leads to favour, and tags averaging 2 or below are avoided. **Sources**: outlets averaging 4+ on quality are preferred, and those under 2.5 after 3+ ratings are avoided. **Length**: `too_long` → shorter; `too_shallow` → longer.
- Update `learned.md` with new points, citing dates. On Sundays rewrite it compactly.

## 5. Build and publish each reader

For each reader with a setup:

1. `BRIEF_HOME=work/<r> python3 scripts/newsroom.py select <r> work/<r>/dist/selection.json` (it prints LEAD and CHANGE lines).
2. `BRIEF_HOME=work/<r> python3 scripts/assemble_edition.py <date> daily --lead "<LEAD title>" --changes "<CHANGE>" …`
3. `BRIEF_HOME=work/<r> python3 scripts/validate_edition.py work/<r>/data/editions/<date>.json`. Fix errors by editing the desk files and re-running from step 1.
4. `BRIEF_HOME=work/<r> python3 scripts/build.py <date>` and `BRIEF_HOME=work/<r> python3 scripts/make_pdf.py <date>`.
5. `BRIEF_HOME=work/<r> python3 scripts/newsroom.py files <r> <date>` prints the `files` list and root.
6. `Artifact` publish: `file_path` `work/<r>/dist/live.html`, `url` `<url>`, `root` `work/<r>/dist`, `files` from step 5. Omit `capabilities`. If a path is refused as "not read", read it with `action: "read"` and `path`, then publish again.
7. Save state: `BRIEF_HOME=work/<r> python3 scripts/state.py pack` prints a doc id; `ArtifactData` set collection `state`, that `doc_id`, `file_path` `work/<r>/dist/state-doc.json`. This creates a new doc, so no version is needed.
8. Mark fulfilled requests: an `ArtifactData` `batch` of `update` writes `{"status": "done", "article_date": "<date>", "article_id": "<aXX>"}`, each pinned with the version you read.

## 6. Finish (daily)

Reply with one line per reader (articles and briefs, what changed from feedback, problems) and the shared-research totals. Never invent content to fill gaps; a short edition is fine.

## 7. Refresh mode

For every active reader (or only `reader=<r>` if the trigger text names one):
1. `ArtifactData` get `control/refresh` and query `requests` with `status == "pending"`. If the flag is absent or `status` is not `pending`, and there are no pending requests, skip the reader. **If no reader needs anything, stop here.** This is the common case and must stay cheap.
2. For a reader who needs work: steps 1.1–1.6 of section 1 (no ratings ingest). Also read today's `pdf/<date>/daily-brief-<date>.pdf` path from their brief, so it can be replaced.
3. One personal desk for that reader: write every pending request in full, then, if the refresh flag is set, enough fresh articles from their topics to make 5–8 in total, plus 10–15 new briefs. Write the output to `work/<r>/dist/desk-refresh.json`.
4. `BRIEF_HOME=work/<r> python3 scripts/assemble_edition.py <date> refresh --changes "Refresh: …"`, then validate, build, PDFs and publish as in section 5 (steps 3–6).
5. Mark requests done (section 5 step 8). Set `control/refresh` to `{"status": "done", "handled_at": "<now>"}` with an `update`, pinned to its version.

## 8. Mail mode (Peter only, in his chat session)

1. `python3 scripts/newsroom.py prepare peter`. Then `Artifact` read Peter's brief with `paths` `["editions/<date>.json"]`, `out_dir` `work/peter/export`, and copy the file to `work/peter/data/editions/`. Also `ArtifactData` get `profile/setup` into the export and run `state.py unpack`, so the topic labels are right.
2. `BRIEF_HOME=work/peter python3 scripts/build.py <date> --email-body > work/peter/dist/email.html` (headlines and key points, about 35 KB).
3. A subagent sends it with `mcp__Gmail__send_message` to `peter@khdtechnology.com`, subject `Daily Brief · <Day DD Mon> · <N> reads, <M> min`, `htmlBody` the file verbatim, and a one-line plain `body` with the brief link.
4. If today's edition is missing, do not send. Report it.

## Limits
- About 15 page fetches per desk. If a desk fails, publish without it and say so.
- Some outlets (Reuters, AP, BBC, Telegraph, Guardian, SCMP) are often blocked: use syndicated copies that credit them, and cite what you actually read.
- Readers can see each other's topics only through the shared pool; never put one reader's personal context (e.g. Peter's unannounced egg-line product) into a shared desk prompt or a shared article.
