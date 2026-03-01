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
        pass
    
    return {"ab": 0, "hits": 0, "hr": 0, "avg": "-", "ops": "-"}

def fetch_combined_splits(session, person_id, hand_code, group_type="hitting"):
    """
    Fetches splits for Last Season + Current Season, aggregates them, 
    and manually calculates the combined AVG and OPS for maximum accuracy.
    """
    current_year = datetime.utcnow().year
    years = [current_year - 1, current_year]
    
    totals = {
        "ab": 0, "h": 0, "2b": 0, "3b": 0, "hr": 0, 
        "bb": 0, "hbp": 0, "sf": 0, "k": 0
    }
    
    for year in years:
        url = f"https://statsapi.mlb.com/api/v1/people/{person_id}/stats?stats=statSplits&sitCodes={hand_code}&group={group_type}&gameType=R&season={year}"
        try:
            res = session.get(url, timeout=10)
            data = res.json()
            splits = data.get('stats', [{}])[0].get('splits', [])
            if splits:
                stat = splits[0].get('stat', {})
                totals["ab"] += stat.get('atBats', 0)
                totals["h"] += stat.get('hits', 0)
                totals["2b"] += stat.get('doubles', 0)
                totals["3b"] += stat.get('triples', 0)
                totals["hr"] += stat.get('homeRuns', 0)
                totals["bb"] += stat.get('baseOnBalls', 0)
                totals["hbp"] += stat.get('hitByPitch', 0)
                totals["sf"] += stat.get('sacFlies', 0)
                totals["k"] += stat.get('strikeOuts', 0)
        except Exception:
            pass
        
        time.sleep(0.05) # Polite internal throttle
            
    # Calculate Official MLB Rates
    ab = totals["ab"]
    h = totals["h"]
    hr = totals["hr"]
    bb = totals["bb"]
    hbp = totals["hbp"]
    sf = totals["sf"]
    k = totals["k"]
    
    if ab > 0:
        avg = h / ab
        single = h - (totals["2b"] + totals["3b"] + hr)
        tb = single + (2 * totals["2b"]) + (3 * totals["3b"]) + (4 * hr)
        slg = tb / ab
    else:
        avg = 0.0
        slg = 0.0
        
    obp_denom = ab + bb + hbp + sf
    if obp_denom > 0:
        obp = (h + bb + hbp) / obp_denom
    else:
        obp = 0.0
        
    ops = obp + slg
    
    # Format strings for the frontend (e.g., 0.250 -> .250)
    avg_str = f"{avg:.3f}".replace("0.", ".")
    ops_str = f"{ops:.3f}".replace("0.", ".")
    if avg_str == ".000" and ab == 0: avg_str = "-"
    if ops_str == ".000" and ab == 0: ops_str = "-"
    
    split_label = ""
    if group_type == "hitting":
        split_label = "LHP" if hand_code == 'vl' else "RHP"
    else:
        split_label = "LHB" if hand_code == 'vl' else "RHB"
        
    return {
        "split_type": split_label,
        "ab": ab,
        "hr": hr,
        "k": k,    
        "bb": bb,  
        "avg": avg_str,
        "ops": ops_str
    }

def main():
    print(f"🚀 Starting Matchup Fetcher for {TODAY_STR}")
    
    session = requests.Session()
    session.headers.update({"User-Agent": "MLBStartingNine-DataBot/1.0"})
    
    cache = load_cache()
    games_cache = cache['games']
    
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

    for game in games:
        game_pk = str(game['gamePk'])
        if game_pk not in games_cache:
            games_cache[game_pk] = {}

        teams = game.get('teams', {})
        
        away_starter = teams.get('away', {}).get('probablePitcher')
        home_starter = teams.get('home', {}).get('probablePitcher')
        
        away_starter_id = str(away_starter.get('id')) if away_starter else None
        home_starter_id = str(home_starter.get('id')) if home_starter else None
        
        # --- PROCESS STARTING PITCHERS ---
        for p_id, p_data in [(away_starter_id, away_starter), (home_starter_id, home_starter)]:
            if p_id and p_id not in games_cache[game_pk]:
                print(f"   [NEW] Fetching Pitcher Splits for {p_data['fullName']}...")
                games_cache[game_pk][p_id] = {
                    "name": p_data['fullName'],
                    "is_pitcher": True,
                    "split_vL": fetch_combined_splits(session, p_id, 'vl', group_type="pitching"),
                    "split_vR": fetch_combined_splits(session, p_id, 'vr', group_type="pitching")
                }
                updates_made = True
                save_cache(cache)
                time.sleep(0.2)

        lineups = game.get('lineups', {})
        away_lineup = lineups.get('awayPlayers', [])
        home_lineup = lineups.get('homePlayers', [])
        
        # --- PROCESS AWAY BATTERS (vs Home Starter) ---
        if home_starter_id:
            for batter in away_lineup:
                batter_id = str(batter['id'])
                if batter_id not in games_cache[game_pk]:
                    print(f"   [NEW] Fetching Away Batter {batter['fullName']} vs Pitcher {home_starter_id}...")
                    
                    bvp_stats = fetch_bvp(session, batter_id, home_starter_id) 
                    split_vL = fetch_combined_splits(session, batter_id, 'vl', group_type="hitting")
                    split_vR = fetch_combined_splits(session, batter_id, 'vr', group_type="hitting")
                    
                    games_cache[game_pk][batter_id] = {
                        "name": batter['fullName'],
                        "bvp": bvp_stats,
                        "split_vL": split_vL,
                        "split_vR": split_vR
                    }
                    updates_made = True
                    save_cache(cache) 
                    time.sleep(0.2)   

        # --- PROCESS HOME BATTERS (vs Away Starter) ---
        if away_starter_id:
            for batter in home_lineup:
                batter_id = str(batter['id'])
                if batter_id not in games_cache[game_pk]:
                    print(f"   [NEW] Fetching Home Batter {batter['fullName']} vs Pitcher {away_starter_id}...")
                    
                    bvp_stats = fetch_bvp(session, batter_id, away_starter_id) 
                    split_vL = fetch_combined_splits(session, batter_id, 'vl', group_type="hitting")
                    split_vR = fetch_combined_splits(session, batter_id, 'vr', group_type="hitting")
                    
                    games_cache[game_pk][batter_id] = {
                        "name": batter['fullName'],
                        "bvp": bvp_stats,
                        "split_vL": split_vL,
                        "split_vR": split_vR
                    }
                    updates_made = True
                    save_cache(cache) 
                    time.sleep(0.2)   

    if updates_made:
        print("✅ Finished processing new lineups. Cache updated.")
    else:
        print("💤 No new lineups or scratches found. Zero BvP API calls made.")

if __name__ == "__main__":
    main()
