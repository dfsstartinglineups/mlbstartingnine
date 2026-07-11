import os
import json
import time
import requests
from datetime import datetime, timedelta

# --- CONFIGURATION ---
DATA_DIR = 'data'
LIVE_DIR = os.path.join(DATA_DIR, 'LIVE')  # Keeps yesterday's live game logs lookup path intact
MASTER_STATS_FILE = os.path.join(DATA_DIR, 'player_master_data.json')  # Updated destination path 🚀

os.makedirs(LIVE_DIR, exist_ok=True)

# ==========================================
# --- CORE DATA FETCHERS (MLB API) ---
# ==========================================
def fetch_mlb_season_and_splits(session, player_id, group_type="hitting"):
    """
    Queries MLB API to compile season totals alongside left/right splits 
    for the current calendar year.
    """
    current_year = datetime.utcnow().year
    stats_profile = {
        "season": {"ab": 0, "hits": 0, "hr": 0, "rbi": 0, "sb": 0, "avg": "-", "obp": "-", "ops": "-"},
        "split_vL": {"ab": 0, "hr": 0, "avg": "-", "ops": "-"},
        "split_vR": {"ab": 0, "hr": 0, "avg": "-", "ops": "-"}
    }
    
    # 1. Fetch Year Totals
    season_url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=season&group={group_type}&gameType=R&season={current_year}"
    try:
        res = session.get(season_url, timeout=8).json()
        splits = res.get('stats', [{}])[0].get('splits', [])
        if splits:
            stat = splits[0].get('stat', {})
            if group_type == "hitting":
                stats_profile["season"] = {
                    "ab": stat.get('atBats', 0),
                    "hits": stat.get('hits', 0),
                    "hr": stat.get('homeRuns', 0),
                    "rbi": stat.get('rbi', 0),
                    "sb": stat.get('stolenBases', 0),
                    "avg": stat.get('avg', '-'),
                    "obp": stat.get('obp', '-'),
                    "ops": stat.get('ops', '-')
                }
            else:
                stats_profile["season"] = {
                    "ip": stat.get('inningsPitched', '0.0'),
                    "w": stat.get('wins', 0),
                    "l": stat.get('losses', 0),
                    "era": stat.get('era', '-'),
                    "whip": stat.get('whip', '-'),
                    "k": stat.get('strikeOuts', 0)
                }
    except Exception:
        pass

    # 2. Fetch Handedness Platoon Splits
    for sit_code, target_key in [('vl', 'split_vL'), ('vr', 'split_vR')]:
        split_url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=statSplits&sitCodes={sit_code}&group={group_type}&gameType=R&season={current_year}"
        try:
            res = session.get(split_url, timeout=8).json()
            splits = res.get('stats', [{}])[0].get('splits', [])
            if splits:
                stat = splits[0].get('stat', {})
                stats_profile[target_key] = {
                    "ab": stat.get('atBats' if group_type == "hitting" else 'battersFaced', 0),
                    "hr": stat.get('homeRuns', 0),
                    "avg": stat.get('avg', '-'),
                    "ops": stat.get('ops', '-')
                }
        except Exception:
            pass
        time.sleep(0.05) # Polite throttle pacing

    return stats_profile

# ==========================================
# --- PROCESSING ENGINE ---
# ==========================================
def main():
    session = requests.Session()
    session.headers.update({"User-Agent": "MLBStartingNine-OvernightLogBot/1.0"})

    # 1. Establish Processing Windows (Target Yesterday's Finalized Action)
    yesterday_str = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
    live_file_name = f"live_mlb_{yesterday_str}.json"
    live_file_path = os.path.join(LIVE_DIR, live_file_name)

    print(f"🔄 Starting overnight sync loop using reference file: {live_file_path}")

    if not os.path.exists(live_file_path):
        print(f"🛑 Aborting: Finalized log target '{live_file_name}' not found on server.")
        return

    # 2. Open Persistent State Base Dictionary
    if os.path.exists(MASTER_STATS_FILE):
        with open(MASTER_STATS_FILE, 'r') as f:
            master_registry = json.load(f)
    else:
        master_registry = {}

    # 3. Read Yesterday's Final Stats
    with open(live_file_path, 'r') as f:
        yesterday_live_data = json.load(f)

    # Track distinct active entries handled to throttle batch API requests
    updated_players_count = 0

    for game_id, game_ctx in yesterday_live_data.items():
        if game_ctx.get("status") != "Final":
            print(f"⚠️ Warning: Game {game_id} is not marked Final. Processing metrics anyway.")

        players_box = game_ctx.get("players", {})
        all_game_players = {**players_box.get("AWAY", {}), **players_box.get("HOME", {})}

    	# Iterate through every player record from yesterday's slate
        for api_id_key, player_data in all_game_players.items():
            player_id = api_id_key.replace("ID", "")
            player_name = player_data.get("name")
            
            # Determine role context maps
            is_pitcher = player_data.get("batting") is None
            stats_block = player_data.get("pitching") if is_pitcher else player_data.get("batting")

            # Verify if player actually logged action lines
            if not stats_block or not stats_block.get("summary"):
                continue

            game_summary_line = stats_block.get("summary")
            dk_score = player_data.get("dk_pts", 0.0)
            fd_score = player_data.get("fd_pts", 0.0)

            # Initialize completely new entries inside master registry securely
            if api_id_key not in master_registry:
                master_registry[api_id_key] = {
                    "player_id": player_id,
                    "name": player_name,
                    "is_pitcher": is_pitcher,
                    "season": {},
                    "split_vL": {},
                    "split_vR": {},
                    "game_log": []
                }

            # 4. Check for duplicate logs before appending
            existing_log = master_registry[api_id_key].get("game_log", [])
            if any(log.get("date") == yesterday_str for log in existing_log):
                print(f"⏩ Line entry for {player_name} on {yesterday_str} already exists. Skipping log insertion.")
            else:
                # Append new historical line element
                new_log_entry = {
                    "date": yesterday_str,
                    "summary": game_summary_line,
                    "dk_pts": dk_score,
                    "fd_pts": fd_score
                }
                existing_log.append(new_log_entry)
                
                # Re-sort chronological tracking (newest date first) and slice down to standard 10 logs
                existing_log.sort(key=lambda x: x['date'], reverse=True)
                master_registry[api_id_key]["game_log"] = existing_log[:10]

            # 5. Call MLB API to update cumulative statistics
            print(f"   📊 Refreshing seasonal cumulative splits tracking for: {player_name}")
            role_label = "pitching" if is_pitcher else "hitting"
            updated_stats = fetch_mlb_season_and_splits(session, player_id, group_type=role_label)
            
            master_registry[api_id_key]["season"] = updated_stats["season"]
            master_registry[api_id_key]["split_vL"] = updated_stats["split_vL"]
            master_registry[api_id_key]["split_vR"] = updated_stats["split_vR"]
            
            updated_players_count += 1
            time.sleep(0.1) # Safe spacing API gate protection

    # 6. Save data structure state back to disk
    with open(MASTER_STATS_FILE, 'w') as f:
        json.dump(master_registry, f, indent=4)

    print("\n" + "="*40)
    print(f"🏁 MASTER BUILD COMPLETE: {updated_players_count} Active Profiles Refreshed.")
    print("="*40)

if __name__ == "__main__":
    main()
