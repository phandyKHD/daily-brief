# Daily Brief

This repo is Peter's personal news brief. If you were started by the morning routine or a refresh, read `AGENT.md` and follow it exactly.

Conventions:
- Scripts are Python 3 standard library only. Run them from the repo root.
- Edition files live at `data/editions/YYYY-MM-DD.json` and must pass `scripts/validate_edition.py` before building.
- Never edit `data/ratings.jsonl` by hand. It is append-only and written by `scripts/ingest_ratings.py`.
- `profile/standing-instructions.md` comes from Peter's own feedback and outranks everything else in `profile/`.
- Dates and times are Europe/London.
- Viewer artifact URL and routine trigger id are stored in `config.json`.
