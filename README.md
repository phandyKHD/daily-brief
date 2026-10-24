# Daily Brief

A personal morning news brief that learns what Peter likes.

Every day at 04:30 UK time a Claude Code routine researches Peter's topics, writes 12–15 short original articles (2–4 minute reads) with source links, publishes them to a private viewer page on claude.ai and emails an offline copy. Each article is rated for relevance and quality, and free-text notes steer the next day's edition.

- `plan.md`: the full design and phase checklist
- `AGENT.md`: the morning agent's playbook
- `profile/`: interests, company context and everything the agent has learned
- `data/editions/`: one JSON file per day
- `viewer/template.html`: the viewer page
- `scripts/`: build, validation and rating ingestion (Python standard library only)

Build locally:

```
python3 scripts/validate_edition.py data/editions/2026-10-25.json
python3 scripts/build.py 2026-10-25
```
