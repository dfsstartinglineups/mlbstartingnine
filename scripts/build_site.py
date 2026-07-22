import os
import json
import html
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
import pytz

# ==========================================
# 1. EMBEDDED HTML TEMPLATE
# ==========================================
BASE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-TW817924LJ"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){dataLayer.push(arguments);}
      gtag('js', new Date());
      gtag('config', 'G-TW817924LJ');
    </script>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "WebSite",
      "name": "MLB Starting Nine",
      "alternateName": ["MLBStartingNine", "MLB Starting 9"],
      "url": "https://mlbstartingnine.com/"
    }
    </script>
    <!-- Add this placeholder line right here -->
    <!-- DYNAMIC_GAMES_SCHEMA -->
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" href="/favicon.ico" sizes="any">
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">
    
    <title>MLB Starting Nine | Today's MLB Starting Lineups, Odds & Player Projections</title>
    
    
    <meta name="description" content="Live MLB starting lineups, probable pitchers, moneylines, and totals. Plus daily MLB player projections, Batter vs. Pitcher (BvP) matchups, pitcher splits, umpire tendencies, and park factors.">
    <meta name="keywords" content="MLB starting lineups, MLB player projections, MLB odds, baseball projections, BvP matchups, batter vs pitcher, pitcher splits, umpire tendencies, stadium park factors, daily fantasy baseball, DFS lineups, MLB betting, MLB starting pitchers">
    <link rel="canonical" href="https://mlbstartingnine.com/">
    <meta property="og:site_name" content="MLB Starting Nine">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://mlbstartingnine.com/">
    <meta property="og:title" content="MLB Starting Nine | Today's MLB Starting Lineups, Odds & Player Projections">
    <meta property="og:description" content="Live MLB starting lineups, probable pitchers, moneylines, and totals. Plus daily MLB player projections, Batter vs. Pitcher (BvP) matchups, pitcher splits, and umpire tendencies.">
    <meta property="og:image" content="https://mlbstartingnine.com/mlb-social-share.jpg">
    <meta name="twitter:card" content="summary">
    <meta property="twitter:domain" content="mlbstartingnine.com">
    <meta property="twitter:url" content="https://mlbstartingnine.com/">
    <meta name="twitter:title" content="MLB Starting Nine | Today's MLB Starting Lineups, Odds & Player Projections">
    <meta name="twitter:description" content="Live MLB starting lineups, probable pitchers, moneylines, and totals. Plus daily MLB player projections, Batter vs. Pitcher (BvP) matchups, pitcher splits, and umpire tendencies.">
    <meta name="twitter:image" content="https://mlbstartingnine.com/mlb-social-share.jpg">

    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <style>
        body { background-color: #f1f3f5; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        .header-brand { font-weight: 900; letter-spacing: -1px; font-size: 2rem; color: #fff; font-style: italic; text-shadow: 0 2px 4px rgba(0,0,0,0.5); }
        .header-brand a { color: inherit; text-decoration: none; }
        .header-brand span { background: linear-gradient(to bottom, #7CD0FF 0%, #1A8CFF 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; padding-right: 2px; display: inline-block; }
        .lineup-card { background: #fff; border: 1px solid #dee2e6; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 24px; overflow: hidden; }
        .batting-order { padding-left: 0; list-style-type: none; margin-bottom: 0; }
        .batting-order li { padding: 6px 12px; font-size: 0.85rem; border-bottom: 1px solid #f1f3f5; display: flex; justify-content: space-between; align-items: center; }
        .batter-name { font-weight: 600; color: #495057; }
        .promo-btn { font-size: 0.8rem; font-weight: 700; letter-spacing: 0.5px; }
        #team-search { color: #ffffff !important; color-scheme: dark; width: 140px; background-color: #343a40; border: 1px solid #495057; }
        #team-search::placeholder { color: #adb5bd !important; }
        
        /* Restored DFS Green Toggles CSS */
        .dk-btn-label { color: #6c9d2f; border-color: #6c9d2f; background-color: #fff; }
        .dk-btn-label:hover { color: #fff; background-color: #6c9d2f; border-color: #6c9d2f; }
        .btn-check:checked + .dk-btn-label { background-color: #6c9d2f !important; border-color: #6c9d2f !important; color: #fff !important; }
    </style>
</head>
<body>

<nav class="navbar shadow-sm py-3 mb-2" style="background-color: #212529;">
    <div class="container d-flex justify-content-between align-items-center flex-wrap">
        <div class="header-brand mb-2 mb-md-0">
            <a href="/" class="text-decoration-none">MLB Starting <span>Nine</span></a>
        </div>
        <div class="d-flex align-items-center gap-2 flex-wrap">
            <!-- 3-Day Layout Nav Switchers -->
            <button id="btn-yesterday" class="btn btn-sm btn-outline-light fw-bold" onclick="switchDay('yesterday')">◀ Yesterday</button>
            <button id="btn-today" class="btn btn-sm btn-primary fw-bold d-none" onclick="switchDay('today')">Today</button>
            <button id="btn-tomorrow" class="btn btn-sm btn-outline-light fw-bold" onclick="switchDay('tomorrow')">Tomorrow ▶</button>
            
            <input type="text" id="team-search" class="form-control form-control-sm ms-1" placeholder="🔍 Search...">
            
            <!-- Restored Team Lineups Dropdown -->
            <select class="form-select form-select-sm fw-bold ms-1" style="background-color: #343a40; color: #adb5bd; border: 1px solid #495057; cursor: pointer; max-width: 170px;" onchange="if(this.value) window.location.href=this.value;">
                <option value="">Team Lineups</option>
                <option value="/lineups/arizona-diamondbacks/">Arizona Diamondbacks</option>
                <option value="/lineups/athletics/">Athletics</option>
                <option value="/lineups/atlanta-braves/">Atlanta Braves</option>
                <option value="/lineups/baltimore-orioles/">Baltimore Orioles</option>
                <option value="/lineups/boston-red-sox/">Boston Red Sox</option>
                <option value="/lineups/chicago-cubs/">Chicago Cubs</option>
                <option value="/lineups/chicago-white-sox/">Chicago White Sox</option>
                <option value="/lineups/cincinnati-reds/">Cincinnati Reds</option>
                <option value="/lineups/cleveland-guardians/">Cleveland Guardians</option>
                <option value="/lineups/colorado-rockies/">Colorado Rockies</option>
                <option value="/lineups/detroit-tigers/">Detroit Tigers</option>
                <option value="/lineups/houston-astros/">Houston Astros</option>
                <option value="/lineups/kansas-city-royals/">Kansas City Royals</option>
                <option value="/lineups/los-angeles-angels/">Los Angeles Angels</option>
                <option value="/lineups/los-angeles-dodgers/">Los Angeles Dodgers</option>
                <option value="/lineups/miami-marlins/">Miami Marlins</option>
                <option value="/lineups/milwaukee-brewers/">Milwaukee Brewers</option>
                <option value="/lineups/minnesota-twins/">Minnesota Twins</option>
                <option value="/lineups/new-york-mets/">New York Mets</option>
                <option value="/lineups/new-york-yankees/">New York Yankees</option>
                <option value="/lineups/philadelphia-phillies/">Philadelphia Phillies</option>
                <option value="/lineups/pittsburgh-pirates/">Pittsburgh Pirates</option>
                <option value="/lineups/san-diego-padres/">San Diego Padres</option>
                <option value="/lineups/san-francisco-giants/">San Francisco Giants</option>
                <option value="/lineups/seattle-mariners/">Seattle Mariners</option>
                <option value="/lineups/st-louis-cardinals/">St. Louis Cardinals</option>
                <option value="/lineups/tampa-bay-rays/">Tampa Bay Rays</option>
                <option value="/lineups/texas-rangers/">Texas Rangers</option>
                <option value="/lineups/toronto-blue-jays/">Toronto Blue Jays</option>
                <option value="/lineups/washington-nationals/">Washington Nationals</option>
            </select>
        </div>
    </div>
</nav>

<div class="container mt-3 mb-3 text-center">
    <h1 id="main-page-header" class="h5 fw-bold text-dark mb-1">MLB Starting Lineups & Projections: <!-- PRETTY_TODAY --></h1>
    <p class="text-muted mb-2" style="font-size: 0.85rem;">Live BvP matchups, pitcher splits, umpire tendencies, daily fantasy projections, and park factors.</p>
</div>

<!-- Restored DFS Controls Row (Global Expand/Collapse Button Removed) -->
<div id="dfs-controls-row" class="container d-flex align-items-center mb-3 gap-2 px-2">
    <div class="btn-group shadow-sm flex-shrink-0" role="group">
        <input type="radio" class="btn-check dfs-toggle" name="dfsPlatform" id="btn-fd" value="fd" checked>
        <label class="btn btn-outline-primary fw-bold px-3 py-1" for="btn-fd" style="font-size: 0.85rem;">FD</label>
        
        <input type="radio" class="btn-check dfs-toggle" name="dfsPlatform" id="btn-dk" value="dk">
        <label class="btn fw-bold px-3 py-1 dk-btn-label" for="btn-dk" style="font-size: 0.85rem;">DK</label>
    </div>
    <select id="dfs-page-selector" class="form-select form-select-sm fw-bold shadow-sm" style="width: auto; min-width: 180px; cursor: pointer; font-size: 0.85rem; border-color: #ced4da; color: #212529;" onchange="if(this.value) window.location.href=this.value;">
        <!-- Populated by JS -->
    </select>
</div>

<!-- Three Separated Partitions Built Pre-rendered by Python Backend -->
<div class="container">
    <div id="games-yesterday" class="row justify-content-center d-none">
        <!-- GALAXY_YESTERDAY -->
    </div>
    <div id="games-today" class="row justify-content-center">
        <!-- GALAXY_TODAY -->
    </div>
    <div id="games-tomorrow" class="row justify-content-center d-none">
        <!-- GALAXY_TOMORROW -->
    </div>
</div>

<!-- Restored Footer -->
<footer class="mt-5 py-4 bg-light border-top">
    <div class="container text-center">
        <p class="text-muted mb-1" style="font-size: 0.85rem; font-weight: 600;">
            © 2026 MLB Starting Nine
        </p>
        <p class="text-muted mb-0" style="font-size: 0.70rem; max-width: 600px; margin: 0 auto; line-height: 1.4;">
            This site is for informational and entertainment purposes only. <strong>Disclaimer:</strong> MLB Starting Nine is not affiliated with, endorsed by, authorized by, or sponsored by Major League Baseball (MLB) or any of its respective teams. All team names, logos, and brands are property of their respective owners.
        </p>
    </div>
</footer>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>

<script>
// ========================================================
// 1. LIGHTWEIGHT CONTROLS & EVENT SWAPPERS
// ========================================================
let currentActiveDay = 'today';
window.ACTIVE_GAME_TABS = {};

const HEADER_DATES = {
    'yesterday': '<!-- PRETTY_YEST -->',
    'today': '<!-- PRETTY_TODAY -->',
    'tomorrow': '<!-- PRETTY_TOM -->'
};

function switchDay(targetDay) {
    currentActiveDay = targetDay;
    
    // Dynamically update the H1 text for the user
    const h1El = document.getElementById('main-page-header');
    if (h1El && HEADER_DATES[targetDay]) {
        h1El.textContent = `MLB Starting Lineups & Projections: ${HEADER_DATES[targetDay]}`;
    }

    document.getElementById('games-yesterday').classList.add('d-none');
    document.getElementById('games-today').classList.add('d-none');
    document.getElementById('games-tomorrow').classList.add('d-none');
    
    document.getElementById(`games-${targetDay}`).classList.remove('d-none');
    
    const btnYest = document.getElementById('btn-yesterday');
    const btnToday = document.getElementById('btn-today');
    const btnTom = document.getElementById('btn-tomorrow');
    
    if (targetDay === 'today') {
        btnYest.className = "btn btn-sm btn-outline-light fw-bold"; btnYest.classList.remove('d-none');
        btnTom.className = "btn btn-sm btn-outline-light fw-bold"; btnTom.classList.remove('d-none');
        btnToday.classList.add('d-none');
    } else if (targetDay === 'yesterday') {
        btnYest.classList.add('d-none'); btnTom.classList.add('d-none');
        btnToday.className = "btn btn-sm btn-outline-light fw-bold"; btnToday.textContent = "Today ▶"; btnToday.classList.remove('d-none');
    } else if (targetDay === 'tomorrow') {
        btnYest.classList.add('d-none'); btnTom.classList.add('d-none');
        btnToday.className = "btn btn-sm btn-outline-light fw-bold"; btnToday.textContent = "◀ Today"; btnToday.classList.remove('d-none');
    }
    filterTeams();
    adjustOverflowingNames(); // Fix names when unhiding containers
}

window.switchGameTab = function(gamePk, tabName, btnEl) {
    const card = document.getElementById(`game-${gamePk}`);
    if (!card) return;
    
    const isAlreadyActive = btnEl.classList.contains('active');
    
    // Reset all buttons in this card to their default look
    card.querySelectorAll('.tab-btn').forEach(b => {
        b.classList.remove('active', 'btn-primary', 'text-white');
        b.classList.add('btn-outline-secondary', 'text-muted');
    });
    
    // Hide all view variants completely
    card.querySelectorAll('.player-view').forEach(v => v.classList.add('d-none'));
    
    if (isAlreadyActive) {
        // TOGGLE OFF: If they clicked an active button, return to the default clean view
        card.querySelectorAll('.view-default').forEach(v => v.classList.remove('d-none'));
        delete window.ACTIVE_GAME_TABS[gamePk];
    } else {
        // TOGGLE ON: Highlight the clicked button and show its specific stats view
        btnEl.classList.add('active', 'btn-primary', 'text-white');
        btnEl.classList.remove('btn-outline-secondary', 'text-muted');
        window.ACTIVE_GAME_TABS[gamePk] = tabName;
        card.querySelectorAll(`.view-${tabName}`).forEach(v => v.classList.remove('d-none'));
    }
};

function filterTeams() {
    const query = document.getElementById('team-search').value.toLowerCase();
    const container = document.getElementById(`games-${currentActiveDay}`);
    container.querySelectorAll('.col-xl-4').forEach(cardColumn => {
        const text = cardColumn.textContent.toLowerCase();
        if(text.includes(query)) {
            cardColumn.classList.remove('d-none');
        } else {
            cardColumn.classList.add('d-none');
        }
    });
}
document.getElementById('team-search').addEventListener('input', filterTeams);

// ========================================================
// 2. DFS CONTROLS & DROPDOWN LOGIC
// ========================================================
function populateDFSLinks() {
    const platformNode = document.querySelector('input[name="dfsPlatform"]:checked');
    const platform = platformNode ? platformNode.value : 'fd';
    
    const selector = document.getElementById('dfs-page-selector');
    if (!selector) return;
    
    selector.innerHTML = '<option value="">Top DFS Plays...</option>';
    
    const links = platform === 'dk' ? [
        { slug: "live-slate-leaderboard", label: "🔴 Live Leaderboard" },
        { slug: "pitchers", label: "Pitchers" }, { slug: "catchers", label: "Catchers" },
        { slug: "first-base", label: "First Base" }, { slug: "second-base", label: "Second Base" },
        { slug: "third-base", label: "Third Base" }, { slug: "shortstops", label: "Shortstops" },
        { slug: "outfielders", label: "Outfielders" }, { slug: "util", label: "Util (All Hitters)" }
    ] : [
        { slug: "live-slate-leaderboard", label: "🔴 Live Leaderboard" },
        { slug: "pitchers", label: "Pitchers" }, { slug: "catchers-first-base", label: "C / 1B" },
        { slug: "second-base", label: "Second Base" }, { slug: "third-base", label: "Third Base" },
        { slug: "shortstops", label: "Shortstops" }, { slug: "outfielders", label: "Outfielders" },
        { slug: "util", label: "Utility" }
    ];
    
    const platSlug = platform === 'dk' ? 'draftkings' : 'fanduel';
    
    links.forEach(link => {
        const opt = document.createElement('option');
        
        // Check if it's the live leaderboard to omit the "top-" prefix
        if (link.slug === "live-slate-leaderboard") {
            opt.value = `/dfs/${platSlug}/${link.slug}/`;
        } else {
            opt.value = `/dfs/${platSlug}/top-${link.slug}/`;
        }
        
        opt.textContent = link.label;
        selector.appendChild(opt);
    });
}
document.querySelectorAll('.dfs-toggle').forEach(radio => radio.addEventListener('change', populateDFSLinks));
document.addEventListener('DOMContentLoaded', populateDFSLinks);

// ========================================================
// 3. UI POLISH (TEXT OVERFLOW & EXPAND/COLLAPSE)
// ========================================================
function adjustOverflowingNames() {
    requestAnimationFrame(() => {
        document.querySelectorAll('.batter-name').forEach(el => {
            if (el.scrollWidth > el.clientWidth) {
                const shortName = el.getAttribute('data-shortname');
                if (shortName && shortName !== el.textContent) {
                    el.textContent = shortName;
                }
            }
        });
    });
}
document.addEventListener('DOMContentLoaded', adjustOverflowingNames);
window.addEventListener('resize', adjustOverflowingNames);

document.addEventListener('click', (e) => {
    if (e.target.closest('.card-toggle-btn')) {
        const btn = e.target.closest('.card-toggle-btn');
        const card = btn.closest('.lineup-card');
        const isExp = btn.textContent.includes('+');
        card.querySelectorAll('.stats-collapse').forEach(d => isExp ? d.classList.remove('d-none') : d.classList.add('d-none'));
        btn.textContent = isExp ? '[-] Collapse Matchups' : '[+] Expand Matchups';
    }
    // Global toggle event block completely stripped out from here
});

// ========================================================
// 4. DEEP LINK SCROLLING & GLOW EFFECT
// ========================================================
function handleHashNavigation() {
    if (window.location.hash) {
        setTimeout(() => {
            const targetId = window.location.hash.substring(1);
            const targetCard = document.getElementById(targetId);
            
            if (targetCard) {
                const parentDay = targetCard.closest('.row[id^="games-"]');
                if (parentDay && parentDay.classList.contains('d-none')) {
                    const dayString = parentDay.id.replace('games-', '');
                    switchDay(dayString);
                }

                targetCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
                const innerHeader = targetCard.querySelector('.p-2.pb-1'); 
                
                targetCard.style.transition = 'all 0.4s ease-out';
                targetCard.style.transform = 'scale(1.02)';
                targetCard.style.setProperty('border', '3px solid #0d6efd', 'important');
                targetCard.style.setProperty('box-shadow', '0 0 25px rgba(13, 110, 253, 0.8)', 'important');
                targetCard.style.position = 'relative'; 
                targetCard.style.zIndex = '10';
                
                if (innerHeader) {
                    innerHeader.style.transition = 'background-color 0.4s ease-out';
                    innerHeader.style.backgroundColor = '#cfe2ff'; 
                }
                
                setTimeout(() => {
                    targetCard.style.transform = 'scale(1)';
                    targetCard.style.removeProperty('border'); 
                    targetCard.style.setProperty('box-shadow', '0 2px 4px rgba(0,0,0,0.05)', 'important');
                    targetCard.style.zIndex = '1';
                    if (innerHeader) innerHeader.style.backgroundColor = '#edf4f8'; 
                }, 4000); 
            }
        }, 600); 
    }
}
document.addEventListener('DOMContentLoaded', handleHashNavigation);
window.addEventListener('hashchange', handleHashNavigation);

// ========================================================
// 5. STATE-PRESERVING SILENT REFRESH (EVERY 30 SECONDS)
// ========================================================
setInterval(async () => {
    try {
        const res = await fetch('/index.html?v=' + new Date().getTime());
        if (!res.ok) return;
        const htmlText = await res.text();
        
        const parser = new DOMParser();
        const doc = parser.parseFromString(htmlText, 'text/html');
        
        const scrollY = window.scrollY;
        const savedTabs = { ...window.ACTIVE_GAME_TABS };
        const activeDayState = currentActiveDay;
        
        ['yesterday', 'today', 'tomorrow'].forEach(day => {
            const oldContainer = document.getElementById(`games-${day}`);
            const newContainer = doc.getElementById(`games-${day}`);
            if (oldContainer && newContainer) {
                oldContainer.innerHTML = newContainer.innerHTML;
            }
        });
        
        switchDay(activeDayState);
        adjustOverflowingNames(); // Re-evaluate text limits
        
        Object.keys(savedTabs).forEach(gamePk => {
            const card = document.getElementById(`game-${gamePk}`);
            if(card) {
                const targetBtn = card.querySelector(`[onclick*="${savedTabs[gamePk]}"]`);
                if(targetBtn) targetBtn.click();
            }
        });
        
        window.scrollTo(0, scrollY);
    } catch (e) {
        console.log("Silent refresh execution bypassed this loop cycle.", e);
    }
}, 30000);
</script>
</body>
</html>
"""

# ==========================================
# 2. DATE CALCULATION (3:00 AM EST CROSSOVER)
# ==========================================
def get_3day_dates():
    est_tz = pytz.timezone('America/New_York')
    now_est = datetime.now(pytz.utc).astimezone(est_tz)
    
    adjusted_time = now_est - timedelta(hours=3)
    today_date = adjusted_time.date()
    
    yesterday_date = today_date - timedelta(days=1)
    tomorrow_date = today_date + timedelta(days=1)
    
    return yesterday_date.strftime('%Y-%m-%d'), today_date.strftime('%Y-%m-%d'), tomorrow_date.strftime('%Y-%m-%d')

# ==========================================
# 3. UTILITY HELPER FUNCTIONS
# ==========================================
def update_homepage_sitemap_date(target_url="https://mlbstartingnine.com/"):
    """Updates the <lastmod> date specifically for the homepage URL in the sitemap."""
    sitemap_path = "sitemap.xml"
    if not os.path.exists(sitemap_path):
        return
    
    try:
        ET.register_namespace('', "http://www.sitemaps.org/schemas/sitemap/0.9")
        tree = ET.parse(sitemap_path)
        root = tree.getroot()
        
        today_str = datetime.now(pytz.utc).strftime("%Y-%m-%d")
        updated = False
        
        for url_node in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
            loc_node = url_node.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
            if loc_node is not None and loc_node.text and loc_node.text.strip() == target_url:
                lastmod_node = url_node.find("{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod")
                if lastmod_node is not None:
                    lastmod_node.text = today_str
                else:
                    ET.SubElement(url_node, 'lastmod').text = today_str
                updated = True
                break
        
        if updated:
            raw_xml = ET.tostring(root, 'utf-8')
            parsed_xml = minidom.parseString(raw_xml)
            pretty_xml = parsed_xml.toprettyxml(indent="  ")
            
            with open(sitemap_path, "w", encoding="utf-8") as f:
                f.write("\n".join([line for line in pretty_xml.splitlines() if line.strip()]))
                
    except Exception as e:
        print(f"⚠️ Error updating sitemap: {e}")

def generate_games_schema(date_str):
    file_path = f"data/daily_files/games_{date_str}.json"
    if not os.path.exists(file_path):
        return ""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        games_list = raw_data if isinstance(raw_data, list) else raw_data.get('games', [])
    except Exception:
        return ""
        
    schema_events = []
    for data in games_list:
        game = data.get('gameRaw', {})
        away_name = game.get('teams', {}).get('away', {}).get('team', {}).get('name', '')
        home_name = game.get('teams', {}).get('home', {}).get('team', {}).get('name', '')
        game_date = game.get('gameDate', '')
        venue_name = game.get('venue', {}).get('name', '')
        
        # Pull down the arrays to determine official status
        a_proj = data.get('projectedLineups', {}).get('away', {}).get('battingOrder', [])
        h_proj = data.get('projectedLineups', {}).get('home', {}).get('battingOrder', [])
        a_players = game.get('lineups', {}).get('awayPlayers', [])
        h_players = game.get('lineups', {}).get('homePlayers', [])
        
        is_a_official = len(a_players) > 0
        is_h_official = len(h_players) > 0
        
        final_away = a_players if is_a_official else a_proj
        final_home = h_players if is_h_official else h_proj

        # Convert the player structures into an ordered list schema with STATUS labels
        def build_roster_schema(player_list, team_name, is_official):
            if not player_list: 
                return None
            
            status_label = "Official" if is_official else "Projected"
            roster_items = []
            
            for idx, p in enumerate(player_list[:9]):
                p_name = p.get('fullName', p.get('name', ''))
                roster_items.append({
                    "@type": "ListItem",
                    "position": idx + 1,
                    "item": {
                        "@type": "Person",
                        "name": p_name
                    }
                })
                
            return {
                "@type": "ItemList", 
                "name": f"{team_name} {status_label} Starting Lineup",
                "itemListElement": roster_items
            }

        away_roster = build_roster_schema(final_away, away_name, is_a_official)
        home_roster = build_roster_schema(final_home, home_name, is_h_official)

        if away_name and home_name:
            event = {
                "@context": "https://schema.org",
                "@type": "SportsEvent",
                "name": f"{away_name} at {home_name} Matchup",
                "startDate": game_date,
                "location": {
                    "@type": "Place",
                    "name": venue_name
                },
                "competitor": [
                    {
                        "@type": "SportsTeam",
                        "name": away_name,
                        "subOrganization": away_roster if away_roster else {}
                    },
                    {
                        "@type": "SportsTeam",
                        "name": home_name,
                        "subOrganization": home_roster if home_roster else {}
                    }
                ]
            }
            
            # Clean up empty subOrganization keys if rosters are missing entirely
            if not away_roster: event["competitor"][0].pop("subOrganization", None)
            if not home_roster: event["competitor"][1].pop("subOrganization", None)
            
            schema_events.append(event)
            
    if not schema_events:
        return ""
        
    return f'<script type="application/ld+json">\n{json.dumps(schema_events, indent=2)}\n</script>'

def slugify(text):
    if not text:
        return ""
    import unicodedata
    import re
    text = str(text).lower()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[\s-]+', '-', text).strip()

def get_player_slug(player_id, default_name, player_db):
    if player_id and player_db:
        db_key = f"ID{player_id}"
        if db_key in player_db and 'slug' in player_db[db_key]:
            return player_db[db_key]['slug']
    return slugify(default_name)

def get_status_weight(game):
    status = game.get('status', {}).get('abstractGameState', '')
    detailed = game.get('status', {}).get('detailedState', '')
    linescore = game.get('linescore', {})
    inning = linescore.get('currentInning', 0)
    half = linescore.get('inningHalf', '')

    if status == "Final":
        return 2
    if status == "Live" or "In Progress" in detailed:
        if inning == 0 or (inning == 1 and half == 'Top'):
            return 0
        return 1
    return 0

def queue_urls_for_indexnow(new_urls, queue_file="data/updates_queue.json"):
    """Appends newly updated URLs to the IndexNow JSON queue safely."""
    if not new_urls:
        return

    if not os.path.exists(queue_file):
        os.makedirs(os.path.dirname(queue_file), exist_ok=True)
        queue_data = {
            "last_sent": "2000-01-01T00:00:00",
            "urls": []
        }
    else:
        with open(queue_file, "r", encoding="utf-8") as f:
            try:
                queue_data = json.load(f)
            except json.JSONDecodeError:
                queue_data = {
                    "last_sent": "2000-01-01T00:00:00",
                    "urls": []
                }

    queue_data["urls"].extend(new_urls)

    with open(queue_file, "w", encoding="utf-8") as f:
        json.dump(queue_data, f, indent=2)

# ==========================================
# 4. CARD & LINEUP BUILDERS
# ==========================================
def build_pitcher_header(pitcher_obj, ml_odds, p_hand, deep_stats, player_db):
    if not pitcher_obj or not pitcher_obj.get('id'):
        return '<div class="d-flex align-items-center justify-content-center bg-light rounded border text-muted fst-italic w-100" style="height: 42px; font-size: 0.70rem;">TBD</div>'
    
    pid_str = str(pitcher_obj['id'])
    p_stats = deep_stats.get(pid_str, {}).get('season', {'w': 0, 'l': 0, 'era': "-", 'k': 0})
    
    player_name = pitcher_obj.get('fullName', pitcher_obj.get('name', ''))
    abbr_name = f"{player_name.split(' ')[0][0]}. {' '.join(player_name.split(' ')[1:])}" if ' ' in player_name else player_name
    
    photo_url = f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:brooks:default/w_180,q_auto:best/v1/people/{pid_str}/headshot/67/current"
    hand_text = f'<span class="text-muted fw-bold me-1" style="font-size:0.65rem;">({p_hand})</span>' if p_hand else ""
    slug = get_player_slug(pid_str, player_name, player_db)

    return f"""
    <div class="d-flex align-items-center bg-light rounded p-1 border w-100" style="min-height: 44px;">
        <div class="d-flex flex-column align-items-center justify-content-center me-2 flex-shrink-0" style="width: 32px;">
            <img src="{photo_url}" style="width: 24px; height: 24px; border-radius: 50%; object-fit: cover; border: 1px solid #dee2e6; background: #fff; margin-bottom: 2px;">
            {ml_odds}
        </div>
        <div class="d-flex flex-column justify-content-center text-truncate w-100">
            <div class="d-flex align-items-center text-truncate w-100">
                {hand_text}
                <a href="/players/{slug}/" class="fw-bold text-dark text-truncate text-decoration-none" style="font-size: 0.75rem;" title="{html.escape(player_name)}">{html.escape(abbr_name)}</a>
            </div>
            <span class="text-muted" style="font-size: 0.65rem; margin-top: 1px;">{p_stats.get('w', 0)}-{p_stats.get('l', 0)} • {p_stats.get('era', '-')} • {p_stats.get('k', 0)}K</span>
        </div>
    </div>"""

def build_lineup_html(players, opposing_pitcher_hand, game_data, player_db):
    if not players:
        return '<div class="p-4 text-center text-muted small fw-bold">Lineup not yet posted</div>'
    
    hand_dict = game_data.get('lineupHandedness', {})
    deep_stats = game_data.get('deepStats', {})
    pos_dict = game_data.get('gamePositions', {})

    list_items = []
    for index, p in enumerate(players):
        pid_str = str(p['id'])
        player_name = p.get('fullName', p.get('name', ''))
        abbr_name = f"{player_name.split(' ')[0][0]}. {' '.join(player_name.split(' ')[1:])}" if ' ' in player_name else player_name

        bat_code = hand_dict.get(pid_str, "")
        hand_text = f'<span class="text-muted fw-bold" style="font-size:0.60rem;">({bat_code})</span>' if bat_code else ""
        
        game_pos = pos_dict.get(pid_str, "")
        prefix_text = game_pos if game_pos else f"{p.get('order', index)}."
        
        photo_url = f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:brooks:default/w_180,q_auto:best/v1/people/{pid_str}/headshot/67/current"
        slug = get_player_slug(pid_str, player_name, player_db)

        top_line = f"""<div class="d-flex align-items-center text-truncate w-100" style="padding-bottom: 2px;">
            <span class="text-muted fw-bold text-center flex-shrink-0" style="font-size: 0.65rem; width: 22px; margin-right: 4px;">{prefix_text}</span>
            {hand_text}
            <a href="/players/{slug}/" class="batter-name fw-bold text-dark text-truncate ms-1 text-decoration-none" style="font-size: 0.65rem;" title="{html.escape(player_name)}" data-shortname="{html.escape(abbr_name)}">{html.escape(player_name)}</a>
        </div>"""

        v_default = f"""<div class="d-flex align-items-center w-100">
            <span class="text-muted fw-bold text-center flex-shrink-0" style="font-size: 0.65rem; width: 22px; margin-right: 4px;">{prefix_text}</span>
            <img src="{photo_url}" style="width: 26px; height: 26px; border-radius: 50%; object-fit: cover; border: 1px solid #dee2e6; background: #fff; margin-right: 6px;" onerror="this.onerror=null; this.src='data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iI2FkYjViZCI+PHBhdGggZD0iTTEyIDJDMi42NCAyIDIgNi42NCAyIDEyeiIvPjwvc3ZnPg==';">
            {hand_text}
            <a href="/players/{slug}/" class="batter-name fw-bold text-dark text-truncate ms-1 text-decoration-none" style="font-size: 0.70rem;" title="{html.escape(player_name)}" data-shortname="{html.escape(abbr_name)}">{html.escape(player_name)}</a>
        </div>"""

        s_stats = deep_stats.get(pid_str, {}).get('season', {'avg': '-', 'ops': '-', 'hr': 0})
        v_season = f"{top_line}<div class='text-muted text-truncate w-100' style='font-size: 0.60rem;'>{s_stats.get('avg','-')} • {s_stats.get('ops','-')} OPS • {s_stats.get('hr',0)} HR</div>"

        bvp = deep_stats.get(pid_str, {}).get('bvp', {'hits': 0, 'ab': 0, 'avg': '-', 'ops': '-', 'hr': 0})
        v_vsp = f"{top_line}<div class='text-muted text-truncate w-100' style='font-size: 0.60rem;'>{bvp.get('hits',0)}-{bvp.get('ab',0)} • {bvp.get('avg','-')} • {bvp.get('ops','-')} OPS • {bvp.get('hr',0)} HR</div>"

        split = deep_stats.get(pid_str, {}).get(f'split_v{opposing_pitcher_hand}', {'ab': 0, 'avg': '-', 'ops': '-', 'hr': 0})
        try:
            split_hits = round(float(split.get('avg', 0)) * split.get('ab', 0)) if (split.get('ab', 0) > 0 and split.get('avg', '-') != '-') else 0
        except ValueError:
            split_hits = 0
        v_splits = f"{top_line}<div class='text-muted text-truncate w-100' style='font-size: 0.60rem;'>v{opposing_pitcher_hand}: {split_hits}-{split.get('ab',0)}•{split.get('avg','-')}•{split.get('ops','-')}•{split.get('hr',0)} HR</div>"

        fd_sal = p.get('salary', 0)
        fd_sal_str = f"${fd_sal/1000:.1f}K".replace('.0', '') if fd_sal > 0 else '-'
        v_fd = f"""{top_line}<div class="d-flex gap-2 text-muted text-truncate w-100" style="font-size: 0.60rem;">
            <span>{fd_sal_str}</span>
            <span class="text-primary fw-bold">Proj: {f"{float(p.get('proj', 0)):.1f}" if p.get('proj') else '-'}</span>
            <span class="text-success fw-bold">Value: {f"{float(p.get('value', 0)):.1f}x" if p.get('value') else '-'}</span>
        </div>"""

        dk_sal = p.get('dk_salary', 0)
        dk_sal_str = f"${dk_sal/1000:.1f}K".replace('.0', '') if dk_sal > 0 else '-'
        v_dk = f"""{top_line}<div class="d-flex gap-2 text-muted text-truncate w-100" style="font-size: 0.60rem;">
            <span>{dk_sal_str}</span>
            <span class="text-primary fw-bold">Proj: {f"{float(p.get('dk_proj', 0)):.1f}" if p.get('dk_proj') else '-'}</span>
            <span class="text-success fw-bold">Value: {f"{float(p.get('dk_value', 0)):.1f}x" if p.get('dk_value') else '-'}</span>
        </div>"""

        list_items.append(f"""
        <li class="d-flex align-items-center w-100 px-2 py-1 border-bottom" style="min-height: 36px;">
            <div class="d-flex align-items-center flex-grow-1 text-truncate w-100 lh-sm">
                <!-- Clean default view shows first on load -->
                <div class="player-view view-default align-items-center w-100">{v_default}</div>
                <div class="player-view view-season flex-column justify-content-center w-100 d-none">{v_season}</div>
                <div class="player-view view-vsp flex-column justify-content-center w-100 d-none">{v_vsp}</div>
                <div class="player-view view-splits flex-column justify-content-center w-100 d-none">{v_splits}</div>
                <div class="player-view view-fd flex-column justify-content-center w-100 d-none">{v_fd}</div>
                <div class="player-view view-dk flex-column justify-content-center w-100 d-none">{v_dk}</div>
            </div>
        </li>""")

    return f'<div class="w-100 m-0 p-0"><ul class="batting-order w-100 m-0 p-0" style="list-style-type: none;">{"".join(list_items)}</ul></div>'

def generate_games_html(date_str, player_db):
    file_path = f"data/daily_files/games_{date_str}.json"
    if not os.path.exists(file_path):
        return f'<div class="col-12 text-center mt-5"><div class="alert alert-light border shadow-sm py-4"><h5 class="text-muted mb-0">Schedule pending for {date_str}</h5></div></div>'
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        games_list = raw_data if isinstance(raw_data, list) else raw_data.get('games', [])
    except Exception:
        return f'<div class="col-12 text-center mt-5"><div class="alert alert-light border shadow-sm py-4"><h5 class="text-muted mb-0">Error reading data for {date_str}</h5></div></div>'
    
    if not games_list:
        return f'<div class="col-12 text-center mt-5"><div class="alert alert-light border shadow-sm py-4"><h5 class="text-muted mb-0">No games scheduled for {date_str}</h5></div></div>'

    games_list.sort(key=lambda x: (get_status_weight(x.get('gameRaw', {})), x.get('gameRaw', {}).get('gameDate', '')))
    cards_html = []
    for data in games_list:
        game = data.get('gameRaw', {})
        deep_stats = data.get('deepStats', {})
        park_stats = data.get('parkStats')
        hp_umpire = data.get('hpUmpire', "TBD")
        ump_stats = data.get('umpStats')
        
        game_pk = game.get('gamePk', '')
        away_team = game.get('teams', {}).get('away', {})
        home_team = game.get('teams', {}).get('home', {})
        away_name_full = away_team.get('team', {}).get('name', '')
        home_name_full = home_team.get('team', {}).get('name', '')
        
        away_name = away_team.get('team', {}).get('teamName', away_name_full.split(' ')[-1])
        home_name = home_team.get('team', {}).get('teamName', home_name_full.split(' ')[-1])
        if 'Red Sox' in away_name_full: away_name = 'Red Sox'
        if 'White Sox' in away_name_full: away_name = 'White Sox'
        if 'Blue Jays' in away_name_full: away_name = 'Blue Jays'
        if away_name == 'Diamondbacks': away_name = 'Dbacks'
        if 'Red Sox' in home_name_full: home_name = 'Red Sox'
        if 'White Sox' in home_name_full: home_name = 'White Sox'
        if 'Blue Jays' in home_name_full: home_name = 'Blue Jays'
        if home_name == 'Diamondbacks': home_name = 'Dbacks'

        # Extract and format league records safely
        a_rec = away_team.get('leagueRecord', {})
        h_rec = home_team.get('leagueRecord', {})
        
        away_record = f"({a_rec.get('wins')}-{a_rec.get('losses')})" if a_rec.get('wins') is not None else ""
        home_record = f"({h_rec.get('wins')}-{h_rec.get('losses')})" if h_rec.get('wins') is not None else ""

        away_logo = f"https://www.mlbstatic.com/team-logos/team-cap-on-light/{away_team.get('team',{}).get('id')}.svg"
        home_logo = f"https://www.mlbstatic.com/team-logos/team-cap-on-light/{home_team.get('team',{}).get('id')}.svg"
        
        game_date_obj = datetime.strptime(game.get('gameDate'), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).astimezone(pytz.timezone('America/New_York'))
        game_time = game_date_obj.strftime("%I:%M %p").lstrip('0')
        
        game_state = game.get('status', {}).get('abstractGameState', '')
        detailed_state = game.get('status', {}).get('detailedState', '')
        
        if detailed_state in ['Postponed', 'Delayed', 'Suspended', 'Cancelled', 'Delayed Start']:
            time_badge = f'<span class="badge bg-danger text-white shadow-sm border px-2 py-1" style="font-size: 0.70rem;">{detailed_state}</span>'
        elif game_state == 'Live':
            ls = game.get('linescore', {})
            a_runs = ls.get('teams', {}).get('away', {}).get('runs', away_team.get('score', 0))
            h_runs = ls.get('teams', {}).get('home', {}).get('runs', home_team.get('score', 0))
            half = ls.get('inningHalf', '')
            inn_str = f"{( 'T' if half=='Top' else ('B' if half=='Bottom' else '') )}{ls.get('currentInning','')}" or 'Live'
            time_badge = f'<span class="badge bg-primary text-white shadow-sm border px-2 py-1" style="font-size: 0.70rem;">{inn_str} {a_runs}-{h_runs}</span>'
        elif game_state == 'Final':
            ls = game.get('linescore', {})
            a_runs = ls.get('teams', {}).get('away', {}).get('runs', away_team.get('score', 0))
            h_runs = ls.get('teams', {}).get('home', {}).get('runs', home_team.get('score', 0))
            time_badge = f'<span class="badge bg-dark text-white shadow-sm border px-2 py-1" style="font-size: 0.70rem;">F {a_runs}-{h_runs}</span>'
        else:
            time_badge = f'<span class="badge bg-white text-dark shadow-sm border px-2 py-1" style="font-size: 0.70rem;">{game_time}</span>'

        right_side_html = f'<div class="text-muted fw-bold text-uppercase text-end ms-auto" style="font-size: 0.70rem; letter-spacing: 0.5px; line-height: 1.1;">{game.get("venue",{}).get("name")}</div>'
        if park_stats:
            def get_park_badge(f):
                diff = f - 100
                return f'<span class="text-success" style="font-family:sans-serif; font-size:0.70rem; font-weight:600;">+{abs(diff)}%</span>' if diff > 0 else (f'<span class="text-danger" style="font-family:sans-serif; font-size:0.70rem; font-weight:600;">-{abs(diff)}%</span>' if diff < 0 else '<span class="text-muted" style="font-family:sans-serif; font-size:0.70rem; font-weight:600;">0%</span>')
            
            lbl = "font-family:sans-serif; font-size:0.70rem; color:#495057; display: inline-block; width: 42px; text-align: right; padding-right: 4px;"
            sep = "font-family:sans-serif; font-size:0.65rem; color:#adb5bd; margin:0 3px;"
            s_blk = lambda v, l: f'<div class="d-flex align-items-baseline">{v}<span style="font-size:0.65rem; color:#6c757d; margin-left:1px;">{l}</span></div>'
            
            right_side_html = f"""
            <div class="d-flex align-items-center ms-auto">
                <div class="text-muted fw-bold text-uppercase text-end" style="font-size: 0.70rem; letter-spacing: 0.5px; max-width: 85px; white-space: normal; line-height: 1.1;">{game.get("venue",{}).get("name")}</div>
                <div class="d-flex flex-column justify-content-center border-start ps-2 ms-2" style="line-height:1.2;">
                    <div class="d-flex align-items-baseline w-100 mb-1"><span style="{lbl}">R:</span>{get_park_badge(park_stats.get('runs',100))}</div>
                    <div class="d-flex align-items-baseline w-100 mb-1"><span style="{lbl}">HR:</span>{s_blk(get_park_badge(park_stats.get('hr_l',100)), 'L')}<span style="{sep}">/</span>{s_blk(get_park_badge(park_stats.get('hr_r',100)), 'R')}</div>
                    <div class="d-flex align-items-baseline w-100"><span style="{lbl}">wOBA:</span>{s_blk(get_park_badge(park_stats.get('woba_l',100)), 'L')}<span style="{sep}">/</span>{s_blk(get_park_badge(park_stats.get('woba_r',100)), 'R')}</div>
                </div>
            </div>"""

        ml_away, ml_home, ou_html = '', '', ''
        odds_data = data.get('odds', {})
        if odds_data and odds_data.get('bookmakers'):
            h2h_market, totals_market = None, None
            for bookie in odds_data['bookmakers']:
                if not h2h_market: h2h_market = next((m for m in bookie.get('markets', []) if m['key'] == 'h2h'), None)
                if not totals_market: totals_market = next((m for m in bookie.get('markets', []) if m['key'] == 'totals'), None)
            if h2h_market:
                ao = next((o for o in h2h_market['outcomes'] if o['name'] == away_name_full), None)
                ho = next((o for o in h2h_market['outcomes'] if o['name'] == home_name_full), None)
                if ao and ao.get('price'): ml_away = f'<div class="badge bg-light text-dark border" style="font-size: 0.60rem; padding: 2px 4px; font-family: monospace;">{"+" if ao["price"] > 0 else ""}{ao["price"]}</div>'
                if ho and ho.get('price'): ml_home = f'<div class="badge bg-light text-dark border" style="font-size: 0.60rem; padding: 2px 4px; font-family: monospace;">{"+" if ho["price"] > 0 else ""}{ho["price"]}</div>'
            if totals_market and totals_market.get('outcomes'):
                ou_html = f'<span class="badge bg-secondary text-white shadow-sm border px-2 py-1 ms-2" style="font-size: 0.70rem;">O/U {totals_market["outcomes"][0].get("point")}</span>'

        a_pitcher = game.get('teams', {}).get('away', {}).get('probablePitcher', {})
        h_pitcher = game.get('teams', {}).get('home', {}).get('probablePitcher', {})
        a_hand = a_pitcher.get('pitchHand', {}).get('code', 'R') if a_pitcher else 'R'
        h_hand = h_pitcher.get('pitchHand', {}).get('code', 'R') if h_pitcher else 'R'

        away_pitcher_box = build_pitcher_header(a_pitcher, ml_away, a_hand, deep_stats, player_db)
        home_pitcher_box = build_pitcher_header(h_pitcher, ml_home, h_hand, deep_stats, player_db)

        a_proj = data.get('projectedLineups', {}).get('away', {}).get('battingOrder', [])
        h_proj = data.get('projectedLineups', {}).get('home', {}).get('battingOrder', [])
        
        a_players = game.get('lineups', {}).get('awayPlayers', [])
        h_players = game.get('lineups', {}).get('homePlayers', [])
        
        is_a_official = len(a_players) > 0
        is_h_official = len(h_players) > 0

        final_away = a_players if is_a_official else a_proj
        final_home = h_players if is_h_official else h_proj

        tracking = data.get('lineupTracking', {'away': {}, 'home': {}})
        
        def get_banner(side, is_official, has_p, team_full_name):
            if not has_p: return ''
            track = tracking.get(side, {})
            
            # Generate the URL route (e.g., /lineups/boston-red-sox/)
            team_slug = slugify(team_full_name)
            link_url = f"/lineups/{team_slug}/"
            
            # Build the anchor tags with 'd-block' and 'text-decoration-none' so they act exactly like the old divs
            if is_official:
                if track.get('status') == 'MODIFIED':
                    return f'<a href="{link_url}" class="d-block text-center py-1 fw-bold text-white w-100 border-bottom text-decoration-none" style="background-color: #dc3545; font-size: 0.75rem;">⚠️ LATE SWAP <span style="font-size:0.65rem; font-weight:normal;">({track.get("modifiedAt","")})</span></a>'
                return f'<a href="{link_url}" class="d-block text-center py-1 fw-bold text-white w-100 border-bottom text-decoration-none" style="background-color: #198754; font-size: 0.75rem;">OFFICIAL {"("+track.get("officialAt")+")" if track.get("officialAt") else ""}</a>'
            
            return f'<a href="{link_url}" class="d-block text-center py-1 fw-bold text-dark w-100 border-bottom text-decoration-none" style="background-color: #ffecb5; font-size: 0.75rem;">⏳ PROJECTED</a>'

        away_banner = get_banner('away', is_a_official, len(final_away)>0, away_name_full)
        home_banner = get_banner('home', is_h_official, len(final_home)>0, home_name_full)

        away_order = build_lineup_html(final_away, h_hand, data, player_db)
        home_order = build_lineup_html(final_home, a_hand, data, player_db)

        display_ump = f"{hp_umpire.split(' ')[0][0]}. {' '.join(hp_umpire.split(' ')[1:])}" if (' ' in hp_umpire and hp_umpire != "TBD") else hp_umpire
        ump_str = f'<span class="text-dark fw-bold">{html.escape(display_ump)}</span>'
        if ump_stats:
            raw_k = ump_stats.get('k_rate', '-')
            raw_bb = ump_stats.get('bb_rate', '-')
            raw_r = ump_stats.get('rpg', '-')

            # Safely strip out '%' signs to convert to floats for threshold comparisons
            uk = float(str(raw_k).replace('%', '').strip()) if raw_k and raw_k != '-' else 0.0
            ubb = float(str(raw_bb).replace('%', '').strip()) if raw_bb and raw_bb != '-' else 0.0
            ur = float(str(raw_r).replace('%', '').strip()) if raw_r and raw_r != '-' else 0.0
            
            # Text coloring thresholds based on parsed floats
            kc = "text-danger" if uk >= 23.0 else ("text-success" if uk <= 21.0 else "text-dark")
            bbc = "text-success" if ubb >= 9.0 else ("text-danger" if ubb <= 7.5 else "text-dark")
            rc = "text-success" if ur >= 9.5 else ("text-danger" if ur <= 8.0 else "text-dark")
            
            # Use the original raw values (like '20.8%') for the visual display strings
            ump_str += f'<span class="text-muted fw-normal" style="margin-left: 4px;">(G: <span class="text-dark fw-bold">{ump_stats.get("games", "-")}</span>•K: <span class="{kc} fw-bold">{raw_k}</span>•BB: <span class="{bbc} fw-bold">{raw_bb}</span>•Runs: <span class="{rc} fw-bold">{raw_r}</span>)</span>'

        cards_html.append(f"""
        <div class="col-md-6 col-lg-6 col-xl-4 px-1 mb-3">
            <div class="lineup-card shadow-sm border rounded bg-white overflow-hidden h-100" style="border-color: #dee2e6 !important;" id="game-{game_pk}">
                <div class="p-2 pb-1" style="background-color: #edf4f8;">
                    <div class="d-flex justify-content-between align-items-center mb-0 w-100 pb-1">
                        <div class="d-flex align-items-center flex-shrink-0">
                            {time_badge}
                            {ou_html}
                        </div>
                        {right_side_html}
                    </div>
                    <div class="d-flex justify-content-between w-100 mt-2 px-1">
                        <div class="d-flex flex-column" style="width: 48%;">
                            <div class="d-flex align-items-center text-truncate mb-1">
                                <img src="{away_logo}" style="height: 24px; width: 24px; margin-right: 6px; flex-shrink: 0;">
                                <span class="fw-bold text-truncate" style="font-size: 0.95rem;">
                                    {away_name} <span class="text-muted fw-normal" style="font-size: 0.8rem; margin-left: 2px;">{away_record}</span>
                                </span>
                            </div>
                            {away_pitcher_box}
                        </div>
                        <div class="d-flex flex-column" style="width: 48%;">
                            <div class="d-flex align-items-center text-truncate mb-1">
                                <img src="{home_logo}" style="height: 24px; width: 24px; margin-right: 6px; flex-shrink: 0;">
                                <span class="fw-bold text-truncate" style="font-size: 0.95rem;">
                                    {home_name} <span class="text-muted fw-normal" style="font-size: 0.8rem; margin-left: 2px;">{home_record}</span>
                                </span>
                            </div>
                            {home_pitcher_box}
                        </div>
                    </div>
                </div>
                
                <!-- Reconfigured Sub-tabs Button Layout (Acts as stats toggles) -->
                <div class="d-flex justify-content-center align-items-center gap-1 my-2 px-2 pb-2 border-bottom w-100">
                    <button class="btn btn-sm fw-bold rounded-pill px-2 py-1 tab-btn flex-grow-1 btn-outline-secondary text-muted" style="font-size: 0.65rem;" onclick="switchGameTab('{game_pk}', 'season', this)">SEASON</button>
                    <button class="btn btn-sm fw-bold rounded-pill px-2 py-1 tab-btn flex-grow-1 btn-outline-secondary text-muted" style="font-size: 0.65rem;" onclick="switchGameTab('{game_pk}', 'vsp', this)">VS P</button>
                    <button class="btn btn-sm fw-bold rounded-pill px-2 py-1 tab-btn flex-grow-1 btn-outline-secondary text-muted" style="font-size: 0.65rem;" onclick="switchGameTab('{game_pk}', 'splits', this)">SPLITS</button>
                    <button class="btn btn-sm fw-bold rounded-pill px-2 py-1 tab-btn flex-grow-1 btn-outline-secondary text-muted" style="font-size: 0.65rem;" onclick="switchGameTab('{game_pk}', 'fd', this)">FD</button>
                    <button class="btn btn-sm fw-bold rounded-pill px-2 py-1 tab-btn flex-grow-1 btn-outline-secondary text-muted" style="font-size: 0.65rem;" onclick="switchGameTab('{game_pk}', 'dk', this)">DK</button>
                </div>
                
                <div class="row g-0 bg-white stats-collapse">
                    <div class="col-6 border-end">
                        {away_banner}
                        {away_order}
                    </div>
                    <div class="col-6">
                        {home_banner}
                        {home_order}
                    </div>
                </div>
                
                <!-- Added Expand/Collapse Support for Stats -->
                <div class="px-2 py-1 text-center bg-white border-top">
                    <button class="btn btn-link btn-sm card-toggle-btn text-muted fw-bold p-0 text-decoration-none" style="font-size: 0.70rem;">[-] Collapse Matchups</button>
                </div>
                
                <div class="px-2 py-1 border-top border-bottom text-center text-truncate" style="background-color: #f8f9fa; font-size: 0.70rem; letter-spacing: 0.5px;">
                    <span class="text-muted fw-bold text-uppercase">HP:</span> {ump_str}
                </div>
                <div class="p-2 text-center bg-white">
                    <a href="https://weathermlb.com/#game-{game_pk}" target="_blank" class="btn btn-sm w-100 promo-btn" style="background-color: #f8f9fa; border: 1px solid #dee2e6; color: #0d6efd;">
                        🌧️ View Weather & Wind Impact
                    </a>
                </div>
            </div>
        </div>""")

    return "\n".join(cards_html)

# ==========================================
# 5. MAIN PIPELINE
# ==========================================
def main():
    player_db = {}
    if os.path.exists('data/player_master_data.json'):
        with open('data/player_master_data.json', 'r', encoding='utf-8') as f:
            player_db = json.load(f)

    yest, today, tom = get_3day_dates()
    
    html_yest = generate_games_html(yest, player_db)
    html_today = generate_games_html(today, player_db)
    html_tom = generate_games_html(tom, player_db)

    # Generate Google Schema strictly for TODAY'S games
    today_schema = generate_games_schema(today)
    
    # Format a human-readable header date (e.g., "July 20, 2026")
    import datetime as dt_module
    pretty_today = dt_module.datetime.strptime(today, "%Y-%m-%d").strftime("%B %d, %Y")
    pretty_yest = dt_module.datetime.strptime(yest, "%Y-%m-%d").strftime("%B %d, %Y")
    pretty_tom = dt_module.datetime.strptime(tom, "%Y-%m-%d").strftime("%B %d, %Y")
    
    # Perform the replacements
    output = BASE_TEMPLATE.replace('<!-- GALAXY_YESTERDAY -->', html_yest)
    output = output.replace('<!-- GALAXY_TODAY -->', html_today)
    output = output.replace('<!-- GALAXY_TOMORROW -->', html_tom)
    
    # Inject the new SEO targeting schemas and dynamic UI dates
    output = output.replace('<!-- DYNAMIC_GAMES_SCHEMA -->', today_schema)
    output = output.replace('<!-- PRETTY_TODAY -->', pretty_today)
    output = output.replace('<!-- PRETTY_YEST -->', pretty_yest)
    output = output.replace('<!-- PRETTY_TOM -->', pretty_tom)
    
    existing_html = ""
    if os.path.exists('index.html'):
        with open('index.html', 'r', encoding='utf-8') as f:
            existing_html = f.read()

    if output != existing_html:
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(output)
        
        # --- NEW: Queue the homepage for IndexNow ---
        queue_urls_for_indexnow(["https://mlbstartingnine.com/"])
        
        # --- NEW: Update the XML Sitemap Date for the Homepage ---
        update_homepage_sitemap_date("https://mlbstartingnine.com/")
        
        print(f"Build Complete! Target Dates -> Yesterday: {yest} | Today: {today} | Tomorrow: {tom} (Updates Queued & Sitemap Modified)")
    else:
        print(f"Build Complete! Target Dates -> Yesterday: {yest} | Today: {today} | Tomorrow: {tom} (No Changes Detected)")

if __name__ == "__main__":
    main()
