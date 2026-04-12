import os
import json
import requests
import tweepy
import zoneinfo
from datetime import datetime, timezone, timedelta
import time
import random
import copy
from atproto import Client, client_utils
import firebase_admin
from firebase_admin import credentials, db
import asyncio
from playwright.async_api import async_playwright
import gc
import subprocess
import sys
import ctypes

# --- AUTOMATIC PLAYWRIGHT BROWSER INSTALL ---
def ensure_browsers():
    try:
        import playwright
        print("🌐 Checking Playwright browser binaries...")
        # Use check_call to block the script until installation is finished
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("✅ Playwright binaries are ready.")
    except Exception as e:
        print(f"⚠️ Playwright auto-install failed: {e}")

# Call it immediately
ensure_browsers()

# ==========================================
# 0. ENVIRONMENT & DRY RUN SETTINGS
# ==========================================
# Set DRY_RUN = False in Render Environment Variables to go live!
DRY_RUN = os.environ.get("DRY_RUN", "True").lower() == "true"

# ==========================================
# 1. FIREBASE INITIALIZATION
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
            print("✅ Firebase authenticated for Render Tweet Bot!")
        except Exception as e:
            print(f"❌ Firebase Auth Failed: {e}")

# ==========================================
# 2. UNIFIED CREDENTIALS & CLIENTS
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

def create_x_clients(consumer_key, consumer_secret, access_token, access_token_secret):
    if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
        return None, None
    client = tweepy.Client(
        consumer_key=consumer_key, consumer_secret=consumer_secret, 
        access_token=access_token, access_token_secret=access_token_secret
    )
    auth = tweepy.OAuth1UserHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    api_v1 = tweepy.API(auth)
    return client, api_v1

def get_dynamic_clients(key):
    creds = auth_data.get(key, {})
    return create_x_clients(
        creds.get("consumer_key"), creds.get("consumer_secret"),
        creds.get("access_token"), creds.get("access_token_secret")
    )

LEAGUE_CONFIG = {
    "mlb": {"league_name": "MLB ⚾", "bsky_client": setup_bsky_client("mlb_account")},
    "nba": {"league_name": "NBA 🏀", "bsky_client": setup_bsky_client("nba_account")}
}

# --- CORE ACCOUNTS ---
mlb_client, mlb_api_v1 = get_dynamic_clients("mlb_x")
nba_client, nba_api_v1 = get_dynamic_clients("nba_x")
futbol_client, futbol_api_v1 = get_dynamic_clients("futbol_x")
friendly_client, friendly_api_v1 = get_dynamic_clients("friendly_x")

# --- SOCCER SUB-ACCOUNTS ---
championship_client, championship_api_v1 = get_dynamic_clients("championship_x")
bundesliga_client, bundesliga_api_v1 = get_dynamic_clients("bundesliga_x")
nwsl_client, nwsl_api_v1 = get_dynamic_clients("nwsl_x")
mls_client, mls_api_v1 = get_dynamic_clients("mls_x")
ligue1_client, ligue1_api_v1 = get_dynamic_clients("ligue1_x")
seriea_client, seriea_api_v1 = get_dynamic_clients("seriea_x")
laliga_client, laliga_api_v1 = get_dynamic_clients("laliga_x")
epl_client, epl_api_v1 = get_dynamic_clients("epl_x")

# ==========================================
# 3. PLAYWRIGHT & HELPER FUNCTIONS
# ==========================================
async def take_screenshot(fixture_id, target_date):
    print(f"📸 Booting headless browser for Fixture {fixture_id}...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-gpu', 
                '--disable-dev-shm-usage', 
                '--no-sandbox', 
                '--disable-setuid-sandbox', 
                '--no-zygote',
                '--single-process', # 🛑 MASSIVE MEMORY SAVER: Runs everything in 1 process
                '--disable-site-isolation-trials', # Disables heavy security sandboxing
                '--disable-features=IsolateOrigins,site-per-process',
                '--js-flags="--max-old-space-size=50"' # 🛑 Limits JS engine to 50MB
            ]
        )
        page = await browser.new_page(viewport={'width': 1080, 'height': 1350})
        url = f"https://futbolstartingeleven.com/matchup_card.html?date={target_date}&fixture={fixture_id}"
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.locator(".player-node").nth(21).wait_for(timeout=30000)
            await asyncio.sleep(2)
            
            capture_area = page.locator("#capture-area")
            await capture_area.screenshot(path="temp_matchup.png", type="png")
            await capture_area.screenshot(path="temp_matchup.jpg", type="jpeg", quality=70)
            print("✅ Futbol Screenshots saved (PNG & JPEG)!")
            await browser.close()
            return True
            
        except Exception as e:
            print(f"⚠️ Futbol Graphics failed. Error: {e}")
            await browser.close()
            return False

async def take_mlb_screenshot(game_pk, side, target_date):
    print(f"📸 Booting headless browser for MLB {game_pk} ({side})...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-gpu', 
                '--disable-dev-shm-usage', 
                '--no-sandbox', 
                '--disable-setuid-sandbox', 
                '--no-zygote',
                '--single-process', # 🛑 MASSIVE MEMORY SAVER: Runs everything in 1 process
                '--disable-site-isolation-trials', # Disables heavy security sandboxing
                '--disable-features=IsolateOrigins,site-per-process',
                '--js-flags="--max-old-space-size=50"' # 🛑 Limits JS engine to 50MB
            ]
        )
        page = await browser.new_page(viewport={'width': 1080, 'height': 1350})
        url = f"https://mlbstartingnine.com/mlb_card.html?date={target_date}&gamePk={game_pk}&side={side}"
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.locator("#lineup-container .player-row").nth(8).wait_for(timeout=30000)
            await asyncio.sleep(2)
            
            capture_area = page.locator("#capture-area")
            await capture_area.screenshot(path="mlb_matchup.png", type="png")
            await capture_area.screenshot(path="mlb_matchup.jpg", type="jpeg", quality=70)
            print("✅ MLB Screenshots saved (PNG & JPEG)!")
            await browser.close()
            return True
            
        except Exception as e:
            print(f"⚠️ MLB Graphics failed. Error: {e}")
            await browser.close()
            return False

async def take_nba_screenshot(team_abbr, side, target_date):
    print(f"📸 Booting headless browser for NBA {team_abbr} ({side})...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-gpu', 
                '--disable-dev-shm-usage', 
                '--no-sandbox', 
                '--disable-setuid-sandbox', 
                '--no-zygote',
                '--single-process', # 🛑 MASSIVE MEMORY SAVER: Runs everything in 1 process
                '--disable-site-isolation-trials', # Disables heavy security sandboxing
                '--disable-features=IsolateOrigins,site-per-process',
                '--js-flags="--max-old-space-size=50"' # 🛑 Limits JS engine to 50MB
            ]
        )
        page = await browser.new_page(viewport={'width': 1080, 'height': 1080})
        url = f"https://nbastartingfive.com/nba_card.html?date={target_date}&team={team_abbr}&side={side}"
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.locator(".player-node").nth(4).wait_for(timeout=30000)
            await asyncio.sleep(2) 
            
            capture_area = page.locator("#capture-area")
            await capture_area.screenshot(path="nba_matchup.png", type="png")
            await capture_area.screenshot(path="nba_matchup.jpg", type="jpeg", quality=70)
            print("✅ NBA Screenshots saved (PNG & JPEG)!")
            await browser.close()
            return True
            
        except Exception as e:
            print(f"⚠️ NBA Graphics failed. Error: {e}")
            await browser.close()
            return False

def get_short_name(full_name, team_name):
    name = team_name if team_name else full_name.split(' ')[-1]
    if 'Red Sox' in full_name: name = 'Red Sox'
    if 'White Sox' in full_name: name = 'White Sox'
    if 'Blue Jays' in full_name: name = 'Blue Jays'
    if name == 'Diamondbacks': name = 'Dbacks'
    for country in ['Dominican Republic', 'United States', 'Puerto Rico', 'Great Britain', 'Chinese Taipei']:
        if country in full_name: name = country
    if 'Korea' in full_name or name == 'Korea': name = 'South Korea'
    return name

def format_odds(price):
    if price == "TBD": return price
    return f"+{price}" if price > 0 else str(price)

def get_lineup_hash(players_array):
    return "-".join([str(p['id']) for p in players_array[:9]])

def parse_futbol_lineup(startXI):
    pos_dict = {'G': [], 'D': [], 'M': [], 'F': []}
    for player_item in startXI:
        p = player_item.get('player', {})
        pos = p.get('pos', 'M')
        if pos not in pos_dict: pos = 'M' 
        pos_dict[pos].append(p.get('name', 'Unknown'))
    return pos_dict

# ==========================================
# 4. THE COLD START MIGRATION BRIDGE
# ==========================================
def fetch_initial_memory():
    """Pulls from Firebase first. If empty, bridges the gap with GitHub."""
    mem = {}
    if firebase_admin._apps:
        try:
            fb_state = db.reference('tweet_log').get()
            if fb_state and isinstance(fb_state, dict):
                print("🗄️ Fetched persistent tweet log from Firebase.")
                return fb_state
        except Exception as e:
            print(f"⚠️ Firebase memory fetch failed: {e}")
            
    # MIGRATION BRIDGE (Update Repo URL here if needed)
    print("🌉 Firebase empty. Bridging gap: Fetching legacy tweet log from GitHub...")
    gh_url = f"https://raw.githubusercontent.com/dfsstartinglineups/mlbstartingnine/refs/heads/main/data/tweet_log.json?v={time.time()}"
    try:
        gh_resp = requests.get(gh_url, headers={'Cache-Control': 'no-cache'}, timeout=10)
        if gh_resp.status_code == 200:
            mem = gh_resp.json()
            print(f"✅ Successfully bridged legacy GitHub log! ({len(mem)} dates found)")
    except Exception as e:
        print(f"⚠️ Failed to fetch GitHub bridge: {e}")
        
    if mem is None:
        mem = {}
    return mem

# ==========================================
# 5. CORE BOT ENGINE (RUNS EVERY LOOP)
# ==========================================
def run_engines(memory):
    # Establish fresh dates and URLs for this specific loop
    today_est = datetime.now(zoneinfo.ZoneInfo("America/New_York"))
    date_str = today_est.strftime('%Y-%m-%d')
    game_date_short = f"{today_est.month}/{today_est.day}"
    yesterday_str = (today_est - timedelta(days=1)).strftime('%Y-%m-%d')
    tomorrow_str = (today_est + timedelta(days=1)).strftime('%Y-%m-%d')

    current_date = today_est.date()
    wbc_start, wbc_end = datetime(2026, 3, 4).date(), datetime(2026, 3, 17).date()
    sport_ids = "1,51" if wbc_start <= current_date <= wbc_end else "1"

    MLB_API_URL = f"https://statsapi.mlb.com/api/v1/schedule?sportId={sport_ids}&date={date_str}&hydrate=probablePitcher,lineups,person"
    MLB_ODDS_URL = "https://weathermlb.com/data/odds.json"
    NBA_DATA_URL = f"https://nbastartingfive.com/data/{date_str}.json?v={today_est.timestamp()}"

    # --- THE JANITOR: Clean old memory ---
    dates_to_keep = [date_str, yesterday_str, tomorrow_str]
    keys_to_delete = [k for k in memory.keys() if k not in dates_to_keep]
    for k in keys_to_delete:
        del memory[k]
        if firebase_admin._apps:
            try:
                db.reference(f'tweet_log/{k}').delete()
                print(f"🧹 Janitor: Deleted old log '{k}' from Firebase.")
            except: pass

    if date_str not in memory: memory[date_str] = []
    log_today = memory[date_str]
    
    tweeted_recently = []
    for date_list in memory.values():
        tweeted_recently.extend(date_list)

    new_tweets_sent = False

    # ==========================================
    # NBA ENGINE
    # ==========================================
    try: nba_data = requests.get(NBA_DATA_URL).json().get('games', [])
    except: nba_data = []

    ESPN_TO_STD = {"NY": "NYK", "NO": "NOP", "SA": "SAS", "GS": "GSW", "WSH": "WAS", "UTAH": "UTA"}
    nba_odds_map = {}
    try:
        espn_date = date_str.replace('-', '')
        espn_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={espn_date}"
        espn_data = requests.get(espn_url).json()
        for event in espn_data.get('events', []):
            espn_game_id = str(event.get('id', ''))
            espn_state = event.get('status', {}).get('type', {}).get('state', 'pre')
            comp = event['competitions'][0]
            spread, ou = "TBD", "TBD"
            if comp.get('odds'):
                spread = comp['odds'][0].get('details', 'TBD')
                ou = comp['odds'][0].get('overUnder', 'TBD')
            for c in comp['competitors']:
                espn_abbr = c['team']['abbreviation'].upper()
                std_abbr = ESPN_TO_STD.get(espn_abbr, espn_abbr)
                nba_odds_map[std_abbr] = {"spread": spread, "ou": ou, "id": espn_game_id, "state": espn_state}
    except: pass

    NBA_TEAM_NAMES = {
        "ATL": "Hawks", "BOS": "Celtics", "BKN": "Nets", "CHA": "Hornets", "CHI": "Bulls", "CLE": "Cavaliers", "DAL": "Mavericks", "DEN": "Nuggets",
        "DET": "Pistons", "GSW": "Warriors", "HOU": "Rockets", "IND": "Pacers", "LAC": "Clippers", "LAL": "Lakers", "MEM": "Grizzlies", "MIA": "Heat",
        "MIL": "Bucks", "MIN": "Timberwolves", "NOP": "Pelicans", "NYK": "Knicks", "OKC": "Thunder", "ORL": "Magic", "PHI": "76ers", "PHX": "Suns",
        "POR": "Trail Blazers", "SAC": "Kings", "SAS": "Spurs", "TOR": "Raptors", "UTA": "Jazz", "WAS": "Wizards"
    }

    for game in nba_data:
        if not game.get('teams') or len(game['teams']) < 2: continue
        away_team, home_team = game['teams'][0], game['teams'][1]
        matchup = f"{away_team} vs {home_team}"
        
        if game.get('date') and game.get('date') != date_str: continue
        if nba_odds_map.get(away_team, {}).get('state') in ['in', 'post']: continue

        meta = game.get('meta', {})
        url_game_id = game.get('id') or f"{away_team}-{home_team}-{date_str}"
        espn_game_id = nba_odds_map.get(away_team, {}).get('id', url_game_id)
            
        final_spread, final_ou = "TBD", "TBD"
        if away_team in nba_odds_map and nba_odds_map[away_team]['spread'] != "TBD":
            final_spread = nba_odds_map[away_team]['spread']
            final_ou = nba_odds_map[away_team]['ou']
        else:
            local_spread = meta.get('spread', 'TBD')
            local_ou = meta.get('total', 'TBD')
            if str(local_spread) not in ["TBD", "nan", "+nan", "None", ""]:
                final_spread = f"{away_team} {local_spread}" if "-" in str(local_spread) else f"{home_team} -{str(local_spread).replace('+', '')}"
            if str(local_ou) not in ["TBD", "nan", "+nan", "None", ""]: final_ou = local_ou
                
        odds_parts = [final_spread] if final_spread != "TBD" else []
        if final_ou != "TBD": odds_parts.append(f"O/U {final_ou}")
        odds_str = f" [{' | '.join(odds_parts)}]" if odds_parts else ""

        for team, data in game.get('rosters', {}).items():
            team_date_key = f"NBA_{team}_{date_str}"
            espn_team_key = f"NBA_{team}_{espn_game_id}" 
            legacy_base_key = f"NBA_{team}"
            
            if team_date_key in tweeted_recently or espn_team_key in tweeted_recently or legacy_base_key in log_today:
                continue
                
            players = data.get('players', [])
            is_official = data.get('is_official') == True or (len(players) >= 5 and all(p.get('verified') == True for p in players))
            
            if is_official:
                opp = matchup.replace(team, '').replace(' vs ', '').strip()
                team_name, opp_name = NBA_TEAM_NAMES.get(team, team), NBA_TEAM_NAMES.get(opp, opp)
                team_hash = team_name.replace(" ", "")
                side = "away" if team == away_team else "home"

                tweet_text = f"🏀 {game_date_short} {team_name} Starting Lineup vs {opp_name}\n\n"
                if odds_str: tweet_text += f"📊 Live Line:{odds_str}\n\n"
                link_url = f"https://nbastartingfive.com/#game-{url_game_id}"
                if random.randint(1, 100) <= 100: tweet_text += f"Full matchups, stats, & odds:\n{link_url}\n\n"
                tweet_text += f"#{team_hash} #{team_hash}Lineup #NBA"
                
                bsky_tb = client_utils.TextBuilder()
                bsky_tb.text(f"🏀 {game_date_short} {team_name} Starting Lineup vs {opp_name}\n\n")
                if odds_str: bsky_tb.text(f"📊 Live Line:{odds_str}\n\n")
                bsky_tb.text("Full matchups, stats, & odds:\n")
                bsky_tb.link(link_url, link_url)
                bsky_tb.text(f"\n\n#{team_hash} #{team_hash}Lineup #NBA")

                # The IN-MEMORY Race Condition check (Since Render is single-instance, we just check local dict)
                if team_date_key in memory.get(date_str, []):
                    continue

                screenshot_success = False
                for attempt in range(2):
                    try:
                        if asyncio.run(take_nba_screenshot(team, side, date_str)):
                            screenshot_success = True
                            break 
                        time.sleep(5)
                    except: time.sleep(5)
                        
                if not screenshot_success: continue 

                alt_parts = [f"Graphical lineup card for the {team_name} starting 5 against the {opp_name}."]
                for p in players[:5]: alt_parts.append(f"{p.get('pos', 'Flex')}: {p.get('name', 'Unknown')}.")
                nba_alt_text = " ".join(alt_parts)[:1000]

                if DRY_RUN:
                    print(f"\n[SHADOW] 🛑 DRY RUN ACTIVE. Mocking NBA Tweet for {team_name}:")
                    print(f"      -> Text: {tweet_text[:80]}...")
                    print(f"      -> Image Generated: True | Alt: {nba_alt_text[:60]}...")
                else:
                    try:
                        media = nba_api_v1.media_upload("nba_matchup.png")
                        nba_api_v1.create_media_metadata(media.media_id, nba_alt_text)
                        nba_client.create_tweet(text=tweet_text, media_ids=[media.media_id])
                        print(f"✅ Successfully tweeted {team_name} NBA lineup graphic!")
                        
                        config = LEAGUE_CONFIG.get("nba")
                        if config and config.get("bsky_client"):
                            with open("nba_matchup.jpg", "rb") as f:
                                img_data = f.read()
                            config["bsky_client"].send_image(text=bsky_tb, image=img_data, image_alt=nba_alt_text)
                            print(f"✅ Successfully posted {team_name} to Bluesky (Native JPEG)!")
                    except Exception as e:
                        print(f"❌ Failed to tweet {team_name}: {e}")

                if os.path.exists("nba_matchup.png"): os.remove("nba_matchup.png")
                if os.path.exists("nba_matchup.jpg"): os.remove("nba_matchup.jpg")
                
                log_today.append(team_date_key)
                tweeted_recently.append(team_date_key)
                memory[date_str] = log_today
                new_tweets_sent = True
                
                # 🛑 KEEPING FIREBASE SYNC:
                if firebase_admin._apps:
                    db.reference('tweet_log').update({date_str: log_today})
                    
                # 🧹 FORCE GARBAGE COLLECTION
                # 🧹 FORCE GARBAGE COLLECTION & LINUX MEMORY FLUSH
                gc.collect()
                try:
                    ctypes.CDLL('libc.so.6').malloc_trim(0)
                except Exception:
                    pass

    # ==========================================
    # MLB ENGINE
    # ==========================================
    try:
        schedule_data = requests.get(MLB_API_URL).json()
        games = schedule_data['dates'][0]['games'] if schedule_data.get('dates') else []
    except:
        games = []

    try: odds_data = requests.get(MLB_ODDS_URL).json().get('odds', [])
    except: odds_data = []

    def send_mlb_tweet(game_pk, team_short, side, date_string, team_hash, team_odds, total_string, alt_text, memory_key, alert_header=None):
        if memory_key in memory.get(date_str, []): return False
        
        tweet_text = f"{alert_header}\n\n" if alert_header else f"{game_date_short} ⚾ {team_short} Lineup is Out\n\n"
        if team_odds != "TBD": tweet_text += f"📊 Live Line: {team_short} {team_odds}{total_string}\n\n"
        link_url = f"https://mlbstartingnine.com/#game-{game_pk}"
        if random.randint(1, 100) <= 100 and not alert_header: tweet_text += f"Full matchup stats, BvP, & umpire ratings:\n{link_url}\n\n"
        tweet_text += f"#{team_hash} #{team_hash}Lineup #MLB"
        
        bsky_tb = client_utils.TextBuilder()
        bsky_tb.text(f"{alert_header}\n\n" if alert_header else f"{game_date_short} ⚾ {team_short} Lineup is Out\n\n")
        if team_odds != "TBD": bsky_tb.text(f"📊 Live Line: {team_short} {team_odds}{total_string}\n\n")
        if not alert_header:
            bsky_tb.text("Full matchup stats, BvP, & umpire ratings:\n")
            bsky_tb.link(link_url, link_url)
            bsky_tb.text("\n\n")
        bsky_tb.text(f"#{team_hash} #{team_hash}Lineup #MLB")

        screenshot_success = False
        for attempt in range(2):
            try:
                if asyncio.run(take_mlb_screenshot(game_pk, side, date_string)):
                    screenshot_success = True
                    break 
                time.sleep(5)
            except: time.sleep(5)
                
        if not screenshot_success: return False

        if DRY_RUN:
            print(f"\n[SHADOW] 🛑 DRY RUN ACTIVE. Mocking MLB Tweet for {team_short}:")
            print(f"      -> Text: {tweet_text[:80]}...")
            print(f"      -> Image Generated: True | Alt: {alt_text[:60]}...")
            if os.path.exists("mlb_matchup.png"): os.remove("mlb_matchup.png")
            return True
        else:
            try:
                media = mlb_api_v1.media_upload("mlb_matchup.png")
                mlb_api_v1.create_media_metadata(media.media_id, alt_text)
                mlb_client.create_tweet(text=tweet_text, media_ids=[media.media_id])
                print(f"✅ Successfully tweeted {team_short} MLB lineup graphic!")
                
                config = LEAGUE_CONFIG.get("mlb")
                if config and config.get("bsky_client"):
                    with open("mlb_matchup.jpg", "rb") as f:
                        img_data = f.read()
                    config["bsky_client"].send_image(text=bsky_tb, image=img_data, image_alt=alt_text)
                    print(f"✅ Successfully posted {team_short} to Bluesky (Native JPEG)!")
            except Exception as e: print(f"❌ Failed to tweet {team_short}: {e}")
            
            if os.path.exists("mlb_matchup.png"): os.remove("mlb_matchup.png")
            if os.path.exists("mlb_matchup.jpg"): os.remove("mlb_matchup.jpg")
            
            # 🧹 FORCE GARBAGE COLLECTION & LINUX MEMORY FLUSH
            gc.collect()
            try:
                ctypes.CDLL('libc.so.6').malloc_trim(0)
            except Exception:
                pass
                
            return True

    

    for game in games:
        game_pk = str(game['gamePk'])
        status = game.get('status', {})
        if status.get('detailedState') == 'Postponed':
            postponed_key = f"MLB_POSTPONED_{game_pk}"
            if postponed_key not in tweeted_recently:
                away_full, home_full = game['teams']['away']['team']['name'], game['teams']['home']['team']['name']
                away_short = get_short_name(away_full, game['teams']['away']['team'].get('teamName'))
                home_short = get_short_name(home_full, game['teams']['home']['team'].get('teamName'))
                reason = status.get('reason', 'unspecified reasons')
                alert_text = f"🚨 POSTPONED: The game between the {away_short} and {home_short} has been postponed due to {reason}.\n\n#{away_short.replace(' ', '')} #{home_short.replace(' ', '')} #MLB"
                
                if DRY_RUN:
                    print(f"\n[SHADOW] 🛑 DRY RUN ACTIVE. Mocking MLB Postponement for {away_short}:")
                    print(f"      -> Text: {alert_text}")
                else:
                    try:
                        mlb_client.create_tweet(text=alert_text)
                        config = LEAGUE_CONFIG.get("mlb")
                        if config and config.get("bsky_client"):
                            bsky_tb = client_utils.TextBuilder()
                            bsky_tb.text(alert_text)
                            config["bsky_client"].send_post(bsky_tb)
                        print(f"✅ Successfully tweeted postponement for {away_short} vs {home_short}!")
                    except Exception as e: print(f"❌ Failed to tweet postponement: {e}")
                    
                log_today.append(postponed_key)
                tweeted_recently.append(postponed_key)
                memory[date_str] = log_today
                new_tweets_sent = True
                # 🛑 ADD THIS HERE:
                if firebase_admin._apps:
                    db.reference('tweet_log').update({date_str: log_today})
            continue
        
        positions = {}
        try:
            box_teams = requests.get(f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live").json().get('liveData', {}).get('boxscore', {}).get('teams', {})
            for pid, p_data in {**box_teams.get('away', {}).get('players', {}), **box_teams.get('home', {}).get('players', {})}.items():
                if p_data.get('position', {}).get('abbreviation'): positions[p_data['person']['id']] = p_data['position']['abbreviation']
                elif p_data.get('allPositions'): positions[p_data['person']['id']] = p_data['allPositions'][0]['abbreviation']
        except: pass

        away_full, home_full = game['teams']['away']['team']['name'], game['teams']['home']['team']['name']
        away_short = get_short_name(away_full, game['teams']['away']['team'].get('teamName'))
        home_short = get_short_name(home_full, game['teams']['home']['team'].get('teamName'))
        away_p_name = game['teams']['away'].get('probablePitcher', {}).get('fullName', 'TBD')
        home_p_name = game['teams']['home'].get('probablePitcher', {}).get('fullName', 'TBD')

        raw_away_odds, raw_home_odds, raw_total = "TBD", "TBD", "TBD"
        try: game_time_ms = datetime.strptime(game['gameDate'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp() * 1000
        except: game_time_ms = 0

        def parse_odds_time(date_str):
            if date_str.endswith('Z'): date_str = date_str[:-1]
            if len(date_str.split(':')) == 2: date_str += ":00"
            try: return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp() * 1000
            except: return 0

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
        away_odds_str, home_odds_str = format_odds(raw_away_odds), format_odds(raw_home_odds)

        for side in ['away', 'home']:
            players_array = game.get('lineups', {}).get(f'{side}Players', [])
            if not players_array or len(players_array) < 9: continue

            current_hash = get_lineup_hash(players_array)
            base_key = f"{game_pk}_{side}"
            full_key = f"{base_key}_{current_hash}"

            team_short_ref = away_short if side == 'away' else home_short
            team_p_ref = f"{away_p_name}" if side == 'away' else f"{home_p_name}"
            team_o_ref = away_odds_str if side == 'away' else home_odds_str
            opp_short_ref = home_short if side == 'away' else away_short

            mlb_alt_parts = [f"Graphical lineup card for the {team_short_ref} against the {opp_short_ref}.", "Batting Order:"]
            for i in range(9): mlb_alt_parts.append(f"{i+1}. {players_array[i].get('fullName', 'Unknown')} ({positions.get(players_array[i].get('id'), '-')}).")
            mlb_alt_parts.append(f"Starting Pitcher: {team_p_ref}.")
            mlb_alt_text = " ".join(mlb_alt_parts)[:1000]

            previously_tweeted_keys = [k for k in tweeted_recently if k.startswith(base_key + "_")]

            if not previously_tweeted_keys:
                if send_mlb_tweet(game_pk, team_short_ref, side, date_str, team_short_ref.replace(" ", ""), team_o_ref, total_string, mlb_alt_text, full_key):
                    log_today.append(full_key)
                    tweeted_recently.append(full_key)
                    new_tweets_sent = True
                    # 🛑 ADD THIS HERE:
                    if firebase_admin._apps:
                        db.reference('tweet_log').update({date_str: log_today})
            elif full_key not in previously_tweeted_keys:
                old_ids = previously_tweeted_keys[0].replace(f"{base_key}_", "").split('-')
                new_ids = current_hash.split('-')
                out_ids = [pid for pid in old_ids if pid not in new_ids]
                in_ids = [pid for pid in new_ids if pid not in old_ids]

                if len(out_ids) == 0 and len(in_ids) == 0: alert_header = f"⚠️ {team_short_ref} LINEUP SHUFFLE: The batting order has changed."
                else:
                    out_names = [next((p.get('fullName', 'Unknown Player') for p in players_array if str(p['id']) == pid), 'Unknown') for pid in out_ids]
                    in_names = [next((p.get('fullName', 'Unknown Player') for p in players_array if str(p['id']) == pid), 'Unknown') for pid in in_ids]
                    alert_header = f"🚨 {team_short_ref} LATE SCRATCH\nOUT: {', '.join(out_names) if out_names else 'None'}\nIN: {', '.join(in_names) if in_names else 'None'}"

                if send_mlb_tweet(game_pk, team_short_ref, side, date_str, team_short_ref.replace(" ", ""), team_o_ref, total_string, mlb_alt_text, full_key, alert_header=alert_header):
                    for k in previously_tweeted_keys:
                        if k in log_today: log_today.remove(k)
                        if k in tweeted_recently: tweeted_recently.remove(k)
                    log_today.append(full_key)
                    tweeted_recently.append(full_key)
                    new_tweets_sent = True

    # ==========================================
    # FUTBOL ENGINE (Lineups & Live Alerts)
    # ==========================================
    FUTBOL_LEAGUES = {
         40:  {"name": "\U0001f3f4\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f CHAMPIONSHIP", "tag": "#Championship", "url_slug": "championship", "x_client": nwsl_client, "v1_client": nwsl_api_v1, "base_url": "https://futbolstartingeleven.com/championship.html"},
    61:  {"name": "🇫🇷 LIGUE 1", "tag": "#Ligue1", "url_slug": "ligue1", "base_url": "https://futbolstartingeleven.com/ligue1.html"}, 
    10:  {"name": "🌎 INTERNATIONAL Friendlies", "tag": "#Friendly", "url_slug": "intl", "base_url": "https://futbolstartingeleven.com/friendlies.html"},
    39:  {"name": "\U0001f3f4\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f PREMIER LEAGUE", "tag": "#EPL", "url_slug": "epl", "x_client": nwsl_client, "v1_client": nwsl_api_v1, "base_url": "https://futbolstartingeleven.com/epl.html"},
        140: {"name": "🇪🇸 LA LIGA", "tag": "#LaLiga", "base_url": "https://futbolstartingeleven.com/laliga.html"},
        135: {"name": "SERIE A 🇮🇹", "tag": "#SerieA", "x_client": seriea_client, "v1_client": seriea_api_v1, "base_url": "https://futbolstartingeleven.com/seriea.html"},
        2:   {"name": "🇪🇺 CHAMPIONS LEAGUE", "tag": "#UCL"},
        45:  {"name": "\U0001f3f4\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f FA CUP", "tag": "#FACup"},
        78:  {"name": "🇩🇪 BUNDESLIGA", "tag": "#Bundesliga", "x_client": bundesliga_client, "v1_client": bundesliga_api_v1, "base_url": "https://futbolstartingeleven.com/bundesliga.html"},
       # 254: {"name": "🇺🇸 NWSL", "tag": "#NWSL", "x_client": nwsl_client, "v1_client": nwsl_api_v1, "base_url": "https://futbolstartingeleven.com/nwsl.html"},
        253: {"name": "🇺🇸 MLS", "tag": "#MLS", "x_client": mls_client, "v1_client": mls_api_v1, "base_url": "https://futbolstartingeleven.com/mls.html"},
        3:   {"name": "🇪🇺 EUROPA LEAGUE", "tag": "#EuropaLeague"},
        13:  {"name": "🌎 COPA LIBERTADORES", "tag": "#Libertadores"},
        16:  {"name": "🏆 CHAMPIONS CUP", "tag": "#ChampionsCup"},
        71:  {"name": "🇧🇷 BRASILEIRÃO", "tag": "#Brasileirao"},
        128: {"name": "🇦🇷 LIGA PROFESIONAL", "tag": "#LigaProfesional"},
        88:  {"name": "🇳🇱 EREDIVISIE", "tag": "#Eredivisie"},
        262: {"name": "🇲🇽 LIGA MX", "tag": "#LigaMX"},
        94:  {"name": "🇵🇹 PRIMEIRA LIGA", "tag": "#PrimeiraLiga"},
        239: {"name": "🇨🇴 PRIMERA A", "tag": "#PrimeraA"},
        188: {"name": "🇦🇺 A-LEAGUE", "tag": "#ALeague"},
        203: {"name": "🇹🇷 SÜPER LIG", "tag": "#SuperLig"},
        144: {"name": "🇧🇪 PRO LEAGUE", "tag": "#ProLeague"},
        179: {"name": "\U0001f3f4\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f PREMIERSHIP", "tag": "#ScottishPremiership"},
        119: {"name": "🇩🇰 SUPERLIGA", "tag": "#Superliga"},
        11:  {"name": "🌎 COPA SUDAMERICANA", "tag": "#Sudamericana #LaGranConquista"},
        5:   {"name": "🇪🇺 UEFA NATIONS LEAGUE", "tag": "#NationsLeague #UNL"},
        531: {"name": "🌎 CONCACAF NATIONS LEAGUE", "tag": "#CNL #Concacaf"},
        307: {"name": "🇸🇦 SAUDI PRO LEAGUE", "tag": "#SaudiProLeague #SPL"}
    }

    INTL_FLAGS = {
        "England": "\U0001f3f4\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f", "Scotland": "\U0001f3f4\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f", "Wales": "\U0001f3f4\U000e0067\U000e0062\U000e0077\U000e006c\U000e0073\U000e007f",
        "Northern Ireland": "🇬🇧", "Argentina": "🇦🇷", "Brazil": "🇧🇷", "France": "🇫🇷", "Germany": "🇩🇪", "Italy": "🇮🇹", "Mexico": "🇲🇽", "Netherlands": "🇳🇱", "Portugal": "🇵🇹", "Spain": "🇪🇸", "USA": "🇺🇸"
    }

    futbol_dates_to_check = [date_str]
    if today_est.hour >= 20: futbol_dates_to_check.append(tomorrow_str)
    if today_est.hour <= 2: futbol_dates_to_check.append(yesterday_str)   

    for target_date_str in futbol_dates_to_check:
        if target_date_str not in memory: memory[target_date_str] = []
        log_target_date = memory[target_date_str]

        try: futbol_data = requests.get(f"https://futbolstartingeleven.com/data/games_{target_date_str}.json?v={today_est.timestamp()}").json()
        except: futbol_data = []

        # --- A. FUTBOL LINEUPS ---
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

            raw_h_name, raw_a_name = match['teams']['home']['name'], match['teams']['away']['name']
            h_name = f"{INTL_FLAGS.get(raw_h_name, '')} {raw_h_name}".strip() if league_id == 10 else raw_h_name
            a_name = f"{INTL_FLAGS.get(raw_a_name, '')} {raw_a_name}".strip() if league_id == 10 else raw_a_name

            h_pos, a_pos = parse_futbol_lineup(home_startXI), parse_futbol_lineup(away_startXI)
            h_form = home_lineup.get('formation', 'TBD')
            a_form = away_lineup.get('formation', 'TBD')
            odds = match.get('odds', {})
            odds_str = f"📊 Live Match Odds\n{h_name}: {odds.get('home', 'TBD')} | Draw: {odds.get('draw', 'TBD')} | {a_name}: {odds.get('away', 'TBD')}\nOver {odds.get('total', '2.5')}: {odds.get('over', 'TBD')} | Under {odds.get('total', '2.5')}: {odds.get('under', 'TBD')}"
            
            h_hash, a_hash = raw_h_name.replace(' ', '').replace('-', '').replace('.', ''), raw_a_name.replace(' ', '').replace('-', '').replace('.', '')
            base_url = league_info.get("base_url", f"https://futbolstartingeleven.com/?league=top&date={target_date_str}")
            
            chosen_title = random.choice([f"🚨 OFFICIAL STARTING XI: {league_info['name']}", f"⚽ {h_name} vs {a_name} starting lineups are out!"])
            h_rank = f"[{match['teams']['home']['rank']}] " if match['teams']['home'].get('rank') else ""
            h_rec = f"({match['teams']['home']['record']})" if match['teams']['home'].get('record') else ""
            a_rank = f"[{match['teams']['away']['rank']}] " if match['teams']['away'].get('rank') else ""
            a_rec = f"({match['teams']['away']['record']})" if match['teams']['away'].get('record') else ""
            
            header = f"{chosen_title}\n{h_rank}{h_name} {h_rec} vs {a_rank}{a_name} {a_rec}".replace("  ", " ").strip()
            link_text = f"📱 Live stats & scores: {base_url}#lineup-{fixture_id}"
            tags_text = f"{league_info['tag']} #{h_hash} #{a_hash}"
            tweet_text = "\n\n".join([header, link_text, odds_str, tags_text])

            bsky_tb = client_utils.TextBuilder()
            bsky_tb.text(header + "\n\n")
            bsky_tb.link(link_text, base_url + f"#lineup-{fixture_id}")
            bsky_tb.text("\n\n" + odds_str + "\n\n" + tags_text)

            futbol_alt_text = f"Graphical tactical lineup card for {h_name} vs {a_name}."

            if team_key in memory.get(date_str, []): continue

            # Apply the 2-attempt safety net to Futbol!
            screenshot_success = False
            for attempt in range(2):
                try:
                    if asyncio.run(take_screenshot(fixture_id, target_date_str)):
                        screenshot_success = True
                        break 
                    time.sleep(5)
                except: time.sleep(5)
                
            if not screenshot_success: continue

            target_client, target_v1_client = league_info.get("x_client") or futbol_client, league_info.get("v1_client") or futbol_api_v1

            if DRY_RUN:
                print(f"\n[SHADOW] 🛑 DRY RUN ACTIVE. Mocking Futbol Lineup for {h_name}:")
                print(f"      -> Text: {tweet_text[:80]}...")
            else:
                try:
                    media = target_v1_client.media_upload("temp_matchup.png")
                    target_v1_client.create_media_metadata(media.media_id, futbol_alt_text)
                    if target_client: target_client.create_tweet(text=tweet_text, media_ids=[media.media_id])
                    
                    target_bsky_client = league_info.get("bsky_client")
                    if target_bsky_client:
                        with open("temp_matchup.jpg", "rb") as f:
                            img_data = f.read()
                        target_bsky_client.send_image(text=bsky_tb, image=img_data, image_alt=futbol_alt_text)
                        print(f"✅ Successfully posted to Bluesky (Native JPEG)!")
                except Exception as e: print(f"❌ Failed to tweet Futbol matchup: {e}")

            if os.path.exists("temp_matchup.png"): os.remove("temp_matchup.png")
            if os.path.exists("temp_matchup.jpg"): os.remove("temp_matchup.jpg")
            
            log_target_date.append(team_key)
            tweeted_recently.append(team_key)
            new_tweets_sent = True
            
            # 🛑 KEEPING FIREBASE SYNC:
            if firebase_admin._apps:
                db.reference('tweet_log').update({target_date_str: log_target_date})
                
            # 🧹 FORCE GARBAGE COLLECTION & LINUX MEMORY FLUSH
            gc.collect()
            try:
                ctypes.CDLL('libc.so.6').malloc_trim(0)
            except Exception:
                pass            

        # --- B. FUTBOL LIVE ALERTS ---
        live_futbol_data = {}
        if target_date_str == date_str:
            try:
                live_snapshot = db.reference('futbol_live_games').get()
                if live_snapshot: live_futbol_data = list(live_snapshot.values())
            except: pass

        alerts_source = live_futbol_data if live_futbol_data else futbol_data

        for match in alerts_source:
            league_id = match.get('league', {}).get('id')
            if league_id not in FUTBOL_LEAGUES: continue
            league_info = FUTBOL_LEAGUES[league_id]
            fixture_id = match.get('fixture', {}).get('id')
            fixture_status = match.get('fixture', {}).get('status', {}).get('short', '')
            events = match.get('events', [])
            if not events: continue

            h_id, a_id = match['teams']['home']['id'], match['teams']['away']['id']
            raw_h_name, raw_a_name = match['teams']['home']['name'], match['teams']['away']['name']
            h_name = f"{INTL_FLAGS.get(raw_h_name, '')} {raw_h_name}".strip() if league_id == 10 else raw_h_name
            a_name = f"{INTL_FLAGS.get(raw_a_name, '')} {raw_a_name}".strip() if league_id == 10 else raw_a_name

            def get_actual_minute(e):
                t_str = str(e.get('time', '0')).replace("'", "").strip()
                if '+' in t_str:
                    parts = t_str.split('+')
                    try: return int(parts[0]) + int(parts[1])
                    except: return int(parts[0]) if parts[0].isdigit() else 90
                return int(t_str) if t_str.isdigit() else 0

            is_shootout = fixture_status in ['P', 'PEN'] or sum(1 for e in events if e.get('type') == 'Goal' and e.get('detail') == 'Penalty' and get_actual_minute(e) >= 90) > 1
            valid_goal_events = [e for e in events if e.get('type') == 'Goal' and e.get('detail') in ['Normal Goal', 'Penalty', 'Own Goal'] and not (e.get('detail') == 'Penalty' and get_actual_minute(e) >= 90 and is_shootout)]
            valid_goal_events.sort(key=get_actual_minute)

            current_home_score, current_away_score = 0, 0
            try: home_odds = float(match.get('odds', {}).get('home') or 0.0)
            except: home_odds = 0.0
            
            try: away_odds = float(match.get('odds', {}).get('away') or 0.0)
            except: away_odds = 0.0

            for event in valid_goal_events: 
                team_id = event.get('team_id')
                if team_id == h_id: current_home_score += 1
                else: current_away_score += 1
                
                event_time = get_actual_minute(event)
                event_key = f"ALERT_{fixture_id}_{team_id}_Goal_{current_home_score if team_id == h_id else current_away_score}"
                if event_key in tweeted_recently: continue

                is_late, is_stoppage, is_equalizer = 75 <= event_time < 90, event_time >= 90, current_home_score == current_away_score
                is_go_ahead = (team_id == h_id and current_home_score - current_away_score == 1) or (team_id == a_id and current_away_score - current_home_score == 1)
                scorer_odds = home_odds if team_id == h_id else away_odds
                is_standard_upset, is_massive_upset = is_go_ahead and (4.00 <= scorer_odds < 7.00), is_go_ahead and (scorer_odds >= 7.00)
                
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
                    match_ended_str = match.get("match_ended_at")
                    is_stale = True
                    if match_ended_str:
                        try:
                            if (datetime.now(timezone.utc) - datetime.fromisoformat(match_ended_str)).total_seconds() / 60 < 20: is_stale = False
                        except: pass
                    if is_stale:
                        log_target_date.append(event_key)
                        tweeted_recently.append(event_key)
                        memory[target_date_str] = log_target_date
                        continue

                scoring_team_name = h_name if team_id == h_id else a_name
                conceding_team_name = a_name if team_id == h_id else h_name
                scorer = event.get('player')
                
                # NEW: If the API hasn't provided the player's name yet, skip and try again next minute
                if not scorer or str(scorer).lower() == "null":
                    continue
                
                # Since we know the scorer exists now, we can simplify the strings
                if event.get('detail') == 'Own Goal':
                    scorer_str = f"{scorer} (Own Goal)"
                else:
                    scorer_str = f"{scorer} ({scoring_team_name})"

                american_odds = f"+{int((scorer_odds - 1) * 100)}"
                h_hash, a_hash = raw_h_name.replace(' ', '').replace('-', '').replace('.', ''), raw_a_name.replace(' ', '').replace('-', '').replace('.', '')
                base_url = league_info.get("base_url", f"https://futbolstartingeleven.com/?league=top&date={target_date_str}")
                link = f"{base_url}#goal-{fixture_id}"

                titles = {"late_equalizer": ["🚨 LATE EQUALIZER!", "🚨 DRAMATIC EQUALIZER!"], "late_go_ahead": ["🚨 LATE GO-AHEAD GOAL!", "🚨 CLUTCH MOMENT!"], "stoppage_equalizer": ["🚨 STOPPAGE TIME EQUALIZER!"], "stoppage_go_ahead": ["🚨 STOPPAGE TIME THRILLER!"], "standard_upset": ["⚠️ UPSET ALERT!"], "massive_upset": ["🚨🔥 MAJOR UPSET ALERT!"], "late_upset": ["🚨⚠️ LATE UPSET BREWING!"], "stoppage_upset": ["🚨🔥 STUNNER IN STOPPAGE TIME!"]}
                
                title = random.choice(titles.get(scenario_key, ["🚨 LATE GOAL!"]))
                tweet_text = f"{title}\n\n⚽ {event_time}' GOAL - {scorer_str}\n{h_name} {current_home_score} - {current_away_score} {a_name}\n\n"
                if "upset" in scenario_key: tweet_text += f"📊 Pre-Match Line: {scoring_team_name} ({american_odds})\n\n"
                if random.randint(1, 100) <= 100: tweet_text += f"Watch the final minutes unfold live:\n⬇️\n{link}\n\n"
                tweet_text += f"{league_info['tag']} #{h_hash} #{a_hash}"
                
                if DRY_RUN:
                    print(f"\n[SHADOW] 🛑 DRY RUN ACTIVE. Mocking Goal Alert for {scoring_team_name}:")
                    print(f"      -> Text: {tweet_text[:80]}...")
                else:
                    try:
                        target_client = league_info.get("x_client") or futbol_client
                        if target_client: target_client.create_tweet(text=tweet_text)
                        print(f"✅ [{league_info['name']}] Successfully tweeted ALERTS for {scoring_team_name}!")
                    except Exception as e: print(f"❌ Failed to tweet ALERT: {e}")

                log_target_date.append(event_key)
                tweeted_recently.append(event_key)
                new_tweets_sent = True
                memory[target_date_str] = log_target_date

    # ==========================================
    # FIREBASE SYNC (END OF LOOP)
    # ==========================================
    if new_tweets_sent and firebase_admin._apps:
        try:
            db.reference('tweet_log').update(memory)
            print("\n💾 In-Memory State Synced to Firebase.")
        except Exception as e:
            print(f"⚠️ Failed to push log to Firebase: {e}")
    
    return 60, memory # Return the target sleep time and the persistent memory

# ==========================================
# 6. THE PERSISTENT RENDER WRAPPER
# ==========================================
if __name__ == "__main__":
    print("🤖 Starting Publisher Bot (Render Persistent Engine)...")
    
    # 1. Fetch initial state
    persisted_memory = fetch_initial_memory()
    
    # 2. SEED FIREBASE: If Firebase is empty but we got GH data, save it now!
    if firebase_admin._apps:
        existing_fb = db.reference('tweet_log').get()
        if not existing_fb and persisted_memory:
            print("🌱 Seeding Firebase with legacy GitHub log...")
            db.reference('tweet_log').set(persisted_memory)
    
    if persisted_memory is None:
        persisted_memory = {}
    
    while True:
        try:
            loop_start_time = time.time()
            
            # Run engines - we now capture the updated memory and the sleep time
            target_sleep_sec, updated_memory = run_engines(persisted_memory)
            persisted_memory = updated_memory
            
            loop_elapsed = time.time() - loop_start_time
            actual_sleep = max(0.0, target_sleep_sec - loop_elapsed)
            
            if actual_sleep > 0:
                print(f"⏳ Loop took {loop_elapsed:.1f}s. Sleeping {actual_sleep:.1f}s...")
                time.sleep(actual_sleep)
                
        except Exception as e:
            print(f"\n❌ Loop crashed: {e}. Restarting loop in 60s...")
            time.sleep(60)
            # CRITICAL: We DO NOT re-fetch memory here. 
            # We keep the persisted_memory we already have in RAM.
