import os

# ==========================================
# 1. THE MASTER 30 MLB TEAMS DICTIONARY
# ==========================================
# Maps exact MLB API IDs to clean URL slugs and display names
MLB_TEAMS = [
    # AL East
    {"id": 110, "slug": "baltimore-orioles", "name": "Baltimore Orioles"},
    {"id": 111, "slug": "boston-red-sox", "name": "Boston Red Sox"},
    {"id": 147, "slug": "new-york-yankees", "name": "New York Yankees"},
    {"id": 139, "slug": "tampa-bay-rays", "name": "Tampa Bay Rays"},
    {"id": 141, "slug": "toronto-blue-jays", "name": "Toronto Blue Jays"},
    # AL Central
    {"id": 145, "slug": "chicago-white-sox", "name": "Chicago White Sox"},
    {"id": 114, "slug": "cleveland-guardians", "name": "Cleveland Guardians"},
    {"id": 116, "slug": "detroit-tigers", "name": "Detroit Tigers"},
    {"id": 118, "slug": "kansas-city-royals", "name": "Kansas City Royals"},
    {"id": 142, "slug": "minnesota-twins", "name": "Minnesota Twins"},
    # AL West
    {"id": 117, "slug": "houston-astros", "name": "Houston Astros"},
    {"id": 108, "slug": "los-angeles-angels", "name": "Los Angeles Angels"},
    {"id": 133, "slug": "athletics", "name": "Athletics"},
    {"id": 136, "slug": "seattle-mariners", "name": "Seattle Mariners"},
    {"id": 140, "slug": "texas-rangers", "name": "Texas Rangers"},
    # NL East
    {"id": 144, "slug": "atlanta-braves", "name": "Atlanta Braves"},
    {"id": 146, "slug": "miami-marlins", "name": "Miami Marlins"},
    {"id": 121, "slug": "new-york-mets", "name": "New York Mets"},
    {"id": 143, "slug": "philadelphia-phillies", "name": "Philadelphia Phillies"},
    {"id": 120, "slug": "washington-nationals", "name": "Washington Nationals"},
    # NL Central
    {"id": 112, "slug": "chicago-cubs", "name": "Chicago Cubs"},
    {"id": 113, "slug": "cincinnati-reds", "name": "Cincinnati Reds"},
    {"id": 158, "slug": "milwaukee-brewers", "name": "Milwaukee Brewers"},
    {"id": 134, "slug": "pittsburgh-pirates", "name": "Pittsburgh Pirates"},
    {"id": 138, "slug": "st-louis-cardinals", "name": "St. Louis Cardinals"},
    # NL West
    {"id": 109, "slug": "arizona-diamondbacks", "name": "Arizona Diamondbacks"},
    {"id": 115, "slug": "colorado-rockies", "name": "Colorado Rockies"},
    {"id": 119, "slug": "los-angeles-dodgers", "name": "Los Angeles Dodgers"},
    {"id": 135, "slug": "san-diego-padres", "name": "San Diego Padres"},
    {"id": 137, "slug": "san-francisco-giants", "name": "San Francisco Giants"}
]

# ==========================================
# 2. THE HARDCODED STATIC HTML TEMPLATE
# ==========================================
# Notice the ../../ relative paths to ensure your root CSS and JS load cleanly!
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    
    <title>{team_name} Starting Lineup Today | Batting Order & Pitcher</title>
    <meta name="description" content="View the official {team_name} starting lineup, projected batting order, confirmed starting pitcher, live Vegas odds, and DFS matchup stats for today's game.">
    <link rel="canonical" href="https://mlbstartingnine.com/lineups/{team_slug}">
    
    <meta property="og:type" content="website">
    <meta property="og:title" content="{team_name} Starting 9 | Today's Lineup & Stats">
    <meta property="og:description" content="Official batting order, live odds, and matchup analytics for the {team_name}. Updated in real-time.">
    <meta property="og:url" content="https://mlbstartingnine.com/lineups/{team_slug}">
    <meta property="og:site_name" content="MLB Starting 9">
    <meta name="twitter:card" content="summary_large_image">
    
    
    
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Montserrat:wght@400;600;700&family=Roboto+Mono:wght@500;700&display=swap" rel="stylesheet">
<style>
        body { background-color: #f1f3f5; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        
        /* Sleek Header - Upgraded to match image */
        .header-brand { 
            font-weight: 900; 
            letter-spacing: -1px; 
            font-size: 2rem; 
            color: #fff; 
            font-style: italic; 
            text-shadow: 0 2px 4px rgba(0,0,0,0.5); 
        }
        .header-brand a {
            color: inherit;
        }
        .header-brand span { 
            text-shadow: none !important;
            background: linear-gradient(to bottom, #7CD0FF 0%, #1A8CFF 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            filter: drop-shadow(0 0 12px rgba(26, 140, 255, 0.8));
            padding-right: 2px; /* Fix for italic 'e' getting cut off */
            display: inline-block; /* Required for padding to push the bounding box */
        }
        
        /* Lineup Card */
        .lineup-card { 
            background: #fff; 
            border: 1px solid #dee2e6; 
            border-radius: 12px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            margin-bottom: 24px;
            overflow: hidden;
        }

        /* Logos */
        .team-logo {
            width: 65px;
            height: 65px;
            object-fit: contain;
            filter: drop-shadow(0px 2px 2px rgba(0,0,0,0.1));
        }
        
        /* Batting Order List */
        .batting-order { padding-left: 0; list-style-type: none; margin-bottom: 0; }
        .batting-order li {
            padding: 6px 12px;
            font-size: 0.85rem;
            border-bottom: 1px solid #f1f3f5;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .batting-order li:last-child { border-bottom: none; }
        .order-num { color: #adb5bd; font-weight: 700; font-size: 0.7rem; width: 15px; display: inline-block; }
        .batter-name { font-weight: 600; color: #495057; }
        
        /* Cross-Promo Link */
        .promo-btn { font-size: 0.8rem; font-weight: 700; letter-spacing: 0.5px; }

        /* --- X (Twitter) Share Button Styles --- */
        .x-btn {
            background-color: #000;
            color: #fff;
            border: none;
            border-radius: 4px;
            padding: 4px 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background-color 0.2s;
        }
        .x-btn:hover {
            background-color: #333;
            color: #fff;
        }
        .x-icon {
            fill: currentColor;
            width: 14px;
            height: 14px;
        }

        
        /* EXPANDING SEARCH BOX (MLB THEME) */
        #team-search { 
            color: #ffffff !important; 
            color-scheme: dark; 
            width: 45px;
            transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            background-color: #343a40;
            border: 1px solid #495057;
            cursor: pointer;
        }
        #team-search::placeholder { 
            color: #adb5bd !important; 
            opacity: 1; 
        }
        #team-search:focus { 
            width: 150px;
            background-color: #495057 !important; 
            color: #ffffff !important; 
            border-color: #0d6efd !important; /* MLB Blue */
            box-shadow: 0 0 0 0.2rem rgba(13, 110, 253, 0.25) !important;
            cursor: text;
        }
    </style>

</head>
<body class="dark-theme">

    <div id="main-wrapper">
        <div id="header-container"></div>
        <div id="capture-area"></div>
        <div id="public-analytics-section"></div>
        <div id="footer-container"></div>
    </div>

    <script>
        window.TARGET_TEAM_SLUG = "{team_slug}";
        window.TARGET_TEAM_ID = {team_id};
        window.TARGET_TEAM_NAME = "{team_name}";
    </script>

    <script src="../../mlb_starting_lineup.js"></script>
</body>
</html>
"""

# ==========================================
# 3. BUILD ENGINE
# ==========================================
def generate_all_team_pages():
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lineups")
    
    print("⚾ Starting MLB Team Pages Generator...")
    
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        print(f"📁 Created master directory: {base_dir}")
        
    for team in MLB_TEAMS:
        team_dir = os.path.join(base_dir, team["slug"])
        
        # Create team folder if it doesn't exist
        if not os.path.exists(team_dir):
            os.makedirs(team_dir)
            
        # Format the HTML template with this specific team's data
        # Safely replace variables without tripping over CSS curly braces
        file_content = (
            HTML_TEMPLATE.replace("{team_name}", team["name"])
                         .replace("{team_slug}", team["slug"])
                         .replace("{team_id}", str(team["id"]))
        )
        
        file_path = os.path.join(team_dir, "index.html")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file_content)
            
        print(f"✅ Generated: /lineups/{team['slug']}/index.html")
        
    print(f"\n🚀 Successfully generated all 30 static MLB team pages inside '{base_dir}'!")

if __name__ == "__main__":
    generate_all_team_pages()
