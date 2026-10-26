# Daily Brief

A personal morning news brief for several readers (Peter and the people he shares it with), run from Peter's account.

- If you were started by a routine (newsroom, refresh or mail), read `AGENT.md` and follow it exactly.
- If you are Peter's builder session: code changes go to GitHub as usual; runs never push.

Conventions:
- Scripts are Python 3 standard library only, except `scripts/make_pdf.py` (reportlab, preinstalled). Run them from the repo root.
- Per-reader scripts read `BRIEF_HOME=work/<reader>`; without it they use the repo root (the old single-reader layout).
- `readers.json` lists readers and their brief URLs; `topics.json` is the shared topic library.
- Each reader's state lives in their own brief (artifact db and published files), never in git.
- A reader's `standing-instructions.md` comes from their own notes and outranks everything else for them.
- Dates and times are Europe/London.
