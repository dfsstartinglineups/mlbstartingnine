import os
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timezone

# ==========================================
# 1. CONFIGURATION & FILE PATHS
# ==========================================
DOMAIN = "https://mlbstartingnine.com"
SITEMAP_OUTPUT_PATH = "sitemap-bullpen.xml"
QUEUE_FILE = "data/updates_queue.json"
BULLPEN_DATA_PATH = "data/bullpen_data.json"
MASTER_DATA_PATH = "data/player_master_data.json"
OUTPUT_TEAMS_DIR = "teams"
OUTPUT_HUB_DIR = os.path.join("reports", "bullpens")

# ==========================================
# 2. CORE UTILITIES
# ==========================================
def load_json_safe(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def slugify(text):
    if not text:
        return ""
    text = str(text).lower()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[\s-]+', '-', text).strip()

def get_rank_color_class(rank):
    if not rank: return "text-muted"
    if rank <= 5: return "text-success fw-bold"
    elif rank >= 26: return "text-danger fw-bold"
    return "text-muted fw-bold"

def get_status_badge(status):
    if status == "Available":
        return '<span class="badge bg-success shadow-sm w-100 py-1" style="font-size: 0.65rem;">AVAILABLE</span>'
    elif status == "Tired":
        return '<span class="badge bg-warning text-dark shadow-sm w-100 py-1" style="font-size: 0.65rem;">TIRED</span>'
    else:
        return '<span class="badge bg-danger shadow-sm w-100 py-1" style="font-size: 0.65rem;">UNAVAILABLE</span>'

def get_pitch_cell(count):
    if count == 0:
        return '<td class="text-muted" style="background-color: #f8f9fa;">-</td>'
    elif count >= 20:
        return f'<td class="fw-bold" style="background-color: #f8d7da; color: #842029;">{count}</td>'
    else:
        return f'<td class="fw-bold">{count}</td>'

# ==========================================
# 3. SITEMAP & INDEXING UTILITIES
# ==========================================
def update_sitemap(all_urls, updated_urls):
    existing_data = {}
    if os.path.exists(SITEMAP_OUTPUT_PATH):
        try:
            ET.register_namespace('', "http://www.sitemaps.org/schemas/sitemap/0.9")
            tree = ET.parse(SITEMAP_OUTPUT_PATH)
            root = tree.getroot()
            for url_node in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
                loc_node = url_node.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
                lastmod_node = url_node.find("{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod")
                if loc_node is not None and loc_node.text:
                    loc = loc_node.text.strip()
                    lastmod = lastmod_node.text.strip() if lastmod_node is not None and lastmod_node.text else None
                    existing_data[loc] = lastmod
        except Exception:
            pass

    final_urls = sorted(list(set(all_urls).union(existing_data.keys())))
    today_str = datetime.now(timezone.utc).isoformat(timespec='seconds')
    xml_root = ET.Element('urlset', xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    
    for url in final_urls:
        url_node = ET.SubElement(xml_root, 'url')
        ET.SubElement(url_node, 'loc').text = url
        lastmod = today_str if url in updated_urls else (existing_data.get(url) or today_str)
        ET.SubElement(url_node, 'lastmod').text = lastmod

    raw_xml = ET.tostring(xml_root, 'utf-8')
    parsed_xml = minidom.parseString(raw_xml)
    pretty_xml = parsed_xml.toprettyxml(indent="  ")
    
    with open(SITEMAP_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join([line for line in pretty_xml.splitlines() if line.strip()]))

def queue_urls_for_indexnow(new_urls, queue_file=QUEUE_FILE):
    if not new_urls: return
    if not os.path.exists(queue_file):
        os.makedirs(os.path.dirname(queue_file), exist_ok=True)
        queue_data = {"last_sent": "2000-01-01T00:00:00", "urls": []}
    else:
        with open(queue_file, "r", encoding="utf-8") as f:
            try: queue_data = json.load(f)
            except json.JSONDecodeError: queue_data = {"last_sent": "2000-01-01T00:00:00", "urls": []}

    queue_data["urls"].extend(new_urls)
    with open(queue_file, "w", encoding="utf-8") as f: json.dump(queue_data, f, indent=2)

# ==========================================
# 4. HEATMAP GENERATOR UTILITY
# ==========================================
def build_heatmap_rows(relievers, player_db):
    heat_map_rows = ""
    for r in relievers:
        pid = str(r.get("player_id", ""))
        name = r.get("name", "Unknown")
        status = r.get("status", "Available")
        era = r.get("era", "-")
        whip = r.get("whip", "-")
        appearances = r.get("recent_appearances", 0)
        pitches = r.get("pitches_last_5", [0,0,0,0,0])
        
        headshot = f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:brooks:default/w_180,q_auto:best/v1/people/{pid}/headshot/67/current"
        master_key = f"ID{pid}"
        p_slug = player_db.get(master_key, {}).get("slug")
        
        # Cross-reference the player DB to build the profile link
        name_html = f'<a href="/players/{p_slug}/" class="text-dark fw-bold text-decoration-none">{name}</a>' if p_slug else f'<span class="text-dark fw-bold">{name}</span>'
            
        heat_map_rows += f"""
        <tr class="bg-white">
            <td class="text-start align-middle ps-3 border-end">
                <div class="d-flex align-items-center">
                    <img src="{headshot}" style="width: 28px; height: 28px; border-radius: 50%; border: 1px solid #dee2e6; object-fit: cover; background: #fff; margin-right: 8px;">
                    {name_html}
                </div>
            </td>
            <td class="align-middle fw-bold text-dark">{era}</td>
            <td class="align-middle fw-bold text-dark border-end">{whip}</td>
            <td class="align-middle border-end" style="width: 110px;">{get_status_badge(status)}</td>
            <td class="align-middle fw-bold text-muted border-end">{appearances}</td>
            {get_pitch_cell(pitches[0])}
            {get_pitch_cell(pitches[1])}
            {get_pitch_cell(pitches[2])}
            {get_pitch_cell(pitches[3])}
            {get_pitch_cell(pitches[4])}
        </tr>"""
    return heat_map_rows

# ==========================================
# 5. HUB PAGE BUILDER (LEAGUE AGGREGATE)
# ==========================================
def generate_hub_html(bullpen_data, player_db):
    page_url = f"{DOMAIN}/reports/bullpens/"
    
    tbody_groups = []
    
    for team_slug, data in bullpen_data.items():
        team_name = data.get("team", "Unknown Team")
        team_id = data.get("team_id", "")
        stats = data.get("bullpen_stats", {})
        relievers = data.get("active_relievers", [])
        
        team_logo_url = f"https://www.mlbstatic.com/team-logos/team-cap-on-light/{team_id}.svg" if team_id else ""
        available_count = sum(1 for r in relievers if r.get("status") == "Available")
        total_arms = len(relievers)
        
        era = float(stats.get("era", {}).get("value", 99.99))
        whip = float(stats.get("whip", {}).get("value", 99.99))
        k9 = float(stats.get("k_per_9", {}).get("value", 0))
        saves = int(stats.get("saves", {}).get("value", 0))
        
        def get_hub_val(key, is_float=True):
            val = stats.get(key, {}).get("value", "-")
            if val == "-": return "-"
            if key == "baa": return f".{str(val).split('.')[-1].ljust(3, '0')}"
            return f"{float(val):.2f}" if is_float else str(val)

        heatmap = build_heatmap_rows(relievers, player_db)

        tbody_html = f"""
        <tbody class="team-group" data-era="{era}" data-whip="{whip}" data-k9="{k9}" data-saves="{saves}">
            <!-- Main Summary Row -->
            <tr class="accordion-toggle align-middle" data-bs-toggle="collapse" data-bs-target="#collapse-{team_slug}" style="cursor: pointer;">
                <td class="text-start fw-bold text-dark ps-3 border-end position-relative">
                    <div class="d-flex align-items-center justify-content-between">
                        <div class="d-flex align-items-center">
                            <span class="text-primary me-2" style="font-size: 0.7rem;">▶</span>
                            <img src="{team_logo_url}" style="width: 24px; height: 24px; object-fit: contain; margin-right: 8px;">
                            {team_name}
                        </div>
                        <a href="/teams/{team_slug}/bullpen/" class="btn btn-sm text-primary p-0 ms-2 text-decoration-none" title="Go to {team_name} Full Report" onclick="event.stopPropagation();">🔗</a>
                    </div>
                </td>
                <td class="fw-bold text-dark">{get_hub_val('era')}</td>
                <td class="fw-bold text-dark border-end">{get_hub_val('whip')}</td>
                <td class="text-muted">{get_hub_val('k_per_9')}</td>
                <td class="text-muted">{get_hub_val('bb_per_9')}</td>
                <td class="text-muted border-end">{get_hub_val('baa')}</td>
                <td class="fw-bold text-success">{get_hub_val('saves', False)}</td>
                <td class="fw-bold text-secondary border-end">{get_hub_val('holds', False)}</td>
                <td class="fw-bold text-primary">{available_count} / {total_arms}</td>
            </tr>
            <!-- Collapsible Detail Heatmap -->
            <tr id="collapse-{team_slug}" class="collapse collapse-row">
                <td colspan="9" class="p-0 border-0">
                    <div class="p-3 pb-4" style="background-color: #f8f9fa; border-bottom: 3px solid #dee2e6;">
                        <div class="d-flex justify-content-between align-items-end mb-2">
                            <h6 class="fw-bold mb-0 text-dark">🔥 5-Day Pitch Count Heat Map</h6>
                            <a href="/teams/{team_slug}/bullpen/" class="btn btn-sm btn-outline-primary fw-bold" style="font-size: 0.75rem;">View Full {team_name} Report →</a>
                        </div>
                        <div class="table-responsive bg-white border rounded shadow-sm">
                            <table class="table table-bordered text-center align-middle mb-0 m-0" style="font-size:0.8rem; min-width: 750px;">
                                <thead class="table-dark text-white fw-bold">
                                    <tr>
                                        <th class="text-start ps-3 border-end">Pitcher</th>
                                        <th>ERA</th>
                                        <th class="border-end">WHIP</th>
                                        <th style="min-width: 100px;" class="border-end">Status</th>
                                        <th style="font-size:0.7rem;" class="border-end">App<br>(L5)</th>
                                        <th>Yest</th>
                                        <th>2 Days</th>
                                        <th>3 Days</th>
                                        <th>4 Days</th>
                                        <th>5 Days</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {heatmap}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </td>
            </tr>
        </tbody>"""
        tbody_groups.append(tbody_html)

    tbody_groups_sorted = sorted(tbody_groups, key=lambda tb: float(re.search(r'data-era="([0-9.]+)"', tb).group(1)))

    schema = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": "MLB Bullpen Reports & Pitch Count Rankings",
        "url": page_url,
        "description": "Interactive MLB bullpen reports. Sort all 30 teams by ERA, WHIP, and saves, and instantly expand to view 5-day pitcher fatigue heat maps."
    }

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-TW817924LJ"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', 'G-TW817924LJ');
    </script>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MLB Bullpen Reports & Pitch Count Heat Maps | DFS Rankings</title>
    <meta name="description" content="Interactive MLB bullpen reports. Sort all 30 teams by ERA, WHIP, and saves, and instantly expand to view 5-day pitcher fatigue heat maps.">
    <meta name="keywords" content="MLB bullpen rankings, bullpen pitcher stats, relief pitcher fatigue, pitch count heat map, MLB closer rankings, DFS baseball tools">
    <link rel="canonical" href="{page_url}" />
    <link rel="icon" href="/favicon.ico" sizes="any">
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    
    <meta property="og:site_name" content="MLB Starting Nine">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{page_url}">
    <meta property="og:title" content="MLB Bullpen Reports & Pitch Count Heat Maps">
    <meta property="og:description" content="Interactive MLB bullpen reports. Sort all 30 teams by ERA, WHIP, and saves, and instantly expand to view 5-day pitcher fatigue heat maps.">
    
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script type="application/ld+json">\n{json.dumps(schema, indent=2)}\n    </script>
    <style>
        body {{ background-color: #f1f3f5; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        .header-brand {{ font-weight: 900; letter-spacing: -1px; font-size: 2rem; color: #fff; font-style: italic; text-shadow: 0 2px 4px rgba(0,0,0,0.5); }}
        .header-brand a {{ color: inherit; text-decoration: none; }}
        .header-brand span {{ background: linear-gradient(to bottom, #7CD0FF 0%, #1A8CFF 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; padding-right: 2px; display: inline-block; }}
        .hub-table th {{ background-color: #212529; color: #fff; cursor: pointer; user-select: none; font-size: 0.8rem; text-transform: uppercase; padding: 12px; }}
        .hub-table th:hover {{ background-color: #343a40; }}
        .accordion-toggle:hover {{ background-color: #f8f9fa; }}
    </style>
</head>
<body>
<nav class="navbar shadow-sm py-3 mb-4" style="background-color: #212529;">
    <div class="container d-flex justify-content-between align-items-center flex-wrap">
        <div class="header-brand mb-0"><a href="/">MLB Starting <span>Nine</span></a></div>
        <div><a href="/" class="btn btn-sm btn-outline-light font-weight-bold">← Back to Starting Lineups</a></div>
    </div>
</nav>

<div class="container px-2 px-md-3 pb-5">
    <div class="text-center mb-4">
        <h1 class="h3 fw-bold text-dark mb-2">MLB Bullpen Reports & Fatigue Rankings</h1>
        <p class="text-muted">Sort the league by performance metrics. Click any team row to view their daily reliever availability and 5-day pitch count heat map.</p>
    </div>

    <div class="d-flex justify-content-end gap-2 mb-3">
        <button id="btn-expand" class="btn btn-sm btn-outline-primary fw-bold shadow-sm bg-white">↕ Expand All</button>
        <button id="btn-collapse" class="btn btn-sm btn-outline-secondary fw-bold shadow-sm bg-white">⇡ Collapse All</button>
    </div>

    <div class="card shadow-sm border rounded bg-white overflow-hidden mb-4">
        <div class="table-responsive">
            <table class="table text-center align-middle mb-0 hub-table" id="main-hub-table" style="min-width: 900px;">
                <thead>
                    <tr>
                        <th class="text-start ps-3 border-end" onclick="sortTable('team')">Team ↕</th>
                        <th onclick="sortTable('era')">ERA ↕</th>
                        <th class="border-end" onclick="sortTable('whip')">WHIP ↕</th>
                        <th onclick="sortTable('k9')">K/9 ↕</th>
                        <th onclick="sortTable('bb9')">BB/9</th>
                        <th class="border-end">BAA</th>
                        <th onclick="sortTable('saves')">Saves ↕</th>
                        <th class="border-end">Holds</th>
                        <th>Available Arms</th>
                    </tr>
                </thead>
                {''.join(tbody_groups_sorted)}
            </table>
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
    document.getElementById('btn-expand').addEventListener('click', () => {{
        document.querySelectorAll('.collapse-row').forEach(row => row.classList.add('show'));
    }});
    document.getElementById('btn-collapse').addEventListener('click', () => {{
        document.querySelectorAll('.collapse-row').forEach(row => row.classList.remove('show'));
    }});

    let sortState = {{ 'era': 1, 'whip': 1, 'k9': -1, 'saves': -1, 'team': 1 }};

    function sortTable(key) {{
        const table = document.getElementById('main-hub-table');
        const tbodies = Array.from(table.querySelectorAll('tbody.team-group'));
        const dir = sortState[key] || 1;
        
        tbodies.sort((a, b) => {{
            if (key === 'team') {{
                const nameA = a.querySelector('.text-start').textContent.trim();
                const nameB = b.querySelector('.text-start').textContent.trim();
                return nameA.localeCompare(nameB) * dir;
            }} else {{
                const valA = parseFloat(a.getAttribute(`data-${{key}}`)) || 0;
                const valB = parseFloat(b.getAttribute(`data-${{key}}`)) || 0;
                return (valA - valB) * dir;
            }}
        }});
        
        tbodies.forEach(tb => table.appendChild(tb));
        sortState[key] = dir * -1;
    }}
</script>
</body>
</html>"""

# ==========================================
# 6. INDIVIDUAL TEAM BUILDER
# ==========================================
def generate_team_bullpen_html(team_slug, data, player_db):
    team_name = data.get("team", "Unknown Team")
    team_id = data.get("team_id", "")
    stats = data.get("bullpen_stats", {})
    relievers = data.get("active_relievers", [])
    
    page_url = f"{DOMAIN}/teams/{team_slug}/bullpen/"
    team_logo_url = f"https://www.mlbstatic.com/team-logos/team-cap-on-light/{team_id}.svg" if team_id else ""
    available_count = sum(1 for r in relievers if r.get("status") == "Available")
    total_arms = len(relievers)
    
    def build_stat_card(label, key, is_float=True):
        stat_node = stats.get(key, {})
        val = stat_node.get("value", "-")
        rank = stat_node.get("rank", 0)
        display_val = f"{float(val):.2f}" if is_float and val != "-" else str(val)
        if key == "baa" and val != "-": display_val = f".{str(display_val).split('.')[-1].ljust(3, '0')}"
        color_class = get_rank_color_class(rank)
        return f"""
        <div class="col-4">
            <div class="border rounded p-2 text-center bg-white shadow-sm h-100">
                <div class="text-muted fw-bold" style="font-size: 0.65rem;">{label}</div>
                <div class="d-flex justify-content-center align-items-end gap-1">
                    <span class="fs-5 fw-bold text-dark">{display_val}</span>
                    <span class="{color_class} mb-1" style="font-size: 0.7rem;">({rank})</span>
                </div>
            </div>
        </div>"""

    stat_grid = f"""
    <div class="row g-2 mb-4">
        {build_stat_card('ERA', 'era')}
        {build_stat_card('WHIP', 'whip')}
        {build_stat_card('BAA', 'baa')}
        {build_stat_card('K/9', 'k_per_9')}
        {build_stat_card('BB/9', 'bb_per_9')}
        {build_stat_card('HR/9', 'hr_per_9')}
        {build_stat_card('SAVES', 'saves', is_float=False)}
        {build_stat_card('HOLDS', 'holds', is_float=False)}
        {build_stat_card('BLOWN SV', 'blown_saves', is_float=False)}
    </div>"""

    heat_map_rows = build_heatmap_rows(relievers, player_db)

    schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{DOMAIN}/"},
            {"@type": "ListItem", "position": 2, "name": "League Bullpens", "item": f"{DOMAIN}/reports/bullpens/"},
            {"@type": "ListItem", "position": 3, "name": f"{team_name} Bullpen", "item": page_url}
        ]
    }

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-TW817924LJ"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', 'G-TW817924LJ');
    </script>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Today's {team_name} Bullpen Usage, Rest Report & Rankings</title>
    <meta name="description" content="Get today's {team_name} bullpen pitch counts, fatigue status, season-long reliever performance rankings, and daily relief pitcher availability.">
    <link rel="canonical" href="{page_url}" />
    <link rel="icon" href="/favicon.ico" sizes="any">
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">
    
    <meta property="og:site_name" content="MLB Starting Nine">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{page_url}">
    <meta property="og:title" content="Today's {team_name} Bullpen Usage, Rest Report & Rankings">
    <meta property="og:description" content="Get today's {team_name} bullpen pitch counts, fatigue status, season-long reliever performance rankings, and daily relief pitcher availability.">
    
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script type="application/ld+json">\n{json.dumps(schema, indent=2)}\n    </script>
    <style>
        body {{ background-color: #f1f3f5; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        .header-brand {{ font-weight: 900; letter-spacing: -1px; font-size: 2rem; color: #fff; font-style: italic; text-shadow: 0 2px 4px rgba(0,0,0,0.5); }}
        .header-brand a {{ color: inherit; text-decoration: none; }}
        .header-brand span {{ background: linear-gradient(to bottom, #7CD0FF 0%, #1A8CFF 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; padding-right: 2px; display: inline-block; }}
    </style>
</head>
<body>
<nav class="navbar shadow-sm py-3 mb-4" style="background-color: #212529;">
    <div class="container d-flex justify-content-between align-items-center flex-wrap">
        <div class="header-brand mb-0"><a href="/">MLB Starting <span>Nine</span></a></div>
        <div>
            <a href="/reports/bullpens/" class="btn btn-sm btn-outline-light font-weight-bold me-2">📊 MLB Bullpen Report</a>
            <a href="/lineups/{team_slug}/" class="btn btn-sm btn-outline-light font-weight-bold">← Team Lineups</a>
        </div>
    </div>
</nav>

<div class="container px-2 px-md-3 pb-5">
    <div class="row justify-content-center">
        <div class="col-lg-10 col-xl-9">
            
            <div class="d-flex align-items-center mb-4 gap-3">
                <img src="{team_logo_url}" style="width: 65px; height: 65px; object-fit: contain;">
                <div>
                    <h1 class="h3 fw-bold text-dark mb-0">Today's {team_name} Bullpen Report</h1>
                    <p class="text-muted mb-0 fw-semibold" style="font-size: 0.9rem;">Reliever Fatigue, Pitch Counts & Season Rankings</p>
                </div>
            </div>

            <div class="card shadow-sm border-0 mb-4" style="border-left: 4px solid #0d6efd !important;">
                <div class="card-body p-3 bg-white rounded-end d-flex justify-content-between align-items-center">
                    <div>
                        <span class="fw-bold text-dark d-block" style="font-size: 1.1rem;">Bullpen Status</span>
                        <span class="text-muted" style="font-size: 0.85rem;">{available_count} of {total_arms} active arms are fully rested today.</span>
                    </div>
                    <span class="badge bg-primary fs-5 px-3 py-2 shadow-sm">{available_count} / {total_arms}</span>
                </div>
            </div>

            <h5 class="fw-bold mb-3 text-dark border-bottom pb-2" style="font-size: 1rem;">📊 Season Performance Rankings</h5>
            {stat_grid}

            <h5 class="fw-bold mb-3 text-dark border-bottom pb-2 mt-2" style="font-size: 1rem;">🔥 5-Day Pitch Count Heat Map</h5>
            <div class="card shadow-sm border rounded bg-white overflow-hidden mb-4">
                <div class="table-responsive">
                    <table class="table table-bordered text-center align-middle mb-0" style="font-size:0.8rem; min-width: 750px;">
                        <thead class="table-dark text-white fw-bold">
                            <tr>
                                <th class="text-start ps-3 border-end">Pitcher</th>
                                <th>ERA</th>
                                <th class="border-end">WHIP</th>
                                <th style="min-width: 100px;" class="border-end">Status</th>
                                <th style="font-size:0.7rem;" class="border-end">Appearances<br>(Last 5)</th>
                                <th>Yest</th>
                                <th>2 Days</th>
                                <th>3 Days</th>
                                <th>4 Days</th>
                                <th>5 Days</th>
                            </tr>
                        </thead>
                        <tbody>
                            {heat_map_rows}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""

# ==========================================
# 7. MAIN EXECUTION
# ==========================================
def main():
    print("🔨 Starting Bullpen HTML Generator...")
    
    bullpen_data = load_json_safe(BULLPEN_DATA_PATH)
    if not bullpen_data:
        print("⚠️ No bullpen data found. Exiting.")
        return

    player_db = load_json_safe(MASTER_DATA_PATH)
    all_urls = []
    updated_urls = []
    
    # 1. Build Individual Team Pages
    for team_slug, data in bullpen_data.items():
        team_dir = os.path.join(OUTPUT_TEAMS_DIR, team_slug, "bullpen")
        os.makedirs(team_dir, exist_ok=True)
        index_path = os.path.join(team_dir, "index.html")
        page_url = f"{DOMAIN}/teams/{team_slug}/bullpen/"
        all_urls.append(page_url)
        
        new_html = generate_team_bullpen_html(team_slug, data, player_db)
        
        existing_html = ""
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f: existing_html = f.read()

        if new_html != existing_html:
            with open(index_path, "w", encoding="utf-8") as f: f.write(new_html)
            updated_urls.append(page_url)
            print(f"   ✅ Built Team: {team_slug}")

    # 2. Build Master Hub Page (/reports/bullpens/)
    os.makedirs(OUTPUT_HUB_DIR, exist_ok=True)
    hub_index_path = os.path.join(OUTPUT_HUB_DIR, "index.html")
    hub_url = f"{DOMAIN}/reports/bullpens/"
    all_urls.append(hub_url)
    
    new_hub_html = generate_hub_html(bullpen_data, player_db)
    
    existing_hub = ""
    if os.path.exists(hub_index_path):
        with open(hub_index_path, "r", encoding="utf-8") as f: existing_hub = f.read()
        
    if new_hub_html != existing_hub:
        with open(hub_index_path, "w", encoding="utf-8") as f: f.write(new_hub_html)
        updated_urls.append(hub_url)
        print(f"   ✅ Built Hub: /reports/bullpens/")

    # 3. Post-Build Ping & Sitemap
    update_sitemap(all_urls, updated_urls)
    if updated_urls:
        queue_urls_for_indexnow(updated_urls)
        print(f"🚀 Queued {len(updated_urls)} updated URLs for IndexNow.")
        
    print("🏁 Build Complete!")

if __name__ == "__main__":
    main()
