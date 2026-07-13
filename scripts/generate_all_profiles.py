<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    
    <!-- 1. CONVERSATIONAL SEO META TAGS -->
    <title>Is {{ player_name }} Starting Today? Lineup & Stats | Futbol Starting Eleven</title>
    <meta name="description" content="Is {{ player_name }} starting today? Get live matchday lineup status, real-time performance stats, and season overview metrics for {{ player_name }} ({{ team_name }}).">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://futbolstartingeleven.com/players/{{ player_slug }}/">

    <!-- 2. OPEN GRAPH META TAGS -->
    <meta property="og:site_name" content="Futbol Starting Eleven">
    <meta property="og:type" content="profile">
    <meta property="og:title" content="Is {{ player_name }} Starting Today? Lineup & Stats | Futbol Starting Eleven">
    <meta property="og:description" content="Live starting lineups, form ratings, and seasonal breakdown for {{ player_name }} at {{ team_name }}.">
    <meta property="og:url" content="https://futbolstartingeleven.com/players/{{ player_slug }}/">
    <meta property="og:image" content="https://futbolstartingeleven.com/social-share1.png">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">

    <!-- 3. X / TWITTER CARD META TAGS -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:domain" content="futbolstartingeleven.com">
    <meta name="twitter:title" content="{{ player_name }} - {{ team_name }} Matchday Profile">
    <meta name="twitter:description" content="Track live performance matrix, formation maps, and stats for {{ player_name }} on Futbol Starting Eleven.">
    <meta name="twitter:image" content="https://futbolstartingeleven.com/social-share1.png">

    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <style>
        body { 
            background-color: #f1f3f5; 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
            overflow-x: hidden; 
        }
        
        /* THEME HEADER */
        .header-brand { font-weight: 900; letter-spacing: -1px; font-size: 2rem; color: #fff; font-style: italic; text-shadow: 0 2px 4px rgba(0,0,0,0.5); }
        .header-brand a { color: inherit; }
        .header-brand span { 
            text-shadow: none !important; 
            background: linear-gradient(to bottom, #20c997 0%, #198754 100%); 
            -webkit-background-clip: text; 
            -webkit-text-fill-color: transparent; 
            background-clip: text; 
            filter: drop-shadow(0 0 12px rgba(32, 201, 151, 0.6)); 
        }

        /* SIDEBAR PROFILE CARD */
        .profile-sidebar-card {
            background: #fff;
            border: 1px solid #dee2e6;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.03);
            padding: 24px;
            text-align: center;
        }
        .player-avatar-wrapper {
            position: relative;
            width: 110px;
            height: 110px;
            margin: 0 auto 15px auto;
        }
        .player-avatar {
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: 50%;
            border: 4px solid #20c997;
            background-color: #f8f9fa;
        }
        .team-badge-sub {
            position: absolute;
            bottom: -2px;
            right: -2px;
            width: 35px;
            height: 35px;
            background: #fff;
            border-radius: 50%;
            padding: 3px;
            border: 1px solid #dee2e6;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .sidebar-player-name {
            font-size: 1.4rem;
            font-weight: 800;
            color: #212529;
            margin-bottom: 2px;
        }
        .sidebar-player-meta {
            font-size: 0.8rem;
            font-weight: 700;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 20px;
        }

        /* SEAMLESS SEO LINK STYLES (Keeps native formatting) */
        .seo-link {
            color: inherit; 
            text-decoration: none; 
            transition: color 0.15s ease-in-out;
        }
        .sidebar-player-meta .seo-link:hover { color: #20c997; }
        .table tbody td .seo-link:hover { color: #198754; }
        .info-card .seo-link { font-weight: inherit; }
        .info-card .seo-link:hover { color: #198754; }

        /* INFO CARDS & DATA TABLES */
        .info-card {
            background: #fff;
            border: 1px solid #dee2e6;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.03);
            padding: 20px;
            margin-bottom: 24px;
        }
        .info-card h3 {
            font-size: 1rem;
            font-weight: 800;
            color: #212529;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #f1f3f5;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .stat-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #f8f9fa;
        }
        .stat-row:last-child { border-bottom: none; }
        .stat-label { color: #6c757d; font-size: 0.85rem; font-weight: 600; }
        .stat-value { color: #212529; font-size: 0.9rem; font-weight: 700; text-align: right; }

        /* H2H METRIC STYLING */
        .h2h-summary-box {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 12px;
            text-align: center;
        }
        .h2h-record-title { font-size: 0.75rem; font-weight: 700; color: #6c757d; text-transform: uppercase; margin-bottom: 3px; }
        .h2h-record-value { font-size: 1.25rem; font-weight: 800; color: #212529; }

        /* PERFORMANCE TABLE WRAPPER WITH CONTAINED OVERFLOW */
        .table-responsive {
            border-radius: 8px;
            overflow-x: auto;
            border: 1px solid #dee2e6;
            width: 100%;
        }
        .table thead th {
            background-color: #212529;
            color: #fff;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-weight: 700;
            border: none;
            padding: 12px;
            white-space: nowrap;
        }
        .table tbody td {
            font-size: 0.85rem;
            font-weight: 600;
            color: #495057;
            padding: 12px;
            vertical-align: middle;
            border-bottom: 1px solid #f1f3f5;
            white-space: nowrap;
        }
        .table tbody tr:last-child td { border-bottom: none; }
        .table tbody tr:hover { background-color: #f8f9fa; }
        .comp-logo { width: 20px; height: 20px; margin-right: 8px; vertical-align: text-bottom; }

        /* SUMMARY BLOCKS */
        .big-stat-box {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 12px;
            text-align: center;
            border: 1px solid #e9ecef;
        }
        .big-stat-value {
            font-size: 1.6rem;
            font-weight: 900;
            color: #198754;
            line-height: 1;
        }
        .big-stat-label {
            font-size: 0.7rem;
            font-weight: 700;
            color: #6c757d;
            text-transform: uppercase;
            margin-top: 5px;
            letter-spacing: 0.5px;
        }

        /* GREEN PULSING BALL ANIMATION */
        @keyframes pulse-green {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(32, 201, 151, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(32, 201, 151, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(32, 201, 151, 0); }
        }
        .live-dot {
            display: inline-block;
            width: 8px;
            height: 8px;
            background-color: #20c997;
            border-radius: 50%;
            margin-right: 6px;
            margin-bottom: 1px;
            animation: pulse-green 2s infinite;
        }

        @media (max-width: 576px) { 
            .header-brand { font-size: 1.5rem; } 
        }
    </style>
</head>
<body>

    <!-- NAVBAR -->
    <nav class="navbar sticky-top shadow-sm pt-2 pb-2 mb-4" style="background-color: #212529; z-index: 1050;">
        <div class="container d-flex justify-content-between align-items-center flex-wrap">
            <div class="header-brand">
                <a href="/" class="text-decoration-none">Futbol Starting <span>Eleven</span></a>
            </div>
            <div class="d-flex align-items-center gap-2">
                <a href="/lineups/{{ team_slug }}/" class="btn btn-sm btn-outline-light fw-bold" style="font-size:0.75rem;">← Back to {{ team_name }}</a>
            </div>
        </div>
    </nav>

    <!-- MAIN GRID CONTAINER -->
    <div class="container mb-5">
        <div class="row g-4">
            
            <!-- LEFT COLUMN: PHOTO + PERSONAL DETAILS -->
            <div class="col-lg-4">
                <div class="profile-sidebar-card">
                    
                    <div class="player-avatar-wrapper">
                        <img src="{{ player_photo_url }}" alt="{{ player_name }}" class="player-avatar">
                        <img src="{{ team_badge_url }}" alt="{{ team_name }}" class="team-badge-sub">
                    </div>
                    
                    <div class="sidebar-player-name">{{ player_name }}</div>
                    <div class="sidebar-player-meta"><a href="/lineups/{{ team_slug }}/" class="seo-link fw-bold">{{ team_name }}</a> • {{ player_position }}</div>
                    
                    <hr style="border-color: #dee2e6; opacity: 1; margin: 15px 0;">
                    
                    <div class="text-start">
                        <div class="stat-row">
                            <span class="stat-label">Nationality</span>
                            <span class="stat-value">{{ player_nationality_flag_entity }}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Age</span>
                            <span class="stat-value">{{ player_age }} ({{ player_birth_date }})</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Height / Weight</span>
                            <span class="stat-value">{{ player_height }} / {{ player_weight }}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Squad Number</span>
                            <span class="stat-value">#{{ player_number }}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Preferred Foot</span>
                            <span class="stat-value">{{ player_foot }}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Form Rating</span>
                            <span class="stat-value text-success">{{ player_rating }}</span>
                        </div>
                    </div>
                    
                </div>
            </div>

            <!-- RIGHT COLUMN: LIVE CARD + SPECIFIC STATISTICS -->
            <div class="col-lg-8">
                
                <!-- LIVE STATUS BAR -->
                <div class="info-card border-success" style="border-left: 5px solid #20c997; margin-bottom: 20px;">
                    <div class="d-flex align-items-center justify-content-between flex-wrap gap-2">
                        <div class="d-flex align-items-center">
                            <span class="live-dot"></span>
                            <span class="fw-bold text-dark" style="font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.5px;">Live Matchday Center</span>
                        </div>
                        <div class="stat-value text-end" style="font-size: 0.9rem;">
                            <a href="/lineups/{{ team_slug }}/" class="seo-link fw-bold text-dark">{{ team_name }}</a> vs <a href="/lineups/{{ opponent_slug }}/" class="seo-link fw-bold text-dark">{{ opponent_name }}</a> ({{ live_match_minute }}') <span class="text-muted font-monospace mx-1">|</span> <span class="badge bg-success text-white fw-bold px-2 py-1" style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px;">{{ live_lineup_status }}</span>
                        </div>
                    </div>
                </div>

                <!-- UPCOMING MATCHUP HEAD-TO-HEAD -->
                <div class="info-card" style="margin-bottom: 20px;">
                    <h3>Matchup History: {{ team_name }} vs {{ opponent_name }}</h3>
                    <div class="row g-2 mb-3">
                        <div class="col-4">
                            <div class="h2h-summary-box">
                                <div class="h2h-record-title">{{ team_name }} Wins</div>
                                <div class="h2h-record-value text-success">{{ h2h_home_wins }}</div>
                            </div>
                        </div>
                        <div class="col-4">
                            <div class="h2h-summary-box">
                                <div class="h2h-record-title">Draws</div>
                                <div class="h2h-record-value text-muted">{{ h2h_draws }}</div>
                            </div>
                        </div>
                        <div class="col-4">
                            <div class="h2h-summary-box">
                                <div class="h2h-record-title">{{ opponent_name }} Wins</div>
                                <div class="h2h-record-value text-danger">{{ h2h_away_wins }}</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="table-responsive">
                        <table class="table table-sm table-borderless mb-0 text-center" style="font-size: 0.8rem;">
                            <thead>
                                <tr style="background-color: #f8f9fa; border-bottom: 1px solid #dee2e6;">
                                    <th class="text-start" style="padding: 8px 12px; color: #6c757d;">Date</th>
                                    <th style="padding: 8px; color: #6c757d;">Competition</th>
                                    <th class="text-end" style="padding: 8px 12px; color: #6c757d;">Result</th>
                                </tr>
                            </thead>
                            <tbody>
                                {{ h2h_match_rows }}
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- POSITION STATISTICS OVERVIEW -->
                <div class="info-card">
                    <h3>{{ current_season }} Season Overview (All Comps)</h3>
                    <div class="row g-3">
                        <div class="col-6 col-sm-3">
                            <div class="big-stat-box">
                                <div class="big-stat-value">{{ total_matches }}</div>
                                <div class="big-stat-label">Matches</div>
                            </div>
                        </div>
                        <div class="col-6 col-sm-3">
                            <div class="big-stat-box">
                                <div class="big-stat-value">{{ highlight_metric_1_val }}</div>
                                <div class="big-stat-label">{{ highlight_metric_1_label }}</div>
                            </div>
                        </div>
                        <div class="col-6 col-sm-3">
                            <div class="big-stat-box">
                                <div class="big-stat-value">{{ highlight_metric_2_val }}</div>
                                <div class="big-stat-label">{{ highlight_metric_2_label }}</div>
                            </div>
                        </div>
                        <div class="col-6 col-sm-3">
                            <div class="big-stat-box">
                                <div class="big-stat-value">{{ highlight_metric_3_val }}</div>
                                <div class="big-stat-label">{{ highlight_metric_3_label }}</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- PERFORMANCE BREAKDOWN MATRIX -->
                <div class="info-card">
                    <h3>Performance by Competition</h3>
                    <div class="table-responsive">
                        <table class="table table-borderless mb-0">
                            <thead>
                                <tr>
                                    <th>Competition</th>
                                    <th class="text-center">MP</th>
                                    <th class="text-center">Min</th>
                                    <th class="text-center">Gls</th>
                                    <th class="text-center">Ast</th>
                                    <th class="text-center">{{ custom_header_1 }}</th>
                                    <th class="text-center">{{ custom_header_2 }}</th>
                                    <th class="text-center">{{ custom_header_3 }}</th>
                                    <th class="text-center">{{ custom_header_4 }}</th>
                                    <th class="text-center">Yel/Red</th>
                                </tr>
                            </thead>
                            <tbody>
                                {{ competition_rows }}
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- ROLLING 10-GAME MATCH LOG -->
                <div class="info-card">
                    <h3>Recent Matches (Last 10 Games)</h3>
                    <div class="table-responsive">
                        <table class="table table-sm table-borderless mb-0 text-center" style="font-size: 0.8rem;">
                            <thead>
                                <tr style="background-color: #f8f9fa; border-bottom: 1px solid #dee2e6;">
                                    <th class="text-start" style="padding: 8px 12px; color: #6c757d;">Date</th>
                                    <th class="text-start" style="padding: 8px; color: #6c757d;">Opponent</th>
                                    <th style="padding: 8px; color: #6c757d;">Result</th>
                                    <th style="padding: 8px; color: #6c757d;">Min</th>
                                    <th style="padding: 8px; color: #6c757d;">Gls</th>
                                    <th style="padding: 8px; color: #6c757d;">Ast</th>
                                    <th style="padding: 8px; color: #6c757d;">{{ custom_log_header }}</th>
                                    <th style="padding: 8px; color: #6c757d;">Rating</th>
                                </tr>
                            </thead>
                            <tbody>
                                {{ gamelog_rows }}
                            </tbody>
                        </table>
                    </div>
                </div>
                
            </div>
        </div>
    </div>

</body>
</html>
