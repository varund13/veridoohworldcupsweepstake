#!/usr/bin/env python3
"""
WC26 Sweepstake Tracker — GitHub Actions edition
Fetches match results from ESPN API, updates board.json, posts to Slack.
Runs inside GitHub Actions where git push is available.
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

BOARD_PATH = "public/board.json"
SLACK_CHANNEL = "C0B97JGMG1F"
VARUN_DM = "U0B114QFZMG"
BOARD_URL = "https://varund13.github.io/veridoohworldcupsweepstake/"

# R32 bracket index map (must match board.json bracket.r32 order)
R32_MAP = [
    ("Canada", "South Africa"),
    ("Brazil", "Japan"),
    ("Germany", "Paraguay"),
    ("Netherlands", "Morocco"),
    ("Ivory Coast", "Norway"),
    ("France", "Sweden"),
    ("Mexico", "Ecuador"),
    ("England", "DR Congo"),
    ("Belgium", "Senegal"),
    ("United States", "Bosnia & Herzegovina"),
    ("Spain", "Austria"),
    ("Portugal", "Croatia"),
    ("Switzerland", "Algeria"),
    ("Australia", "Egypt"),
    ("Argentina", "Cape Verde"),
    ("Colombia", "Ghana"),
]

# Country flags
FLAGS = {
    "Canada": "🇨🇦", "South Africa": "🇿🇦", "Brazil": "🇧🇷", "Japan": "🇯🇵",
    "Germany": "🇩🇪", "Paraguay": "🇵🇾", "Netherlands": "🇳🇱", "Morocco": "🇲🇦",
    "Ivory Coast": "🇨🇮", "Norway": "🇳🇴", "France": "🇫🇷", "Sweden": "🇸🇪",
    "Mexico": "🇲🇽", "Ecuador": "🇪🇨", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "DR Congo": "🇨🇩",
    "Belgium": "🇧🇪", "Senegal": "🇸🇳", "United States": "🇺🇸",
    "Bosnia & Herzegovina": "🇧🇦", "Spain": "🇪🇸", "Austria": "🇦🇹",
    "Portugal": "🇵🇹", "Croatia": "🇭🇷", "Switzerland": "🇨🇭", "Algeria": "🇩🇿",
    "Australia": "🇦🇺", "Egypt": "🇪🇬", "Argentina": "🇦🇷", "Cape Verde": "🇨🇻",
    "Colombia": "🇨🇴", "Ghana": "🇬🇭",
}

# ESPN team name → board.json name (where they differ)
ESPN_NAME_MAP = {
    "Cote d'Ivoire": "Ivory Coast",
    "United States": "United States",
    "Bosnia and Herzegovina": "Bosnia & Herzegovina",
    "Democratic Republic of Congo": "DR Congo",
    "Congo DR": "DR Congo",
    "Cabo Verde": "Cape Verde",
}


def flag(country):
    return FLAGS.get(country, "🏳️")


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def slack_post(token, channel, text):
    payload = json.dumps({"channel": channel, "text": text}).encode()
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=payload,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        resp = json.loads(r.read())
    if not resp.get("ok"):
        print(f"Slack error: {resp.get('error')}", file=sys.stderr)
    return resp.get("ok", False)


def normalize_name(name):
    return ESPN_NAME_MAP.get(name, name)


def get_round_label(name):
    name = name.lower()
    if "round of 32" in name or "32" in name:
        return "Round of 32"
    if "round of 16" in name or "16" in name:
        return "Round of 16"
    if "quarter" in name:
        return "Quarter-final"
    if "semi" in name:
        return "Semi-final"
    if "final" in name:
        return "Final"
    return name.title()


def get_espn_results():
    """Fetch all completed WC2026 matches from ESPN scoreboard."""
    url = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
    try:
        data = fetch_json(url)
    except Exception as e:
        print(f"ESPN fetch error: {e}", file=sys.stderr)
        return []

    results = []
    for event in data.get("events", []):
        comp = event.get("competitions", [{}])[0]
        status = comp.get("status", {}).get("type", {})
        if status.get("name") != "STATUS_FULL_TIME":
            continue

        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            continue

        # ESPN returns home/away; find each by homeAway field
        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

        home_name = normalize_name(home.get("team", {}).get("displayName", ""))
        away_name = normalize_name(away.get("team", {}).get("displayName", ""))
        home_score = int(home.get("score", 0))
        away_score = int(away.get("score", 0))

        # Determine winner (handle penalties)
        winner = None
        notes = comp.get("notes", [])
        note_text = " ".join(n.get("headline", "") for n in notes).lower()
        aet = "aet" in note_text or "extra time" in note_text
        pens = "penalt" in note_text or "shootout" in note_text
        if home_score > away_score:
            winner = home_name
        elif away_score > home_score:
            winner = away_name
        else:
            # Draw in 90 — check notes for penalty winner
            for n in notes:
                hl = n.get("headline", "")
                m = re.search(r"(\w[\w\s&]+) win[s]? on penalt", hl, re.IGNORECASE)
                if m:
                    pen_winner = normalize_name(m.group(1).strip())
                    winner = pen_winner
                    break

        # Date from event
        date_str = event.get("date", "")[:10]  # YYYY-MM-DD
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            date_label = dt.strftime("%-d %b")
        except Exception:
            date_label = date_str

        # Round
        round_name = get_round_label(
            event.get("season", {}).get("slug", "") + " " +
            comp.get("type", {}).get("text", "")
        )

        # Match key
        match_key = f"{home_name} vs {away_name} on {date_label}"

        results.append({
            "home": home_name,
            "away": away_name,
            "home_score": home_score,
            "away_score": away_score,
            "winner": winner,
            "date": date_label,
            "match_key": match_key,
            "round": round_name,
            "aet": aet,
            "pens": pens,
            "note_text": note_text,
        })

    return results


def propagate_bracket(b):
    """Fill in next-round slots from confirmed winners."""
    rounds = [("r32", "r16"), ("r16", "qf"), ("qf", "sf")]
    for from_r, to_r in rounds:
        src = b[from_r]
        dst = b[to_r]
        for i, match in enumerate(src):
            if not match.get("w"):
                continue
            di = i // 2
            side = "a" if i % 2 == 0 else "b"
            if dst[di].get(side) is None:
                dst[di][side] = match["w"]
    # sf → fin
    sf = b.get("sf", [])
    fin = b.get("fin", {})
    if isinstance(sf, list) and len(sf) >= 2:
        if sf[0].get("w") and not fin.get("a"):
            fin["a"] = sf[0]["w"]
        if sf[1].get("w") and not fin.get("b"):
            fin["b"] = sf[1]["w"]
    if isinstance(fin, dict) and fin.get("w") and not b.get("champion"):
        b["champion"] = fin["w"]


def build_slack_message(match, board):
    """Build Slack message for a completed knockout match."""
    home, away = match["home"], match["away"]
    hs, as_ = match["home_score"], match["away_score"]
    winner = match["winner"]
    loser = away if winner == home else home
    date = match["date"]
    round_label = match["round"]
    mapping = board.get("mapping", {})

    score_note = ""
    if match["pens"]:
        score_note = " _(AET — wins on penalties)_"
    elif match["aet"]:
        score_note = " _(AET)_"

    person_home = mapping.get(home, "?")
    person_away = mapping.get(away, "?")
    person_loser = mapping.get(loser, "?")

    lines = [
        f"{flag(home)} *{home}* {hs}–{as_} *{away}* {flag(away)}{score_note}",
        f"📅 {date} · {round_label} · #FIFAWorldCup2026",
        "",
        f"🏆 *{winner}* advance to the next round!",
        f"💀 {flag(loser)} {loser} are eliminated — tough luck *{person_loser}*! 😢",
        f"👀 Sweepstake watch: {flag(home)} belongs to *{person_home}* · {flag(away)} belongs to *{person_away}*",
        f"<{BOARD_URL}|📊 View the bracket>",
    ]
    return "\n".join(lines)


def main():
    slack_token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not slack_token:
        print("ERROR: SLACK_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    # Load board
    with open(BOARD_PATH) as f:
        board = json.load(f)

    posted = set(board.get("posted_matches", []))
    bracket = board.setdefault("bracket", {})
    out = board.setdefault("out", {})

    # Fetch results
    results = get_espn_results()
    print(f"ESPN: {len(results)} completed matches found")

    new_posts = 0
    bracket_updates = 0
    new_eliminations = []

    for match in results:
        key = match["match_key"]
        winner = match["winner"]
        loser = match["away"] if winner == match["home"] else match["home"]

        # Update bracket for R32 matches
        for i, (a, b_team) in enumerate(R32_MAP):
            home_norm = match["home"]
            away_norm = match["away"]
            if (a == home_norm and b_team == away_norm) or (a == away_norm and b_team == home_norm):
                if winner and not bracket.get("r32", [{}] * 16)[i].get("w"):
                    bracket["r32"][i]["w"] = winner
                    bracket_updates += 1
                    print(f"Bracket: r32[{i}].w = {winner}")
                break

        # Knock-out elimination: add loser to out
        if winner and loser and loser not in out:
            out[loser] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            new_eliminations.append(loser)
            print(f"Eliminated: {loser}")

        # Post to Slack if not already posted
        if key not in posted:
            msg = build_slack_message(match, board)
            if slack_post(slack_token, SLACK_CHANNEL, msg):
                posted.add(key)
                new_posts += 1
                print(f"Posted: {key}")
            else:
                print(f"Slack post failed: {key}", file=sys.stderr)

    # Propagate bracket winners to next rounds
    propagate_bracket(bracket)

    # Save updated board
    board["posted_matches"] = sorted(posted)
    board["exportedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    with open(BOARD_PATH, "w") as f:
        json.dump(board, f, indent=2)

    print(f"Done: {new_posts} new posts, {bracket_updates} bracket updates, {len(new_eliminations)} new eliminations")

    # Status DM to Varun
    r32_winners = sum(1 for m in bracket.get("r32", []) if m.get("w"))
    status_msg = (
        f"✅ WC26 tracker run complete (GitHub Actions) — "
        f"{len(out)} eliminated, {len(posted)} posted matches, "
        f"{new_posts} new results posted, {bracket_updates} bracket positions updated. "
        f"R32 winners so far: {r32_winners}/16. Board updated."
    )
    slack_post(slack_token, VARUN_DM, status_msg)


if __name__ == "__main__":
    main()
