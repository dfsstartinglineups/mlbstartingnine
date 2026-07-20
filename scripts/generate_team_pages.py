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
    108: {"name": "Angels", "paperBg": "#f4f1ea", "paperLine": "rgba(186, 0, 33, 0.35)", "markerInk": "#ba0021"},
    109: {"name": "Diamondbacks", "paperBg": "#f4f1ea", "paperLine": "rgba(167, 25, 48, 0.35)", "markerInk": "#a71930"},
    110: {"name": "Orioles", "paperBg": "#f4f1ea", "paperLine": "rgba(223, 70, 1, 0.35)", "markerInk": "#df4601"},
    111: {"name": "Red Sox", "paperBg": "#f4f1ea", "paperLine": "rgba(189, 48, 57, 0.35)", "markerInk": "#bd3039"},
    112: {"name": "Cubs", "paperBg": "#f4f1ea", "paperLine": "rgba(14, 51, 134, 0.35)", "markerInk": "#0e3386"},
    113: {"name": "Reds", "paperBg": "#f4f1ea", "paperLine": "rgba(198, 1, 31, 0.35)", "markerInk": "#c6011f"},
    114: {"name": "Guardians", "paperBg": "#f4f1ea", "paperLine": "rgba(227, 25, 55, 0.35)", "markerInk": "#e31937"},
    115: {"name": "Rockies", "paperBg": "#f4f1ea", "paperLine": "rgba(51, 0, 111, 0.35)", "markerInk": "#33006f"},
    116: {"name": "Tigers", "paperBg": "#f4f1ea", "paperLine": "rgba(12, 35, 64, 0.35)", "markerInk": "#0c2340"},
    117: {"name": "Astros", "paperBg": "#f4f1ea", "paperLine": "rgba(235, 110, 31, 0.35)", "markerInk": "#eb6e1f"},
    118: {"name": "Royals", "paperBg": "#f4f1ea", "paperLine": "rgba(0, 70, 135, 0.35)", "markerInk": "#004687"},
    119: {"name": "Dodgers", "paperBg": "#f4f1ea", "paperLine": "rgba(0, 90, 156, 0.35)", "markerInk": "#005a9c"},
    120: {"name": "Nationals", "paperBg": "#f4f1ea", "paperLine": "rgba(171, 0, 3, 0.35)", "markerInk": "#ab0003"},
    121: {"name": "Mets", "paperBg": "#f4f1ea", "paperLine": "rgba(255, 89, 16, 0.35)", "markerInk": "#ff5910"},
    133: {"name": "Athletics", "paperBg": "#f4f1ea", "paperLine": "rgba(0, 56, 49, 0.35)", "markerInk": "#003831"},
    134: {"name": "Pirates", "paperBg": "#f4f1ea", "paperLine": "rgba(253, 184, 39, 0.45)", "markerInk": "#fdb827"},
    135: {"name": "Padres", "paperBg": "#f4f1ea", "paperLine": "rgba(47, 36, 29, 0.35)", "markerInk": "#2f241d"},
    136: {"name": "Mariners", "paperBg": "#f4f1ea", "paperLine": "rgba(0, 92, 92, 0.35)", "markerInk": "#005c5c"},
    137: {"name": "Giants", "paperBg": "#f4f1ea", "paperLine": "rgba(253, 90, 30, 0.35)", "markerInk": "#fd5a1e"},
    138: {"name": "Cardinals", "paperBg": "#f4f1ea", "paperLine": "rgba(196, 30, 58, 0.35)", "markerInk": "#c41e3a"},
    139: {"name": "Rays", "paperBg": "#f4f1ea", "paperLine": "rgba(9, 44, 87, 0.35)", "markerInk": "#092c57"},
    140: {"name": "Rangers", "paperBg": "#f4f1ea", "paperLine": "rgba(0, 50, 120, 0.35)", "markerInk": "#003278"},
    141: {"name": "Blue Jays", "paperBg": "#f4f1ea", "paperLine": "rgba(19, 74, 142, 0.35)", "markerInk": "#134a8e"},
    142: {"name": "Twins", "paperBg": "#f4f1ea", "paperLine": "rgba(0, 43, 92, 0.35)", "markerInk": "#002b5c"},
    143: {"name": "Phillies", "paperBg": "#f4f1ea", "paperLine": "rgba(232, 24, 40, 0.35)", "markerInk": "#e81828"},
    144: {"name": "Braves", "paperBg": "#f4f1ea", "paperLine": "rgba(206, 17, 65, 0.35)", "markerInk": "#ce1141"},
    145: {"name": "White Sox", "paperBg": "#f4f1ea", "paperLine": "rgba(39, 37, 31, 0.35)", "markerInk": "#27251f"},
    146: {"name": "Marlins", "paperBg": "#f4f1ea", "paperLine": "rgba(0, 163, 224, 0.35)", "markerInk": "#00a3e0"},
    147: {"name": "Yankees", "paperBg": "#f4f1ea", "paperLine": "rgba(12, 35, 64, 0.35)", "markerInk": "#0c2340"}
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
    now_est = datetime.now(tz)
    
    # 🛑 3:00 AM EST Crossover Window
    # If it's between midnight and 2:59:59 AM Eastern, operational today is pushed back 1 day
    if now_est.hour < 3:
        operational_today = now_est - timedelta(days=1)
    else:
        operational_today = now_est
        
    # Calculate the targeted day offset relative to the operational window baseline
    target_date = operational_today + timedelta(days=offset_days)
    return target_date.strftime("%Y-%m-%d")

def get_player_slug(player_id, default_name, player_db):
    key = f"ID{player_id}"
    if key in player_db and "slug" in player_db[key]:
        return player_db[key]["slug"]
    return slugify(default_name)

def get_headshot_url(person_id):
    if not person_id: return "https://www.mlbstatic.com/team-logos/100.svg"
    return f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/{person_id}/headshot/67/current"

def load_json_safe(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f: return json.load(f)
    except Exception:
        return {}

def get_slug_from_id(team_id):
    for t in MLB_TEAMS:
        if t["id"] == team_id: return t["slug"]
    return "los-angeles-dodgers"

def get_short_team_name(full_name, team_name_node):
    short = team_name_node or full_name.split(' ')[-1]
    if 'Red Sox' in full_name: short = 'Red Sox'
    if 'White Sox' in full_name: short = 'White Sox'
    if 'Blue Jays' in full_name: short = 'Blue Jays'
    if short == 'Diamondbacks': short = 'D-Backs'
    return short.upper()

def get_safe_pitcher(game_data, side_key, game_num):
    raw = game_data.get("gameRaw", {})
    proj = game_data.get("projectedLineups", {}).get(side_key, {}).get("startingPitcher", {})
    official = raw.get("teams", {}).get(side_key, {}).get("probablePitcher", {})
    hand_map = game_data.get("lineupHandedness", {})

    if official and official.get("fullName"):
        h = hand_map.get(str(official.get("id"))) or (proj.get("hand", "") if proj.get("id") == official.get("id") else "")
        return {"id": official.get("id"), "name": official.get("fullName"), "hand": h}
        
    if game_num == 1 and proj and proj.get("name"):
        h = hand_map.get(str(proj.get("id"))) or proj.get("hand", "")
        return {"id": proj.get("id"), "name": proj.get("name"), "hand": h}
        
    return {"id": None, "name": "TBD / Bullpen Game", "hand": ""}

def find_game_in_slate(slate_data, team_id):
    if not slate_data or "games" not in slate_data: return None, None, False, 1
        
    matching_games = []
    for g in slate_data.get("games", []):
        raw = g.get("gameRaw", {})
        teams = raw.get("teams", {})
        if teams.get("away", {}).get("team", {}).get("id") == team_id or teams.get("home", {}).get("team", {}).get("id") == team_id:
            matching_games.append(g)
            
    if not matching_games: return None, None, False, 1
        
    matching_games.sort(key=lambda x: x.get("gameRaw", {}).get("gameNumber", 1))
    is_double_header = len(matching_games) > 1
    
    active_games = [m for m in matching_games if "Postponed" not in m.get("gameRaw", {}).get("status", {}).get("abstractGameState", "") and "Postponed" not in m.get("gameRaw", {}).get("status", {}).get("detailedState", "") and m.get("gameRaw", {}).get("status", {}).get("statusCode") != "C"]
    
    if active_games:
        selected = next((m for m in active_games if m.get("gameRaw", {}).get("status", {}).get("abstractGameState") in ["Live", "In Progress"]), None)
        if not selected:
            selected = next((m for m in active_games if m.get("gameRaw", {}).get("status", {}).get("abstractGameState") in ["Preview", "Scheduled"]), None)
        if not selected:
            selected = active_games[-1]
    else:
        selected = matching_games[0]
                
    raw = selected.get("gameRaw", {})
    target_side = 'away' if raw.get("teams", {}).get("away", {}).get("team", {}).get("id") == team_id else 'home'
    game_num = raw.get("gameNumber", 1)
    
    return selected, target_side, is_double_header, game_num

# ==========================================
# 3. HTML GENERATORS
# ==========================================
def render_analytics_section(target_game, target_side, batters, game_num, player_db):
    if not target_game or not target_game.get("deepStats"): return ""
    
    deep_stats = target_game.get("deepStats") or {}
    ump_stats = target_game.get("umpStats") or {}
    park_stats = target_game.get("parkStats") or {}
    
    opp_side = 'home' if target_side == 'away' else 'away'
    opp_pitcher = get_safe_pitcher(target_game, opp_side, game_num)
    p_stats = deep_stats.get(str(opp_pitcher["id"]), {}) if opp_pitcher["id"] else None
    pitcher_hand = opp_pitcher["hand"] or 'R'
    
    table_css = """
    <style>
        .stat-container { max-width: 580px; width: 94%; margin: 10px auto 40px auto; font-family: 'Montserrat', sans-serif; }
        .stat-card { background: #1a1d24; border: 1px solid #2d323b; border-radius: 10px; margin-bottom: 25px; overflow: hidden; box-shadow: 0 8px 20px rgba(0,0,0,0.4); }
        .stat-header { background: #22262e; padding: 12px 15px; border-bottom: 2px solid var(--marker-ink, #444); color: #fff; font-weight: 700; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; display: flex; align-items: center; justify-content: space-between; }
        .stat-table { width: 100%; border-collapse: collapse; color: #ddd; font-size: 12px; }
        .stat-table th { background: #15171c; padding: 10px; text-align: center; color: #8892a3; font-weight: 600; text-transform: uppercase; font-size: 10px; border-bottom: 1px solid #2d323b; }
        .stat-table th:first-child, .stat-table td:first-child { text-align: left; padding-left: 15px; font-weight: 600; color: #fff; }
        .stat-table td { padding: 10px; text-align: center; border-bottom: 1px solid #252933; }
        .stat-table tr:last-child td { border-bottom: none; }
        .stat-table tr:hover { background: rgba(255,255,255,0.03); }
        .highlight-text { color: #00e676; font-weight: 700; }
        .env-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; padding: 15px; }
        .env-box { background: #15171c; border-radius: 8px; padding: 12px; border: 1px solid #252933; }
        .env-title { font-size: 10px; color: #8892a3; text-transform: uppercase; font-weight: 700; margin-bottom: 8px; border-bottom: 1px solid #2d323b; padding-bottom: 4px; }
        .env-row { display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px; color: #ddd; }
    </style>
    """
    
    # 1. Build DFS Table
    dfs_rows = ""
    for b in batters:
        b_name = b.get("name") or b.get("fullName") or "Unknown"
        b_slug = get_player_slug(b.get("id"), b_name, player_db)
        fd_sal = f"${b.get('salary')}" if b.get('salary') else '-'
        fd_proj = f"{float(b.get('proj', 0)):.1f}" if b.get('proj') else '-'
        dk_sal = f"${b.get('dk_salary')}" if b.get('dk_salary') else '-'
        dk_proj = f"{float(b.get('dk_proj', 0)):.1f}" if b.get('dk_proj') else '-'
        pos = b.get("fd_positions") or b.get("dk_positions") or "FLEX"
        
        dfs_rows += f"""<tr>
            <td><a href="/players/{b_slug}/" style="color: inherit; text-decoration: none;">{b_name}</a></td>
            <td style="color: #8892a3;">{pos}</td>
            <td>{fd_sal}</td>
            <td class="highlight-text">{fd_proj}</td>
            <td>{dk_sal}</td>
            <td class="highlight-text">{dk_proj}</td>
        </tr>"""

    # 2. Build Pitcher Table
    pitcher_html = ""
    if p_stats:
        vl, vr, season = p_stats.get("split_vL", {}), p_stats.get("split_vR", {}), p_stats.get("season", {})
        opp_slug = get_player_slug(opp_pitcher["id"], opp_pitcher["name"], player_db)
        opp_link = f"""<a href="/players/{opp_slug}/" style="color: inherit; text-decoration: none;">{opp_pitcher['name']}</a>""" if opp_pitcher["name"] else "TBD"
        
        vl_ops_cls = "highlight-text" if (vl.get("ops") and vl.get("ops") != "-" and float(vl.get("ops")) > 0.750) else ""
        vr_ops_cls = "highlight-text" if (vr.get("ops") and vr.get("ops") != "-" and float(vr.get("ops")) > 0.750) else ""

        pitcher_html = f"""
        <div class="stat-card">
            <div class="stat-header">Opposing Pitcher: {opp_link}</div>
            <table class="stat-table">
                <thead><tr><th>Split</th><th>AVG</th><th>OPS</th><th>HR</th><th>K</th></tr></thead>
                <tbody>
                    <tr><td>vs LHB</td><td>{vl.get('avg','-')}</td><td class="{vl_ops_cls}">{vl.get('ops','-')}</td><td>{vl.get('hr','-')}</td><td>{vl.get('k','-')}</td></tr>
                    <tr><td>vs RHB</td><td>{vr.get('avg','-')}</td><td class="{vr_ops_cls}">{vr.get('ops','-')}</td><td>{vr.get('hr','-')}</td><td>{vr.get('k','-')}</td></tr>
                </tbody>
            </table>
            <div style="background: #15171c; padding: 10px 15px; font-size: 11px; color: #8892a3; border-top: 1px solid #2d323b; display: flex; gap: 15px; justify-content: center;">
                <span><strong>SEASON:</strong></span>
                <span>{season.get('ip',0)} IP</span><span>{season.get('era','-')} ERA</span><span>{season.get('whip','-')} WHIP</span><span>{season.get('k','-')} SO</span>
            </div>
        </div>"""
    else:
        pitcher_html = """
        <div class="stat-card">
            <div class="stat-header">Opposing Pitcher: TBD / Bullpen Game</div>
            <div style="padding: 20px; text-align: center; color: #8892a3; font-size: 13px;">Advanced split stats will populate once an official starting pitcher is announced.</div>
        </div>"""

    # 3. Build Batter Splits Table
    split_rows = ""
    for b in batters:
        b_name = b.get("name") or b.get("fullName") or "Unknown"
        b_slug = get_player_slug(b.get("id"), b_name, player_db)
        b_stats = deep_stats.get(str(b.get("id")), {})
        split_data = b_stats.get("split_vL", {}) if pitcher_hand == 'L' else b_stats.get("split_vR", {})
        ops = split_data.get("ops", "-")
        bvp = b_stats.get("bvp", {})
        bvp_ab = bvp.get("ab", "-")
        bvp_avg = bvp.get("avg", "-")
        bvp_hr = bvp.get("hr", "-")
        
        ops_cls = "highlight-text" if ops != "-" and float(ops) > 0.800 else ""
        hr_sty = "color: #ff1744; font-weight: 700;" if bvp_hr != "-" and float(bvp_hr) > 0 else "color: inherit; font-weight: 400;"
        
        split_rows += f"""<tr>
            <td><a href="/players/{b_slug}/" style="color: inherit; text-decoration: none;">{b_name}</a></td>
            <td class="{ops_cls}">{ops}</td><td>{bvp_ab}</td><td>{bvp_avg}</td><td style="{hr_sty}">{bvp_hr}</td>
        </tr>"""

    # 4. Environment
    runs_cls = "highlight-text" if park_stats.get("runs", 0) > 102 else ""
    env_html = f"""
    <div class="stat-card">
        <div class="stat-header">Game Environment</div>
        <div class="env-grid">
            <div class="env-box">
                <div class="env-title">Park Factors (100 = Avg)</div>
                <div class="env-row"><span>Runs:</span> <span class="{runs_cls}">{park_stats.get('runs','-')}</span></div>
                <div class="env-row"><span>HR (LHB):</span> <span>{park_stats.get('hr_l','-')}</span></div>
                <div class="env-row"><span>HR (RHB):</span> <span>{park_stats.get('hr_r','-')}</span></div>
            </div>
            <div class="env-box">
                <div class="env-title">Umpire: {target_game.get('hpUmpire', 'TBD')}</div>
                <div class="env-row"><span>K Rate:</span> <span>{ump_stats.get('k_rate','-')}</span></div>
                <div class="env-row"><span>BB Rate:</span> <span>{ump_stats.get('bb_rate','-')}</span></div>
                <div class="env-row"><span>Runs/Game:</span> <span>{ump_stats.get('rpg','-')}</span></div>
            </div>
        </div>
    </div>"""

    return table_css + f"""
    <div class="stat-container">
        <div class="stat-card">
            <div class="stat-header">DFS Projections & Pricing</div>
            <table class="stat-table">
                <thead><tr><th>Batter</th><th>Pos</th><th>FD $</th><th>FD Proj</th><th>DK $</th><th>DK Proj</th></tr></thead>
                <tbody>{dfs_rows}</tbody>
            </table>
        </div>
        {pitcher_html}
        <div class="stat-card">
            <div class="stat-header">Batter Splits & BvP</div>
            <table class="stat-table">
                <thead><tr><th>Batter</th><th>vs {pitcher_hand}HP (OPS)</th><th>BvP AB</th><th>BvP AVG</th><th>BvP HR</th></tr></thead>
                <tbody>{split_rows}</tbody>
            </table>
        </div>
        {env_html}
    </div>
    """

def generate_team_html(team, player_db, daily_slates):
    team_id = team["id"]
    theme = TEAM_THEMES.get(team_id, {"paperBg": "#f4f1ea", "paperLine": "rgba(0,0,0,0.2)", "markerInk": "#111"})
    
    target_game, target_side, is_future, is_double_header, game_num, future_date_str = None, None, False, False, 1, ""
    
    for i in range(3):
        slate = daily_slates.get(i, {})
        tg, ts, idh, gn = find_game_in_slate(slate, team_id)
        if tg:
            target_game, target_side, is_double_header, game_num = tg, ts, idh, gn
            if i > 0:
                is_future = True
                future_date_str = get_est_date_string(i)
            break
            
    capture_area_html = ""
    analytics_html = ""
    
    if not target_game:
        capture_area_html = f"""
        <div style="max-width: 550px; margin: 30px auto; background: {theme['paperBg']}; border: 2px dashed {theme['markerInk']}; border-radius: 10px; padding: 35px 20px; text-align: center; font-family: 'Montserrat', sans-serif; color: #222; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
            <img src="https://www.mlbstatic.com/team-logos/{team_id}.svg" style="height: 70px; margin-bottom: 12px; opacity: 0.8;">
            <h1 style="font-family: 'Bebas Neue', cursive; font-size: 32px; color: {theme['markerInk']}; margin: 0;">NO GAME SCHEDULED</h1>
            <p style="font-size: 14px; color: #555; margin-top: 8px;">The {team['name']} do not have a game scheduled in the next 48 hours.</p>
            <a href="/" style="display: inline-block; margin-top: 18px; background: {theme['markerInk']}; color: #fff; padding: 8px 18px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 12px;">View Full Slate &rarr;</a>
        </div>"""
    else:
        raw = target_game.get("gameRaw", {})
        opp_side = 'home' if target_side == 'away' else 'away'
        opp_team_obj = raw.get("teams", {}).get(opp_side, {}).get("team", {"name": "Opponent"})
        tracking = target_game.get("lineupTracking", {}).get(target_side, {})
        proj_data = target_game.get("projectedLineups", {}).get(target_side, {})
        
        pos_map = target_game.get("gamePositions", {})
        hand_map = target_game.get("lineupHandedness", {})
        
        short_name = get_short_team_name(team["name"], raw.get("teams", {}).get(target_side, {}).get("team", {}).get("teamName"))
        opp_short_name = get_short_team_name(opp_team_obj.get("name", ""), opp_team_obj.get("teamName", ""))
        
        abstract_state = raw.get("status", {}).get("abstractGameState", "")
        detailed_state = raw.get("status", {}).get("detailedState", "")
        is_postponed = "Postponed" in abstract_state or "Postponed" in detailed_state or raw.get("status", {}).get("statusCode") == "C"
        
        opp_slug = get_slug_from_id(opp_team_obj.get("id"))
        opp_anchor = f'<a href="/lineups/{opp_slug}/" style="color: inherit; text-decoration: none; border-bottom: 1px dashed #888;">{opp_short_name}</a>'
        
        game_date_raw = raw.get("officialDate") or future_date_str or datetime.now().strftime("%Y-%m-%d")
        yy, mm, dd = game_date_raw.split('-')
        d_obj = datetime(int(yy), int(mm), int(dd))
        display_date = d_obj.strftime("%a, %B %d").upper()
        if is_double_header:
            display_date += f" &nbsp;•&nbsp; <span style='color: #ff1744;'>GAME {game_num}</span>"
            
        status = tracking.get("status", "NONE")
        badge_html = ""
        if is_postponed:
            badge_html = '<span style="background: #ff1744; color: #fff; font-weight: 800; font-size: 10px; padding: 3px 8px; border-radius: 20px; letter-spacing: 0.5px; display: inline-block; box-shadow: 0 0 8px rgba(255, 23, 68, 0.4);">✕ GAME POSTPONED (PPD)</span>'
        elif status == "OFFICIAL":
            time_str = f" ({tracking.get('officialAt')})" if tracking.get('officialAt') else ""
            badge_html = f'<span style="background: #00e676; color: #000; font-weight: 800; font-size: 10px; padding: 3px 8px; border-radius: 20px; letter-spacing: 0.5px; display: inline-block; box-shadow: 0 0 8px rgba(0, 230, 118, 0.4);">✓ OFFICIAL STARTING 9{time_str}</span>'
        elif status == "MODIFIED":
            badge_html = '<span style="background: #ff1744; color: #fff; font-weight: 800; font-size: 10px; padding: 3px 8px; border-radius: 20px; letter-spacing: 0.5px; display: inline-block; box-shadow: 0 0 8px rgba(255, 23, 68, 0.4);">🚨 MODIFIED / LATE SCRATCH</span>'
        else:
            badge_html = '<span style="background: #ffb300; color: #000; font-weight: 800; font-size: 10px; padding: 3px 8px; border-radius: 20px; letter-spacing: 0.5px; display: inline-block;">⏳ PROJECTED BATTING ORDER</span>'
            
        vs_symbol = f"@ {opp_anchor}" if target_side == 'away' else f"vs {opp_anchor}"
        venue_name = raw.get("venue", {}).get("name", "Stadium")
        
        odds_str = ""
        if target_game.get("odds") and target_game["odds"].get("moneyline") and not is_postponed:
            ml = target_game["odds"]["moneyline"].get(target_side)
            if ml:
                ml_format = f"+{ml}" if ml > 0 else str(ml)
                ou = f" • O/U {target_game['odds']['overUnder']}" if target_game["odds"].get("overUnder") else ""
                odds_str = f"<div style=\"font-family: 'Roboto Mono', monospace; font-size: 11px; color: #555; margin-top: 3px;\">Vegas Line: {ml_format}{ou}</div>"

        future_banner_html = ""
        if is_future and not is_postponed:
            nice_date = d_obj.strftime("%A, %B %d")
            vs_symbol_banner = f"@ {opp_anchor}" if target_side == 'away' else f"vs {opp_anchor}"
            future_banner_html = f"""
            <div style="max-width: 580px; width: 94%; margin: 15px auto 0; background: #fff3cd; border: 1px solid #ffeeba; color: #856404; padding: 12px; border-radius: 8px; font-family: 'Montserrat', sans-serif; font-size: 13px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
                <strong>The {team['name']} are off today.</strong> Their next matchup is on <strong>{nice_date}</strong> {vs_symbol_banner}. Below is the early projected lineup.
            </div>"""

        card_html = future_banner_html + f"""
        <div style="max-width: 580px; width: 94%; margin: 15px auto; background: {theme['paperBg']}; border-radius: 10px; padding: 18px 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.7), inset 0 0 30px rgba(0,0,0,0.03); position: relative; overflow: hidden; border: 1px solid #bbb; color: {theme['markerInk']}; box-sizing: border-box; --paper-line: {theme['paperLine']}; --marker-ink: {theme['markerInk']};">
            <img src="https://www.mlbstatic.com/team-logos/{team_id}.svg" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 420px; height: 420px; object-fit: contain; opacity: 0.09; pointer-events: none; z-index: 0;">
            <div style="display: flex; align-items: center; gap: 14px; border-bottom: 2.5px solid var(--marker-ink); padding-bottom: 12px; margin-bottom: 10px; position: relative; z-index: 1;">
                <img src="https://www.mlbstatic.com/team-logos/{team_id}.svg" alt="{team['name']} Logo" style="height: 56px; width: 56px; filter: drop-shadow(1px 3px 4px rgba(0,0,0,0.2)); flex-shrink: 0;">
                <div style="overflow: hidden; width: 100%;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 2px;">
                        {badge_html}
                        <span style="font-family: 'Montserrat', sans-serif; font-size: 10px; font-weight: 700; color: #666; letter-spacing: 0.5px;">{display_date}</span>
                    </div>
                    <h1 style="font-family: 'Permanent Marker', cursive; font-size: clamp(26px, 7vw, 38px); color: var(--marker-ink); margin: 0; line-height: 0.95; letter-spacing: 0.5px; text-transform: uppercase; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{short_name}</h1>
                    <div style="font-family: 'Caveat', cursive; font-size: clamp(16px, 4vw, 19px); color: #4a4f58; font-weight: 700; margin-top: 2px;">{vs_symbol} <span style="font-family: 'Montserrat', sans-serif; font-size: 11px; font-weight: 600; color: #777;">| {venue_name}</span></div>
                    {odds_str}
                </div>
            </div>
            <div style="position: relative; z-index: 1;">
                <div style="font-family: 'Montserrat', sans-serif; font-size: 10px; text-transform: uppercase; color: #666; font-weight: 700; letter-spacing: 1px; margin-bottom: 4px; border-bottom: 1px dashed var(--paper-line); padding-bottom: 3px;">Batting Order</div>
        """

        is_official = status in ["OFFICIAL", "MODIFIED"]
        batters = raw.get("lineups", {}).get(f"{target_side}Players", []) if (is_official and raw.get("lineups", {}).get(f"{target_side}Players")) else proj_data.get("battingOrder", [])
        
        if is_postponed:
            card_html += """
                <div style="padding: 40px 15px; text-align: center; font-family: 'Montserrat', sans-serif; background: rgba(255, 23, 68, 0.05); border: 1px dashed rgba(255, 23, 68, 0.4); border-radius: 8px; margin-top: 15px; position: relative; z-index: 2;">
                    <div style="color: #d32f2f; font-weight: 800; font-size: 17px; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px;">Matchup Called Off</div>
                    <div style="color: #666; font-size: 12.5px; font-weight: 500;">This game has been postponed due to weather or scheduling changes.</div>
                </div>
            </div>"""
        else:
            if not batters:
                card_html += """<div style="padding: 15px; text-align: center; font-family: 'Montserrat', sans-serif; color: #666; font-style: italic;">Batting order not populated yet.</div>"""
            else:
                for idx, b in enumerate(batters):
                    p_name = b.get("name") or b.get("fullName") or "Unknown"
                    pos = pos_map.get(str(b.get("id"))) or b.get("fd_positions") or b.get("dk_positions") or "DH"
                    hand = hand_map.get(str(b.get("id"))) or b.get("hand") or ""
                    hand_display = f"({hand}) " if hand else ""
                    headshot = get_headshot_url(b.get("id"))
                    p_slug = get_player_slug(b.get("id"), p_name, player_db)
                    
                    card_html += f"""
                    <div style="display: flex; align-items: center; border-bottom: 1px solid var(--paper-line); height: 42px; position: relative; z-index: 2; padding: 0 4px;">
                        <div style="width: 32px; height: 100%; display: flex; justify-content: center; align-items: center; border-right: 1px solid var(--paper-line); font-family: 'Permanent Marker', cursive; font-size: 17px; color: var(--marker-ink); flex-shrink: 0;">{idx + 1}</div>
                        <div style="width: 44px; height: 100%; display: flex; justify-content: center; align-items: center; border-right: 1px solid var(--paper-line); flex-shrink: 0;">
                            <div style="width: 32px; height: 32px; border-radius: 50%; background: #e0dcd3; overflow: hidden; border: 1.5px solid var(--marker-ink); border-radius: 255px 15px 225px 15px/15px 225px 15px 255px; display: flex; justify-content: center; align-items: center;">
                                <img src="{headshot}" style="width: 100%; height: 100%; object-fit: cover; object-position: center;">
                            </div>
                        </div>
                        <div style="flex-grow: 1; height: 100%; display: flex; align-items: center; padding-left: 10px; font-family: 'Permanent Marker', cursive; font-size: clamp(15px, 3.8vw, 17px); text-transform: uppercase; letter-spacing: 0.5px; color: #1a1e24; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                            <span style="font-family: 'Caveat', cursive; font-size: clamp(15px, 3.8vw, 17px); color: #4a4f58; opacity: 0.85; font-weight: 700; text-transform: none;">{hand_display}</span><a href="/players/{p_slug}/" style="color: inherit; text-decoration: none;">{p_name}</a>
                        </div>
                        <div style="width: 50px; height: 100%; display: flex; justify-content: center; align-items: center; font-family: 'Caveat', cursive; font-size: 19px; font-weight: 700; color: #4a4f58; flex-shrink: 0;">{pos}</div>
                    </div>"""

            sp = get_safe_pitcher(target_game, target_side, game_num)
            sp_name, sp_hand = sp["name"], sp["hand"]
            sp_hand_display = f"({sp_hand}) " if sp_hand else ""
            sp_headshot = get_headshot_url(sp["id"])
            sp_slug = get_player_slug(sp["id"], sp_name, player_db)
            
            card_html += f"""
                </div>
                <div style="margin-top: 12px; position: relative; z-index: 1;">
                    <div style="font-family: 'Caveat', cursive; font-size: 17px; color: #4a4f58; font-weight: 700; margin-bottom: 2px; padding-left: 4px;">Starting Pitcher</div>
                    <div style="display: flex; align-items: center; border: 1.5px solid var(--marker-ink); background-color: rgba(0,0,0,0.03); border-radius: 6px; height: 50px; overflow: hidden; box-shadow: 0 2px 6px rgba(0,0,0,0.04); padding: 0 4px;">
                        <div style="width: 36px; height: 100%; display: flex; justify-content: center; align-items: center; border-right: 1px solid var(--paper-line); font-family: 'Permanent Marker', cursive; font-size: 16px; color: var(--marker-ink); background: rgba(0,0,0,0.04); flex-shrink: 0;">SP</div>
                        <div style="width: 48px; height: 100%; display: flex; justify-content: center; align-items: center; border-right: 1px solid var(--paper-line); flex-shrink: 0;">
                            <div style="width: 36px; height: 36px; border-radius: 50%; background: #e0dcd3; overflow: hidden; border: 1.5px solid var(--marker-ink); border-radius: 255px 15px 225px 15px/15px 225px 15px 255px; display: flex; justify-content: center; align-items: center;">
                                <img src="{sp_headshot}" style="width: 100%; height: 100%; object-fit: cover; object-position: center;">
                            </div>
                        </div>
                        <div style="flex-grow: 1; height: 100%; display: flex; align-items: center; padding-left: 10px; font-family: 'Permanent Marker', cursive; font-size: clamp(16px, 4vw, 18px); text-transform: uppercase; letter-spacing: 0.5px; color: #1a1e24; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                            <span style="font-family: 'Caveat', cursive; font-size: clamp(16px, 4vw, 18px); color: #4a4f58; opacity: 0.85; font-weight: 700; text-transform: none;">{sp_hand_display}</span><a href="/players/{sp_slug}/" style="color: inherit; text-decoration: none;">{sp_name}</a>
                        </div>
                        <div style="width: 50px; height: 100%; display: flex; justify-content: center; align-items: center; font-family: 'Caveat', cursive; font-size: 19px; font-weight: 700; color: #4a4f58; flex-shrink: 0;">SP</div>
                    </div>
                </div>
            </div>"""
            
            analytics_html = render_analytics_section(target_game, target_side, batters, game_num, player_db)
            
        capture_area_html = card_html

    # The HTML string formatting uses doubled curly braces {{ and }} for CSS classes to avoid python f-string errors
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{team['name']} Starting Lineup Today | Batting Order & Pitcher</title>
    
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="../../styles.css">
    
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Caveat:wght@600;700&family=Montserrat:wght@400;600;700&family=Permanent+Marker&family=Roboto+Mono:wght@500;700&display=swap" rel="stylesheet">
    
    <style>
        .header-brand {{ font-weight: 900; letter-spacing: -1px; font-size: 2rem; color: #fff; font-style: italic; text-shadow: 0 2px 4px rgba(0,0,0,0.5); }}
        .header-brand a {{ color: inherit; text-decoration: none; }}
        .header-brand span {{ background: linear-gradient(to bottom, #7CD0FF 0%, #1A8CFF 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; padding-right: 2px; display: inline-block; }}
    </style>
</head>
<body class="dark-theme">
    <nav class="navbar shadow-sm py-3 mb-4" style="background-color: #212529;">
        <div class="container d-flex justify-content-between align-items-center flex-wrap">
            <div class="header-brand mb-0"><a href="/">MLB Starting <span>Nine</span></a></div>
            <div><a href="/" class="btn btn-sm btn-outline-light font-weight-bold" style="font-size:0.8rem;">← Back To Slate</a></div>
        </div>
    </nav>

    <div id="main-wrapper">
        <div id="capture-area">
            {capture_area_html}
        </div>
        <div id="public-analytics-section">
            {analytics_html}
        </div>
        <footer style="background: #0a0a0a; border-top: 1px solid #1a1a1a; padding: 25px 15px; text-align: center; margin-top: 40px; font-family: 'Montserrat', sans-serif;">
            <p style="color: #666; font-size: 11px; margin: 0 0 8px 0;">&copy; {datetime.now().year} MLB Starting 9. All rights reserved.</p>
        </footer>
    </div>
</body>
</html>"""
    return html_content

# ==========================================
# 4. CONDITIONAL BUILD EXECUTION
# ==========================================
def main():
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lineups")
    os.makedirs(base_dir, exist_ok=True)
    
    player_db = load_json_safe("data/player_master_data.json")
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
        
        new_html = generate_team_html(team, player_db, daily_slates)
        
        existing_html = ""
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                existing_html = f.read()
                
        if new_html != existing_html:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_html)
            updated_files += 1

if __name__ == "__main__":
    main()
