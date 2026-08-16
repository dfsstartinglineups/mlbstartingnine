import os
import json
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, db, messaging

# Establish absolute paths to ensure the script finds the data folder 
# regardless of where it is executed from.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

# Team Map for Names and URL Slugs
TEAM_MAP = {
    108: {"name": "Los Angeles Angels", "slug": "los-angeles-angels"},
    109: {"name": "Arizona Diamondbacks", "slug": "arizona-diamondbacks"},
    110: {"name": "Baltimore Orioles", "slug": "baltimore-orioles"},
    111: {"name": "Boston Red Sox", "slug": "boston-red-sox"},
    112: {"name": "Chicago Cubs", "slug": "chicago-cubs"},
    113: {"name": "Cincinnati Reds", "slug": "cincinnati-reds"},
    114: {"name": "Cleveland Guardians", "slug": "cleveland-guardians"},
    115: {"name": "Colorado Rockies", "slug": "colorado-rockies"},
    116: {"name": "Detroit Tigers", "slug": "detroit-tigers"},
    117: {"name": "Houston Astros", "slug": "houston-astros"},
    118: {"name": "Kansas City Royals", "slug": "kansas-city-royals"},
    119: {"name": "Los Angeles Dodgers", "slug": "los-angeles-dodgers"},
    120: {"name": "Washington Nationals", "slug": "washington-nationals"},
    121: {"name": "New York Mets", "slug": "new-york-mets"},
    133: {"name": "Oakland Athletics", "slug": "athletics"},
    134: {"name": "Pittsburgh Pirates", "slug": "pittsburgh-pirates"},
    135: {"name": "San Diego Padres", "slug": "san-diego-padres"},
    136: {"name": "Seattle Mariners", "slug": "seattle-mariners"},
    137: {"name": "San Francisco Giants", "slug": "san-francisco-giants"},
    138: {"name": "St. Louis Cardinals", "slug": "st-louis-cardinals"},
    139: {"name": "Tampa Bay Rays", "slug": "tampa-bay-rays"},
    140: {"name": "Texas Rangers", "slug": "texas-rangers"},
    141: {"name": "Toronto Blue Jays", "slug": "toronto-blue-jays"},
    142: {"name": "Minnesota Twins", "slug": "minnesota-twins"},
    143: {"name": "Philadelphia Phillies", "slug": "philadelphia-phillies"},
    144: {"name": "Atlanta Braves", "slug": "atlanta-braves"},
    145: {"name": "Chicago White Sox", "slug": "chicago-white-sox"},
    146: {"name": "Miami Marlins", "slug": "miami-marlins"},
    147: {"name": "New York Yankees", "slug": "new-york-yankees"},
    158: {"name": "Milwaukee Brewers", "slug": "milwaukee-brewers"}
}

def initialize_firebase():
    """Initialize the Firebase Admin SDK using GitHub Secrets."""
    secret_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
    if not secret_json:
        raise ValueError("FIREBASE_SERVICE_ACCOUNT environment variable is missing.")
    
    cred = credentials.Certificate(json.loads(secret_json))
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://nbastartingfive-8b420-default-rtdb.firebaseio.com'
    })

def get_today_date_string():
    """Ensure the server matches the frontend's localized date format."""
    tz = pytz.timezone('America/Los_Angeles')
    return datetime.now(tz).strftime('%Y-%m-%d')

def clean_old_watchlists(today_date):
    """Delete DFS watchlists from previous days to keep the database fast and clean."""
    ref = db.reference('watchlist')
    all_users = ref.get() or {}
    
    deleted_count = 0
    for uid, data in list(all_users.items()):
        if data.get('date') != today_date:
            ref.child(uid).delete()
            del all_users[uid]
            deleted_count += 1
            
    print(f"Cleanup Complete: Removed {deleted_count} stale DFS watchlists.")
    return all_users

def clean_old_team_watchlists(today_date):
    """Clear daily team subs and notification receipts from previous days."""
    ref = db.reference('team_watchlist')
    all_team_users = ref.get() or {}
    
    cleaned_count = 0
    for uid, data in list(all_team_users.items()):
        if data.get('date') != today_date:
            # Wipe today's daily subs and reset notification receipts
            ref.child(uid).child('daily').delete()
            ref.child(uid).child('notified').delete()
            ref.child(uid).update({'date': today_date})
            
            # Update local state so current run uses clean data
            all_team_users[uid]['daily'] = []
            all_team_users[uid]['notified'] = {}
            all_team_users[uid]['date'] = today_date
            cleaned_count += 1
            
    print(f"Cleanup Complete: Reset {cleaned_count} stale Team Subscriptions.")
    return all_team_users

def load_daily_json(today_date):
    """Grab the daily JSON file strictly by its exact filename, using absolute paths."""
    file_path = os.path.join(REPO_ROOT, 'data', 'daily_files', f'games_{today_date}.json')
    
    try:
        print(f"Reading official lineups from: {file_path}")
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Critical Error: {file_path} is missing. Halting execution.")

def extract_official_lineups(daily_data):
    """Parse the daily JSON to find official lineups, pitchers, and postponed games with doubleheader awareness."""
    official_teams = set()
    active_starters = set()
    postponed_teams = set()
    modified_teams = set()

    games = daily_data.get('games', [])

    # 1. Identify all teams playing a doubleheader today
    dh_teams = set()
    team_game_counts = {}
    for game in games:
        game_raw = game.get('gameRaw', {})
        teams = game_raw.get('teams', {})
        away_id = str(teams.get('away', {}).get('team', {}).get('id', ''))
        home_id = str(teams.get('home', {}).get('team', {}).get('id', ''))
        is_dh = game_raw.get('doubleHeader') == 'Y' or game_raw.get('gameNumber', 1) > 1

        if away_id:
            team_game_counts[away_id] = team_game_counts.get(away_id, 0) + 1
            if is_dh: dh_teams.add(away_id)
        if home_id:
            team_game_counts[home_id] = team_game_counts.get(home_id, 0) + 1
            if is_dh: dh_teams.add(home_id)

    for tid, count in team_game_counts.items():
        if count > 1:
            dh_teams.add(tid)

    # 2. Extract lineups, tagging starters with _G1 / _G2 if playing a doubleheader
    for game in games:
        game_raw = game.get('gameRaw', {})
        teams = game_raw.get('teams', {})
        lineups = game_raw.get('lineups', {})
        tracking = game.get('lineupTracking', {})
        status = game_raw.get('status', {})
        projected_lineups = game.get('projectedLineups', {})

        away_team_id = str(teams.get('away', {}).get('team', {}).get('id', ''))
        home_team_id = str(teams.get('home', {}).get('team', {}).get('id', ''))

        game_num = game_raw.get('gameNumber', 1)
        away_tag = f"G{game_num}" if away_team_id in dh_teams else None
        home_tag = f"G{game_num}" if home_team_id in dh_teams else None

        # Check for postponed games
        detailed_state = status.get('detailedState', '')
        status_code = status.get('statusCode', '')
        if 'Postponed' in detailed_state or status_code in ['PP', 'PR']:
            if away_tag:
                postponed_teams.add(f"{away_team_id}_{away_tag}")
            else:
                postponed_teams.add(away_team_id)
                postponed_teams.add(f"{away_team_id}_G1")

            if home_tag:
                postponed_teams.add(f"{home_team_id}_{home_tag}")
            else:
                postponed_teams.add(home_team_id)
                postponed_teams.add(f"{home_team_id}_G1")
            continue

        # Process Away Team
        away_status = tracking.get('away', {}).get('status')
        if away_status in ['OFFICIAL', 'MODIFIED']:
            if away_tag:
                official_teams.add(f"{away_team_id}_{away_tag}")
                if away_status == 'MODIFIED':
                    modified_teams.add(f"{away_team_id}_{away_tag}")
            else:
                official_teams.add(away_team_id)
                official_teams.add(f"{away_team_id}_G1")
                if away_status == 'MODIFIED':
                    modified_teams.add(away_team_id)
                    modified_teams.add(f"{away_team_id}_G1")

            for player in lineups.get('awayPlayers', []):
                pid = str(player.get('id'))
                if away_tag:
                    active_starters.add(f"{pid}_{away_tag}")
                else:
                    active_starters.add(pid)
                    active_starters.add(f"{pid}_G1")

            away_sp = projected_lineups.get('away', {}).get('startingPitcher', {})
            if away_sp and away_sp.get('id'):
                sp_id = str(away_sp.get('id'))
                if away_tag:
                    active_starters.add(f"{sp_id}_{away_tag}")
                else:
                    active_starters.add(sp_id)
                    active_starters.add(f"{sp_id}_G1")

        # Process Home Team
        home_status = tracking.get('home', {}).get('status')
        if home_status in ['OFFICIAL', 'MODIFIED']:
            if home_tag:
                official_teams.add(f"{home_team_id}_{home_tag}")
                if home_status == 'MODIFIED':
                    modified_teams.add(f"{home_team_id}_{home_tag}")
            else:
                official_teams.add(home_team_id)
                official_teams.add(f"{home_team_id}_G1")
                if home_status == 'MODIFIED':
                    modified_teams.add(home_team_id)
                    modified_teams.add(f"{home_team_id}_G1")

            for player in lineups.get('homePlayers', []):
                pid = str(player.get('id'))
                if home_tag:
                    active_starters.add(f"{pid}_{home_tag}")
                else:
                    active_starters.add(pid)
                    active_starters.add(f"{pid}_G1")

            home_sp = projected_lineups.get('home', {}).get('startingPitcher', {})
            if home_sp and home_sp.get('id'):
                sp_id = str(home_sp.get('id'))
                if home_tag:
                    active_starters.add(f"{sp_id}_{home_tag}")
                else:
                    active_starters.add(sp_id)
                    active_starters.add(f"{sp_id}_G1")

    return official_teams, active_starters, postponed_teams, modified_teams

def process_dfs_notifications(active_users, official_teams, active_starters, postponed_teams):
    """Evaluate DFS watchlists, group alerts, and send push notifications in high-speed batches."""
    master_data_path = os.path.join(REPO_ROOT, 'data', 'player_master_data.json')
    try:
        with open(master_data_path, 'r') as f:
            master_data = json.load(f)
    except FileNotFoundError:
        master_data = {}

    messages_to_send = []
    database_updates = {}

    for uid, user_data in active_users.items():
        push_token = user_data.get('push_token')
        pref = user_data.get('preference', 'critical_only')
        watchlist = user_data.get('watchlist', {})
        notified_state = user_data.get('notified_state', {})

        if not push_token or not watchlist:
            continue

        user_updates = {}
        scratches = []
        confirmed = []
        late_scratches = []
        late_adds = []
        postponed_players = [] 

        for watch_key, team_id in watchlist.items():
            team_id = str(team_id)
            current_state = notified_state.get(watch_key)
            
            # Deconstruct composite keys (e.g., "680777_G1" -> base_id: "680777", suffix: "G1")
            if '_' in watch_key:
                base_player_id, game_suffix = watch_key.split('_', 1)
                game_tag = f" ({game_suffix.replace('G', 'GM')})"  # Formats as " (GM1)" or " (GM2)"
                team_check_key = f"{team_id}_{game_suffix}"
            else:
                base_player_id = watch_key
                game_suffix = None
                game_tag = ""
                team_check_key = team_id

            # Lookup player name and attach the GM1/GM2 tag if applicable
            lookup_key = f"ID{base_player_id}"
            player_name = master_data.get(lookup_key, {}).get('name', 'Your player') + game_tag
            
            new_state = ""

            # Check for postponement first (this overrides everything else)
            if team_check_key in postponed_teams or team_id in postponed_teams:
                if current_state != 'postponed':
                    postponed_players.append(player_name)
                    new_state = 'postponed'
                if new_state and new_state != current_state:
                    user_updates[watch_key] = new_state
                continue 

            # Guardrail: Do nothing if this specific game's lineup hasn't dropped yet
            if team_check_key not in official_teams:
                continue 

            is_starting = watch_key in active_starters

            if is_starting and current_state != 'confirmed':
                if current_state == 'scratched':
                    late_adds.append(player_name)
                elif pref == 'full_coverage':
                    confirmed.append(player_name)
                new_state = 'confirmed'

            elif not is_starting and current_state != 'scratched':
                if current_state == 'confirmed':
                    late_scratches.append(player_name)
                else:
                    scratches.append(player_name)
                new_state = 'scratched'

            if new_state and new_state != current_state:
                user_updates[watch_key] = new_state

        if not user_updates:
            continue

        # 1. Chunk each alert category so player names never exceed lock screen width (~85 chars)
        def chunk_category(prefix, player_list, max_len=85):
            if not player_list:
                return []
            chunks = []
            current = []
            for player in player_list:
                test_str = f"{prefix}: " + ", ".join(current + [player])
                if len(test_str) > max_len and current:
                    chunks.append(f"{prefix}: " + ", ".join(current))
                    current = [player]
                else:
                    current.append(player)
            if current:
                chunks.append(f"{prefix}: " + ", ".join(current))
            return chunks

        category_lines = []
        category_lines.extend(chunk_category("☔ POSTPONED", postponed_players))
        category_lines.extend(chunk_category("🚨 LATE SCRATCH", late_scratches))
        category_lines.extend(chunk_category("🚨 OUT", scratches))
        category_lines.extend(chunk_category("✅ LATE ADD", late_adds))
        category_lines.extend(chunk_category("✅ IN", confirmed))

        # 2. Pack lines into notification batches (Strict limit: max 90 chars or max 2 lines per alert)
        batched_bodies = []
        current_batch = []
        current_len = 0

        for line in category_lines:
            line_len = len(line)
            if current_batch and (current_len + line_len + 1 > 90 or len(current_batch) >= 2):
                batched_bodies.append("\n".join(current_batch))
                current_batch = [line]
                current_len = line_len
            else:
                current_batch.append(line)
                current_len += line_len + 1

        if current_batch:
            batched_bodies.append("\n".join(current_batch))

        for i, body_text in enumerate(batched_bodies):
            title = "Lineup Alert" if len(batched_bodies) == 1 else f"Lineup Alert ({i+1}/{len(batched_bodies)})"
            
            msg = messaging.Message(
                data={
                    "title": title,
                    "body": body_text,
                    "url": "https://mlbstartingnine.com/"
                },
                token=push_token
            )
            messages_to_send.append(msg)

        for pid, state in user_updates.items():
            database_updates[f'watchlist/{uid}/notified_state/{pid}'] = state

    if messages_to_send:
        chunk_size = 500
        for i in range(0, len(messages_to_send), chunk_size):
            chunk = messages_to_send[i:i + chunk_size]
            try:
                response = messaging.send_each(chunk)
                print(f"DFS Batch sent: {response.success_count} successful, {response.failure_count} failed.")
            except Exception as e:
                print(f"Failed to send DFS batch: {e}")

    if database_updates:
        try:
            db.reference().update(database_updates)
            print(f"Successfully updated {len(database_updates)} DFS database receipts.")
        except Exception as e:
            print(f"Failed to update DFS database receipts: {e}")

def process_team_notifications(active_team_users, official_teams, postponed_teams, modified_teams):
    """Evaluate team-level subscriptions and send push notifications when lineups go official or are modified."""
    messages_to_send = []
    database_updates = {}

    for uid, user_data in active_team_users.items():
        push_token = user_data.get('push_token')
        if not push_token:
            continue

        daily_subs = user_data.get('daily', [])
        season_subs = user_data.get('season', [])
        
        # Combine subscribed team IDs into a set of strings for rapid checking
        subscribed_teams = set()
        if daily_subs: subscribed_teams.update(str(t) for t in daily_subs)
        if season_subs: subscribed_teams.update(str(t) for t in season_subs)
        
        if not subscribed_teams:
            continue

        # Get existing notification receipts
        notified_states = user_data.get('notified', {})
        user_updates = {}

        # 1. Evaluate Postponed Games
        for ppd_team in postponed_teams: # e.g. '147' or '147_G1'
            base_team = ppd_team.split('_')[0]
            
            # FIX: Ignore artificial "_G1" duplicates on normal days
            if ppd_team.endswith('_G1') and base_team in postponed_teams:
                continue
                
            ppd_key = f"PPD_{ppd_team}"
            
            if base_team in subscribed_teams and ppd_key not in notified_states:
                team_info = TEAM_MAP.get(int(base_team), {})
                team_name = team_info.get("name", "Team")
                team_slug = team_info.get("slug", "los-angeles-dodgers")
                
                msg = messaging.Message(
                    data={
                        "title": "Game Postponed",
                        "body": f"☔ The {team_name} game has been postponed.",
                        "url": f"https://mlbstartingnine.com/lineups/{team_slug}/"
                    },
                    token=push_token
                )
                messages_to_send.append(msg)
                user_updates[ppd_key] = True

        # 2. Evaluate Official & Modified Lineups
        for off_team in official_teams:
            base_team = off_team.split('_')[0]
            
            # FIX: Ignore artificial "_G1" duplicates on normal days
            if off_team.endswith('_G1') and base_team in official_teams:
                continue
            
            is_modified = off_team in modified_teams
            
            if base_team in subscribed_teams:
                has_official_receipt = off_team in notified_states
                has_modified_receipt = f"MOD_{off_team}" in notified_states
                
                alert_type = None
                
                if is_modified and not has_modified_receipt:
                    alert_type = "MODIFIED"
                elif not is_modified and not has_official_receipt:
                    alert_type = "OFFICIAL"
                    
                if alert_type:
                    team_info = TEAM_MAP.get(int(base_team), {})
                    team_name = team_info.get("name", "Team")
                    team_slug = team_info.get("slug", "los-angeles-dodgers")
                    
                    game_tag = ""
                    if "_G1" in off_team: game_tag = " (Game 1)"
                    elif "_G2" in off_team: game_tag = " (Game 2)"
                    
                    if alert_type == "MODIFIED":
                        body_text = f"🚨 MODIFIED: The {team_name} starting lineup{game_tag} has been updated! Tap to view the lineup."
                        # Mark both receipts so we don't backfire and send an official alert later
                        user_updates[f"MOD_{off_team}"] = True
                        user_updates[off_team] = True
                    else:
                        body_text = f"🚨 OFFICIAL: The {team_name} starting lineup{game_tag} is live! Tap to view the lineup."
                        user_updates[off_team] = True
                
                    msg = messaging.Message(
                        data={
                            "title": "Lineup Alert",
                            "body": body_text,
                            "url": f"https://mlbstartingnine.com/lineups/{team_slug}/"
                        },
                        token=push_token
                    )
                    messages_to_send.append(msg)

        # Queue database receipts
        if user_updates:
            for key, val in user_updates.items():
                database_updates[f'team_watchlist/{uid}/notified/{key}'] = val

    # Send Notification Payload
    if messages_to_send:
        chunk_size = 500
        for i in range(0, len(messages_to_send), chunk_size):
            chunk = messages_to_send[i:i + chunk_size]
            try:
                response = messaging.send_each(chunk)
                print(f"Team Alert Batch sent: {response.success_count} successful, {response.failure_count} failed.")
            except Exception as e:
                print(f"Failed to send Team Alert batch: {e}")

    # Write DB Receipts
    if database_updates:
        try:
            db.reference().update(database_updates)
            print(f"Successfully updated {len(database_updates)} Team DB receipts.")
        except Exception as e:
            print(f"Failed to update Team database receipts: {e}")

if __name__ == "__main__":
    print("Starting Unified MLB Notification Worker...")
    initialize_firebase()
    
    today = get_today_date_string()
    
    # 1. Clean both databases simultaneously
    active_dfs_users = clean_old_watchlists(today)
    active_team_users = clean_old_team_watchlists(today)
    
    # 2. Parse the daily JSON (Only happens once for maximum speed)
    daily_json = load_daily_json(today)
    official_teams, active_starters, postponed_teams, modified_teams = extract_official_lineups(daily_json)
    
    print(f"Teams with official lineups: {len(official_teams)}")
    print(f"Modified lineups: {len(modified_teams)}")
    print(f"Postponed teams: {len(postponed_teams)}")
    print(f"Total active starters parsed: {len(active_starters)}")
    
    # 3. Process DFS Scratches & Notifications
    process_dfs_notifications(active_dfs_users, official_teams, active_starters, postponed_teams)
    
    # 4. Process Team Level Notifications
    process_team_notifications(active_team_users, official_teams, postponed_teams, modified_teams)
    
    print("Unified Worker complete.")
