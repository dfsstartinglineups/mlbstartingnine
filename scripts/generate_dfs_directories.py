import os
import json
import re
import datetime
import unicodedata

# =========================================================================
# --- 1. DYNAMIC PATH ROUTING (Adjusted for /scripts/ folder) ---
# =========================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

DATA_DIR = os.path.join(ROOT_DIR, "data")
DAILY_FILES_DIR = os.path.join(DATA_DIR, "daily_files")
PLAYER_MASTER_PATH = os.path.join(DATA_DIR, "player_master_data.json")
OUTPUT_BASE_DIR = os.path.join(ROOT_DIR, "dfs")
SITEMAP_PATH = os.path.join(ROOT_DIR, "sitemap-dfs.xml")

# Nudge Matrix Thresholds
TEAM_MEGA_SCORE = 5.5
TEAM_MEGA_BOOST = 0.050
TEAM_ELITE_SCORE = 5.0
TEAM_ELITE_BOOST = 0.035
TEAM_GOOD_SCORE = 4.5
TEAM_GOOD_BOOST = 0.025
TEAM_BAD_SCORE = 3.5
TEAM_BAD_PENALTY = -0.050

# =========================================================================
# --- 2. SEO METADATA MATRIX ---
# =========================================================================
SEO_METADATA = {
    "draftkings": {
        "pitchers": {"title": "Top DraftKings Pitcher Projections Today - DFS Lineup Values", "desc": "Optimized DraftKings pitcher projections for today's MLB slate. Discover proprietary value ratings, projected stats, and custom vegas splits."},
        "catchers": {"title": "Best DraftKings Catchers Today - Daily Fantasy C Projections", "desc": "Daily fantasy baseball rankings for DraftKings catchers. View calculated values, salaries, and platoon advantages for today's games."},
        "first-base": {"title": "Top DraftKings 1B Projections Today - Elite First Base Value", "desc": "Analyze today's DraftKings first base projections. Get proprietary performance multipliers, matchup stats, and salary rankings."},
        "second-base": {"title": "Optimized DraftKings 2B Value Picks Today - DFS Rankings", "desc": "Unlock top-rated DraftKings second base projections. Real-time situational performance matrices for today's fantasy baseball slates."},
        "third-base": {"title": "Best DraftKings 3B Projections Today - Daily Fantasy Third Base", "desc": "Premium DraftKings third base projections featuring advanced park factor adjustments, batting order weights, and optimizer data."},
        "shortstops": {"title": "Top DraftKings Shortstop Picks Today - Advanced SS Projections", "desc": "Compare daily fantasy shortstop values on DraftKings. Updated projections utilizing proprietary BvP and Vegas linescoring data."},
        "outfielders": {"title": "Best DraftKings Outfield Projections Today - DFS OF Value Grid", "desc": "Comprehensive DraftKings outfield rankings and value projections for today's MLB slate. Filter by individual main and late slates instantly."}
    },
    "fanduel": {
        "pitchers": {"title": "Top FanDuel Pitcher Projections Today - Daily Fantasy Baseball", "desc": "Maximize your FanDuel pitching slot with real-time projections, advanced umpire data, and proprietary situational matchup scoring."},
        "catchers-first-base": {"title": "Best FanDuel C/1B Projections Today - Catchers & First Base Value", "desc": "Optimized FanDuel combined Catcher and First Base projections. View real-time value scores adjusted for park metrics and platoon splits."},
        "second-base": {"title": "Top FanDuel 2B Rankings Today - Daily Fantasy Second Base Picks", "desc": "Find the highest-value second basemen on FanDuel today. Projections calculated via proprietary live vegas total adjustments."},
        "third-base": {"title": "Optimized FanDuel 3B Projections Today - Fantasy Third Base Value", "desc": "Advanced FanDuel third base projections. Tap into custom hitter multipliers and game environment tracking data for today's games."},
        "shortstops": {"title": "Best FanDuel Shortstop Picks Today - DFS SS Rankings", "desc": "Daily updated FanDuel shortstop projections. Real-time value tiers using current matchup analytics and confirmed official starting lineups."},
        "outfielders": {"title": "Top FanDuel Outfield Projections Today - DFS Outfielder Rankings", "desc": "Deep-dive FanDuel outfielder value tables. The ultimate tool for finding elite, mid-tier, and value salary plays for tonight's slates."}
    }
}

# =========================================================================
# --- 3. URL SLUG AND LOOKUP UTILITIES ---
# =========================================================================
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
# --- 4. PROPRIETARY ALGORITHM NUDGES ---
# =========================================================================
def get_team_name(game_node, side):
    """Safely extracts full team names instead of abbreviations."""
    if f"{side}Team" in game_node and isinstance(game_node[f"{side}Team"], dict) and "name" in game_node[f"{side}Team"]:
        return game_node[f"{side}Team"]["name"]
    raw_teams = game_node.get("gameRaw", {}).get("teams", {})
    if side in raw_teams and "team" in raw_teams[side] and "name" in raw_teams[side]["team"]:
        return raw_teams[side]["team"]["name"]
    return "AWAY" if side == "away" else "HOME"

def calculate_vegas_nudge(itt):
    if itt >= TEAM_MEGA_SCORE: return TEAM_MEGA_BOOST
    elif itt >= TEAM_ELITE_SCORE: return TEAM_ELITE_BOOST
    elif itt >= TEAM_GOOD_SCORE: return TEAM_GOOD_BOOST
    elif 0 < itt <= TEAM_BAD_SCORE: return TEAM_BAD_PENALTY
    return 0.0

def process_proprietary_projection(player, is_pitcher, team_name, opp_name, is_home, game, is_dk=False):
    raw_proj = float(player.get("dk_proj" if is_dk else "proj", 0.0))
    salary = int(player.get("dk_salary" if is_dk else "salary", 0))
    
    if raw_proj <= 0 or salary <= 0:
        return None

    slate_block = player.get("dk_slates" if is_dk else "fd_slates", {})
    slate_ids = list(slate_block.keys()) if isinstance(slate_block, dict) else []

    odds = game.get("odds", {})
    total = 0.0
    
    if odds and "bookmakers" in odds and len(odds["bookmakers"]) > 0:
        market_totals = odds["bookmakers"][0].get("markets", [])
        for m in market_totals:
            if m["key"] == "totals" and m["outcomes"]:
                total = float(m["outcomes"][0].get("point", 0.0))
    
    away_itt = round(total / 2.0, 2) if total > 0 else 4.2
    home_itt = round(total / 2.0, 2) if total > 0 else 4.2
    
    my_itt = home_itt if is_home else away_itt
    opp_itt = away_itt if is_home else home_itt

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

    if is_pitcher:
        hitter_mult = 1.00 - (calculate_vegas_nudge(opp_itt) + park_nudge)
        final_proj = round(raw_proj * hitter_mult, 2)
    else:
        hitter_mult = 1.00 + vegas_nudge + order_nudge + park_nudge
        final_proj = round(raw_proj * hitter_mult, 2)

    value = round(final_proj / (salary / 1000), 2) if salary > 0 else 0.0

    return {
        "id": player.get("id"),
        "name": player.get("name") or player.get("fullName"),
        "team": team_name,
        "opponent": f"vs. {opp_name}" if is_home else f"@ {opp_name}",
        "salary": salary,
        "proj": final_proj,
        "value": value,
        "slates": ",".join(slate_ids),
        "url": get_player_url(player.get("id"), player.get("name") or player.get("fullName"))
    }

# =========================================================================
# --- 5. THE JINJA2 MASTER HTML DIRECTORY TEMPLATE ---
# =========================================================================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    
    <!-- Favicons -->
    <link rel="icon" href="/favicon.ico" sizes="any">
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">

    <title>{{ seo_title }}</title>
    <meta name="description" content="{{ seo_desc }}">
    
    <!-- Open Graph Tags -->
    <meta property="og:site_name" content="MLB Starting Nine">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{{ page_url }}">
    <meta property="og:title" content="{{ seo_title }}">
    <meta property="og:description" content="{{ seo_desc }}">
    <meta property="og:image" content="https://mlbstartingnine.com/mlb-social-share.jpg">

    <!-- Twitter Card Tags -->
    <meta name="twitter:card" content="summary">
    <meta property="twitter:domain" content="mlbstartingnine.com">
    <meta property="twitter:url" content="{{ page_url }}">
    <meta name="twitter:title" content="{{ seo_title }}">
    <meta name="twitter:description" content="{{ seo_desc }}">
    <meta name="twitter:image" content="https://mlbstartingnine.com/mlb-social-share.jpg">

    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f4f7f6; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        
        /* Updated MLB Starting Nine Header Style */
        .header-brand { 
            font-weight: 900; 
            letter-spacing: -1px; 
            font-size: 2rem; 
            color: #fff; 
            font-style: italic; 
            text-shadow: 0 2px 4px rgba(0,0,0,0.5); 
        }
        .header-brand a { color: inherit; text-decoration: none; }
        .header-brand span { 
            text-shadow: none !important;
            background: linear-gradient(to bottom, #7CD0FF 0%, #1A8CFF 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            filter: drop-shadow(0 0 12px rgba(26, 140, 255, 0.8));
            padding-right: 2px; 
            display: inline-block; 
        }

        .table-card { border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border: 1px solid #dee2e6; overflow: hidden; background: #fff; }
        .table th { background-color: #212529; color: #fff; font-size: 0.75rem; text-transform: uppercase; font-weight: 700; padding: 12px; }
        .table td { vertical-align: middle; padding: 10px 12px; font-size: 0.85rem; border-bottom: 1px solid #edf2f4; }
        .player-link { font-weight: 700; color: #212529; text-decoration: none; }
        .player-link:hover { color: #0d6efd; text-decoration: underline; }
        .disclaimer-box { background-color: #fff9db; border: 1px solid #ffe3e3; border-radius: 6px; font-size: 0.75rem; color: #616161; line-height: 1.4; }
        .team-icon { width: 16px; height: 16px; margin-right: 6px; vertical-align: text-bottom; }
    </style>
</head>
<body>

<nav class="navbar shadow-sm py-3 mb-2" style="background-color: #212529;">
    <div class="container d-flex justify-content-between align-items-center flex-wrap">
        <div class="header-brand mb-2 mb-md-0">
            <a href="/" class="text-decoration-none">MLB Starting <span>Nine</span></a>
        </div>
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

    <!-- Dropdown Slate Row Filtering -->
    {% if distinct_slates %}
    <div class="d-flex align-items-center gap-2 mb-3">
        <span class="fw-bold text-secondary small text-uppercase">Slates:</span>
        <select class="form-select form-select-sm w-auto fw-bold" id="slate-selector" onchange="filterSlate(this.value)">
            <option value="all">All Games</option>
            {% for s_id, s_name in distinct_slates.items() %}
            <option value="{{ s_id }}">{{ s_name }}</option>
            {% endfor %}
        </select>
    </div>
    {% endif %}

    <!-- Proprietary Metric Disclaimer Box -->
    <div class="disclaimer-box p-3 mb-4 shadow-sm">
        <strong>Disclaimer Algorithm Note:</strong> The daily predictions displayed below are generated through the proprietary <code>mlbstartingnine.com</code> analytics system. Our engine alters baseline performance profiles by cross-checking real-time stadium indices, historical hitter platoon margins, and shifting Vegas bookmaker implied configurations to establish contextual DFS values.
    </div>

    <!-- Core Dynamic Data Directory Table -->
    <div class="table-card shadow-sm">
        <div class="table-responsive">
            <table class="table table-hover mb-0" id="leaderboard-table">
                <thead>
                    <tr>
                        <th style="width: 5%;">Rank</th>
                        <th>Player</th>
                        <th>Team</th>
                        <th>Matchup</th>
                        <th class="text-end">Salary</th>
                        <th class="text-end">Proj</th>
                        <th class="text-end text-primary">Value</th>
                    </tr>
                </thead>
                <tbody>
                    {% for p in players %}
                    <tr data-slates="{{ p.slates }}">
                        <td class="fw-bold text-muted">{{ loop.index }}</td>
                        <td>
                            <div class="d-flex align-items-center">
                                <img src="https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_64,q_auto:best/v1/people/{{ p.id }}/headshot/67/current" alt="headshot" class="rounded-circle me-2" style="width: 32px; height: 32px; object-fit: cover; border: 1px solid #ced4da;">
                                <a href="{{ p.url }}" class="player-link">{{ p.name }}</a>
                            </div>
                        </td>
                        <td>
                            <span class="badge bg-light text-dark border d-flex align-items-center" style="width: fit-content;">
                                <img src="image_a3cc42.png" alt="Team Icon" class="team-icon"> {{ p.team }}
                            </span>
                        </td>
                        <td class="text-muted font-monospace">
                            <div class="d-flex align-items-center">
                                <img src="image_a3cc42.png" alt="Team Icon" class="team-icon"> {{ p.opponent }}
                            </div>
                        </td>
                        <td class="text-end fw-semibold">${{ "{:,}".format(p.salary) }}</td>
                        <td class="text-end fw-bold">{{ p.proj }}</td>
                        <td class="text-end fw-bold text-success">{{ p.value }}x</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>

<script>
function filterSlate(slateId) {
    const rows = document.querySelectorAll('#leaderboard-table tbody tr');
    rows.forEach(row => {
        if (slateId === 'all') {
            row.style.display = '';
            return;
        }
        const rowSlates = row.getAttribute('data-slates').split(',');
        if (rowSlates.includes(slateId)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}
</script>
</body>
</html>
"""

# =========================================================================
# --- 6. COMPILING & BUILDING EXECUTION LOOP ---
# =========================================================================
def main():
    today_str = datetime.date.today().strftime("%Y-%m-%d")
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
            print(f"❌ Error: No games JSON files discovered inside directory: {DAILY_FILES_DIR}")
            return

    print(f"📂 Processing Live JSON Source Stream: {target_path}")
    with open(target_path, "r", encoding="utf-8") as f:
        data_stream = json.load(f)

    games_list = data_stream.get("games", []) if isinstance(data_stream, dict) else data_stream
    slates_dictionary = data_stream.get("slates", {"fanduel": [], "draftkings": []}) if isinstance(data_stream, dict) else {"fanduel": [], "draftkings": []}

    dk_slate_map = {s["id"]: s["name"] for s in slates_dictionary.get("draftkings", []) if "id" in s}
    fd_slate_map = {s["id"]: s["name"] for s in slates_dictionary.get("fanduel", []) if "id" in s}

    has_dk_data = False
    has_fd_data = False

    for game in games_list:
        p_data = game.get("projectedLineups", {})
        for side in ["away", "home"]:
            batters = p_data.get(side, {}).get("battingOrder", [])
            pitcher = p_data.get(side, {}).get("startingPitcher", {})
            
            if any(b.get("dk_salary", 0) > 0 for b in batters) or pitcher.get("dk_salary", 0) > 0:
                has_dk_data = True
            if any(b.get("salary", 0) > 0 for b in batters) or pitcher.get("salary", 0) > 0:
                has_fd_data = True

    print(f"🏁 Constraint Status Check -> DraftKings Data Found: {has_dk_data} | FanDuel Data Found: {has_fd_data}")

    dk_pools = {"pitchers": [], "catchers": [], "first-base": [], "second-base": [], "third-base": [], "shortstops": [], "outfielders": []}
    fd_pools = {"pitchers": [], "catchers-first-base": [], "second-base": [], "third-base": [], "shortstops": [], "outfielders": []}

    for game in games_list:
        p_data = game.get("projectedLineups", {})
        
        # Use full team names instead of abbreviations
        away_team = get_team_name(game, "away")
        home_team = get_team_name(game, "home")

        # Properly match side block with correct context flags
        for side, team, opp, is_home in [("away", away_team, home_team, False), ("home", home_team, away_team, True)]:
            side_node = p_data.get(side, {})
            
            pitcher = side_node.get("startingPitcher")
            if pitcher:
                if has_dk_data:
                    p_res = process_proprietary_projection(pitcher, True, team, opp, is_home, game, is_dk=True)
                    if p_res: dk_pools["pitchers"].append(p_res)
                if has_fd_data:
                    p_res = process_proprietary_projection(pitcher, True, team, opp, is_home, game, is_dk=False)
                    if p_res: fd_pools["pitchers"].append(p_res)

            for batter in side_node.get("battingOrder", []):
                if has_dk_data:
                    p_res = process_proprietary_projection(batter, False, team, opp, is_home, game, is_dk=True)
                    if p_res:
                        dk_positions = str(batter.get("dk_positions", "")).upper().split("/")
                        for raw_pos in dk_positions:
                            if "P" in raw_pos: dk_pools["pitchers"].append(p_res)
                            elif "C" == raw_pos: dk_pools["catchers"].append(p_res)
                            elif "1B" == raw_pos: dk_pools["first-base"].append(p_res)
                            elif "2B" == raw_pos: dk_pools["second-base"].append(p_res)
                            elif "3B" == raw_pos: dk_pools["third-base"].append(p_res)
                            elif "SS" == raw_pos: dk_pools["shortstops"].append(p_res)
                            elif "OF" in raw_pos: dk_pools["outfielders"].append(p_res)

                if has_fd_data:
                    p_res = process_proprietary_projection(batter, False, team, opp, is_home, game, is_dk=False)
                    if p_res:
                        fd_positions = str(batter.get("fd_positions", "")).upper().split("/")
                        for raw_pos in fd_positions:
                            if "P" in raw_pos: fd_pools["pitchers"].append(p_res)
                            elif "C" in raw_pos or "1B" in raw_pos: fd_pools["catchers-first-base"].append(p_res)
                            elif "2B" in raw_pos: fd_pools["second-base"].append(p_res)
                            elif "3B" in raw_pos: fd_pools["third-base"].append(p_res)
                            elif "SS" in raw_pos: fd_pools["shortstops"].append(p_res)
                            elif "OF" in raw_pos: fd_pools["outfielders"].append(p_res)

    for key in dk_pools:
        dk_pools[key] = sorted(dk_pools[key], key=lambda x: x["value"], reverse=True)
    for key in fd_pools:
        fd_pools[key] = sorted(fd_pools[key], key=lambda x: x["value"], reverse=True)

    def render_static_html(seo_title, seo_desc, page_url, page_heading, platform_name, date_str, players_list, distinct_slates):
        try:
            from jinja2 import Template
            t = Template(HTML_TEMPLATE)
            return t.render(
                seo_title=seo_title, 
                seo_desc=seo_desc, 
                page_url=page_url,
                page_heading=page_heading, 
                platform_name=platform_name, 
                date_str=date_str, 
                players=players_list, 
                distinct_slates=distinct_slates
            )
        except ImportError:
            return "Jinja2 parsing engine dependency required to compile static structure outputs."

    # URLs for the Sitemap & OG Tags
    generated_urls = []
    base_domain = "https://mlbstartingnine.com"

    if has_dk_data:
        for pos_slug, player_set in dk_pools.items():
            folder_path = os.path.join(OUTPUT_BASE_DIR, "draftkings", f"top-{pos_slug}")
            os.makedirs(folder_path, exist_ok=True)
            
            meta = SEO_METADATA["draftkings"].get(pos_slug, {"title": f"DraftKings {pos_slug.title()}", "desc": "MLB Projections"})
            clean_title = pos_slug.replace("-", " ").title()
            page_url = f"{base_domain}/dfs/draftkings/top-{pos_slug}/"

            html_output = render_static_html(
                seo_title=meta["title"],
                seo_desc=meta["desc"],
                page_url=page_url,
                page_heading=f"DraftKings {clean_title} Leaderboard",
                platform_name="DraftKings",
                date_str=today_str,
                players_list=player_set,
                distinct_slates=dk_slate_map
            )
            with open(os.path.join(folder_path, "index.html"), "w", encoding="utf-8") as file:
                file.write(html_output)
            
            generated_urls.append(page_url)
            
        print("✅ DraftKings Directory Pages Generated.")

    if has_fd_data:
        for pos_slug, player_set in fd_pools.items():
            folder_path = os.path.join(OUTPUT_BASE_DIR, "fanduel", f"top-{pos_slug}")
            os.makedirs(folder_path, exist_ok=True)
            
            meta = SEO_METADATA["fanduel"].get(pos_slug, {"title": f"FanDuel {pos_slug.title()}", "desc": "MLB Projections"})
            clean_title = pos_slug.replace("-", " ").title()
            if "Catchers" in clean_title: clean_title = "C / 1B Split"
            page_url = f"{base_domain}/dfs/fanduel/top-{pos_slug}/"

            html_output = render_static_html(
                seo_title=meta["title"],
                seo_desc=meta["desc"],
                page_url=page_url,
                page_heading=f"FanDuel {clean_title} Leaderboard",
                platform_name="FanDuel",
                date_str=today_str,
                players_list=player_set,
                distinct_slates=fd_slate_map
            )
            with open(os.path.join(folder_path, "index.html"), "w", encoding="utf-8") as file:
                file.write(html_output)
            
            generated_urls.append(page_url)
            
        print("✅ FanDuel Directory Pages Generated.")

    # =========================================================================
    # --- 7. XML SITEMAP GENERATOR ---
    # =========================================================================
    if generated_urls:
        sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        
        for url in generated_urls:
            sitemap_xml += "  <url>\n"
            sitemap_xml += f"    <loc>{url}</loc>\n"
            sitemap_xml += f"    <lastmod>{today_str}</lastmod>\n"
            sitemap_xml += "    <changefreq>daily</changefreq>\n"
            sitemap_xml += "    <priority>0.8</priority>\n"
            sitemap_xml += "  </url>\n"
            
        sitemap_xml += '</urlset>'
        
        with open(SITEMAP_PATH, "w", encoding="utf-8") as f:
            f.write(sitemap_xml)
        print(f"✅ Sitemap successfully generated at true site root: {SITEMAP_PATH}")

if __name__ == "__main__":
    main()
