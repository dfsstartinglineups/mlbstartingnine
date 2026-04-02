import requests
import json
import os
import time
import zoneinfo
import csv
import io
import re
import unicodedata
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# --- SELENIUM IMPORTS ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
DATA_DIR = 'data'
DAILY_FILES_DIR = os.path.join(DATA_DIR, 'daily_files')
UMPIRES_FILE = os.path.join(DATA_DIR, 'umpires.json')
PARKS_FILE = os.path.join(DATA_DIR, 'parks.json')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DAILY_FILES_DIR, exist_ok=True)

# --- API TRACKING ---
API_CALL_TRACKER = {
    "schedule": 0, "odds": 0, "live_feed": 0, "bvp": 0, "splits": 0, "bbm_csv": 0
}

GLOBAL_SLATES = {'fanduel': {}, 'draftkings': {}}

# --- BBM TO MLB ID MAPPING ---
BBM_TO_MLB_ID = {
    'ARI': 109, 'ATL': 144, 'BAL': 110, 'BOS': 111, 'CHC': 112, 
    'CHW': 145, 'CIN': 113, 'CLE': 114, 'COL': 115, 'DET': 116, 
    'HOU': 117, 'KC': 118,  'LAA': 108, 'LAD': 119, 'MIA': 146, 
    'MIL': 158, 'MIN': 142, 'NYM': 121, 'NYY': 147, 'OAK': 133, 
    'PHI': 143, 'PIT': 134, 'SD': 135,  'SEA': 136, 'SF': 137, 
    'STL': 138, 'TB': 139,  'TEX': 140, 'TOR': 141, 'WAS': 120
}

# ==========================================
# --- HELPER FUNCTIONS ---
# ==========================================
def clean_player_name(name):
    if not name or name == '-': return ""
    name = str(name).lower().strip()
    # Strip (h) and (p) just in case it sneaks through
    name = re.sub(r'\s*\([hp]\)', '', name)
    # Strip punctuation and convert hyphens to spaces
    name = name.replace('.', '').replace("'", "").replace("-", " ")
    # Strip accents (e.g. Acuña -> Acuna)
    name = ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    # Strip suffixes
    for suffix in [' jr', ' sr', ' ii', ' iii', ' iv']:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name.strip()

def get_dff_team_abbr(team_name):
    map_ = {
        "Diamondbacks": "ARI", "Braves": "ATL", "Orioles": "BAL", "Red Sox": "BOS", "Cubs": "CHC",
        "White Sox": "CWS", "Reds": "CIN", "Guardians": "CLE", "Rockies": "COL", "Tigers": "DET",
        "Astros": "HOU", "Royals": "KC", "Angels": "LAA", "Dodgers": "LAD", "Marlins": "MIA",
        "Brewers": "MIL", "Twins": "MIN", "Mets": "NYM", "Yankees": "NYY", "Athletics": "OAK",
        "Phillies": "PHI", "Pirates": "PIT", "Padres": "SD", "Giants": "SF", "Mariners": "SEA",
        "Cardinals": "STL", "Rays": "TB", "Rangers": "TEX", "Blue Jays": "TOR", "Nationals": "WAS"
    }
    for k, v in map_.items():
        if k in team_name: return v
    return team_name[:3].upper()

def load_json(path, default_val):
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                # Load the data, but use the default if f is empty (None)
                loaded_data = json.load(f)
                return loaded_data if loaded_data is not None else default_val
        except (json.JSONDecodeError, OSError) as e:
            # If the file is corrupted, print a warning and use the default
            print(f"⚠️ Warning: Found corrupted JSON file at {path}. Ignoring file. Error: {e}")
            return default_val
        except Exception as e:
            # Catch-all for unexpected issues
            print(f"⚠️ Unexpected error loading {path}: {e}")
            return default_val
    return default_val

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)

def get_active_sport_ids():
    current_date = datetime.utcnow().date()
    wbc_start = datetime(2026, 3, 4).date()
    wbc_end = datetime(2026, 3, 17).date()
    if wbc_start <= current_date <= wbc_end:
        return "1,51"
    return "1"

# ==========================================
# --- DATA FETCHERS ---
# ==========================================
def get_bbm_projected_lineups(target_date):
    global API_CALL_TRACKER
    API_CALL_TRACKER["bbm_csv"] += 1
    
    session = requests.Session()
    headers = {'User-Agent': 'Mozilla/5.0'}
    session.get("https://baseballmonster.com/lineups.aspx", headers=headers)
    
    csv_url = f"https://baseballmonster.com/Lineups.aspx?csv=1&d={target_date}"
    response = session.get(csv_url, headers=headers)
    projections = {}
    
    if response.status_code == 200 and len(response.text) > 100:
        csv_data = io.StringIO(response.text)
        reader = csv.reader(csv_data)
        next(reader, None) 
        
        for row in reader:
            if len(row) < 7: continue
            
            team_code = row[0].strip()
            game_num = row[2].strip()
            player_mlb_id = row[3].strip()
            
            # CRITICAL FIX: Strip (H) and (P) out of the raw display name for Ohtani
            raw_name = row[4].strip()
            player_name = re.sub(r'\s*\([HP]\)', '', raw_name, flags=re.IGNORECASE).strip()
            
            batting_order = row[5].strip()
            confirmed = True if row[6].strip().upper() == 'Y' else False
            mlb_team_id = BBM_TO_MLB_ID.get(team_code)
            if not mlb_team_id: continue 
            
            team_key = f"{mlb_team_id}_{game_num}"
            if team_key not in projections:
                projections[team_key] = {"startingPitcher": None, "battingOrder": []}
                
            player_obj = {
                "id": int(player_mlb_id) if player_mlb_id.isdigit() else player_mlb_id,
                "name": player_name,
                "verified": confirmed
            }
            if batting_order.isdigit() and 1 <= int(batting_order) <= 9:
                player_obj["order"] = int(batting_order)
                projections[team_key]["battingOrder"].append(player_obj)
            else:
                projections[team_key]["startingPitcher"] = player_obj
                
        for key in projections:
            projections[key]["battingOrder"].sort(key=lambda x: x["order"])
            
    return projections

def scrape_dff_projections(target_date_str):
    print(f"\n--- BROWSER BOT STARTING FOR: {target_date_str} ---")
    dff_data = {}
    platforms = ['fanduel', 'draftkings']
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    try:
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
    except Exception as e:
        print(f"Failed to launch browser bot: {e}")
        return dff_data

    for platform in platforms:
        base_url = f"https://www.dailyfantasyfuel.com/mlb/projections/{platform}/{target_date_str}"
        slate_ids = set()
        
        try:
            print(f"Loading {platform.upper()} Base URL: {base_url}")
            driver.get(base_url)
            time.sleep(3) 
            
            try:
                toggles = driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'SLATE', 'slate'), 'slate') or contains(translate(text(), 'MAIN', 'main'), 'main') or contains(@class, 'slate')]")
                for t in toggles:
                    try:
                        if not t.get_attribute("href"):
                            driver.execute_script("arguments[0].click();", t)
                    except: pass
                time.sleep(1) 
            except: pass

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            def add_slate_name(sid, name):
                if not sid or not re.match(r'^[a-zA-Z0-9]{5}$', str(sid)): return
                slate_ids.add(sid)
                name = str(name).strip()
                if name and len(name) > 2:
                    bad_names = ["projections", "matchups", "odds", "starting lineups", "players", "lineups", "optimizer"]
                    if name.lower() not in bad_names:
                        if sid not in GLOBAL_SLATES[platform] or GLOBAL_SLATES[platform][sid].startswith("Slate "):
                            clean_name = re.sub(r'^(FD|DK)\s+', '', name, flags=re.IGNORECASE).strip()
                            if clean_name:
                                GLOBAL_SLATES[platform][sid] = clean_name

            active_sid = None
            for opt in soup.find_all('option'):
                val = opt.get('value', '')
                if opt.has_attr('selected'): active_sid = val
                add_slate_name(val, opt.get_text(separator=" ", strip=True))
                
            for el in soup.find_all(attrs={"data-slate": True}):
                add_slate_name(el.get("data-slate", ""), el.get_text(separator=" ", strip=True))
                
            for a in soup.find_all('a', href=True):
                match = re.search(r'slate=([a-zA-Z0-9]{5})', a['href'])
                if match:
                    add_slate_name(match.group(1), a.get_text(separator=" ", strip=True))

            html_text = driver.page_source
            matches = re.findall(r'slate=["\']?([a-zA-Z0-9]{5})', html_text)
            for m in matches:
                slate_ids.add(m)
                if m not in GLOBAL_SLATES[platform]:
                    GLOBAL_SLATES[platform][m] = f"Slate {m}"
                
            print(f"Browser found slates: {slate_ids}")
            
            def parse_row(row, plt, sid):
                team_raw = row.get('data-team')
                if not team_raw: return
                team = team_raw.upper()
                if team == 'CHW': team = 'CWS'
                
                raw_name = row.get('data-name', '')
                clean_name = clean_player_name(raw_name)
                
                try:
                    sal = float(row.get('data-salary', '0') or '0')
                    proj = float(row.get('data-ppg_proj') or row.get('data-fpts_proj') or '0')
                    val = float(row.get('data-value_proj', '0') or '0')
                except:
                    sal, proj, val = 0, 0, 0
                    
                # 1. GRAB POSITIONS FIRST
                pos = row.get('data-pos', '').strip()
                pos_alt = row.get('data-pos_alt', '').strip()
                combined_pos = f"{pos}/{pos_alt}" if pos_alt else pos
                
                # 2. DEFINE THE KEY WITH THE _P OR _B SUFFIX
                is_pitcher = 'P' in combined_pos.split('/')
                p_key = f"{team}_{clean_name}_{'P' if is_pitcher else 'B'}"
                
                # 3. INITIALIZE THE DICTIONARY USING THE CORRECT SUFFIXED KEY
                if p_key not in dff_data:
                    dff_data[p_key] = {
                        "salary": 0, "proj": 0.0, "value": 0.0,
                        "dk_salary": 0, "dk_proj": 0.0, "dk_value": 0.0,
                        "fd_slates": {}, "dk_slates": {},
                        "fd_positions": "", "dk_positions": ""
                    }
                
                # 4. SAVE THE DATA
                if plt == 'fanduel' and sal > 0:
                    dff_data[p_key]["fd_positions"] = combined_pos # Save the FD string
                    if sid:
                        dff_data[p_key]["fd_slates"][sid] = {"salary": int(sal), "proj": round(proj, 1), "value": round(val, 2)}
                elif plt == 'draftkings' and sal > 0:
                    dff_data[p_key]["dk_positions"] = combined_pos # Save the DK string
                    if sid:
                        dff_data[p_key]["dk_slates"][sid] = {"salary": int(sal), "proj": round(proj, 1), "value": round(val, 2)}

            if active_sid:
                for row in soup.find_all('tr', class_='projections-listing'):
                    parse_row(row, platform, active_sid)
            
            for sid in slate_ids:
                if sid == active_sid: continue
                try:
                    headers = {'User-Agent': 'Mozilla/5.0', 'X-Requested-With': 'XMLHttpRequest'}
                    res = requests.get(f"{base_url}?slate={sid}", headers=headers, timeout=5)
                    if res.status_code == 200:
                        sub_soup = BeautifulSoup(res.text, 'html.parser')
                        for row in sub_soup.find_all('tr', class_='projections-listing'):
                            parse_row(row, platform, sid)
                except: pass
                
        except Exception as e:
            print(f"Error scraping DFF ({platform}): {e}")
            
    print("Applying Waterfall Logic for Default DFS Stats...")
    def get_slate_priority(slate_name):
        name_lower = slate_name.lower()
        if "all day" in name_lower: return 1
        elif "main" in name_lower: return 2
        elif any(x in name_lower for x in ["showdown", "single game", "captain", "mvp", "@"]): return 4
        else: return 3 
        
    for p_key, p_data in dff_data.items():
        best_fd_sid, best_fd_pri = None, 99
        for sid, stats in p_data["fd_slates"].items():
            pri = get_slate_priority(GLOBAL_SLATES['fanduel'].get(sid, ""))
            if pri < best_fd_pri or (pri == best_fd_pri and stats["proj"] > p_data["fd_slates"].get(best_fd_sid, {}).get("proj", 0)):
                best_fd_pri, best_fd_sid = pri, sid
        if best_fd_sid:
            p_data["salary"], p_data["proj"], p_data["value"] = p_data["fd_slates"][best_fd_sid]["salary"], p_data["fd_slates"][best_fd_sid]["proj"], p_data["fd_slates"][best_fd_sid]["value"]
            
        best_dk_sid, best_dk_pri = None, 99
        for sid, stats in p_data["dk_slates"].items():
            pri = get_slate_priority(GLOBAL_SLATES['draftkings'].get(sid, ""))
            if pri < best_dk_pri or (pri == best_dk_pri and stats["proj"] > p_data["dk_slates"].get(best_dk_sid, {}).get("proj", 0)):
                best_dk_pri, best_dk_sid = pri, sid
        if best_dk_sid:
            p_data["dk_salary"], p_data["dk_proj"], p_data["dk_value"] = p_data["dk_slates"][best_dk_sid]["salary"], p_data["dk_slates"][best_dk_sid]["proj"], p_data["dk_slates"][best_dk_sid]["value"]

    driver.quit() 
    return dff_data

def fetch_bvp(session, batter_id, pitcher_id):
    global API_CALL_TRACKER
    API_CALL_TRACKER["bvp"] += 1
    
    # Ask the API for ALL history
    url = f"https://statsapi.mlb.com/api/v1/people/{batter_id}/stats?stats=vsPlayer&opposingPlayerId={pitcher_id}&group=hitting"
    
    try:
        res = session.get(url, timeout=10).json()
        stats_list = res.get('stats', [])
        
        if stats_list and len(stats_list) > 0:
            splits = stats_list[0].get('splits', [])
            
            if splits:
                total_ab = 0
                total_hits = 0
                total_hr = 0
                total_bb = 0
                total_hbp = 0
                total_sf = 0
                total_2b = 0
                total_3b = 0
                
                # Define exactly which game types we care about
                # R = Regular Season
                # D, L, W, F, P = Various Postseason rounds
                valid_game_types = {'R', 'D', 'L', 'W', 'F', 'P'}
                
                for split in splits:
                    # Check the game type for this specific stint
                    game_type = split.get('gameType', '')
                    
                    # Only add the stats to the total if it's a meaningful game
                    if game_type in valid_game_types:
                        stat = split.get('stat', {})
                        total_ab += stat.get('atBats', 0)
                        total_hits += stat.get('hits', 0)
                        total_hr += stat.get('homeRuns', 0)
                        total_bb += stat.get('baseOnBalls', 0)
                        total_hbp += stat.get('hitByPitch', 0)
                        total_sf += stat.get('sacFlies', 0)
                        total_2b += stat.get('doubles', 0)
                        total_3b += stat.get('triples', 0)
                
                # If they have actual history in meaningful games, calculate!
                if total_ab > 0:
                    avg = total_hits / total_ab
                    
                    obp_denom = total_ab + total_bb + total_hbp + total_sf
                    obp = (total_hits + total_bb + total_hbp) / obp_denom if obp_denom > 0 else 0.0
                    
                    singles = total_hits - (total_2b + total_3b + total_hr)
                    total_bases = singles + (2 * total_2b) + (3 * total_3b) + (4 * total_hr)
                    slg = total_bases / total_ab
                    
                    ops = obp + slg
                    
                    avg_str = f"{avg:.3f}".replace("0.", ".")
                    ops_str = f"{ops:.3f}".replace("0.", ".")
                    
                    return {
                        "ab": total_ab, 
                        "hits": total_hits,
                        "hr": total_hr, 
                        "avg": avg_str, 
                        "ops": ops_str
                    }
                
    except requests.exceptions.RequestException as e:
        print(f"   ⚠️ Network error fetching BvP: {e}")
    except Exception as e:
        print(f"   ⚠️ Unexpected error parsing BvP: {e}")

    # Fallback if no history or error occurs
    return {"ab": 0, "hits": 0, "hr": 0, "avg": "-", "ops": "-"}

def fetch_combined_splits(session, person_id, hand_code, group_type="hitting"):
    global API_CALL_TRACKER
    current_year = datetime.utcnow().year
    years = [current_year - 1, current_year]
    totals = {"ab": 0, "h": 0, "2b": 0, "3b": 0, "hr": 0, "bb": 0, "hbp": 0, "sf": 0, "k": 0}
    
    for year in years:
        API_CALL_TRACKER["splits"] += 1
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

# ==========================================
# --- MAIN SCRIPT LOGIC ---
# ==========================================
def main():
    global API_CALL_TRACKER, GLOBAL_SLATES
    est_tz = zoneinfo.ZoneInfo("America/New_York")
    current_est_time = datetime.now(est_tz)
    
    # --- 🛑 THE DEEP SLEEP CHECK ---
    if 4 <= current_est_time.hour < 8:
        print(f"💤 SLEEP MODE ACTIVE: It is currently {current_est_time.strftime('%I:%M %p')} EST.")
        return

    is_nightly_refresh = current_est_time.hour == 3
    
    if is_nightly_refresh:
        print(f"🧹 NIGHTLY REFRESH ACTIVE: Wiping saved stats to fetch fresh data for the day.")
        
    today_est_str = current_est_time.strftime('%Y-%m-%d')
    
    # --- 🌅 MORNING CUTOFF FOR YESTERDAY'S GAMES ---
    # Only scrape yesterday's games to finalize late West Coast box scores before 6:00 AM EST
    if current_est_time.hour < 6:
        start_date = (current_est_time - timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        start_date = today_est_str
        
    end_date = (current_est_time + timedelta(days=7)).strftime('%Y-%m-%d') 
    
    print(f"🚀 Building Master JSONs using the Daily File as Memory")
    
    session = requests.Session()
    session.headers.update({"User-Agent": "MLBStartingNine-DataBot/1.0"})
    
    ump_cache = load_json(UMPIRES_FILE, {}).get('umpires', {})
    park_cache = load_json(PARKS_FILE, {}).get('parks', {})
    
    API_CALL_TRACKER["odds"] += 1
    try: odds_data = requests.get("https://weathermlb.com/data/odds.json", timeout=10).json().get('odds', [])
    except Exception: odds_data = []

    API_CALL_TRACKER["schedule"] += 1
    sport_ids = get_active_sport_ids()
    schedule_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId={sport_ids}&startDate={start_date}&endDate={end_date}&hydrate=linescore,probablePitcher,lineups,person"
    try: schedule_data = session.get(schedule_url, timeout=15).json()
    except Exception as e:
        print(f"❌ Failed to fetch schedule: {e}")
        return

    master_dates = {}
    
    # --- CROSS-DATE MEMORY CACHES ---
    run_cache_splits = {}
    run_cache_bvp = {}

    for date_item in schedule_data.get('dates', []):
        date_str = date_item['date']
        master_dates[date_str] = []
        
        # CLEAR SLATES PER DATE
        GLOBAL_SLATES = {'fanduel': {}, 'draftkings': {}}
        
        # --- 📖 READ THE DAILY FILE MEMORY (Updated for Dictionary structure) ---
        daily_file_path = os.path.join(DAILY_FILES_DIR, f'games_{date_str}.json')
        daily_memory = {}
        if os.path.exists(daily_file_path):
            existing_data = load_json(daily_file_path, {})
            # Gracefully handle both old Array structures and new Object structures
            existing_games = existing_data.get('games', []) if isinstance(existing_data, dict) else existing_data
            for g in existing_games:
                daily_memory[str(g['gameRaw']['gamePk'])] = g
                
        # --- 🤖 TIME GATES FOR BBM & DFF ---
        target_date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        days_away = (target_date_obj - current_est_time.date()).days
        
        # BBM LOGIC
        needs_bbm_fetch = True
        bbm_projections_for_date = {}
        has_real_games = False
        for g in date_item.get('games', []):
            if g.get('gameType') in ['R', 'F', 'D', 'L', 'W']:
                has_real_games = True
                break
                
        if not has_real_games:
            needs_bbm_fetch = False
            print(f"   [BBM] Skipping {date_str} - Only Spring Training/Exhibition games scheduled.")
            
        if needs_bbm_fetch and daily_memory:
            first_game = list(daily_memory.values())[0]
            last_updated = first_game.get('projectedLineups', {}).get('lastUpdated', 0)
            threshold_seconds = 600 if days_away == 0 else 86400
            if (current_est_time.timestamp() - last_updated) < threshold_seconds:
                needs_bbm_fetch = False

        if days_away == 0 and needs_bbm_fetch:
            all_official = True
            for g in date_item.get('games', []):
                state = g.get('status', {}).get('abstractGameState', '')
                if state not in ['Final', 'Postponed', 'Cancelled']:
                    a_len = len(g.get('lineups', {}).get('awayPlayers', []))
                    h_len = len(g.get('lineups', {}).get('homePlayers', []))
                    if a_len == 0 or h_len == 0:
                        all_official = False
                        break
            if all_official: needs_bbm_fetch = False

        if needs_bbm_fetch:
            print(f"   [BBM] Fetching fresh projected lineups for {date_str} (Days Away: {days_away})...")
            bbm_projections_for_date = get_bbm_projected_lineups(date_str)
            time.sleep(1) 

        # DFF LOGIC
        needs_dff_fetch = False
        if days_away == 0: needs_dff_fetch = True 
        elif days_away == 1 and current_est_time.hour >= 23: needs_dff_fetch = True 
            
        dff_projections = {}
        has_valid_dfs = False
        if needs_dff_fetch:
            dff_projections = scrape_dff_projections(date_str)
            has_valid_dfs = len(dff_projections) > 0
            if not has_valid_dfs:
                print(f"⚠️ Safety Valve Triggered: DFF scrape for {date_str} failed or was empty. Skipping injection.")
                
        def inject_dfs(player_obj, team_abbr, is_pitcher_slot=False):
            if not player_obj: return
            
            # Safely grab the name whether it's an MLB API object (fullName) or BBM object (name)
            raw_name = player_obj.get('fullName', player_obj.get('name', ''))
            if not raw_name: return
            
            clean_name = clean_player_name(raw_name)
            
            # --- OHTANI FIX: PRIORITIZE THE CORRECT SUFFIX ---
            suffixes = ['_P', '_B'] if is_pitcher_slot else ['_B', '_P']
            
            dff_p = None
            for suffix in suffixes:
                p_key = f"{team_abbr}_{clean_name}{suffix}"
                if p_key in dff_projections:
                    dff_p = dff_projections[p_key]
                    break
            
            if not dff_p:
                parts = clean_name.split()
                if len(parts) >= 2:
                    for suffix in suffixes:
                        for d_key, d_val in dff_projections.items():
                            if d_key.startswith(f"{team_abbr}_") and d_key.endswith(suffix):
                                d_name = d_key.split('_')[1]
                                if parts[-1] in d_name and d_name.startswith(parts[0][0]):
                                    dff_p = d_val
                                    break
                        if dff_p: break
            
            if dff_p and (dff_p.get('salary', 0) > 0 or dff_p.get('dk_salary', 0) > 0):
                player_obj['salary'], player_obj['proj'], player_obj['value'] = dff_p.get('salary', 0), dff_p.get('proj', 0), dff_p.get('value', 0)
                player_obj['dk_salary'], player_obj['dk_proj'], player_obj['dk_value'] = dff_p.get('dk_salary', 0), dff_p.get('dk_proj', 0), dff_p.get('dk_value', 0)
                player_obj['fd_slates'], player_obj['dk_slates'] = dff_p.get('fd_slates', {}), dff_p.get('dk_slates', {})
                
                # --- NEW: PUSH POSITIONS TO FINAL JSON ---
                player_obj['fd_positions'] = dff_p.get('fd_positions', '')
                player_obj['dk_positions'] = dff_p.get('dk_positions', '')

        # --- PROCESS GAMES ---
        for game in date_item.get('games', []):
            game_pk = str(game['gamePk'])
            
            existing_game_state = daily_memory.get(game_pk, {})
            
            # 🌙 NIGHTLY REFRESH LOGIC
            if is_nightly_refresh and date_str >= today_est_str:
                game_deep_stats = {}
                lineup_tracking = {'away': {}, 'home': {}}
            else:
                game_deep_stats = existing_game_state.get('deepStats', {})
                lineup_tracking = existing_game_state.get('lineupTracking', {'away': {}, 'home': {}})
                
            game_positions = existing_game_state.get('gamePositions', {})
            lineup_handedness = existing_game_state.get('lineupHandedness', {})
            hp_umpire = existing_game_state.get('hpUmpire', "TBD")
            ump_stats = ump_cache.get(hp_umpire) if hp_umpire != "TBD" else None
            
            teams = game.get('teams', {})
            away_team_name = teams.get('away', {}).get('team', {}).get('name', '')
            home_team_name = teams.get('home', {}).get('team', {}).get('name', '')
            away_team_id = str(teams.get('away', {}).get('team', {}).get('id', ''))
            home_team_id = str(teams.get('home', {}).get('team', {}).get('id', ''))
            game_num = str(game.get('gameNumber', 1))
            
            game_odds = None
            game_time_ms = datetime.strptime(game['gameDate'], "%Y-%m-%dT%H:%M:%SZ").timestamp() * 1000
            
            def parse_odds_time(date_str):
                if date_str.endswith('Z'): date_str = date_str[:-1]
                if len(date_str.split(':')) == 2: date_str += ":00"
                return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S").timestamp() * 1000
                
            potential_odds = [o for o in odds_data if o['home_team'] == home_team_name and o['away_team'] == away_team_name]
            if potential_odds:
                game_odds = sorted(potential_odds, key=lambda o: abs(parse_odds_time(o['commence_time']) - game_time_ms))[0]

            away_starter = teams.get('away', {}).get('probablePitcher')
            home_starter = teams.get('home', {}).get('probablePitcher')
            away_starter_id = str(away_starter.get('id')) if away_starter else None
            home_starter_id = str(home_starter.get('id')) if home_starter else None
            
            for p_id, p_data in [(away_starter_id, away_starter), (home_starter_id, home_starter)]:
                if p_id and p_id not in game_deep_stats:
                    # Check our script memory first
                    if p_id not in run_cache_splits:
                        print(f"   [NEW] Fetching Pitcher Splits for {p_data['fullName']}...")
                        run_cache_splits[p_id] = {
                            "split_vL": fetch_combined_splits(session, p_id, 'vl', group_type="pitching"),
                            "split_vR": fetch_combined_splits(session, p_id, 'vr', group_type="pitching")
                        }
                    
                    game_deep_stats[p_id] = {
                        "name": p_data['fullName'], 
                        "is_pitcher": True,
                        "split_vL": run_cache_splits[p_id]["split_vL"],
                        "split_vR": run_cache_splits[p_id]["split_vR"]
                    }

            # --- CRITICAL FIX: BULK FETCH HANDEDNESS FOR ALL PLAYERS ---
            lineups = game.get('lineups', {})
            away_lineup = lineups.get('awayPlayers', [])
            home_lineup = lineups.get('homePlayers', [])
            
            # --- LINEUP STATE TRACKER (For Late Swaps) ---
            def get_lineup_hash(players_array):
                return "-".join([str(p['id']) for p in players_array[:9]]) if players_array else ""

            for side, lineup in [('away', away_lineup), ('home', home_lineup)]:
                if len(lineup) > 0:
                    current_hash = get_lineup_hash(lineup)
                    tracking = lineup_tracking.get(side, {})
                    
                    if not tracking.get('hash'):
                        tracking['hash'] = current_hash
                        tracking['status'] = "OFFICIAL"
                        tracking['officialAt'] = current_est_time.strftime("%I:%M %p ET")
                    elif tracking.get('hash') != current_hash:
                        tracking['hash'] = current_hash
                        tracking['status'] = "MODIFIED"
                        tracking['modifiedAt'] = current_est_time.strftime("%I:%M %p ET")
                        
                    lineup_tracking[side] = tracking
            # ---------------------------------------------
            
            # 1. Safely grab projected lineups whether fresh from BBM or from memory
            # 1. Safely grab projected lineups whether fresh from BBM or from memory
            away_proj = []
            home_proj = []
            
            if needs_bbm_fetch:
                away_proj = (bbm_projections_for_date.get(f"{away_team_id}_{game_num}") or {}).get('battingOrder', [])
                home_proj = (bbm_projections_for_date.get(f"{home_team_id}_{game_num}") or {}).get('battingOrder', [])
            else:
                proj_lineups = existing_game_state.get('projectedLineups') or {}
                away_proj = (proj_lineups.get('away') or {}).get('battingOrder', [])
                home_proj = (proj_lineups.get('home') or {}).get('battingOrder', [])

            # Collect all known player IDs for this game (Official + Projected)
            all_pids = set()
            for p in away_lineup + home_lineup + away_proj + home_proj:
                if 'id' in p: all_pids.add(str(p['id']))
            
            # Bulk fetch the missing handedness from MLB People API
            if all_pids:
                try:
                    people_data = session.get(f"https://statsapi.mlb.com/api/v1/people?personIds={','.join(all_pids)}", timeout=5).json()
                    for person in people_data.get('people', []):
                        pid = str(person['id'])
                        bat_side = person.get('batSide', {}).get('code')
                        if bat_side:
                            lineup_handedness[pid] = bat_side
                except Exception:
                    pass

            # Ensure Pitchers get their handedness assigned too
            if away_starter and away_starter.get('pitchHand'):
                lineup_handedness[str(away_starter['id'])] = away_starter['pitchHand'].get('code')
            if home_starter and home_starter.get('pitchHand'):
                lineup_handedness[str(home_starter['id'])] = home_starter['pitchHand'].get('code')
            # -------------------------------------------------------------------------------------

            # 2. Combine Official and Projected lists to fetch Deep Stats
            combined_away_batters = away_lineup + away_proj
            combined_home_batters = home_lineup + home_proj
            

            # --- AWAY BATTERS VS HOME STARTER ---
            for batter in combined_away_batters:
                if 'id' not in batter: continue
                batter_id = str(batter['id'])
                batter_name = batter.get('fullName', batter.get('name', 'Unknown'))
                
                # Initialize the player if they are totally new to memory
                if batter_id not in game_deep_stats:
                    game_deep_stats[batter_id] = {"name": batter_name}
                    
                # 1. Fetch Splits (Only if missing from memory)
                if "split_vL" not in game_deep_stats[batter_id]:
                    if batter_id not in run_cache_splits:
                        run_cache_splits[batter_id] = {
                            "split_vL": fetch_combined_splits(session, batter_id, 'vl'), 
                            "split_vR": fetch_combined_splits(session, batter_id, 'vr')
                        }
                    game_deep_stats[batter_id]["split_vL"] = run_cache_splits[batter_id]["split_vL"]
                    game_deep_stats[batter_id]["split_vR"] = run_cache_splits[batter_id]["split_vR"]
                    
                # 2. Fetch BvP (Refetch automatically if the Pitcher changed)
                current_bvp = game_deep_stats[batter_id].get("bvp", {})
                saved_pitcher_id = current_bvp.get("pitcher_id")
                
                if home_starter_id and saved_pitcher_id != home_starter_id:
                    bvp_key = f"{batter_id}_{home_starter_id}"
                    if bvp_key not in run_cache_bvp:
                        run_cache_bvp[bvp_key] = fetch_bvp(session, batter_id, home_starter_id)
                    
                    # Copy the stats and stamp the new pitcher's ID into memory
                    bvp_stats = dict(run_cache_bvp[bvp_key])
                    bvp_stats["pitcher_id"] = home_starter_id
                    game_deep_stats[batter_id]["bvp"] = bvp_stats
                    
                elif not home_starter_id and "bvp" not in game_deep_stats[batter_id]:
                    game_deep_stats[batter_id]["bvp"] = {"ab": 0, "hits": 0, "hr": 0, "avg": "-", "ops": "-"}

            # --- HOME BATTERS VS AWAY STARTER ---
            for batter in combined_home_batters:
                if 'id' not in batter: continue
                batter_id = str(batter['id'])
                batter_name = batter.get('fullName', batter.get('name', 'Unknown'))
                
                # Initialize the player if they are totally new to memory
                if batter_id not in game_deep_stats:
                    game_deep_stats[batter_id] = {"name": batter_name}
                    
                # 1. Fetch Splits (Only if missing from memory)
                if "split_vL" not in game_deep_stats[batter_id]:
                    if batter_id not in run_cache_splits:
                        run_cache_splits[batter_id] = {
                            "split_vL": fetch_combined_splits(session, batter_id, 'vl'), 
                            "split_vR": fetch_combined_splits(session, batter_id, 'vr')
                        }
                    game_deep_stats[batter_id]["split_vL"] = run_cache_splits[batter_id]["split_vL"]
                    game_deep_stats[batter_id]["split_vR"] = run_cache_splits[batter_id]["split_vR"]
                    
                # 2. Fetch BvP (Refetch automatically if the Pitcher changed)
                current_bvp = game_deep_stats[batter_id].get("bvp", {})
                saved_pitcher_id = current_bvp.get("pitcher_id")
                
                if away_starter_id and saved_pitcher_id != away_starter_id:
                    bvp_key = f"{batter_id}_{away_starter_id}"
                    if bvp_key not in run_cache_bvp:
                        run_cache_bvp[bvp_key] = fetch_bvp(session, batter_id, away_starter_id)
                    
                    # Copy the stats and stamp the new pitcher's ID into memory
                    bvp_stats = dict(run_cache_bvp[bvp_key])
                    bvp_stats["pitcher_id"] = away_starter_id
                    game_deep_stats[batter_id]["bvp"] = bvp_stats
                    
                elif not away_starter_id and "bvp" not in game_deep_stats[batter_id]:
                    game_deep_stats[batter_id]["bvp"] = {"ab": 0, "hits": 0, "hr": 0, "avg": "-", "ops": "-"}

            game_state = game.get('status', {}).get('abstractGameState', '')
            needs_live_feed = False
            
            if date_str == today_est_str and (len(away_lineup) > 0 or len(home_lineup) > 0):
                if game_state != 'Final': needs_live_feed = True
                elif hp_umpire == "TBD" or not game_positions: needs_live_feed = True

            if needs_live_feed:
                try:
                    API_CALL_TRACKER["live_feed"] += 1
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
                        
                        # Ask for TODAY'S position first!
                        if p_val.get('position') and p_val['position'].get('abbreviation'): 
                            game_positions[pid] = p_val['position'].get('abbreviation')
                        elif p_val.get('allPositions'): 
                            game_positions[pid] = p_val['allPositions'][0].get('abbreviation')
                            
                        if p_val.get('person', {}).get('batSide'): lineup_handedness[pid] = p_val['person']['batSide'].get('code')
                except Exception: pass
                
            if needs_bbm_fetch:
                game_projected_lineups = {
                    "lastUpdated": current_est_time.timestamp(),
                    "away": bbm_projections_for_date.get(f"{away_team_id}_{game_num}") or {},
                    "home": bbm_projections_for_date.get(f"{home_team_id}_{game_num}") or {}
                }
            else:
                game_projected_lineups = existing_game_state.get('projectedLineups', {})
                if "lastUpdated" not in game_projected_lineups:
                    game_projected_lineups["lastUpdated"] = current_est_time.timestamp()

            # INJECT DFS STATS
            if has_valid_dfs:
                away_abbr = get_dff_team_abbr(away_team_name)
                home_abbr = get_dff_team_abbr(home_team_name)
                
                # 1. Inject into Projected Lineups (Baseball Monster)
                if game_projected_lineups.get("away"):
                    inject_dfs(game_projected_lineups["away"].get("startingPitcher"), away_abbr, is_pitcher_slot=True)
                    for batter in game_projected_lineups["away"].get("battingOrder", []): inject_dfs(batter, away_abbr, is_pitcher_slot=False)
                if game_projected_lineups.get("home"):
                    inject_dfs(game_projected_lineups["home"].get("startingPitcher"), home_abbr, is_pitcher_slot=True)
                    for batter in game_projected_lineups["home"].get("battingOrder", []): inject_dfs(batter, home_abbr, is_pitcher_slot=False)
                    
                # 2. Inject into Official Lineups (MLB API) to catch surprise starters
                for batter in game.get('lineups', {}).get('awayPlayers', []):
                    inject_dfs(batter, away_abbr, is_pitcher_slot=False)
                for batter in game.get('lineups', {}).get('homePlayers', []):
                    inject_dfs(batter, home_abbr, is_pitcher_slot=False)

            master_dates[date_str].append({
                "gameRaw": game,
                "projectedLineups": game_projected_lineups,
                "odds": game_odds,
                "lineupTracking": lineup_tracking,
                "lineupHandedness": lineup_handedness,
                "gamePositions": game_positions,
                "deepStats": game_deep_stats,
                "hpUmpire": hp_umpire,
                "umpStats": ump_stats,
                "parkStats": park_cache.get(game.get('venue', {}).get('name'))
            })

        # Save Daily File
        formatted_slates = {
            "fanduel": [{"id": k, "name": v} for k, v in GLOBAL_SLATES['fanduel'].items()],
            "draftkings": [{"id": k, "name": v} for k, v in GLOBAL_SLATES['draftkings'].items()]
        }

        # ALWAYS save as the new Object structure to standardize the Frontend
        final_output = {
            "last_updated": current_est_time.strftime("%b %d, %I:%M %p ET"),
            "slates": formatted_slates if has_valid_dfs else {"fanduel": [], "draftkings": []},
            "games": master_dates[date_str]
        }

        daily_file = os.path.join(DAILY_FILES_DIR, f'games_{date_str}.json')
        save_json(daily_file, final_output)
        print(f"✅ Created/Updated {daily_file} with {len(master_dates[date_str])} games.")

    # --- PRINT API METRICS ---
    total_calls = sum(API_CALL_TRACKER.values())
    print("\n" + "="*40)
    print(f"📊 API CALL SUMMARY: {total_calls} Total Requests")
    print("="*40)
    for k, v in API_CALL_TRACKER.items(): print(f"  - {k.replace('_', ' ').title()}: {v}")
    print("="*40 + "\n")

if __name__ == "__main__":
    main()
