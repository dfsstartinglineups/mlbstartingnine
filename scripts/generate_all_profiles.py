import os
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Path Configurations
MASTER_DATA_PATH = "data/player_master_data.json"
OUTPUT_PLAYERS_DIR = "players"
SITEMAP_OUTPUT_PATH = "sitemap.xml"
DOMAIN = "https://mlbstartingnine.com"

# ==========================================
# 1. CORE UTILITIES & SLUGIFICATION
# ==========================================
def slugify(text):
    text = text.lower()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s-]+", "-", text).strip("-")

def get_target_slate_date():
    now = datetime.now(ZoneInfo("America/New_York"))
    if now.hour < 3:
        now = now - timedelta(days=1)
    return now.strftime("%Y-%m-%d")

def get_slug_from_team_id(team_id):
    slug_map = {
        108: "los-angeles-angels", 109: "arizona-diamondbacks", 110: "baltimore-orioles", 111: "boston-red-sox",
        112: "chicago-cubs", 113: "cincinnati-reds", 114: "cleveland-guardians", 115: "colorado-rockies",
        116: "detroit-tigers", 117: "houston-astros", 118: "kansas-city-royals", 119: "los-angeles-dodgers",
        120: "washington-nationals", 121: "new-york-mets", 133: "athletics", 134: "pittsburgh-pirates",
        135: "san-diego-padres", 136: "seattle-mariners", 137: "san-francisco-giants", 138: "st-louis-cardinals",
        139: "tampa-bay-rays", 140: "texas-rangers", 141: "toronto-blue-jays", 142: "minnesota-twins",
        143: "philadelphia-phillies", 144: "atlanta-braves", 145: "chicago-white-sox", 146: "miami-marlins",
        147: "new-york-yankees", 158: "milwaukee-brewers"
    }
    return slug_map.get(int(team_id), "los-angeles-dodgers")

def load_json_safe(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def update_sitemap(new_player_urls):
    existing_urls = set()
    if os.path.exists(SITEMAP_OUTPUT_PATH):
        try:
            ET.register_namespace('', "http://www.sitemaps.org/schemas/sitemap/0.9")
            tree = ET.parse(SITEMAP_OUTPUT_PATH)
            root = tree.getroot()
            for loc in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                if loc.text: existing_urls.add(loc.text.strip())
        except Exception:
            pass

    home_url = f"{DOMAIN}/"
    existing_urls.add(home_url)
    for url in new_player_urls:
        existing_urls.add(url)

    xml_root = ET.Element('urlset', xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for url in sorted(list(existing_urls)):
        url_node = ET.SubElement(xml_root, 'url')
        ET.SubElement(url_node, 'loc').text = url
        if url == home_url:
            ET.SubElement(url_node, 'changefreq').text = "always"
            ET.SubElement(url_node, 'priority').text = "1.0"
        elif "/lineups/" in url:
            ET.SubElement(url_node, 'changefreq').text = "daily"
            ET.SubElement(url_node, 'priority').text = "0.9"
        elif "/players/" in url:
            ET.SubElement(url_node, 'changefreq').text = "daily"
            ET.SubElement(url_node, 'priority').text = "0.8"
        else:
            ET.SubElement(url_node, 'changefreq').text = "weekly"
            ET.SubElement(url_node, 'priority').text = "0.6"

    raw_xml = ET.tostring(xml_root, 'utf-8')
    parsed_xml = minidom.parseString(raw_xml)
    pretty_xml = parsed_xml.toprettyxml(indent="  ")
    with open(SITEMAP_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join([line for line in pretty_xml.splitlines() if line.strip()]))

# ==========================================
# 2. MATCHUP ENGINE
# ==========================================
def resolve_active_matchup(player_id, team_name, daily_data):
    matching_games = []
    p_id_str = str(player_id)
    
    for game in daily_data.get("games", []):
        game_raw = game.get("gameRaw", {})
        teams = game_raw.get("teams", {})
        home_team_name = teams.get("home", {}).get("team", {}).get("name", "")
        away_team_name = teams.get("away", {}).get("team", {}).get("name", "")
        
        home_p = str(teams.get("home", {}).get("probablePitcher", {}).get("id", "") or game.get("projectedLineups", {}).get("home", {}).get("startingPitcher", {}).get("id", ""))
        away_p = str(teams.get("away", {}).get("probablePitcher", {}).get("id", "") or game.get("projectedLineups", {}).get("away", {}).get("startingPitcher", {}).get("id", ""))
        
        in_home = (p_id_str in [str(p.get("id")) for p in game_raw.get("lineups", {}).get("homePlayers", [])] or 
                   p_id_str in [str(p.get("id")) for p in game.get("projectedLineups", {}).get("home", {}).get("battingOrder", [])] or 
                   home_p == p_id_str or (home_team_name and home_team_name in team_name))
                   
        in_away = (p_id_str in [str(p.get("id")) for p in game_raw.get("lineups", {}).get("awayPlayers", [])] or 
                   p_id_str in [str(p.get("id")) for p in game.get("projectedLineups", {}).get("away", {}).get("battingOrder", [])] or 
                   away_p == p_id_str or (away_team_name and away_team_name in team_name))
                   
        if in_home: matching_games.append({"game": game, "teamSide": "home"})
        if in_away: matching_games.append({"game": game, "teamSide": "away"})
            
    if not matching_games: return None, None
        
    if len(matching_games) > 1:
        live_match = next((m for m in matching_games if m["game"].get("gameRaw", {}).get("status", {}).get("abstractGameState") in ["Live", "In Progress"]), None)
        upcoming_match = next((m for m in matching_games if m["game"].get("gameRaw", {}).get("status", {}).get("abstractGameState") in ["Preview", "Scheduled"]), None)
        if live_match: return live_match["game"], live_match["teamSide"]
        elif upcoming_match: return upcoming_match["game"], upcoming_match["teamSide"]
        else: return matching_games[-1]["game"], matching_games[-1]["teamSide"]
            
    return matching_games[0]["game"], matching_games[0]["teamSide"]

# ==========================================
# 3. HTML SUB-RENDERERS
# ==========================================
def render_badge_zone(player_id, team_side, my_game):
    game_raw = my_game.get("gameRaw", {})
    my_team_id = game_raw.get("teams", {}).get(team_side, {}).get("team", {}).get("id", 119)
    tracking_node = my_game.get("lineupTracking", {}).get(team_side, {})
    
    abstract_state = game_raw.get("status", {}).get("abstractGameState", "")
    detailed_state = game_raw.get("status", {}).get("detailedState", "")
    is_postponed = "Postponed" in abstract_state or "Postponed" in detailed_state or game_raw.get("status", {}).get("statusCode") == "C"
    
    if is_postponed:
        return '<div class="badge bg-danger p-2 w-100 shadow-sm text-uppercase fw-bold text-white">✕ GAME POSTPONED</div>'
        
    is_starting_pitcher = (str(game_raw.get("teams", {}).get(team_side, {}).get("probablePitcher", {}).get("id", "")) == str(player_id) or 
                           str(my_game.get("projectedLineups", {}).get(team_side, {}).get("startingPitcher", {}).get("id", "")) == str(player_id))
                           
    if is_starting_pitcher:
        badge_html = '<div class="badge status-badge-confirmed p-2 w-100 shadow-sm text-uppercase">IN LINEUP: Starting Pitcher</div>'
    else:
        actual_lineup = game_raw.get("lineups", {}).get(f"{team_side}Players", [])
        has_live_lineup = len(actual_lineup) > 0
        is_confirmed = tracking_node.get("status") in ["OFFICIAL", "UPDATED", "MODIFIED", "CONFIRMED"] or has_live_lineup
        
        slot_index = -1
        if has_live_lineup:
            slot_index = next((i for i, p in enumerate(actual_lineup) if str(p.get("id")) == str(player_id)), -1)
        if slot_index == -1 and tracking_node.get("hash"):
            slot_index = tracking_node.get("hash").split('-').index(str(player_id)) if str(player_id) in tracking_node.get("hash").split('-') else -1
        if slot_index == -1:
            proj_order = my_game.get("projectedLineups", {}).get(team_side, {}).get("battingOrder", [])
            slot_index = next((i for i, p in enumerate(proj_order) if str(p.get("id")) == str(player_id)), -1)
            
        if is_confirmed and slot_index != -1:
            badge_html = f'<div class="badge status-badge-confirmed p-2 w-100 shadow-sm text-uppercase">IN LINEUP: Batting #{slot_index + 1}</div>'
        elif is_confirmed and slot_index == -1:
            badge_html = '<div class="badge status-badge-scratched p-2 w-100 shadow-sm text-uppercase">✕ NOT STARTING</div>'
        elif slot_index != -1:
            badge_html = f'<div class="badge status-badge-projected p-2 w-100 shadow-sm text-uppercase text-dark">Projected #{slot_index + 1}</div>'
        else:
            badge_html = '<div class="badge status-badge-scratched p-2 w-100 shadow-sm text-uppercase">✕ NOT PROJECTED TO START</div>'
            
    team_slug = get_slug_from_team_id(my_team_id)
    lineup_link_text = "View Official Lineup" if (tracking_node.get("status") in ["OFFICIAL", "CONFIRMED"]) else "View Projected Lineup"
    link_html = f'<a href="https://mlbstartingnine.com/lineups/{team_slug}/" class="btn btn-sm btn-outline-primary w-100 mt-2 fw-bold text-uppercase shadow-sm" style="font-size: 0.7rem; letter-spacing: 0.5px;">📊 {lineup_link_text}</a>'
    
    return f'<div class="mb-3">{badge_html}{link_html}</div>'

def render_live_console(player_id, team_side, my_game, live_data, dk_val, fd_val):
    game_raw = my_game.get("gameRaw", {})
    game_pk = str(game_raw.get("gamePk", ""))
    opp_side = "home" if team_side == "away" else "away"
    opp_pitcher_name = game_raw.get("teams", {}).get(opp_side, {}).get("probablePitcher", {}).get("fullName", "TBD")
    
    abstract_state = game_raw.get("status", {}).get("abstractGameState", "")
    detailed_state = game_raw.get("status", {}).get("detailedState", "")
    if "Postponed" in abstract_state or "Postponed" in detailed_state or game_raw.get("status", {}).get("statusCode") == "C":
        return ('<span class="text-danger fw-bold">Postponed</span>', 
                '<div class="p-3 border-bottom text-center" style="background-color: #fdf2f2;"><span class="badge bg-danger text-uppercase mb-1" style="font-size:0.6rem;">PPD</span><span class="text-dark d-block fw-semibold" style="font-size: 0.85rem;">This matchup has been called off.</span></div>')

    active_live = live_data.get(game_pk)
    if active_live:
        # THE FIX: Calculate the clean inning number BEFORE inserting it into the f-string
        inning_raw = active_live.get('inning', '')
        inning_clean = re.sub(r'\D', '', inning_raw)
        game_state_lbl = f"{active_live.get('status', 'Live')} {active_live.get('half', '')} {inning_clean}".strip()
        
        side_upper = team_side.upper()
        player_box = active_live.get("players", {}).get(side_upper, {}).get(f"ID{player_id}", {})
        profile = player_box.get("batting", {}) or player_box.get("pitching", {})
        
        summary = profile.get("summary", "")
        dk_pts = player_box.get("dk_pts", 0.0)
        fd_pts = player_box.get("fd_pts", 0.0)
        
        console_html = f"""
        <div class="p-3 border-bottom" style="background-color: #edf4f8;">
            <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
                <div>
                    <span class="badge bg-primary text-uppercase me-2" style="font-size:0.65rem;">Box Score</span>
                    <strong class="text-dark" style="font-size: 0.9rem;">{summary if summary else "Active in Game"}</strong>
                </div>
                <div class="d-flex align-items-center gap-2">
                    <div class="bg-white border rounded px-3 py-1 shadow-sm text-center">
                        <span class="text-muted d-block" style="font-size: 0.55rem; font-weight:700; text-transform:uppercase;">DraftKings</span>
                        <div class="d-flex align-items-baseline gap-1">
                            <span class="dk-accent" style="font-size: 1.1rem;">{dk_pts:.1f}</span>
                            <span class="text-muted" style="font-size:0.75rem;">/</span>
                            <span class="text-secondary fw-bold" style="font-size:0.85rem;">{dk_val}</span>
                        </div>
                    </div>
                    <div class="bg-white border rounded px-3 py-1 shadow-sm text-center">
                        <span class="text-muted d-block" style="font-size: 0.55rem; font-weight:700; text-transform:uppercase;">FanDuel</span>
                        <div class="d-flex align-items-baseline gap-1">
                            <span class="fd-accent" style="font-size: 1.1rem;">{fd_pts:.1f}</span>
                            <span class="text-muted" style="font-size:0.75rem;">/</span>
                            <span class="text-secondary fw-bold" style="font-size:0.85rem;">{fd_val}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>"""
        return game_state_lbl, console_html
    else:
        game_state_lbl = game_raw.get("status", {}).get("abstractGameState", "Scheduled")
        console_html = f"""
        <div class="p-3 border-bottom" style="background-color: #edf4f8;">
            <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
                <div>
                    <span class="badge bg-secondary text-uppercase me-2" style="font-size:0.65rem;">Upcoming Matchup</span>
                    <span class="text-dark fw-semibold" style="font-size: 0.85rem;">vs. {opp_pitcher_name}</span>
                </div>
                <div class="d-flex align-items-center gap-2">
                    <div class="bg-white border rounded px-3 py-1 shadow-sm text-center">
                        <span class="text-muted d-block" style="font-size: 0.55rem; font-weight:700; text-transform:uppercase;">DK Proj</span>
                        <span class="text-dark fw-bold" style="font-size: 1rem;">{dk_val}</span>
                    </div>
                    <div class="bg-white border rounded px-3 py-1 shadow-sm text-center">
                        <span class="text-muted d-block" style="font-size: 0.55rem; font-weight:700; text-transform:uppercase;">FD Proj</span>
                        <span class="text-dark fw-bold" style="font-size: 1rem;">{fd_val}</span>
                    </div>
                </div>
            </div>
        </div>"""
        return game_state_lbl, console_html

def render_advanced_matrices(player_id, team_side, my_game, p_deep_stats, is_pitcher):
    game_raw = my_game.get("gameRaw", {})
    opp_side = "home" if team_side == "away" else "away"
    opp_pitcher_name = game_raw.get("teams", {}).get(opp_side, {}).get("probablePitcher", {}).get("fullName", "TBD")
    opp_pitcher_id = str(game_raw.get("teams", {}).get(opp_side, {}).get("probablePitcher", {}).get("id", ""))
    is_away = (team_side == 'away')
    
    hr_html = ""
    bvp_html = ""
    
    if not is_pitcher:
        split_r = p_deep_stats.get("split_vR", {})
        split_l = p_deep_stats.get("split_vL", {})
        opp_hand = my_game.get("lineupHandedness", {}).get(opp_pitcher_id, "R")
        
        if opp_hand == 'R':
            hit_hr_rate = float(split_r.get("hr", 0)) / float(split_r.get("ab", 1)) if float(split_r.get("ab", 0)) > 0 else 0
        elif opp_hand == 'L':
            hit_hr_rate = float(split_l.get("hr", 0)) / float(split_l.get("ab", 1)) if float(split_l.get("ab", 0)) > 0 else 0
        else:
            t_hr = float(split_r.get("hr", 0)) + float(split_l.get("hr", 0))
            t_ab = float(split_r.get("ab", 0)) + float(split_l.get("ab", 0))
            hit_hr_rate = t_hr / t_ab if t_ab > 0 else 0
            
        base_score = (max(hit_hr_rate, 0.01) / 0.03) * 10.0
        if my_game.get("parkStats"):
            factor = my_game["parkStats"].get("hr_l" if is_away else "hr_r", 100)
            base_score *= (float(factor) / 100.0)
            
        rating = "AVERAGE"
        bar_color = "bg-primary"
        progress_pct = (base_score / 10.0) * 33.33 if base_score <= 10.0 else (33.33 + ((base_score - 10.0) / 5.0) * 33.33 if base_score <= 15.0 else 66.66 + ((base_score - 15.0) / 10.0) * 33.33)
        progress_pct = min(max(progress_pct, 10), 100)
        
        if base_score >= 25.0: rating, bar_color = "ELITE", "bg-danger text-white"
        elif base_score >= 15.0: rating, bar_color = "GOOD", "bg-success text-white"
        elif base_score < 5.0: rating, bar_color = "LOW", "bg-secondary text-white"
        
        hr_html = f"""
        <div class="border rounded p-3 bg-white shadow-sm mb-2">
            <div class="d-flex justify-content-between align-items-center border-bottom pb-2 mb-2">
                <div class="d-flex align-items-center gap-2">
                    <span class="fw-bold text-dark" style="font-size: 0.85rem;">🚀 Home Run Power Predictor</span>
                    <span class="badge {bar_color} fw-bold" style="font-size: 0.65rem;">{rating}</span>
                </div>
                <span class="badge bg-dark fw-bold shadow-sm" style="font-size:0.8rem; padding: 4px 8px;">HR Score: {base_score:.1f}</span>
            </div>
            <div class="w-100">
                <div class="progress rounded-pill" style="height: 12px; background-color: #e9ecef;">
                    <div class="progress-bar progress-bar-striped progress-bar-animated {bar_color}" role="progressbar" style="width: {progress_pct}%;"></div>
                </div>
                <div class="d-flex justify-content-between text-muted px-1 mt-1 font-monospace" style="font-size: 0.6rem;">
                    <span>Low (&lt; 5.0)</span><span>Average (10.0)</span><span>Good (15.0+)</span><span>Elite (25.0+)</span>
                </div>
            </div>
        </div>"""
        
        bvp = p_deep_stats.get("bvp", {})
        if bvp and float(bvp.get("ab", 0)) > 0:
            bvp_html = f"""
            <div class="border rounded p-3 bg-white shadow-sm mb-2">
                <div class="fw-bold text-dark border-bottom pb-2 mb-2 d-flex justify-content-between align-items-center" style="font-size: 0.85rem;">
                    <span>⚔️ Lifetime Matchup Analysis</span>
                    <span class="badge bg-primary">vs. {opp_pitcher_name}</span>
                </div>
                <div class="row text-center g-2 pt-1">
                    <div class="col-3 border-end"><span class="text-muted d-block" style="font-size: 0.6rem; font-weight:700;">AT BATS</span><strong class="text-dark">{bvp['ab']}</strong></div>
                    <div class="col-3 border-end"><span class="text-muted d-block" style="font-size: 0.6rem; font-weight:700;">HITS</span><strong class="text-dark">{bvp['hits']}</strong></div>
                    <div class="col-3 border-end"><span class="text-muted d-block" style="font-size: 0.6rem; font-weight:700;">HOME RUNS</span><strong class="text-dark">{bvp['hr']}</strong></div>
                    <div class="col-3"><span class="text-muted d-block" style="font-size: 0.6rem; font-weight:700;">OPS</span><strong class="text-success">{bvp['ops']}</strong></div>
                </div>
            </div>"""
        else:
            bvp_html = f"""<div class="border rounded p-2 text-center text-muted fst-italic bg-white shadow-sm mb-2" style="font-size: 0.8rem;">🚫 Potential Matchup: No previous history recorded against starting pitcher <strong>{opp_pitcher_name}</strong>.</div>"""
            
    else:
        split_r = p_deep_stats.get("split_vR", {})
        split_l = p_deep_stats.get("split_vL", {})
        t_hr = float(split_l.get("hr", 0)) + float(split_r.get("hr", 0))
        t_ab = float(split_l.get("ab", 0)) + float(split_r.get("ab", 0))
        pitch_hr_rate = t_hr / t_ab if t_ab > 0 else 0
        
        base_danger = (max(pitch_hr_rate, 0.01) / 0.03) * 10.0
        if my_game.get("parkStats"):
            factor = (float(my_game["parkStats"].get("hr_l", 100)) + float(my_game["parkStats"].get("hr_r", 100))) / 2.0
            base_danger *= (factor / 100.0)
            
        rating = "AVERAGE"
        bar_color = "bg-warning text-dark"
        progress_pct = (base_danger / 10.0) * 33.33 if base_danger <= 10.0 else (33.33 + ((base_danger - 10.0) / 8.0) * 33.33 if base_danger <= 18.0 else 66.66 + ((base_danger - 18.0) / 7.0) * 33.33)
        progress_pct = min(max(progress_pct, 10), 100)
        
        if base_danger >= 18.0: rating, bar_color = "DANGEROUS", "bg-danger text-white"
        elif base_danger < 10.0: rating, bar_color = "SAFE", "bg-success text-white"
        
        hr_html = f"""
        <div class="border rounded p-3 bg-white shadow-sm mb-2">
            <div class="d-flex justify-content-between align-items-center border-bottom pb-2 mb-2">
                <div class="d-flex align-items-center gap-2">
                    <span class="fw-bold text-dark" style="font-size: 0.85rem;">🛡️ HR Suppression Gauge</span>
                    <span class="badge {bar_color} fw-bold" style="font-size: 0.65rem;">{rating}</span>
                </div>
                <span class="badge bg-dark fw-bold shadow-sm" style="font-size:0.8rem; padding: 4px 8px;">Danger Score: {base_danger:.1f}</span>
            </div>
            <div class="w-100">
                <div class="progress rounded-pill" style="height: 12px; background-color: #e9ecef;">
                    <div class="progress-bar progress-bar-striped progress-bar-animated {bar_color}" role="progressbar" style="width: {progress_pct}%;"></div>
                </div>
                <div class="d-flex justify-content-between text-muted px-1 mt-1 font-monospace" style="font-size: 0.6rem;">
                    <span>Safe (&lt; 10.0)</span><span>Average</span><span>Dangerous (18.0+)</span>
                </div>
            </div>
        </div>"""
        
        order_list = my_game.get("lineupTracking", {}).get(opp_side, {}).get("hash", "").split('-') if my_game.get("lineupTracking", {}).get(opp_side, {}).get("hash") else []
        if not order_list:
            order_list = [str(p.get("id")) for p in my_game.get("projectedLineups", {}).get(opp_side, {}).get("battingOrder", [])]
            
        rows_html = ""
        hist_count = 0
        for idx, b_id in enumerate(order_list):
            if not b_id: continue
            b_stats = my_game.get("deepStats", {}).get(b_id, {})
            bvp = b_stats.get("bvp", {})
            b_name = b_stats.get("name") or next((p.get("name") for p in my_game.get("projectedLineups", {}).get(opp_side, {}).get("battingOrder", []) if str(p.get("id")) == str(b_id)), f"Batter #{idx+1}")
            
            if bvp and float(bvp.get("ab", 0)) > 0:
                hist_count += 1
                rows_html += f"<tr><td class='text-start fw-semibold'>{idx + 1}. {b_name}</td><td><strong>{bvp['ab']}</strong></td><td>{bvp['hits']}</td><td>{bvp['hr']}</td><td class='text-success fw-bold'>{bvp['ops']}</td></tr>"
            else:
                rows_html += f"<tr><td class='text-start text-muted'>{idx + 1}. {b_name}</td><td colspan='4' class='text-muted fst-italic text-center' style='font-size: 0.7rem;'>No historic matchups recorded</td></tr>"
                
        opp_team_name = game_raw.get("teams", {}).get(opp_side, {}).get("teamName", "Opponent")
        bvp_html = f"""
        <div class="card shadow-sm border rounded overflow-hidden mb-2">
            <div class="card-header bg-primary text-white py-2 d-flex justify-content-between align-items-center">
                <h6 class="mb-0 fw-bold" style="font-size: 0.8rem;">⚔️ Head-to-Head vs Opposing {opp_team_name} Lineup</h6>
                <span class="badge bg-light text-primary fw-bold" style="font-size:0.65rem;">{hist_count} Bats Tracked</span>
            </div>
            <div class="table-responsive">
                <table class="table table-striped text-center align-middle mb-0" style="font-size:0.75rem; min-width: 450px;">
                    <thead class="table-light text-secondary font-weight-bold">
                        <tr><th class="text-start ps-2">Lineup Position & Batter</th><th>AB</th><th>H</th><th>HR</th><th>Lifetime OPS</th></tr>
                    </thead>
                    <tbody>{rows_html}</tbody>
                </table>
            </div>
        </div>"""
        
    return hr_html, bvp_html

# ==========================================
# 4. PRIMARY HTML LAYOUT BUILDER
# ==========================================
def generate_player_html(profile, slug, daily_data, live_data):
    player_id = profile.get("player_id", "")
    team_id = profile.get("team_id", "")
    team_logo_url = f"https://www.mlbstatic.com/team-logos/team-cap-on-light/{team_id}.svg" if team_id else "https://www.mlbstatic.com/team-logos/team-cap-on-light/blank.svg"
    p_name = profile.get("name", "Unknown Player")
    is_pitcher = profile.get("is_pitcher", False)
    team_name = profile.get("team_name", "Free Agent")
    position = profile.get("position", "Unknown Position")
    
    my_game, team_side = resolve_active_matchup(player_id, team_name, daily_data)
    
    dk_proj_val, fd_proj_val = 'NA', 'NA'
    badge_matrix_html = '<div class="badge status-badge-scratched p-2 w-100 shadow-sm text-uppercase">✕ NO GAME SCHEDULED</div>'
    game_state_lbl = '<strong>Game Status:</strong> Not on Today\'s Active Slate'
    live_console_html = '<div class="p-3 border-bottom" style="background-color: #edf4f8;"><span class="badge bg-secondary text-uppercase me-2" style="font-size:0.65rem;">Off Slate</span><span class="text-dark fw-semibold" style="font-size: 0.85rem;">No schedules match this player today.</span></div>'
    hr_predictor_html = ""
    bvp_cards_html = '<div class="border rounded p-3 text-center text-muted fst-italic bg-white shadow-sm" style="font-size: 0.8rem;">🚫 No active matchup setup for today\'s slate.</div>'
    
    if my_game and team_side:
        p_deep_stats = my_game.get("deepStats", {}).get(str(player_id), {})
        p_proj_node = None
        if my_game.get("projectedLineups", {}).get(team_side):
            pl = my_game["projectedLineups"][team_side]
            if str(pl.get("startingPitcher", {}).get("id")) == str(player_id):
                p_proj_node = pl.get("startingPitcher")
            else:
                p_proj_node = next((p for p in pl.get("battingOrder", []) if str(p.get("id")) == str(player_id)), None)
                
        dk_raw = p_proj_node.get("dk_slates", {}).get(list(p_proj_node.get("dk_slates", {}).keys())[0], {}).get("proj") if (p_proj_node and p_proj_node.get("dk_slates")) else (p_proj_node.get("dk_proj") if p_proj_node else None)
        fd_raw = p_proj_node.get("fd_slates", {}).get(list(p_proj_node.get("fd_slates", {}).keys())[0], {}).get("proj") if (p_proj_node and p_proj_node.get("fd_slates")) else (p_proj_node.get("proj") if p_proj_node else None)
        
        dk_raw = dk_raw if dk_raw is not None else (p_deep_stats.get("dk_proj") or p_deep_stats.get("dk_points"))
        fd_raw = fd_raw if fd_raw is not None else (p_deep_stats.get("fd_proj") or p_deep_stats.get("fd_points") or p_deep_stats.get("proj"))
        
        dk_proj_val = f"{float(dk_raw):.1f}" if dk_raw is not None else 'NA'
        fd_proj_val = f"{float(fd_raw):.1f}" if fd_raw is not None else 'NA'
        
        badge_matrix_html = render_badge_zone(player_id, team_side, my_game)
        game_state_lbl, live_console_html = render_live_console(player_id, team_side, my_game, live_data, dk_proj_val, fd_proj_val)
        hr_predictor_html, bvp_cards_html = render_advanced_matrices(player_id, team_side, my_game, p_deep_stats, is_pitcher)

    if is_pitcher:
        title = f"Is {p_name} Pitching Today? Lineup Status & Matchup Stats"
        desc = f"Find out if {p_name} is starting today. View real-time lineup validation, pitch split analytics, opponent HR safety factors, and daily fantasy projection scores."
        wins, losses, era = profile.get("season", {}).get("w", 0), profile.get("season", {}).get("l", 0), profile.get("season", {}).get("era", "-")
        season_string = f"{position} • {team_name} • {wins}-{losses} • {era} ERA"
        split_vl_header = '<span class="badge bg-secondary me-1">LHB</span> vs. Left-Handed Batters'
        split_vr_header = '<span class="badge bg-dark me-1">RHB</span> vs. Right-Handed Batters'
        split_vol_label, split_hr_label = "Batters Faced:", "HR Allowed:"
    else:
        title = f"Is {p_name} Playing Today? Lineup Status, BvP & Matchup Stats"
        desc = f"Find out if {p_name} is in today's starting lineup. View real-time lineup status, lifetime matchup analytics, daily HR probability scores, and live box scores."
        avg, hr = profile.get("season", {}).get("avg", "-"), profile.get("season", {}).get("hr", 0)
        season_string = f"{position} • {team_name} • {avg} AVG • {hr} HR"
        split_vl_header, split_vr_header = 'Splits VS Left-Handed', 'Splits VS Right-Handed'
        split_vol_label, split_hr_label = "ABs:", "Homeruns:"

    vl, vr = profile.get("split_vL", {}), profile.get("split_vR", {})
    historical_table_rows = "".join([f"<tr><td class='text-start ps-3 fw-bold'>{log.get('date','')}</td><td>{log.get('summary','')}</td><td class='dk-accent'>{log.get('dk_pts',0.0):.2f}</td><td class='fd-accent'>{log.get('fd_pts',0.0):.1f}</td></tr>" for log in profile.get("game_log", [])])
    if not historical_table_rows:
        historical_table_rows = '<tr><td colspan="4" class="text-center p-3 text-muted">No recent history logged.</td></tr>'

    player_url = f"{DOMAIN}/players/{slug}/"

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
    <title>{title}</title>
    <meta name="description" content="{desc}">
    <link rel="canonical" href="{player_url}" />
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ background-color: #f1f3f5; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        .header-brand {{ font-weight: 900; letter-spacing: -1px; font-size: 2rem; color: #fff; font-style: italic; text-shadow: 0 2px 4px rgba(0,0,0,0.5); }}
        .header-brand a {{ color: inherit; text-decoration: none; }}
        .header-brand span {{ background: linear-gradient(to bottom, #7CD0FF 0%, #1A8CFF 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; padding-right: 2px; display: inline-block; }}
        .profile-hero-card {{ background: #fff; border: 1px solid #dee2e6; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); overflow: hidden; margin-bottom: 24px; }}
        .profile-hero-bg {{ background: linear-gradient(135deg, #212529 0%, #343a40 100%); padding: 24px; }}
        .player-headshot-frame {{ position: relative; width: 120px; height: 120px; }}
        .player-headshot {{ width: 120px; height: 120px; border-radius: 50%; object-fit: cover; background: #fff; border: 3px solid #fff; }}
        .player-team-badge {{ width: 38px; height: 38px; position: absolute; bottom: -2px; right: -2px; border-radius: 50%; background: #fff; border: 2px solid #dee2e6; object-fit: contain; padding: 2px; }}
        .status-badge-confirmed {{ background-color: #198754; color: #fff; font-size: 0.75rem; font-weight: 700; }}
        .status-badge-projected {{ background-color: #ffecb5; color: #1a1a1a; font-size: 0.75rem; font-weight: 700; }}
        .status-badge-scratched {{ background-color: #dc3545; color: #fff; font-size: 0.75rem; font-weight: 700; }}
        .dk-accent {{ color: #6c9d2f; font-weight: 800; }}
        .fd-accent {{ color: #0d6efd; font-weight: 800; }}
    </style>
</head>
<body>
<nav class="navbar shadow-sm py-3 mb-4" style="background-color: #212529;">
    <div class="container d-flex justify-content-between align-items-center flex-wrap">
        <div class="header-brand mb-0"><a href="/">MLB Starting <span>Nine</span></a></div>
        <div><a href="/" class="btn btn-sm btn-outline-light font-weight-bold">← Back To Slate</a></div>
    </div>
</nav>

<div class="container px-2 px-md-3">
    <div class="row justify-content-center">
        <div class="col-lg-10 col-xl-8">
            <div class="profile-hero-card">
                <div class="profile-hero-bg d-flex align-items-center flex-column flex-sm-row text-center text-sm-start gap-4">
                    <div class="player-headshot-frame flex-shrink-0">
                        <img src="https://img.mlbstatic.com/mlb-photos/image/upload/d_people:brooks:default/w_180,q_auto:best/v1/people/{player_id}/headshot/67/current" class="player-headshot" alt="{p_name}">
                        <img src="{team_logo_url}" class="player-team-badge" alt="Team Badge">
                    </div>
                    <div class="w-100 text-white">
                        <div class="d-flex flex-column flex-sm-row justify-content-sm-between align-items-center align-items-sm-start gap-3">
                            <div>
                                <h1 class="h3 fw-black mb-1 italic text-white">{p_name}</h1>
                                <p class="text-muted mb-0" style="color: #adb5bd !important; font-size: 0.9rem; font-weight: 600;" id="player-meta-sub">{season_string}</p>
                            </div>
                            <div class="d-flex flex-column gap-2 flex-shrink-0" style="min-width: 180px;">{badge_matrix_html}</div>
                        </div>
                        <div class="border-top border-secondary mt-3 pt-2 text-muted" style="color: #dee2e6 !important; font-size: 0.8rem;">
                            <span>{game_state_lbl}</span>
                        </div>
                    </div>
                </div>

                <div id="live-consoles-container">{live_console_html}</div>

                <div class="card-body p-3">
                    <h5 class="fw-bold mb-3 text-dark border-bottom pb-2" style="font-size: 1rem;">📈 Split Analytics & Matchup Matrix</h5>
                    <div id="hr-predictor-container">{hr_predictor_html}</div>
                    <div id="bvp-cards-container">{bvp_cards_html}</div>

                    <div class="row g-2">
                        <div class="col-md-6">
                            <div class="border rounded p-2 bg-light">
                                <div class="fw-bold text-dark border-bottom pb-1 mb-2">{split_vl_header}</div>
                                <div class="d-flex justify-content-between small text-muted px-1 py-1"><span>{split_vol_label}</span><strong class="text-dark">{vl.get('ab', 0)}</strong></div>
                                <div class="d-flex justify-content-between small text-muted px-1 py-1"><span>Batting Avg:</span><strong class="text-dark">{vl.get('avg', '-')}</strong></div>
                                <div class="d-flex justify-content-between small text-muted px-1 py-1"><span>OPS:</span><strong class="text-dark">{vl.get('ops', '-')}</strong></div>
                                <div class="d-flex justify-content-between small text-muted px-1 py-1"><span>{split_hr_label}</span><strong class="text-dark">{vl.get('hr', 0)}</strong></div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="border rounded p-2 bg-light">
                                <div class="fw-bold text-dark border-bottom pb-1 mb-2">{split_vr_header}</div>
                                <div class="d-flex justify-content-between small text-muted px-1 py-1"><span>{split_vol_label}</span><strong class="text-dark">{vr.get('ab', 0)}</strong></div>
                                <div class="d-flex justify-content-between small text-muted px-1 py-1"><span>Batting Avg:</span><strong class="text-dark">{vr.get('avg', '-')}</strong></div>
                                <div class="d-flex justify-content-between small text-muted px-1 py-1"><span>OPS:</span><strong class="text-dark">{vr.get('ops', '-')}</strong></div>
                                <div class="d-flex justify-content-between small text-muted px-1 py-1"><span>{split_hr_label}</span><strong class="text-dark">{vr.get('hr', 0)}</strong></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card shadow-sm border rounded bg-white overflow-hidden mb-4" style="border-color: #dee2e6 !important;">
                <div class="card-header bg-dark text-white py-2"><h6 class="mb-0 fw-bold" style="font-size: 0.85rem;">📋 Rolling Performance Log (Last 10 Games)</h6></div>
                <div class="table-responsive">
                    <table class="table table-striped text-center align-middle mb-0" style="font-size:0.8rem; min-width: 500px;">
                        <thead class="table-light fw-bold text-secondary">
                            <tr><th class="text-start ps-3">Date</th><th>Game Line Performance</th><th>DraftKings Pts</th><th>FanDuel Pts</th></tr>
                        </thead>
                        <tbody>{historical_table_rows}</tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""

def main():
    if not os.path.exists(MASTER_DATA_PATH):
        return

    master_data = load_json_safe(MASTER_DATA_PATH)
    target_date_str = get_target_slate_date()
    
    daily_data = load_json_safe(f"data/daily_files/games_{target_date_str}.json")
    live_data = load_json_safe(f"data/LIVE/live_mlb_{target_date_str}.json")

    all_player_urls = []
    updated_count = 0

    for key, profile in master_data.items():
        player_name = profile.get("name", "Unknown Player")
        player_slug = profile.get("slug") or slugify(player_name)
        
        player_dir = os.path.join(OUTPUT_PLAYERS_DIR, player_slug)
        os.makedirs(player_dir, exist_ok=True)
        index_file_path = os.path.join(player_dir, "index.html")
        
        all_player_urls.append(f"{DOMAIN}/players/{player_slug}/")

        new_html_content = generate_player_html(profile, player_slug, daily_data, live_data)
        
        existing_html = ""
        if os.path.exists(index_file_path):
            with open(index_file_path, "r", encoding="utf-8") as f:
                existing_html = f.read()

        if new_html_content != existing_html:
            with open(index_file_path, "w", encoding="utf-8") as html_out:
                html_out.write(new_html_content)
            updated_count += 1

    update_sitemap(all_player_urls)

if __name__ == "__main__":
    main()
