import os
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from xml.dom import minidom

# Path Configurations
MASTER_DATA_PATH = "data/player_master_data.json"
OUTPUT_PLAYERS_DIR = "players"
SITEMAP_OUTPUT_PATH = "sitemap.xml"
DOMAIN = "https://mlbstartingnine.com"

def slugify(text):
    """Converts a player name into a clean, URL-safe SEO slug."""
    text = text.lower()
    # Normalize accents (e.g., James Domínguez -> james dominguez)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    # Strip out punctuation like apostrophes or periods (e.g., Ryan O'Hearn -> ryan ohearn)
    text = re.sub(r"[^\w\s-]", "", text)
    # Replace spaces with standard clean dashes
    text = re.sub(r"[\s-]+", "-", text).strip("-")
    return text

def update_sitemap(new_player_urls):
    """Safely merges and appends new player URLs into the existing sitemap.xml without erasing data."""
    existing_urls = set()
    
    # 1. Read and extract current URLs if the sitemap already exists
    if os.path.exists(SITEMAP_OUTPUT_PATH):
        try:
            # Register the sitemap namespace to avoid ugly 'ns0:' prefixing
            ET.register_namespace('', "http://www.sitemaps.org/schemas/sitemap/0.9")
            
            tree = ET.parse(SITEMAP_OUTPUT_PATH)
            root = tree.getroot()
            
            # Extract all current locations out of the existing XML tags
            for loc in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                if loc.text:
                    existing_urls.add(loc.text.strip())
            print(f"📖 Found existing sitemap. Loaded {len(existing_urls)} current URLs.")
        except Exception as e:
            print(f"⚠️ Error parsing existing sitemap ({e}). Starting fresh to prevent script crash.")

    # 2. Add baseline homepage if it's completely missing from your registry
    home_url = f"{DOMAIN}/"
    existing_urls.add(home_url)

    # 3. Merge new player urls into the master tracking set (Sets naturally prevent duplicates)
    new_additions_count = 0
    for url in new_player_urls:
        if url not in existing_urls:
            existing_urls.add(url)
            new_additions_count += 1

    print(f"➕ Appending {new_additions_count} brand-new player profiles to the master map.")

    # 4. Rebuild the master structured XML document tree cleanly
    xml_root = ET.Element('urlset', xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    
    for url in sorted(list(existing_urls)):
        url_node = ET.SubElement(xml_root, 'url')
        ET.SubElement(url_node, 'loc').text = url
        
        # Set dynamic priority crawl weights based on URL context
        if url == home_url:
            ET.SubElement(url_node, 'changefreq').text = "always"
            ET.SubElement(url_node, 'priority').text = "1.0"
        elif "/lineups/" in url:
            # Explicit rule to preserve your critical team page configurations
            ET.SubElement(url_node, 'changefreq').text = "daily"
            ET.SubElement(url_node, 'priority').text = "0.9"
        elif "/players/" in url:
            ET.SubElement(url_node, 'changefreq').text = "daily"
            ET.SubElement(url_node, 'priority').text = "0.8"
        else:
            # Fallback for generic text articles, privacy policy, contact pages, etc.
            ET.SubElement(url_node, 'changefreq').text = "weekly"
            ET.SubElement(url_node, 'priority').text = "0.6"

    # 5. Output beautiful, human-readable indented code for Google bots
    raw_xml = ET.tostring(xml_root, 'utf-8')
    parsed_xml = minidom.parseString(raw_xml)
    pretty_xml = parsed_xml.toprettyxml(indent="  ")

    # Save cleanly back to the root directory
    with open(SITEMAP_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join([line for line in pretty_xml.splitlines() if line.strip()]))
        
    print(f"✅ Sitemap successfully compiled. Total active URLs: {len(existing_urls)}")

def generate_player_html(player_id, p_name, is_pitcher, slug):
    """Generates a static HTML skeleton optimized specifically for player type."""
    player_url = f"{DOMAIN}/players/{slug}/"
    
    # Contextual SEO Meta switches
    if is_pitcher:
        title = f"Is {p_name} Pitching Today? Lineup Status & Matchup Stats"
        desc = f"Find out if {p_name} is starting today. View real-time lineup validation, pitch split analytics, opponent HR safety factors, and daily fantasy projection scores."
    else:
        title = f"Is {p_name} Playing Today? Lineup Status, BvP & Matchup Stats"
        desc = f"Find out if {p_name} is in today's starting lineup. View real-time lineup status, lifetime matchup analytics, daily HR probability scores, and live box scores."

    html_content = f"""<!DOCTYPE html>
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
    <link rel="icon" href="/favicon.ico" sizes="any">
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">
    
    <title>{title}</title>
    <meta name="description" content="{desc}">
    <link rel="canonical" href="{player_url}" />

    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <style>
        body {{ background-color: #f1f3f5; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        .header-brand {{ font-weight: 900; letter-spacing: -1px; font-size: 2rem; color: #fff; font-style: italic; text-shadow: 0 2px 4px rgba(0,0,0,0.5); }}
        .header-brand a {{ color: inherit; }}
        .header-brand span {{ 
            text-shadow: none !important;
            background: linear-gradient(to bottom, #7CD0FF 0%, #1A8CFF 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            filter: drop-shadow(0 0 12px rgba(26, 140, 255, 0.8));
            padding-right: 2px;
            display: inline-block;
        }}
        .profile-hero-card {{ background: #fff; border: 1px solid #dee2e6; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); overflow: hidden; margin-bottom: 24px; }}
        .profile-hero-bg {{ background: linear-gradient(135deg, #212529 0%, #343a40 100%); position: relative; padding: 24px; }}
        .player-headshot-frame {{ position: relative; width: 120px; height: 120px; }}
        .player-headshot {{ width: 120px; height: 120px; border-radius: 50%; object-fit: cover; background: #fff; border: 3px solid #fff; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }}
        .player-team-badge {{ width: 38px; height: 38px; position: absolute; bottom: -2px; right: -2px; border-radius: 50%; background: #fff; border: 2px solid #dee2e6; object-fit: contain; padding: 2px; }}
        .status-badge-confirmed {{ background-color: #198754; color: #fff; font-size: 0.75rem; font-weight: 700; }}
        .status-badge-projected {{ background-color: #ffecb5; color: #1a1a1a; font-size: 0.75rem; font-weight: 700; }}
        .status-badge-scratched {{ background-color: #dc3545; color: #fff; font-size: 0.75rem; font-weight: 700; }}
        .dk-accent {{ color: #6c9d2f; font-weight: 800; }}
        .fd-accent {{ color: #0d6efd; font-weight: 800; }}
        .log-table-responsive {{ -webkit-scrollbar {{ height: 4px; }} }}
    </style>
</head>
<body>

<nav class="navbar shadow-sm py-3 mb-4" style="background-color: #212529;">
    <div class="container d-flex justify-content-between align-items-center flex-wrap">
        <div class="header-brand mb-0"><a href="/" class="text-decoration-none">MLB Starting <span>Nine</span></a></div>
        <div class="d-flex align-items-center gap-3"><a href="/" class="btn btn-sm btn-outline-light font-weight-bold" style="font-size:0.8rem;">← Back To Slate</a></div>
    </div>
</nav>

<div class="container px-2 px-md-3">
    <div class="row justify-content-center">
        <div class="col-lg-10 col-xl-8">
            
            <div class="profile-hero-card">
                <div class="profile-hero-bg d-flex align-items-center flex-column flex-sm-row text-center text-sm-start gap-4">
                    <div class="player-headshot-frame flex-shrink-0">
                        <img src="https://img.mlbstatic.com/mlb-photos/image/upload/d_people:brooks:default/w_180,q_auto:best/v1/people/{player_id}/headshot/67/current" class="player-headshot" id="player-headshot-img" alt="{p_name}">
                        <img src="https://www.mlbstatic.com/team-logos/team-cap-on-light/blank.svg" class="player-team-badge" id="player-team-logo" alt="Team Badge">
                    </div>
                    <div class="w-100 text-white">
                        <div class="d-flex flex-column flex-sm-row justify-content-sm-between align-items-center align-items-sm-start gap-3">
                            <div>
                                <h1 class="h3 fw-black mb-1 italic text-white" id="player-name-header">{p_name}</h1>
                                <p class="text-muted mb-0" style="color: #adb5bd !important; font-size: 0.9rem; font-weight: 600;" id="player-meta-sub">Synchronizing Player Data...</p>
                            </div>
                            <div class="d-flex flex-column gap-2 flex-shrink-0" style="min-width: 180px;" id="badge-matrix-zone"></div>
                        </div>
                        <div class="border-top border-secondary mt-3 pt-2 text-muted" style="color: #dee2e6 !important; font-size: 0.8rem;">
                            <span id="live-game-state-label"><strong>Game Status:</strong> Syncing Today's Slate Profiles...</span>
                        </div>
                    </div>
                </div>

                <div id="live-consoles-container"></div>

                <div class="card-body p-3">
                    <h5 class="fw-bold mb-3 text-dark border-bottom pb-2" style="font-size: 1rem; letter-spacing: -0.2px;">📈 Split Analytics & Matchup Matrix</h5>
                    
                    <div id="hr-predictor-container" class="mb-3"></div>
                    <div id="bvp-cards-container" class="mb-3"></div>

                    <div class="row g-2">
                        <div class="col-md-6">
                            <div class="border rounded p-2 bg-light">
                                <div class="fw-bold text-dark border-bottom pb-1 mb-2" id="split-vl-header">Splits VS Left-Handed</div>
                                <div class="d-flex justify-content-between small text-muted px-1 py-1"><span id="split-vl-label-volume">Volume:</span><strong class="text-dark" id="split-vl-vol">--</strong></div>
                                <div class="d-flex justify-content-between small text-muted px-1 py-1"><span>Batting Avg:</span><strong class="text-dark" id="split-vl-avg">--</strong></div>
                                <div class="d-flex justify-content-between small text-muted px-1 py-1"><span>OPS:</span><strong class="text-dark" id="split-vl-ops">--</strong></div>
                                <div class="d-flex justify-content-between small text-muted px-1 py-1"><span id="split-vl-label-hr">Power Stat:</span><strong class="text-dark" id="split-vl-hr">--</strong></div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="border rounded p-2 bg-light">
                                <div class="fw-bold text-dark border-bottom pb-1 mb-2" id="split-vr-header">Splits VS Right-Handed</div>
                                <div class="d-flex justify-content-between small text-muted px-1 py-1"><span id="split-vr-label-volume">Volume:</span><strong class="text-dark" id="split-vr-vol">--</strong></div>
                                <div class="d-flex justify-content-between small text-muted px-1 py-1"><span>Batting Avg:</span><strong class="text-dark" id="split-vr-avg">--</strong></div>
                                <div class="d-flex justify-content-between small text-muted px-1 py-1"><span>OPS:</span><strong class="text-dark" id="split-vr-ops">--</strong></div>
                                <div class="d-flex justify-content-between small text-muted px-1 py-1"><span id="split-vr-label-hr">Power Stat:</span><strong class="text-dark" id="split-vr-hr">--</strong></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card shadow-sm border rounded bg-white overflow-hidden mb-4" style="border-color: #dee2e6 !important;">
                <div class="card-header bg-dark text-white py-2"><h6 class="mb-0 fw-bold" style="font-size: 0.85rem;">📋 Rolling Performance Log (Last 10 Games)</h6></div>
                <div class="table-responsive log-table-responsive">
                    <table class="table table-striped text-center align-middle mb-0" style="font-size:0.8rem; min-width: 500px;">
                        <thead class="table-light fw-bold text-secondary">
                            <tr><th class="text-start ps-3">Date</th><th>Game Line Performance</th><th>DraftKings Pts</th><th>FanDuel Pts</th></tr>
                        </thead>
                        <tbody id="game-historical-tbody"></tbody>
                    </table>
                </div>
            </div>

        </div>
    </div>
</div>

<script>var PLAYER_ID = "{player_id}";</script>
<script src="/scripts/player_core.js"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""
    return html_content

def main():
    if not os.path.exists(MASTER_DATA_PATH):
        print(f"❌ Error: Could not locate master log registry file at {MASTER_DATA_PATH}")
        return

    with open(MASTER_DATA_PATH, "r", encoding="utf-8") as f:
        master_data = json.load(f)

    all_player_urls = []
    created_count = 0
    skipped_count = 0

    print(f"📦 Commencing deployment processing loop for {len(master_data)} baseline player records...")

    for key, profile in master_data.items():
        raw_player_id = key.replace("ID", "")
        player_name = profile.get("name", "Unknown Player")
        is_pitcher = profile.get("is_pitcher", False)

        player_slug = slugify(player_name)
        player_dir = os.path.join(OUTPUT_PLAYERS_DIR, player_slug)
        index_file_path = os.path.join(player_dir, "index.html")
        
        all_player_urls.append(f"{DOMAIN}/players/{player_slug}/")

        if os.path.exists(index_file_path):
            skipped_count += 1
            continue

        os.makedirs(player_dir, exist_ok=True)

        html_code = generate_player_html(raw_player_id, player_name, is_pitcher, player_slug)
        with open(index_file_path, "w", encoding="utf-8") as html_out:
            html_out.write(html_code)
        
        created_count += 1

    print(f"⚡ Loop Complete. Created: {created_count} profiles | Skipped: {skipped_count} existing profiles.")

    # Execute safe sitemap merger process
    update_sitemap(all_player_urls)

if __name__ == "__main__":
    main()
