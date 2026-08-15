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
    """Parse the daily JSON to find teams with released lineups and active players."""
    official_teams = set()
    active_starters = set()

    for game in daily_data.get('games', []):
        game_raw = game.get('gameRaw', {})
        teams = game_raw.get('teams', {})
        lineups = game_raw.get('lineups', {})
        tracking = game.get('lineupTracking', {})

        # Process Away Team
        away_team_id = str(teams.get('away', {}).get('team', {}).get('id', ''))
        if tracking.get('away', {}).get('status') == 'OFFICIAL':
            official_teams.add(away_team_id)
            for player in lineups.get('awayPlayers', []):
                active_starters.add(str(player.get('id')))

        # Process Home Team
        home_team_id = str(teams.get('home', {}).get('team', {}).get('id', ''))
        if tracking.get('home', {}).get('status') == 'OFFICIAL':
            official_teams.add(home_team_id)
            for player in lineups.get('homePlayers', []):
                active_starters.add(str(player.get('id')))

    return official_teams, active_starters

def process_notifications(active_users, official_teams, active_starters):
    """Evaluate watchlists, group alerts to prevent spam, and send push notifications."""
    master_data_path = os.path.join(REPO_ROOT, 'data', 'player_master_data.json')
    try:
        with open(master_data_path, 'r') as f:
            master_data = json.load(f)
    except FileNotFoundError:
        master_data = {}

    for uid, user_data in active_users.items():
        push_token = user_data.get('push_token')
        pref = user_data.get('preference', 'critical_only')
        watchlist = user_data.get('watchlist', {})
        notified_state = user_data.get('notified_state', {})

        if not push_token or not watchlist:
            continue

        # Temporary storage for this user's alerts during this pipeline run
        user_updates = {}
        scratches = []
        confirmed = []
        late_scratches = []
        late_adds = []

        for player_id, team_id in watchlist.items():
            team_id = str(team_id)
            
            # Guardrail: Do nothing if the team's lineup hasn't dropped yet
            if team_id not in official_teams:
                continue 

            is_starting = player_id in active_starters
            current_state = notified_state.get(player_id)
            player_name = master_data.get(player_id, {}).get('name', 'Your player')

            new_state = ""

            # Scenario 1: Player is IN the official lineup
            if is_starting and current_state != 'confirmed':
                if current_state == 'scratched':
                    late_adds.append(player_name)
                elif pref == 'full_coverage':
                    confirmed.append(player_name)
                
                new_state = 'confirmed'

            # Scenario 2: Player is NOT in the official lineup (Scratched)
            elif not is_starting and current_state != 'scratched':
                if current_state == 'confirmed':
                    late_scratches.append(player_name)
                else:
                    scratches.append(player_name)
                
                new_state = 'scratched'

            # Track the state change to update Firebase later
            if new_state and new_state != current_state:
                user_updates[player_id] = new_state

        # If nothing changed for this user, move to the next user
        if not user_updates:
            continue

        # Build the grouped notification body strings
        body_lines = []
        if late_scratches:
            body_lines.append("🚨 LATE SCRATCH: " + ", ".join(late_scratches))
        if scratches:
            body_lines.append("🚨 OUT: " + ", ".join(scratches))
        if late_adds:
            body_lines.append("✅ LATE ADD: " + ", ".join(late_adds))
        if confirmed:
            body_lines.append("✅ IN: " + ", ".join(confirmed))

        # Batch the lines so we don't exceed mobile lock screen limits (~200 chars)
        batched_messages = []
        current_batch = ""

        for line in body_lines:
            if len(current_batch) + len(line) > 200:
                batched_messages.append(current_batch.strip())
                current_batch = line + "\n"
            else:
                current_batch += line + "\n"
        
        if current_batch:
            batched_messages.append(current_batch.strip())

        # Fire the grouped notifications
        for i, body_text in enumerate(batched_messages):
            # If multiple batches, number the titles (e.g., 1/2)
            title = "MLB Lineup Alert" if len(batched_messages) == 1 else f"MLB Lineup Alert ({i+1}/{len(batched_messages)})"
            
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body_text),
                token=push_token,
                data={"url": "https://mlbstartingnine.com/"}
            )
            try:
                messaging.send(message)
                print(f"Sent batched alert {i+1} to {uid}")
            except Exception as e:
                print(f"Failed to send batched alert to {uid}: {e}")

        # Finally, update the database receipts for all processed players
        for pid, state in user_updates.items():
            db.reference(f'watchlist/{uid}/notified_state/{pid}').set(state)

if __name__ == "__main__":
    print("Starting MLB Lineup Notification Worker...")
    initialize_firebase()
    
    today = get_today_date_string()
    
    # 1. Clean the database
    active_users = clean_old_watchlists(today)
    
    # 2. Parse the daily JSON
    daily_json = load_daily_json(today)
    official_teams, active_starters = extract_official_lineups(daily_json)
    
    print(f"Teams with official lineups: {len(official_teams)}")
    print(f"Total active starters parsed: {len(active_starters)}")
    
    # 3. Process the state machine and send alerts
    process_notifications(active_users, official_teams, active_starters)
    print("Worker complete.")
