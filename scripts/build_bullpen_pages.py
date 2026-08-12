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
SITEMAP_OUTPUT_PATH = "sitemap.xml"
QUEUE_FILE = "data/updates_queue.json"
BULLPEN_DATA_PATH = "data/bullpen_data.json"
MASTER_DATA_PATH = "data/player_master_data.json"
OUTPUT_TEAMS_DIR = "teams"

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
    """Assigns color-coding to stats based on league-wide rank (1-30)."""
    if not rank:
        return "text-muted"
    if rank <= 5:
        return "text-success fw-bold"
    elif rank >= 26:
        return "text-danger fw-bold"
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
    if not new_urls:
        return
    if not os.path.exists(queue_file):
        os.makedirs(os.path.dirname(queue_file), exist_ok=True)
        queue_data = {"last_sent": "2000-01-01T00:00:00", "urls": []}
    else:
        with open(queue_file, "r", encoding="utf-8") as f:
            try:
                queue_data = json.load(f)
            except json.JSONDecodeError:
                queue_data = {"last_sent": "2000-01-01T00:00:00", "urls": []}

    queue_data["urls"].extend(new_urls)
    with open(queue_file, "w", encoding="utf-8") as f:
        json.dump(queue_data, f, indent=2)

# ==========================================
# 4. HTML BUILDER
# ==========================================
def generate_team_bullpen_html(team_slug, data, player_db):
    team_name = data.get("team", "Unknown Team")
    team_id = data.get("team_id", "")
    stats = data.get("bullpen_stats", {})
    relievers = data.get("active_relievers", [])
    
    page_url = f"{DOMAIN}/teams/{team_slug}/bullpen/"
    team_logo_url = f"https://www.mlbstatic.com/team-logos/team-cap-on-light/{team_id}.svg" if team_id else "https://www.mlbstatic.com/team-logos/team-cap-on-light/blank.svg"
    
    available_count = sum(1 for r in relievers if r.get("status") == "Available")
    total_arms = len(relievers)
    
    # --- 3x3 STAT GRID ---
    def build_stat_card(label, key, is_float=True):
        stat_node = stats.get(key, {})
        val = stat_node.get("value", "-")
        rank = stat_node.get("rank", 0)
        
        display_val = f"{float(val):.2f}" if is_float and val != "-" else str(val)
        if key == "baa" and val != "-":
            display_val = f".{str(display_val).split('.')[-1].ljust(3, '0')}"
            
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

    # --- HEAT MAP ---
    heat_map_rows = ""
    for r in relievers:
        pid = str(r.get("player_id", ""))
        name = r.get("name", "Unknown")
        status = r.get("status", "Available")
        appearances = r.get("recent_appearances", 0)
        pitches = r.get("pitches_last_5", [0,0,0,0,0])
        
        headshot = f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:brooks:default/w_180,q_auto:best/v1/people/{pid}/headshot/67/current"
        
        master_key = f"ID{pid}"
        p_slug = player_db.get(master_key, {}).get("slug")
        
        if p_slug:
            name_html = f'<a href="/players/{p_slug}/" class="text-dark fw-bold text-decoration-none">{name}</a>'
        else:
            name_html = f'<span class="text-dark fw-bold">{name}</span>'
            
        heat_map_rows += f"""
        <tr>
            <td class="text-start align-middle ps-3">
                <div class="d-flex align-items-center">
                    <img src="{headshot}" style="width: 30px; height: 30px; border-radius: 50%; border: 1px solid #dee2e6; object-fit: cover; background: #fff; margin-right: 8px;">
                    {name_html}
                </div>
            </td>
            <td class="align-middle">{get_status_badge(status)}</td>
            <td class="align-middle fw-bold text-muted">{appearances}</td>
            {get_pitch_cell(pitches[0])}
            {get_pitch_cell(pitches[1])}
            {get_pitch_cell(pitches[2])}
            {get_pitch_cell(pitches[3])}
            {get_pitch_cell(pitches[4])}
        </tr>"""

    # --- STRUCTURED DATA ---
    schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{DOMAIN}/"},
            {"@type": "ListItem", "position": 2, "name": f"{team_name} Lineups", "item": f"{DOMAIN}/lineups/{team_slug}/"},
            {"@type": "ListItem", "position": 3, "name": "Bullpen Report", "item": page_url}
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
    <title>{team_name} Bullpen Usage, Rest Report & Rankings</title>
    <meta name="description" content="Get today's {team_name} bullpen pitch counts, fatigue status, season-long reliever performance rankings, and daily relief pitcher availability.">
    <link rel="canonical" href="{page_url}" />
    <link rel="icon" href="/favicon.ico" sizes="any">
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">
    
    <meta property="og:site_name" content="MLB Starting Nine">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{page_url}">
    <meta property="og:title" content="{team_name} Bullpen Usage, Rest Report & Rankings">
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
        <div><a href="/lineups/{team_slug}/" class="btn btn-sm btn-outline-light font-weight-bold">← Team Lineups</a></div>
    </div>
</nav>

<div class="container px-2 px-md-3 pb-5">
    <div class="row justify-content-center">
        <div class="col-lg-10 col-xl-9">
            
            <div class="d-flex align-items-center mb-4 gap-3">
                <img src="{team_logo_url}" style="width: 65px; height: 65px; object-fit: contain;">
                <div>
                    <h1 class="h3 fw-bold text-dark mb-0">{team_name} Bullpen Report</h1>
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
                    <table class="table table-bordered text-center align-middle mb-0" style="font-size:0.8rem; min-width: 650px;">
                        <thead class="table-dark text-white fw-bold">
                            <tr>
                                <th class="text-start ps-3">Pitcher</th>
                                <th style="min-width: 100px;">Status</th>
                                <th style="font-size:0.7rem;">Appearances<br>(Last 5)</th>
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
# 5. MAIN PIPELINE
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
    
    for team_slug, data in bullpen_data.items():
        team_dir = os.path.join(OUTPUT_TEAMS_DIR, team_slug, "bullpen")
        os.makedirs(team_dir, exist_ok=True)
        index_path = os.path.join(team_dir, "index.html")
        
        page_url = f"{DOMAIN}/teams/{team_slug}/bullpen/"
        all_urls.append(page_url)
        
        new_html = generate_team_bullpen_html(team_slug, data, player_db)
        
        existing_html = ""
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                existing_html = f.read()

        if new_html != existing_html:
            with open(index_path, "w", encoding="utf-8") as f:
                f.write(new_html)
            updated_urls.append(page_url)
            print(f"   ✅ Built: {team_slug}")

    # TEMPORARILY DISABLED: Indexing and Sitemap updates turned off until launch
    # update_sitemap(all_urls, updated_urls)
    # if updated_urls:
    #     queue_urls_for_indexnow(updated_urls)
    #     print(f"🚀 Queued {len(updated_urls)} updated URLs for IndexNow.")
        
    print("🏁 Build Complete! (Sitemap and IndexNow updates bypassed)")

if __name__ == "__main__":
    main()
