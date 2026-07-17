// Lightweight Live Hydration Engine - MLB Starting Nine

const safeText = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };
const safeHtml = (id, html) => { const el = document.getElementById(id); if (el) el.innerHTML = html; };

function getTargetSlateDate() {
    const now = new Date();
    const estStr = now.toLocaleString("en-US", { timeZone: "America/New_York" });
    const estDate = new Date(estStr);
    if (estDate.getHours() < 4) { estDate.setDate(estDate.getDate() - 1); }
    const yyyy = estDate.getFullYear();
    const mm = String(estDate.getMonth() + 1).padStart(2, '0');
    const dd = String(estDate.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
}

function getSlugFromId(id) {
    const slugMap = {
        108: "los-angeles-angels", 109: "arizona-diamondbacks", 110: "baltimore-orioles", 111: "boston-red-sox",
        112: "chicago-cubs", 113: "cincinnati-reds", 114: "cleveland-guardians", 115: "colorado-rockies",
        116: "detroit-tigers", 117: "houston-astros", 118: "kansas-city-royals", 119: "los-angeles-dodgers",
        120: "washington-nationals", 121: "new-york-mets", 133: "athletics", 134: "pittsburgh-pirates",
        135: "san-diego-padres", 136: "seattle-mariners", 137: "san-francisco-giants", 138: "st-louis-cardinals",
        139: "tampa-bay-rays", 140: "texas-rangers", 141: "toronto-blue-jays", 142: "minnesota-twins",
        143: "philadelphia-phillies", 144: "atlanta-braves", 145: "chicago-white-sox", 146: "miami-marlins",
        147: "new-york-yankees", 158: "milwaukee-brewers"
    };
    return slugMap[id] || "los-angeles-dodgers";
}

async function loadPlayerProfileData() {
    if (typeof PLAYER_ID === 'undefined') return;

    const targetDateStr = getTargetSlateDate();
    
    try {
        const dailyRes = await fetch(`https://mlbstartingnine.com/data/daily_files/games_${targetDateStr}.json`);
        const liveRes = await fetch(`https://mlbstartingnine.com/data/LIVE/live_mlb_${targetDateStr}.json?v=` + Date.now()).catch(() => ({ ok: false }));
        
        if (dailyRes.ok) {
            const dailyData = await dailyRes.json();
            const liveData = liveRes.ok ? await liveRes.json() : {};
            
            let myGame = null;
            let teamSide = null;
            let matchingGames = []; // Track all matches for doubleheaders
            
            // Read the team name that Python baked into the header (e.g., "San Francisco Giants")
            const metaSub = document.getElementById('player-meta-sub')?.textContent || "";
            
            // 1. Gather all potential game matches for this team/player
            for (const game of (dailyData.games || [])) {
                const homeTeamName = game.gameRaw?.teams?.home?.team?.name || "";
                const awayTeamName = game.gameRaw?.teams?.away?.team?.name || "";
                
                const homeP = String(game.gameRaw?.teams?.home?.probablePitcher?.id || game.projectedLineups?.home?.startingPitcher?.id);
                const awayP = String(game.gameRaw?.teams?.away?.probablePitcher?.id || game.projectedLineups?.away?.startingPitcher?.id);
                
                const inHome = (game.gameRaw?.lineups?.homePlayers || []).some(p => String(p.id) === PLAYER_ID) || 
                               (game.projectedLineups?.home?.battingOrder || []).some(p => String(p.id) === PLAYER_ID) || 
                               homeP === PLAYER_ID ||
                               (homeTeamName && metaSub.includes(homeTeamName));

                const inAway = (game.gameRaw?.lineups?.awayPlayers || []).some(p => String(p.id) === PLAYER_ID) || 
                               (game.projectedLineups?.away?.battingOrder || []).some(p => String(p.id) === PLAYER_ID) || 
                               awayP === PLAYER_ID ||
                               (awayTeamName && metaSub.includes(awayTeamName));
                
                if (inHome) { matchingGames.push({ game, teamSide: 'home' }); }
                if (inAway) { matchingGames.push({ game, teamSide: 'away' }); }
            }

            // 2. DOUBLEHEADER RESOLUTION LOGIC
            if (matchingGames.length > 0) {
                let selectedMatch = matchingGames[0]; // Default fallback

                if (matchingGames.length > 1) {
                    // Check if one of the games is currently live or active
                    const liveMatch = matchingGames.find(m => {
                        const state = m.game.gameRaw?.status?.abstractGameState || "";
                        return state === "Live" || state === "In Progress";
                    });

                    // Check if one of the games is upcoming
                    const upcomingMatch = matchingGames.find(m => {
                        const state = m.game.gameRaw?.status?.abstractGameState || "";
                        return state === "Preview" || state === "Scheduled";
                    });

                    if (liveMatch) {
                        selectedMatch = liveMatch; // Prioritize the game currently being played
                    } else if (upcomingMatch) {
                        selectedMatch = upcomingMatch; // Otherwise, prioritize the next game on deck
                    } else {
                        selectedMatch = matchingGames[matchingGames.length - 1]; // If both are Final, show the nightcap
                    }
                }

                myGame = selectedMatch.game;
                teamSide = selectedMatch.teamSide;
            }

            if (myGame) {
                const badgeZone = document.getElementById('badge-matrix-zone');
                const bvpZone = document.getElementById('bvp-cards-container');
                const liveConsoleZone = document.getElementById('live-consoles-container');
                const hrZone = document.getElementById('hr-predictor-container');
                
                const gameRaw = myGame.gameRaw || {};
                const gamePk = String(gameRaw.gamePk);
                const oppSide = teamSide === "away" ? "home" : "away";
                const sideLabelUpper = teamSide === "away" ? "AWAY" : "HOME";
                
                // Hydrate Team Logo Dynamically
                const myTeamId = gameRaw.teams?.[teamSide]?.team?.id;
                if (myTeamId) {
                    const logoEl = document.getElementById('player-team-logo');
                    if (logoEl) logoEl.src = `https://www.mlbstatic.com/team-logos/team-cap-on-light/${myTeamId}.svg`;
                }

                const trackingNode = myGame.lineupTracking?.[teamSide] || {};
                const oppPitcherName = gameRaw.teams?.[oppSide]?.probablePitcher?.fullName || "TBD";
                const oppPitcherId = String(gameRaw.teams?.[oppSide]?.probablePitcher?.id);
                const pDeepStats = myGame.deepStats[PLAYER_ID] || {};
                
                let pProjNode = null;
                if (myGame.projectedLineups?.[teamSide]) {
                    const pl = myGame.projectedLineups[teamSide];
                    if (String(pl.startingPitcher?.id) === PLAYER_ID) {
                        pProjNode = pl.startingPitcher;
                    } else {
                        pProjNode = (pl.battingOrder || []).find(p => String(p.id) === PLAYER_ID);
                    }
                }
                
                let dkRaw = pProjNode?.dk_slates ? pProjNode.dk_slates[Object.keys(pProjNode.dk_slates)[0]]?.proj : pProjNode?.dk_proj;
                let fdRaw = pProjNode?.fd_slates ? pProjNode.fd_slates[Object.keys(pProjNode.fd_slates)[0]]?.proj : pProjNode?.proj;
                
                dkRaw = dkRaw ?? pDeepStats.dk_proj ?? pDeepStats.dk_points;
                fdRaw = fdRaw ?? pDeepStats.fd_proj ?? pDeepStats.fd_points ?? pDeepStats.proj;
                
                const dkProjectionValue = (dkRaw) ? Number(dkRaw).toFixed(1) : 'NA';
                const fdProjectionValue = (fdRaw) ? Number(fdRaw).toFixed(1) : 'NA';

                let isConfirmed = trackingNode.status === "OFFICIAL";
                let slotIndex = -1;
                if (isConfirmed && trackingNode.hash) {
                    slotIndex = trackingNode.hash.split('-').indexOf(PLAYER_ID);
                }
                if (slotIndex === -1) {
                    slotIndex = (myGame.projectedLineups?.[teamSide]?.battingOrder || []).findIndex(p => String(p.id) === PLAYER_ID);
                }

                const isStartingPitcher = String(gameRaw.teams?.[teamSide]?.probablePitcher?.id) === PLAYER_ID || 
                                          String(myGame.projectedLineups?.[teamSide]?.startingPitcher?.id) === PLAYER_ID;

                // Check for game postponement status
                const abstractState = gameRaw.status?.abstractGameState || "";
                const detailedState = gameRaw.status?.detailedState || "";
                const isPostponed = abstractState.includes("Postponed") || detailedState.includes("Postponed") || gameRaw.status?.statusCode === "C";

                let badgeHtml = '';
                if (isPostponed) {
                    badgeHtml = `<div class="badge bg-danger p-2 w-100 shadow-sm text-uppercase fw-bold text-white">✕ GAME POSTPONED</div>`;
                } else if (isStartingPitcher) {
                    badgeHtml = `<div class="badge status-badge-confirmed p-2 w-100 shadow-sm text-uppercase">IN LINEUP:  Starting Pitcher</div>`;
                } else {
                    if (isConfirmed && slotIndex !== -1) {
                        badgeHtml = `<div class="badge status-badge-confirmed p-2 w-100 shadow-sm text-uppercase">IN LINEUP:  Batting #${slotIndex + 1}</div>`;
                    } else if (isConfirmed && slotIndex === -1) {
                        // NEW LOGIC: Team is official, player is completely scratched
                        badgeHtml = `<div class="badge status-badge-scratched p-2 w-100 shadow-sm text-uppercase">✕ NOT STARTING</div>`;
                    } else if (slotIndex !== -1) {
                        badgeHtml = `<div class="badge status-badge-projected p-2 w-100 shadow-sm text-uppercase text-dark">Projected #${slotIndex + 1}</div>`;
                    } else {
                        // Team is not official yet, but player isn't projected to play
                        badgeHtml = `<div class="badge status-badge-scratched p-2 w-100 shadow-sm text-uppercase">✕ NOT PROJECTED TO START</div>`;
                    }
                }

                const teamSlug = getSlugFromId(myTeamId);
                const lineupLinkText = isConfirmed ? "View Official Lineup" : "View Projected Lineup";
                const lineupLinkHtml = isPostponed ? "" : `<a href="https://mlbstartingnine.com/lineups/${teamSlug}/" class="btn btn-sm btn-outline-primary w-100 mt-2 fw-bold text-uppercase shadow-sm" style="font-size: 0.7rem; letter-spacing: 0.5px;">📊 ${lineupLinkText}</a>`;

                badgeZone.innerHTML = `<div class="mb-3">${badgeHtml}${lineupLinkHtml}</div>`;

                // If game is postponed, update text status and halt active rendering 
                if (isPostponed) {
                    safeHtml('live-game-state-label', `<strong>Game Status:</strong> <span class="text-danger fw-bold">Postponed</span>`);
                    liveConsoleZone.innerHTML = `
                    <div class="p-3 border-bottom text-center" style="background-color: #fdf2f2;">
                        <span class="badge bg-danger text-uppercase mb-1" style="font-size:0.6rem;">PPD</span>
                        <span class="text-dark d-block fw-semibold" style="font-size: 0.85rem;">This matchup has been called off.</span>
                    </div>`;
                    if (hrZone) hrZone.innerHTML = '';
                    return;
                }

                // Game State Text
                const activeLiveGame = liveData[gamePk];
                if (activeLiveGame) {
                    let gameStateStr = activeLiveGame.status === "Final" ? "Final" : `${activeLiveGame.half || ''} ${activeLiveGame.inning ? activeLiveGame.inning.replace(/\D/g, '') : ''}`;
                    safeHtml('live-game-state-label', `<strong>Game Status:</strong> ${gameStateStr}`);

                    const playerBox = activeLiveGame.players?.[sideLabelUpper]?.[`ID${PLAYER_ID}`];
                    const profile = playerBox?.batting || playerBox?.pitching;
                    
                    if (playerBox && profile?.summary) {
                        liveConsoleZone.innerHTML = `
                        <div class="p-3 border-bottom" style="background-color: #edf4f8;">
                            <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
                                <div>
                                    <span class="badge bg-primary text-uppercase me-2" style="font-size:0.65rem;">Box Score</span>
                                    <strong class="text-dark" style="font-size: 0.9rem;">${profile.summary}</strong>
                                </div>
                                <div class="d-flex align-items-center gap-2">
                                    <div class="bg-white border rounded px-3 py-1 shadow-sm text-center">
                                        <span class="text-muted d-block" style="font-size: 0.55rem; font-weight:700; text-transform:uppercase;">DraftKings</span>
                                        <div class="d-flex align-items-baseline gap-1">
                                            <span class="dk-accent" style="font-size: 1.1rem;">${playerBox.dk_pts.toFixed(1)}</span>
                                            <span class="text-muted" style="font-size:0.75rem;">/</span>
                                            <span class="text-secondary fw-bold" style="font-size:0.85rem;">${dkProjectionValue}</span>
                                        </div>
                                    </div>
                                    <div class="bg-white border rounded px-3 py-1 shadow-sm text-center">
                                        <span class="text-muted d-block" style="font-size: 0.55rem; font-weight:700; text-transform:uppercase;">FanDuel</span>
                                        <div class="d-flex align-items-baseline gap-1">
                                            <span class="fd-accent" style="font-size: 1.1rem;">${playerBox.fd_pts.toFixed(1)}</span>
                                            <span class="text-muted" style="font-size:0.75rem;">/</span>
                                            <span class="text-secondary fw-bold" style="font-size:0.85rem;">${fdProjectionValue}</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>`;
                    }
                } else {
                    safeHtml('live-game-state-label', `<strong>Game Status:</strong> ${gameRaw.status?.abstractGameState || 'Scheduled'}`);
                    liveConsoleZone.innerHTML = `
                    <div class="p-3 border-bottom" style="background-color: #edf4f8;">
                        <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
                            <div>
                                <span class="badge bg-secondary text-uppercase me-2" style="font-size:0.65rem;">Upcoming Matchup</span>
                                <span class="text-dark fw-semibold" style="font-size: 0.85rem;">vs. ${oppPitcherName}</span>
                            </div>
                            <div class="d-flex align-items-center gap-2">
                                <div class="bg-white border rounded px-3 py-1 shadow-sm text-center">
                                    <span class="text-muted d-block" style="font-size: 0.55rem; font-weight:700; text-transform:uppercase;">DK Proj</span>
                                    <span class="text-dark fw-bold" style="font-size: 1rem;">${dkProjectionValue}</span>
                                </div>
                                <div class="bg-white border rounded px-3 py-1 shadow-sm text-center">
                                    <span class="text-muted d-block" style="font-size: 0.55rem; font-weight:700; text-transform:uppercase;">FD Proj</span>
                                    <span class="text-dark fw-bold" style="font-size: 1rem;">${fdProjectionValue}</span>
                                </div>
                            </div>
                        </div>
                    </div>`;
                }

                // Identify if Pitcher by checking deepStats OR the baked-in Python header
                const isPitcher = pDeepStats.is_pitcher === true || metaSub.includes("Pitcher");
                const splitR = pDeepStats.split_vR || {};
                const splitL = pDeepStats.split_vL || {};
                const isAway = teamSide === 'away';
                
                if (!isPitcher) {
                    let hitHrRate = 0; 
                    const oppHand = myGame.lineupHandedness ? myGame.lineupHandedness[oppPitcherId] : 'R';
                    
                    if (oppHand === 'R') {
                        hitHrRate = (Number(splitR.ab) > 0) ? (Number(splitR.hr) || 0) / Number(splitR.ab) : 0;
                    } else if (oppHand === 'L') {
                        hitHrRate = (Number(splitL.ab) > 0) ? (Number(splitL.hr) || 0) / Number(splitL.ab) : 0;
                    } else {
                        const tHr = (Number(splitR.hr) || 0) + (Number(splitL.hr) || 0);
                        const tAb = (Number(splitR.ab) || 0) + (Number(splitL.ab) || 0);
                        hitHrRate = tAb > 0 ? tHr / tAb : 0;
                    }

                    let baseScore = (Math.max(hitHrRate, 0.01) / 0.03) * 10.0;
                    if (myGame.parkStats) {
                        const rawFactor = isAway ? (myGame.parkStats.hr_l || 100) : (myGame.parkStats.hr_r || 100);
                        baseScore = baseScore * (rawFactor / 100);
                    }

                    let ratingLabel = "AVERAGE";
                    let barColorClass = "bg-primary";
                    let progressPct = 0;
                    
                    if (baseScore <= 10.0) {
                        progressPct = (baseScore / 10.0) * 33.33;
                    } else if (baseScore <= 15.0) {
                        progressPct = 33.33 + ((baseScore - 10.0) / 5.0) * 33.33;
                    } else {
                        progressPct = 66.66 + ((baseScore - 15.0) / 10.0) * 33.33;
                    }
                    progressPct = Math.min(Math.max(progressPct, 10), 100);

                    if (baseScore >= 25.0) { ratingLabel = "ELITE"; barColorClass = "bg-danger text-white"; }
                    else if (baseScore >= 15.0) { ratingLabel = "GOOD"; barColorClass = "bg-success text-white"; }
                    else if (baseScore < 5.0) { ratingLabel = "LOW"; barColorClass = "bg-secondary text-white"; }

                    hrZone.innerHTML = `
                    <div class="border rounded p-3 bg-white shadow-sm mb-2">
                        <div class="d-flex justify-content-between align-items-center border-bottom pb-2 mb-2">
                            <div class="d-flex align-items-center gap-2">
                                <span class="fw-bold text-dark" style="font-size: 0.85rem;">🚀 Home Run Power Predictor</span>
                                <span class="badge ${barColorClass} fw-bold" style="font-size: 0.65rem;">${ratingLabel}</span>
                            </div>
                            <span class="badge bg-dark fw-bold shadow-sm" style="font-size:0.8rem; padding: 4px 8px;">HR Score: ${baseScore.toFixed(1)}</span>
                        </div>
                        <div class="w-100">
                            <div class="progress rounded-pill" style="height: 12px; background-color: #e9ecef;">
                                <div class="progress-bar progress-bar-striped progress-bar-animated ${barColorClass}" role="progressbar" style="width: ${progressPct}%;" aria-valuenow="${progressPct}" aria-valuemin="0" aria-valuemax="100"></div>
                            </div>
                            <div class="d-flex justify-content-between text-muted px-1 mt-1 font-monospace" style="font-size: 0.6rem;">
                                <span>Low (< 5.0)</span><span>Average (10.0)</span><span>Good (15.0+)</span><span>Elite (25.0+)</span>
                            </div>
                        </div>
                    </div>`;
                    
                    const bvp = pDeepStats.bvp || {};
                    if (bvp && bvp.ab > 0) {
                        bvpZone.innerHTML = `
                        <div class="border rounded p-3 bg-white shadow-sm mb-2">
                            <div class="fw-bold text-dark border-bottom pb-2 mb-2 d-flex justify-content-between align-items-center" style="font-size: 0.85rem;">
                                <span>⚔️ Lifetime Matchup Analysis</span>
                                <span class="badge bg-primary">vs. ${oppPitcherName}</span>
                            </div>
                            <div class="row text-center g-2 pt-1">
                                <div class="col-3 border-end"><span class="text-muted d-block" style="font-size: 0.6rem; font-weight:700;">AT BATS</span><strong class="text-dark">${bvp.ab}</strong></div>
                                <div class="col-3 border-end"><span class="text-muted d-block" style="font-size: 0.6rem; font-weight:700;">HITS</span><strong class="text-dark">${bvp.hits}</strong></div>
                                <div class="col-3 border-end"><span class="text-muted d-block" style="font-size: 0.6rem; font-weight:700;">HOME RUNS</span><strong class="text-dark">${bvp.hr}</strong></div>
                                <div class="col-3"><span class="text-muted d-block; font-size: 0.6rem; font-weight:700;">OPS</span><strong class="text-success">${bvp.ops}</strong></div>
                            </div>
                        </div>`;
                    } else {
                        bvpZone.innerHTML = `
                        <div class="border rounded p-2 text-center text-muted fst-italic bg-white shadow-sm mb-2" style="font-size: 0.8rem;">
                            🚫 Potential Matchup: No previous history recorded against starting pitcher <strong>${oppPitcherName}</strong>.
                        </div>`;
                    }
                } else {
                    const totalHr = (Number(splitL.hr) || 0) + (Number(splitR.hr) || 0);
                    const totalAb = (Number(splitL.ab) || 0) + (Number(splitR.ab) || 0);
                    const pitchHrRate = totalAb > 0 ? (totalHr / totalAb) : 0;

                    let baseDangerScore = (Math.max(pitchHrRate, 0.01) / 0.03) * 10.0;
                    if (myGame.parkStats) {
                        const rawFactor = ((myGame.parkStats.hr_l || 100) + (myGame.parkStats.hr_r || 100)) / 2;
                        baseDangerScore = baseDangerScore * (rawFactor / 100);
                    }

                    let ratingLabel = "AVERAGE";
                    let barColorClass = "bg-warning text-dark"; 
                    let progressPct = 0;
                    
                    if (baseDangerScore <= 10.0) {
                        progressPct = (baseDangerScore / 10.0) * 33.33;
                    } else if (baseDangerScore <= 18.0) {
                        progressPct = 33.33 + ((baseDangerScore - 10.0) / 8.0) * 33.33;
                    } else {
                        progressPct = 66.66 + ((baseDangerScore - 18.0) / 7.0) * 33.33;
                    }
                    progressPct = Math.min(Math.max(progressPct, 10), 100);

                    if (baseDangerScore >= 18.0) { ratingLabel = "DANGEROUS"; barColorClass = "bg-danger text-white"; }
                    else if (baseDangerScore < 10.0) { ratingLabel = "SAFE"; barColorClass = "bg-success text-white"; }

                    hrZone.innerHTML = `
                    <div class="border rounded p-3 bg-white shadow-sm mb-2">
                        <div class="d-flex justify-content-between align-items-center border-bottom pb-2 mb-2">
                            <div class="d-flex align-items-center gap-2">
                                <span class="fw-bold text-dark" style="font-size: 0.85rem;">🛡️ HR Suppression Gauge</span>
                                <span class="badge ${barColorClass} fw-bold" style="font-size: 0.65rem;">${ratingLabel}</span>
                            </div>
                            <span class="badge bg-dark fw-bold shadow-sm" style="font-size:0.8rem; padding: 4px 8px;">Danger Score: ${baseDangerScore.toFixed(1)}</span>
                        </div>
                        <div class="w-100">
                            <div class="progress rounded-pill" style="height: 12px; background-color: #e9ecef;">
                                <div class="progress-bar progress-bar-striped progress-bar-animated ${barColorClass}" role="progressbar" style="width: ${progressPct}%;" aria-valuenow="${progressPct}" aria-valuemin="0" aria-valuemax="100"></div>
                            </div>
                            <div class="d-flex justify-content-between text-muted px-1 mt-1 font-monospace" style="font-size: 0.6rem;">
                                <span>Safe (< 10.0)</span><span>Average</span><span>Dangerous (18.0+)</span>
                            </div>
                        </div>
                    </div>`;

                    let orderList = myGame.lineupTracking?.[oppSide]?.hash ? myGame.lineupTracking[oppSide].hash.split('-') : [];
                    if (orderList.length === 0) {
                        orderList = (myGame.projectedLineups?.[oppSide]?.battingOrder || []).map(p => String(p.id));
                    }

                    let tableRowsHtml = '';
                    let historyCount = 0;

                    orderList.forEach((batterId, idx) => {
                        const batterStats = myGame.deepStats[batterId] || {};
                        const bvp = batterStats.bvp || {};
                        const batterName = batterStats.name || myGame.projectedLineups?.[oppSide]?.battingOrder?.find(p => String(p.id) === batterId)?.name || `Batter #${idx+1}`;

                        if (bvp && bvp.ab > 0) {
                            historyCount++;
                            tableRowsHtml += `
                            <tr>
                                <td class="text-start fw-semibold">${idx + 1}. ${batterName}</td>
                                <td><strong>${bvp.ab}</strong></td>
                                <td>${bvp.hits}</td>
                                <td>${bvp.hr}</td>
                                <td class="text-success fw-bold">${bvp.ops}</td>
                            </tr>`;
                        } else {
                            tableRowsHtml += `
                            <tr>
                                <td class="text-start text-muted">${idx + 1}. ${batterName}</td>
                                <td colspan="4" class="text-muted fst-italic text-center" style="font-size: 0.7rem;">No historic matchups recorded</td>
                            </tr>`;
                        }
                    });

                    const oppTeamName = gameRaw.teams?.[oppSide]?.teamName || "Opponent";

                    bvpZone.innerHTML = `
                    <div class="card shadow-sm border rounded overflow-hidden mb-2">
                        <div class="card-header bg-primary text-white py-2 d-flex justify-content-between align-items-center">
                            <h6 class="mb-0 fw-bold" style="font-size: 0.8rem;">⚔️ Head-to-Head vs Opposing ${oppTeamName} Lineup</h6>
                            <span class="badge bg-light text-primary fw-bold" style="font-size:0.65rem;">${historyCount} Bats Tracked</span>
                        </div>
                        <div class="table-responsive">
                            <table class="table table-striped text-center align-middle mb-0" style="font-size:0.75rem; min-width: 450px;">
                                <thead class="table-light text-secondary font-weight-bold">
                                    <tr>
                                        <th class="text-start ps-2">Lineup Position & Batter</th>
                                        <th>AB</th>
                                        <th>H</th>
                                        <th>HR</th>
                                        <th>Lifetime OPS</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${tableRowsHtml}
                                </tbody>
                            </table>
                        </div>
                    </div>`;
                }
            } else {
                safeHtml('live-game-state-label', `<strong>Game Status:</strong> Not on Today's Active Slate`);
                document.getElementById('badge-matrix-zone').innerHTML = `<div class="badge status-badge-scratched p-2 w-100 shadow-sm text-uppercase">✕ NO GAME SCHEDULED</div>`;
                document.getElementById('bvp-cards-container').innerHTML = `<div class="border rounded p-3 text-center text-muted fst-italic bg-white shadow-sm" style="font-size: 0.8rem;">🚫 No active matchup setup for today's slate.</div>`;
            }
        }
    } catch(e) { console.error("Error evaluating live tracking loops.", e); }
}

window.addEventListener('DOMContentLoaded', loadPlayerProfileData);
