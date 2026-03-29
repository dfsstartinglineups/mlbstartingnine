import json
import os
import requests
import zoneinfo
from datetime import datetime, timedelta

# ==========================================================
# --- FOLDER SETUP ---
# ==========================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'LIVE')

# Ensure the data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

HEADERS = {'User-Agent': 'Mozilla/5.0'}

# ==========================================================
# --- DFS SCORING CALCULATORS ---
# ==========================================================
def calc_hitter_dfs(stats):
    """Calculates DK and FD points for hitters"""
    dk = 0.0
    fd = 0.0
    
    if not stats: return dk, fd
    
    h = stats.get('hits', 0)
    d = stats.get('doubles', 0)
    t = stats.get('triples', 0)
    hr = stats.get('homeRuns', 0)
    s = h - d - t - hr # Singles
    
    rbi = stats.get('rbi', 0)
    r = stats.get('runs', 0)
    bb = stats.get('baseOnBalls', 0)
    hbp = stats.get('hitByPitch', 0)
    sb = stats.get('stolenBases', 0)

    # DraftKings Hitting: 1B=3, 2B=5, 3B=8, HR=10, RBI=2, R=2, BB=2, HBP=2, SB=5
    dk = (s*3) + (d*5) + (t*8) + (hr*10) + (rbi*2) + (r*2) + (bb*2) + (hbp*2) + (sb*5)
    
    # FanDuel Hitting: 1B=3, 2B=6, 3B=9, HR=12, RBI=3.2, R=3.2, BB=3, HBP=3, SB=6
    fd = (s*3) + (d*6) + (t*9) + (hr*12) + (rbi*3.2) + (r*3.2) + (bb*3) + (hbp*3) + (sb*6)
    
    return round(dk, 2), round(fd, 2)

def calc_pitcher_dfs(stats):
    """Calculates DK and FD points for pitchers"""
    dk = 0.0
    fd = 0.0
    
    if not stats: return dk, fd
    
    outs = stats.get('outs', 0)
    k = stats.get('strikeOuts', 0)
    er = stats.get('earnedRuns', 0)
    w = stats.get('wins', 0)
    
    hits_allowed = stats.get('hits', 0)
    bb_allowed = stats.get('baseOnBalls', 0)
    hbp_allowed = stats.get('hitByPitch', 0)
    
    # Complete Game / No Hitter / Shutout bonuses (Rare, but included for DK)
    cg = stats.get('completeGames', 0)
    sho = stats.get('shutouts', 0)

    # DraftKings Pitching: Out=0.75, K=2, W=4, ER=-2, Hit=-0.6, BB=-0.6, HBP=-0.6, CG=2.5, CGSO=2.5, NH=2.5 (Skipping NH for simplicity unless 9IP 0H)
    dk = (outs * 0.75) + (k * 2) + (w * 4) + (er * -2) + (hits_allowed * -0.6) + (bb_allowed * -0.6) + (hbp_allowed * -0.6)
    if cg > 0: dk += 2.5
    if sho > 0: dk += 2.5
    
    # FanDuel Pitching: Out=1, K=3, W=6, ER=-3, QS=4
    fd = (outs * 1) + (k * 3) + (w * 6) + (er * -3)
    
    # FD Quality Start: 6+ IP (18+ outs) and 3 or fewer ER
    if outs >= 18 and er <= 3:
        fd += 4
        
    return round(dk, 2), round(fd, 2)

# ==========================================================
# --- MAIN LIVE SCRAPER ---
# ==========================================================
def scrape_live_games():
    ny_tz = zoneinfo.ZoneInfo("America/New_York")
    now_est = datetime.now(ny_tz)
    date_str = now_est.strftime('%Y-%m-%d')
    
    # 1. Get today's schedule to find the gamePks
    sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
    print(f"Fetching schedule for {date_str}...")
    
    try:
        sched_res = requests.get(sched_url, headers=HEADERS, timeout=10).json()
    except Exception as e:
        print(f"Failed to fetch schedule: {e}")
        return

    dates = sched_res.get('dates', [])
    if not dates:
        print("No games scheduled today.")
        return
        
    games = dates[0].get('games', [])
    
    live_data_dict = {}
    
    # 2. Loop through each game and fetch its live feed
    for game in games:
        game_pk = str(game['gamePk'])
        abstract_state = game.get('status', {}).get('abstractGameState', 'Preview')
        detailed_state = game.get('status', {}).get('detailedState', '')
        
        away_abbr = game['teams']['away']['team'].get('abbreviation', 'AWAY')
        home_abbr = game['teams']['home']['team'].get('abbreviation', 'HOME')
        
        # Don't hit the live feed if it hasn't started yet and isn't delayed
        if abstract_state == 'Preview' and 'Delayed' not in detailed_state:
            continue
            
        print(f"  > Fetching live feed for {away_abbr} @ {home_abbr} ({game_pk})...")
        live_url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
        
        try:
            live_res = requests.get(live_url, headers=HEADERS, timeout=10).json()
            game_data = live_res.get('gameData', {})
            live_data = live_res.get('liveData', {})
            
            # --- Linescore & Game State ---
            linescore = live_data.get('linescore', {})
            plays = live_data.get('plays', {})
            
            current_inning = linescore.get('currentInningOrdinal', '')
            inning_half = linescore.get('inningHalf', '')
            outs = linescore.get('outs', 0)
            
            away_score = linescore.get('teams', {}).get('away', {}).get('runs', 0)
            home_score = linescore.get('teams', {}).get('home', {}).get('runs', 0)
            
            # Base Runners
            offense = linescore.get('offense', {})
            bases = {
                "1B": 'first' in offense,
                "2B": 'second' in offense,
                "3B": 'third' in offense
            }
            
            # Current Play Text
            current_play = plays.get('currentPlay', {}).get('result', {}).get('description', '')
            
            # --- Build the Live Object ---
            game_obj = {
                "status": abstract_state,
                "detailed_status": detailed_state,
                "inning": current_inning,
                "half": inning_half,
                "outs": outs,
                "away_score": away_score,
                "home_score": home_score,
                "bases": bases,
                "current_play": current_play,
                "players": {}
            }
            
            # --- Parse Boxscore for DFS Points ---
            boxscore = live_data.get('boxscore', {}).get('teams', {})
            
            for team_side, abbr in [('away', away_abbr), ('home', home_abbr)]:
                game_obj["players"][abbr] = {}
                team_players = boxscore.get(team_side, {}).get('players', {})
                
                for pid, p_data in team_players.items():
                    name = p_data.get('person', {}).get('fullName', 'Unknown')
                    b_stats = p_data.get('stats', {}).get('batting', {})
                    p_stats = p_data.get('stats', {}).get('pitching', {})
                    
                    # Check if they actually played
                    if b_stats.get('plateAppearances', 0) > 0 or p_stats.get('battersFaced', 0) > 0:
                        hit_dk, hit_fd = calc_hitter_dfs(b_stats)
                        pitch_dk, pitch_fd = calc_pitcher_dfs(p_stats)
                        
                        # Add them together (Pitchers get hitting points too if they hit!)
                        total_dk = hit_dk + pitch_dk
                        total_fd = hit_fd + pitch_fd
                        
                        game_obj["players"][abbr][pid] = {
                            "name": name,
                            "dk_pts": total_dk,
                            "fd_pts": total_fd,
                            "batting": b_stats if b_stats.get('plateAppearances', 0) > 0 else None,
                            "pitching": p_stats if p_stats.get('battersFaced', 0) > 0 else None
                        }
            
            live_data_dict[game_pk] = game_obj
            
        except Exception as e:
            print(f"  [!] Error processing {game_pk}: {e}")

    # 3. Save the payload
    if live_data_dict:
        file_path = os.path.join(DATA_DIR, f"live_mlb_{date_str}.json")
        with open(file_path, 'w') as f:
            json.dump(live_data_dict, f, indent=2)
        print(f"\n✅ Successfully saved live data for {len(live_data_dict)} games to {file_path}")

if __name__ == "__main__":
    scrape_live_games()
