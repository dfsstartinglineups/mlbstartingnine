import json
import os
from datetime import datetime, timedelta
import pytz
from jinja2 import Template

def load_json(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return data.get("games", [])
    except FileNotFoundError:
        print(f"Warning: File not found {filepath}")
        return []

def build_site():
    data_dir = 'data/daily_files'
    
    # 1. Get the exact current time in US/Eastern (EST/EDT)
    est_tz = pytz.timezone('US/Eastern')
    now_est = datetime.now(est_tz)
    
    # 2. Apply the 3:00 AM EST Crossover Logic
    # If it's between midnight and 2:59:59 AM EST, we are operationally still "yesterday"
    if now_est.hour < 3:
        operational_today = now_est - timedelta(days=1)
    else:
        operational_today = now_est

    # 3. Calculate operational yesterday and tomorrow relative to our shifted "today"
    operational_yesterday = operational_today - timedelta(days=1)
    operational_tomorrow = operational_today + timedelta(days=1)

    # 4. Format to string names matching your file system layout
    yesterday_str = operational_yesterday.strftime('%Y-%m-%d')
    today_str = operational_today.strftime('%Y-%m-%d')
    tomorrow_str = operational_tomorrow.strftime('%Y-%m-%d')
    
    print(f"Operational Window (3AM EST Rollover) Configured:")
    print(f" -> Yesterday Target: games_{yesterday_str}.json")
    print(f" -> Today Target:     games_{today_str}.json")
    print(f" -> Tomorrow Target:  games_{tomorrow_str}.json")

    # 5. Extract the dynamic date payloads
    data = {
        'yesterday': load_json(os.path.join(data_dir, f'games_{yesterday_str}.json')),
        'today': load_json(os.path.join(data_dir, f'games_{today_str}.json')),
        'tomorrow': load_json(os.path.join(data_dir, f'games_{tomorrow_str}.json'))
    }

    # The consolidated production template structure
    html_template = """<!DOCTYPE html>
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
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" href="/favicon.ico" sizes="any">
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">
    
    <title>MLB Starting Nine | Today's MLB Starting Lineups, Odds & Player Projections</title>
    
    <meta name="description" content="Live MLB starting lineups, probable pitchers, moneylines, and totals. Plus daily MLB player projections, Batter vs. Pitcher (BvP) matchups, pitcher splits, umpire tendencies, and park factors.">
    <meta name="keywords" content="MLB starting lineups, MLB player projections, MLB odds, baseball projections, BvP matchups, batter vs pitcher, pitcher splits, umpire tendencies, stadium park factors, daily fantasy baseball, DFS lineups, MLB betting, MLB starting pitchers">
    <meta property="og:site_name" content="MLB Starting Nine">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://mlbstartingnine.com/">
    <meta property="og:title" content="MLB Starting Nine | Today's MLB Starting Lineups, Odds & Player Projections">
    <meta property="og:description" content="Live MLB starting lineups, probable pitchers, moneylines, and totals. Plus daily MLB player projections, Batter vs. Pitcher (BvP) matchups, pitcher splits, and umpire tendencies.">
    <meta property="og:image" content="https://mlbstartingnine.com/mlb-social-share.jpg">

    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <style>
        body { background-color: #f1f3f5; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        .header-brand { font-weight: 900; letter-spacing: -1px; font-size: 2rem; color: #fff; font-style: italic; text-shadow: 0 2px 4px rgba(0,0,0,0.5); }
        .header-brand a { color: inherit; text-decoration: none; }
        .header-brand span { background: linear-gradient(to bottom, #7CD0FF 0%, #1A8CFF 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; padding-right: 2px; display: inline-block; }
        .lineup-card { background: #fff; border: 1px solid #dee2e6; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 24px; overflow: hidden; }
        .team-logo { width: 65px; height: 65px; object-fit: contain; filter: drop-shadow(0px 2px 2px rgba(0,0,0,0.1)); }
        .batting-order { padding-left: 0; list-style-type: none; margin-bottom: 0; }
        .batting-order li { padding: 6px 12px; font-size: 0.85rem; border-bottom: 1px solid #f1f3f5; display: flex; justify-content: space-between; align-items: center; }
        .batting-order li:last-child { border-bottom: none; }
        .promo-btn { font-size: 0.8rem; font-weight: 700; letter-spacing: 0.5px; }
        #team-search { color: #ffffff !important; color-scheme: dark; width: 45px; transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1); background-color: #343a40; border: 1px solid #495057; cursor: pointer; }
        #team-search::placeholder { color: #adb5bd !important; opacity: 1; }
        #team-search:focus { width: 150px; background-color: #495057 !important; color: #ffffff !important; border-color: #0d6efd !important; box-shadow: 0 0 0 0.2rem rgba(13, 110, 253, 0.25) !important; cursor: text; }
        
        .day-container { display: none; }
        #today-container { display: flex; } 
    </style>
</head>
<body>

<nav class="navbar shadow-sm py-3 mb-2" style="background-color: #212529;">
    <div class="container d-flex justify-content-between align-items-center flex-wrap">
        <div class="header-brand mb-2 mb-md-0">
            <a href="/" class="text-decoration-none">MLB Starting <span>Nine</span></a>
        </div>
        <div class="d-flex align-items-center gap-2 gap-md-3">
            <input type="text" id="team-search" class="form-control form-control-sm" placeholder="🔍">
            <div class="btn-group" role="group">
                <button type="button" class="btn btn-sm btn-outline-light fw-bold" onclick="showDay('yesterday-container')">Yesterday</button>
                <button type="button" class="btn btn-sm btn-light fw-bold" onclick="showDay('today-container')">Today</button>
                <button type="button" class="btn btn-sm btn-outline-light fw-bold" onclick="showDay('tomorrow-container')">Tomorrow</button>
            </div>
        </div>
    </div>
</nav>

<div class="container mt-3 mb-3 text-center">
    <h1 class="h5 fw-bold text-dark mb-1">MLB Starting Nine: Today's MLB Starting Lineups, Odds & Player Projections</h1>
    <p class="text-muted mb-2" style="font-size: 0.85rem;">Live BvP matchups, pitcher splits, umpire tendencies, daily fantasy projections, and park factors.</p>
</div>

{% macro render_game(item) %}
    {% set game = item.gameRaw %}
    {% set away_name = game.teams.away.team.teamName %}
    {% set home_name = game.teams.home.team.teamName %}
    {% set away_id = game.teams.away.team.id %}
    {% set home_id = game.teams.home.team.id %}
    
    <div class="col-md-6 col-lg-6 col-xl-4 px-1 mb-3">
        <div class="lineup-card shadow-sm border rounded bg-white overflow-hidden h-100" style="border-color: #dee2e6 !important;" id="game-{{ game.gamePk }}">
            <div class="p-2 pb-1" style="background-color: #edf4f8;">
                <div class="d-flex justify-content-between align-items-center mb-0 w-100 pb-1 border-white">
                    <div class="d-flex align-items-center flex-shrink-0">
                        <span class="badge bg-primary text-white shadow-sm border px-2 py-1" style="font-size: 0.70rem;">
                            {{ game.status.detailedState }}
                        </span>
                    </div>
                    <div class="text-muted fw-bold text-uppercase text-end ms-auto" style="font-size: 0.70rem; letter-spacing: 0.5px; line-height: 1.1;">
                        {{ game.venue.name }}
                    </div>
                </div>
                
                <div class="d-flex justify-content-between w-100 mt-2 px-1">
                    <div class="d-flex flex-column" style="width: 48%;">
                        <div class="d-flex align-items-center text-truncate mb-1">
                            <img src="https://www.mlbstatic.com/team-logos/team-cap-on-light/{{ away_id }}.svg" style="height: 24px; width: 24px; margin-right: 6px; flex-shrink: 0;">
                            <span class="fw-bold text-truncate" style="font-size: 0.95rem;">{{ away_name }}</span>
                        </div>
                    </div>
                    <div class="d-flex flex-column" style="width: 48%;">
                        <div class="d-flex align-items-center text-truncate mb-1">
                            <img src="https://www.mlbstatic.com/team-logos/team-cap-on-light/{{ home_id }}.svg" style="height: 24px; width: 24px; margin-right: 6px; flex-shrink: 0;">
                            <span class="fw-bold text-truncate" style="font-size: 0.95rem;">{{ home_name }}</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="d-flex justify-content-center align-items-center gap-2 my-2 px-2 pb-2 border-bottom w-100">
                <button class="btn btn-sm fw-bold rounded-pill px-3 py-1 tab-btn flex-grow-1 active btn-primary text-white" style="font-size: 0.65rem;" onclick="switchTab(this, 'season')">SEASON</button>
                <button class="btn btn-sm fw-bold rounded-pill px-3 py-1 tab-btn flex-grow-1 btn-outline-secondary text-muted" style="font-size: 0.65rem;" onclick="switchTab(this, 'vsp')">VS P</button>
                <button class="btn btn-sm fw-bold rounded-pill px-3 py-1 tab-btn flex-grow-1 btn-outline-secondary text-muted" style="font-size: 0.65rem;" onclick="switchTab(this, 'splits')">SPLITS</button>
            </div>
            
            <div class="row g-0 bg-white">
                <div class="col-6 border-end">
                    <div class="text-center py-1 fw-bold text-dark w-100 border-bottom" style="background-color: #ffecb5; font-size: 0.75rem;"><span style="font-size: 0.7rem;">⏳</span> PROJECTED</div>
                    <div class="w-100 m-0 p-0">
                        <ul class="batting-order w-100 m-0 p-0" style="list-style-type: none;">
                            {% for player in item.projectedLineups.away.battingOrder if item.projectedLineups and item.projectedLineups.away %}
                            <li class="d-flex align-items-center w-100 px-2 py-1 border-bottom" style="min-height: 36px;">
                                <div class="d-flex align-items-center flex-grow-1 text-truncate w-100 lh-sm">
                                    <span class="text-muted fw-bold text-center flex-shrink-0" style="font-size: 0.65rem; width: 22px; margin-right: 4px;">{{ loop.index }}.</span>
                                    <img src="https://img.mlbstatic.com/mlb-photos/image/upload/d_people:brooks:default/w_180,q_auto:best/v1/people/{{ player.id }}/headshot/67/current" style="width: 26px; height: 26px; border-radius: 50%; object-fit: cover; border: 1px solid #dee2e6; margin-right: 6px;">
                                    <span class="batter-name fw-bold text-dark text-truncate ms-1" style="font-size: 0.70rem;">{{ player.name }}</span>
                                </div>
                            </li>
                            {% else %}
                            <div class="p-4 text-center text-muted small fw-bold">Lineup not yet posted</div>
                            {% endfor %}
                        </ul>
                    </div>
                </div>
                <div class="col-6">
                    <div class="text-center py-1 fw-bold text-dark w-100 border-bottom" style="background-color: #ffecb5; font-size: 0.75rem;"><span style="font-size: 0.7rem;">⏳</span> PROJECTED</div>
                    <div class="w-100 m-0 p-0">
                        <ul class="batting-order w-100 m-0 p-0" style="list-style-type: none;">
                            {% for player in item.projectedLineups.home.battingOrder if item.projectedLineups and item.projectedLineups.home %}
                            <li class="d-flex align-items-center w-100 px-2 py-1 border-bottom" style="min-height: 36px;">
                                <div class="d-flex align-items-center flex-grow-1 text-truncate w-100 lh-sm">
                                    <span class="text-muted fw-bold text-center flex-shrink-0" style="font-size: 0.65rem; width: 22px; margin-right: 4px;">{{ loop.index }}.</span>
                                    <img src="https://img.mlbstatic.com/mlb-photos/image/upload/d_people:brooks:default/w_180,q_auto:best/v1/people/{{ player.id }}/headshot/67/current" style="width: 26px; height: 26px; border-radius: 50%; object-fit: cover; border: 1px solid #dee2e6; margin-right: 6px;">
                                    <span class="batter-name fw-bold text-dark text-truncate ms-1" style="font-size: 0.70rem;">{{ player.name }}</span>
                                </div>
                            </li>
                            {% else %}
                            <div class="p-4 text-center text-muted small fw-bold">Lineup not yet posted</div>
                            {% endfor %}
                        </ul>
                    </div>
                </div>
            </div>

            <div class="p-2 text-center bg-white">
                <a href="https://weathermlb.com/#game-{{ game.gamePk }}" target="_blank" class="btn btn-sm w-100 promo-btn" style="background-color: #f8f9fa; border: 1px solid #dee2e6; color: #0d6efd;">
                    🌧️ View Weather & Wind Impact
                </a>
            </div>
        </div>
    </div>
{% endmacro %}

<div class="container">
    <div id="yesterday-container" class="row justify-content-center day-container">
        {% for game in data.yesterday %}
            {{ render_game(game) }}
        {% else %}
            <div class="col-12 text-center py-5 text-muted fw-bold">No games scheduled.</div>
        {% endfor %}
    </div>

    <div id="today-container" class="row justify-content-center day-container">
        {% for game in data.today %}
            {{ render_game(game) }}
        {% else %}
            <div class="col-12 text-center py-5 text-muted fw-bold">No games scheduled.</div>
        {% endfor %}
    </div>

    <div id="tomorrow-container" class="row justify-content-center day-container">
        {% for game in data.tomorrow %}
            {{ render_game(game) }}
        {% else %}
            <div class="col-12 text-center py-5 text-muted fw-bold">No games scheduled.</div>
        {% endfor %}
    </div>
</div>

<footer class="mt-5 py-4 bg-light border-top">
    <div class="container text-center">
        <p class="text-muted mb-1" style="font-size: 0.85rem; font-weight: 600;">© 2026 MLB Starting Nine</p>
    </div>
</footer>

<script>
    function showDay(containerId) {
        document.querySelectorAll('.day-container').forEach(el => {
            el.style.display = 'none';
        });
        document.getElementById(containerId).style.display = 'flex';
        
        document.querySelectorAll('.btn-group button').forEach(btn => {
            btn.classList.remove('btn-light');
            btn.classList.add('btn-outline-light');
        });
        event.target.classList.remove('btn-outline-light');
        event.target.classList.add('btn-light');
    }

    function switchTab(btn, tabName) {
        const card = btn.closest('.lineup-card');
        const allBtns = card.querySelectorAll('.tab-btn');
        allBtns.forEach(b => {
            b.classList.remove('active', 'btn-primary', 'text-white');
            b.classList.add('btn-outline-secondary', 'text-muted');
        });
        btn.classList.add('active', 'btn-primary', 'text-white');
        btn.classList.remove('btn-outline-secondary', 'text-muted');
    }
</script>

<script src="silent_refresh.js"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

    print("Compiling HTML with Jinja2...")
    template = Template(html_template)
    rendered_html = template.render(data=data)

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(rendered_html)
        
    print("Successfully built static index.html")

if __name__ == "__main__":
    build_site()
