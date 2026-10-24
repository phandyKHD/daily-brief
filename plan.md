# Daily Brief: a personal news app that learns what you like

A morning agent researches your topics, writes a set of short original articles (2–4 minutes each) with source links, and publishes them to an HTML viewer. You rate each article for **relevance** and **quality** and can leave a note. The next day's agent reads those ratings and notes and adjusts what it covers. A **Refresh** button runs the agent again on demand. Each edition is also emailed as an offline HTML file.

---

## 1. Goals and constraints

| Requirement | How the plan covers it |
|---|---|
| Runs every morning, unattended | Claude Code **Routine** (scheduled cloud session) at 04:30 UK time, every day |
| Short articles, mostly about 2 minutes, a few up to 4 | The agent writes original summaries of about 400–800 words, each built from several sources and linking back to them. Text is never copied from the sources (avoids copyright problems) |
| Learns from ratings | Two ratings out of 5 (relevance, quality), stored in a database the agent reads next morning |
| Free-text feedback that steers the next day | Feedback box under each article, read by the agent before it plans the next edition |
| Refresh button | The viewer starts the routine again with `mode=refresh`, which adds more articles to today's edition |
| Offline copy by email | A self-contained HTML file is attached to an email sent through the Gmail connector, with headlines and summaries in the email body as well |
| Right-leaning perspective | Source list and opinion selection favour centre-right outlets. Facts must still be accurate, and opinion pieces are labelled |
| US politics capped | Hard limit of 2 US-politics articles per edition, whatever the ratings say |

---

## 2. Architecture

```
                    ┌────────────────────────────────────────────┐
  04:30 UK cron ───►│  Claude Code Routine  (fresh cloud session)│◄── Refresh button
                    │  repo: daily-brief                         │    (fire_trigger via
                    │                                            │     Claude Code Remote
                    │  1. Ingest ratings + feedback (ArtifactData)│     connector)
                    │  2. Update learned profile                 │
                    │  3. Plan today's slots (quotas)            │
                    │  4. Desk subagents research in parallel    │
                    │  5. Editor writes articles → edition JSON  │
                    │  6. Build viewer HTML (live + offline)     │
                    │  7. Commit + push to GitHub                │
                    │  8. Republish viewer Artifact              │
                    │  9. Email offline HTML (Gmail connector)   │
                    └────────────────────────────────────────────┘
                                   │                     │
                         ┌─────────▼─────────┐   ┌───────▼────────┐
                         │ Viewer (Artifact) │   │ Email: offline │
                         │ private claude.ai │   │ .html attached │
                         │ page; db holds    │   └────────────────┘
                         │ ratings/feedback  │
                         └───────────────────┘
```

### Why this stack
- **No servers, no API keys.** The routine runs on your Claude plan. Gmail is already connected. The viewer is a private claude.ai Artifact that works on desktop, on mobile web and in the Claude app.
- **The Artifact `db` capability** saves ratings and feedback from the page, and the agent can read them back with the `ArtifactData` tool. No backend to build.
- **The Artifact `mcp` capability** lets the page call the built-in *Claude Code Remote* connector as you. The Refresh button can therefore call `fire_trigger` on the routine directly.
- **A GitHub repo is the source of truth** for the profile, the edition archive and the rating history. Routine sessions start empty each run, so anything that must persist goes through git.

### Fallback if the Artifact runtime is a problem
Host the viewer on GitHub Pages and store ratings in a small Cloudflare Worker with KV. Refresh would trigger a GitHub Actions `workflow_dispatch`. The data formats below are the same in both setups, so switching later is cheap.

---

## 3. Repository layout (`daily-brief`, private)

```
daily-brief/
├── CLAUDE.md                    # tells any session: "this is the Daily Brief project; see AGENT.md"
├── AGENT.md                     # the morning agent's full playbook (the routine prompt points here)
├── profile/
│   ├── interests.yaml           # topics, base quotas, hard caps, editorial stance, source lists
│   ├── company.md               # KHD Technology + competitor context for the Industry desk
│   ├── learned.md               # agent-maintained: what Peter likes/dislikes, with evidence
│   └── standing-instructions.md # distilled from free-text feedback; highest priority
├── data/
│   ├── editions/2026-10-25.json # one file per day (refresh rounds appended)
│   ├── ratings.jsonl            # append-only copy of every rating pulled from the db
│   ├── feedback-log.md          # every free-text note, dated, with article title
│   └── stats.json               # rolling per-topic / per-source / per-tag scores
├── viewer/
│   ├── template.html            # single-file viewer (CSS + JS inline, no external deps)
│   └── offline.css              # print/offline tweaks
├── scripts/
│   ├── build.py                 # edition JSON → dist/live.html + dist/offline-YYYY-MM-DD.html
│   ├── ingest_ratings.py        # merges db export → ratings.jsonl, recomputes stats.json
│   └── validate_edition.py      # schema + word-count + quota checks before publishing
└── dist/                        # build output (git-ignored except latest offline copy)
```

---

## 4. Starting interest profile (`profile/interests.yaml`)

Target edition size: **12–15 articles** (around 35–40 minutes of reading). Most should be about 2 minutes. The first 2 weeks are larger (around 16) to learn faster.

| Topic | Base quota | Rules |
|---|---|---|
| **Industry: food hygiene and belt sanitation** | 1–2 | See §5 |
| **China**: economy, CCP politics, Taiwan, trade, UK–China relations | 2 | |
| **NATO and defence**: spending, procurement, UK armed forces, alliance politics | 1–2 | |
| **Ukraine war**: front line, diplomacy, aid, sanctions | 2 | |
| **UK politics**: Westminster, Conservatives and Reform, economy and tax, immigration | 2–3 | |
| **US politics** | 1 (max 2) | **Hard cap of 2.** Never raised by learning |
| **AI in practice**: how people and businesses actually use it, tools, workflows, SMEs and manufacturing | 2 | Favour practical "how X is using AI" pieces over funding or model-release news |
| **Wildcard / exploration** | 1 | Something outside the profile that the agent thinks will interest you. Keeps the feed from narrowing to a filter bubble |

**Editorial stance (written into AGENT.md):**
- Favour centre-right sources and commentary, for example: The Telegraph, The Spectator, The Times, City AM, UnHerd, CapX, The Critic, ConservativeHome, Daily Mail (news only), GB News (news only), WSJ, The Free Press, National Review, Washington Examiner. Use wire services (Reuters, AP) and specialist outlets for facts: ISW and RUSI for Ukraine and defence, SCMP and Nikkei Asia for China.
- Keep facts accurate and do not invent anything. Where an article contains opinion, label it **Opinion / Analysis** and say whose view it is.
- When a story is contested, include the strongest counter-argument in one line.

---

## 5. Industry desk context (`profile/company.md`)

**KHD Technology** (Keith Handy Design Ltd, Stone, Staffordshire) designs and manufactures portable, food-grade **conveyor belt cleaning systems** that use **dry saturated steam** and no chemicals:
- Mesh belt cleaners (Jet System 5, static and hand-held spinners), portable flat belt cleaners (brush and brushless), fixed-head cleaners and special designs
- Steam generators: KHD-16 (9 kW), KHD-32 (18 kW), KHD-36 (36 kW)
- Telescopic steam wall cleaner
- Markets: food processing, especially **bakery** (bread, pans and trays), plus non-food uses. Belt types: wire mesh, spiral and modular. Sells direct in the UK and through distributors abroad.
- Selling points: less labour, water, energy and chemical use, and fewer belt replacements.

**Main competitor: Goodway Technologies** (Stamford, Connecticut, founded 1966). It is much broader than KHD: tube cleaning, industrial vacuums, cooling tower and HVAC maintenance, dry steam cleaners, and the **PureBelt** conveyor belt cleaning system and BioSpray sanitiser sprayers for food and beverage.

**What the Industry desk looks for:**
- Goodway news, product launches and case studies (especially PureBelt), plus any other belt-sanitation or dry-steam competitors it finds. These are logged in `company.md` so the list grows over time.
- Food safety regulation and enforcement: UK FSA, BRCGS standard updates, US FDA FSMA, Listeria and allergen recalls caused by equipment hygiene.
- Bakery and food-processing investment: new plants, automation, labour shortages and their effect on cleaning.
- Sustainability pressure on water, energy and chemical use in sanitation.
- Trade shows: PPMA Show, IFFA, Anuga FoodTec, IBIE, Process Expo.
- Trade press to search: Food Manufacture (UK), Food Engineering, Food Processing, Bakery & Snacks, Baking Business, British Baker, New Food.
- Every industry article ends with **"Why it matters for KHD"**: one or two lines on the sales angle, a competitive threat or a product idea.

---

## 6. The morning agent (`AGENT.md`)

The routine prompt is short: *"You are the Daily Brief agent. Read AGENT.md and execute a `daily` run for today."* (or `refresh`, passed in the fire text). All real logic lives in `AGENT.md` in the repo, so it can change without editing the routine.

### Steps
1. **Ingest.** Use `ArtifactData list` to read `ratings` and `feedback` docs newer than the last ingest. Append them to `ratings.jsonl` and `feedback-log.md`, then run `ingest_ratings.py` to recompute `stats.json`.
2. **Learn** (see §8). Update `learned.md`, `standing-instructions.md` and today's quotas. Write 1–3 lines saying **"What changed today based on your feedback"**. These appear at the top of the edition.
3. **Plan.** Build a slot list, e.g. `[industry×2, china×2, nato×1, ukraine×2, uk×3, us×1, ai×2, wildcard×1]`. Include today's leads from `learned.md`, such as tags you like or follow-ups to stories you rated highly.
4. **Research (in parallel).** Run one subagent per desk: Industry, Geopolitics (China, NATO, Ukraine), UK politics, US politics, AI and Wildcard. Each desk:
   - runs targeted web searches for the last 24–36 hours (72 hours for Industry, where news is slower)
   - fetches and reads the 3–6 best sources
   - returns candidate stories ranked by importance, fit to the profile and source quality, each with facts, quotes and URLs
5. **Dedupe.** Drop stories already covered in the last 7 editions unless there is real new development. Follow-ups are labelled "Update".
6. **Edit and write.** An editor pass picks the final set to fill the slots and writes each article (format below).
7. **Validate.** Run `validate_edition.py`, which checks the schema, word counts, the US cap, that every article has at least 2 sources and that no links are broken.
8. **Build and publish.** Run `build.py`, commit and push, then republish the viewer Artifact with today's data.
9. **Email** the offline HTML (§9).
10. **Log** run metadata (duration, sources used, any failures) into the edition JSON.

### Article format
```
Title                      (plain, informative, not clickbait)
Topic · Read time · Opinion/Analysis label if relevant
TL;DR                      3 bullets
Body                       ~400 words (2-min), up to ~800 (4-min); short paragraphs
Why it matters             1–2 lines (always for Industry; optional elsewhere)
Sources                    2–5 links with outlet names
Tags                       3–6 entities/themes used for learning (e.g. "Taiwan", "Reform UK", "drones", "AI agents in SMEs")
```

### Refresh mode
- Reads ratings and feedback given *so far today* and learns from them straight away.
- Adds a "Round 2" (then 3, and so on) of 5–8 articles to today's edition. It avoids anything already in today's edition and leans on the slots that scored best that morning.
- Republishes the viewer. It does **not** email again, unless the refresh text says `email`.

---

## 7. Viewer (`viewer/template.html` → claude.ai Artifact)

One self-contained HTML file. It is mobile-first, supports light and dark mode, and needs no external dependencies, so the same file also works offline.

**Layout**
- Header: date, edition stats (e.g. "14 articles · 38 min"), the **"What changed today"** note and a **Refresh** button (with a running/done state).
- Topic filter chips with counts. Progress bar showing "6 / 14 rated".
- Article cards. Collapsed: title, topic, read time and the TL;DR. Expanded: full body, why it matters, sources.
- **At the end of each article:**
  - Relevance ★★★★★
  - Quality ★★★★★
  - Quick tags: `more like this` · `less like this` · `too long` · `too shallow` · `already knew` · `biased` · `great source`
  - Feedback box: *"Notes for tomorrow's agent…"*. Saved automatically and shown as "Saved ✓".
- An archive drawer for past editions, loaded from the repo build or embedded for the last 7 days.
- A "What I've learned about you" panel showing a read-only view of `learned.md`, topic scores and top and bottom sources. It makes the learning visible and easy to correct.

**Capabilities declared**
- `db` + `user`: ratings and feedback documents, writable only by you.
  - `ratings/{date}_{articleId}` → `{relevance, quality, tags[], feedback, ratedAt, round}`
  - `requests/{id}` → refresh requests (used as a fallback; see risks)
- `mcp`: the `Claude Code Remote` server with the `fire_trigger` tool. This is what makes the Refresh button work.
- If the page loads without these capabilities, rating falls back to `localStorage` with an "Export ratings" button. The page always renders either way.

---

## 8. Learning loop

Relevance and quality are tracked **separately** because they answer different questions:
- **Relevance** tunes *what* gets covered: topic quotas, subtopics and tags, search queries.
- **Quality** tunes *how* and *from where*: source trust, depth, length and writing style.

**Rules (recomputed in `stats.json` each run):**
- **Topic weight** = exponentially weighted average of relevance over 14 days. `quota = base × clamp(avg/3.5, 0.5, 1.5)`, rounded. Every core topic keeps at least 1 slot. US stays capped at 2. The wildcard always keeps 1 slot.
- **Tag affinity**: average relevance per tag, counted once a tag has at least 2 ratings. The top tags become explicit search leads and the bottom tags are avoided.
- **Source trust**: average quality per outlet. Outlets averaging 4 or more are preferred. Outlets under 2.5 after 3 or more ratings are dropped from primary sourcing.
- **Length and depth**: the `too long` and `too shallow` tags plus quality scores per read-time bucket shift the 2/3/4-minute mix.
- **Free-text feedback has the highest priority.** It is read in full every run. Lasting preferences ("stop covering X", "more on Y", "I like analysis from Z") are added to `standing-instructions.md` with a date. One-off requests ("follow up on the Leopard tank story") go into the next edition only.
- **Unrated articles** count as weak negatives for that topic only, and only after 3 days unrated. Skipped is not the same as disliked.
- **Weekly (Sunday run):** compact `learned.md` and remove outdated rules. Add a "Your week in ratings" summary card to the edition.
- **Cold start (first 14 days):** larger editions, 2 wildcard slots, and the Refresh button highlighted.

---

## 9. Offline email

- After publishing, `build.py` produces `offline-YYYY-MM-DD.html`. This is the same viewer with all CSS inline, no network calls and all articles expanded by default. Ratings are saved to `localStorage`.
- Send it with `mcp__Gmail__send_message` to `peter@khdtechnology.com`:
  - **Subject:** `Daily Brief · Sat 25 Oct · 14 reads, 38 min`
  - **htmlBody:** each headline and TL;DR plus the "What changed today" note. Gmail's mobile app caches this, so the email body is readable offline even without opening the attachment.
  - **Attachment:** the offline HTML, base64-encoded, `text/html` (well under the 25 MB limit).
- **Phase 2 (optional): rate while offline.** The offline file gets a "Send my ratings" button that opens a pre-filled `mailto:` with a compact ratings block. The next run searches Gmail for `subject:"Daily Brief ratings"` and ingests it like database ratings.

---

## 10. Scheduling

- Routine: `create_trigger` with `create_new_session_on_fire: true` and repo `daily-brief`.
  - Cron `CRON_TZ=Europe/London 30 4 * * *` (04:30 every day, weekends included).
  - Connectors: `["Gmail"]` (the Claude Code Remote connector is needed by the viewer, not by the routine).
  - Notifications: push when finished.
- Refresh: the viewer calls `fire_trigger(trigger_id, text="mode=refresh")`. The trigger id is embedded in the page at publish time.

---

## 11. Implementation phases

Each phase ends with something usable.

**Phase 0: Setup**
- [ ] Create the private GitHub repo `daily-brief` and attach it to the session
- [ ] Write `interests.yaml`, `company.md`, empty `learned.md` and `standing-instructions.md`
- [ ] Write the `CLAUDE.md` and `AGENT.md` skeleton

**Phase 1: Viewer with sample data**
- [ ] Edition JSON schema + `validate_edition.py`
- [ ] `template.html`: cards, ratings, tags, feedback, filters, progress, dark mode, phone layout
- [ ] `build.py` producing the live and offline variants
- [ ] Publish as an Artifact with `db` + `user`. Check that ratings save and can be read back with `ArtifactData`

**Phase 2: First real edition (manual run)**
- [ ] Desk subagent prompts, editor prompt and article format in `AGENT.md`
- [ ] Run once by hand, check quality, length and the right-leaning balance, adjust
- [ ] Commit the edition and republish the viewer

**Phase 3: Email**
- [ ] Email body template, offline HTML attachment and a send test

**Phase 4: Automation and Refresh**
- [ ] Create the routine (cron + Gmail connector)
- [ ] Wire the Refresh button through the `mcp` capability to `fire_trigger`, then test end to end
- [ ] Implement refresh mode (Round 2 articles added to today's edition)

**Phase 5: Learning loop**
- [ ] `ingest_ratings.py` + `stats.json`
- [ ] Quota, tag and source rules; feedback added to standing instructions; the "What changed today" note
- [ ] "What I've learned about you" panel
- [ ] Sunday compaction and weekly summary

**Phase 6: Polish (later)**
- [ ] Offline rating by email
- [ ] Audio version (text-to-speech) for the commute
- [ ] Recurring watch items, e.g. "track Goodway PureBelt", "track the BRCGS Issue 10 timeline"

---

## 12. Risks and open questions

| # | Item | Plan |
|---|---|---|
| 1 | **Refresh via `mcp` → `fire_trigger`** depends on the Artifact runtime allowing that connector from the page. | Test in Phase 4. Fallback: the button writes a `requests/` doc and opens the routine's page on claude.ai, where you tap "Run now". |
| 2 | Routine sessions must be able to use `ArtifactData` and republish the Artifact. | Check in the Phase 2 manual run from a routine-style fresh session. Fallback: GitHub Pages plus a Worker (§2). |
| 3 | Paywalls (Telegraph, Times, WSJ) limit what the agent can read. | Use the free text, wire copy and other outlets for the facts. Paywalled outlets can still supply the opinion angle through quotes reported elsewhere. Source trust learns what actually gets read. |
| 4 | Run time and usage: around 6 desks with several fetches each. | Cap at about 40 fetches per run. Log the run duration and trim if needed. |
| 5 | A right-leaning perspective must not turn into misinformation. | At least 2 sources per article, opinion labelled, a counter-argument line on contested stories, and the `biased` tag gives feedback. |
| 6 | Email recipient | Decided: peter@khdtechnology.com. |
| 7 | Delivery time | Decided: 04:30 UK, every day including weekends. |
| 8 | Repo | `phandyKHD/daily-brief` (private) |
