#!/usr/bin/env python3
"""
WC26 Sweepstake Tracker — GitHub Actions edition
Fetches match results from ESPN API, updates board.json, posts to Slack.
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

BOARD_PATH = "public/board.json"
SLACK_CHANNEL = "C0B97JGMG1F"
VARUN_DM = "U0B114QFZMG"
BOARD_URL = "https://varund13.github.io/veridoohworldcupsweepstake/"

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

ESPN_NAME_MAP = {
    "Cote d'Ivoire": "Ivory Coast",
    "Bosnia and Herzegovina": "Bosnia & Herzegovina",
    "Bosnia-Herzegovina": "Bosnia & Herzegovina",
    "Democratic Republic of Congo": "DR Congo",
    "Congo DR": "DR Congo",
    "Cabo Verde": "Cape Verde",
}

ROUND_SLUG_MAP = {
    "round-of-32": "Round of 32",
    "round-of-16": "Round of 16",
    "quarterfinal": "Quarter-final",
    "semifinal": "Semi-final",
    "final": "Final",
}

# Bracket round key → (array key, next array key)
BRACKET_ROUNDS = [
    ("r32", "r16"),
    ("r16", "qf"),
    ("qf", "sf"),
    ("sf", "fin"),
]


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
        data=payload, method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        resp = json.loads(r.read())
    if not resp.get("ok"):
        print(f"Slack error: {resp.get('error')}", file=sys.stderr)
    return resp.get("ok", False)


def normalize_name(name):
    return ESPN_NAME_MAP.get(name, name)


def get_espn_results():
    # Query last 7 days by date to catch matches that fell off the live scoreboard
    base = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
    today = datetime.now(timezone.utc)
    dates = [(today - __import__('datetime').timedelta(days=i)).strftime("%Y%m%d") for i in range(7)]

    seen_ids = set()
    all_events = []
    for date in dates:
        try:
            data = fetch_json(f"{base}?dates={date}")
            for event in data.get("events", []):
                if event.get("id") not in seen_ids:
                    seen_ids.add(event.get("id"))
                    all_events.append(event)
        except Exception as e:
            print(f"ESPN fetch error ({date}): {e}", file=sys.stderr)

    results = []
    for event in all_events:
        comp = event.get("competitions", [{}])[0]
        FINAL_STATUSES = {"STATUS_FULL_TIME", "STATUS_FINAL", "STATUS_FINAL_AET", "STATUS_FINAL_PEN"}
        if comp.get("status", {}).get("type", {}).get("name") not in FINAL_STATUSES:
            continue

        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            continue

        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
        home_name = normalize_name(home.get("team", {}).get("displayName", ""))
        away_name = normalize_name(away.get("team", {}).get("displayName", ""))
        home_score = int(home.get("score", 0))
        away_score = int(away.get("score", 0))

        notes = comp.get("notes", [])
        note_text = " ".join(n.get("headline", "") for n in notes).lower()
        aet = "aet" in note_text or "extra time" in note_text
        pens = "penalt" in note_text or "shootout" in note_text

        if home_score > away_score:
            winner = home_name
        elif away_score > home_score:
            winner = away_name
        else:
            # Tied after 90/120 min — check notes then ESPN winner boolean
            winner = None
            for n in notes:
                m = re.search(r"([\w][\w\s&']+?)\s+(?:wins?|advance[sd]?)\s+(?:\d+-\d+\s+on\s+penalt|\bon\s+penalt)", n.get("headline", ""), re.IGNORECASE)
                if m:
                    winner = normalize_name(m.group(1).strip())
                    pens = True
                    break
            # Fallback: use ESPN's winner boolean on competitors
            if not winner:
                if home.get("winner"):
                    winner = home_name
                elif away.get("winner"):
                    winner = away_name

        # Build team_id → team_name map
        team_id_map = {}
        for c in competitors:
            team_id_map[c.get("team", {}).get("id")] = normalize_name(c.get("team", {}).get("displayName", ""))

        # Parse goalscorers from details (excluding shootout penalties)
        goalscorers = []
        for detail in comp.get("details", []):
            if not detail.get("scoringPlay"):
                continue
            if detail.get("shootout"):
                continue
            clock = detail.get("clock", {}).get("displayValue", "")
            own_goal = detail.get("ownGoal", False)
            pen = detail.get("penaltyKick", False)
            athletes = detail.get("athletesInvolved", [])
            scorer_name = athletes[0].get("shortName", athletes[0].get("displayName", "?")) if athletes else "?"
            team_id = detail.get("team", {}).get("id")
            team_name = team_id_map.get(team_id, "")
            suffix = " (pen)" if pen else (" (og)" if own_goal else "")
            goalscorers.append({
                "name": scorer_name,
                "clock": clock,
                "team": team_name,
                "suffix": suffix,
                "flag": FLAGS.get(team_name, "🏳️"),
            })

        season_slug = event.get("season", {}).get("slug", "")
        round_label = ROUND_SLUG_MAP.get(season_slug, season_slug.replace("-", " ").title())

        date_str = event.get("date", "")[:10]
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            date_label = dt.strftime("%-d %b")
        except Exception:
            date_label = date_str

        results.append({
            "home": home_name, "away": away_name,
            "home_score": home_score, "away_score": away_score,
            "winner": winner,
            "loser": (away_name if winner == home_name else home_name) if winner else None,
            "date": date_label,
            "event_id": event.get("id", ""),
            "match_key": f"{home_name} vs {away_name} on {date_label}",
            "round": round_label,
            "round_slug": season_slug,
            "aet": aet, "pens": pens,
            "goalscorers": goalscorers,
        })

    return results


def find_bracket_slot(bracket, team_a, team_b):
    """Find which round and index a match belongs to, by team names."""
    for round_key, _ in BRACKET_ROUNDS:
        slots = bracket.get(round_key, [])
        if not isinstance(slots, list):
            continue
        for i, slot in enumerate(slots):
            a, b = slot.get("a"), slot.get("b")
            if {a, b} == {team_a, team_b}:
                return round_key, i
    # Check fin (1-element array)
    fin_slots = bracket.get("fin", [])
    if isinstance(fin_slots, list) and fin_slots:
        fin = fin_slots[0]
        if {fin.get("a"), fin.get("b")} == {team_a, team_b}:
            return "fin", 0
    return None, None


def update_bracket_winner(bracket, round_key, idx, winner):
    """Set winner and propagate to next round's slot."""
    if round_key == "fin":
        fin_slot = bracket["fin"][0]
        if not fin_slot.get("w"):
            fin_slot["w"] = winner
            bracket["champion"] = winner
        return

    slots = bracket[round_key]
    if slots[idx].get("w"):
        return  # Already set
    slots[idx]["w"] = winner

    # Propagate to next round
    next_round = dict(BRACKET_ROUNDS).get(round_key)
    if not next_round:
        return

    next_idx = idx // 2
    side = "a" if idx % 2 == 0 else "b"

    if next_round == "fin":
        fin_slots = bracket.setdefault("fin", [{"a": None, "b": None, "w": None}])
        if not fin_slots[0].get(side):
            fin_slots[0][side] = winner
    else:
        next_slots = bracket.setdefault(next_round, [])
        while len(next_slots) <= next_idx:
            next_slots.append({"a": None, "b": None, "w": None})
        if not next_slots[next_idx].get(side):
            next_slots[next_idx][side] = winner


def build_slack_message(match, mapping):
    home, away = match["home"], match["away"]
    winner, loser = match["winner"], match["loser"]
    score_note = " _(AET — wins on penalties)_" if match["pens"] else (" _(AET)_" if match["aet"] else "")

    lines = [
        f"{flag(home)} *{home}* {match['home_score']}–{match['away_score']} *{away}* {flag(away)}{score_note}",
        f"📅 {match['date']} · {match['round']} · #FIFAWorldCup2026",
        "",
        f"🏆 *{winner}* advance to the next round!",
        f"💀 {flag(loser)} {loser} are eliminated — tough luck *{mapping.get(loser, '?')}*! 😢",
    ]

    # Goals line
    goals = match.get("goalscorers", [])
    if goals:
        goal_parts = [f"{g['flag']} {g['name']} {g['clock']}{g['suffix']}" for g in goals]
        lines.append("⚽ " + " · ".join(goal_parts))

    lines += [
        f"👀 Sweepstake watch: {flag(home)} belongs to *{mapping.get(home, '?')}* · {flag(away)} belongs to *{mapping.get(away, '?')}*",
        f"<{BOARD_URL}|📊 View the bracket>",
    ]
    return "\n".join(lines)


def main():
    slack_token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not slack_token:
        print("ERROR: SLACK_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    with open(BOARD_PATH) as f:
        board = json.load(f)

    # posted_event_ids is the canonical dedup key (ESPN event ID, timezone-proof)
    # posted_matches kept for legacy/display only
    posted_ids = set(board.get("posted_event_ids", []))
    posted_keys = set(board.get("posted_matches", []))
    bracket = board.setdefault("bracket", {})
    out = board.setdefault("out", {})
    mapping = board.get("mapping", {})

    results = get_espn_results()
    print(f"ESPN: {len(results)} completed matches found")

    new_posts = 0
    bracket_updates = 0
    new_eliminations = []

    for match in results:
        winner, loser = match["winner"], match["loser"]
        event_id = match["event_id"]
        key = match["match_key"]

        # Update bracket
        round_key, idx = find_bracket_slot(bracket, match["home"], match["away"])
        if round_key and winner:
            slots = bracket.get(round_key, [])
            current_w = slots[idx].get("w") if isinstance(slots, list) else None
            if not current_w:
                update_bracket_winner(bracket, round_key, idx, winner)
                bracket_updates += 1
                print(f"Bracket: {round_key}[{idx}].w = {winner}")

        # Track elimination
        if loser and loser not in out:
            out[loser] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            new_eliminations.append(loser)
            print(f"Eliminated: {loser}")

        # Post to Slack — dedup by event_id (falls back to key for legacy entries)
        already_posted = event_id in posted_ids or key in posted_keys
        if not already_posted and winner:
            msg = build_slack_message(match, mapping)
            if slack_post(slack_token, SLACK_CHANNEL, msg):
                posted_ids.add(event_id)
                posted_keys.add(key)
                new_posts += 1
                print(f"Posted: {key}")
            else:
                print(f"Slack post failed: {key}", file=sys.stderr)

    board["posted_event_ids"] = sorted(posted_ids)
    board["posted_matches"] = sorted(posted_keys)
    board["exportedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    with open(BOARD_PATH, "w") as f:
        json.dump(board, f, indent=2)

    print(f"Done: {new_posts} new posts, {bracket_updates} bracket updates, {len(new_eliminations)} new eliminations")

    r32_winners = sum(1 for m in bracket.get("r32", []) if m.get("w"))
    slack_post(slack_token, VARUN_DM,
        f"✅ WC26 tracker run complete (GitHub Actions) — "
        f"{len(out)} eliminated, {len(posted_keys)} posted matches, "
        f"{new_posts} new results posted, {bracket_updates} bracket positions updated. "
        f"R32: {r32_winners}/16 decided. Board updated."
    )


if __name__ == "__main__":
    main()
