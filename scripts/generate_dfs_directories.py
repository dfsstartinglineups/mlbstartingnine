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

# Position Dropdown Mappings
POS_LABELS_DK = {
    "pitchers": "Pitchers", "catchers": "Catchers", "first-base": "First Base",
    "second-base": "Second Base", "third-base": "Third Base", 
    "shortstops": "Shortstops", "outfielders": "Outfielders", "util": "Util (All Hitters)"
}
POS_LABELS_FD = {
    "pitchers": "Pitchers", "catchers-first-base": "C / 1B",
    "second-base": "Second Base", "third-base": "Third Base", 
    "shortstops": "Shortstops", "outfielders": "Outfielders", "util": "Utility"
}

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
        "outfielders": {"title": "Best DraftKings Outfield Projections Today - DFS OF Value Grid", "desc": "Comprehensive DraftKings outfield rankings and value projections for today's MLB slate. Filter by individual main and late slates instantly."},
        "util": {"title": "Top DraftKings Hitters Today - DFS Overall Value Rankings", "desc": "View the highest projected DraftKings hitters across all positions. The ultimate leaderboard for finding pure salary value and lineup upside."}
    },
    "fanduel": {
        "pitchers": {"title": "Top FanDuel Pitcher Projections Today - Daily Fantasy Baseball", "desc": "Maximize your FanDuel pitching slot with real-time projections, advanced umpire data, and proprietary situational matchup scoring."},
        "catchers-first-base": {"title": "Best FanDuel C/1B Projections Today - Catchers & First Base Value", "desc": "Optimized FanDuel combined Catcher and First Base projections. View real-time value scores adjusted for park metrics and platoon splits."},
        "second-base": {"title": "Top FanDuel 2B Rankings Today - Daily Fantasy Second Base Picks", "desc": "Find the highest-value second basemen on FanDuel today. Projections calculated via proprietary live vegas total adjustments."},
        "third-base": {"title": "Optimized FanDuel 3B Projections Today - Fantasy Third Base Value", "desc": "Advanced FanDuel third base projections. Tap into custom hitter multipliers and game environment tracking data for today's games."},
        "shortstops": {"title": "Best FanDuel Shortstop Picks Today - DFS SS Rankings", "desc": "Daily updated FanDuel shortstop projections. Real-time value tiers using current matchup analytics and confirmed official starting lineups."},
        "outfielders": {"title": "Top FanDuel Outfield Projections Today - DFS Outfielder Rankings", "desc": "Deep-dive FanDuel outfielder value tables. The ultimate tool for finding elite, mid-tier, and value salary plays for tonight's slates."},
        "util": {"title": "Best FanDuel Utility Projections Today - DFS UTIL Picks", "desc": "Fill your FanDuel Utility slot with the highest value hitters. Optimized projections comparing all non-pitchers on today's main and late MLB slates."}
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

    # Calculate multiplier
    if is_pitcher:
        hitter_mult = 1.00 - (calculate_vegas_nudge(opp_itt) + park_nudge)
    else:
        hitter_mult = 1.00 + vegas_nudge + order_nudge + park_nudge

    # Baseline calculations
    final_proj = round(raw_proj * hitter_mult, 2)
    value = round(final_proj / (salary / 1000), 2) if salary > 0 else 0.0

    # Build slate-specific stats dictionary for dynamic frontend swapping
    slate_stats = {}
    for s_id, s_data in slate_block.items():
        if isinstance(s_data, dict):
            s_raw_proj = float(s_data.get("proj", raw_proj))
            s_salary = int(s_data.get("salary", salary))
            s_final_proj = round(s_raw_proj * hitter_mult, 2)
            s_val = round(s_final_proj / (s_salary / 1000), 2) if s_salary > 0 else 0.0
            
            slate_stats[s_id] = {
                "salary": f"${s_salary:,}",
                "proj": f"{s_final_proj:.2f}",
                "value": f"{s_val:.2f}x"
            }

    return {
        "id": player.get("id"),
        "name": player.get("name") or player.get("fullName"),
        "team": team_name,
        "team_id": team_id,
        "opp_indicator": "vs." if is_home else "@",
        "opp_name": opp_name,
        "opp_id": opp_id,
        "salary": salary,
        "proj": final_proj,
        "value": value,
        "slates": ",".join(slate_ids),
        "slate_stats_json": json.dumps(slate_stats),
        "lineup_pos": lineup_pos,
        "order_status": order_status,
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
    
    <link rel="icon" href="/favicon.ico" sizes="any">
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">

    <title>{{ seo_title }}</title>
    <meta name="description" content="{{ seo_desc }}">
    
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
        .table th { background-color: #212529; color: #fff; font-size: 0.75rem; text-transform: uppercase; font-weight: 700; padding: 12px; cursor: pointer; user-select: none; }
        .table th:hover { background-color: #343a40; }
        .table td { vertical-align: middle; padding: 10px 12px; font-size: 0.85rem; border-bottom: 1px solid #edf2f4; }
        .player-link { font-weight: 700; color: #212529; text-decoration: none; }
        .player-link:hover { color: #0d6efd; text-decoration: underline; }
        .disclaimer-box { background-color: #fff9db; border: 1px solid #ffe3e3; border-radius: 6px; font-size: 0.75rem; color: #616161; line-height: 1.4; }
        
        .team-icon { width: 22px; height: 22px; margin-right: 6px; vertical-align: middle; }
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

    <!-- Dropdown Controls for Slates & Positions -->
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
        
        <div class="d-flex align-items-center gap-2 ms-md-3">
            <span class="fw-bold text-secondary small text-uppercase">Position:</span>
            <select class="form-select form-select-sm w-auto fw-bold" id="position-selector" onchange="window.location.href=this.value">
                {% for pos_key, pos_label in position_links.items() %}
                <option value="/dfs/{{ platform_slug }}/top-{{ pos_key }}/" {% if pos_key == current_pos %}selected{% endif %}>{{ pos_label }}</option>
                {% endfor %}
            </select>
        </div>
    </div>

    <div class="disclaimer-box p-3 mb-4 shadow-sm">
        <strong>Disclaimer Algorithm Note:</strong> The daily predictions displayed below are generated through the proprietary <code>mlbstartingnine.com</code> analytics system. Our engine alters baseline performance profiles by cross-checking real-time stadium indices, historical hitter platoon margins, and shifting Vegas bookmaker implied configurations to establish contextual DFS values.
    </div>

    <div class="table-card shadow-sm">
        <div class="table-responsive">
            <table class="table table-hover mb-0" id="leaderboard-table">
                <thead>
                    <tr>
                        <th style="width: 5%;" onclick="sortTable(this, 0)">Rank &#x21D5;</th>
                        <th onclick="sortTable(this, 1)">Player &#x21D5;</th>
                        <th onclick="sortTable(this, 2)">Team &#x21D5;</th>
                        <th onclick="sortTable(this, 3)">Matchup &#x21D5;</th>
                        <th class="text-end" onclick="sortTable(this, 4)">Salary &#x21D5;</th>
                        <th class="text-end" onclick="sortTable(this, 5)">Proj &#x21D5;</th>
                        <th class="text-end text-primary" onclick="sortTable(this, 6)">Value &#x21D5;</th>
                    </tr>
                </thead>
                <tbody>
                    {% for p in players %}
                    <tr data-slates="{{ p.slates }}" 
                        data-slate-stats='{{ p.slate_stats_json }}' 
                        data-default-salary="${{ "{:,}".format(p.salary) }}" 
                        data-default-proj="{{ p.proj }}" 
                        data-default-value="{{ p.value }}x">
                        
                        <td class="fw-bold text-muted col-rank">{{ loop.index }}</td>
                        <td>
                            <div class="d-flex align-items-center">
                                {% if p.order_status == 'official' %}
                                    <span class="badge bg-success me-2 shadow-sm d-inline-block text-center" style="font-size: 0.65rem; width: 30px;" title="Official Lineup Position">{{ p.lineup_pos }}</span>
                                {% elif p.order_status == 'projected' %}
                                    <span class="badge bg-warning text-dark me-2 shadow-sm d-inline-block text-center" style="font-size: 0.65rem; width: 30px;" title="Projected Lineup Position">{{ p.lineup_pos }}</span>
                                {% elif p.order_status == 'ns' %}
                                    <span class="badge bg-danger me-2 shadow-sm d-inline-block text-center" style="font-size: 0.65rem; width: 30px;" title="Not Starting">NS</span>
                                {% endif %}
                                
                                <img src="https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_64,q_auto:best/v1/people/{{ p.id }}/headshot/67/current" alt="headshot" class="rounded-circle me-2" style="width: 32px; height: 32px; object-fit: cover; border: 1px solid #ced4da;">
                                <a href="{{ p.url }}" class="player-link">{{ p.name }}</a>
                            </div>
                        </td>
                        <td>
                            <span class="badge bg-light text-dark border d-flex align-items-center" style="width: fit-content; font-size: 0.85rem;">
                                <img src="https://www.mlbstatic.com/team-logos/{{ p.team_id }}.svg" alt="{{ p.team }} Icon" class="team-icon"> {{ p.team }}
                            </span>
                        </td>
                        <td class="text-muted font-monospace fw-semibold">
                            <div class="d-flex align-items-center">
                                {{ p.opp_indicator }} <img src="https://www.mlbstatic.com/team-logos/{{ p.opp_id }}.svg" alt="{{ p.opp_name }} Icon" class="team-icon ms-2" style="margin-right: 4px;"> {{ p.opp_name }}
                            </div>
                        </td>
                        <td class="text-end fw-semibold col-salary">${{ "{:,}".format(p.salary) }}</td>
                        <td class="text-end fw-bold col-proj">{{ p.proj }}</td>
                        <td class="text-end fw-bold text-success col-value">{{ p.value }}x</td>
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
        const rowSlates = row.getAttribute('data-slates').split(',');
        const statsRaw = row.getAttribute('data-slate-stats');
        const stats = statsRaw ? JSON.parse(statsRaw) : {};

        if (slateId === 'all') {
            row.style.display = '';
            // Revert back to master base stats
            row.querySelector('.col-salary').textContent = row.getAttribute('data-default-salary');
            row.querySelector('.col-proj').textContent = row.getAttribute('data-default-proj');
            row.querySelector('.col-value').textContent = row.getAttribute('data-default-value');
        } else {
            if (rowSlates.includes(slateId)) {
                row.style.display = '';
                // Inject the specific slate salary, projection, and value dynamically
                if (stats[slateId]) {
                    row.querySelector('.col-salary').textContent = stats[slateId].salary;
                    row.querySelector('.col-proj').textContent = stats[slateId].proj;
                    row.querySelector('.col-value').textContent = stats[slateId].value;
                }
            } else {
                row.style.display = 'none';
            }
        }
    });

    // Automatically trigger a Sort by Value (Col Index 6) descending when a slate is changed
    const valueHeader = document.querySelectorAll('#leaderboard-table th')[6];
    sortTable(valueHeader, 6, true);
}

function sortTable(thElement, colIndex, forceDesc = false) {
    const table = thElement.closest("table");
    const tbody = table.querySelector("tbody");
    const rows = Array.from(tbody.querySelectorAll("tr"));
    
    let isAscending = thElement.classList.contains("asc");
    
    // If we are forcing a descending sort (e.g. from the filter function), override here
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

    // Re-append sorted rows to the DOM
    rows.forEach(row => tbody.appendChild(row));

    // Recalculate rank numbers (1, 2, 3...) for whatever rows are currently visible
    let currentRank = 1;
    rows.forEach(row => {
        if (row.style.display !== 'none') {
            row.querySelector('.col-rank').textContent = currentRank++;
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

    # Add util to initialization pools
    dk_pools = {"pitchers": [], "catchers": [], "first-base": [], "second-base": [], "third-base": [], "shortstops": [], "outfielders": [], "util": []}
    fd_pools = {"pitchers": [], "catchers-first-base": [], "second-base": [], "third-base": [], "shortstops": [], "outfielders": [], "util": []}

    for game in games_list:
        p_data = game.get("projectedLineups", {})
        
        away_name, away_id = get_team_data(game, "away")
        home_name, home_id = get_team_data(game, "home")

        for side, team_name, team_id, opp_name, opp_id, is_home in [
            ("away", away_name, away_id, home_name, home_id, False), 
            ("home", home_name, home_id, away_name, away_id, True)
        ]:
            side_node = p_data.get(side, {})
            
            # Setup official lineup verification cross-checking
            raw_lineups = game.get("gameRaw", {}).get("lineups", {})
            official_players_raw = raw_lineups.get(f"{side}Players", [])
            is_official = len(official_players_raw) > 0
            official_ids = [str(p.get("id")) for p in official_players_raw]
            
            pitcher = side_node.get("startingPitcher")
            if pitcher:
                pitcher_id = str(pitcher.get("id"))
                prob_pitcher = game.get("gameRaw", {}).get("teams", {}).get(side, {}).get("probablePitcher", {})
                prob_id = str(prob_pitcher.get("id", ""))
                
                lineup_pos = "P"
                if is_official:
                    if prob_id == pitcher_id or pitcher_id in official_ids:
                        order_status = "official"
                    else:
                        order_status = "ns"
                        lineup_pos = "NS"
                else:
                    order_status = "projected"

                if has_dk_data:
                    p_res = process_proprietary_projection(pitcher, True, team_name, team_id, opp_name, opp_id, is_home, game, is_dk=True, lineup_pos=lineup_pos, order_status=order_status)
                    if p_res: dk_pools["pitchers"].append(p_res)
                if has_fd_data:
                    p_res = process_proprietary_projection(pitcher, True, team_name, team_id, opp_name, opp_id, is_home, game, is_dk=False, lineup_pos=lineup_pos, order_status=order_status)
                    if p_res: fd_pools["pitchers"].append(p_res)

            for batter in side_node.get("battingOrder", []):
                batter_id = str(batter.get("id"))
                lineup_pos = str(batter.get("order", ""))
                
                if is_official:
                    if batter_id in official_ids:
                        order_status = "official"
                    else:
                        order_status = "ns"
                        lineup_pos = "NS"
                else:
                    order_status = "projected"

                if has_dk_data:
                    p_res = process_proprietary_projection(batter, False, team_name, team_id, opp_name, opp_id, is_home, game, is_dk=True, lineup_pos=lineup_pos, order_status=order_status)
                    if p_res:
                        # Add every non-pitcher to the util array
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

                if has_fd_data:
                    p_res = process_proprietary_projection(batter, False, team_name, team_id, opp_name, opp_id, is_home, game, is_dk=False, lineup_pos=lineup_pos, order_status=order_status)
                    if p_res:
                        # Add every non-pitcher to the util array
                        fd_pools["util"].append(p_res)
                        
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

    def render_static_html(seo_title, seo_desc, page_url, page_heading, platform_name, platform_slug, current_pos, position_links, date_str, players_list, distinct_slates):
        try:
            from jinja2 import Template
            t = Template(HTML_TEMPLATE)
            return t.render(
                seo_title=seo_title, 
                seo_desc=seo_desc, 
                page_url=page_url,
                page_heading=page_heading, 
                platform_name=platform_name,
                platform_slug=platform_slug,
                current_pos=current_pos,
                position_links=position_links,
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
            
            if pos_slug == "util":
                clean_title = "Utility (All Hitters)"
            else:
                clean_title = pos_slug.replace("-", " ").title()
                
            page_url = f"{base_domain}/dfs/draftkings/top-{pos_slug}/"

            html_output = render_static_html(
                seo_title=meta["title"],
                seo_desc=meta["desc"],
                page_url=page_url,
                page_heading=f"Top Projected DraftKings {clean_title}",
                platform_name="DraftKings",
                platform_slug="draftkings",
                current_pos=pos_slug,
                position_links=POS_LABELS_DK,
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
            
            if pos_slug == "util":
                clean_title = "Utility"
            else:
                clean_title = pos_slug.replace("-", " ").title()
                if "Catchers" in clean_title: clean_title = "C / 1B Split"
                
            page_url = f"{base_domain}/dfs/fanduel/top-{pos_slug}/"

            html_output = render_static_html(
                seo_title=meta["title"],
                seo_desc=meta["desc"],
                page_url=page_url,
                page_heading=f"Top Projected FanDuel {clean_title}",
                platform_name="FanDuel",
                platform_slug="fanduel",
                current_pos=pos_slug,
                position_links=POS_LABELS_FD,
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
