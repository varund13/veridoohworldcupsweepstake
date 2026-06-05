# World Cup 2026 — Last Man Standing Sweepstake

A digital version of the "48 envelopes on the wall" office sweepstake. Every staff member is
secretly sealed inside a country envelope. As countries are knocked out of the FIFA World Cup 2026,
their envelopes open — with a cinematic reveal — to show who's eliminated. The last person whose
country is still alive wins. Eliminations are detected **automatically every 6 hours**; no admin needed.

## Layout
```
public/sweepstake.html   the whole app (admin tool + public live board, one file)
public/board.json        public snapshot (eliminations, bracket, champion) — served by Netlify
draw-private.json        the SEALED draw (country -> person). Repo root, NEVER served. (you create this)
apply-eliminations.js    deterministic: turns a list of eliminated countries into board.json
TRACKER.md               runbook the 6-hourly auto-tracker routine follows
netlify.toml             tells Netlify to publish only public/
```
The page auto-detects its mode: opened locally (`file://`) → **admin/authoring**; served by Netlify
with a `board.json` present → **read-only LIVE board** (re-checks `board.json` every 2 min, auto-plays
the elimination popup, no admin controls, no hidden names).

Admin passphrase lives in `public/sweepstake.html` → `const ADMIN_PASS` (default `veridooh2026` — change it).
Only matters locally; the deployed board has no admin powers.

## One-time setup
1. Open `public/sweepstake.html` locally. Admin → **Draw & Seal** (must be exactly 48 people).
2. **Export board.json** → save to `public/board.json`. **Export draw (private)** → save to `draw-private.json` (repo root).
3. `git add -A && git commit && git push` (this is a **private** repo — `draw-private.json` lives here but is never served).
4. Netlify is connected to this repo; publish dir `public/` (see `netlify.toml`).

## How updates happen (automatic)
The `wc26-sweepstake-tracker` routine runs every 6h: reads the sealed draw + current board, researches
live results from 2+ sources (FIFA + BBC/Sky), marks teams **officially** eliminated (only when 2+
sources agree), runs `apply-eliminations.js`, and pushes `public/board.json` → Netlify redeploys → the
live board reveals the envelope within ~2 minutes.

Manual override (optional): the admin tool can still knock teams out by hand and re-export.

## Knockout bracket
Symmetric R32 → R16 → QF → SF → Final (centre) → champion, with connector lines. Admin assigns the 32
survivors and picks winners; the loser's envelope opens. (The tracker currently drives the envelope
eliminations; the bracket can be filled by an admin.)

## Notes / limits
- **Headcount = exactly 48.** The draw refuses to run otherwise.
- **Security is "good for an office game," not Fort Knox.** The deployed board only ever contains
  already-public info. The sealed mapping lives in `draw-private.json` (private repo, never served).
- Don't deploy `.claude/` — `netlify.toml` already limits publishing to `public/`.
