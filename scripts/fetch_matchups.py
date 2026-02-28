import requests
import json
import os
import time
from datetime import datetime

# --- CONFIGURATION ---
DATA_DIR = 'data'
MATCHUPS_FILE = os.path.join(DATA_DIR, 'matchups.json')
TODAY_STR = datetime.utcnow().strftime('%Y-%m-%d') # MLB API uses UTC dates natively

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

def load_cache():
    """Loads the existing matchups to use as a diff baseline."""
    if os.path.exists(MATCHUPS_FILE):
        try:
            with open(MATCHUPS_FILE, 'r') as f:
                data = json.load(f)
                # If the cache is from yesterday, wipe it clean for today
                if data.get('date') != TODAY_STR:
                    return {"date": TODAY_STR, "games": {}}
                return data
        except json.JSONDecodeError:
            pass
    return {"date": TODAY_STR, "games": {}}

def save_cache(data):
    """Saves the incremental progress to disk."""
    with open(MATCHUPS_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def fetch_bvp(session, batter_id, pitcher_id):
    """Fetches Batter vs Pitcher lifetime regular season stats."""
    url = f"https://statsapi.mlb.com/api/v1/people/{batter_id}/stats?stats=vsPlayer&opposingPlayerId={pitcher_id}&group=hitting&gameType=R"
    try:
        res = session.get(url, timeout=10)
        data = res.json()
        splits = data.get('stats', [{}])[0].get('splits', [])
        if splits:
            stat = splits[0].get('stat', {})
            return {
                "ab": stat.get('atBats', 0),
                "hits": stat.get('hits', 0),
                "hr": stat.get('homeRuns', 0),
                "avg": stat.get('avg', '.000'),
                "ops": stat.get('ops', '.000')
            }
    except Exception as e:
        print(f"Error fetching BvP for {batter_id} vs {pitcher_id}: {e}")
    
    # Return 0s if no history exists
    return {"ab": 0, "hits": 0, "hr": 0, "avg": "-", "ops": "-"}

def fetch_split(session, batter_id, hand_code):
    """Fetches Batter lifetime splits vs LHP or RHP."""
    # hand_code expected: 'vl' or 'vr'
    # Use 'careerStatSplits' instead of 'statSplits' to get lifetime data
    url = f"https://statsapi.mlb.com/api/v1/people/{batter_id}/stats?stats=careerStatSplits&sitCodes={hand_code}&group=hitting&gameType=R"
    try:
        res = session.get(url, timeout=10)
        data = res.json()
        splits = data.get('stats', [{}])[0].get('splits', [])
        if splits:
            stat = splits[0].get('stat', {})
            return {
                "split_type": "LHP" if hand_code == 'vl' else "RHP",
                "ab": stat.get('atBats', 0),
                "hr": stat.get('homeRuns', 0),
                "avg": stat.get('avg', '.000'),
                "ops": stat.get('ops', '.000')
            }
    except Exception as e:
        print(f"Error fetching splits for {batter_id}: {e}")
        
    return {"split_type": "LHP" if hand_code == 'vl' else "RHP", "ab": 0, "hr": 0, "avg": "-", "ops": "-"}

def main():
    print(f"🚀 Starting Matchup Fetcher for {TODAY_STR}")
    
    # 1. Open a persistent connection pool (Fast & Polite)
    session = requests.Session()
    session.headers.update({"User-Agent": "MLBStartingNine-DataBot/1.0"})
    
    # 2. Load our local saved data
    cache = load_cache()
    games_cache = cache['games']
    
    # 3. Get today's live schedule & lineups
    schedule_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={TODAY_STR}&hydrate=probablePitcher,lineups"
    try:
        schedule_res = session.get(schedule_url, timeout=15)
        schedule_data = schedule_res.json()
    except Exception as e:
        print(f"❌ Failed to fetch schedule: {e}")
        return

    if schedule_data.get('totalGames', 0) == 0:
        print("No games today. Exiting.")
        return

    games = schedule_data['dates'][0]['games']
    updates_made = False

    # 4. Loop through the games and perform the "Diff" check
    for game in games:
        game_pk = str(game['gamePk'])
        if game_pk not in games_cache:
            games_cache[game_pk] = {}

        teams = game.get('teams', {})
        
        # Get Starters
        away_starter = teams.get('away', {}).get('probablePitcher')
        home_starter = teams.get('home', {}).get('probablePitcher')
        
        # Determine Pitcher Handedness for Splits (vL or vR)
        away_starter_id = away_starter.get('id') if away_starter else None
        home_starter_id = home_starter.get('id') if home_starter else None
        
        # Note: If handedness isn't in this payload, we default to RHP for the split fallback 
        # (Though we can easily cross-reference this later, assuming RHP for safety on empty data)
        # However, the hydrate=person payload on the frontend gives us exact hands. 
        # For the script, we'll try to guess from the hand code if available, else standard split.
        
        lineups = game.get('lineups', {})
        away_lineup = lineups.get('awayPlayers', [])
        home_lineup = lineups.get('homePlayers', [])
        
        # --- PROCESS AWAY BATTERS (vs Home Starter) ---
        if home_starter_id:
            for batter in away_lineup:
                batter_id = str(batter['id'])
                # THE DIFF CHECK: Do we already have this batter saved for this game?
                if batter_id not in games_cache[game_pk]:
                    print(f"   [NEW] Fetching Away Batter {batter['fullName']} vs Pitcher {home_starter_id}...")
                    
                    bvp_stats = fetch_bvp(session, batter_id, home_starter_id)
                    # We will assume RHP fallback if hand isn't attached to probablePitcher object here
                    # To be ultra-safe, we just fetch 'vR' and 'vL' combined, or rely on frontend. Let's fetch vR for now.
                    # A more advanced version fetches the pitcher hand first. Let's just fetch both!
                    split_vL = fetch_split(session, batter_id, 'vL')
                    split_vR = fetch_split(session, batter_id, 'vR')
                    
                    games_cache[game_pk][batter_id] = {
                        "name": batter['fullName'],
                        "bvp": bvp_stats,
                        "split_vL": split_vL,
                        "split_vR": split_vR
                    }
                    updates_made = True
                    save_cache(cache) # Incremental save
                    time.sleep(0.2)   # Polite throttling

        # --- PROCESS HOME BATTERS (vs Away Starter) ---
        if away_starter_id:
            for batter in home_lineup:
                batter_id = str(batter['id'])
                if batter_id not in games_cache[game_pk]:
                    print(f"   [NEW] Fetching Home Batter {batter['fullName']} vs Pitcher {away_starter_id}...")
                    
                    bvp_stats = fetch_bvp(session, batter_id, away_starter_id)
                    split_vL = fetch_split(session, batter_id, 'vL')
                    split_vR = fetch_split(session, batter_id, 'vR')
                    
                    games_cache[game_pk][batter_id] = {
                        "name": batter['fullName'],
                        "bvp": bvp_stats,
                        "split_vL": split_vL,
                        "split_vR": split_vR
                    }
                    updates_made = True
                    save_cache(cache) # Incremental save
                    time.sleep(0.2)   # Polite throttling

    if updates_made:
        print("✅ Finished processing new lineups. Cache updated.")
    else:
        print("💤 No new lineups or scratches found. Zero BvP API calls made.")

if __name__ == "__main__":
    main()
