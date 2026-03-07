import os
import json
import requests
import tweepy
from datetime import datetime, timezone, timedelta

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

# ==========================================
# 2. SETUP DATES & FILE PATHS
# ==========================================
today_est = datetime.now(timezone.utc) - timedelta(hours=4)
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

# ==========================================
# 3. LOAD & CLEAN MEMORY
# ==========================================
try:
    with open(LOG_FILE, 'r') as f:
        memory = json.load(f)
except FileNotFoundError:
    memory = {}

# Keep only today and yesterday to prevent infinite file growth
yesterday_str = (today_est - timedelta(days=1)).strftime('%Y-%m-%d')
dates_to_keep = [date_str, yesterday_str]
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

# --- FETCH ESPN ODDS ---
ESPN_TO_STD = {"NY": "NYK", "NO": "NOP", "SA": "SAS", "GS": "GSW", "WSH": "WAS", "UTAH": "UTA"}
nba_odds_map = {}
try:
    espn_date = date_str.replace('-', '')
    espn_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={espn_date}"
    espn_data = requests.get(espn_url).json()
    for event in espn_data.get('events', []):
        comp = event['competitions'][0]
        if comp.get('odds'):
            spread = comp['odds'][0].get('details', 'TBD')
            ou = comp['odds'][0].get('overUnder', 'TBD')
            for c in comp['competitors']:
                espn_abbr = c['team']['abbreviation'].upper()
                std_abbr = ESPN_TO_STD.get(espn_abbr, espn_abbr)
                nba_odds_map[std_abbr] = {"spread": spread, "ou": ou}
except Exception as e:
    print(f"Error fetching ESPN odds: {e}")

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
    game_id = game.get('id', '')
    if not game.get('teams') or len(game['teams']) < 2: continue
    
    away_team = game['teams'][0]
    home_team = game['teams'][1]
    matchup = f"{away_team} vs {home_team}"
    meta = game.get('meta', {})
    
    # --- SMART ODDS RESOLVER ---
    final_spread = "TBD"
    final_ou = "TBD"
    
    # 1. Try ESPN Live Odds First
    if away_team in nba_odds_map and nba_odds_map[away_team]['spread'] != "TBD":
        final_spread = nba_odds_map[away_team]['spread']
        final_ou = nba_odds_map[away_team]['ou']
    else:
        # 2. Fallback to local JSON memory
        local_spread = meta.get('spread', 'TBD')
        local_ou = meta.get('total', 'TBD')
        
        if str(local_spread) not in ["TBD", "nan", "+nan", "None", ""]:
            # If away team's spread has a minus, they are favored. If plus, home is favored.
            if "-" in str(local_spread):
                final_spread = f"{away_team} {local_spread}"
            else:
                clean_spread = str(local_spread).replace('+', '')
                final_spread = f"{home_team} -{clean_spread}"
                
        if str(local_ou) not in ["TBD", "nan", "+nan", "None", ""]:
            final_ou = local_ou
            
    # UPDATED: Cleanly strip TBD odds from NBA string
    odds_parts = []
    if final_spread != "TBD":
        odds_parts.append(final_spread)
    if final_ou != "TBD":
        odds_parts.append(f"O/U {final_ou}")
        
    odds_str = f" [{' | '.join(odds_parts)}]" if odds_parts else ""

    rosters = game.get('rosters', {})
    
    for team, data in rosters.items():
        team_key = f"NBA_{team}" 
        
        if team_key in tweeted_recently:
            continue
            
        players = data.get('players', [])
        
        # Check if we have 5 players and ALL are verified
        is_official = len(players) >= 5 and all(p.get('verified') == True for p in players)
        
        if is_official:
            opp = matchup.replace(team, '').replace(' vs ', '').strip()
            
            # --- APPLY TEAM NAME TRANSLATIONS ---
            team_name = NBA_TEAM_NAMES.get(team, team)
            opp_name = NBA_TEAM_NAMES.get(opp, opp)
            
            tweet_text = f"🏀 {game_date_short} {team_name} Starting Lineup vs {opp_name}\n{odds_str}\n\n"
            
            for index, p in enumerate(players):
                if index < 5:
                    final_pos = NBA_POS_ORDER[index]
                    name = p.get('name', 'Unknown')
                    tweet_text += f"{final_pos} {name}\n"
                
            # Create a hashtag-friendly version (e.g., "Trail Blazers" -> "TrailBlazers")
            team_hash = team_name.replace(" ", "")
            
            tweet_text += f"\n\nFull matchups & odds: https://nbastartingfive.com/#game-{game_id}\n\n#{team_hash} #{team_hash}Lineup #NBA #DFS #StartingFive"
            
            try:
                nba_client.create_tweet(text=tweet_text)
                print(f"✅ Successfully tweeted {team_name} NBA lineup!")
                log_today.append(team_key)
                tweeted_recently.append(team_key)
                new_tweets_sent = True
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
        # UPDATED: Only inject the brackets if the odds are actually available
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
# 6. SAVE MEMORY
# ==========================================
if new_tweets_sent:
    memory[date_str] = log_today
    with open(LOG_FILE, 'w') as f:
        json.dump(memory, f, indent=4)
    print("\n💾 Memory updated.")
else:
    print("\nNo new lineups to tweet for NBA or MLB.")
