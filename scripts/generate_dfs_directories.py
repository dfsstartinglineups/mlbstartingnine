import os
import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import unicodedata

# =========================================================================
# --- 1. DYNAMIC PATH ROUTING ---
# =========================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

DATA_DIR = os.path.join(ROOT_DIR, "data")
DAILY_FILES_DIR = os.path.join(DATA_DIR, "daily_files")
LIVE_FILES_DIR = os.path.join(DATA_DIR, "LIVE")
PLAYER_MASTER_PATH = os.path.join(DATA_DIR, "player_master_data.json")
OUTPUT_BASE_DIR = os.path.join(ROOT_DIR, "dfs")
SITEMAP_PATH = os.path.join(ROOT_DIR, "sitemap-dfs.xml")

TEAM_MEGA_SCORE = 5.5
TEAM_MEGA_BOOST = 0.050
TEAM_ELITE_SCORE = 5.0
TEAM_ELITE_BOOST = 0.035
TEAM_GOOD_SCORE = 4.5
TEAM_GOOD_BOOST = 0.025
TEAM_BAD_SCORE = 3.5
TEAM_BAD_PENALTY = -0.050

POS_LABELS_DK = {
    "pitchers": "Pitchers", "catchers": "Catchers", "first-base": "First Base",
    "second-base": "Second Base", "third-base": "Third Base", 
    "shortstops": "Shortstops", "outfielders": "Outfielders", "util": "Util (All Hitters)",
    "live-slate-leaderboard": "🔴 Live Leaderboard"
}
POS_LABELS_FD = {
    "pitchers": "Pitchers", "catchers-first-base": "C / 1B",
    "second-base": "Second Base", "third-base": "Third Base", 
    "shortstops": "Shortstops", "outfielders": "Outfielders", "util": "Utility",
    "live-slate-leaderboard": "🔴 Live Leaderboard"
}

# =========================================================================
# --- 2. SEO METADATA MATRIX ---
# =========================================================================
SEO_METADATA = {
    "draftkings": {
        "pitchers": {"title": "Top DraftKings Pitcher Projections Today - DFS Lineup Values", "desc": "Optimized DraftKings pitcher projections for today's MLB slate."},
        "catchers": {"title": "Best DraftKings Catchers Today - Daily Fantasy C Projections", "desc": "Daily fantasy baseball rankings for DraftKings catchers."},
        "first-base": {"title": "Top DraftKings 1B Projections Today - Elite First Base Value", "desc": "Analyze today's DraftKings first base projections."},
        "second-base": {"title": "Optimized DraftKings 2B Value Picks Today - DFS Rankings", "desc": "Unlock top-rated DraftKings second base projections."},
        "third-base": {"title": "Best DraftKings 3B Projections Today - Daily Fantasy Third Base", "desc": "Premium DraftKings third base projections."},
        "shortstops": {"title": "Top DraftKings Shortstop Picks Today - Advanced SS Projections", "desc": "Compare daily fantasy shortstop values on DraftKings."},
        "outfielders": {"title": "Best DraftKings Outfield Projections Today - DFS OF Value Grid", "desc": "Comprehensive DraftKings outfield rankings and value projections."},
        "util": {"title": "Top DraftKings Hitters Today - DFS Overall Value Rankings", "desc": "View the highest projected DraftKings hitters across all positions."},
        "live-slate-leaderboard": {"title": "Live DraftKings DFS Leaderboard - Real-Time Fantasy Baseball Scores", "desc": "Live updating DraftKings fantasy baseball leaderboard. Track real-time player points and contextual stat lines across all active MLB slates."}
    },
    "fanduel": {
        "pitchers": {"title": "Top FanDuel Pitcher Projections Today - Daily Fantasy Baseball", "desc": "Maximize your FanDuel pitching slot with real-time projections."},
        "catchers-first-base": {"title": "Best FanDuel C/1B Projections Today - Catchers & First Base Value", "desc": "Optimized FanDuel combined Catcher and First Base projections."},
        "second-base": {"title": "Top FanDuel 2B Rankings Today - Daily Fantasy Second Base Picks", "desc": "Find the highest-value second basemen on FanDuel today."},
        "third-base": {"title": "Optimized FanDuel 3B Projections Today - Fantasy Third Base Value", "desc": "Advanced FanDuel third base projections."},
        "shortstops": {"title": "Best FanDuel Shortstop Picks Today - DFS SS Rankings", "desc": "Daily updated FanDuel shortstop projections."},
        "outfielders": {"title": "Top FanDuel Outfield Projections Today - DFS Outfielder Rankings", "desc": "Deep-dive FanDuel outfielder value tables."},
        "util": {"title": "Best FanDuel Utility Projections Today - DFS UTIL Picks", "desc": "Fill your FanDuel Utility slot with the highest value hitters."},
        "live-slate-leaderboard": {"title": "Live FanDuel DFS Leaderboard - Real-Time Fantasy Baseball Scores", "desc": "Live updating FanDuel fantasy baseball leaderboard. Track real-time player points and contextual stat lines across all active MLB slates."}
    }
}

# =========================================================================
# --- 3. URL SLUG AND LOOKUP UTILITIES ---
# =========================================================================
TEAM_SLUG_MAP = {
    108: "los-angeles-angels", 109: "arizona-diamondbacks", 110: "baltimore-orioles", 111: "boston-red-sox",
    112: "chicago-cubs", 113: "cincinnati-reds", 114: "cleveland-guardians", 115: "colorado-rockies",
    116: "detroit-tigers", 117: "houston-astros", 118: "kansas-city-royals", 119: "los-angeles-dodgers",
    120: "washington-nationals", 121: "new-york-mets", 133: "athletics", 134: "pittsburgh-pirates",
    135: "san-diego-padres", 136: "seattle-mariners", 137: "san-francisco-giants", 138: "st-louis-cardinals",
    139: "tampa-bay-rays", 140: "texas-rangers", 141: "toronto-blue-jays", 142: "minnesota-twins",
    143: "philadelphia-phillies", 144: "atlanta-braves", 145: "chicago-white-sox", 146: "miami-marlins",
    147: "new-york-yankees", 158: "milwaukee-brewers"
}

def load_player_database():
    if os.path.exists(PLAYER_MASTER_PATH):
        try:
            with open(PLAYER_MASTER_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Warning: Could not parse player_master_data.json: {e}")
    return {}

PLAYER_DATABASE = load_player_database()

def slugify(text):
    if not text: return ""
    text = unicodedata.normalize('NFKD', str(text)).encode('ASCII', 'ignore').decode('utf-8')
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s-]+', '-', text)
    return text.strip()

def get_player_url(player_id, default_name):
    db_key = f"ID{player_id}"
    if player_id and db_key in PLAYER_DATABASE:
        if "slug" in PLAYER_DATABASE[db_key]:
            return f"/players/{PLAYER_DATABASE[db_key]['slug']}/"
    return f"/players/{slugify(default_name)}/"

# =========================================================================
# --- 4. ALGORITHMS & LIVE LOGIC ---
# =========================================================================
def get_team_data(game_node, side):
    team_name = "AWAY" if side == "away" else "HOME"
    team_id = 0
    raw_teams = game_node.get("gameRaw", {}).get("teams", {})
    if side in raw_teams and "team" in raw_teams[side]:
        team_info = raw_teams[side]["team"]
        full_name = team_info.get("name", "")
        team_id = team_info.get("id", 0)
        team_name = team_info.get("teamName")
        if not team_name:
            team_name = full_name.split(' ')[-1] if full_name else ("AWAY" if side == "away" else "HOME")
        if "Red Sox" in full_name: team_name = "Red Sox"
        elif "White Sox" in full_name: team_name = "White Sox"
        elif "Blue Jays" in full_name: team_name = "Blue Jays"
        elif team_name == "Diamondbacks": team_name = "Dbacks"
    return team_name, team_id

def calculate_vegas_nudge(itt):
    if itt >= TEAM_MEGA_SCORE: return TEAM_MEGA_BOOST
    elif itt >= TEAM_ELITE_SCORE: return TEAM_ELITE_BOOST
    elif itt >= TEAM_GOOD_SCORE: return TEAM_GOOD_BOOST
    elif 0 < itt <= TEAM_BAD_SCORE: return TEAM_BAD_PENALTY
    return 0.0

def process_proprietary_projection(player, is_pitcher, team_name, team_id, opp_name, opp_id, is_home, game, is_dk=False, lineup_pos="", order_status=""):
    raw_proj = float(player.get("dk_proj" if is_dk else "proj", 0.0))
    salary = int(player.get("dk_salary" if is_dk else "salary", 0))
    
    # Check ONLY for salary presence to ensure deep bench players still populate Live Slates
    if salary <= 0: return None
    
    slate_block = player.get("dk_slates" if is_dk else "fd_slates", {})
    slate_ids = [str(k).strip() for k in slate_block.keys()] if isinstance(slate_block, dict) else []

    odds = game.get("odds", {})
    total = 0.0
    if odds and "bookmakers" in odds and len(odds["bookmakers"]) > 0:
        market_totals = odds["bookmakers"][0].get("markets", [])
        for m in market_totals:
            if m["key"] == "totals" and m["outcomes"]:
                total = float(m["outcomes"][0].get("point", 0.0))
    
    away_itt = round(total / 2.0, 2) if total > 0 else 4.2
    home_itt = round(total / 2.0, 2) if total > 0 else 4.2
    opp_itt = away_itt if is_home else home_itt
    my_itt = home_itt if is_home else away_itt

    vegas_nudge = calculate_vegas_nudge(my_itt if not is_pitcher else opp_itt)
    
    order_nudge = 0.0
    if not is_pitcher:
        order = int(player.get("order", 6))
        if order in [1, 2, 3]: order_nudge = 0.04
        elif order in [4, 5]: order_nudge = 0.02
        elif order in [8, 9]: order_nudge = -0.03

    park_nudge = 0.0
    park_stats = game.get("parkStats", {})
    if park_stats:
        woba_avg = (float(park_stats.get("woba_l", 100)) + float(park_stats.get("woba_r", 100))) / 2.0
        if woba_avg > 105: park_nudge = -0.03 if is_pitcher else 0.04
        elif woba_avg < 96: park_nudge = 0.04 if is_pitcher else -0.03

    hitter_mult = 1.00 - (calculate_vegas_nudge(opp_itt) + park_nudge) if is_pitcher else 1.00 + vegas_nudge + order_nudge + park_nudge
    final_proj = round(raw_proj * hitter_mult, 2)
    value = round(final_proj / (salary / 1000), 2) if salary > 0 else 0.0

    slate_stats = {}
    for s_id, s_data in slate_block.items():
        if isinstance(s_data, dict):
            s_raw_proj = float(s_data.get("proj", raw_proj))
            s_salary = int(s_data.get("salary", salary))
            s_final_proj = round(s_raw_proj * hitter_mult, 2)
            s_val = round(s_final_proj / (s_salary / 1000), 2) if s_salary > 0 else 0.0
            slate_stats[str(s_id).strip()] = {"salary": f"${s_salary:,}", "proj": f"{s_final_proj:.2f}", "value": f"{s_val:.2f}x"}
            
    team_slug = TEAM_SLUG_MAP.get(int(team_id) if team_id else 0, "los-angeles-dodgers")

    return {
        "id": player.get("id"), "name": player.get("name") or player.get("fullName"),
        "team": team_name, "team_id": team_id, "team_slug": team_slug,
        "opp_indicator": "vs." if is_home else "@", "opp_name": opp_name, "opp_id": opp_id,
        "salary": salary, "proj": final_proj, "value": value,
        "slates": ",".join(slate_ids), "slate_stats_json": json.dumps(slate_stats),
        "lineup_pos": lineup_pos, "order_status": order_status, "is_pitcher": is_pitcher,
        "url": get_player_url(player.get("id"), player.get("name") or player.get("fullName")),
        "raw_live_stats": "", "live_points": 0.0 
    }

def flatten_live_data(live_json):
    """Flattens game-level live JSON into a single player ID lookup dictionary."""
    flat_map = {}
    if not isinstance(live_json, dict):
        return flat_map
    
    for game_id, game_data in live_json.items():
        if not isinstance(game_data, dict):
            continue
        players_node = game_data.get("players", {})
        if not isinstance(players_node, dict):
            continue
        for side in ["AWAY", "HOME"]:
            side_players = players_node.get(side, {})
            if isinstance(side_players, dict):
                for p_key, p_val in side_players.items():
                    clean_id = str(p_key).replace("ID", "").strip()
                    flat_map[clean_id] = p_val
    return flat_map

def process_live_leaderboard_player(base_player, flat_live_data, platform):
    pid = str(base_player["id"]).replace("ID", "").strip()
    
    # Initialize default pre-game state
    live_pts = 0.0
    stat_string = "Pre-game"
    
    p_live = flat_live_data.get(pid, {})

    if p_live:
        live_pts = float(p_live.get("dk_pts" if platform == "dk" else "fd_pts", 0.0))
        
        if base_player["is_pitcher"]:
            pitching = p_live.get("pitching")
            if isinstance(pitching, dict):
                stat_string = pitching.get("summary") or ""
                if not stat_string:
                    ip = pitching.get("inningsPitched", "0.0")
                    k = pitching.get("strikeOuts", 0)
                    er = pitching.get("earnedRuns", 0)
                    bb = pitching.get("baseOnBalls", 0)
                    w = "W, " if pitching.get("wins", 0) > 0 else ""
                    stat_string = f"{w}{ip} IP, {k} K, {er} ER, {bb} BB"
        else:
            batting = p_live.get("batting")
            if isinstance(batting, dict):
                stat_string = batting.get("summary") or ""
                if not stat_string:
                    h = batting.get("hits", 0)
                    ab = batting.get("atBats", 0)
                    hr = batting.get("homeRuns", 0)
                    rbi = batting.get("rbi", 0)
                    r = batting.get("runs", 0)
                    sb = batting.get("stolenBases", 0)
                    
                    pieces = [f"{h}-{ab}"]
                    if hr > 0: pieces.append(f"{hr} HR")
                    if rbi > 0: pieces.append(f"{rbi} RBI")
                    if r > 0: pieces.append(f"{r} R")
                    if sb > 0: pieces.append(f"{sb} SB")
                    stat_string = ", ".join(pieces)
            
    # Calculate baseline values
    salary = base_player["salary"]
    live_value = round(live_pts / (salary / 1000), 2) if salary > 0 else 0.0

    # Build slate stats dynamically based on current live points
    slate_stats = {}
    original_slate_stats = json.loads(base_player["slate_stats_json"])
    for s_id, s_data in original_slate_stats.items():
        s_salary = int(str(s_data["salary"]).replace('$', '').replace(',', ''))
        s_val = round(live_pts / (s_salary / 1000), 2) if s_salary > 0 else 0.0
        slate_stats[s_id] = {
            "salary": s_data["salary"],
            "proj": f"{live_pts:.2f}", 
            "value": f"{s_val:.2f}x"
        }

    return {
        **base_player,
        "proj": round(live_pts, 2), 
        "value": live_value,
        "slate_stats_json": json.dumps(slate_stats),
        "raw_live_stats": stat_string or "In Game"
    }

# =========================================================================
# --- 5. JINJA2 HTML TEMPLATE ---
# =========================================================================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-TW817924LJ"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){dataLayer.push(arguments);}
      gtag('js', new Date());
      gtag('config', 'G-TW817924LJ');
    </script>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    
    <link rel="icon" href="/favicon.ico" sizes="any">
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">

    <title>{{ seo_title }}</title>
    <meta name="description" content="{{ seo_desc }}">
    
    <link rel="canonical" href="{{ page_url }}" />
    
    <meta property="og:site_name" content="MLB Starting Nine">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{{ page_url }}">
    <meta property="og:title" content="{{ seo_title }}">
    <meta property="og:description" content="{{ seo_desc }}">
    <meta property="og:image" content="https://mlbstartingnine.com/mlb-social-share.jpg">

    <meta name="twitter:card" content="summary">
    <meta property="twitter:domain" content="mlbstartingnine.com">
    <meta property="twitter:url" content="{{ page_url }}">
    <meta name="twitter:title" content="{{ seo_title }}">
    <meta name="twitter:description" content="{{ seo_desc }}">
    <meta name="twitter:image" content="https://mlbstartingnine.com/mlb-social-share.jpg">

    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f4f7f6; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        
        .header-brand { font-weight: 900; letter-spacing: -1px; font-size: 2rem; color: #fff; font-style: italic; text-shadow: 0 2px 4px rgba(0,0,0,0.5); }
        .header-brand a { color: inherit; text-decoration: none; }
        .header-brand span { background: linear-gradient(to bottom, #7CD0FF 0%, #1A8CFF 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; padding-right: 2px; display: inline-block; }

        .table-card { border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border: 1px solid #dee2e6; overflow: hidden; background: #fff; }
        .table th { background-color: #212529; color: #fff; font-size: 0.75rem; text-transform: uppercase; font-weight: 700; padding: 12px; cursor: pointer; user-select: none; white-space: nowrap; }
        .table th:hover { background-color: #343a40; }
        .table td { vertical-align: middle; padding: 10px 12px; font-size: 0.85rem; border-bottom: 1px solid #edf2f4; }
        .player-link { font-weight: 700; color: #212529; text-decoration: none; }
        .player-link:hover { color: #0d6efd; text-decoration: underline; }
        .disclaimer-box { background-color: #fff9db; border: 1px solid #ffe3e3; border-radius: 6px; font-size: 0.75rem; color: #616161; line-height: 1.4; }

        @media (max-width: 768px) {
            .table th, .table td { padding: 8px 6px; font-size: 0.75rem; white-space: nowrap; }
            .player-link { font-size: 0.80rem; }
            .col-rank { padding-right: 4px !important; padding-left: 4px !important; }
        }
    </style>
</head>
<body>

<nav class="navbar shadow-sm py-3 mb-4" style="background-color: #212529;">
    <div class="container d-flex justify-content-between align-items-center flex-wrap">
        <div class="header-brand mb-0"><a href="/">MLB Starting <span>Nine</span></a></div>
        <div><a href="/" class="btn btn-sm btn-outline-light font-weight-bold">← Back To Slate</a></div>
    </div>
</nav>

<div class="container my-4">
    <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
        <div>
            <h1 class="h3 fw-bold text-dark mb-1">{{ page_heading }}</h1>
            <p class="text-muted small mb-0">Updated: {{ date_str }} | Real-time Context Performance Matrix</p>
        </div>
        <span class="badge bg-dark px-3 py-2 fs-6 shadow-sm">{{ platform_name }}</span>
    </div>

    <div class="d-flex align-items-center gap-2 mb-3 flex-wrap">
        {% if distinct_slates %}
        <div class="d-flex align-items-center gap-2">
            <span class="fw-bold text-secondary small text-uppercase">Slates:</span>
            <select class="form-select form-select-sm w-auto fw-bold" id="slate-selector" onchange="filterSlate(this.value)">
                <option value="all">All Games</option>
                {% for s_id, s_name in distinct_slates.items() %}
                <option value="{{ s_id }}">{{ s_name }}</option>
                {% endfor %}
            </select>
        </div>
        {% endif %}
        
        {% if current_pos != 'live-slate-leaderboard' %}
        <div class="d-flex align-items-center gap-2 ms-md-3">
            <span class="fw-bold text-secondary small text-uppercase">Position:</span>
            <select class="form-select form-select-sm w-auto fw-bold" id="position-selector" onchange="changePosition(this.value)">
                {% for pos_key, pos_label in position_links.items() %}
                <option value="/dfs/{{ platform_slug }}/top-{{ pos_key }}/" {% if pos_key == current_pos %}selected{% endif %}>{{ pos_label }}</option>
                {% endfor %}
            </select>
        </div>
        {% endif %}
    </div>

    <div class="table-card shadow-sm mb-4 position-relative">
        <div id="scroll-indicator" class="d-md-none position-absolute top-50 end-0 translate-middle-y pe-2 pe-none shadow-sm rounded-start bg-dark text-white px-2 py-1 z-3" style="opacity: 0.85; transition: opacity 0.3s; font-size: 0.70rem; letter-spacing: 0.5px;">
            &larr; Swipe
        </div>

        <div class="table-responsive" id="table-scroll-container">
            <table class="table table-hover mb-0" id="leaderboard-table">
                <thead>
                    <tr>
                        <th style="width: 1%;" class="text-center px-2" onclick="sortTable(this, 0)"># &#x21D5;</th>
                        <th onclick="sortTable(this, 1)">Player &#x21D5;</th>
                        
                        {% if current_pos == 'live-slate-leaderboard' %}
                        <th class="text-end" onclick="sortTable(this, 2)">{{ score_col_name }} &#x21D5;</th>
                        <th onclick="sortTable(this, 3)">Live Stats &#x21D5;</th>
                        {% else %}
                        <th class="text-end text-primary" onclick="sortTable(this, 2)">Value &#x21D5;</th>
                        <th onclick="sortTable(this, 3)">Team &#x21D5;</th>
                        <th onclick="sortTable(this, 4)">Matchup &#x21D5;</th>
                        <th class="text-end" onclick="sortTable(this, 5)">Salary &#x21D5;</th>
                        <th class="text-end" onclick="sortTable(this, 6)">{{ score_col_name }} &#x21D5;</th>
                        {% endif %}
                    </tr>
                </thead>
                <tbody>
                    {% for p in players %}
                    <tr data-slates="{{ p.slates }}" 
                        data-slate-stats='{{ p.slate_stats_json }}' 
                        data-default-salary="${{ "{:,}".format(p.salary) }}" 
                        data-default-proj="{{ p.proj }}" 
                        data-default-value="{{ p.value }}x">
                        
                        <td class="fw-bold text-muted col-rank text-center px-2" style="width: 1%;">{{ loop.index }}</td>
                        <td>
                            <div class="d-flex align-items-center">
                                <a href="/lineups/{{ p.team_slug }}/" class="text-decoration-none">
                                    {% if p.order_status == 'official' %}
                                        <span class="badge bg-success me-2 shadow-sm d-inline-block text-center" style="font-size: 0.60rem; width: 26px;" title="Official Lineup Position">{{ p.lineup_pos }}</span>
                                    {% elif p.order_status == 'projected' %}
                                        <span class="badge bg-warning text-dark me-2 shadow-sm d-inline-block text-center" style="font-size: 0.60rem; width: 26px;" title="Projected Lineup Position">{{ p.lineup_pos }}</span>
                                    {% elif p.order_status == 'ns' %}
                                        <span class="badge bg-danger me-2 shadow-sm d-inline-block text-center" style="font-size: 0.60rem; width: 26px;" title="Not Starting">NS</span>
                                    {% endif %}
                                </a>
                                
                                <div class="position-relative d-inline-block me-2 flex-shrink-0">
                                    <img src="https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_64,q_auto:best/v1/people/{{ p.id }}/headshot/67/current" alt="headshot" class="rounded-circle" style="width: 34px; height: 34px; object-fit: cover; border: 1px solid #ced4da; background-color: #fff;">
                                    <img src="https://www.mlbstatic.com/team-logos/{{ p.team_id }}.svg" alt="Team Badge" class="position-absolute bg-white rounded-circle shadow-sm" style="width: 16px; height: 16px; bottom: -2px; right: -4px; padding: 1px; border: 1px solid #ced4da;">
                                </div>
                                
                                <a href="{{ p.url }}" class="player-link text-nowrap">{{ p.name }}</a>
                            </div>
                        </td>
                        
                        {% if current_pos == 'live-slate-leaderboard' %}
                        <td class="text-end fw-bold col-proj fs-6">{{ p.proj }}</td>
                        <td class="fw-semibold text-secondary" style="font-size: 0.85rem;">{{ p.raw_live_stats }}</td>
                        {% else %}
                        <td class="text-end fw-bold text-success col-value">{{ p.value }}x</td>
                        <td>
                            <span class="badge bg-light text-dark border d-flex align-items-center" style="width: fit-content; font-size: 0.80rem;">
                                {{ p.team }}
                            </span>
                        </td>
                        <td class="text-muted font-monospace fw-semibold" style="font-size: 0.80rem;">
                            <div class="d-flex align-items-center text-nowrap">
                                {{ p.opp_indicator }} <img src="https://www.mlbstatic.com/team-logos/{{ p.opp_id }}.svg" alt="{{ p.opp_name }} Icon" style="width: 18px; height: 18px; margin: 0 4px;"> {{ p.opp_name }}
                            </div>
                        </td>
                        <td class="text-end fw-semibold col-salary">${{ "{:,}".format(p.salary) }}</td>
                        <td class="text-end fw-bold col-proj">{{ p.proj }}</td>
                        {% endif %}
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    <div class="disclaimer-box p-3 mb-4 shadow-sm">
        <strong>Disclaimer Algorithm Note:</strong> The daily predictions displayed below are generated through the proprietary <code>mlbstartingnine.com</code> analytics system. Our engine alters baseline performance profiles by cross-checking real-time stadium indices, historical hitter platoon margins, and shifting Vegas bookmaker implied configurations to establish contextual DFS values.
    </div>
</div>

<script>
document.addEventListener("DOMContentLoaded", () => {
    const scrollContainer = document.getElementById('table-scroll-container');
    const scrollIndicator = document.getElementById('scroll-indicator');
    
    if (scrollContainer && scrollIndicator) {
        scrollContainer.addEventListener('scroll', () => {
            if (scrollContainer.scrollLeft > 10) {
                scrollIndicator.style.opacity = '0';
            } else {
                scrollIndicator.style.opacity = '0.85';
            }
        }, { passive: true });
    }

    const urlParams = new URLSearchParams(window.location.search);
    const slateParam = urlParams.get('slate');
    if (slateParam) {
        const slateSelector = document.getElementById('slate-selector');
        if (slateSelector) {
            const optionExists = Array.from(slateSelector.options).some(opt => opt.value === slateParam);
            if (optionExists) {
                slateSelector.value = slateParam;
                filterSlate(slateParam);
            }
        }
    }
});

function changePosition(base_url) {
    const slateSelector = document.getElementById('slate-selector');
    if (slateSelector && slateSelector.value !== 'all') {
        window.location.href = base_url + '?slate=' + slateSelector.value;
    } else {
        window.location.href = base_url;
    }
}

function filterSlate(slateId, preserveSort = false) {
    const rows = document.querySelectorAll('#leaderboard-table tbody tr');
    rows.forEach(row => {
        const rowSlates = row.getAttribute('data-slates').split(',');
        const statsRaw = row.getAttribute('data-slate-stats');
        const stats = statsRaw ? JSON.parse(statsRaw) : {};

        if (slateId === 'all') {
            row.style.display = '';
            
            const salCol = row.querySelector('.col-salary');
            const projCol = row.querySelector('.col-proj');
            const valCol = row.querySelector('.col-value');
            
            if (salCol) salCol.textContent = row.getAttribute('data-default-salary');
            if (projCol) projCol.textContent = row.getAttribute('data-default-proj');
            if (valCol) valCol.textContent = row.getAttribute('data-default-value');
        } else {
            if (rowSlates.includes(slateId)) {
                row.style.display = '';
                if (stats[slateId]) {
                    const salCol = row.querySelector('.col-salary');
                    const projCol = row.querySelector('.col-proj');
                    const valCol = row.querySelector('.col-value');

                    if (salCol) salCol.textContent = stats[slateId].salary;
                    if (projCol) projCol.textContent = stats[slateId].proj;
                    if (valCol) valCol.textContent = stats[slateId].value;
                }
            } else {
                row.style.display = 'none';
            }
        }
    });

    let targetHeader, sortIndex, forceDesc = false;

    if (preserveSort) {
        targetHeader = document.querySelector('#leaderboard-table th.asc, #leaderboard-table th.desc');
        if (targetHeader) {
            const headers = Array.from(document.querySelectorAll('#leaderboard-table th'));
            sortIndex = headers.indexOf(targetHeader);
            const isDesc = targetHeader.classList.contains('desc');
            
            targetHeader.classList.remove('desc', 'asc');
            targetHeader.classList.add(isDesc ? 'asc' : 'desc');
        }
    }

    if (!targetHeader) {
        sortIndex = 2; // Column index 2 handles default sorting correctly for both Proj Value AND Live Pts
        targetHeader = document.querySelectorAll('#leaderboard-table th')[sortIndex];
        forceDesc = true;
    }

    if (targetHeader) sortTable(targetHeader, sortIndex, forceDesc);
}

function sortTable(thElement, colIndex, forceDesc = false) {
    const table = thElement.closest("table");
    const tbody = table.querySelector("tbody");
    const rows = Array.from(tbody.querySelectorAll("tr"));
    let isAscending = thElement.classList.contains("asc");
    
    if (forceDesc) isAscending = true; 
    
    table.querySelectorAll("th").forEach(th => {
        th.classList.remove("asc", "desc");
    });

    thElement.classList.add(isAscending ? "desc" : "asc");
    const dirModifier = isAscending ? -1 : 1;

    rows.sort((a, b) => {
        const aText = a.cells[colIndex].textContent.trim().replace(/[$,x]/g, '');
        const bText = b.cells[colIndex].textContent.trim().replace(/[$,x]/g, '');
        const aVal = isNaN(parseFloat(aText)) ? aText : parseFloat(aText);
        const bVal = isNaN(parseFloat(bText)) ? bText : parseFloat(bText);

        if (aVal > bVal) return 1 * dirModifier;
        if (aVal < bVal) return -1 * dirModifier;
        return 0;
    });

    rows.forEach(row => tbody.appendChild(row));

    let currentRank = 1;
    rows.forEach(row => {
        if (row.style.display !== 'none') {
            row.querySelector('.col-rank').textContent = currentRank++;
        }
    });
}

// ==========================================================
// SILENT REFRESH LOGIC (Only runs on Live Leaderboard Pages)
// ==========================================================
{% if current_pos == 'live-slate-leaderboard' %}
setInterval(() => {
    fetch(window.location.href, { cache: 'no-store' })
        .then(response => response.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            
            const newTbody = doc.querySelector('#leaderboard-table tbody');
            const currentTbody = document.querySelector('#leaderboard-table tbody');
            
            if (newTbody && currentTbody) {
                const scrollContainer = document.getElementById('table-scroll-container');
                const scrollTop = scrollContainer.scrollTop;
                const scrollLeft = scrollContainer.scrollLeft;
                
                const slateSelector = document.getElementById('slate-selector');
                const currentSlate = slateSelector ? slateSelector.value : 'all';

                currentTbody.innerHTML = newTbody.innerHTML;
                filterSlate(currentSlate, true);

                scrollContainer.scrollTop = scrollTop;
                scrollContainer.scrollLeft = scrollLeft;
            }
        })
        .catch(error => console.error('Silent refresh failed:', error));
}, 60000); 
{% endif %}
</script>
</body>
</html>
"""

# =========================================================================
# --- 6. EXECUTION LOOP ---
# =========================================================================
def get_target_slate_date():
    now = datetime.now(ZoneInfo("America/New_York"))
    if now.hour < 3: now = now - timedelta(days=1)
    return now.strftime("%Y-%m-%d")

def main():
    today_str = get_target_slate_date()
    target_pattern = f"games_{today_str}.json"
    target_path = os.path.join(DAILY_FILES_DIR, target_pattern)

    if not os.path.exists(target_path):
        import glob
        all_json_files = glob.glob(os.path.join(DAILY_FILES_DIR, "games_*.json"))
        if all_json_files:
            all_json_files.sort(reverse=True)
            target_path = all_json_files[0]
            today_str = os.path.basename(target_path).replace("games_", "").replace(".json", "")
        else:
            return

    with open(target_path, "r", encoding="utf-8") as f:
        data_stream = json.load(f)

    # 1. Load live data (handles live_mlb_YYYY-MM-DD.json and live_YYYY-MM-DD.json)
    live_data_raw = {}
    live_path_mlb = os.path.join(LIVE_FILES_DIR, f"live_mlb_{today_str}.json")
    live_path_std = os.path.join(LIVE_FILES_DIR, f"live_{today_str}.json")
    
    target_live_path = live_path_mlb if os.path.exists(live_path_mlb) else live_path_std

    if os.path.exists(target_live_path):
        try:
            with open(target_live_path, "r", encoding="utf-8") as f:
                live_data_raw = json.load(f)
        except Exception as e:
            print(f"⚠️ Warning: Could not parse live file: {e}")

    # Flatten nested game JSON into a direct player ID map
    flat_live_data = flatten_live_data(live_data_raw)

    games_list = data_stream.get("games", []) if isinstance(data_stream, dict) else data_stream
    slates_dictionary = data_stream.get("slates", {"fanduel": [], "draftkings": []}) if isinstance(data_stream, dict) else {"fanduel": [], "draftkings": []}

    dk_slate_map = {str(s["id"]).strip(): str(s["name"]) for s in slates_dictionary.get("draftkings", []) if "id" in s}
    fd_slate_map = {str(s["id"]).strip(): str(s["name"]) for s in slates_dictionary.get("fanduel", []) if "id" in s}

    has_dk_data = False
    has_fd_data = False

    # Check for salary presence, skipping postponed games
    for game in games_list:
        game_raw = game.get("gameRaw", {})
        game_status = game_raw.get("status", {}).get("abstractGameState", "")
        detailed_status = game_raw.get("status", {}).get("detailedState", "")
        status_code = game_raw.get("status", {}).get("statusCode", "")

        # Skip postponed games individually
        if "Postponed" in game_status or "Postponed" in detailed_status or "PPD" in detailed_status or status_code == "C":
            continue

        p_data = game.get("projectedLineups", {})
        for side in ["away", "home"]:
            batters = p_data.get(side, {}).get("battingOrder", [])
            pitcher = p_data.get(side, {}).get("startingPitcher", {})
            if any(b.get("dk_salary", 0) > 0 for b in batters) or pitcher.get("dk_salary", 0) > 0: has_dk_data = True
            if any(b.get("salary", 0) > 0 for b in batters) or pitcher.get("salary", 0) > 0: has_fd_data = True

    dk_pools = {"pitchers": [], "catchers": [], "first-base": [], "second-base": [], "third-base": [], "shortstops": [], "outfielders": [], "util": []}
    fd_pools = {"pitchers": [], "catchers-first-base": [], "second-base": [], "third-base": [], "shortstops": [], "outfielders": [], "util": []}
    dk_live_pool, fd_live_pool = [], []

    # Main player extraction loop
    for game in games_list:
        game_raw = game.get("gameRaw", {})
        game_status = game_raw.get("status", {}).get("abstractGameState", "")
        detailed_status = game_raw.get("status", {}).get("detailedState", "")
        status_code = game_raw.get("status", {}).get("statusCode", "")

        # Skip postponed games individually to handle doubleheaders cleanly
        if "Postponed" in game_status or "Postponed" in detailed_status or "PPD" in detailed_status or status_code == "C":
            continue

        p_data = game.get("projectedLineups", {})
        away_name, away_id = get_team_data(game, "away")
        home_name, home_id = get_team_data(game, "home")

        for side, team_name, team_id, opp_name, opp_id, is_home in [
            ("away", away_name, away_id, home_name, home_id, False), 
            ("home", home_name, home_id, away_name, away_id, True)
        ]:
            side_node = p_data.get(side, {})
            official_players_raw = game_raw.get("lineups", {}).get(f"{side}Players", [])
            is_official = len(official_players_raw) > 0
            official_ids = [str(p.get("id")) for p in official_players_raw]
            
            pitcher = side_node.get("startingPitcher")
            if pitcher:
                pid = str(pitcher.get("id"))
                prob_id = str(game_raw.get("teams", {}).get(side, {}).get("probablePitcher", {}).get("id", ""))
                lineup_pos = "P"
                order_status = "official" if (is_official and (prob_id == pid or pid in official_ids)) else ("ns" if is_official else "projected")

                if has_dk_data:
                    p_res = process_proprietary_projection(pitcher, True, team_name, team_id, opp_name, opp_id, is_home, game, is_dk=True, lineup_pos=lineup_pos, order_status=order_status)
                    if p_res: 
                        dk_pools["pitchers"].append(p_res)
                        l_res = process_live_leaderboard_player(p_res, flat_live_data, "dk")
                        if l_res: dk_live_pool.append(l_res)

                if has_fd_data:
                    p_res = process_proprietary_projection(pitcher, True, team_name, team_id, opp_name, opp_id, is_home, game, is_dk=False, lineup_pos=lineup_pos, order_status=order_status)
                    if p_res: 
                        fd_pools["pitchers"].append(p_res)
                        l_res = process_live_leaderboard_player(p_res, flat_live_data, "fd")
                        if l_res: fd_live_pool.append(l_res)

            for batter in side_node.get("battingOrder", []):
                bid = str(batter.get("id"))
                lineup_pos = str(batter.get("order", ""))
                order_status = "official" if (is_official and bid in official_ids) else ("ns" if is_official else "projected")

                if has_dk_data:
                    p_res = process_proprietary_projection(batter, False, team_name, team_id, opp_name, opp_id, is_home, game, is_dk=True, lineup_pos=lineup_pos, order_status=order_status)
                    if p_res:
                        dk_pools["util"].append(p_res)
                        dk_positions = str(batter.get("dk_positions", "")).upper().split("/")
                        for raw_pos in dk_positions:
                            if "P" in raw_pos: dk_pools["pitchers"].append(p_res)
                            elif "C" == raw_pos: dk_pools["catchers"].append(p_res)
                            elif "1B" == raw_pos: dk_pools["first-base"].append(p_res)
                            elif "2B" == raw_pos: dk_pools["second-base"].append(p_res)
                            elif "3B" == raw_pos: dk_pools["third-base"].append(p_res)
                            elif "SS" == raw_pos: dk_pools["shortstops"].append(p_res)
                            elif "OF" in raw_pos: dk_pools["outfielders"].append(p_res)
                            
                        l_res = process_live_leaderboard_player(p_res, flat_live_data, "dk")
                        if l_res: dk_live_pool.append(l_res)

                if has_fd_data:
                    p_res = process_proprietary_projection(batter, False, team_name, team_id, opp_name, opp_id, is_home, game, is_dk=False, lineup_pos=lineup_pos, order_status=order_status)
                    if p_res:
                        fd_pools["util"].append(p_res)
                        fd_positions = str(batter.get("fd_positions", "")).upper().split("/")
                        for raw_pos in fd_positions:
                            if "P" in raw_pos: fd_pools["pitchers"].append(p_res)
                            elif "C" in raw_pos or "1B" in raw_pos: fd_pools["catchers-first-base"].append(p_res)
                            elif "2B" in raw_pos: fd_pools["second-base"].append(p_res)
                            elif "3B" in raw_pos: fd_pools["third-base"].append(p_res)
                            elif "SS" in raw_pos: fd_pools["shortstops"].append(p_res)
                            elif "OF" in raw_pos: fd_pools["outfielders"].append(p_res)

                        l_res = process_live_leaderboard_player(p_res, flat_live_data, "fd")
                        if l_res: fd_live_pool.append(l_res)

    for key in dk_pools: dk_pools[key] = sorted(dk_pools[key], key=lambda x: x["value"], reverse=True)
    for key in fd_pools: fd_pools[key] = sorted(fd_pools[key], key=lambda x: x["value"], reverse=True)
    dk_live_pool = sorted(dk_live_pool, key=lambda x: x["proj"], reverse=True)
    fd_live_pool = sorted(fd_live_pool, key=lambda x: x["proj"], reverse=True)

    def render_static_html(seo_title, seo_desc, page_url, page_heading, platform_name, platform_slug, current_pos, position_links, date_str, players_list, distinct_slates, score_col_name="Proj"):
        try:
            from jinja2 import Template
            t = Template(HTML_TEMPLATE)
            return t.render(
                seo_title=seo_title, seo_desc=seo_desc, page_url=page_url, page_heading=page_heading, 
                platform_name=platform_name, platform_slug=platform_slug, current_pos=current_pos,
                position_links=position_links, date_str=date_str, players=players_list, 
                distinct_slates=distinct_slates, score_col_name=score_col_name
            )
        except ImportError:
            return "Jinja2 dependency required."

    generated_urls = []
    base_domain = "https://mlbstartingnine.com"

    if has_dk_data:
        for pos_slug, player_set in dk_pools.items():
            folder_path = os.path.join(OUTPUT_BASE_DIR, "draftkings", f"top-{pos_slug}")
            os.makedirs(folder_path, exist_ok=True)
            meta = SEO_METADATA["draftkings"].get(pos_slug, {"title": f"DraftKings {pos_slug.title()}", "desc": "MLB Projections"})
            clean_title = "Utility (All Hitters)" if pos_slug == "util" else pos_slug.replace("-", " ").title()
            page_url = f"{base_domain}/dfs/draftkings/top-{pos_slug}/"
            html_output = render_static_html(meta["title"], meta["desc"], page_url, f"Top Projected DraftKings {clean_title}", "DraftKings", "draftkings", pos_slug, POS_LABELS_DK, today_str, player_set, dk_slate_map)
            with open(os.path.join(folder_path, "index.html"), "w", encoding="utf-8") as file: file.write(html_output)
            generated_urls.append(page_url)

        if dk_live_pool:
            folder_path = os.path.join(OUTPUT_BASE_DIR, "draftkings", "live-slate-leaderboard")
            os.makedirs(folder_path, exist_ok=True)
            meta = SEO_METADATA["draftkings"]["live-slate-leaderboard"]
            page_url = f"{base_domain}/dfs/draftkings/live-slate-leaderboard/"
            html_output = render_static_html(meta["title"], meta["desc"], page_url, "Live DraftKings Slate Leaderboard", "DraftKings", "draftkings", "live-slate-leaderboard", POS_LABELS_DK, today_str, dk_live_pool, dk_slate_map, "Live Pts")
            with open(os.path.join(folder_path, "index.html"), "w", encoding="utf-8") as file: file.write(html_output)
            generated_urls.append(page_url)

    if has_fd_data:
        for pos_slug, player_set in fd_pools.items():
            folder_path = os.path.join(OUTPUT_BASE_DIR, "fanduel", f"top-{pos_slug}")
            os.makedirs(folder_path, exist_ok=True)
            meta = SEO_METADATA["fanduel"].get(pos_slug, {"title": f"FanDuel {pos_slug.title()}", "desc": "MLB Projections"})
            clean_title = "Utility" if pos_slug == "util" else pos_slug.replace("-", " ").title()
            if "Catchers" in clean_title: clean_title = "C / 1B Split"
            page_url = f"{base_domain}/dfs/fanduel/top-{pos_slug}/"
            html_output = render_static_html(meta["title"], meta["desc"], page_url, f"Top Projected FanDuel {clean_title}", "FanDuel", "fanduel", pos_slug, POS_LABELS_FD, today_str, player_set, fd_slate_map)
            with open(os.path.join(folder_path, "index.html"), "w", encoding="utf-8") as file: file.write(html_output)
            generated_urls.append(page_url)

        if fd_live_pool:
            folder_path = os.path.join(OUTPUT_BASE_DIR, "fanduel", "live-slate-leaderboard")
            os.makedirs(folder_path, exist_ok=True)
            meta = SEO_METADATA["fanduel"]["live-slate-leaderboard"]
            page_url = f"{base_domain}/dfs/fanduel/live-slate-leaderboard/"
            html_output = render_static_html(meta["title"], meta["desc"], page_url, "Live FanDuel Slate Leaderboard", "FanDuel", "fanduel", "live-slate-leaderboard", POS_LABELS_FD, today_str, fd_live_pool, fd_slate_map, "Live Pts")
            with open(os.path.join(folder_path, "index.html"), "w", encoding="utf-8") as file: file.write(html_output)
            generated_urls.append(page_url)

    if generated_urls:
        sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        for url in generated_urls:
            sitemap_xml += f"  <url>\n    <loc>{url}</loc>\n    <lastmod>{today_str}</lastmod>\n    <changefreq>daily</changefreq>\n    <priority>0.8</priority>\n  </url>\n"
        sitemap_xml += '</urlset>'
        with open(SITEMAP_PATH, "w", encoding="utf-8") as f: f.write(sitemap_xml)

if __name__ == "__main__":
    main()
