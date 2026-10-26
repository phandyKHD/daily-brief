# Daily Brief for several readers: plan

Goal: Peter runs one system that gives his wife and colleagues their own Daily Brief. Each reader:
- has their own topics, set up in their own words
- gets the same article, rating, More stories and Refresh layout Peter has now
- opens a link to read; no GitHub, no email setup, nothing to install

The agent itself must never depend on GitHub pushes or the Gmail connector at run time, because those are the two things that broke.

---

## 1. What we learned from the last three days

| Problem | Cause | Design response |
|---|---|---|
| Push to GitHub refused | Fresh routine sessions cannot be granted push access | Run-time state never goes to GitHub. GitHub holds code only, and is only read. |
| Email not sent | Fresh routine sessions do not get the Gmail connector | Email becomes optional. Offline reading uses the edition PDF from the viewer. |
| Running inside Peter's chat session | Works, but the chat grows every day and runs queue behind conversation | Go back to a fresh session per run, now possible because nothing needs push or Gmail. |
| Refresh press lost | A trigger fire into a busy session can go missing | Refresh becomes a database flag that a light poller picks up. It no longer depends on firing a trigger. |
| Email took 2 hours to send | 121 KB body copied by hand through the tool | No full-text email. |

What has worked every time: **reading the code from GitHub, publishing artifacts, and reading and writing artifact databases.** The new design uses only those.

---

## 2. Architecture

```
                      GitHub repo (code only, read-only at run time)
                                 │ clone
                                 ▼
 04:00 "Daily Brief – newsroom" routine (fresh session)
   1. Load reader registry (readers.json) and each reader's setup + ratings
      from their own artifact database
   2. SHARED RESEARCH: one desk per topic that ANY reader subscribes to
      (industry, UK politics, Ukraine, …, plus custom topics)
      → a pool of ~60–90 articles and ~150 summaries for the day
   3. PER READER (in parallel, one cheap editor subagent each):
      pick from the pool by that reader's quotas and learning,
      write reader-specific "Why it matters" lines, order the edition,
      add any custom-topic desk that only they need
   4. Build viewer + PDFs per reader, publish each reader's artifact
   5. Save state (learned profile, stats, edition JSON) into that
      reader's own artifact database
                                 │
          ┌──────────────────────┼──────────────────────┐
          ▼                      ▼                      ▼
   Peter's brief          Wife's brief           Colleague's brief
   (artifact + db)        (artifact + db)        (artifact + db)

 Hourly 07:00–22:00 "Daily Brief – refresh" routine (fresh session)
   Checks every reader's db for a "refresh wanted" flag or pending
   "Write this up" requests. If none: stops (cheap). If any: writes
   those up for that reader only and republishes their brief.
```

### Why a shared pool
The expensive part is research: about 100k tokens per topic desk. Ten readers each running their own desks would cost ten times as much and hit plan limits quickly. With a pool, each topic is researched once a day, and each extra reader only costs one editor pass. That is roughly 10–20% of a full run, plus any custom topic only they want.

### Where everything lives

| Thing | Where | Who writes it |
|---|---|---|
| Code, viewer template, playbook | GitHub repo | Builder session only (this chat), when changing features |
| Reader registry (`readers.json`: id, name, artifact URL, active) | GitHub repo | Builder session, when a reader is added |
| Reader's setup (topics, tone, length, context) | Reader's artifact db `profile/setup` | The reader, from a **Setup** tab in their brief |
| Learned profile, standing instructions, stats | Reader's artifact db `profile/*` | Newsroom run |
| Ratings, notes, thumbs, requests, refresh flag | Reader's artifact db | Reader, from the page |
| Editions (last 30 days) | Reader's artifact published files `editions/<date>.json` | Newsroom run |

Peter's current repo state (`profile/`, `data/`) moves into his artifact db once, during the migration step, and from then on the runs never push.

---

## 3. Reader experience

1. Peter says "add Sarah, sarah@example.com". The builder session:
   - creates her brief artifact with an empty edition and the **Setup** tab open
   - adds her to `readers.json`
   - gives Peter the link
2. Peter shares it from the artifact's Share menu:
   - **Colleagues in the KHD organisation:** add them by name as Contributors.
   - **His wife (outside the organisation):** email invite as Contributor. She needs a free claude.ai login. This organisation's settings turn off public links, so "anyone with the link" is not available. A one-time sign-in is the lightest option.
3. On first open she fills in **Setup**:
   - her topics (pick from the shared list, or add her own with a sentence describing it)
   - roughly how many articles per topic
   - preferred length (1, 2 or 3 minutes) and tone or perspective
   - free-text context about herself ("I'm a GP in Staffordshire, interested in…")
   - anything to avoid
4. From the next morning she gets her own edition. Everything else works exactly as it does for Peter: stars, thumbs, notes, More stories, Write this up with a focus note, Save as PDF, Refresh. She can come back to Setup and change it at any time, and the next run picks it up.

Peter's own brief keeps its current URL.

---

## 4. Viewer changes (same layout)

- New **Setup** tab: the form above, saved to `profile/setup` in the db. On the first visit with no setup, the page opens on this tab.
- **Refresh** writes `control/refresh` `{requested_at}` to the db, and the hourly poller does the work. The button shows "Queued, usually ready within the hour". For Peter only, it also tries the direct trigger as it does now.
- "What I've learned" reads the learned profile from the db instead of the embedded copy.
- Archive reads past editions from the artifact's published files.
- Everything else is unchanged.

---

## 5. Email

Default off: offline reading uses **Save edition as PDF**. If Peter wants the morning email back, it can be kept just for him by a small daily job in this chat session that sends a short email of headlines and summary points, about 15 KB, not full text. It is optional and never blocks the brief.

---

## 6. Cost and limits (Peter's plan pays for every reader)

The figures below are rough. They will be measured in the first week.

| | Today (1 reader) | 3 readers, shared pool | 6 readers, shared pool |
|---|---|---|---|
| Research desks | ~0.7M tokens | ~0.9M (a few more topics) | ~1.1M |
| Editors and per-reader extras | (included) | ~0.3M | ~0.6M |
| Hourly refresh checks | none | ~15 × small | ~15 × small |
| Refresh write-ups | as used | as used | as used |

If plan limits bite:
- stagger the readers (some at 04:00, some at 05:30)
- cap summaries at 30 for other readers
- run custom topics every other day

---

## 7. Build phases

1. **State out of GitHub.** Scripts work from a local working folder that is filled from, and saved back to, a reader's artifact (db and files). Peter's data is migrated. Runs no longer push.
2. **Multi-reader pipeline.**
   - `readers.json`
   - a shared topic library (`topics/*.yaml`, with Peter's KHD industry brief as a private topic)
   - pool desks
   - a per-reader editor that writes `data/editions` into the reader's artifact
3. **Viewer:** Setup tab, refresh flag, archive and learned profile read from the artifact.
4. **Routines:**
   - "Daily Brief – newsroom": 04:00, fresh session each run
   - "Daily Brief – refresh": hourly, 07:00–22:00
   - remove the self-bound trigger
5. **Add-a-reader procedure:** one command in the builder session that creates the artifact, adds the registry entry and returns the link.
6. **Pilot:** Peter plus one reader for a week, measure token use, then add the rest.

## 8. Decisions for Peter
1. Email: off for everyone (PDF instead), or keep a short headlines email for Peter only?
2. How many readers to start, and who first?
3. Should colleagues share the KHD industry topic (same company context), or should each have their own industry angle?
4. Is the hourly refresh check from 07:00 to 22:00 acceptable, or every 2 hours to save usage?
