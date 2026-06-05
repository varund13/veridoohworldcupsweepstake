# Auto-Tracker Runbook (every 6 hours)

Goal: with **no admin in the loop**, detect which World Cup 2026 teams are officially out,
reveal their envelopes on the live board, and publish — fully autonomously.

This file is the instruction set the scheduled routine follows. The schedule was created with
`/schedule` to run **every 6 hours**.

## What the routine does each run

1. **Read the sealed draw** — `draw-private.json` at the repo root (`mapping`: country → person, plus `groups`).
2. **Read current state** — `public/board.json` (which teams are already marked out).
3. **Research live results from 2+ independent sources** — e.g. the FIFA site + BBC Sport/Sky Sports.
   Determine the full set of teams that are **officially eliminated** right now:
   - **Group stage:** a team is out when it cannot finish in the top 2 of its group AND cannot be one of
     the 8 best third-placed teams (i.e. mathematically eliminated / confirmed bottom).
   - **Knockout stage:** a team is out the moment it loses its knockout match.
   - Only count an elimination as official when **at least 2 sources agree**. If sources conflict or a
     result is provisional/under protest, **do not** open that envelope this run — leave it for next time.
4. **Apply** — run the deterministic helper with the cumulative list of ALL eliminated countries:
   ```
   node apply-eliminations.js --out "Scotland,Curaçao,Haiti,..."
   ```
   At the very end, when one team remains, also pass `--champion "<Country>"`.
   (Country names must match `draw-private.json` exactly — e.g. `Bosnia & Herzegovina`, `Curaçao`.)
5. **Publish** — commit and push so Netlify redeploys:
   ```
   git add public/board.json && git commit -m "tracker: update eliminations $(date -u +%FT%TZ)" && git push
   ```
   The live page polls `board.json` every 2 minutes and auto-plays the cinematic reveal for any
   newly-opened envelope.

## Guardrails
- **Cumulative list:** always pass the *complete* set of eliminated teams to `--out`, not just new ones.
  The helper preserves earlier knockout dates, so re-passing old teams is safe.
- **Never reveal a team that is still alive.** When unsure, do nothing — the next run (6h later) will catch it.
- **2-source rule is mandatory.** A single headline is not enough.
- Log each run (teams researched, sources, decisions) so a human can audit later.

## One-time human setup (required before the routine can publish)
1. Draw & seal once in the admin tool, then **Export board.json** → `public/board.json`,
   and **Export draw (private)** → `draw-private.json` at the repo root.
2. Create a **private** GitHub repo, push this folder.
3. Connect Netlify to the repo (publish dir is `public/`, set in `netlify.toml`).
4. Ensure the routine has Git push credentials for the repo.
