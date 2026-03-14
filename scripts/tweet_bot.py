import os
import json
import requests
import tweepy
import zoneinfo
from datetime import datetime, timezone, timedelta
import time
import os  # Make sure this is imported at the top!
import random

def save_memory_safely(memory_data):
    """Safely writes to the log file using a temporary file to prevent corruption."""
    temp_file = f"{LOG_FILE}.tmp"
    with open(temp_file, 'w') as f:
        json.dump(memory_data, f, indent=4)
    os.replace(temp_file, LOG_FILE) # This atomic swap is instant and crash-proof


# ==========================================
# 1. AUTHENTICATE WITH X (TWITTER)
# ==========================================

# MLB Client (Main Account)
mlb_client = tweepy.Client(
    consumer_key=os.environ.get("X_API_KEY"),
    consumer_secret=os.environ.get("X_API_SECRET"),
    access_token=os.environ.get("X_ACCESS_TOKEN"),
    access_token_secret=os.environ.get("X_ACCESS_TOKEN_SECRET")
)

# NBA Client (@DailyNBAlineups)
nba_client = tweepy.Client(
    consumer_key=os.environ.get("NBA_X_API_KEY"),
    consumer_secret=os.environ.get("NBA_X_API_SECRET"),
    access_token=os.environ.get("NBA_X_ACCESS_TOKEN"),
    access_token_secret=os.environ.get("NBA_X_ACCESS_TOKEN_SECRET")
)

# Futbol Client (@FutbolStarting11 - Using existing SerieA Env Vars)
futbol_client = tweepy.Client(
    consumer_key=os.environ.get("SERIEA_X_API_KEY"),
    consumer_secret=os.environ.get("SERIEA_X_API_SECRET"),
    access_token=os.environ.get("SERIEA_X_ACCESS_TOKEN"),
    access_token_secret=os.environ.get("SERIEA_X_ACCESS_TOKEN_SECRET")
)

# ==========================================
# 2. SETUP DATES & FILE PATHS
# ==========================================

# Automatically handles EST/EDT shifts
today_est = datetime.now(zoneinfo.ZoneInfo("America/New_York"))
date_str = today_est.strftime('%Y-%m-%d')
game_date_short = f"{today_est.month}/{today_est.day}"

LOG_FILE = 'data/tweet_log.json'

# --- MLB URLS ---
current_date = today_est.date()
wbc_start = datetime(2026, 3, 4).date()
wbc_end = datetime(2026, 3, 17).date()
sport_ids = "1,51" if wbc_start <= current_date <= wbc_end else "1"

MLB_API_URL = f"https://statsapi.mlb.com/api/v1/schedule?sportId={sport_ids}&date={date_str}&hydrate=probablePitcher,lineups,person"
MLB_ODDS_URL = "https://weathermlb.com/data/odds.json"

# --- NBA URL ---
NBA_DATA_URL = f"https://nbastartingfive.com/nba_data.json?v={today_est.timestamp()}"

# --- FUTBOL URL ---
FUTBOL_API_URL = f"https://futbolstartingeleven.com/data/games_{date_str}.json?v={today_est.timestamp()}"

                                                                                

# ==========================================
# 3. LOAD & CLEAN MEMORY
# ==========================================
try:
    with open(LOG_FILE, 'r') as f:
        memory = json.load(f)
except FileNotFoundError:
    memory = {}

# Keep today, yesterday, AND tomorrow to prevent infinite file growth but allow midnight crossovers
yesterday_str = (today_est - timedelta(days=1)).strftime('%Y-%m-%d')
tomorrow_str = (today_est + timedelta(days=1)).strftime('%Y-%m-%d')
dates_to_keep = [date_str, yesterday_str, tomorrow_str]
memory = {k: v for k, v in memory.items() if k in dates_to_keep}

if date_str not in memory:
    memory[date_str] = []

log_today = memory[date_str]

# Create a master list of EVERY game in memory (today + yesterday)
tweeted_recently = []
for date_list in memory.values():
    tweeted_recently.extend(date_list)

new_tweets_sent = False

# ==========================================
# 4. NBA ENGINE
# ==========================================
print("--- STARTING NBA ENGINE ---")

try:
    nba_response = requests.get(NBA_DATA_URL)
    nba_data = nba_response.json().get('games', [])
except Exception as e:
    print(f"Error fetching NBA data: {e}")
    nba_data = []

# --- FETCH ESPN ODDS, IDs, & REAL-TIME STATUS ---
ESPN_TO_STD = {"NY": "NYK", "NO": "NOP", "SA": "SAS", "GS": "GSW", "WSH": "WAS", "UTAH": "UTA"}
nba_odds_map = {}
try:
    espn_date = date_str.replace('-', '')
    espn_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={espn_date}"
    espn_data = requests.get(espn_url).json()
    for event in espn_data.get('events', []):
        espn_game_id = str(event.get('id', ''))
        
        # Grab ESPN's highly accurate game status ('pre', 'in', or 'post')
        espn_state = event.get('status', {}).get('type', {}).get('state', 'pre')
        
        comp = event['competitions'][0]
        spread, ou = "TBD", "TBD"
        if comp.get('odds'):
            spread = comp['odds'][0].get('details', 'TBD')
            ou = comp['odds'][0].get('overUnder', 'TBD')
            
        for c in comp['competitors']:
            espn_abbr = c['team']['abbreviation'].upper()
            std_abbr = ESPN_TO_STD.get(espn_abbr, espn_abbr)
            nba_odds_map[std_abbr] = {
                "spread": spread, 
                "ou": ou, 
                "id": espn_game_id,
                "state": espn_state  # Save the state!
            }
except Exception as e:
    print(f"Error fetching ESPN odds/IDs: {e}")

# Hardcoded traditional lineup order
NBA_POS_ORDER = ["PG", "SG", "SF", "PF", "C"]

# --- TEAM NAME TRANSLATION MAP ---
NBA_TEAM_NAMES = {
    "ATL": "Hawks", "BOS": "Celtics", "BKN": "Nets", "CHA": "Hornets",
    "CHI": "Bulls", "CLE": "Cavaliers", "DAL": "Mavericks", "DEN": "Nuggets",
    "DET": "Pistons", "GSW": "Warriors", "HOU": "Rockets", "IND": "Pacers",
    "LAC": "Clippers", "LAL": "Lakers", "MEM": "Grizzlies", "MIA": "Heat",
    "MIL": "Bucks", "MIN": "Timberwolves", "NOP": "Pelicans", "NYK": "Knicks",
    "OKC": "Thunder", "ORL": "Magic", "PHI": "76ers", "PHX": "Suns",
    "POR": "Trail Blazers", "SAC": "Kings", "SAS": "Spurs", "TOR": "Raptors",
    "UTA": "Jazz", "WAS": "Wizards"
}

for game in nba_data:
    if not game.get('teams') or len(game['teams']) < 2: continue
    
    away_team = game['teams'][0]
    home_team = game['teams'][1]
    matchup = f"{away_team} vs {home_team}"
    
    # ----------------------------------------------------
    # FIX 1: THE DATE CHECK (Kills the midnight bug)
    # ----------------------------------------------------
    game_date_str = game.get('date') 
    if game_date_str and game_date_str != date_str:
        print(f"Skipping {matchup} - Stale data from {game_date_str} (Today is {date_str}).")
        continue

    # ----------------------------------------------------
    # FIX 2: THE ESPN STATUS CHECK (Stop tweeting after tipoff)
    # ----------------------------------------------------
    espn_game_data = nba_odds_map.get(away_team, {})
    if espn_game_data.get('state') in ['in', 'post']:
        print(f"Skipping {matchup} - Game has already started or finished according to ESPN.")
        continue

    meta = game.get('meta', {})
            
    # Bulletproof fallback for the website URL hash link if ID is missing
    url_game_id = game.get('id')
    if not url_game_id:
        url_game_id = f"{away_team}-{home_team}-{date_str}"
        
    # Get the ESPN ID for fallback/safety
    espn_game_id = espn_game_data.get('id', url_game_id)
        
    # --- SMART ODDS RESOLVER ---
    final_spread = "TBD"
    final_ou = "TBD"
    
    if away_team in nba_odds_map and nba_odds_map[away_team]['spread'] != "TBD":
        final_spread = nba_odds_map[away_team]['spread']
        final_ou = nba_odds_map[away_team]['ou']
    else:
        local_spread = meta.get('spread', 'TBD')
        local_ou = meta.get('total', 'TBD')
        
        if str(local_spread) not in ["TBD", "nan", "+nan", "None", ""]:
            if "-" in str(local_spread):
                final_spread = f"{away_team} {local_spread}"
            else:
                clean_spread = str(local_spread).replace('+', '')
                final_spread = f"{home_team} -{clean_spread}"
                
        if str(local_ou) not in ["TBD", "nan", "+nan", "None", ""]:
            final_ou = local_ou
            
    odds_parts = []
    if final_spread != "TBD":
        odds_parts.append(final_spread)
    if final_ou != "TBD":
        odds_parts.append(f"O/U {final_ou}")
        
    odds_str = f" [{' | '.join(odds_parts)}]" if odds_parts else ""

    rosters = game.get('rosters', {})
    
    for team, data in rosters.items():
        # ----------------------------------------------------
        # FIX 3: REVERT TO TEAM/DATE KEY FOR THE TWEET LOG
        # ----------------------------------------------------
        team_date_key = f"NBA_{team}_{date_str}"
        
        # Keep legacy checks to prevent duplicates during today's transition
        espn_team_key = f"NBA_{team}_{espn_game_id}" 
        legacy_base_key = f"NBA_{team}"
        
        if team_date_key in tweeted_recently or espn_team_key in tweeted_recently or legacy_base_key in log_today:
            continue
            
        players = data.get('players', [])
        
        is_official = len(players) >= 5 and all(p.get('verified') == True for p in players)
        
        if is_official:
            opp = matchup.replace(team, '').replace(' vs ', '').strip()
            
            team_name = NBA_TEAM_NAMES.get(team, team)
            opp_name = NBA_TEAM_NAMES.get(opp, opp)
            
            tweet_text = f"🏀 {game_date_short} {team_name} Starting Lineup vs {opp_name}\n{odds_str}\n\n"
            
            for index, p in enumerate(players):
                if index < 5:
                    final_pos = NBA_POS_ORDER[index]
                    name = p.get('name', 'Unknown')
                    tweet_text += f"{final_pos} {name}\n"
                
            team_hash = team_name.replace(" ", "")
            
            tweet_text += f"\n\nFull matchups & odds: https://nbastartingfive.com/#game-{url_game_id}\n\n#{team_hash} #{team_hash}Lineup #NBA #DFS #StartingFive"
            
            try:
                nba_client.create_tweet(text=tweet_text)
                print(f"✅ Successfully tweeted {team_name} NBA lineup!")
                log_today.append(team_date_key)
                tweeted_recently.append(team_date_key)
                new_tweets_sent = True
                # --- IMMEDIATE SAFE LOG SAVE ---
                memory[date_str] = log_today
                save_memory_safely(memory)
                time.sleep(5)
            except Exception as e:
                print(f"❌ Failed to tweet {team_name} NBA lineup: {e}")

# ==========================================
# 5. MLB ENGINE
# ==========================================
print("\n--- STARTING MLB ENGINE ---")
try:
    schedule_data = requests.get(MLB_API_URL).json()
    games = schedule_data['dates'][0]['games'] if schedule_data.get('dates') else []
except Exception as e:
    print(f"Error fetching MLB schedule: {e}")
    games = []

odds_data = []
try:
    odds_data = requests.get(MLB_ODDS_URL).json().get('odds', [])
except:
    pass

def get_short_name(full_name, team_name):
    name = team_name if team_name else full_name.split(' ')[-1]
    if 'Red Sox' in full_name: name = 'Red Sox'
    if 'White Sox' in full_name: name = 'White Sox'
    if 'Blue Jays' in full_name: name = 'Blue Jays'
    if name == 'Diamondbacks': name = 'Dbacks'
    wbc_full_names = ['Dominican Republic', 'United States', 'Puerto Rico', 'Great Britain', 'Chinese Taipei']
    for country in wbc_full_names:
        if country in full_name: name = country
    if 'Korea' in full_name or name == 'Korea': name = 'South Korea'
    return name

def format_odds(price):
    if price == "TBD": return price
    return f"+{price}" if price > 0 else str(price)

for game in games:
    game_pk = game['gamePk']
    
    away_needs_tweet = 'lineups' in game and 'awayPlayers' in game['lineups'] and len(game['lineups']['awayPlayers']) > 0 and f"{game_pk}_away" not in tweeted_recently
    home_needs_tweet = 'lineups' in game and 'homePlayers' in game['lineups'] and len(game['lineups']['homePlayers']) > 0 and f"{game_pk}_home" not in tweeted_recently

    if not away_needs_tweet and not home_needs_tweet:
        continue

    positions, hands = {}, {}
    try:
        feed_data = requests.get(f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live").json()
        box_teams = feed_data.get('liveData', {}).get('boxscore', {}).get('teams', {})
        all_players = {**box_teams.get('away', {}).get('players', {}), **box_teams.get('home', {}).get('players', {})}
        for pid, p_data in all_players.items():
            person_id = p_data.get('person', {}).get('id')
            if p_data.get('allPositions'): positions[person_id] = p_data['allPositions'][0].get('abbreviation', '')
            elif p_data.get('position'): positions[person_id] = p_data['position'].get('abbreviation', '')

        player_ids = [str(p['id']) for p in game.get('lineups', {}).get('awayPlayers', []) + game.get('lineups', {}).get('homePlayers', [])]
        if player_ids:
            people_data = requests.get(f"https://statsapi.mlb.com/api/v1/people?personIds={','.join(player_ids)}").json()
            for person in people_data.get('people', []):
                hands[person['id']] = person.get('batSide', {}).get('code', '')
    except Exception as e: pass

    away_full = game['teams']['away']['team']['name']
    home_full = game['teams']['home']['team']['name']
    away_short = get_short_name(away_full, game['teams']['away']['team'].get('teamName'))
    home_short = get_short_name(home_full, game['teams']['home']['team'].get('teamName'))

    away_p_name = game['teams']['away'].get('probablePitcher', {}).get('fullName', 'TBD')
    away_p_hand = game['teams']['away'].get('probablePitcher', {}).get('pitchHand', {}).get('code', 'R') if away_p_name != "TBD" else ""
    away_pitcher_str = f"{away_p_name} ({away_p_hand})" if away_p_name != "TBD" else "TBD"

    home_p_name = game['teams']['home'].get('probablePitcher', {}).get('fullName', 'TBD')
    home_p_hand = game['teams']['home'].get('probablePitcher', {}).get('pitchHand', {}).get('code', 'R') if home_p_name != "TBD" else ""
    home_pitcher_str = f"{home_p_name} ({home_p_hand})" if home_p_name != "TBD" else "TBD"

    raw_away_odds, raw_home_odds, raw_total = "TBD", "TBD", "TBD"
    for o in odds_data:
        if o['home_team'] == home_full and o['away_team'] == away_full:
            for bookie in o.get('bookmakers', []):
                h2h = next((m for m in bookie['markets'] if m['key'] == 'h2h'), None)
                totals = next((m for m in bookie['markets'] if m['key'] == 'totals'), None)
                if h2h:
                    for outcome in h2h['outcomes']:
                        if outcome['name'] == away_full: raw_away_odds = outcome['price']
                        if outcome['name'] == home_full: raw_home_odds = outcome['price']
                if totals and totals['outcomes']:
                    raw_total = totals['outcomes'][0]['point']
                if raw_away_odds != "TBD": break
            break

    total_string = f" • O/U {raw_total}" if raw_total != "TBD" else ""
    away_odds_str = format_odds(raw_away_odds)
    home_odds_str = format_odds(raw_home_odds)

    def send_mlb_tweet(team_short, team_pitcher, team_odds, opp_pitcher, opp_odds, players, side):
        team_odds_display = f" [{team_odds}]" if team_odds != "TBD" else ""
        opp_odds_display = f" [{opp_odds}]" if opp_odds != "TBD" else ""
        
        tweet_text = f"⚾ {game_date_short} {team_short} Lineup{total_string}\nSP: {team_pitcher}{team_odds_display}\nvs {opp_pitcher}{opp_odds_display}\n\n"
        
        for i, p in enumerate(players):
            pid = p['id']
            hand = f"({hands.get(pid)})" if hands.get(pid) else ""
            pos = f"({positions.get(pid)})" if positions.get(pid) else ""
            line = f"{i+1}. {p['fullName']} {pos} {hand}"
            tweet_text += " ".join(line.split()) + "\n"
            
        team_hash = team_short.replace(" ", "")
        tweet_text += f"\n\nGo directly to this gameCard with BvP, Splits, umpire ratings, etc here: https://mlbstartingnine.com/#game-{game_pk}\n\n#{team_hash} #{team_hash}Lineup #MLB #DFS #MLBOdds #StartingPitchers"
        
        try:
            mlb_client.create_tweet(text=tweet_text)
            print(f"✅ Successfully tweeted {team_short} MLB lineup!")
            log_today.append(f"{game_pk}_{side}")
            tweeted_recently.append(f"{game_pk}_{side}")
            return True
            # --- IMMEDIATE SAFE LOG SAVE ---
            memory[date_str] = log_today
            save_memory_safely(memory)
            time.sleep(5)
        except Exception as e:
            print(f"❌ Failed to tweet {team_short}: {e}")
            return False

    if away_needs_tweet:
        if send_mlb_tweet(away_short, away_pitcher_str, away_odds_str, home_pitcher_str, home_odds_str, game['lineups']['awayPlayers'], 'away'):
            new_tweets_sent = True

    if home_needs_tweet:
        if send_mlb_tweet(home_short, home_pitcher_str, home_odds_str, away_pitcher_str, away_odds_str, game['lineups']['homePlayers'], 'home'):
            new_tweets_sent = True


# ==========================================
# 6. MULTI-LEAGUE FUTBOL ENGINE
# ==========================================
print("\n--- STARTING MULTI-LEAGUE FUTBOL ENGINE ---")

FUTBOL_LEAGUES = {
    39:  {"name": "PREMIER LEAGUE 🇬🇧", "tag": "#EPL", "url_slug": "epl"},
    140: {"name": "LA LIGA 🇪🇸", "tag": "#LaLiga", "url_slug": "laliga"},
    135: {"name": "SERIE A 🇮🇹", "tag": "#SerieA", "url_slug": "seriea"},
    2:   {"name": "CHAMPIONS LEAGUE 🇪🇺", "tag": "#UCL", "url_slug": "ucl"},
    45:  {"name": "FA CUP 🇬🇧", "tag": "#FACup", "url_slug": "facup"},
    40:  {"name": "CHAMPIONSHIP 🇬🇧", "tag": "#Championship", "url_slug": "championship"},
    78:  {"name": "BUNDESLIGA 🇩🇪", "tag": "#Bundesliga", "url_slug": "bundesliga"},
    61:  {"name": "LIGUE 1 🇫🇷", "tag": "#Ligue1", "url_slug": "ligue1"},
    253: {"name": "MLS 🇺🇸", "tag": "#MLS", "url_slug": "mls"},
    3:   {"name": "EUROPA LEAGUE 🇪🇺", "tag": "#EuropaLeague", "url_slug": "europa"},
    13:  {"name": "COPA LIBERTADORES 🌎", "tag": "#Libertadores", "url_slug": "libertadores"},
    16:  {"name": "CHAMPIONS CUP 🏆", "tag": "#ChampionsCup", "url_slug": "concacaf"},
    71:  {"name": "BRASILEIRÃO 🇧🇷", "tag": "#Brasileirao", "url_slug": "brazil"},
    128: {"name": "LIGA PROFESIONAL 🇦🇷", "tag": "#LigaProfesional", "url_slug": "argentina"},
    848: { "name": "CONFERENCE LEAGUE 🇪🇺", "tag": "#UECL #ConferenceLeague", "url_slug": "conference" },
    307: { "name": "SAUDI PRO LEAGUE 🇸🇦", "tag": "#SaudiProLeague #SPL", "url_slug": "saudi" },
    88:  { "name": "EREDIVISIE 🇳🇱", "tag": "#Eredivisie", "url_slug": "eredivisie" },
    262: {"name": "LIGA MX 🇲🇽", "tag": "#LigaMX", "url_slug": "ligamx"},
    98:  {"name": "J1 LEAGUE 🇯🇵", "tag": "#J1League", "url_slug": "japan"}
}

def parse_futbol_lineup(startXI):
    pos_dict = {'G': [], 'D': [], 'M': [], 'F': []}
    for player_item in startXI:
        p = player_item.get('player', {})
        pos = p.get('pos', 'M')
        if pos not in pos_dict:
            pos = 'M' 
        pos_dict[pos].append(p.get('name', 'Unknown'))
    return pos_dict

# ----------------------------------------------------
# FUTBOL "LOOK AHEAD" LOGIC
# ----------------------------------------------------
futbol_dates_to_check = [date_str]
if today_est.hour >= 20: # If it's 8 PM EST or later, check tomorrow's file too
    futbol_dates_to_check.append(tomorrow_str)
if today_est.hour <= 2: # If it's 2 AM EST or earlier, check yesterday's file too
    futbol_dates_to_check.append(yesterday_str)    

for target_date_str in futbol_dates_to_check:
    print(f"\n>> Fetching Futbol file for: {target_date_str}")
    
    if target_date_str not in memory:
        memory[target_date_str] = []
    log_target_date = memory[target_date_str]

    target_url = f"https://futbolstartingeleven.com/data/games_{target_date_str}.json?v={today_est.timestamp()}"
    
    try:
        futbol_response = requests.get(target_url)
        if futbol_response.status_code == 200:
            futbol_data = futbol_response.json()
        else:
            futbol_data = []
    except Exception as e:
        print(f"Error fetching Futbol data for {target_date_str}: {e}")
        futbol_data = []

    # ==========================================
    # A. LINEUPS ENGINE (For target_date_str)
    # ==========================================
    for match in futbol_data:
        league_id = match.get('league', {}).get('id')
        if league_id not in FUTBOL_LEAGUES: continue
            
        league_info = FUTBOL_LEAGUES[league_id]
        fixture_id = match.get('fixture', {}).get('id')
        team_key = f"FUTBOL_{fixture_id}"
        
        if team_key in tweeted_recently: continue
            
        home_lineup = match.get('homeLineup')
        away_lineup = match.get('awayLineup')
        
        if not home_lineup or not away_lineup: continue
            
        home_startXI = home_lineup.get('startXI', [])
        away_startXI = away_lineup.get('startXI', [])
        
        if not home_startXI or not away_startXI: continue

        home_t = match['teams']['home']
        away_t = match['teams']['away']
        h_rank = f"[{home_t['rank']}] " if home_t.get('rank') else ""
        h_rec = f"({home_t['record']})" if home_t.get('record') else ""
        h_name = home_t['name']
        a_rank = f"[{away_t['rank']}] " if away_t.get('rank') else ""
        a_rec = f"({away_t['record']})" if away_t.get('record') else ""
        a_name = away_t['name']
        
        print(f"[{fixture_id}] Both lineups found for {h_name} vs {a_name} ({league_info['tag']}). Building tweet...")

        header = f"🚨 OFFICIAL STARTING XI: {league_info['name']}\n{h_rank}{h_name} {h_rec} vs {a_rank}{a_name} {a_rec}".replace("  ", " ").strip()
        h_pos = parse_futbol_lineup(home_startXI)
        a_pos = parse_futbol_lineup(away_startXI)
        h_form = home_lineup.get('formation', 'TBD')
        a_form = away_lineup.get('formation', 'TBD')
        
        home_str = f"🟢 {h_name} ({h_form})\nG: {', '.join(h_pos['G'])}\nD: {', '.join(h_pos['D'])}\nM: {', '.join(h_pos['M'])}\nF: {', '.join(h_pos['F'])}"
        away_str = f"🔴 {a_name} ({a_form})\nG: {', '.join(a_pos['G'])}\nD: {', '.join(a_pos['D'])}\nM: {', '.join(a_pos['M'])}\nF: {', '.join(a_pos['F'])}"
        
        odds = match.get('odds', {})
        odds_str = f"📊 Live Match Odds\n{h_name}: {odds.get('home', 'TBD')} | Draw: {odds.get('draw', 'TBD')} | {a_name}: {odds.get('away', 'TBD')}\nOver {odds.get('total', '2.5')}: {odds.get('over', 'TBD')} | Under {odds.get('total', '2.5')}: {odds.get('under', 'TBD')}"
        
        inj = match.get('injuries', {})
        h_inj = ", ".join(str(p) for p in inj.get('home', []) if p) if inj.get('home') else ""
        a_inj = ", ".join(str(p) for p in inj.get('away', []) if p) if inj.get('away') else ""
        inj_lines = []
        if h_inj: inj_lines.append(f"{h_name}: {h_inj}")
        if a_inj: inj_lines.append(f"{a_name}: {a_inj}")
        inj_str = f"🤕 Key Absences:\n" + "\n".join(inj_lines) if inj_lines else ""
        
        h_hash = h_name.replace(' ', '').replace('-', '').replace('.', '')
        a_hash = a_name.replace(' ', '').replace('-', '').replace('.', '')
        
        # Link uses target_date_str, NOT the global date_str
        footer = f"📱 Live stats & scores: https://futbolstartingeleven.com/?league={league_info['url_slug']}&date={target_date_str}#card-{fixture_id}\n\n{league_info['tag']} #{h_hash} #{h_hash}StartingXI #{a_hash} #{a_hash}StartingXI"
        
        tweet_parts = [header, home_str, away_str, odds_str]
        if inj_str: tweet_parts.append(inj_str)
        tweet_parts.append(footer)
        tweet_text = "\n\n".join(tweet_parts)
        
        try:
            futbol_client.create_tweet(text=tweet_text)
            print(f"✅ Successfully tweeted Futbol matchup: {h_name} vs {a_name}!")
            log_target_date.append(team_key)
            tweeted_recently.append(team_key)
            new_tweets_sent = True
            memory[target_date_str] = log_target_date
            save_memory_safely(memory)
            time.sleep(5)
        except Exception as e:
            print(f"❌ Failed to tweet Futbol matchup ({h_name} vs {a_name}): {e}")

    # ==========================================
    # B. LIVE ALERTS ENGINE (For target_date_str)
    # ==========================================
    for match in futbol_data:
        league_id = match.get('league', {}).get('id')
        if league_id not in FUTBOL_LEAGUES: continue
            
        league_info = FUTBOL_LEAGUES[league_id]
        fixture_id = match.get('fixture', {}).get('id')
        fixture_status = match.get('fixture', {}).get('status', {}).get('short', '')
        
        events = match.get('events', [])
        if not events: continue
            
        h_id = match['teams']['home']['id']
        a_id = match['teams']['away']['id']
        h_name = match['teams']['home']['name']
        a_name = match['teams']['away']['name']
        
        official_home_score = int(match.get('goals', {}).get('home') or 0)
        official_away_score = int(match.get('goals', {}).get('away') or 0)
        
        # --- 🛡️ SHOOTOUT PRE-FILTER ---
        # API-Sports sends shootout penalties as regular "Penalty" events, which causes massive spam.
        valid_goal_events = []
        is_shootout = fixture_status in ['P', 'PEN']
        
        # Fallback Check: If status is lagging but multiple late penalties appear, it's a shootout
        late_penalties = sum(1 for e in events if e.get('type') == 'Goal' and e.get('detail') == 'Penalty' and int(str(e.get('time', '0')) if str(e.get('time', '0')).isdigit() else 0) >= 90)
        if late_penalties > 1:
            is_shootout = True
            
        for e in events:
            if e.get('type') == 'Goal' and e.get('detail') in ['Normal Goal', 'Penalty']:
                e_time = int(str(e.get('time', '0'))) if str(e.get('time', '0')).isdigit() else 0
                
                # Nuke shootout penalties so they don't corrupt the live score or trigger tweets
                if e.get('detail') == 'Penalty' and e_time >= 90 and is_shootout:
                    continue
                
                valid_goal_events.append(e)

        # If all events were scrubbed, skip to the next game
        if not valid_goal_events: 
            continue
            
        # Recalculate totals using ONLY the valid regular-play goals
        home_events_total = sum(1 for e in valid_goal_events if e.get('team_id') == h_id)
        away_events_total = sum(1 for e in valid_goal_events if e.get('team_id') == a_id)
        
        current_home_score = max(0, official_home_score - home_events_total)
        current_away_score = max(0, official_away_score - away_events_total)
        
        home_odds_str = match.get('odds', {}).get('home', 'TBD')
        away_odds_str = match.get('odds', {}).get('away', 'TBD')
        try: home_odds = float(home_odds_str) if home_odds_str != 'TBD' else 0.0
        except ValueError: home_odds = 0.0
        try: away_odds = float(away_odds_str) if away_odds_str != 'TBD' else 0.0
        except ValueError: away_odds = 0.0

        for event in valid_goal_events: # <--- Make sure this line is looping the valid events!
            team_id = event.get('team_id')
            
            if team_id == h_id:
                current_home_score += 1
                team_goal_count = current_home_score
            else:
                current_away_score += 1
                team_goal_count = current_away_score
                
            event_time_str = str(event.get('time', '0'))
            try: event_time = int(event_time_str)
            except ValueError: event_time = 0
                    
                event_key = f"ALERT_{fixture_id}_{team_id}_Goal_{team_goal_count}"
                
                if event_key in tweeted_recently: continue

                calc_home_score = current_home_score
                calc_away_score = current_away_score
                    
                PHRASES = {
                    "late_equalizer": {
                        "titles": ["🚨 LATE EQUALIZER!", "🚨 DRAMATIC EQUALIZER!", "🚨 TIED UP LATE!", "🚨 CLOSING STAGES CHAOS!", "🚨 ALL SQUARE LATE!"],
                        "blurbs": [
                            "A massive goal from {scoring_team_name} to level the score, leaving {conceding_team_name} scrambling as time winds down!",
                            "{scoring_team_name} claws their way back to tie the match, ripping the momentum right out of {conceding_team_name}'s hands.",
                            "{scoring_team_name} refuses to go away quietly! We are all square as {conceding_team_name} tries to regain control.",
                            "A crucial tying goal for {scoring_team_name} stuns {conceding_team_name} and sets up a frantic finish!",
                            "{scoring_team_name} finds a late lifeline against {conceding_team_name}! A massive momentum swing erases the deficit."
                        ],
                        "ctas": ["Track the final push for a game-winner here:", "See the live momentum shift and pitch data:", "Can someone find a late winner? Follow live:", "Watch the closing minutes unfold live:"]
                    },
                    "late_go_ahead": {
                        "titles": ["🚨 LATE GO-AHEAD GOAL!", "🚨 THE DEADLOCK IS BROKEN!", "🚨 CLUTCH MOMENT!", "🚨 HUGE LATE GOAL!", "🚨 TENSION IN THE FINAL 15!"],
                        "blurbs": [
                            "A game-changing strike from {scoring_team_name} forces {conceding_team_name} to chase the game late!",
                            "{scoring_team_name} snatches the advantage right when they needed it, leaving {conceding_team_name} stunned.",
                            "A massive momentum swing puts {scoring_team_name} in front, and now {conceding_team_name} is running out of time!",
                            "The defense finally cracks! {scoring_team_name} takes a crucial late lead over {conceding_team_name}.",
                            "Heartbreak for {conceding_team_name} as they concede the lead to {scoring_team_name} late in the half!"
                        ],
                        "ctas": ["Can they hold on? Follow the final minutes live:", "Track the closing stages and live stats here:", "See if the defense can shut the door:", "Follow the live pitch data as time winds down:"]
                    },
                    "stoppage_equalizer": {
                        "titles": ["🚨 STOPPAGE TIME EQUALIZER!", "🚨 SAVED AT THE DEATH!", "🚨 LAST MINUTE LIFELINE!", "🚨 90TH MINUTE MADNESS!", "🚨 SCENES IN STOPPAGE TIME!"],
                        "blurbs": [
                            "Absolute scenes! A miraculous stoppage-time equalizer for {scoring_team_name} throws {conceding_team_name} into chaos!",
                            "{scoring_team_name} climbs out of the grave to level the match. Is there still time for {conceding_team_name} to respond?!",
                            "You can't write a better script! {scoring_team_name} stuns {conceding_team_name} with a tying goal deep in stoppage time.",
                            "A devastating blown lead for {conceding_team_name}! {scoring_team_name} forces a dramatic tie in the dying moments.",
                            "An unbelievable momentum shift! {scoring_team_name} breaks {conceding_team_name}'s hearts to level the score right at the end."
                        ],
                        "ctas": ["Watch the frantic final moments unfold live:", "Track the live pitch data before the referee blows the whistle:", "See the post-goal chaos and live match center here:", "Don't miss the ending. See live stats and match data here:"]
                    },
                    "stoppage_go_ahead": {
                        "titles": ["🚨 STOPPAGE TIME THRILLER!", "🚨 AT THE DEATH!", "🚨 LATE HEARTBREAK!", "🚨 STOPPAGE TIME DAGGER!", "🚨 90TH MINUTE MADNESS!"],
                        "blurbs": [
                            "Heartbreak for {conceding_team_name}! {scoring_team_name} pulls a rabbit out of the hat to take the lead in stoppage time.",
                            "A staggering late dagger! {scoring_team_name} snatches a crucial lead, leaving {conceding_team_name} with virtually no time to respond.",
                            "Absolute madness! {scoring_team_name} takes the lead at the death, forcing {conceding_team_name} into pure panic mode.",
                            "A devastating stoppage-time strike puts {scoring_team_name} in front, leaving {conceding_team_name} desperate for a last-second miracle.",
                            "Have they just won it at the death?! {scoring_team_name} stuns {conceding_team_name} with a massive go-ahead goal in the dying moments."
                        ],
                        "ctas": ["Can they survive the final whistle? Follow live:", "Don't miss the frantic ending. See live stats and pitch data here:", "Will there be one last twist? Track the closing seconds here:", "Watch the desperate final push unfold live:"]
                    },
                    "standard_upset": {
                        "titles": ["⚠️ UPSET ALERT!", "⚠️ UNDERDOGS OUT IN FRONT!", "⚠️ SURPRISE BREWING!", "⚠️ UPSET IN PROGRESS!"],
                        "blurbs": [
                            "The underdogs have taken the lead! {scoring_team_name} strikes against {conceding_team_name}.",
                            "A surprising turn of events puts {scoring_team_name} ahead of heavy favorites {conceding_team_name}.",
                            "The heavy favorites find themselves trailing as {scoring_team_name} takes the game right to {conceding_team_name}!",
                            "Vegas might be sweating a bit as {scoring_team_name} snatches the lead from {conceding_team_name}.",
                            "The script is flipped! {scoring_team_name} grabs the advantage over {conceding_team_name}."
                        ],
                        "ctas": ["Can they hold on for the upset? Track live here:", "Follow the live match center and pitch data here:", "See the live odds and full stats here:"]
                    },
                    "massive_upset": {
                        "titles": ["🚨🔥 MAJOR UPSET ALERT!", "🚨🔥 SHOCKER IN PROGRESS!", "🚨🔥 MASSIVE UPSET BREWING!", "🚨🔥 DAVID VS GOLIATH!"],
                        "blurbs": [
                            "A massive shocker is unfolding! {scoring_team_name} takes a stunning lead over {conceding_team_name}.",
                            "Nobody saw this coming! Massive underdogs {scoring_team_name} are out in front of {conceding_team_name}.",
                            "Stunning scenes! The heavy favorites are on the ropes as {scoring_team_name} goes up on {conceding_team_name}.",
                            "A potential shocker of the weekend is happening right now, with {scoring_team_name} leading {conceding_team_name}.",
                            "Parlays are in serious danger! {scoring_team_name} just flipped the script on {conceding_team_name}."
                        ],
                        "ctas": ["Witness the upset attempt live:", "Don't miss this potential shocker. Live stats and odds:", "Will the favorites respond? Follow the live action here:"]
                    },
                    "late_upset": {
                        "titles": ["🚨⚠️ LATE UPSET BREWING!", "🚨⚠️ LATE UNDERDOG ALERT!", "🚨⚠️ UPSET WATCH: CLOSING STAGES!", "🚨⚠️ VEGAS IS SWEATING!"],
                        "blurbs": [
                            "{scoring_team_name} snatches a crucial late lead, putting {conceding_team_name} in serious danger of a huge upset!",
                            "A massive late goal puts heavy favorites {conceding_team_name} on the brink of defeat against {scoring_team_name}.",
                            "With time running out, {scoring_team_name} takes a shocking late lead over {conceding_team_name}!",
                            "Live bettors take note: {scoring_team_name} just struck late to put {conceding_team_name} on the ropes!"
                        ],
                        "ctas": ["Watch the frantic final push live here:", "Can the underdogs hold the line? Live stats:", "Will Goliath respond? Follow the live action here:"]
                    },
                    "stoppage_upset": {
                        "titles": ["🚨🔥 STUNNER IN STOPPAGE TIME!", "🚨🔥 LATE UPSET THRILLER!", "🚨🔥 MADNESS AT THE DEATH!", "🚨🔥 THE ULTIMATE SHOCKER!"],
                        "blurbs": [
                            "A staggering stoppage-time strike! {scoring_team_name} takes a shocking lead, forcing {conceding_team_name} into a desperate final push.",
                            "Parlays are in critical danger! {scoring_team_name} strikes in stoppage time to go ahead of {conceding_team_name}. Will there be one last twist?",
                            "You cannot write a better script! {scoring_team_name} takes a massive late lead, leaving {conceding_team_name} stunned with the clock ticking down.",
                            "Absolute pandemonium! {scoring_team_name} scores deep in stoppage time, putting heavy favorites {conceding_team_name} on the brink of an epic collapse.",
                            "A potential miracle in the making! {scoring_team_name} snatches a shock lead, leaving {conceding_team_name} desperate for a last-gasp response."
                        ],
                        "ctas": ["Witness the final frantic moments live:", "Don't miss the final whistle of this shocker. Live stats:", "See the post-goal chaos and live match center here:"]
                    }
                }

                is_late = 75 <= event_time < 90
                is_stoppage = event_time >= 90
                is_equalizer = (calc_home_score == calc_away_score)
                
                is_go_ahead = (team_id == h_id and calc_home_score - calc_away_score == 1) or \
                              (team_id == a_id and calc_away_score - calc_home_score == 1)
                
                scorer_odds = home_odds if team_id == h_id else away_odds
                is_standard_upset = is_go_ahead and (4.00 <= scorer_odds < 7.00)
                is_massive_upset = is_go_ahead and (scorer_odds >= 7.00)
                
                scenario_key = None
                
                if is_stoppage and (is_standard_upset or is_massive_upset): scenario_key = "stoppage_upset"
                elif is_late and (is_standard_upset or is_massive_upset): scenario_key = "late_upset"
                elif is_massive_upset: scenario_key = "massive_upset"
                elif is_standard_upset: scenario_key = "standard_upset"
                elif is_stoppage and is_go_ahead: scenario_key = "stoppage_go_ahead"
                elif is_stoppage and is_equalizer: scenario_key = "stoppage_equalizer"
                elif is_late and is_go_ahead: scenario_key = "late_go_ahead"
                elif is_late and is_equalizer: scenario_key = "late_equalizer"
                    
                if not scenario_key: continue

                if fixture_status in ['FT', 'AET', 'PEN']:
                    # Only silence the tweet if the game has been over for more than 20 minutes
                    is_stale = True
                    match_ended_str = match.get("match_ended_at")
                    
                    if match_ended_str:
                        try:
                            ended_time = datetime.fromisoformat(match_ended_str)
                            mins_since_end = (datetime.now(timezone.utc) - ended_time).total_seconds() / 60
                            if mins_since_end < 20:
                                is_stale = False # The game just finished! Let the late tweet through!
                        except Exception:
                            pass
                            
                    if is_stale:
                        log_target_date.append(event_key)
                        tweeted_recently.append(event_key)
                        memory[target_date_str] = log_target_date
                        save_memory_safely(memory)
                        continue
                    
                scoring_team_name = h_name if team_id == h_id else a_name
                conceding_team_name = a_name if team_id == h_id else h_name
                scorer = event.get('player')
                
                scorer_str = f"{scorer} ({scoring_team_name})" if scorer and scorer != "null" else f"{scoring_team_name}"
                american_odds = f"+{int((scorer_odds - 1) * 100)}"
                
                h_hash = h_name.replace(' ', '').replace('-', '').replace('.', '')
                a_hash = a_name.replace(' ', '').replace('-', '').replace('.', '')
                
                # Link uses target_date_str, NOT the global date_str
                link = f"https://futbolstartingeleven.com/?league={league_info['url_slug']}&date={target_date_str}#card-{fixture_id}"
                
                title = random.choice(PHRASES[scenario_key]["titles"])
                blurb_raw = random.choice(PHRASES[scenario_key]["blurbs"])
                cta = random.choice(PHRASES[scenario_key]["ctas"])
                
                blurb = blurb_raw.format(scoring_team_name=scoring_team_name, conceding_team_name=conceding_team_name)

                tweet_text = f"{title}\n\n⚽ {event_time}' GOAL - {scorer_str}\n{h_name} {calc_home_score} - {calc_away_score} {a_name}\n\n"
                if "upset" in scenario_key: tweet_text += f"📊 Pre-Match Line: {scoring_team_name} ({american_odds})\n\n"
                tweet_text += f"{blurb}\n\n{cta}\n⬇️\n{link}\n\n{league_info['tag']} #{h_hash} #{a_hash}"
                
                try:
                    futbol_client.create_tweet(text=tweet_text)
                    print(f"✅ Successfully tweeted ALERTS for {scoring_team_name}!")
                    
                    log_target_date.append(event_key)
                    tweeted_recently.append(event_key)
                    new_tweets_sent = True
                    memory[target_date_str] = log_target_date
                    save_memory_safely(memory)
                    time.sleep(5)
                    
                except Exception as e:
                    print(f"❌ Failed to tweet ALERT: {e}")

# ==========================================
# 7. SAVE MEMORY
# ==========================================
if new_tweets_sent:
    # Just save the global memory object (which already has today, tomorrow, and yesterday safely updated)
    save_memory_safely(memory)
    print("\n💾 Memory updated.")
else:
    print("\nNo new lineups to tweet for NBA, MLB, or Futbol.")
