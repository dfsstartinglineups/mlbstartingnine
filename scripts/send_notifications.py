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
    """Delete watchlists from previous days to keep the database fast and clean."""
    ref = db.reference('watchlist')
    all_users = ref.get() or {}
    
    deleted_count = 0
    for uid, data in list(all_users.items()):
        if data.get('date') != today_date:
            ref.child(uid).delete()
            del all_users[uid]
            deleted_count += 1
            
    print(f"Cleanup Complete: Removed {deleted_count} stale watchlists.")
    return all_users

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
    """Parse the daily JSON to find official lineups, pitchers, and postponed games."""
    official_teams = set()
    active_starters = set()
    postponed_teams = set()

    for game in daily_data.get('games', []):
        game_raw = game.get('gameRaw', {})
        teams = game_raw.get('teams', {})
        lineups = game_raw.get('lineups', {})
        tracking = game.get('lineupTracking', {})
        status = game_raw.get('status', {})
        
        # Pull the projectedLineups node to access the starting pitchers
        projected_lineups = game.get('projectedLineups', {})

        away_team_id = str(teams.get('away', {}).get('team', {}).get('id', ''))
        home_team_id = str(teams.get('home', {}).get('team', {}).get('id', ''))

        # Check if the game has been officially postponed
        detailed_state = status.get('detailedState', '')
        status_code = status.get('statusCode', '')
        if 'Postponed' in detailed_state or status_code in ['PP', 'PR']:
            postponed_teams.add(away_team_id)
            postponed_teams.add(home_team_id)
            continue # Skip lineup parsing for postponed games

        # Process Away Team
        if tracking.get('away', {}).get('status') == 'OFFICIAL':
            official_teams.add(away_team_id)
            
            # Add the 9 starting batters
            for player in lineups.get('awayPlayers', []):
                active_starters.add(str(player.get('id')))
                
            # Add the Starting Pitcher
            away_sp = projected_lineups.get('away', {}).get('startingPitcher', {})
            if away_sp and away_sp.get('id'):
                active_starters.add(str(away_sp.get('id')))

        # Process Home Team
        if tracking.get('home', {}).get('status') == 'OFFICIAL':
            official_teams.add(home_team_id)
            
            # Add the 9 starting batters
            for player in lineups.get('homePlayers', []):
                active_starters.add(str(player.get('id')))
                
            # Add the Starting Pitcher
            home_sp = projected_lineups.get('home', {}).get('startingPitcher', {})
            if home_sp and home_sp.get('id'):
                active_starters.add(str(home_sp.get('id')))

    return official_teams, active_starters, postponed_teams

def process_notifications(active_users, official_teams, active_starters, postponed_teams):
    """Evaluate watchlists, group alerts, and send push notifications in high-speed batches."""
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

        for player_id, team_id in watchlist.items():
            team_id = str(team_id)
            current_state = notified_state.get(player_id)
            
            # Prepend 'ID' to the player_id for the lookup
            lookup_key = f"ID{player_id}"
            player_name = master_data.get(lookup_key, {}).get('name', 'Your player')
            
            new_state = ""

            # Check for postponement first (this overrides everything else)
            if team_id in postponed_teams:
                if current_state != 'postponed':
                    postponed_players.append(player_name)
                    new_state = 'postponed'
                if new_state and new_state != current_state:
                    user_updates[player_id] = new_state
                continue 

            # Guardrail: Do nothing if the team's lineup hasn't dropped yet
            if team_id not in official_teams:
                continue 

            is_starting = player_id in active_starters

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
                user_updates[player_id] = new_state

        if not user_updates:
            continue

        # Add the postponed players to the batching logic
        body_lines = []
        if postponed_players:
            body_lines.append("☔ POSTPONED: " + ", ".join(postponed_players))
        if late_scratches:
            body_lines.append("🚨 LATE SCRATCH: " + ", ".join(late_scratches))
        if scratches:
            body_lines.append("🚨 OUT: " + ", ".join(scratches))
        if late_adds:
            body_lines.append("✅ LATE ADD: " + ", ".join(late_adds))
        if confirmed:
            body_lines.append("✅ IN: " + ", ".join(confirmed))

        batched_bodies = []
        current_batch = ""

        for line in body_lines:
            if len(current_batch) + len(line) > 200:
                batched_bodies.append(current_batch.strip())
                current_batch = line + "\n"
            else:
                current_batch += line + "\n"
        
        if current_batch:
            batched_bodies.append(current_batch.strip())

        for i, body_text in enumerate(batched_bodies):
            title = "Lineup Alert" if len(batched_bodies) == 1 else f"Lineup Alert ({i+1}/{len(batched_bodies)})"
            
            # THE FIX: Send as a pure data payload so only the Service Worker triggers
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
                print(f"Batch sent: {response.success_count} successful, {response.failure_count} failed.")
            except Exception as e:
                print(f"Failed to send batch: {e}")

    if database_updates:
        try:
            db.reference().update(database_updates)
            print(f"Successfully updated {len(database_updates)} database receipts.")
        except Exception as e:
            print(f"Failed to update database receipts: {e}")
            
if __name__ == "__main__":
    print("Starting MLB Lineup Notification Worker...")
    initialize_firebase()
    
    today = get_today_date_string()
    
    # 1. Clean the database
    active_users = clean_old_watchlists(today)
    
    # 2. Parse the daily JSON
    daily_json = load_daily_json(today)
    official_teams, active_starters, postponed_teams = extract_official_lineups(daily_json)
    
    print(f"Teams with official lineups: {len(official_teams)}")
    print(f"Postponed teams: {len(postponed_teams)}")
    print(f"Total active starters parsed: {len(active_starters)}")
    
    # 3. Process the state machine and send alerts
    process_notifications(active_users, official_teams, active_starters, postponed_teams)
    print("Worker complete.")
