import os
import json
import requests
from datetime import datetime, timedelta
import pytz

# ==========================================
# 1. CONFIGURATION & THRESHOLDS
# ==========================================
BULLPEN_THRESHOLDS = {
    "UNAVAILABLE": {
        "consecutive_days": 3,
        "pitches_yesterday": 35,
        "pitches_last_2_days": 50,
        "pitches_last_3_days": 65
    },
    "TIRED": {
        "consecutive_days": 2,
        "pitches_yesterday": 20,
        "pitches_last_2_days": 35,
        "pitches_last_3_days": 45
    }
}

OUTPUT_PATH = "data/bullpen_data.json"
CURRENT_SEASON = 2026

# ==========================================
# 2. UTILITY & DATE FUNCTIONS
# ==========================================
def get_target_dates():
    """Returns today's date and the last 5 calendar days of actual game action."""
    est_tz = pytz.timezone('America/New_York')
    now_est = datetime.now(pytz.utc).astimezone(est_tz)
    
    if now_est.hour < 3:
        now_est -= timedelta(days=1)
        
    today = now_est.date()
    past_dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(1, 6)]
    return today, past_dates

def safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def convert_ip(ip_str):
    """Converts a baseball IP string (e.g., '3.1') to a decimal for accurate math."""
    if not ip_str: return 0.0
    parts = str(ip_str).split('.')
    full_innings = float(parts[0])
    partial = float(parts[1]) if len(parts) > 1 else 0.0
    if partial == 1: return full_innings + 0.33
    if partial == 2: return full_innings + 0.67
    return full_innings

# ==========================================
# 3. LEAGUE-WIDE DATA FETCHING
# ==========================================
def get_scheduled_probables(today):
    """Fetches the next 4 days of scheduled probable pitchers for the rookie exception."""
    future_date = today + timedelta(days=4)
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate={today.strftime('%Y-%m-%d')}&endDate={future_date.strftime('%Y-%m-%d')}&hydrate=probablePitcher"
    
    probables = set()
    try:
        data = requests.get(url, timeout=10).json()
        for date_node in data.get('dates', []):
            for game in date_node.get('games', []):
                away_p = game.get('teams', {}).get('away', {}).get('probablePitcher', {}).get('id')
                home_p = game.get('teams', {}).get('home', {}).get('probablePitcher', {}).get('id')
                if away_p: probables.add(away_p)
                if home_p: probables.add(home_p)
    except Exception as e:
        print(f"⚠️ Failed to fetch probable pitchers: {e}")
    return probables

def get_bullpen_rankings():
    """Fetches league-wide pitching stats (filtered for relievers) and generates rankings."""
    # Using the split parameter to isolate relief appearances
    url = f"https://statsapi.mlb.com/api/v1/teams/stats?season={CURRENT_SEASON}&sportIds=1&group=pitching&stats=statSplits&sitCodes=rp"
    
    raw_stats = {}
    try:
        data = requests.get(url, timeout=10).json()
        for split in data.get('stats', [{}])[0].get('splits', []):
            team_id = split.get('team', {}).get('id')
            stats = split.get('stat', {})
            if team_id:
                raw_stats[team_id] = {
                    "era": safe_float(stats.get('era', 9.99)),
                    "whip": safe_float(stats.get('whip', 9.99)),
                    "k_per_9": safe_float(stats.get('strikeoutsPer9Inn', 0)),
                    "bb_per_9": safe_float(stats.get('walksPer9Inn', 9.99)),
                    "hr_per_9": safe_float(stats.get('homeRunsPer9', 9.99)),
                    "baa": safe_float(stats.get('avg', .999)),
                    "saves": int(stats.get('saves', 0)),
                    "holds": int(stats.get('holds', 0)),
                    "blown_saves": int(stats.get('blownSaves', 0))
                }
    except Exception as e:
        print(f"⚠️ Failed to fetch team reliever stats: {e}")
        return {}

    # Define how each stat should be sorted (True = Higher is better)
    metrics = {
        "era": False, "whip": False, "k_per_9": True, 
        "bb_per_9": False, "hr_per_9": False, "baa": False,
        "saves": True, "holds": True, "blown_saves": False
    }
    
    rankings = {}
    for team_id in raw_stats.keys():
        rankings[team_id] = {}

    for metric, reverse_sort in metrics.items():
        sorted_teams = sorted(raw_stats.items(), key=lambda x: x[1][metric], reverse=reverse_sort)
        for rank_idx, (t_id, t_stats) in enumerate(sorted_teams):
            rankings[t_id][metric] = {
                "value": t_stats[metric],
                "rank": rank_idx + 1
            }
            
    return rankings

# ==========================================
# 4. PLAYER EVALUATION LOGIC
# ==========================================
def evaluate_reliever(player_id, past_dates, scheduled_probables):
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}?hydrate=stats(group=[pitching],type=[season,gameLog])"
    
    try:
        data = requests.get(url, timeout=10).json()
        person = data.get('people', [{}])[0]
        stats_list = person.get('stats', [])
        
        season_stats = {}
        game_log = []
        for s in stats_list:
            if s.get('type', {}).get('displayName') == "season":
                season_stats = s.get('splits', [{}])[0].get('stat', {})
            elif s.get('type', {}).get('displayName') == "gameLog":
                game_log = s.get('splits', [])

        # --- THE WORKLOAD FILTER ---
        games_played = int(season_stats.get('gamesPlayed', 0))
        games_started = int(season_stats.get('gamesStarted', 0))
        ip_total = convert_ip(season_stats.get('inningsPitched', '0.0'))
        
        # Check if any recent outing was an actual START with a high pitch count (>= 60 pitches)
        has_recent_starter_outing = False
        for log in game_log:
            g_stat = log.get('stat', {})
            was_start = int(g_stat.get('gamesStarted', 0)) == 1
            pitches = int(g_stat.get('numberOfPitches', 0))
            
            if was_start and pitches >= 60:
                has_recent_starter_outing = True
                break

        # 1. Low Sample Size Filter (3 or fewer appearances)
        if games_played <= 3:
            # If they STARTED a game and threw 60+ pitches, they are a rotation starter
            if has_recent_starter_outing:
                return None
                
            # If they haven't pitched yet, check if they are an announced probable starter
            if games_played == 0 and player_id in scheduled_probables:
                return None
                
            # If majority of their 1-3 appearances are starts averaging 3.0+ IP
            elif games_started > 0 and (games_started / games_played) >= 0.5 and (ip_total / games_played) >= 3.0:
                return None

        # 2. Established Pitchers (> 3 appearances)
        else:
            avg_ip = ip_total / games_played if games_played > 0 else 0
            start_ratio = games_started / games_played if games_played > 0 else 0
            
            # Filter out traditional starters (majority starts with 3.5+ IP avg) or recent heavy starter outings
            if (start_ratio >= 0.5 and avg_ip >= 3.5) or has_recent_starter_outing:
                return None

        # --- FATIGUE CALCULATION ---
        pitches_by_day = {d: 0 for d in past_dates}
        for log in game_log:
            g_date = log.get('date')
            if g_date in pitches_by_day:
                pitches_by_day[g_date] += int(log.get('stat', {}).get('numberOfPitches', 0))
                
        p_1 = pitches_by_day[past_dates[0]]  # Yesterday
        p_2 = pitches_by_day[past_dates[1]]  # 2 days ago
        p_3 = pitches_by_day[past_dates[2]]  # 3 days ago
        
        pitches_last_2_days = p_1 + p_2
        pitches_last_3_days = p_1 + p_2 + p_3
        
        consecutive = 0
        for d in past_dates:
            if pitches_by_day[d] > 0: consecutive += 1
            else: break
            
        recent_appearances = sum(1 for p in pitches_by_day.values() if p > 0)
            
        # Check against thresholds
        status = "Available"
        if (consecutive >= BULLPEN_THRESHOLDS["UNAVAILABLE"]["consecutive_days"] or 
            p_1 >= BULLPEN_THRESHOLDS["UNAVAILABLE"]["pitches_yesterday"] or
            pitches_last_2_days >= BULLPEN_THRESHOLDS["UNAVAILABLE"]["pitches_last_2_days"] or
            pitches_last_3_days >= BULLPEN_THRESHOLDS["UNAVAILABLE"]["pitches_last_3_days"]):
            status = "Unavailable"
        elif (consecutive >= BULLPEN_THRESHOLDS["TIRED"]["consecutive_days"] or 
              p_1 >= BULLPEN_THRESHOLDS["TIRED"]["pitches_yesterday"] or
              pitches_last_2_days >= BULLPEN_THRESHOLDS["TIRED"]["pitches_last_2_days"] or
              pitches_last_3_days >= BULLPEN_THRESHOLDS["TIRED"]["pitches_last_3_days"]):
            status = "Tired"

        return {
            "name": person.get('fullName'),
            "player_id": player_id,
            "status": status,
            "era": season_stats.get('era', '-'),
            "whip": season_stats.get('whip', '-'),
            "recent_appearances": recent_appearances,
            "pitches_last_5": [pitches_by_day[d] for d in past_dates]
        }

    except Exception as e:
        print(f"⚠️ Failed to evaluate player {player_id}: {e}")
        return None

# ==========================================
# 5. MAIN EXECUTION
# ==========================================
def main():
    print("⚾ Starting Bullpen Data Gathering Engine...")
    today, past_dates = get_target_dates()
    
    print("📅 Fetching scheduled probables (Rookie Exception)...")
    scheduled_probables = get_scheduled_probables(today)
    
    print("📊 Compiling league-wide bullpen rankings...")
    bullpen_rankings = get_bullpen_rankings()
    
    teams_url = "https://statsapi.mlb.com/api/v1/teams?sportId=1"
    teams_data = requests.get(teams_url).json().get('teams', [])
    
    final_payload = {}
    
    for team in teams_data:
        team_id = team['id']
        team_name = team['name']
        team_slug = team_name.lower().replace('.', '').replace(' ', '-')
        print(f"   🔍 Processing: {team_name}")
        
        roster_url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster"
        try:
            roster_data = requests.get(roster_url).json().get('roster', [])
        except:
            continue
            
        active_relievers = []
        for player in roster_data:
            if player.get('position', {}).get('abbreviation') == 'P':
                player_id = player.get('person', {}).get('id')
                eval_result = evaluate_reliever(player_id, past_dates, scheduled_probables)
                if eval_result:
                    active_relievers.append(eval_result)
                    
        # Sort so Available arms appear at the top of the heat map
        active_relievers.sort(key=lambda x: (x['status'] != 'Available', x['status'] != 'Tired'))

        final_payload[team_slug] = {
            "team": team_name,
            "team_id": team_id,
            "bullpen_stats": bullpen_rankings.get(team_id, {}),
            "active_relievers": active_relievers
        }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(final_payload, f, indent=2)
        
    print(f"✅ Bullpen data successfully dumped to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
