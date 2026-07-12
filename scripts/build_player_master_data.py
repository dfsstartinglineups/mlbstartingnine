import os
import json
import time
import requests
from datetime import datetime, timedelta

# --- CONFIGURATION ---
DATA_DIR = 'data'
LIVE_DIR = os.path.join(DATA_DIR, 'LIVE')
MASTER_STATS_FILE = os.path.join(DATA_DIR, 'player_master_data.json')

os.makedirs(LIVE_DIR, exist_ok=True)

# ==========================================
# --- CORE DATA FETCHERS (MLB API) ---
# ==========================================
def fetch_all_active_rosters(session):
    """
    Hits the MLB API for all 30 teams and grabs their 40-man rosters.
    Returns a dictionary of all active players with their team and position data.
    """
    print("⚾ Fetching all 30 MLB team rosters...")
    players = {}
    teams_url = "https://statsapi.mlb.com/api/v1/teams?sportId=1"
    
    try:
        teams_res = session.get(teams_url, timeout=10).json()
        for team in teams_res.get('teams', []):
            team_id = team['id']
            team_name = team['name']
            
            # Fetch the 40-Man roster for each team
            roster_url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster/40Man"
            roster_res = session.get(roster_url, timeout=10).json()
            
            for p in roster_res.get('roster', []):
                pid = str(p['person']['id'])
                players[pid] = {
                    "name": p['person']['fullName'],
                    "team_id": team_id,
                    "team_name": team_name,
                    "position": p['position']['name'],
                    "is_pitcher": p['position']['abbreviation'] == 'P'
                }
            time.sleep(0.05) # Polite pacing to not overload the MLB servers
    except Exception as e:
        print(f"❌ Error fetching rosters: {e}")
    
    print(f"✅ Successfully loaded {len(players)} players from official rosters.")
    return players

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
        time.sleep(0.05) 

    return stats_profile

# ==========================================
# --- PROCESSING ENGINE ---
# ==========================================
def main():
    session = requests.Session()
    session.headers.update({"User-Agent": "MLBStartingNine-OvernightLogBot/2.0"})

    if os.path.exists(MASTER_STATS_FILE):
        with open(MASTER_STATS_FILE, 'r') as f:
            master_registry = json.load(f)
    else:
        master_registry = {}

    # 1. Gather Yesterday's Game Logs for Fantasy Points
    yesterday_str = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
    live_file_name = f"live_mlb_{yesterday_str}.json"
    live_file_path = os.path.join(LIVE_DIR, live_file_name)

    yesterday_performances = {}
    if os.path.exists(live_file_path):
        print(f"📖 Reading live logs to extract fantasy points from: {live_file_name}")
        with open(live_file_path, 'r') as f:
            yesterday_live_data = json.load(f)
            
        for game_id, game_ctx in yesterday_live_data.items():
            players_box = game_ctx.get("players", {})
            all_game_players = {**players_box.get("AWAY", {}), **players_box.get("HOME", {})}
            
            for api_id_key, player_data in all_game_players.items():
                pid = api_id_key.replace("ID", "")
                is_pitcher = player_data.get("batting") is None
                stats_block = player_data.get("pitching") if is_pitcher else player_data.get("batting")
                
                if stats_block and stats_block.get("summary"):
                    yesterday_performances[pid] = {
                        "name": player_data.get("name", "Unknown"),
                        "summary": stats_block.get("summary"),
                        "dk_pts": player_data.get("dk_pts", 0.0),
                        "fd_pts": player_data.get("fd_pts", 0.0),
                        "is_pitcher": is_pitcher
                    }
    else:
        print(f"⚠️ Live log target '{live_file_name}' not found. Skipping fantasy points logging.")

    # 2. Grab the full league roster
    roster_players = fetch_all_active_rosters(session)

    # 3. Combine roster players and anyone who played yesterday (in case they were just sent down)
    all_target_ids = set(roster_players.keys()).union(set(yesterday_performances.keys()))

    print(f"🔄 Commencing deep-stat updates for {len(all_target_ids)} total players...")
    updated_players_count = 0

    for player_id in all_target_ids:
        api_id_key = f"ID{player_id}"
        
        # Determine player meta context safely
        if player_id in roster_players:
            meta = roster_players[player_id]
        else:
            # Fallback for players who played yesterday but are no longer on a 40-man roster today
            meta = {
                "name": yesterday_performances[player_id]["name"],
                "team_id": master_registry.get(api_id_key, {}).get("team_id"),
                "team_name": master_registry.get(api_id_key, {}).get("team_name", "Free Agent/Minors"),
                "position": master_registry.get(api_id_key, {}).get("position", "Unknown"),
                "is_pitcher": yesterday_performances[player_id]["is_pitcher"]
            }

        # Initialize missing players
        if api_id_key not in master_registry:
            master_registry[api_id_key] = {
                "player_id": player_id,
                "name": meta["name"],
                "team_id": meta["team_id"],
                "team_name": meta["team_name"],
                "position": meta["position"],
                "is_pitcher": meta["is_pitcher"],
                "season": {},
                "split_vL": {},
                "split_vR": {},
                "game_log": []
            }
        else:
            # Update meta in case of mid-season trades or position changes
            if meta.get("team_id"):
                master_registry[api_id_key]["team_id"] = meta["team_id"]
                master_registry[api_id_key]["team_name"] = meta["team_name"]
            if meta.get("position"):
                master_registry[api_id_key]["position"] = meta["position"]

        # 4. Check if they played yesterday and need a log update
        if player_id in yesterday_performances:
            existing_log = master_registry[api_id_key].get("game_log", [])
            # Prevent duplicate logging if action is re-run
            if not any(log.get("date") == yesterday_str for log in existing_log):
                new_log_entry = {
                    "date": yesterday_str,
                    "summary": yesterday_performances[player_id]["summary"],
                    "dk_pts": yesterday_performances[player_id]["dk_pts"],
                    "fd_pts": yesterday_performances[player_id]["fd_pts"]
                }
                existing_log.append(new_log_entry)
                
                # Re-sort chronological tracking (newest date first) and slice down to standard 10 logs
                existing_log.sort(key=lambda x: x['date'], reverse=True)
                master_registry[api_id_key]["game_log"] = existing_log[:10]

        # 5. Call MLB API to update cumulative statistics
        role_label = "pitching" if meta["is_pitcher"] else "hitting"
        updated_stats = fetch_mlb_season_and_splits(session, player_id, group_type=role_label)
        
        master_registry[api_id_key]["season"] = updated_stats["season"]
        master_registry[api_id_key]["split_vL"] = updated_stats["split_vL"]
        master_registry[api_id_key]["split_vR"] = updated_stats["split_vR"]
        
        updated_players_count += 1
        
        # Log progress so GitHub Actions doesn't look frozen
        if updated_players_count % 100 == 0:
            print(f"   ... processed {updated_players_count} players ...")

    # 6. Save data structure state back to disk
    with open(MASTER_STATS_FILE, 'w') as f:
        json.dump(master_registry, f, indent=4)

    print("\n" + "="*40)
    print(f"🏁 MASTER BUILD COMPLETE: {updated_players_count} Active Profiles Refreshed.")
    print("="*40)

if __name__ == "__main__":
    main()
