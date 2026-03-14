import requests
import json
import os
import time
from datetime import datetime, timedelta

# --- CONFIGURATION ---
DATA_DIR = 'data'
MATCHUPS_FILE = os.path.join(DATA_DIR, 'matchups.json')
UMPIRES_FILE = os.path.join(DATA_DIR, 'umpires.json')
PARKS_FILE = os.path.join(DATA_DIR, 'parks.json')

os.makedirs(DATA_DIR, exist_ok=True)

def get_active_sport_ids():
    current_date = datetime.utcnow().date()
    wbc_start = datetime(2026, 3, 4).date()
    wbc_end = datetime(2026, 3, 17).date()
    if wbc_start <= current_date <= wbc_end:
        return "1,51"
    return "1"

def load_json(path, default_val):
    if os.path.exists(path):
        try:
            with open(path, 'r') as f: return json.load(f)
        except Exception: pass
    return default_val

def save_cache(data):
    with open(MATCHUPS_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def fetch_bvp(session, batter_id, pitcher_id):
    url = f"https://statsapi.mlb.com/api/v1/people/{batter_id}/stats?stats=vsPlayer&opposingPlayerId={pitcher_id}&group=hitting&gameType=R"
    try:
        res = session.get(url, timeout=10).json()
        splits = res.get('stats', [{}])[0].get('splits', [])
        if splits:
            stat = splits[0].get('stat', {})
            return {
                "ab": stat.get('atBats', 0), "hits": stat.get('hits', 0),
                "hr": stat.get('homeRuns', 0), "avg": stat.get('avg', '.000'), "ops": stat.get('ops', '.000')
            }
    except Exception: pass
    return {"ab": 0, "hits": 0, "hr": 0, "avg": "-", "ops": "-"}

def fetch_combined_splits(session, person_id, hand_code, group_type="hitting"):
    current_year = datetime.utcnow().year
    years = [current_year - 1, current_year]
    totals = {"ab": 0, "h": 0, "2b": 0, "3b": 0, "hr": 0, "bb": 0, "hbp": 0, "sf": 0, "k": 0}
    
    for year in years:
        url = f"https://statsapi.mlb.com/api/v1/people/{person_id}/stats?stats=statSplits&sitCodes={hand_code}&group={group_type}&gameType=R&season={year}"
        try:
            res = session.get(url, timeout=10).json()
            splits = res.get('stats', [{}])[0].get('splits', [])
            if splits:
                stat = splits[0].get('stat', {})
                for key in totals.keys():
                    api_key = key if key in stat else 'atBats' if key == 'ab' else 'hits' if key == 'h' else 'doubles' if key == '2b' else 'triples' if key == '3b' else 'homeRuns' if key == 'hr' else 'baseOnBalls' if key == 'bb' else 'hitByPitch' if key == 'hbp' else 'sacFlies' if key == 'sf' else 'strikeOuts'
                    totals[key] += stat.get(api_key, 0)
        except Exception: pass
        time.sleep(0.05)
            
    ab, h, hr, bb, hbp, sf, k = totals["ab"], totals["h"], totals["hr"], totals["bb"], totals["hbp"], totals["sf"], totals["k"]
    avg = h / ab if ab > 0 else 0.0
    tb = (h - (totals["2b"] + totals["3b"] + hr)) + (2 * totals["2b"]) + (3 * totals["3b"]) + (4 * hr)
    slg = tb / ab if ab > 0 else 0.0
    obp = (h + bb + hbp) / (ab + bb + hbp + sf) if (ab + bb + hbp + sf) > 0 else 0.0
    ops = obp + slg
    
    avg_str = f"{avg:.3f}".replace("0.", ".")
    ops_str = f"{ops:.3f}".replace("0.", ".")
    if avg_str == ".000" and ab == 0: avg_str = "-"
    if ops_str == ".000" and ab == 0: ops_str = "-"
    
    split_label = "LHP" if hand_code == 'vl' else "RHP" if group_type == "hitting" else "LHB" if hand_code == 'vl' else "RHB"
    return {"split_type": split_label, "ab": ab, "hr": hr, "k": k, "bb": bb, "avg": avg_str, "ops": ops_str}

def main():
    today_obj = datetime.utcnow()
    start_date = (today_obj - timedelta(days=1)).strftime('%Y-%m-%d')
    end_date = (today_obj + timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"🚀 Building Master JSONs for window: {start_date} to {end_date}")
    
    session = requests.Session()
    session.headers.update({"User-Agent": "MLBStartingNine-DataBot/1.0"})
    
    # Load Caches & Static Data
    cache = load_json(MATCHUPS_FILE, {"games": {}, "handedness": {}})
    games_cache = cache.get('games', {})
    hand_cache = cache.get('handedness', {})
    ump_cache = load_json(UMPIRES_FILE, {}).get('umpires', {})
    park_cache = load_json(PARKS_FILE, {}).get('parks', {})
    
    # Fetch Odds
    try:
        odds_data = requests.get("https://weathermlb.com/data/odds.json", timeout=10).json().get('odds', [])
    except Exception:
        odds_data = []

    # Fetch Schedule
    sport_ids = get_active_sport_ids()
    schedule_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId={sport_ids}&startDate={start_date}&endDate={end_date}&hydrate=linescore,probablePitcher,lineups,person"
    try:
        schedule_data = session.get(schedule_url, timeout=15).json()
    except Exception as e:
        print(f"❌ Failed to fetch schedule: {e}")
        return

    valid_game_pks = set()
    master_dates = {}

    for date_item in schedule_data.get('dates', []):
        date_str = date_item['date']
        master_dates[date_str] = []
        
        for game in date_item.get('games', []):
            game_pk = str(game['gamePk'])
            valid_game_pks.add(game_pk)
            
            if game_pk not in games_cache: games_cache[game_pk] = {}

            teams = game.get('teams', {})
            away_team_name = teams.get('away', {}).get('team', {}).get('name', '')
            home_team_name = teams.get('home', {}).get('team', {}).get('name', '')
            
            # Match Odds
            game_odds = None
            game_time_ms = datetime.strptime(game['gameDate'], "%Y-%m-%dT%H:%M:%SZ").timestamp() * 1000
            potential_odds = [o for o in odds_data if o['home_team'] == home_team_name and o['away_team'] == away_team_name]
            if potential_odds:
                game_odds = sorted(potential_odds, key=lambda o: abs(datetime.strptime(o['commence_time'], "%Y-%m-%dT%H:%M:%SZ").timestamp() * 1000 - game_time_ms))[0]

            # Probable Pitchers & Deep Stats
            away_starter = teams.get('away', {}).get('probablePitcher')
            home_starter = teams.get('home', {}).get('probablePitcher')
            away_starter_id = str(away_starter.get('id')) if away_starter else None
            home_starter_id = str(home_starter.get('id')) if home_starter else None
            
            for p_id, p_data in [(away_starter_id, away_starter), (home_starter_id, home_starter)]:
                if p_id and p_id not in games_cache[game_pk]:
                    print(f"   [NEW] Fetching Pitcher Splits for {p_data['fullName']}...")
                    games_cache[game_pk][p_id] = {
                        "name": p_data['fullName'], "is_pitcher": True,
                        "split_vL": fetch_combined_splits(session, p_id, 'vl', group_type="pitching"),
                        "split_vR": fetch_combined_splits(session, p_id, 'vr', group_type="pitching")
                    }
                    save_cache(cache)

            lineups = game.get('lineups', {})
            away_lineup = lineups.get('awayPlayers', [])
            home_lineup = lineups.get('homePlayers', [])
            
            for batter in away_lineup:
                batter_id = str(batter['id'])
                if home_starter_id and batter_id not in games_cache[game_pk]:
                    games_cache[game_pk][batter_id] = {
                        "name": batter['fullName'], "bvp": fetch_bvp(session, batter_id, home_starter_id),
                        "split_vL": fetch_combined_splits(session, batter_id, 'vl'), "split_vR": fetch_combined_splits(session, batter_id, 'vr')
                    }
                    save_cache(cache)
            
            for batter in home_lineup:
                batter_id = str(batter['id'])
                if away_starter_id and batter_id not in games_cache[game_pk]:
                    games_cache[game_pk][batter_id] = {
                        "name": batter['fullName'], "bvp": fetch_bvp(session, batter_id, away_starter_id),
                        "split_vL": fetch_combined_splits(session, batter_id, 'vl'), "split_vR": fetch_combined_splits(session, batter_id, 'vr')
                    }
                    save_cache(cache)

            # Handedness Caching & Live Feed (Positions/Umpires)
            game_positions = {}
            hp_umpire = "TBD"
            ump_stats = None
            
            try:
                live_data = session.get(f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live", timeout=5).json()
                officials = live_data.get('liveData', {}).get('boxscore', {}).get('officials', [])
                hp = next((o for o in officials if o.get('officialType') == 'Home Plate'), None)
                if hp and hp.get('official'):
                    hp_umpire = hp['official']['fullName']
                    ump_stats = ump_cache.get(hp_umpire)

                box_teams = live_data.get('liveData', {}).get('boxscore', {}).get('teams', {})
                all_live_players = {**box_teams.get('away', {}).get('players', {}), **box_teams.get('home', {}).get('players', {})}
                
                for p_key, p_val in all_live_players.items():
                    pid = str(p_val.get('person', {}).get('id'))
                    # Extract Position
                    if p_val.get('allPositions'): game_positions[pid] = p_val['allPositions'][0].get('abbreviation')
                    elif p_val.get('position'): game_positions[pid] = p_val['position'].get('abbreviation')
                    # Extract & Cache Handedness
                    if p_val.get('person', {}).get('batSide'):
                        hand_cache[pid] = p_val['person']['batSide'].get('code')
            except Exception: pass

            # Re-map handedness for the frontend
            lineup_handedness = {pid: hand_cache.get(pid, "") for pid in [str(p['id']) for p in away_lineup + home_lineup]}

            # Final Unified Object!
            master_dates[date_str].append({
                "gameRaw": game,
                "odds": game_odds,
                "lineupHandedness": lineup_handedness,
                "gamePositions": game_positions,
                "deepStats": games_cache.get(game_pk, {}),
                "hpUmpire": hp_umpire,
                "umpStats": ump_stats,
                "parkStats": park_cache.get(game.get('venue', {}).get('name'))
            })

    # Purge stale cache
    cache['games'] = {pk: data for pk, data in games_cache.items() if pk in valid_game_pks}
    cache['handedness'] = hand_cache
    cache['last_updated'] = today_obj.strftime('%Y-%m-%d %H:%M:%S UTC')
    save_cache(cache)

    # Write the Daily JSON Files!
    daily_files_dir = os.path.join(DATA_DIR, 'daily_files')
    os.makedirs(daily_files_dir, exist_ok=True) # This creates the folder!
    
    for date_str, games_list in master_dates.items():
        # Notice we are using daily_files_dir here, not DATA_DIR
        daily_file = os.path.join(daily_files_dir, f'games_{date_str}.json')
        with open(daily_file, 'w') as f:
            json.dump(games_list, f, indent=4)
        print(f"✅ Created {daily_file} with {len(games_list)} games.")

if __name__ == "__main__":
    main()
