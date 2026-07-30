import os
import json
import requests
import unicodedata
import tweepy
import zoneinfo
from datetime import datetime, timezone, timedelta
import time
import random
import copy
from atproto import Client, client_utils, models
import firebase_admin
from firebase_admin import credentials, db
import asyncio
from playwright.async_api import async_playwright
import gc
import subprocess
import sys
import ctypes
import re

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
    "nba": {"league_name": "NBA 🏀", "bsky_client": setup_bsky_client("nba_account")},
    "futbol": {"league_name": "Futbol ⚽", "bsky_client": setup_bsky_client("futbol_account")}
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
argbracol_client, argbracol_api_v1 = get_dynamic_clients("argbracol_x")

# ==========================================
# 3. PLAYWRIGHT & HELPER FUNCTIONS
# ==========================================
async def take_weather_screenshot(browser):
    print("📸 Generating MLB Daily Weather Graphic...")
    # Using 1080x1080 square viewport to match our compact 3-column grid
    page = await browser.new_page(viewport={'width': 1080, 'height': 1080}) 
    
    bust_cache = int(time.time())
    url = f"https://weathermlb.com/daily_weather_card.html?v={bust_cache}"
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # Target the specific container we created in HTML
        capture_area = page.locator("#capture-area")
        
        # Wait for the grid to actually finish populating from JSON
        await page.locator(".game-card").first.wait_for(state="visible", timeout=30000)
        await asyncio.sleep(2) # Give gradients and fonts a moment to settle
        
        await capture_area.screenshot(path="mlb_weather.png", type="png")
        await capture_area.screenshot(path="mlb_weather.jpg", type="jpeg", quality=75)
        print("✅ Weather Screenshots saved successfully!")
        return True
    except Exception as e:
        print(f"⚠️ Weather Graphic capture failed. Error: {e}")
        return False
    finally:
        await page.close()

async def take_screenshot(browser, fixture_id, target_date):
    print(f"📸 Generating Futbol Graphic for Fixture {fixture_id}...")
    page = await browser.new_page(viewport={'width': 1080, 'height': 1350})
    url = f"https://futbolstartingeleven.com/matchup_card.html?date={target_date}&fixture={fixture_id}"
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.locator(".player-node").first.wait_for(timeout=60000)
        await asyncio.sleep(3) 
        
        capture_area = page.locator("#capture-area")
        await capture_area.screenshot(path="temp_matchup.png", type="png")
        await capture_area.screenshot(path="temp_matchup.jpg", type="jpeg", quality=70)
        print("✅ Futbol Screenshots saved (PNG & JPEG)!")
        return True
    except Exception as e:
        print(f"⚠️ Futbol Graphics failed. Error: {e}")
        return False
    finally:
        await page.close() 

async def take_mlb_screenshot(browser, game_pk, side, target_date):
    print(f"📸 Generating MLB Graphic for {game_pk} ({side})...")
    page = await browser.new_page(viewport={'width': 1080, 'height': 1350})
    
    page.on("console", lambda msg: print(f"   [Browser Console]: {msg.text}"))
    page.on("pageerror", lambda err: print(f"   [Browser JS Error]: {err}"))
    page.on("requestfailed", lambda req: print(f"   [Request Failed]: {req.url}"))
    
    async def intercept_mlb_api(route):
        try:
            res = requests.get(route.request.url, timeout=10)
            await route.fulfill(
                status=res.status_code,
                content_type="application/json",
                body=res.text,
                headers={"Access-Control-Allow-Origin": "*"} 
            )
        except Exception as e:
            print(f"   [Proxy Error]: {e}")
            await route.abort()

    await page.route("**/statsapi.mlb.com/**", intercept_mlb_api)
    
    bust_cache = int(time.time())
    url = f"https://mlbstartingnine.com/mlb_card.html?date={target_date}&gamePk={game_pk}&side={side}&v={bust_cache}"
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.locator("#lineup-container .player-row").first.wait_for(timeout=60000)
        await asyncio.sleep(3)
        
        capture_area = page.locator("#capture-area")
        await capture_area.screenshot(path="mlb_matchup.png", type="png")
        await capture_area.screenshot(path="mlb_matchup.jpg", type="jpeg", quality=70)
        print("✅ MLB Screenshots saved (PNG & JPEG)!")
        return True
    except Exception as e:
        print(f"⚠️ MLB Graphics failed. Error: {e}")
        return False
    finally:
        await page.close()

async def take_nba_screenshot(browser, team_abbr, side, target_date):
    print(f"📸 Generating NBA Graphic for {team_abbr} ({side})...")
    page = await browser.new_page(viewport={'width': 1080, 'height': 1080})
    url = f"https://nbastartingfive.com/nba_card.html?date={target_date}&team={team_abbr}&side={side}"
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.locator(".player-node").first.wait_for(timeout=60000)
        await asyncio.sleep(3) 
        
        capture_area = page.locator("#capture-area")
        await capture_area.screenshot(path="nba_matchup.png", type="png")
        await capture_area.screenshot(path="nba_matchup.jpg", type="jpeg", quality=70)
        print("✅ NBA Screenshots saved (PNG & JPEG)!")
        return True
    except Exception as e:
        print(f"⚠️ NBA Graphics failed. Error: {e}")
        return False
    finally:
        await page.close()

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

def get_team_slug(full_name):
    if full_name == "Athletics": return "athletics"
    return full_name.lower().replace(".", "").replace(" ", "-")

def get_futbol_team_slug(full_name):
    """Generates the exact same URL slug used in the Python site generator"""
    slug = full_name.lower()
    
    # Normalize accents/special characters (e.g., Shkodër -> shkoder)
    slug = unicodedata.normalize('NFKD', slug).encode('ascii', 'ignore').decode('utf-8')
    
    # Strip basic punctuation
    slug = slug.replace(".", "").replace("'", "")
    
    # Replace any remaining spaces or non-alphanumerics (including '/') with a clean hyphen
    slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')
    
    return slug

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
    mem = {}
    if firebase_admin._apps:
        try:
            fb_state = db.reference('tweet_log').get()
            if fb_state and isinstance(fb_state, dict):
                print("🗄️ Fetched persistent tweet log from Firebase.")
                return fb_state
        except Exception as e:
            print(f"⚠️ Firebase memory fetch failed: {e}")
            
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

def log_x_tweet_audit(engine_name, base_key, date_string):
    """Logs successful X (Twitter) posts to Firebase for cost auditing."""
    if not DRY_RUN and firebase_admin._apps:
        try:
            # Sanitize key to prevent Firebase path errors (no ., #, $, [, ])
            safe_key = str(base_key).replace('.', '').replace('#', '').replace('$', '').replace('[', '').replace(']', '').replace('/', '_')
            audit_key = f"{safe_key}_{date_string}"
            
            # Log with the current unix timestamp as the value
            db.reference(f'X_Audit/{engine_name}').update({audit_key: int(time.time())})
        except Exception as e:
            print(f"⚠️ Failed to log X Audit for {engine_name}: {e}")

# ==========================================
# 5. CORE BOT ENGINE (RUNS EVERY LOOP)
# ==========================================
async def run_engines(memory):
    # ----------------------------------------------------
    # BROWSER CONNECTION MANAGER
    # ----------------------------------------------------
    playwright_manager = await async_playwright().start()
    browser = None

    async def get_browser():
        nonlocal browser
        if browser is None:
            print("🌐 Opening Cloud Browser connection for this loop...")
            browserless_url = os.environ.get("BROWSERLESS_URL")
            if browserless_url:
                browser = await playwright_manager.chromium.connect_over_cdp(browserless_url)
            else:
                browser = await playwright_manager.chromium.launch(headless=True, args=['--disable-gpu', '--no-sandbox', '--single-process'])
        return browser

    # ----------------------------------------------------

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

    # 🛡️ Keep 6 days of memory (5 days back, 1 day forward) to prevent timezone ghost tweets
    dates_to_keep = [(today_est + timedelta(days=d)).strftime('%Y-%m-%d') for d in range(-5, 2)]
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

    if True: nba_data = []

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

                if team_date_key in memory.get(date_str, []):
                    continue

                screenshot_success = False
                for attempt in range(2):
                    try:
                        b = await get_browser()
                        if await take_nba_screenshot(b, team, side, date_str):
                            screenshot_success = True
                            break 
                        await asyncio.sleep(5)
                    except: await asyncio.sleep(5)
                        
                if not screenshot_success: continue 

                alt_parts = [f"Graphical lineup card for the {team_name} starting 5 against the {opp_name}."]
                for p in players[:5]: alt_parts.append(f"{p.get('pos', 'Flex')}: {p.get('name', 'Unknown')}.")
                nba_alt_text = " ".join(alt_parts)[:1000]

                if DRY_RUN:
                    print(f"\n[SHADOW] 🛑 DRY RUN ACTIVE. Mocking NBA Tweet for {team_name}:")
                    upload_success = True 
                else:
                    twitter_success = False
                    bsky_success = False
                    
                    for attempt in range(2):
                        try:
                            if attempt == 1: await asyncio.sleep(3) 
                            media = nba_api_v1.media_upload("nba_matchup.png")
                            nba_api_v1.create_media_metadata(media.media_id, nba_alt_text)
                            nba_client.create_tweet(text=tweet_text, media_ids=[media.media_id])
                            
                            log_x_tweet_audit("NBA", team_date_key, date_str)
                            
                            twitter_success = True
                            break 
                        except Exception as e: pass
                            
                    config = LEAGUE_CONFIG.get("nba")
                    if config and config.get("bsky_client"):
                        for attempt in range(2):
                            try:
                                if attempt == 1: await asyncio.sleep(3)
                                with open("nba_matchup.jpg", "rb") as f:
                                    img_data = f.read()
                                config["bsky_client"].send_image(text=bsky_tb, image=img_data, image_alt=nba_alt_text)
                                bsky_success = True
                                break 
                            except Exception as e: pass

                    upload_success = twitter_success or bsky_success

                if os.path.exists("nba_matchup.png"): os.remove("nba_matchup.png")
                if os.path.exists("nba_matchup.jpg"): os.remove("nba_matchup.jpg")
                
                if upload_success:
                    log_today.append(team_date_key)
                    tweeted_recently.append(team_date_key)
                    memory[date_str] = log_today
                    new_tweets_sent = True
                    if firebase_admin._apps:
                        db.reference('tweet_log').update({date_str: log_today})
                    
                gc.collect()
                try: ctypes.CDLL('libc.so.6').malloc_trim(0)
                except Exception: pass

    # ==========================================
    # MLB ENGINE
    # ==========================================
    # ==========================================
    # DAILY MLB WEATHER REPORT (Fires after 10 AM EST with Retries)
    # ==========================================
    weather_key = f"WEATHER_REPORT_{date_str}"
    
    if weather_key not in memory.get(date_str, []) and today_est.hour >= 10:
    #if weather_key not in memory.get(date_str, []) and today_est.hour >= 10 and False:   
        weather_success = False
        for attempt in range(2):
            try:
                b = await get_browser()
                if await take_weather_screenshot(b):
                    weather_success = True
                    break
                await asyncio.sleep(5)
            except Exception as e:
                print(f"⚠️ Weather screenshot attempt {attempt+1} failed: {e}")
                await asyncio.sleep(5)
            
        if weather_success:
            weather_text = f"🌤️ {game_date_short} MLB Daily Weather Report & Hitting Conditions\n\nFull interactive radar & hourly forecasts:\nhttps://weathermlb.com\n\nTrack stadium wind speeds, rain delay risks, and live roof statuses for today's slate.\n\n#MLB #FantasyBaseball #SportsBetting #MLBWeather"
            
            if DRY_RUN:
                print(f"\n[SHADOW] 🛑 Mocking Weather Tweet for {date_str}:\n{weather_text}")
                upload_success = True
            else:
                twitter_success = False
                bsky_success = False
                
                # --- X (Twitter) Upload with 2 Attempts ---
                for attempt in range(2):
                    try:
                        if attempt == 1: await asyncio.sleep(3)
                        media = mlb_api_v1.media_upload("mlb_weather.png")
                        mlb_api_v1.create_media_metadata(media.media_id, "MLB Daily Weather Report & Stadium Wind Speeds")
                        mlb_client.create_tweet(text=weather_text, media_ids=[media.media_id])
                        
                        log_x_tweet_audit("MLB", weather_key, date_str)
                        
                        twitter_success = True
                        print("✅ Successfully tweeted MLB Weather Report to X!")
                        break
                    except Exception as e:
                        print(f"⚠️ X weather upload attempt {attempt+1} failed: {e}")
                        
                # --- Bluesky Upload with 2 Attempts ---
                config = LEAGUE_CONFIG.get("mlb")
                if config and config.get("bsky_client"):
                    for attempt in range(2):
                        try:
                            if attempt == 1: await asyncio.sleep(3)
                            with open("mlb_weather.jpg", "rb") as f:
                                img_data = f.read()
                            bsky_tb = client_utils.TextBuilder()
                            bsky_tb.text(f"🌤️ {game_date_short} MLB Daily Weather Report & Hitting Conditions\n\nTrack stadium wind speeds, rain delay risks, and live roof statuses for today's slate.\n\nFull interactive radar & hourly forecasts:\n")
                            bsky_tb.link("https://weathermlb.com", "https://weathermlb.com")
                            bsky_tb.text("\n\n#MLB #FantasyBaseball #SportsBetting #MLBWeather")
                            
                            config["bsky_client"].send_image(text=bsky_tb, image=img_data, image_alt="MLB Daily Weather Report & Stadium Wind Speeds")
                            bsky_success = True
                            print("✅ Successfully posted MLB Weather Report to Bluesky!")
                            break
                        except Exception as e:
                            print(f"⚠️ Bluesky weather upload attempt {attempt+1} failed: {e}")

                upload_success = twitter_success or bsky_success

            # Clean up images & log to persistent memory
            if os.path.exists("mlb_weather.png"): os.remove("mlb_weather.png")
            if os.path.exists("mlb_weather.jpg"): os.remove("mlb_weather.jpg")
            
            if upload_success:
                log_today.append(weather_key)
                tweeted_recently.append(weather_key)
                new_tweets_sent = True
                if firebase_admin._apps:
                    try: db.reference('tweet_log').update({date_str: log_today})
                    except: pass
    try:
        schedule_data = requests.get(MLB_API_URL).json()
        games = schedule_data['dates'][0]['games'] if schedule_data.get('dates') else []
    except:
        games = []

    try: odds_data = requests.get(MLB_ODDS_URL).json().get('odds', [])
    except: odds_data = []

    async def send_mlb_tweet(game_pk, team_short, full_team_name, side, date_string, team_hash, team_odds, total_string, alt_text, memory_key, alert_header=None):
        if memory_key in memory.get(date_str, []): return False
        
        # 1. URL Setup for Bluesky
        team_slug = get_team_slug(full_team_name)
        team_url = f"https://mlbstartingnine.com/lineups/{team_slug}/"
        main_link = f"https://mlbstartingnine.com/#game-{game_pk}"

        # 2. BUILD X (TWITTER) TEXT - Link-Free (No URLs, Plain Site Name)
        cta_suffix = "Provided by mlbstartingnine (see profile for link)"
        
        if alert_header:
            tweet_text = f"{alert_header}\n{cta_suffix}\n\n"
        else:
            tweet_text = f"{game_date_short} ⚾ {team_short} Lineup is Out!\n{cta_suffix}\n\n"
            
        if team_odds != "TBD": 
            tweet_text += f"📊 Live Line: {team_short} {team_odds}{total_string}\n\n"
            
        tweet_text += f"#{team_hash} #{team_hash}Lineup #MLB"
        
        # 3. BUILD BLUESKY TEXT - Includes Direct Link
        bsky_tb = client_utils.TextBuilder()
        
        if alert_header:
            bsky_tb.text(f"{alert_header}\n\nLive matchups & stats provided by:\n")
        else:
            bsky_tb.text(f"{game_date_short} ⚾ {team_short} Lineup is Out provided by:\n")
            
        bsky_tb.link(main_link, main_link)
        bsky_tb.text("\n\n")
        
        if team_odds != "TBD": 
            bsky_tb.text(f"📊 Live Line: {team_short} {team_odds}{total_string}\n\n")
            
        bsky_tb.text(f"#{team_hash} #{team_hash}Lineup #MLB")

        # 4. GENERATE SCREENSHOT
        screenshot_success = False
        for attempt in range(2):
            try:
                b = await get_browser()
                if await take_mlb_screenshot(b, game_pk, side, date_string):
                    screenshot_success = True
                    break 
                await asyncio.sleep(5)
            except: 
                await asyncio.sleep(5)
                
        if not screenshot_success: return False

        if DRY_RUN:
            print(f"\n[SHADOW] 🛑 DRY RUN ACTIVE. Mocking MLB Tweet for {team_short}:\n{tweet_text}")
            if os.path.exists("mlb_matchup.png"): os.remove("mlb_matchup.png")
            return True
        else:
            twitter_success = False
            bsky_success = False
            
            # --- X (TWITTER) UPLOAD (Single Tweet with Image, No Link, No Reply) ---
            for attempt in range(2):
                try:
                    if attempt == 1: await asyncio.sleep(3) 
                    media = mlb_api_v1.media_upload("mlb_matchup.png")
                    mlb_api_v1.create_media_metadata(media.media_id, alt_text)
                    
                    # Post single tweet with attached image
                    mlb_client.create_tweet(text=tweet_text, media_ids=[media.media_id])
                    log_x_tweet_audit("MLB", memory_key, date_string)
                    
                    twitter_success = True
                    break 
                except Exception as e:
                    print(f"⚠️ Failed to post MLB tweet to X: {e}")
                
            # --- BLUESKY UPLOAD (Main Image Post + Threaded Reply) ---
            config = LEAGUE_CONFIG.get("mlb")
            if config and config.get("bsky_client"):
                for attempt in range(2):
                    try:
                        if attempt == 1: await asyncio.sleep(3) 
                        with open("mlb_matchup.jpg", "rb") as f:
                            img_data = f.read()
                        
                        # 1. Main Post
                        post_response = config["bsky_client"].send_image(text=bsky_tb, image=img_data, image_alt=alt_text)
                        
                        # 2. Threaded Reply
                        reply_tb = client_utils.TextBuilder()
                        reply_tb.text(f"View the {full_team_name} daily starting lineups at our team lineup page:\n")
                        reply_tb.link(team_url, team_url)
                        
                        parent_ref = models.create_strong_ref(post_response)
                        reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=parent_ref)
                        config["bsky_client"].send_post(reply_tb, reply_to=reply_ref)
                        
                        bsky_success = True
                        break 
                    except Exception as e:
                        print(f"⚠️ Failed to post MLB to Bluesky: {e}")

            upload_success = twitter_success or bsky_success
            
            if os.path.exists("mlb_matchup.png"): os.remove("mlb_matchup.png")
            if os.path.exists("mlb_matchup.jpg"): os.remove("mlb_matchup.jpg")
            
            gc.collect()
            try: ctypes.CDLL('libc.so.6').malloc_trim(0)
            except Exception: pass
                
            return upload_success

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
                    upload_success = True 
                else:
                    twitter_success = False
                    bsky_success = False
                    
                    for attempt in range(2):
                        try:
                            if attempt == 1: await asyncio.sleep(3)
                            mlb_client.create_tweet(text=alert_text)
                            
                            log_x_tweet_audit("MLB", postponed_key, date_str)
                            
                            twitter_success = True
                            break
                        except Exception as e: pass

                    config = LEAGUE_CONFIG.get("mlb")
                    if config and config.get("bsky_client"):
                        for attempt in range(2):
                            try:
                                if attempt == 1: await asyncio.sleep(3)
                                bsky_tb = client_utils.TextBuilder()
                                bsky_tb.text(alert_text)
                                config["bsky_client"].send_post(bsky_tb)
                                bsky_success = True
                                break
                            except Exception as e: pass
                                
                    upload_success = twitter_success or bsky_success
                    
                if upload_success:
                    log_today.append(postponed_key)
                    tweeted_recently.append(postponed_key)
                    memory[date_str] = log_today
                    new_tweets_sent = True
                    if firebase_admin._apps:
                        db.reference('tweet_log').update({date_str: log_today})
            continue
        
        positions = {}
        player_names_map = {} 
        try:
            box_teams = requests.get(f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live").json().get('liveData', {}).get('boxscore', {}).get('teams', {})
            for pid, p_data in {**box_teams.get('away', {}).get('players', {}), **box_teams.get('home', {}).get('players', {})}.items():
                person_id = str(p_data['person']['id'])
                player_names_map[person_id] = p_data['person']['fullName'] 
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
            team_full_ref = away_full if side == 'away' else home_full
            team_p_ref = f"{away_p_name}" if side == 'away' else f"{home_p_name}"
            team_o_ref = away_odds_str if side == 'away' else home_odds_str
            opp_short_ref = home_short if side == 'away' else away_short

            mlb_alt_parts = [f"Graphical lineup card for the {team_short_ref} against the {opp_short_ref}.", "Batting Order:"]
            for i in range(9): mlb_alt_parts.append(f"{i+1}. {players_array[i].get('fullName', 'Unknown')} ({positions.get(players_array[i].get('id'), '-')}).")
            mlb_alt_parts.append(f"Starting Pitcher: {team_p_ref}.")
            mlb_alt_text = " ".join(mlb_alt_parts)[:1000]

            previously_tweeted_keys = [k for k in tweeted_recently if k and isinstance(k, str) and k.startswith(base_key + "_")]

            if not previously_tweeted_keys:
                if await send_mlb_tweet(game_pk, team_short_ref, team_full_ref, side, date_str, team_short_ref.replace(" ", ""), team_o_ref, total_string, mlb_alt_text, full_key):
                    log_today.append(full_key)
                    tweeted_recently.append(full_key)
                    new_tweets_sent = True
                    if firebase_admin._apps:
                        db.reference('tweet_log').update({date_str: log_today})
            elif full_key not in previously_tweeted_keys:
                old_ids = previously_tweeted_keys[0].replace(f"{base_key}_", "").split('-')
                new_ids = current_hash.split('-')
                out_ids = [pid for pid in old_ids if pid not in new_ids]
                in_ids = [pid for pid in new_ids if pid not in old_ids]

                if len(out_ids) == 0 and len(in_ids) == 0: alert_header = f"⚠️ {team_short_ref} LINEUP SHUFFLE: The batting order has changed."
                else:
                    out_names = [player_names_map.get(str(pid), 'Unknown') for pid in out_ids]
                    in_names = [next((p.get('fullName', 'Unknown Player') for p in players_array if str(p['id']) == pid), 'Unknown') for pid in in_ids]
                    alert_header = f"🚨 {team_short_ref} LATE SCRATCH\nOUT: {', '.join(out_names) if out_names else 'None'}\nIN: {', '.join(in_names) if in_names else 'None'}"

                if await send_mlb_tweet(game_pk, team_short_ref, team_full_ref, side, date_str, team_short_ref.replace(" ", ""), team_o_ref, total_string, mlb_alt_text, full_key, alert_header=alert_header):
                    for k in previously_tweeted_keys:
                        if k in log_today: log_today.remove(k)
                        if k in tweeted_recently: tweeted_recently.remove(k)
                    log_today.append(full_key)
                    tweeted_recently.append(full_key)
                    new_tweets_sent = True

   # ==========================================
    # FUTBOL ENGINE (Lineups Only)
    # ==========================================
    futbol_tweets_this_loop = 0 # Track tweets to prevent X.com rate limits

    try:
        daily_lineups_url = f"https://futbolstartingeleven.com/data/daily_lineups.json?v={today_est.timestamp()}"
        daily_lineups = requests.get(daily_lineups_url, timeout=10).json()
    except Exception as e:
        print(f"⚠️ Could not fetch daily_lineups.json: {e}")
        daily_lineups = {}

    EMOJIS = ["🚨", "⚽", "📋", "⚔️", "🏟️", "🔥", "📢", "✅", "🔒", "📝"]

    for entry_key, lineup_data in daily_lineups.items():
        # Memory Check: Skip if this specific team key was already tweeted today
        if entry_key in tweeted_recently or entry_key in memory.get(date_str, []):
            continue

        team_name = lineup_data.get('team_name', '')
        opponent_name = lineup_data.get('opponent_name', '')
        league_name = lineup_data.get('league_name', '')
        league_hashtag = lineup_data.get('league_hashtag', '')
        lineup_url = lineup_data.get('lineup_url', '')
        formation = lineup_data.get('formation', '')
        starting_xi = lineup_data.get('starting_xi', [])

        if not team_name or not starting_xi:
            continue

        # Extract player short names grouped by category (G, D, M, F)
        gk_players = [p.get('short_name', p.get('name')) for p in starting_xi if p.get('category') == 'G']
        def_players = [p.get('short_name', p.get('name')) for p in starting_xi if p.get('category') == 'D']
        mid_players = [p.get('short_name', p.get('name')) for p in starting_xi if p.get('category') == 'M']
        fwd_players = [p.get('short_name', p.get('name')) for p in starting_xi if p.get('category') == 'F']

        # Assemble the formation and vertical category lines
        lineup_lines = []
        if formation:
            lineup_lines.append(f"Formation: {formation}")

        if gk_players:
            lineup_lines.append(f"🧤 GK: {', '.join(gk_players)}")
        if def_players:
            lineup_lines.append(f"🛡️ DEF: {', '.join(def_players)}")
        if mid_players:
            lineup_lines.append(f"⚙️ MID: {', '.join(mid_players)}")
        if fwd_players:
            lineup_lines.append(f"🎯 FWD: {', '.join(fwd_players)}")

        players_block = "\n".join(lineup_lines)

        # Clean team and opponent names into clean hashtags
        team_hash = team_name.replace(' ', '').replace('-', '').replace('.', '')
        opponent_hash = opponent_name.replace(' ', '').replace('-', '').replace('.', '')

        e = random.choice(EMOJIS)

        # --- Link-Free X (Twitter) Text ---/
        tweet_text = (
            f"{e} The STARTING XI for {team_name} vs {opponent_name} in {league_name} action has been released.\n"
            f"Follow the action at futbolstartingeleven(link in profile)\n\n"
            f"{players_block}\n\n"
            f"{league_hashtag} #{team_hash} #{opponent_hash}"
        )

        # --- Bluesky Rich Text (CTA & Raw URL near Top, <300 Character Guard) ---
        bsky_tb = client_utils.TextBuilder()
        
        bsky_top = f"{e} {team_name} XI vs {opponent_name}\nFollow live: "
        bsky_hashtags = f"\n\n{league_hashtag} #{team_hash} #{opponent_hash}"
        
        total_chars = len(bsky_top) + len(lineup_url) + len(players_block) + len(bsky_hashtags) + 2
        
        # Auto-trim optional elements if needed
        if total_chars > 290:
            bsky_top = f"{e} {team_name} XI vs {opponent_name}\n"  # Shorten CTA line if tight
            bsky_hashtags = f"\n\n#{team_hash}"
            total_chars = len(bsky_top) + len(lineup_url) + len(players_block) + len(bsky_hashtags) + 2
            
        if total_chars > 290:
            bsky_hashtags = ""  # Omit hashtags completely if still tight
            
        bsky_tb.text(bsky_top)
        bsky_tb.link(lineup_url, lineup_url)  # Raw URL displayed right at the top
        bsky_tb.text(f"\n\n{players_block}{bsky_hashtags}")

        upload_success = False

        if DRY_RUN:
            upload_success = True
            print(f"\n[SHADOW] 🛑 Mocking Futbol Lineup Tweet for {team_name}:\n{tweet_text}")
        else:
            twitter_success = False
            bsky_success = False

            # --- Post to X ---
            try:
                if futbol_client:
                    futbol_client.create_tweet(text=tweet_text)
                    log_x_tweet_audit("FUTBOL", entry_key, date_str)
                    twitter_success = True
            except Exception as err:
                print(f"⚠️ Failed to post Futbol lineup to X for {entry_key}: {err}")

            # --- Post to Bluesky ---
            config = LEAGUE_CONFIG.get("futbol")
            bsky_client_inst = config.get("bsky_client") if config else setup_bsky_client("futbol_account")
            if bsky_client_inst:
                try:
                    bsky_client_inst.send_post(bsky_tb)
                    bsky_success = True
                except Exception as err:
                    print(f"⚠️ Failed to post Futbol lineup to Bluesky for {entry_key}: {err}")

            upload_success = twitter_success or bsky_success

        if upload_success:
            log_today.append(entry_key)
            tweeted_recently.append(entry_key)
            new_tweets_sent = True
            memory[date_str] = log_today

            if firebase_admin._apps:
                try:
                    db.reference('tweet_log').update({date_str: log_today})
                except Exception as e:
                    print(f"⚠️ Failed to update Firebase log: {e}")

            futbol_tweets_this_loop += 1
            if futbol_tweets_this_loop % 3 == 0:
                print("⏳ Throttling API: Sent 3 tweets, resting for 5 seconds...")
                await asyncio.sleep(5)
            else:
                await asyncio.sleep(1.5)

    # ==========================================
    # FUTBOL GOALS ENGINE
    # ==========================================
    try:
        daily_goals_url = f"https://futbolstartingeleven.com/data/daily_goals.json?v={today_est.timestamp()}"
        daily_goals = requests.get(daily_goals_url, timeout=10).json()
    except Exception as e:
        print(f"⚠️ Could not fetch daily_goals.json: {e}")
        daily_goals = {}

    MAX_GOAL_AGE_SECONDS = 300  # Skip goals older than 5 minutes

    PHRASES = {
        "standard_goal": {
            "titles": [
                "⚽ BACK OF THE NET!", "🎯 CLINICAL FINISH!", "💥 WHAT A STRIKE!", 
                "🥅 BEAUTIFUL GOAL!", "⚡ FANTASTIC FINISH!", "✨ MAGIC MOMENT!", "🥶 ICE COLD!", 
                "☄️ BRILLIANT HIT!", "👏 TOP TIER PLAY!", "🚀 RIFLED HOME!"
            ],
            "blurbs": [
                "A moment of pure quality! {player_name} finds the back of the net for {scoring_team_name} against {conceding_team_name}.",
                "Clinical from {player_name}! {scoring_team_name} capitalizes on the opportunity with a fantastic finish.",
                "A brilliant piece of play! {player_name} delivers a beautiful strike to punish {conceding_team_name}.",
                "No mistake from {player_name}! {scoring_team_name} adds another highlight to this clash against {conceding_team_name}.",
                "{scoring_team_name} strikes! A fantastic effort from {player_name} leaves the {conceding_team_name} defense with no answers.",
                "Sublime finish! {player_name} strikes with precision, giving the {scoring_team_name} fans exactly what they wanted to see.",
                "{player_name} makes no mistake! A beautifully worked sequence ends with {scoring_team_name} celebrating.",
                "A fantastic strike from {player_name} keeps {scoring_team_name} rolling in this battle against {conceding_team_name}.",
                "The fans erupt as {player_name} fires a sensational goal for {scoring_team_name} against {conceding_team_name}.",
                "Right on target! {player_name} delivers the goods for {scoring_team_name}, leaving {conceding_team_name} frustrated."
            ],
            "ctas": ["Track the tactical shifts and live pitch data here:", "Follow the momentum, live scores, and player ratings here:", "Dive into the full match center and live lineups:"]
        },
        "hat_trick": {
            "titles": [
                "🎩✨ HAT-TRICK HERO!", "⚽⚽⚽ MATCH BALL SECURED!", "🌟 A PERFECT PERFORMANCE!", 
                "🤯 FLAWLESS!", "👑 MAGNIFICENT THREE!", "🪄 PURE MAGIC!", "🔥 OUT OF THIS WORLD!", 
                "🐐 MASTERCLASS!", "🏆 THREE OF THE BEST!", "💯 TRIPLE THREAT!"
            ],
            "blurbs": [
                "Absolute brilliance! {player_name} bags a sensational hat-trick for {scoring_team_name} to tear {conceding_team_name} apart!",
                "Take a bow, {player_name}! An unforgettable hat-trick secures the match ball and tears {conceding_team_name} apart.",
                "Pure perfection! {player_name} hits the magical milestone with a stunning third goal for {scoring_team_name}.",
                "{conceding_team_name} simply has no answers! {player_name} completes a stunning hat-trick for {scoring_team_name}.",
                "Three goals, one incredible performance! {player_name} achieves a glorious hat-trick for {scoring_team_name}.",
                "{conceding_team_name} has been completely outclassed by {player_name}! A stunning hat-trick for the {scoring_team_name} talisman.",
                "The hat-trick is complete! {player_name} is having a game to remember for {scoring_team_name} against a helpless {conceding_team_name}.",
                "A trio of brilliant strikes! {player_name} writes their name in the headlines today for {scoring_team_name}.",
                "Simply untamable! {player_name} bags goal number three to cap off an unbelievable individual display for {scoring_team_name}.",
                "Give them the match ball! {player_name} clinches a spectacular hat-trick to put {scoring_team_name} out of sight against {conceding_team_name}."
            ],
            "ctas": ["Track the live match stats and pitch data here:", "Can they add a fourth? Follow the live action:", "See the full match center and player ratings here:"]
        },
        "brace": {
            "titles": [
                "✌️ DOUBLE TROUBLE!", "🔥⚽ BRACE ALERT!", "👀 HUNTING THE MATCH BALL!", 
                "☄️ ON FIRE!", "😤 UNSTOPPABLE TODAY!", "🎯 TWO GOOD!", "💥 DOUBLE STRIKE!", 
                "🎭 SEEING DOUBLE!", "🌟 STAR PERFORMANCE!", "💣 BACK FOR MORE!"
            ],
            "blurbs": [
                "{player_name} is putting on an absolute clinic! That is a brilliant brace for the {scoring_team_name} star.",
                "Hunting for the match ball! {player_name} grabs a second goal, leaving the {conceding_team_name} defense searching for answers.",
                "You simply cannot give {player_name} that kind of space! A stunning second goal puts {scoring_team_name} firmly in the driver's seat.",
                "Twice as nice for {scoring_team_name}! {player_name} hits the double to keep the pressure heavily on {conceding_team_name}.",
                "Another one! {player_name} gets their second of the match to extend {scoring_team_name}'s advantage over {conceding_team_name}.",
                "Two goals to their name! {player_name} is having a stellar game for {scoring_team_name}.",
                "A beautiful brace! {player_name} strikes again, and {conceding_team_name} has no answer for the {scoring_team_name} attack.",
                "They just cannot be stopped! {player_name} adds a second goal for {scoring_team_name} against a struggling {conceding_team_name} defense.",
                "The double is complete! {player_name} shines brightest today, giving {scoring_team_name} the edge over {conceding_team_name}.",
                "{scoring_team_name} relies on their star! {player_name} scores twice to put {conceding_team_name} firmly on the back foot."
            ],
            "ctas": ["Will we see a hat-trick? Follow live:", "Track the live match center and stats here:", "See the live pitch data and scores here:"]
        },
        "lightning_start": {
            "titles": [
                "⚡ FAST OUT OF THE BLOCKS!", "🏃💨 CAUGHT SLEEPING!", "⏰ DREAM START!", 
                "🧨 EARLY FIREWORKS!", "🌪️ BLITZ!", "🚀 ROCKET START!", "⏱️ INSTANT IMPACT!", 
                "🤯 BLINK AND YOU'LL MISS IT!", "💥 EXPLOSIVE OPENING!", "🔥 RED HOT START!"
            ],
            "blurbs": [
                "What an opening! {scoring_team_name} lands a massive early punch, catching {conceding_team_name} completely cold.",
                "The fans have barely taken their seats! A dream start for {scoring_team_name} as {player_name} finds the net immediately.",
                "No time wasted! {player_name} fires {scoring_team_name} ahead with incredible urgency.",
                "Explosive! {scoring_team_name} tears down the pitch to strike in the blink of an eye.",
                "An immediate breakthrough! {scoring_team_name} stuns {conceding_team_name} before they can even settle into the match.",
                "Incredible urgency from {scoring_team_name}! {player_name} strikes early to leave {conceding_team_name} shellshocked.",
                "A nightmare start for {conceding_team_name}! {scoring_team_name} attacks successfully just moments after the opening whistle.",
                "Fast, clinical, and deadly! {scoring_team_name} takes a lightning-quick advantage over {conceding_team_name}.",
                "The perfect opening script for {scoring_team_name}! {player_name} strikes inside the opening minutes against {conceding_team_name}.",
                "{conceding_team_name} pays the price for a slow start! {scoring_team_name} capitalizes immediately."
            ],
            "ctas": ["Follow this fast-paced clash live here:", "Track the live match center and pitch data:", "Don't miss a minute. See live scores and odds here:"]
        },
        "tight_clash_goal": {
            "titles": [
                "⚔️ THE TIE TIGHTENS!", "⚖️ GAME ON!", "🥊 BACK AND FORTH WE GO!", 
                "🔥 CRUCIAL STRIKE!", "📈 MOMENTUM SWING!", "🎯 VITAL GOAL!", 
                "💥 BREAKING THE TENSION!", "🥵 HEATING UP!", "🎢 ROLLERCOASTER MATCH!", "🛡️ HARD-FOUGHT GOAL!"
            ],
            "blurbs": [
                "A vital goal from {scoring_team_name}! This clash with {conceding_team_name} is turning into an absolute thriller.",
                "{scoring_team_name} strikes to keep the pressure on {conceding_team_name}! Nothing separating these sides as the battle continues.",
                "We have a massive fight on our hands! {scoring_team_name} finds the back of the net in a tightly contested clash with {conceding_team_name}.",
                "Momentum swing! {scoring_team_name} delivers a crucial blow against {conceding_team_name} as the game remains wide open.",
                "A massive turning point! {scoring_team_name} strikes to alter the complexion of this tight match against {conceding_team_name}.",
                "In a game of fine margins, {scoring_team_name} finds the breakthrough against {conceding_team_name}!",
                "The tension breaks! {player_name} delivers a crucial goal for {scoring_team_name} in this closely fought battle.",
                "End-to-end action! {scoring_team_name} takes their chance, pulling ahead of {conceding_team_name}.",
                "Neither side is backing down! {scoring_team_name} lands a heavy blow against {conceding_team_name} in this fierce contest.",
                "A pivotal moment in the match! {scoring_team_name} gets the upper hand over {conceding_team_name} with a fantastic goal."
            ],
            "ctas": ["Track the live scores and match momentum here:", "Follow the tactical battle and live pitch data:", "See live stats, lineups, and odds here:"]
        },
        "late_equalizer": {
            "titles": [
                "⏱️ LATE EQUALIZER!", "😱 DRAMATIC EQUALIZER!", "⏳ TIED UP LATE!", 
                "🤯 CLOSING STAGES CHAOS!", "⚖️ ALL SQUARE LATE!", "🧨 LATE LIFELINE!", 
                "😤 NEVER GIVE UP!", "🔄 RESETTING THE CLOCK!", "🛡️ SAVED!", "⏰ DOWN TO THE WIRE!"
            ],
            "blurbs": [
                "A massive goal from {scoring_team_name} to level the score, leaving {conceding_team_name} scrambling as time winds down!",
                "{scoring_team_name} claws their way back to tie the match, ripping the momentum right out of {conceding_team_name}'s hands.",
                "{scoring_team_name} refuses to go away quietly! We are all square as {conceding_team_name} tries to regain control.",
                "A crucial tying goal for {scoring_team_name} stuns {conceding_team_name} and sets up a frantic finish!",
                "They never stopped fighting! {scoring_team_name} gets their reward with a late equalizer against {conceding_team_name}.",
                "{conceding_team_name} thought they had it won, but {scoring_team_name} snatches a late equalizer to balance the scales!",
                "The late pressure pays off! {scoring_team_name} draws level, completely changing the dynamic against {conceding_team_name}.",
                "A brilliantly timed strike from {scoring_team_name} ensures this match is dead even heading into the final moments.",
                "Heartbreak for the {conceding_team_name} defense as {scoring_team_name} powers through to tie it up late.",
                "We have a brand new ballgame! {scoring_team_name} equalizes late to put the pressure right back on {conceding_team_name}."
            ],
            "ctas": ["Track the final push for a game-winner here:", "See the live momentum shift and pitch data:", "Can someone find a late winner? Follow live:"]
        },
        "late_go_ahead": {
            "titles": [
                "📈 LATE GO-AHEAD GOAL!", "🔓 THE DEADLOCK IS BROKEN!", "🥶 CLUTCH MOMENT!", 
                "🔨 HUGE LATE GOAL!", "⏳ TENSION IN THE FINAL 15!", "🗡️ LATE DAGGER!", 
                "🚀 TAKING CHARGE LATE!", "🎯 PRECISION WHEN IT MATTERS!", "🏁 RACING TO THE FINISH!", "💥 LATE HEARTBREAK AVERTED!"
            ],
            "blurbs": [
                "A game-changing strike from {scoring_team_name} forces {conceding_team_name} to chase the game late!",
                "{scoring_team_name} snatches the advantage right when they needed it, leaving {conceding_team_name} stunned.",
                "A massive momentum swing puts {scoring_team_name} in front, and now {conceding_team_name} is running out of time!",
                "The defense finally cracks! {scoring_team_name} takes a crucial late lead over {conceding_team_name}.",
                "Cometh the hour, cometh the player! {player_name} scores late to give {scoring_team_name} a priceless lead.",
                "{scoring_team_name} steps up when the pressure is highest, pushing past {conceding_team_name} in the closing stages.",
                "A devastating blow! {scoring_team_name} breaks through the {conceding_team_name} lines to claim a vital late lead.",
                "The stadium erupts! {scoring_team_name} finds the magic touch late on to put {conceding_team_name} against the ropes.",
                "Brilliant composure from {scoring_team_name} to secure a go-ahead goal while the clock ticks down on {conceding_team_name}.",
                "They kept knocking, and the door finally opened! {scoring_team_name} takes a huge late advantage over {conceding_team_name}."
            ],
            "ctas": ["Can they hold on? Follow the final minutes live:", "Track the closing stages and live stats here:"]
        },
        "stoppage_equalizer": {
            "titles": [
                "🤯 SAVED AT THE DEATH!", "🆘 LAST MINUTE LIFELINE!", "⏱️ 90TH MINUTE MADNESS!", 
                "🗣️ SCENES IN STOPPAGE TIME!", "😱 MIRACLE AT THE DEATH!", "🤯 UNBELIEVABLE SCENES!", 
                "🎭 THE DRAMA!", "⏰ BEATING THE CLOCK!", "🚑 RESCUED!", "😵 CHAOS!"
            ],
            "blurbs": [
                "Absolute scenes! A miraculous stoppage-time equalizer for {scoring_team_name} throws {conceding_team_name} into chaos!",
                "{scoring_team_name} climbs out of the grave to level the match. Is there still time for {conceding_team_name} to respond?!",
                "You can't write a better script! {scoring_team_name} stuns {conceding_team_name} with a tying goal deep in stoppage time.",
                "Just when it looked over! {scoring_team_name} pulls a rabbit out of the hat to equalize against {conceding_team_name}.",
                "A gut punch for {conceding_team_name}! {scoring_team_name} scores in the dying seconds to level the playing field.",
                "Pure pandemonium! {scoring_team_name} steals an equalizer at the death to break {conceding_team_name}'s hearts.",
                "The definition of clutch! {scoring_team_name} rescues the match with a stoppage-time stunner against {conceding_team_name}.",
                "{conceding_team_name} thought the whistle was coming, but {scoring_team_name} equalizes at the very last moment!",
                "Unbelievable drama! {scoring_team_name} refuses to lose, burying a stoppage-time equalizer past {conceding_team_name}.",
                "They simply never quit! {scoring_team_name} forces a dramatic draw with {conceding_team_name} in the final seconds."
            ],
            "ctas": ["Watch the frantic final moments unfold live:", "Track the live pitch data before the referee blows the whistle:"]
        },
        "stoppage_go_ahead": {
            "titles": [
                "🗡️ AT THE DEATH!", "💔 LATE HEARTBREAK!", "🔪 STOPPAGE TIME DAGGER!", 
                "🤯 90TH MINUTE MADNESS!", "⏳ STOPPAGE TIME THRILLER!", "😱 WINNING IT LATE!", 
                "🏁 BUZZER BEATER!", "🏆 CLUTCH GENE!", "🥶 ICE IN THE VEINS!", "🤯 THE STANDS ARE SHAKING!"
            ],
            "blurbs": [
                "Heartbreak for {conceding_team_name}! {scoring_team_name} pulls a rabbit out of the hat to take the lead in stoppage time.",
                "A staggering late dagger! {scoring_team_name} snatches a crucial lead, leaving {conceding_team_name} with virtually no time to respond.",
                "Absolute madness! {scoring_team_name} takes the lead at the death, forcing {conceding_team_name} into pure panic mode.",
                "What a finish! {scoring_team_name} wins it late, leaving {conceding_team_name} stunned on the pitch.",
                "The ultimate heartbreaker! {scoring_team_name} scores in stoppage time to steal the victory from {conceding_team_name}.",
                "{conceding_team_name} is in disbelief! {scoring_team_name} finds a miraculous go-ahead goal deep into added time.",
                "An incredible climax! {scoring_team_name} takes all the glory with a stoppage-time strike against {conceding_team_name}.",
                "Ice in their veins! {scoring_team_name} converts at the death to leave {conceding_team_name} empty-handed.",
                "A grandstand finish! {scoring_team_name} powers ahead of {conceding_team_name} just before the final whistle.",
                "The latest of late drama! {scoring_team_name} secures a massive go-ahead goal to sink {conceding_team_name}."
            ],
            "ctas": ["Can they survive the final whistle? Follow live:", "Don't miss the frantic ending. See live stats and pitch data here:"]
        },
        "takes_control": {
            "titles": [
                "🧱 TWO GOAL CUSHION!", "😮‍💨 BREATHING ROOM!", "🎮 IN FULL CONTROL!", 
                "🏎️ PULLING AWAY!", "🔒 LOCKING IT DOWN!", "📈 EXTENDING THE LEAD!", 
                "💼 TAKING CARE OF BUSINESS!", "🛡️ COMFORTABLE LEAD!", "🚦 GREEN LIGHT!", "🔨 HAMMERING IT HOME!"
            ],
            "blurbs": [
                "{scoring_team_name} doubles their advantage! They take a commanding two-goal lead over {conceding_team_name}.",
                "A massive insurance goal for {scoring_team_name}! They are now in full control against {conceding_team_name}.",
                "The gap widens! {scoring_team_name} extends their lead, giving {conceding_team_name} a mountain to climb.",
                "{scoring_team_name} finds the breathing room they were looking for, pulling two goals clear of {conceding_team_name}.",
                "Taking total charge! {scoring_team_name} secures a two-goal cushion to dictate the rest of the game against {conceding_team_name}.",
                "It's getting difficult for {conceding_team_name} now. {scoring_team_name} doubles their lead and takes command.",
                "A crucial second goal! {scoring_team_name} is now comfortably ahead of {conceding_team_name}.",
                "{scoring_team_name} puts their foot on the gas! They stretch their advantage over {conceding_team_name}.",
                "Solidifying their position! {scoring_team_name} gets a vital insurance goal against {conceding_team_name}.",
                "The pressure pays off again! {scoring_team_name} takes a commanding two-goal lead over {conceding_team_name}."
            ],
            "ctas": ["Can the trailing side mount a comeback? Track live:", "Follow the live match center and pitch data here:"]
        },
        "blowout": {
            "titles": [
                "🩸 THE ROUT IS ON!", "💪 ABSOLUTE DOMINANCE!", "🚂 RUNNING RIOT!", 
                "🔭 OUT OF REACH!", "🌪️ A TOTAL STORM!", "🛑 STOP THE FIGHT!", 
                "💥 TOTAL DESTRUCTION!", "🧨 BLOWING THEM AWAY!", "📉 NO MERCY!", "🎮 PLAYING ON ROOKIE MODE!"
            ],
            "blurbs": [
                "It is turning into a nightmare for {conceding_team_name}. {scoring_team_name} extends their massive lead!",
                "{scoring_team_name} is running riot! They pour it on {conceding_team_name} to turn this match into an absolute blowout.",
                "Complete dominance! {scoring_team_name} is tearing {conceding_team_name} apart with another goal.",
                "The floodgates have opened! {scoring_team_name} is showing no mercy against a collapsing {conceding_team_name}.",
                "A total mismatch today! {scoring_team_name} extends their lead, leaving {conceding_team_name} in the dust.",
                "Stop the count! {scoring_team_name} adds another goal to thoroughly humiliate {conceding_team_name}.",
                "A clinical dismantling! {scoring_team_name} runs up the score against a helpless {conceding_team_name} side.",
                "{conceding_team_name} is falling apart! {scoring_team_name} continues their relentless scoring spree.",
                "It's getting ugly! {scoring_team_name} makes it another one to completely blow out {conceding_team_name}.",
                "An absolute masterclass in attack! {scoring_team_name} effortlessly puts another past {conceding_team_name}."
            ],
            "ctas": ["Track the rest of the blowout live here:", "Follow the live match stats and ratings here:"]
        },
        "consolation_goal": {
            "titles": [
                "📉 PULLING ONE BACK", "🤏 NARROWING THE DEFICIT", "🥅 CONSOLATION STRIKE", 
                "🤏 A GLIMMER OF HOPE?", "🩹 SALVAGING PRIDE", "🛡️ A MINOR DENT", 
                "⚽ JUST A STAT?", "⏱️ TOO LITTLE TOO LATE?", "🤷 SOMETHING TO CHEER FOR", "🔥 REFUSING TO QUIT!"
            ],
            "blurbs": [
                "{scoring_team_name} finds the back of the net to pull one back, but they still have a mountain to climb against {conceding_team_name}.",
                "A goal for {scoring_team_name} gives the fans something to cheer about, but {conceding_team_name} remains in complete control of the match.",
                "{scoring_team_name} grabs a goal, but they still heavily trail {conceding_team_name} with the clock ticking down.",
                "Too little, too late? {scoring_team_name} scores, but {conceding_team_name} still holds a massive advantage.",
                "A minor consolation for {scoring_team_name}, who finally breach the {conceding_team_name} defense.",
                "Salvaging some pride! {scoring_team_name} gets on the scoresheet against a dominant {conceding_team_name}.",
                "{scoring_team_name} finally responds, but {conceding_team_name} continues to dictate the terms of this match.",
                "A goal back for {scoring_team_name}! Is it the start of a miracle, or just a stat against {conceding_team_name}?",
                "They refuse to be shut down completely! {scoring_team_name} strikes, though {conceding_team_name} is still cruising.",
                "{scoring_team_name} narrows the gap slightly, but {conceding_team_name} remains firmly in the driver's seat."
            ],
            "ctas": ["See the live match center and stats here:", "Follow the rest of the action live here:"]
        },
        "standard_upset": {
            "titles": [
                "⚠️ THE SCRIPT IS FLIPPED!", "🤫 GIANT KILLERS?!", "👀 SHOCKER IN PROGRESS!", 
                "📉 VEGAS IS SWEATING!", "🎰 UPSET ALERT!", "🧨 SPOILING THE PARTY!", 
                "🔄 TABLES TURNED!", "🚨 SURPRISE LEAD!", "😱 DEFYING THE ODDS!", "🥊 PUNCHING UP!"
            ],
            "blurbs": [
                "Throw the odds out the window! Massive underdogs {scoring_team_name} take the game right to {conceding_team_name}.",
                "A surprising turn of events puts {scoring_team_name} ahead of heavy favorites {conceding_team_name}.",
                "The heavy favorites find themselves trailing as {scoring_team_name} takes the game right to {conceding_team_name}!",
                "Who saw this coming?! {scoring_team_name} takes a shock lead over the heavily favored {conceding_team_name}.",
                "The underdogs bite first! {scoring_team_name} strikes to put all the pressure on {conceding_team_name}.",
                "A fantastic moment for {scoring_team_name} as they go ahead against the much-fancied {conceding_team_name}.",
                "Upset alert! {scoring_team_name} takes the lead, leaving {conceding_team_name} with a lot of work to do.",
                "The script has been torn up! {scoring_team_name} punches above their weight to lead {conceding_team_name}.",
                "{conceding_team_name} is stunned! {scoring_team_name} takes the lead in a massive surprise.",
                "Vegas might be panicking! {scoring_team_name} takes an unexpected lead over {conceding_team_name}."
            ],
            "ctas": ["Can they hold on for the upset? Track live here:", "Follow the live match center and pitch data here:"]
        },
        "massive_upset": {
            "titles": [
                "🌋 MAJOR UPSET ALERT!", "🤯 SHOCKER IN PROGRESS!", "💥 MASSIVE UPSET BREWING!", 
                "🪨 DAVID VS GOLIATH!", "🚨 HOLD THE PRESSES!", "😱 UNBELIEVABLE LEAD!", 
                "📉 BRACKET BUSTER!", "🧨 THE UNTHINKABLE!", "🤯 EARTHQUAKE!", "🚨 SOUND THE ALARM!"
            ],
            "blurbs": [
                "A massive shocker is unfolding! {scoring_team_name} takes a stunning lead over {conceding_team_name}.",
                "Nobody saw this coming! Massive underdogs {scoring_team_name} are out in front of {conceding_team_name}.",
                "Stunning scenes! The heavy favorites are on the ropes as {scoring_team_name} goes up on {conceding_team_name}.",
                "We are on upset watch! {scoring_team_name} takes an unbelievable lead against {conceding_team_name}.",
                "The unthinkable is happening! {scoring_team_name} stuns the football world by going ahead of {conceding_team_name}.",
                "An absolute earthquake of a goal! {scoring_team_name} drops a bomb on {conceding_team_name}.",
                "David is beating Goliath! {scoring_team_name} strikes to take a miracle lead over {conceding_team_name}.",
                "Total disbelief! {scoring_team_name} has heavily favored {conceding_team_name} trailing in this match.",
                "{conceding_team_name} is in serious danger of a historic defeat as {scoring_team_name} takes the lead!",
                "Hold the presses! {scoring_team_name} just scored a mammoth goal against {conceding_team_name}."
            ],
            "ctas": ["Witness the upset attempt live:", "Don't miss this potential shocker. Live stats and odds:"]
        },
        "late_upset": {
            "titles": [
                "👀 LATE UPSET BREWING!", "🚨 LATE UNDERDOG ALERT!", "📉 UPSET WATCH: CLOSING STAGES!", 
                "💦 VEGAS IS SWEATING!", "⏳ LATE SHOCKER!", "🧨 STEALING IT LATE!", 
                "😱 LATE GIANT KILLING!", "⏱️ TICKING CLOCK FOR THE FAVORITES!", "🤯 A LATE STUNNER!", "🚨 NEARING A SHOCKER!"
            ],
            "blurbs": [
                "{scoring_team_name} snatches a crucial late lead, putting {conceding_team_name} in serious danger of a huge upset!",
                "A massive late goal puts heavy favorites {conceding_team_name} on the brink of defeat against {scoring_team_name}.",
                "The clock is ticking on {conceding_team_name} as {scoring_team_name} scores a brilliant late go-ahead goal!",
                "An incredible late twist! Underdogs {scoring_team_name} take the lead, leaving {conceding_team_name} stunned.",
                "Can they pull it off?! {scoring_team_name} finds a late goal to push {conceding_team_name} to the brink.",
                "The giant killers strike late! {scoring_team_name} takes a shocking advantage over {conceding_team_name}.",
                "Panic mode for {conceding_team_name}! {scoring_team_name} nets a late stunner to threaten a massive upset.",
                "A dramatic late shift in power! {scoring_team_name} goes ahead of the highly favored {conceding_team_name}.",
                "The upset is nearly complete! {scoring_team_name} scores late to pile the pressure on {conceding_team_name}.",
                "{conceding_team_name} is running out of time as {scoring_team_name} secures a shocking late lead!"
            ],
            "ctas": ["Watch the frantic final push live here:", "Can the underdogs hold the line? Live stats:"]
        },
        "stoppage_upset": {
            "titles": [
                "🤯 STUNNER IN STOPPAGE TIME!", "😱 LATE UPSET THRILLER!", "💥 MADNESS AT THE DEATH!", 
                "💀 THE ULTIMATE SHOCKER!", "🌋 STOPPAGE TIME UPSET!", "🧨 SHOCKING THE WORLD LATE!", 
                "🚨 A MIRACLE UPSET!", "🤯 SCRIPT TORN APART!", "⏰ BEATING THE ODDS AT THE HORN!", "😱 UNREAL FINISH!"
            ],
            "blurbs": [
                "A staggering stoppage-time strike! {scoring_team_name} takes a shocking lead, forcing {conceding_team_name} into a desperate final push.",
                "Parlays are in critical danger! {scoring_team_name} strikes in stoppage time to go ahead of {conceding_team_name}.",
                "A miracle at the death! {scoring_team_name} scores a stoppage-time stunner to completely rock {conceding_team_name}.",
                "The ultimate giant killing! {scoring_team_name} finds a winner in stoppage time against {conceding_team_name}.",
                "Unbelievable scenes! {scoring_team_name} shatters the odds with a stoppage-time goal against {conceding_team_name}.",
                "{conceding_team_name} is left in absolute shock as {scoring_team_name} takes the lead deep into added time!",
                "The most dramatic of upsets! {scoring_team_name} stuns {conceding_team_name} right before the final whistle.",
                "A historic stoppage-time moment! {scoring_team_name} defies belief to go ahead of {conceding_team_name}.",
                "The heavy favorites are collapsing! {scoring_team_name} scores a miracle goal at the death against {conceding_team_name}.",
                "{scoring_team_name} just pulled off the impossible! A stoppage-time winner to sink {conceding_team_name}."
            ],
            "ctas": ["Witness the final frantic moments live:", "Don't miss the final whistle of this shocker. Live stats:"]
        },
        "agg_late_equalizer": {
            "titles": ["🚨 AGGREGATE TIED LATE!", "🚨 THE TIE IS LEVEL!", "🚨 DRAMATIC AGGREGATE EQUALIZER!"],
            "blurbs": [
                "A massive goal from {scoring_team_name}! They have erased the deficit and the tournament tie is completely level as time winds down.",
                "{scoring_team_name} refuses to go quietly! They tie things up on aggregate, setting up a frantic finish against {conceding_team_name}.",
                "We are all square on aggregate! {scoring_team_name} claws their way back into the tie."
            ],
            "ctas": ["Who will find a winner? Follow the final push live:", "Track the closing minutes of this tie here:"]
        },
        "agg_late_go_ahead": {
            "titles": ["🚨 LATE AGGREGATE LEAD!", "🚨 ADVANTAGE: {scoring_team_name}!", "🚨 CLUTCH TOURNAMENT GOAL!"],
            "blurbs": [
                "A game-changing strike! {scoring_team_name} snatches the aggregate lead late in the 2nd leg.",
                "Heartbreak for {conceding_team_name} as {scoring_team_name} takes a crucial late lead in the tie!",
                "{scoring_team_name} steps up when it matters most, taking the aggregate advantage over {conceding_team_name}."
            ],
            "ctas": ["Can they hold on to advance? Follow live:", "Track the final minutes of this 2nd leg here:"]
        },
        "agg_stoppage_equalizer": {
            "titles": ["🚨 MIRACLE AT THE DEATH!", "🚨 STOPPAGE TIME AGGREGATE EQUALIZER!", "🚨 ABSOLUTE SCENES!"],
            "blurbs": [
                "You cannot write a better script! {scoring_team_name} scores deep in stoppage time to tie the aggregate score!",
                "A devastating blown lead for {conceding_team_name}! {scoring_team_name} forces a dramatic tie in the dying moments.",
                "Absolute madness! {scoring_team_name} climbs out of the grave to level the tie right at the end."
            ],
            "ctas": ["Are we heading to extra time? Follow live:", "Don't miss the post-goal chaos here:"]
        },
        "agg_stoppage_go_ahead": {
            "titles": ["🚨 STOPPAGE TIME TOURNAMENT THRILLER!", "🚨 A DAGGER AT THE DEATH!", "🚨 LATE HEARTBREAK!"],
            "blurbs": [
                "Heartbreak for {conceding_team_name}! {scoring_team_name} takes the aggregate lead in stoppage time.",
                "A staggering late dagger! {scoring_team_name} snatches the tie, leaving {conceding_team_name} with virtually no time to respond.",
                "They have won it at the death! {scoring_team_name} stuns {conceding_team_name} to take the aggregate advantage."
            ],
            "ctas": ["Can they survive the final whistle? Follow live:", "Watch the desperate final seconds unfold here:"]
        },
        "agg_dagger": {
            "titles": ["🚨 NAIL IN THE COFFIN!", "🚨 THE TIE IS SLIPPING AWAY!", "🚨 COMMANDING AGGREGATE LEAD!"],
            "blurbs": [
                "That might just do it! {scoring_team_name} extends their aggregate lead, putting the tie nearly out of reach for {conceding_team_name}.",
                "A devastating blow for {conceding_team_name}. {scoring_team_name} takes a commanding multi-goal lead on aggregate.",
                "{scoring_team_name} flexes their muscles, adding an insurance goal to all but secure their spot in the next round."
            ],
            "ctas": ["Track the remainder of the match live here:", "Follow the live pitch data and stats here:"]
        },
        "agg_consolation": {
            "titles": ["⚽ MATCH GOAL", "⚽ CONSOLATION STRIKE", "⚽ LATE MATCH LEAD"],
            "blurbs": [
                "{scoring_team_name} finds the back of the net on the day, but they still have a mountain to climb against {conceding_team_name} on aggregate.",
                "A goal for {scoring_team_name} rewards the live bettors, but {conceding_team_name} remains in complete control of the overall tie.",
                "{scoring_team_name} gets on the board, but they still heavily trail {conceding_team_name} on aggregate with time running out."
            ],
            "ctas": ["See the live match center and stats here:", "Follow the closing stages of the tie here:"]
        }
    }

    current_time_epoch = time.time()

    for goal_key, goal_data in daily_goals.items():
        # 1. Memory Check: Skip if already tweeted
        if goal_key in tweeted_recently or goal_key in memory.get(date_str, []):
            continue

        # 2. Age Check: Skip if goal is older than MAX_GOAL_AGE_SECONDS
        goal_timestamp = goal_data.get("timestamp", 0)
        if current_time_epoch - goal_timestamp > MAX_GOAL_AGE_SECONDS:
            continue

        scenario = goal_data.get("scenario", "standard_goal")
        if scenario not in PHRASES:
            scenario = "tight_clash_goal"  # Fallback phrase group

        scoring_team = goal_data.get("scoring_team", "")
        conceding_team = goal_data.get("conceding_team", "")
        home_team = goal_data.get("home_team", "")
        away_team = goal_data.get("away_team", "")
        home_score = goal_data.get("home_score", 0)
        away_score = goal_data.get("away_score", 0)
        scorer = goal_data.get("scorer", "")
        display_minute = goal_data.get("display_minute", "")
        is_own_goal = goal_data.get("is_own_goal", False)
        american_odds = goal_data.get("american_odds", "TBD")
        league_hashtag = goal_data.get("league_hashtag", "")
        match_url = goal_data.get("match_url", "")

        raw_title = random.choice(PHRASES[scenario]["titles"])
        title = raw_title.format(
            scoring_team_name=scoring_team,
            conceding_team_name=conceding_team,
            player_name=scorer
        )

        blurb_raw = random.choice(PHRASES[scenario]["blurbs"])
        blurb = blurb_raw.format(
            scoring_team_name=scoring_team,
            conceding_team_name=conceding_team,
            player_name=scorer
        )
        cta = random.choice(PHRASES[scenario]["ctas"])

        scorer_str = f"{scorer} (Own Goal)" if is_own_goal else f"{scorer} ({scoring_team})"

        # Assemble tweet body
        body_content = f"⚽ {display_minute}' GOAL - {scorer_str}\n{home_team} {home_score} - {away_score} {away_team}\n\n"
        if "upset" in scenario and american_odds != "TBD":
            body_content += f"📊 Pre-Match Line: {scoring_team} ({american_odds})\n\n"
        body_content += f"{blurb}"

        home_hash = home_team.replace(' ', '').replace('-', '').replace('.', '')
        away_hash = away_team.replace(' ', '').replace('-', '').replace('.', '')

        # --- Link-Free X (Twitter) Text ---
        tweet_text = f"{title}\nupdate by futbolstartingeleven(link in profile):\n\n{body_content}\n{league_hashtag} #{home_hash} #{away_hash}"

        # --- Bluesky Rich Text (CTA & Raw URL near Top, Bulletproof 3-Stage <290 Guard) ---
        bsky_tb = client_utils.TextBuilder()
        
        # Isolate essential goal info (Scoreline & Scorer)
        core_score_line = f"⚽ {display_minute}' GOAL - {scorer_str}\n{home_team} {home_score} - {away_score} {away_team}"
        if "upset" in scenario and american_odds != "TBD":
            core_score_line += f"\n📊 Pre-Match Line: {scoring_team} ({american_odds})"

        bsky_top = f"{title}\n{cta} "
        bsky_body = f"\n\n{core_score_line}\n\n{blurb}"
        bsky_hashtags = f"\n\n{league_hashtag} #{home_hash} #{away_hash}"
        
        total_chars = len(bsky_top) + len(match_url) + len(bsky_body) + len(bsky_hashtags)
        
        # Stage 1: Shorten CTA and keep primary hashtag
        if total_chars > 290:
            bsky_top = f"{title}\nFollow live: "
            bsky_hashtags = f"\n\n#{home_hash}"
            total_chars = len(bsky_top) + len(match_url) + len(bsky_body) + len(bsky_hashtags)
            
        # Stage 2: Drop all hashtags
        if total_chars > 290:
            bsky_hashtags = ""
            total_chars = len(bsky_top) + len(match_url) + len(bsky_body)
            
        # Stage 3: Drop flavor blurb if raw URL + title + scoreline is still tight
        if total_chars > 290:
            bsky_body = f"\n\n{core_score_line}"
            total_chars = len(bsky_top) + len(match_url) + len(bsky_body)

        bsky_tb.text(bsky_top)
        bsky_tb.link(match_url, match_url)  # Raw URL displayed right at the top
        bsky_tb.text(f"{bsky_body}{bsky_hashtags}")

        upload_success = False

        if DRY_RUN:
            upload_success = True
            print(f"\n[SHADOW] 🛑 Mocking Futbol Goal Tweet ({scenario}):\n{tweet_text}")
        else:
            twitter_success = False
            bsky_success = False

            # --- Post to X ---
            try:
                if futbol_client:
                    futbol_client.create_tweet(text=tweet_text)
                    log_x_tweet_audit("FUTBOL", goal_key, date_str)
                    twitter_success = True
            except Exception as err:
                print(f"⚠️ Failed to post Futbol goal to X for {goal_key}: {err}")

            # --- Post to Bluesky ---
            config = LEAGUE_CONFIG.get("futbol")
            bsky_client_inst = config.get("bsky_client") if config else setup_bsky_client("futbol_account")
            if bsky_client_inst:
                try:
                    bsky_client_inst.send_post(bsky_tb)
                    bsky_success = True
                except Exception as err:
                    print(f"⚠️ Failed to post Futbol goal to Bluesky for {goal_key}: {err}")

            upload_success = twitter_success or bsky_success

        if upload_success:
            log_today.append(goal_key)
            tweeted_recently.append(goal_key)
            new_tweets_sent = True
            memory[date_str] = log_today

            if firebase_admin._apps:
                try:
                    db.reference('tweet_log').update({date_str: log_today})
                except Exception as e:
                    print(f"⚠️ Failed to update Firebase log: {e}")

            futbol_tweets_this_loop += 1
            if futbol_tweets_this_loop % 3 == 0:
                print("⏳ Throttling API: Sent 3 tweets, resting for 5 seconds...")
                await asyncio.sleep(5)
            else:
                await asyncio.sleep(1.5)

    # ==========================================
    # FUTBOL GAME SUMMARIES ENGINE
    # ==========================================
    try:
        summary_url = f"https://futbolstartingeleven.com/data/game_summary.json?v={today_est.timestamp()}"
        game_summaries_data = requests.get(summary_url, timeout=10).json()
    except Exception as e:
        print(f"⚠️ Could not fetch game_summary.json: {e}")
        game_summaries_data = {}

    MAX_SUMMARY_AGE_SECONDS = 300  # Skip summaries older than 5 minutes
    current_time_epoch = time.time()

    SUMMARY_PHRASES = {
        "narrow_win": {
            "titles": [
                "⏱️ DOWN TO THE WIRE!", 
                "⚔️ NARROW WIN!", 
                "🔒 THREE POINTS SECURED!", 
                "🍿 EDGE-OF-YOUR-SEAT FINISH!", 
                "🔥 SQUEAKING THROUGH!", 
                "🛡️ HELD THE LINE!", 
                "💪 DIGGING DEEP FOR THE WIN!",
                "🏁 HARD FOUGHT VICTORY!"
            ],
            "blurbs": [
                "A tight battle until the final whistle, but {winner_name} holds on to secure a huge victory over {loser_name}!",
                "{winner_name} edges out {loser_name} in a razor-thin contest to take all three points!",
                "Fine margins make the difference as {winner_name} claims a hard-earned victory over {loser_name}!",
                "What a battle! {winner_name} digs deep to secure a vital win against {loser_name}.",
                "Neither side gave an inch, but {winner_name} finds the decisive moment to push past {loser_name}!"
            ]
        },
        "comfortable_win": {
            "titles": [
                "💼 SOLID PERFORMANCE!", 
                "✅ TAKING CARE OF BUSINESS!", 
                "🎒 THREE POINTS IN THE BAG!", 
                "🎮 CONTROLLED VICTORY!", 
                "📈 CRUISING TO VICTORY!", 
                "🟢 PROFESSIONAL DISPLAY!", 
                "⚽ COMFORTABLE AT THE WHISTLE!",
                "🏁 JOB WELL DONE!"
            ],
            "blurbs": [
                "{winner_name} puts in a disciplined performance to claim a convincing win against {loser_name}.",
                "{winner_name} stays in control to pull away with a solid victory over {loser_name}!",
                "A professional display from {winner_name} ensures all three points against {loser_name}.",
                "{winner_name} dictates the tempo from start to finish to hand {loser_name} a clear defeat.",
                "No surprises here as {winner_name} handles business and cruises past {loser_name}."
            ]
        },
        "blowout_win": {
            "titles": [
                "💥 STATEMENT WIN!", 
                "🪄 ABSOLUTE MASTERCLASS!", 
                "🔥 RAMPANT PERFORMANCE!", 
                "🚀 BLOWOUT VICTORY!", 
                "🚂 RUNNING RIOT!", 
                "🩸 THE ROUT IS COMPLETE!", 
                "🛑 STOP THE FIGHT!",
                "🏁 TOTAL DOMINANCE!"
            ],
            "blurbs": [
                "An absolute display of power! {winner_name} completely dominates {loser_name} in a runaway victory.",
                "The floodgates opened! {winner_name} puts on a goal-scoring clinic against {loser_name}.",
                "A complete dismantling! {winner_name} leaves no doubt with a dominant win over {loser_name}.",
                "{winner_name} runs riot today, leaving {loser_name} with nowhere to hide in a massive win!",
                "Pure dominance from the opening whistle! {winner_name} blows past {loser_name} in ruthless fashion."
            ]
        },
        "goalless_draw": {
            "titles": [
                "🤝 SPOILS SHARED!", 
                "🛡️ STALEMATE!", 
                "⚖️ HONORS EVEN!", 
                "⭕ ZEROES ON THE BOARD!", 
                "🧱 UNBREAKABLE DEFENSES!", 
                "🚫 NO BREAKTHROUGH!", 
                "🔒 LOCKED OUT AT FULL TIME!",
                "🏁 DEADLOCK AT FULL TIME!"
            ],
            "blurbs": [
                "Neither side could break through today as {home_team} and {away_team} battle to a 0-0 draw.",
                "A defensive battle from start to finish! {home_team} and {away_team} walk away with a point apiece.",
                "Zeroes on the board at the final whistle as {home_team} and {away_team} split the points.",
                "Defenses reign supreme as {home_team} and {away_team} cancel each other out completely.",
                "A hard-tackling, tight stalemate ends with {home_team} and {away_team} taking home one point each."
            ]
        },
        "standard_draw": {
            "titles": [
                "🤝 POINTS SPLIT!", 
                "⚖️ HONORS EVEN!", 
                "⚔️ HARD FOUGHT DRAW!", 
                "🔒 LOCKED IN A DRAW!", 
                "📊 EVEN STEVENS!", 
                "🔄 TRADING BLOWS TO A DRAW!", 
                "🕊️ PEACE DECLARED AT FT!",
                "🏁 ALL SQUARE AT THE WHISTLE!"
            ],
            "blurbs": [
                "A closely fought contest comes to an end with {home_team} and {away_team} sharing the points!",
                "Nothing to separate them! {home_team} and {away_team} finish level after 90 minutes.",
                "Both teams trade blows, but the match finishes all square between {home_team} and {away_team}.",
                "A fair result after 90 minutes as {home_team} and {away_team} leave it all on the pitch.",
                "{home_team} and {away_team} battle back and forth before settling for a well-earned draw."
            ]
        },
        "thrilling_draw": {
            "titles": [
                "🍿 GOAL FESTIVAL!", 
                "🔥 HIGH-DRAMA DRAW!", 
                "🎢 ABSOLUTE SPECTACLE!", 
                "🎆 UNBELIEVABLE ENTERTAINMENT!", 
                "💣 ALL-OUT WAR ENDS EVEN!", 
                "✨ AN ABSOLUTE CLASSIC!", 
                "🎪 CIRCUS OF GOALS!",
                "🏁 WHAT A THRILLER!"
            ],
            "blurbs": [
                "What a match! {home_team} and {away_team} trade blows in an incredible high-scoring draw!",
                "Pure entertainment for the neutral as {home_team} and {away_team} battle to a wild draw!",
                "Goals, drama, and non-stop action! {home_team} and {away_team} share the points in a thrilling clash.",
                "A chaotic showdown ends with {home_team} and {away_team} splitting the points in an instant classic!",
                "Neither side refused to back down in an absolute goal-fest between {home_team} and {away_team}!"
            ]
        },
        "upset_win": {
            "titles": [
                "🚨 THE GIANT FALLS!", 
                "💣 SHOCK FULL-TIME RESULT!", 
                "🔄 SCRIPT FLIPPED!", 
                "🤫 GIANT KILLERS!", 
                "📉 VEGAS TAKES A HIT!", 
                "🎰 UNBELIEVABLE SHOCKER!", 
                "🥊 PUNCHING ABOVE THEIR WEIGHT!",
                "🏁 UPSET COMPLETE!"
            ],
            "blurbs": [
                "{winner_name} defies the odds and pulls off a massive upset victory over {loser_name}!",
                "Underdogs {winner_name} shock {loser_name} with a memorable performance to claim all three points!",
                "The odds meant nothing today! {winner_name} stuns {loser_name} to secure a remarkable win.",
                "A massive shocker as {winner_name} tears up the script to take down {loser_name}!",
                "{loser_name} caught sleeping as {winner_name} delivers a statement upset win!"
            ]
        },
        "massive_upset_win": {
            "titles": [
                "😱 UNBELIEVABLE SHOCKER!", 
                "🌋 EARTHQUAKE RESULT!", 
                "🪨 DAVID SLAYS GOLIATH!", 
                "🚨 HOLD THE PRESSES!", 
                "🧨 HISTORIC SHOCKER!", 
                "💥 BRACKET BUSTER!", 
                "🤯 THE IMPOSSIBLE HAPPENED!",
                "🏁 COLOSSAL UPSET!"
            ],
            "blurbs": [
                "A result that sends shockwaves through the league! Massive underdogs {winner_name} stun {loser_name}!",
                "Nobody saw this coming! {winner_name} pulls off a monumental upset victory against {loser_name}!",
                "Pure disbelief! {winner_name} defies every prediction to beat {loser_name} in an unforgettable match.",
                "An absolute earthquake of a result as {winner_name} slays {loser_name} against all odds!",
                "David takes down Goliath! {winner_name} produces a historic performance to sink {loser_name}."
            ]
        }
    }

    for fix_id, summary in game_summaries_data.items():
        ft_key = f"FT_SUMMARY_{fix_id}"
        
        # 1. Memory Check: Skip if already posted
        if ft_key in tweeted_recently or ft_key in memory.get(date_str, []):
            continue

        # 2. Stale Check: Skip if summary was generated more than 5 mins ago
        created_at = summary.get("created_at", 0)
        if (current_time_epoch - created_at) > MAX_SUMMARY_AGE_SECONDS:
            continue

        home_team = summary.get("home_team", "")
        away_team = summary.get("away_team", "")
        home_score = summary.get("home_score", 0)
        away_score = summary.get("away_score", 0)
        scenario = summary.get("scenario", "standard_draw")
        
        if scenario not in SUMMARY_PHRASES:
            scenario = "narrow_win" if summary.get("outcome") != "draw" else "standard_draw"

        winner_name = summary.get("winner_name") or home_team
        loser_name = summary.get("loser_name") or away_team
        
        raw_title = random.choice(SUMMARY_PHRASES[scenario]["titles"])
        title = raw_title.format(
            winner_name=winner_name,
            loser_name=loser_name,
            home_team=home_team,
            away_team=away_team
        )

        blurb_raw = random.choice(SUMMARY_PHRASES[scenario]["blurbs"])
        blurb = blurb_raw.format(
            winner_name=winner_name,
            loser_name=loser_name,
            home_team=home_team,
            away_team=away_team
        )

        home_scorers = summary.get("home_scorers", [])
        away_scorers = summary.get("away_scorers", [])
        
        # Build individual line-by-line Goalscorer entries
        scorers_block = []
        if home_scorers:
            scorers_block.append(f"⚽ {home_team}:")
            for scorer in home_scorers:
                scorers_block.append(f"• {scorer}")
        if away_scorers:
            if home_scorers:
                scorers_block.append("")  # Empty spacing line between teams
            scorers_block.append(f"⚽ {away_team}:")
            for scorer in away_scorers:
                scorers_block.append(f"• {scorer}")
        
        scorers_str = "\n".join(scorers_block) if scorers_block else "🚫 No goals scored."

        # Build individual line-by-line Red Card entries
        stats = summary.get("stats", {})
        h_reds = stats.get("home_red_cards", 0)
        a_reds = stats.get("away_red_cards", 0)
        red_cards_block = []
        if h_reds > 0:
            red_cards_block.append(f"🟥 {home_team}: {h_reds} Red Card{'s' if h_reds > 1 else ''}")
        if a_reds > 0:
            red_cards_block.append(f"🟥 {away_team}: {a_reds} Red Card{'s' if a_reds > 1 else ''}")
        
        red_card_str = "\n".join(red_cards_block) + "\n" if red_cards_block else ""

        league_hashtag = summary.get("league_hashtag", "")
        league_name = summary.get("league_name", "")
        match_url = summary.get("match_url", "")
        home_hash = home_team.replace(' ', '').replace('-', '').replace('.', '')
        away_hash = away_team.replace(' ', '').replace('-', '').replace('.', '')

        # --- Link-Free X (Twitter) Text ---
        tweet_text = (
            f"{title}\n"
            f"summary by futbolstartingeleven(link in profile)\n\n"
            f"🏁 FT: {home_team} {home_score} - {away_score} {away_team} in {league_name} action\n\n"
            f"{scorers_str}\n"
            f"{red_card_str}\n"
            f"{blurb}\n\n"
            f"{league_hashtag} #{home_hash} #{away_hash}"
        )

        # --- Bluesky Rich Text (Raw URL & Progressive 4-Stage <290 Character Guard) ---
        bsky_tb = client_utils.TextBuilder()
        
        bsky_header = f"{title}\n🏁 FT: {home_team} {home_score} - {away_score} {away_team}\n"
        bsky_cta = "Match stats & ratings: "
        bsky_details = f"{scorers_str}\n{red_card_str}\n{blurb}".strip()
        bsky_hashtags = f"\n\n{league_hashtag} #{home_hash} #{away_hash}"
        
        total_chars = len(bsky_header) + len(bsky_cta) + len(match_url) + len(bsky_details) + len(bsky_hashtags) + 2
        
        # Stage 1: Drop secondary hashtags
        if total_chars > 290:
            bsky_hashtags = f"\n\n#{home_hash}"
            total_chars = len(bsky_header) + len(bsky_cta) + len(match_url) + len(bsky_details) + len(bsky_hashtags) + 2
            
        # Stage 2: Drop all hashtags
        if total_chars > 290:
            bsky_hashtags = ""
            total_chars = len(bsky_header) + len(bsky_cta) + len(match_url) + len(bsky_details) + 2
            
        # Stage 3: Drop flavor blurb
        if total_chars > 290:
            bsky_details = f"{scorers_str}\n{red_card_str}".strip()
            total_chars = len(bsky_header) + len(bsky_cta) + len(match_url) + len(bsky_details) + 2
            
        # Stage 4: Compress goalscorers list if match was a high-scoring blowout
        if total_chars > 290 and (home_scorers or away_scorers):
            compressed_scorers = f"⚽ Goals: {len(home_scorers)} home, {len(away_scorers)} away"
            bsky_details = f"{compressed_scorers}\n{red_card_str}".strip()
            total_chars = len(bsky_header) + len(bsky_cta) + len(match_url) + len(bsky_details) + 2

        # Ultra Fallback: If still over 290, keep only header + CTA link
        if total_chars > 290:
            bsky_details = ""

        bsky_tb.text(bsky_header)
        bsky_tb.text(bsky_cta)
        bsky_tb.link(match_url, match_url)
        if bsky_details:
            bsky_tb.text(f"\n\n{bsky_details}")
        if bsky_hashtags:
            bsky_tb.text(bsky_hashtags)

        upload_success = False

        if DRY_RUN:
            upload_success = True
            print(f"\n[SHADOW] 🛑 Mocking Futbol FT Summary Tweet ({scenario}):\n{tweet_text}")
        else:
            twitter_success = False
            bsky_success = False

            # --- Post to X ---
            try:
                if futbol_client:
                    futbol_client.create_tweet(text=tweet_text)
                    log_x_tweet_audit("FUTBOL", ft_key, date_str)
                    twitter_success = True
            except Exception as err:
                print(f"⚠️ Failed to post Futbol summary to X for {ft_key}: {err}")

            # --- Post to Bluesky ---
            config = LEAGUE_CONFIG.get("futbol")
            bsky_client_inst = config.get("bsky_client") if config else setup_bsky_client("futbol_account")
            if bsky_client_inst:
                try:
                    bsky_client_inst.send_post(bsky_tb)
                    bsky_success = True
                except Exception as err:
                    print(f"⚠️ Failed to post Futbol summary to Bluesky for {ft_key}: {err}")

            upload_success = twitter_success or bsky_success

        if upload_success:
            log_today.append(ft_key)
            tweeted_recently.append(ft_key)
            new_tweets_sent = True
            memory[date_str] = log_today

            if firebase_admin._apps:
                try:
                    db.reference('tweet_log').update({date_str: log_today})
                except Exception as e:
                    print(f"⚠️ Failed to update Firebase log: {e}")

            futbol_tweets_this_loop += 1
            if futbol_tweets_this_loop % 3 == 0:
                print("⏳ Throttling API: Sent 3 tweets, resting for 5 seconds...")
                await asyncio.sleep(5)
            else:
                await asyncio.sleep(1.5)

    # ==========================================
    # CLOSING BROWSER CLEANUP
    # ==========================================
    if browser:
        print("🛑 Closing Cloud Browser connection for this loop.")
        await browser.close()
    await playwright_manager.stop()

    if new_tweets_sent and firebase_admin._apps:
        try:
            db.reference('tweet_log').update(memory)
            print("\n💾 In-Memory State Synced to Firebase.")
        except Exception as e: pass
    
    return 60, memory 

# ==========================================
# 6. THE PERSISTENT RENDER WRAPPER
# ==========================================
async def main():
    print("🤖 Starting Publisher Bot (Render Persistent Engine)...")
    
    persisted_memory = fetch_initial_memory()
    
    if firebase_admin._apps:
        existing_fb = db.reference('tweet_log').get()
        if not existing_fb and persisted_memory:
            db.reference('tweet_log').set(persisted_memory)
    
    if persisted_memory is None:
        persisted_memory = {}
    
    while True:
        try:
            loop_start_time = time.time()
            
            target_sleep_sec, updated_memory = await run_engines(persisted_memory)
            persisted_memory = updated_memory
            
            loop_elapsed = time.time() - loop_start_time
            actual_sleep = max(0.0, target_sleep_sec - loop_elapsed)
            
            if actual_sleep > 0:
                print(f"⏳ Loop took {loop_elapsed:.1f}s. Sleeping {actual_sleep:.1f}s...")
                await asyncio.sleep(actual_sleep)
                
        except Exception as e:
            print(f"\n❌ Loop crashed: {e}. Restarting loop in 60s...")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
