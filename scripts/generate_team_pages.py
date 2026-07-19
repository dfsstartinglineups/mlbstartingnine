import os
import json
import re
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ==========================================
# 1. DICTIONARIES & THEMES
# ==========================================
MLB_TEAMS = [
    {"id": 110, "slug": "baltimore-orioles", "name": "Baltimore Orioles", "abbr": "bal"},
    {"id": 111, "slug": "boston-red-sox", "name": "Boston Red Sox", "abbr": "bos"},
    {"id": 147, "slug": "new-york-yankees", "name": "New York Yankees", "abbr": "nyy"},
    {"id": 139, "slug": "tampa-bay-rays", "name": "Tampa Bay Rays", "abbr": "tb"},
    {"id": 141, "slug": "toronto-blue-jays", "name": "Toronto Blue Jays", "abbr": "tor"},
    {"id": 145, "slug": "chicago-white-sox", "name": "Chicago White Sox", "abbr": "chw"},
    {"id": 114, "slug": "cleveland-guardians", "name": "Cleveland Guardians", "abbr": "cle"},
    {"id": 116, "slug": "detroit-tigers", "name": "Detroit Tigers", "abbr": "det"},
    {"id": 118, "slug": "kansas-city-royals", "name": "Kansas City Royals", "abbr": "kc"},
    {"id": 142, "slug": "minnesota-twins", "name": "Minnesota Twins", "abbr": "min"},
    {"id": 117, "slug": "houston-astros", "name": "Houston Astros", "abbr": "hou"},
    {"id": 108, "slug": "los-angeles-angels", "name": "Los Angeles Angels", "abbr": "laa"},
    {"id": 133, "slug": "athletics", "name": "Athletics", "abbr": "oak"},
    {"id": 136, "slug": "seattle-mariners", "name": "Seattle Mariners", "abbr": "sea"},
    {"id": 140, "slug": "texas-rangers", "name": "Texas Rangers", "abbr": "tex"},
    {"id": 144, "slug": "atlanta-braves", "name": "Atlanta Braves", "abbr": "atl"},
    {"id": 146, "slug": "miami-marlins", "name": "Miami Marlins", "abbr": "mia"},
    {"id": 121, "slug": "new-york-mets", "name": "New York Mets", "abbr": "nym"},
    {"id": 143, "slug": "philadelphia-phillies", "name": "Philadelphia Phillies", "abbr": "phi"},
    {"id": 120, "slug": "washington-nationals", "name": "Washington Nationals", "abbr": "wsh"},
    {"id": 112, "slug": "chicago-cubs", "name": "Chicago Cubs", "abbr": "chc"},
    {"id": 113, "slug": "cincinnati-reds", "name": "Cincinnati Reds", "abbr": "cin"},
    {"id": 158, "slug": "milwaukee-brewers", "name": "Milwaukee Brewers", "abbr": "mil"},
    {"id": 134, "slug": "pittsburgh-pirates", "name": "Pittsburgh Pirates", "abbr": "pit"},
    {"id": 138, "slug": "st-louis-cardinals", "name": "St. Louis Cardinals", "abbr": "stl"},
    {"id": 109, "slug": "arizona-diamondbacks", "name": "Arizona Diamondbacks", "abbr": "ari"},
    {"id": 115, "slug": "colorado-rockies", "name": "Colorado Rockies", "abbr": "col"},
    {"id": 119, "slug": "los-angeles-dodgers", "name": "Los Angeles Dodgers", "abbr": "lad"},
    {"id": 135, "slug": "san-diego-padres", "name": "San Diego Padres", "abbr": "sd"},
    {"id": 137, "slug": "san-francisco-giants", "name": "San Francisco Giants", "abbr": "sf"}
]

TEAM_THEMES = {
    108: {"paperBg": "#f4f1ea", "paperLine": "rgba(186, 0, 33, 0.35)", "markerInk": "#ba0021"},
    119: {"paperBg": "#f4f1ea", "paperLine": "rgba(0, 90, 156, 0.35)", "markerInk": "#005a9c"},
    # Add other themes from your JS file here...
}

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def slugify(text):
    if not text: return ""
    text = str(text).lower()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[\s-]+', '-', text).strip('-')

def get_est_date_string(offset_days=0):
    tz = ZoneInfo("America/New_York")
    target_date = datetime.now(tz) + timedelta(days=offset_days)
    return target_date.strftime("%Y-%m-%d")

def get_player_slug(player_id, default_name, player_db):
    key = f"ID{player_id}"
    if key in player_db and "slug" in player_db[key]:
        return player_db[key]["slug"]
    return slugify(default_name)

def load_json_safe(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def find_game_in_slate(slate_data, team_id):
    if not slate_data or "games" not in slate_data:
        return None, None, False, 1
        
    matching_games = []
    for g in slate_data.get("games", []):
        raw = g.get("gameRaw", {})
        teams = raw.get("teams", {})
        if teams.get("away", {}).get("team", {}).get("id") == team_id or \
           teams.get("home", {}).get("team", {}).get("id") == team_id:
            matching_games.append(g)
            
    if not matching_games:
        return None, None, False, 1
        
    matching_games.sort(key=lambda x: x.get("gameRaw", {}).get("gameNumber", 1))
    
    is_double_header = len(matching_games) > 1
    selected = matching_games[0]
    
    # Simple resolution: grab first active game
    if is_double_header:
        for m in matching_games:
            state = m.get("gameRaw", {}).get("status", {}).get("abstractGameState", "")
            if state in ["Live", "In Progress", "Preview", "Scheduled"]:
                selected = m
                break
                
    raw = selected.get("gameRaw", {})
    target_side = 'away' if raw.get("teams", {}).get("away", {}).get("team", {}).get("id") == team_id else 'home'
    game_num = raw.get("gameNumber", 1)
    
    return selected, target_side, is_double_header, game_num

# ==========================================
# 3. HTML GENERATOR
# ==========================================
def generate_team_html(team, player_db, daily_slates):
    team_id = team["id"]
    theme = TEAM_THEMES.get(team_id, {"paperBg": "#f4f1ea", "paperLine": "rgba(0,0,0,0.2)", "markerInk": "#111"})
    
    target_game = None
    target_side = None
    is_future = False
    is_double_header = False
    game_num = 1
    
    # Check today, tomorrow, next day
    for i in range(3):
        slate = daily_slates.get(i, {})
        target_game, target_side, is_double_header, game_num = find_game_in_slate(slate, team_id)
        if target_game:
            if i > 0: is_future = True
            break
            
    capture_area_html = ""
    if not target_game:
        # Off-day fallback
        capture_area_html = f"""
        <div style="max-width: 550px; margin: 30px auto; background: {theme['paperBg']}; border: 2px dashed {theme['markerInk']}; border-radius: 10px; padding: 35px 20px; text-align: center; color: #222;">
            <h1 style="color: {theme['markerInk']};">NO GAME SCHEDULED</h1>
            <p>The {team['name']} do not have a game scheduled in the next 48 hours.</p>
        </div>"""
    else:
        # Render the full scorecard and batting order HTML here based on target_game
        # (This translates the JS string building directly into Python string building)
        raw = target_game.get("gameRaw", {})
        status = target_game.get("lineupTracking", {}).get(target_side, {}).get("status", "NONE")
        
        # Build the HTML block for the batters...
        capture_area_html = f"""
        <div style="max-width: 580px; margin: 15px auto; background: {theme['paperBg']}; border: 1px solid #bbb; border-radius: 10px; padding: 18px 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.7);">
            <h1 style="color: {theme['markerInk']}; text-transform: uppercase;">{team['name']}</h1>
            <div style="font-weight: bold; margin-bottom: 10px;">Status: {status}</div>
            <!-- Additional Python-rendered batters loop goes here -->
        </div>"""

    # Assemble complete HTML document
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{team['name']} Starting Lineup Today</title>
    <link rel="stylesheet" href="../../styles.css">
</head>
<body class="dark-theme">
    <div id="main-wrapper">
        <div id="header-container">
            <!-- Statically generated header -->
            <a href="/">← Back to Slate</a>
        </div>
        <div id="capture-area">
            {capture_area_html}
        </div>
        <div id="public-analytics-section">
            <!-- Statically generated analytics -->
        </div>
    </div>
</body>
</html>"""
    return html_content

# ==========================================
# 4. CONDITIONAL BUILD EXECUTION
# ==========================================
def main():
    print("⚾ Starting MLB Team Pages Generator (Static SSG)...")
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lineups")
    os.makedirs(base_dir, exist_ok=True)
    
    # Load Master Data once
    player_db = load_json_safe("data/player_master_data.json")
    
    # Pre-load 3 days of slates
    daily_slates = {
        0: load_json_safe(f"data/daily_files/games_{get_est_date_string(0)}.json"),
        1: load_json_safe(f"data/daily_files/games_{get_est_date_string(1)}.json"),
        2: load_json_safe(f"data/daily_files/games_{get_est_date_string(2)}.json")
    }

    updated_files = 0
    
    for team in MLB_TEAMS:
        team_dir = os.path.join(base_dir, team["slug"])
        os.makedirs(team_dir, exist_ok=True)
        file_path = os.path.join(team_dir, "index.html")
        
        # 1. Generate the fresh HTML in memory
        new_html = generate_team_html(team, player_db, daily_slates)
        
        # 2. Read existing HTML to compare
        existing_html = ""
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                existing_html = f.read()
                
        # 3. Only write if the state of the lineup/game has changed
        if new_html != existing_html:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_html)
            print(f"🔄 Updated: /lineups/{team['slug']}/index.html")
            updated_files += 1
            
    print(f"\n🚀 Build complete. {updated_files} team pages were actively modified.")

if __name__ == "__main__":
    main()
