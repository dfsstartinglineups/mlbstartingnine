import os
import json
import requests
import tweepy
from datetime import datetime, timezone, timedelta

# 1. AUTHENTICATE WITH X (TWITTER)
client = tweepy.Client(
    consumer_key=os.environ.get("X_API_KEY"),
    consumer_secret=os.environ.get("X_API_SECRET"),
    access_token=os.environ.get("X_ACCESS_TOKEN"),
    access_token_secret=os.environ.get("X_ACCESS_TOKEN_SECRET")
)

# 2. SETUP DATES & FILE PATHS
today_est = datetime.now(timezone.utc) - timedelta(hours=4)
date_str = today_est.strftime('%Y-%m-%d')
game_date_short = f"{today_est.month}/{today_est.day}"

# --- DYNAMIC WBC DATE CHECKER ---
current_date = today_est.date()
wbc_start = datetime(2026, 3, 4).date()
wbc_end = datetime(2026, 3, 17).date()

sport_ids = "1"
if wbc_start <= current_date <= wbc_end:
    sport_ids = "1,51" # 1 = MLB, 51 = WBC

LOG_FILE = 'data/tweet_log.json'
MLB_API_URL = f"https://statsapi.mlb.com/api/v1/schedule?sportId={sport_ids}&date={date_str}&hydrate=probablePitcher,lineups,person"
ODDS_URL = "https://weathermlb.com/data/odds.json"

# 3. LOAD & CLEAN MEMORY
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

# 4. FETCH BASE DATA (MLB SCHEDULE & ODDS)
try:
    schedule_data = requests.get(MLB_API_URL).json()
    games = schedule_data['dates'][0]['games'] if schedule_data.get('dates') else []
except Exception as e:
    print(f"Error fetching schedule: {e}")
    games = []

odds_data = []
try:
    odds_data = requests.get(ODDS_URL).json().get('odds', [])
except:
    pass

# Helper to format team names exactly like the JS script
def get_short_name(full_name, team_name):
    # The API usually provides the clean team/country name here
    name = team_name if team_name else full_name.split(' ')[-1]
    
    # MLB Exceptions
    if 'Red Sox' in full_name: name = 'Red Sox'
    if 'White Sox' in full_name: name = 'White Sox'
    if 'Blue Jays' in full_name: name = 'Blue Jays'
    if name == 'Diamondbacks': name = 'Dbacks'

    # WBC Exceptions
    if 'Korea' in full_name or name == 'Korea':
        name = 'South Korea'

    return name

# Helper to format odds (adds the "+" sign)
def format_odds(price):
    if price == "TBD": return price
    return f"+{price}" if price > 0 else str(price)

# 5. PROCESS GAMES
for game in games:
    game_pk = game['gamePk']
    
    # Check the master `tweeted_recently` list so we don't double tweet at midnight
    away_needs_tweet = 'lineups' in game and 'awayPlayers' in game['lineups'] and len(game['lineups']['awayPlayers']) > 0 and f"{game_pk}_away" not in tweeted_recently
    home_needs_tweet = 'lineups' in game and 'homePlayers' in game['lineups'] and len(game['lineups']['homePlayers']) > 0 and f"{game_pk}_home" not in tweeted_recently

    if not away_needs_tweet and not home_needs_tweet:
        continue

    # --- FETCH LIVE FEED FOR POSITIONS ---
    positions = {}
    hands = {}
    try:
        # 1. Get Positions from the live feed
        feed_data = requests.get(f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live").json()
        box_teams = feed_data.get('liveData', {}).get('boxscore', {}).get('teams', {})
        
        all_players = {**box_teams.get('away', {}).get('players', {}), **box_teams.get('home', {}).get('players', {})}
        for pid, p_data in all_players.items():
            person_id = p_data.get('person', {}).get('id')
            if p_data.get('allPositions'): positions[person_id] = p_data['allPositions'][0].get('abbreviation', '')
            elif p_data.get('position'): positions[person_id] = p_data['position'].get('abbreviation', '')

        # 2. Get Handedness from the people endpoint
        player_ids = [str(p['id']) for p in game.get('lineups', {}).get('awayPlayers', []) + game.get('lineups', {}).get('homePlayers', [])]
        if player_ids:
            people_data = requests.get(f"https://statsapi.mlb.com/api/v1/people?personIds={','.join(player_ids)}").json()
            for person in people_data.get('people', []):
                hands[person['id']] = person.get('batSide', {}).get('code', '')
                
    except Exception as e:
        print(f"Error fetching positions/hands: {e}")

    # --- EXTRACT TEAM DATA & PITCHERS ---
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

    # --- MATCH ODDS ---
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

    # --- TWEET GENERATOR FUNCTION ---
    def send_tweet(team_short, team_pitcher, team_odds, opp_pitcher, opp_odds, players, side):
        tweet_text = f"⚾ {game_date_short} {team_short} Lineup{total_string}\n"
        tweet_text += f"SP: {team_pitcher} [{team_odds}]\n"
        tweet_text += f"vs {opp_pitcher} [{opp_odds}]\n\n"

        for i, p in enumerate(players):
            pid = p['id']
            hand = f"({hands.get(pid)})" if hands.get(pid) else ""
            pos = f"({positions.get(pid)})" if positions.get(pid) else ""
            
            line = f"{i+1}. {p['fullName']} {pos} {hand}"
            tweet_text += " ".join(line.split()) + "\n"

        team_hash = team_short.replace(" ", "")
        tweet_text += f"\n\nGo directly to this gameCard with BvP, Splits, umpire ratings, etc here: https://mlbstartingnine.com/#game-{game_pk}\n\n#{team_hash} #{team_hash}Lineup #MLB #DFS #MLBOdds #StartingPitchers"

        try:
            client.create_tweet(text=tweet_text)
            print(f"✅ Successfully tweeted {team_short} lineup!")
            # Add to both the save log and the active check list
            log_today.append(f"{game_pk}_{side}")
            tweeted_recently.append(f"{game_pk}_{side}")
            return True
        except Exception as e:
            print(f"❌ Failed to tweet {team_short}: {e}")
            return False

    # --- FIRE THE TWEETS ---
    if away_needs_tweet:
        if send_tweet(away_short, away_pitcher_str, away_odds_str, home_pitcher_str, home_odds_str, game['lineups']['awayPlayers'], 'away'):
            new_tweets_sent = True

    if home_needs_tweet:
        if send_tweet(home_short, home_pitcher_str, home_odds_str, away_pitcher_str, away_odds_str, game['lineups']['homePlayers'], 'home'):
            new_tweets_sent = True

# 6. SAVE MEMORY
if new_tweets_sent:
    memory[date_str] = log_today
    with open(LOG_FILE, 'w') as f:
        json.dump(memory, f, indent=4)
    print("💾 Memory updated.")
else:
    print("⚾ No new lineups to tweet.")
