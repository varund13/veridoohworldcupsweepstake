# Project: WC26 Sweepstake Tracker

> Created: 2026-06-28 | Product area: Other (personal project)
> Global context: ~/.claude/CLAUDE.md (Veridooh company brain — always loaded)

## Purpose
Automated World Cup 2026 sweepstake tracker that monitors match results, updates a live bracket, and publishes to GitHub Pages. Sends Slack notifications to the sweepstake group channel and a status DM to Varun on every run.

## Known constraints
- NO git in the remote routine at all — git clone/push both blocked by egress proxy. Use GitHub REST API (Contents GET) for reads and GitHub GraphQL API (POST /graphql, createCommitOnBranch mutation) for writes to both `main` (public/board.json) and `gh-pages` (board.json at root)
- REST API PUT to /repos/.../contents/ is also blocked by egress proxy — GraphQL POST is the only working write path
- GitHub Pages serves from ROOT of gh-pages branch (not public/)
- base64: use Python's base64.b64encode, NOT shell `base64 -w 0` (macOS incompatible)
- Blocked research sources: Wikipedia (403), BBC Sport (anti-bot), Sky Sports (anti-bot), curl to github.io (proxy blocked)
- Working sources: WebSearch, ESPN, FIFA.com, NBC Sports, CBS Sports, FOX Sports, Al Jazeera, Olympics.com
- apply-eliminations.js drops match_results and posted_matches — always backup/restore when running it
- Full-time rule: require 2 sources explicitly confirming FT before recording any result
- PAT expires Jul 12 2026 — update in claude.ai Routines panel (never paste in chat)

## Notes
- Remote routine: trig_01BYkfko5j1jnBFNiGU4UM6x on claude.ai cloud
- Cron: `30 9,23,4 * * *` UTC = 7pm, 9:30am, 2pm AEST (3 runs/day during knockout stage)
- Slack group channel: C0B97JGMG1F | Varun DM: U0B114QFZMG
- Repo: varund13/veridoohworldcupsweepstake
- R32 bracket fully populated as of 2026-06-28
