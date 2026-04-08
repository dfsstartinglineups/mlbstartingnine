import os
import json
import requests
import tweepy
import zoneinfo
from datetime import datetime, timezone, timedelta
import time
import random
from atproto import Client, client_utils
import firebase_admin
from firebase_admin import credentials, db
import asyncio
from playwright.async_api import async_playwright
from PIL import Image
import io

# ==========================================
# FIREBASE INITIALIZATION
# ==========================================
if not firebase_admin._apps:
    raw_firebase_key = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if raw_firebase_key:
        try:
            cred_dict = json.loads(raw_firebase_key)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://nbastartingfive-8b420-default-rtdb.firebaseio.com/'
            })
            print("✅ Firebase authenticated for Tweet Bot!")
        except Exception as e:
            print(f"❌ Firebase Auth Failed: {e}")

def save_memory_safely(memory_data):
    """Safely writes to the log file using a temporary file to prevent corruption."""
    temp_file = f"{LOG_FILE}.tmp"
    with open(temp_file, 'w') as f:
        json.dump(memory_data, f, indent=4)
    os.replace(temp_file, LOG_FILE)

# ==========================================
# 0. V2 ARCHITECTURE: BLUESKY & DICTIONARY
# ==========================================
try:
    raw_secrets = os.environ.get("NEW_SOCIAL_CREDENTIALS", "{}")
    auth_data = json.loads(raw_secrets)
except Exception as e:
    print(f"⚠️ Could not load V2 credentials: {e}")
    auth_data = {}

def setup_bsky_client(account_key):
    creds = auth_data.get(account_key)
    if creds and creds.get("bsky_handle"):
        try:
            client = Client()
            client.login(creds["bsky_handle"], creds["bsky_password"])
            print(f"✅ Logged into Bluesky as {creds['bsky_handle']}")
            return client
        except Exception as e:
            print(f"❌ Failed to log into Bluesky for {account_key}: {e}")
    return None

LEAGUE_CONFIG = {
    "mlb": {
        "league_name": "MLB ⚾",
        "bsky_client": setup_bsky_client("mlb_account")
    },
    "nba": {
        "league_name": "NBA 🏀",
        "bsky_client": setup_bsky_client("nba_account")
    }
}


# ==========================================
# 1. AUTHENTICATE WITH X (TWITTER)
# ==========================================
# Helper to create both V2 Client and V1.1 API simultaneously
def create_x_clients(consumer_key, consumer_secret, access_token, access_token_secret):
    if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
        return None, None
        
    # CRITICAL FIX: Must use explicit keyword arguments here!
    client = tweepy.Client(
        consumer_key=consumer_key, 
        consumer_secret=consumer_secret, 
        access_token=access_token, 
        access_token_secret=access_token_secret
    )
    auth = tweepy.OAuth1UserHandler(consumer_key, consumer_secret, access_token, access_token_secret)
    api_v1 = tweepy.API(auth)
    
    return client, api_v1

# MLB Client (Main Account)
mlb_client, mlb_api_v1 = create_x_clients(
    os.environ.get("X_API_KEY"), os.environ.get("X_API_SECRET"),
    os.environ.get("X_ACCESS_TOKEN"), os.environ.get("X_ACCESS_TOKEN_SECRET")
)

# NBA Client (@DailyNBAlineups)
nba_client, nba_api_v1 = create_x_clients(
    os.environ.get("NBA_X_API_KEY"), os.environ.get("NBA_X_API_SECRET"),
    os.environ.get("NBA_X_ACCESS_TOKEN"), os.environ.get("NBA_X_ACCESS_TOKEN_SECRET")
)

# Futbol Client (@FutbolStarting11 - Using existing SerieA Env Vars)
futbol_client, futbol_api_v1 = create_x_clients(
    os.environ.get("SERIEA_X_API_KEY"), os.environ.get("SERIEA_X_API_SECRET"),
    os.environ.get("SERIEA_X_ACCESS_TOKEN"), os.environ.get("SERIEA_X_ACCESS_TOKEN_SECRET")
)

# International Friendlies Client
friendly_client, friendly_api_v1 = create_x_clients(
    os.environ.get("FRIENDLY_X_API_KEY"), os.environ.get("FRIENDLY_X_API_SECRET"),
    os.environ.get("FRIENDLY_X_ACCESS_TOKEN"), os.environ.get("FRIENDLY_X_ACCESS_TOKEN_SECRET")
)

# Dynamic Clients Helper
def get_dynamic_clients(key):
    creds = auth_data.get(key, {})
    return create_x_clients(
        creds.get("consumer_key"), creds.get("consumer_secret"),
        creds.get("access_token"), creds.get("access_token_secret")
    )

championship_client, championship_api_v1 = get_dynamic_clients("championship_x")
bundesliga_client, bundesliga_api_v1 = get_dynamic_clients("bundesliga_x")
nwsl_client, nwsl_api_v1 = get_dynamic_clients("nwsl_x")
mls_client, mls_api_v1 = get_dynamic_clients("mls_x")
ligue1_client, ligue1_api_v1 = get_dynamic_clients("ligue1_x")
seriea_client, seriea_api_v1 = get_dynamic_clients("seriea_x")
laliga_client, laliga_api_v1 = get_dynamic_clients("laliga_x")

async def take_screenshot(fixture_id, target_date):
    print(f"📸 Booting headless browser for Fixture {fixture_id}...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1080, 'height': 1350})
        
        # Inject the date and fixture directly into the URL!
        url = f"https://futbolstartingeleven.com/matchup_card.html?date={target_date}&fixture={fixture_id}"
        print(f"🌐 Navigating to {url}...")
        await page.goto(url)
        
        # Wait for the specific players to render
        try:
            await page.wait_for_selector(".player-node", timeout=10000)
            await asyncio.sleep(2) # Extra buffer for images/fonts
        except Exception:
            print("⚠️ Timeout waiting for players. Taking screenshot anyway...")

        capture_area = page.locator("#capture-area")
        await capture_area.screenshot(path="temp_matchup.png")
        print("✅ Screenshot saved!")
        await browser.close()

async def take_mlb_screenshot(game_pk, side, target_date):
    print(f"📸 Booting headless browser for MLB Game {game_pk} ({side})...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1080, 'height': 1350})
        
        # ⚠️ UPDATE THIS URL TO YOUR HOSTED HTML FILE ⚠️
        url = f"https://mlbstartingnine.com/mlb_card.html?date={target_date}&gamePk={game_pk}&side={side}"
        print(f"🌐 Navigating to {url}...")
        await page.goto(url)
        
        # Wait for the players to render from the API
        try:
            # If the players don't load in 15 seconds, this throws an error and jumps to 'except'
            # Wait specifically for the 9th batter in the lineup container to appear
            await page.locator("#lineup-container .player-row").nth(8).wait_for(timeout=15000)
            await asyncio.sleep(2) # Buffer for images and fonts to snap into place
            
            capture_area = page.locator("#capture-area")
            await capture_area.screenshot(path="mlb_matchup.png")
            print("✅ MLB Screenshot saved!")
            await browser.close()
            return True
            
        except Exception as e:
            print(f"⚠️ Players failed to load. Aborting screenshot. Error: {e}")
            await browser.close()
            return False

async def take_nba_screenshot(team_abbr, side, target_date):
    print(f"📸 Booting headless browser for NBA {team_abbr} ({side})...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # 1080x1080 for the square layout
        page = await browser.new_page(viewport={'width': 1080, 'height': 1080})
        
        # Uses the ?team= parameter so the HTML safely finds the right matchup
        url = f"https://nbastartingfive.com/nba_card.html?date={target_date}&team={team_abbr}&side={side}"
        print(f"🌐 Navigating to {url}...")
        await page.goto(url)
        
        try:
            await page.wait_for_selector(".player-node", timeout=15000)
            await asyncio.sleep(3) # Extra buffer for ESPN headshots and fonts
            
            capture_area = page.locator("#capture-area")
            await capture_area.screenshot(path="nba_matchup.png")
            print("✅ NBA Screenshot saved!")
            await browser.close()
            return True
            
        except Exception as e:
            print(f"⚠️ Players failed to load. Aborting screenshot. Error: {e}")
            await browser.close()
            return False
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
NBA_DATA_URL = f"https://nbastartingfive.com/data/{date_str}.json?v={today_est.timestamp()}"

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
            team_hash = team_name.replace(" ", "")
            
            # FIX: Determine "side" for the HTML URL
            side = "away" if team == away_team else "home"

            # 1. Build the lightweight text payload
            tweet_text = f"🏀 {game_date_short} {team_name} Starting Lineup is Out\n\n"
            bsky_text = f"🏀 {game_date_short} {team_name} Starting Lineup is Out\n\n"
            
            if odds_str:
                tweet_text += f"📊 Live Line:{odds_str}\n\n"
                bsky_text += f"📊 Live Line:{odds_str}\n\n"
                
            link_url = f"https://nbastartingfive.com/#game-{url_game_id}"
            
            if random.randint(1, 100) <= 100:
                tweet_text += f"Full matchups, stats, & odds:\n{link_url}\n\n"
                bsky_text += f"Full matchups, stats, & odds:\n"
                
            tags_text = f"#{team_hash} #{team_hash}Lineup #NBA"
            tweet_text += tags_text
            
            bsky_tb = client_utils.TextBuilder()
            bsky_tb.text(bsky_text)
            bsky_tb.link(link_url, link_url)
            bsky_tb.text("\n\n")
            bsky_tb.text(tags_text)

            # 2. Generate the Graphic via Playwright (With 1 Retry)
            screenshot_success = False
            for attempt in range(2):
                try:
                    if asyncio.run(take_nba_screenshot(team, side, date_str)):
                        screenshot_success = True
                        break 
                    else:
                        print(f"⚠️ NBA Screenshot attempt {attempt + 1} failed. Pausing...")
                        time.sleep(5)
                except Exception as e:
                    print(f"❌ Playwright crashed: {e}")
                    time.sleep(5)
                    
            if not screenshot_success:
                print(f"⏭️ Skipping {team_name} tweet due to screenshot failure. Will retry next run.")
                continue 

            # 3. Upload and Post
            try:
                print("⬆️ Uploading NBA graphic to X servers...")
                media = nba_api_v1.media_upload("nba_matchup.png")
                
                nba_client.create_tweet(text=tweet_text, media_ids=[media.media_id])
                print(f"✅ Successfully tweeted {team_name} NBA lineup graphic!")
                
                # --- START BLUESKY UPLOAD ---
                config = LEAGUE_CONFIG.get("nba")
                if config and config.get("bsky_client"):
                    try:
                        with Image.open("nba_matchup.png") as img:
                            rgb_img = img.convert('RGB')
                            img_byte_arr = io.BytesIO()
                            rgb_img.save(img_byte_arr, format='JPEG', quality=70)
                            img_data = img_byte_arr.getvalue()

                        config["bsky_client"].send_image(text=bsky_tb, image=img_data, image_alt=f"{team_name} Starting Lineup")
                        print(f"✅ Successfully posted {team_name} to Bluesky (Compressed JPEG)!")
                    except Exception as e:
                        print(f"❌ Bluesky post failed for {team_name}: {e}")
                # --- END BLUESKY UPLOAD ---
                
                # Clean up local file
                if os.path.exists("nba_matchup.png"):
                    os.remove("nba_matchup.png")
                
                # Log success into memory
                log_today.append(team_date_key)
                tweeted_recently.append(team_date_key)
                new_tweets_sent = True
                memory[date_str] = log_today
                save_memory_safely(memory)
                time.sleep(5)
                
            except Exception as e:
                print(f"❌ Failed to tweet {team_name}: {e}")

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

def get_lineup_hash(players_array):
    """Generates a simple string hash of the 9 starters: '123-456-789...'"""
    return "-".join([str(p['id']) for p in players_array[:9]])

for game in games:
    game_pk = str(game['gamePk'])
    
    # ----------------------------------------------------
    # NEW: POSTPONEMENT CHECK
    # ----------------------------------------------------
    status = game.get('status', {})
    if status.get('detailedState') == 'Postponed':
        postponed_key = f"MLB_POSTPONED_{game_pk}"
        
        # If we haven't tweeted this postponement yet
        if postponed_key not in tweeted_recently:
            # Safely extract team names just for this alert
            away_full = game['teams']['away']['team']['name']
            home_full = game['teams']['home']['team']['name']
            away_short = get_short_name(away_full, game['teams']['away']['team'].get('teamName'))
            home_short = get_short_name(home_full, game['teams']['home']['team'].get('teamName'))
            
            # Grab the reason (e.g., "Rain") if it exists
            reason = status.get('reason', 'unspecified reasons')
            
            # Build the alert text
            away_hash = away_short.replace(" ", "")
            home_hash = home_short.replace(" ", "")
            alert_text = f"🚨 POSTPONED: The game between the {away_short} and {home_short} has been postponed due to {reason}.\n\n#{away_hash} #{home_hash} #MLB"
            
            print(f"🚨 ALERT TRIGGERED: {away_short} vs {home_short} Postponed!")
            
            # Post to platforms
            try:
                # 1. Tweet to X
                mlb_client.create_tweet(text=alert_text)
                print(f"✅ Successfully tweeted postponement for {away_short} vs {home_short}!")
                
                # 2. Post to Bluesky (Text only)
                config = LEAGUE_CONFIG.get("mlb")
                if config and config.get("bsky_client"):
                    bsky_tb = client_utils.TextBuilder()
                    bsky_tb.text(alert_text)
                    try:
                        config["bsky_client"].send_post(bsky_tb)
                    except Exception as e:
                        print(f"❌ Bluesky post failed for postponement: {e}")

                # 3. Log it & save memory so we don't spam it
                log_today.append(postponed_key)
                tweeted_recently.append(postponed_key)
                new_tweets_sent = True
                memory[date_str] = log_today
                save_memory_safely(memory)
                time.sleep(5)
                
            except Exception as e:
                print(f"❌ Failed to tweet postponement: {e}")
                
        # CRITICAL: Skip the lineup feed logic for this game regardless
        continue
    # ----------------------------------------------------
    
    positions, hands = {}, {}
    try:
        feed_data = requests.get(f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live").json()
        box_teams = feed_data.get('liveData', {}).get('boxscore', {}).get('teams', {})
        all_players = {**box_teams.get('away', {}).get('players', {}), **box_teams.get('home', {}).get('players', {})}
        for pid, p_data in all_players.items():
            person_id = p_data.get('person', {}).get('id')
            if p_data.get('position') and p_data['position'].get('abbreviation'): 
                positions[person_id] = p_data['position'].get('abbreviation', '')
            elif p_data.get('allPositions'): 
                positions[person_id] = p_data['allPositions'][0].get('abbreviation', '')

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
    
    def parse_odds_time(date_str):
        if date_str.endswith('Z'): date_str = date_str[:-1]
        if len(date_str.split(':')) == 2: date_str += ":00"
        try: return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp() * 1000
        except: return 0
            
    try: game_time_ms = datetime.strptime(game['gameDate'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp() * 1000
    except: game_time_ms = 0

    potential_odds = [o for o in odds_data if o['home_team'] == home_full and o['away_team'] == away_full]
    if potential_odds and game_time_ms > 0:
        closest_odds = sorted(potential_odds, key=lambda o: abs(parse_odds_time(o['commence_time']) - game_time_ms))[0]
        for bookie in closest_odds.get('bookmakers', []):
            h2h = next((m for m in bookie['markets'] if m['key'] == 'h2h'), None)
            totals = next((m for m in bookie['markets'] if m['key'] == 'totals'), None)
            if h2h:
                for outcome in h2h['outcomes']:
                    if outcome['name'] == away_full: raw_away_odds = outcome['price']
                    if outcome['name'] == home_full: raw_home_odds = outcome['price']
            if totals and totals['outcomes']: raw_total = totals['outcomes'][0]['point']
            if raw_away_odds != "TBD": break

    total_string = f" • O/U {raw_total}" if raw_total != "TBD" else ""
    away_odds_str = format_odds(raw_away_odds)
    home_odds_str = format_odds(raw_home_odds)

    def send_mlb_tweet(game_pk, team_short, side, date_string, team_hash, team_odds, total_string, alert_header=None):
        # 1. Build the lightweight text payload
        if alert_header:
            tweet_text = f"{alert_header}\n\n"
            bsky_text = f"{alert_header}\n\n"
        else:
            header_text = f"{game_date_short} ⚾ {team_short} Lineup is Out\n\n"
            tweet_text = header_text
            bsky_text = header_text
        
        # --- INJECT THE ODDS HERE ---
        if team_odds != "TBD":
            odds_display = f"📊 Live Line: {team_short} {team_odds}{total_string}\n\n"
            tweet_text += odds_display
            bsky_text += odds_display
        
        link_url = f"https://mlbstartingnine.com/#game-{game_pk}"
        
        if random.randint(1, 100) <= 100 and not alert_header:
            tweet_text += f"Full matchup stats, BvP, & umpire ratings:\n{link_url}\n\n"
            bsky_text += f"Full matchup stats, BvP, & umpire ratings:\n"
        
        tags_text = f"#{team_hash} #{team_hash}Lineup #MLB"
        tweet_text += tags_text
        
        bsky_tb = client_utils.TextBuilder()
        bsky_tb.text(bsky_text)
        if not alert_header:
            bsky_tb.link(link_url, link_url)
            bsky_tb.text("\n\n")
        bsky_tb.text(tags_text)

        # 2. Generate the Graphic via Playwright (With 1 Retry)
        screenshot_success = False
        for attempt in range(2):
            try:
                if asyncio.run(take_mlb_screenshot(game_pk, side, date_string)):
                    screenshot_success = True
                    break # The screenshot worked! Break out of the retry loop.
                else:
                    print(f"⚠️ Screenshot attempt {attempt + 1} failed. Pausing for 5 seconds then retrying...")
                    time.sleep(5)
            except Exception as e:
                print(f"❌ Playwright crashed on attempt {attempt + 1}: {e}")
                time.sleep(5)
                
        # If both attempts failed, abort the tweet so it can try again on the next cron run
        if not screenshot_success:
            print(f"⏭️ Skipping {team_short} tweet due to screenshot failure. Will retry next run.")
            return False

        # 3. Upload and Post
        try:
            print("⬆️ Uploading MLB graphic to X servers...")
            media = mlb_api_v1.media_upload("mlb_matchup.png")
            
            mlb_client.create_tweet(text=tweet_text, media_ids=[media.media_id])
            print(f"✅ Successfully tweeted {team_short} MLB lineup graphic!")
            
            # --- START BLUESKY UPLOAD FIX ---
            config = LEAGUE_CONFIG.get("mlb")
            if config and config.get("bsky_client"):
                try:
                    # 1. Open the massive PNG we generated for Twitter
                    with Image.open("mlb_matchup.png") as img:
                        # 2. Convert it to RGB (removes transparency so JPEG works)
                        rgb_img = img.convert('RGB')
                        
                        # 3. Save it to a temporary memory buffer as a highly compressed JPEG
                        img_byte_arr = io.BytesIO()
                        rgb_img.save(img_byte_arr, format='JPEG', quality=70)
                        
                        # 4. Get the raw bytes to send to Bluesky (now well under 1MB!)
                        img_data = img_byte_arr.getvalue()

                    # Send the lightweight JPEG data to Bluesky
                    config["bsky_client"].send_image(text=bsky_tb, image=img_data, image_alt=f"{team_short} Starting Lineup")
                    print(f"✅ Successfully posted {team_short} to Bluesky (Compressed JPEG)!")
                except Exception as e:
                    print(f"❌ Bluesky post failed for {team_short}: {e}")
            # --- END BLUESKY UPLOAD FIX ---
            
            return True
        except Exception as e:
            print(f"❌ Failed to tweet {team_short}: {e}")
            return False

       

    # ==========================================
    # 🧠 THE SMART DIFF ENGINE
    # ==========================================
    for side in ['away', 'home']:
        players_array = game.get('lineups', {}).get(f'{side}Players', [])
        
        # FIX: A real lineup has at least 9 players. If it's just the pitcher, skip it!
        if not players_array or len(players_array) < 9: 
            continue

        current_hash = get_lineup_hash(players_array)
        base_key = f"{game_pk}_{side}"
        full_key = f"{base_key}_{current_hash}"

        team_short_ref = away_short if side == 'away' else home_short
        team_p_ref = away_pitcher_str if side == 'away' else home_pitcher_str
        team_o_ref = away_odds_str if side == 'away' else home_odds_str
        opp_p_ref = home_pitcher_str if side == 'away' else away_pitcher_str
        opp_o_ref = home_odds_str if side == 'away' else away_odds_str

        previously_tweeted_keys = [k for k in tweeted_recently if k.startswith(base_key + "_")]

        # --- 1. FIRST TIME TWEET ---
        if not previously_tweeted_keys:
            team_hash = team_short_ref.replace(" ", "")
            # Pass the odds variables right after team_hash!
            if send_mlb_tweet(game_pk, team_short_ref, side, date_str, team_hash, team_o_ref, total_string):
                log_today.append(full_key)
                tweeted_recently.append(full_key)
                new_tweets_sent = True

        # --- 2. LATE SCRATCH / SHUFFLE ALERTS ---
        elif full_key not in previously_tweeted_keys:
            old_key = previously_tweeted_keys[0] 
            old_hash = old_key.replace(f"{base_key}_", "")
            
            old_ids = old_hash.split('-')
            new_ids = current_hash.split('-')

            out_ids = [pid for pid in old_ids if pid not in new_ids]
            in_ids = [pid for pid in new_ids if pid not in old_ids]

            alert_header = ""

            # Scenario A: Lineup Shuffle
            if len(out_ids) == 0 and len(in_ids) == 0:
                alert_header = f"⚠️ {team_short_ref} LINEUP SHUFFLE: The batting order has changed."
            
            # Scenario B & C: Late Scratch(es)
            else:
                out_names = []
                if out_ids:
                    try:
                        # Fetch the names of the scratched players directly from MLB
                        out_data = requests.get(f"https://statsapi.mlb.com/api/v1/people?personIds={','.join(out_ids)}").json()
                        out_names = [p['fullName'] for p in out_data.get('people', [])]
                    except:
                        out_names = ["Unknown Player"]

                in_names = []
                for pid in in_ids:
                    # The new players are already in the array we possess
                    player_obj = next((p for p in players_array if str(p['id']) == pid), None)
                    if player_obj: in_names.append(player_obj.get('fullName', 'Unknown Player'))

                out_str = ", ".join(out_names) if out_names else "None"
                in_str = ", ".join(in_names) if in_names else "None"
                
                alert_header = f"🚨 {team_short_ref} LATE SCRATCH\nOUT: {out_str}\nIN: {in_str}"

            print(f"🚨 ALERT TRIGGERED FOR {team_short_ref}:\n{alert_header}")

            team_hash = team_short_ref.replace(" ", "")
            # Pass the odds variables here too!
            if send_mlb_tweet(game_pk, team_short_ref, side, date_str, team_hash, team_o_ref, total_string, alert_header=alert_header):
                # Clean up old key to prevent duplicate tweets on the next run
                for k in previously_tweeted_keys:
                    if k in log_today: log_today.remove(k)
                    if k in tweeted_recently: tweeted_recently.remove(k)
                
                log_today.append(full_key)
                tweeted_recently.append(full_key)
                new_tweets_sent = True



# ==========================================
# 6. MULTI-LEAGUE FUTBOL ENGINE
# ==========================================
print("\n--- STARTING MULTI-LEAGUE FUTBOL ENGINE ---")

# Define all leagues, their tags, and optionally their dedicated X client and URL
FUTBOL_LEAGUES = {
    39:  {"name": "\U0001f3f4\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f PREMIER LEAGUE", "tag": "#EPL", "url_slug": "epl"},
    140: {"name": "🇪🇸 LA LIGA", "tag": "#LaLiga", "url_slug": "laliga", "x_client": laliga_client, "v1_client": laliga_api_v1, "base_url": "https://futbolstartingeleven.com/laliga.html"},
    135: {"name": "SERIE A 🇮🇹", "tag": "#SerieA", "url_slug": "seriea", "x_client": seriea_client, "v1_client": seriea_api_v1, "base_url": "https://futbolstartingeleven.com/seriea.html"},
    2:   {"name": "🇪🇺 CHAMPIONS LEAGUE", "tag": "#UCL", "url_slug": "ucl"},
    45:  {"name": "\U0001f3f4\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f FA CUP", "tag": "#FACup", "url_slug": "facup"},
    40:  {"name": "\U0001f3f4\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f CHAMPIONSHIP", "tag": "#Championship", "url_slug": "championship", "x_client": championship_client, "v1_client": championship_api_v1, "base_url": "https://futbolstartingeleven.com/championship.html"},
    78:  {"name": "🇩🇪 BUNDESLIGA", "tag": "#Bundesliga", "url_slug": "bundesliga", "x_client": bundesliga_client, "v1_client": bundesliga_api_v1, "base_url": "https://futbolstartingeleven.com/bundesliga.html"},
    254: {"name": "🇺🇸 NWSL", "tag": "#NWSL", "url_slug": "nwsl", "x_client": nwsl_client, "v1_client": nwsl_api_v1, "base_url": "https://futbolstartingeleven.com/nwsl.html"},
    253: {"name": "🇺🇸 MLS", "tag": "#MLS", "url_slug": "mls", "x_client": mls_client, "v1_client": mls_api_v1, "base_url": "https://futbolstartingeleven.com/mls.html"},
    61:  {"name": "🇫🇷 LIGUE 1", "tag": "#Ligue1", "url_slug": "ligue1", "x_client": ligue1_client, "v1_client": ligue1_api_v1, "base_url": "https://futbolstartingeleven.com/ligue1.html"},
    3:   {"name": "🇪🇺 EUROPA LEAGUE", "tag": "#EuropaLeague", "url_slug": "europa"},
    13:  {"name": "🌎 COPA LIBERTADORES", "tag": "#Libertadores", "url_slug": "libertadores"},
    16:  {"name": "🏆 CHAMPIONS CUP", "tag": "#ChampionsCup", "url_slug": "concacaf"},
    71:  {"name": "🇧🇷 BRASILEIRÃO", "tag": "#Brasileirao", "url_slug": "brazil"},
    128: {"name": "🇦🇷 LIGA PROFESIONAL", "tag": "#LigaProfesional", "url_slug": "argentina"},
    88:  {"name": "🇳🇱 EREDIVISIE", "tag": "#Eredivisie", "url_slug": "eredivisie" },
    262: {"name": "🇲🇽 LIGA MX", "tag": "#LigaMX", "url_slug": "ligamx"},
    94:  {"name": "🇵🇹 PRIMEIRA LIGA", "tag": "#PrimeiraLiga", "url_slug": "portugal"},
    239: {"name": "🇨🇴 PRIMERA A", "tag": "#PrimeraA", "url_slug": "colombia"},
    188: {"name": "🇦🇺 A-LEAGUE", "tag": "#ALeague", "url_slug": "australia"},
    11:  {"name": "🌎 COPA SUDAMERICANA", "tag": "#Sudamericana #LaGranConquista", "url_slug": "sudamericana"},
    5:   {"name": "🇪🇺 UEFA NATIONS LEAGUE", "tag": "#NationsLeague #UNL", "url_slug": "uefanations"},
    531: {"name": "🌎 CONCACAF NATIONS LEAGUE", "tag": "#CNL #Concacaf", "url_slug": "concacafnations"},
    307: { "name": "🇸🇦 SAUDI PRO LEAGUE", "tag": "#SaudiProLeague #SPL", "url_slug": "saudi" },
    10:  {"name": "🌎 INTERNATIONAL", "tag": "#Friendly", "url_slug": "intl", "x_client": friendly_client, "v1_client": friendly_api_v1, "base_url": "https://futbolstartingeleven.com/friendlies.html"}
}


# ==========================================
# NATIONAL TEAM FLAG DICTIONARY (MASTER LIST)
# ==========================================
INTL_FLAGS = {
    # --- The UK Nations (Explicit Unicode escapes to prevent file corruption) ---
    "England": "\U0001f3f4\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f",
    "Scotland": "\U0001f3f4\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f",
    "Wales": "\U0001f3f4\U000e0067\U000e0062\U000e0077\U000e006c\U000e0073\U000e007f",
    "Northern Ireland": "🇬🇧", # Standard emoji fallback for NI

    # --- Global Nations (Alphabetical) ---
    "Albania": "🇦🇱",
    "Algeria": "🇩🇿",
    "Argentina": "🇦🇷",
    "Australia": "🇦🇺",
    "Austria": "🇦🇹",
    "Belgium": "🇧🇪",
    "Bolivia": "🇧🇴",
    "Bosnia and Herzegovina": "🇧🇦",
    "Brazil": "🇧🇷",
    "Bulgaria": "🇧🇬",
    "Burkina Faso": "🇧🇫",
    "Cameroon": "🇨🇲",
    "Canada": "🇨🇦",
    "Chile": "🇨🇱",
    "China": "🇨🇳",
    "Colombia": "🇨🇴",
    "Costa Rica": "🇨🇷",
    "Croatia": "🇭🇷",
    "Czech Republic": "🇨🇿",
    "Denmark": "🇩🇰",
    "DR Congo": "🇨🇩",
    "Ecuador": "🇪🇨",
    "Egypt": "🇪🇬",
    "El Salvador": "🇸🇻",
    "Finland": "🇫🇮",
    "France": "🇫🇷",
    "Georgia": "🇬🇪",
    "Germany": "🇩🇪",
    "Ghana": "🇬🇭",
    "Greece": "🇬🇷",
    "Guatemala": "🇬🇹",
    "Guinea": "🇬🇳",
    "Honduras": "🇭🇳",
    "Hungary": "🇭🇺",
    "Iceland": "🇮🇸",
    "Iran": "🇮🇷",
    "Iraq": "🇮🇶",
    "Israel": "🇮🇱",
    "Italy": "🇮🇹",
    "Ivory Coast": "🇨🇮",
    "Jamaica": "🇯🇲",
    "Japan": "🇯🇵",
    "Mali": "🇲🇱",
    "Mexico": "🇲🇽",
    "Montenegro": "🇲🇪",
    "Morocco": "🇲🇦",
    "Netherlands": "🇳🇱",
    "New Zealand": "🇳🇿",
    "Nigeria": "🇳🇬",
    "North Macedonia": "🇲🇰",
    "Norway": "🇳🇴",
    "Oman": "🇴🇲",
    "Panama": "🇵🇦",
    "Paraguay": "🇵🇾",
    "Peru": "🇵🇪",
    "Poland": "🇵🇱",
    "Portugal": "🇵🇹",
    "Qatar": "🇶🇦",
    "Republic of Ireland": "🇮🇪",
    "Romania": "🇷🇴",
    "Saudi Arabia": "🇸🇦",
    "Senegal": "🇸🇳",
    "Serbia": "🇷🇸",
    "Slovakia": "🇸🇰",
    "Slovenia": "🇸🇮",
    "South Africa": "🇿🇦",
    "South Korea": "🇰🇷",
    "Spain": "🇪🇸",
    "Sweden": "🇸🇪",
    "Switzerland": "🇨🇭",
    "Trinidad and Tobago": "🇹🇹",
    "Tunisia": "🇹🇳",
    "Turkey": "🇹🇷",
    "UAE": "🇦🇪",
    "Ukraine": "🇺🇦",
    "Uruguay": "🇺🇾",
    "USA": "🇺🇸",
    "Uzbekistan": "🇺🇿",
    "Venezuela": "🇻🇪"
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
        raw_h_name = home_t['name']
        
        a_rank = f"[{away_t['rank']}] " if away_t.get('rank') else ""
        a_rec = f"({away_t['record']})" if away_t.get('record') else ""
        raw_a_name = away_t['name']
        
        # If it's the International Friendlies league (10), append the flag!
        if league_id == 10:
            h_name = f"{INTL_FLAGS.get(raw_h_name, '')} {raw_h_name}".strip()
            a_name = f"{INTL_FLAGS.get(raw_a_name, '')} {raw_a_name}".strip()
        else:
            h_name = raw_h_name
            a_name = raw_a_name
        
        print(f"[{fixture_id}] Both lineups found for {h_name} vs {a_name} ({league_info['tag']}). Building tweet...")

        # 1. Pick a random emoji and a random clean title
        EMOJIS = ["🚨", "⚽", "📋", "⚔️", "🏟️", "🔥", "📢", "✅", "🔒", "📝"]
        e = random.choice(EMOJIS)
        
        TITLES = [
            f"{e} OFFICIAL STARTING XI: {league_info['name']}",
            f"{e} {h_name} vs {a_name} starting lineups are out!",
            f"{e} {h_name} and {a_name} have released their starting XI!",
            f"{e} Lineups confirmed! {h_name} takes on {a_name} in {league_info['name']}.",
            f"{e} The starting XI for {h_name} vs {a_name} is locked in.",
            f"{e} {league_info['name']} action incoming! Here are the lineups for {h_name} vs {a_name}.",
            f"{e} Team news is in for {h_name} vs {a_name}!",
            f"{e} Managers have named their starting XI for {h_name} vs {a_name}.",
            f"{e} Official lineups for today's {league_info['name']} clash between {h_name} and {a_name}.",
            f"{e} {h_name} vs {a_name} lineups are confirmed. {league_info['name']}"
        ]
        chosen_title = random.choice(TITLES)
        
        # 2. Add the records/ranks neatly below the title
        matchup_line = f"{h_rank}{h_name} {h_rec} vs {a_rank}{a_name} {a_rec}".replace("  ", " ").strip()
        header = f"{chosen_title}\n{matchup_line}"
        
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
        
        h_hash = raw_h_name.replace(' ', '').replace('-', '').replace('.', '')
        a_hash = raw_a_name.replace(' ', '').replace('-', '').replace('.', '')
        
        # 3. Clean Footer: Link ALWAYS visible + strictly 3 hashtags
        base_url = league_info.get("base_url", f"https://futbolstartingeleven.com/?league=top&date={target_date_str}")
        footer_text = f"📱 Live stats & scores: {base_url}#lineup-{fixture_id}\n\n"
        footer = f"{footer_text}{league_info['tag']} #{h_hash} #{a_hash}"

        # ---------------------------------------------------------
        # NEW: UNIVERSAL IMAGE TWEET LOGIC (NO TEXT LINEUPS, NO INJURIES)
        # ---------------------------------------------------------
        try:
            print(f"📸 Match detected! Generating graphic for {h_name} vs {a_name}...")

            # Reorder the tweet: Header, Link, Odds, Hashtags
            base_url = league_info.get("base_url", f"https://futbolstartingeleven.com/?league=top&date={target_date_str}")
            link_text = f"📱 Live stats & scores: {base_url}#lineup-{fixture_id}"
            tags_text = f"{league_info['tag']} #{h_hash} #{a_hash}"
            
            tweet_parts = [header, link_text, odds_str, tags_text]
            tweet_text = "\n\n".join(tweet_parts)

            # 1. Take the screenshot (halts script temporarily to run async)
            asyncio.run(take_screenshot(fixture_id, target_date_str))

            # 2. Identify the correct clients for this specific league
            target_client = league_info.get("x_client") or futbol_client
            target_v1_client = league_info.get("v1_client") or futbol_api_v1

            # 3. Upload the image using the correct V1.1 API
            print("⬆️ Uploading graphic to X servers...")
            media = target_v1_client.media_upload("temp_matchup.png")

            # 4. Post the V2 Tweet with the media attached
            if target_client:
                target_client.create_tweet(text=tweet_text, media_ids=[media.media_id])
                print(f"✅ [{league_info['name']}] Successfully tweeted graphic for {h_name} vs {a_name}!")
            else:
                print(f"⚠️ Target client for {league_info['name']} is missing credentials. Skipping tweet.")

            # 5. Clean up the server
            if os.path.exists("temp_matchup.png"):
                os.remove("temp_matchup.png")

            # Log success into memory
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
    # NEW: Fetch live data from Firebase instead of the static JSON
    live_futbol_data = {}
    if target_date_str == date_str: # Only use Firebase for 'Today'
        try:
            live_ref = db.reference('futbol_live_games')
            live_snapshot = live_ref.get()
            if live_snapshot:
                # Convert dictionary {id: data} into a list [data, data] to match your existing loop logic
                live_futbol_data = list(live_snapshot.values())
                print(f"📡 Fetched {len(live_futbol_data)} live games from Firebase for alerts.")
        except Exception as e:
            print(f"⚠️ Firebase fetch failed: {e}")

    # Fallback/Merge: If it's a past/future date or Firebase failed, we can use the local file
    # but for live alerts, we primarily want the Firebase list.
    alerts_source = live_futbol_data if live_futbol_data else futbol_data

    for match in alerts_source:
        league_id = match.get('league', {}).get('id')
        if league_id not in FUTBOL_LEAGUES: continue
            
        league_info = FUTBOL_LEAGUES[league_id]
        fixture_id = match.get('fixture', {}).get('id')
        fixture_status = match.get('fixture', {}).get('status', {}).get('short', '')
        
        events = match.get('events', [])
        if not events: continue
            
        h_id = match['teams']['home']['id']
        a_id = match['teams']['away']['id']
        raw_h_name = match['teams']['home']['name']
        raw_a_name = match['teams']['away']['name']
        
        if league_id == 10:
            h_name = f"{INTL_FLAGS.get(raw_h_name, '')} {raw_h_name}".strip()
            a_name = f"{INTL_FLAGS.get(raw_a_name, '')} {raw_a_name}".strip()
        else:
            h_name = raw_h_name
            a_name = raw_a_name
        
        official_home_score = int(match.get('goals', {}).get('home') or 0)
        official_away_score = int(match.get('goals', {}).get('away') or 0)
        
        # --- 🕒 CRITICAL FIX: UNIVERSAL TIME EXTRACTOR ---
        def get_actual_minute(e):
            t_str = str(e.get('time', '0')).replace("'", "").strip()
            if '+' in t_str:
                parts = t_str.split('+')
                try: return int(parts[0]) + int(parts[1])
                except ValueError: return int(parts[0]) if parts[0].isdigit() else 90
            return int(t_str) if t_str.isdigit() else 0

        # --- 🛡️ SHOOTOUT PRE-FILTER ---
        valid_goal_events = []
        is_shootout = fixture_status in ['P', 'PEN']
        
        # Fallback Check using the new universal time math
        late_penalties = sum(1 for e in events if e.get('type') == 'Goal' and e.get('detail') == 'Penalty' and get_actual_minute(e) >= 90)
        if late_penalties > 1:
            is_shootout = True
            
        for e in events:
            if e.get('type') == 'Goal' and e.get('detail') in ['Normal Goal', 'Penalty']:
                e_time = get_actual_minute(e)
                
                # Nuke shootout penalties so they don't corrupt the live score or trigger tweets
                if e.get('detail') == 'Penalty' and e_time >= 90 and is_shootout:
                    continue
                
                valid_goal_events.append(e)

        # Sort goals chronologically to prevent out-of-order API arrays
        valid_goal_events.sort(key=get_actual_minute)

        # 🛑 START AT ZERO! Only count goals that actually exist in the events array!
        current_home_score = 0
        current_away_score = 0
        
        home_odds_str = match.get('odds', {}).get('home', 'TBD')
        away_odds_str = match.get('odds', {}).get('away', 'TBD')
        try: home_odds = float(home_odds_str) if home_odds_str != 'TBD' else 0.0
        except ValueError: home_odds = 0.0
        try: away_odds = float(away_odds_str) if away_odds_str != 'TBD' else 0.0
        except ValueError: away_odds = 0.0

        for event in valid_goal_events: 
            team_id = event.get('team_id')
            
            if team_id == h_id:
                current_home_score += 1
                team_goal_count = current_home_score
            else:
                current_away_score += 1
                team_goal_count = current_away_score
                
            # Automatically adds 90 + 4 to output 94
            event_time = get_actual_minute(event)
            
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
            
            h_hash = raw_h_name.replace(' ', '').replace('-', '').replace('.', '')
            a_hash = raw_a_name.replace(' ', '').replace('-', '').replace('.', '')
            
            # Dynamic URL reading from the dictionary
            base_url = league_info.get("base_url", f"https://futbolstartingeleven.com/?league=top&date={target_date_str}")
            link = f"{base_url}#goal-{fixture_id}"
            
            title = random.choice(PHRASES[scenario_key]["titles"])
            blurb_raw = random.choice(PHRASES[scenario_key]["blurbs"])
            cta = random.choice(PHRASES[scenario_key]["ctas"])
            
            blurb = blurb_raw.format(scoring_team_name=scoring_team_name, conceding_team_name=conceding_team_name)

            tweet_text = f"{title}\n\n⚽ {event_time}' GOAL - {scorer_str}\n{h_name} {calc_home_score} - {calc_away_score} {a_name}\n\n"
            if "upset" in scenario_key: tweet_text += f"📊 Pre-Match Line: {scoring_team_name} ({american_odds})\n\n"
            tweet_text += f"{blurb}\n\n"
            
            # 5% Chance to add the link
            if random.randint(1, 100) <= 100:
                tweet_text += f"{cta}\n⬇️\n{link}\n\n"
                
            tweet_text += f"{league_info['tag']} #{h_hash} #{a_hash}"
            
            try:
                # Dynamic client reading from the dictionary
                target_client = league_info.get("x_client") or futbol_client
                
                if target_client:
                    target_client.create_tweet(text=tweet_text)
                    print(f"✅ [{league_info['name']}] Successfully tweeted ALERTS for {scoring_team_name}!")
                else:
                    print(f"⚠️ Target client for {league_info['name']} is missing credentials. Skipping tweet.")
                
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
