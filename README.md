# Daily Brief

A personal morning news brief for several readers, run from Peter's claude.ai account.

Each reader has their own brief page (a private claude.ai artifact shared with them). Every morning the newsroom routine researches the shared topics once, then writes each reader their own edition from that shared pool plus their personal topics. Readers rate, leave notes, request write-ups ("Write this up") and change their **Setup** tab, and the agent learns from all of it.

| Routine | When (Europe/London) | Where it runs |
|---|---|---|
| Daily Brief – newsroom | 03:23 daily | fresh cloud session |
| Daily Brief – refresh check | every 2 hours, 07:00–21:00 | fresh cloud session |
| Daily Brief – Peter's email | 04:47 daily | Peter's builder chat (the only session with Gmail) |

- `AGENT.md`: the playbook every run follows
- `readers.json`: readers and their brief links
- `topics.json`: the shared topic library shown in Setup
- `scripts/`: state, newsroom, assemble, validate, build, PDF, ingest (Python 3)
- `viewer/template.html`: the brief page

Runs never push to GitHub: each reader's state (setup, learning, ratings, editions) lives in their own brief. The old single-reader files in `profile/` and `data/` are kept only as history.

## Adding a reader
Ask the builder chat: "add <name>". It creates a brief with the Setup tab open, adds it to `readers.json` and gives you the link. Share the brief from its Share menu as a **Contributor** (people in your organisation by name; others by email invite, which needs a free claude.ai login).
