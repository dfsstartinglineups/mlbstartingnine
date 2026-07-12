// Global Player Rendering Engine - MLB Starting Nine

const safeText = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };
const safeHtml = (id, html) => { const el = document.getElementById(id); if (el) el.innerHTML = html; };

function getTargetSlateDate() {
    const now = new Date();
    const estStr = now.toLocaleString("en-US", { timeZone: "America/New_York" });
    const estDate = new Date(estStr);
    if (estDate.getHours() < 7) { estDate.setDate(estDate.getDate() - 1); }
    const yyyy = estDate.getFullYear();
    const mm = String(estDate.getMonth() + 1).padStart(2, '0');
    const dd = String(estDate.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
}

async function loadPlayerProfileData() {
    if (typeof PLAYER_ID === 'undefined') {
        console.error("Core Error: PLAYER_ID token missing from static index configuration.");
        return;
    }

    const targetDateStr = getTargetSlateDate();
    let masterDataProfile = null;

    // ==========================================
    // STEP 1: INITIALIZE STABLE MASTER CORES
    // ==========================================
    try {
        const masterRes = await fetch(`https://mlbstartingnine.com/data/player_master_data.json`);
        if (masterRes.ok) {
            const masterRegistry = await masterRes.json();
            masterDataProfile = masterRegistry["ID" + PLAYER_ID];
            if (masterDataProfile) {
                if (masterDataProfile.is_pitcher) {
                    const wins = masterDataProfile.season?.w !== undefined ? masterDataProfile.season.w : 0;
                    const losses = masterDataProfile.season?.l !== undefined ? masterDataProfile.season.l : 0;
                    const era = masterDataProfile.season?.era || '-';
                    
                    safeText('player-meta-sub', `Pitcher • ${wins}-${losses} • ${era} ERA`);
                    safeHtml('split-vl-header', `<span class="badge bg-secondary me-1">LHB</span> vs. Left-Handed Batters`);
                    safeHtml('split-vr-header', `<span class="badge bg-dark me-1">RHB</span> vs. Right-Handed Batters`);
                    safeText('split-vl-label-volume', "Batters Faced:");
                    safeText('split-vr-label-volume', "Batters Faced:");
                    safeText('split-vl-label-hr', "HR Allowed:");
                    safeText('split-vr-label-hr', "HR Allowed:");
                } else {
                    const avg = masterDataProfile.season?.avg || '-';
                    const hr = masterDataProfile.season?.hr ?? 0;
                    safeText('player-meta-sub', `Position Player • ${avg} AVG • ${hr} HR`);
                }
                
                const vl = masterDataProfile.split_vL || {};
                const vr = masterDataProfile.split_vR || {};
                safeText('split-vl-vol', vl.ab || 0); safeText('split-vl-avg', vl.avg || '-');
                safeText('split-vl-ops', vl.ops || '-'); safeText('split-vl-hr', vl.hr || 0);
                safeText('split-vr-vol', vr.ab || 0); safeText('split-vr-avg', vr.avg || '-');
                safeText('split-vr-ops', vr.ops || '-'); safeText('split-vr-hr', vr.hr || 0);

                const logs = masterDataProfile.game_log || [];
                const logTableBody = document.getElementById('game-historical-tbody');
                if (logTableBody) {
                    if (logs.length > 0) {
                        logTableBody.innerHTML = logs.map(log => `
                            <tr>
                                <td class="text-start ps-3 fw-bold">${log.date}</td>
                                <td>${log.summary}</td>
                                <td class="dk-accent">${typeof log.dk_pts === 'number' ? log.dk_pts.toFixed(2) : log.dk_pts}</td>
                                <td class="fd-accent">${typeof log.fd_pts === 'number' ? log.fd_pts.toFixed(1) : log.fd_pts}</td>
                            </tr>
                        `).join('');
                    } else {
                        logTableBody.innerHTML = `<tr><td colspan="4" class="text-center p-3 text-muted">No recent history logged.</td></tr>`;
                    }
                }
            }
        }
    } catch(e) { console.error("Error loading master logs dictionary.", e); }

    // ==========================================
    // STEP 2: LOOKUP TODAY'S ACTION MATRIX FILES
    // ==========================================
    try {
        const dailyRes = await fetch(`https://mlbstartingnine.com/data/daily_files/games_${targetDateStr}.json`);
        const liveRes = await fetch(`https://mlbstartingnine.com/data/LIVE/live_mlb_${targetDateStr}.json?v=` + Date.now()).catch(() => ({ ok: false }));
        
        if (dailyRes.ok) {
            const dailyData = await dailyRes.json();
            const liveData = liveRes.ok ? await liveRes.json() : {};
            
            let activeMatchNodes = [];
            
            (dailyData.games || []).forEach(game => {
                const deepStats = game.deepStats || {};
                if (deepStats[PLAYER_ID]) { activeMatchNodes.push(game); }
            });

            if (activeMatchNodes.length > 0) {
                const badgeZone = document.getElementById('badge-matrix-zone');
                const bvpZone = document.getElementById('bvp-cards-container');
                const liveConsoleZone = document.getElementById('live-consoles-container');
                const hrZone = document.getElementById('hr-predictor-container');
                
                badgeZone.innerHTML = ''; bvpZone.innerHTML = ''; liveConsoleZone.innerHTML = ''; hrZone.innerHTML = '';
                let globalGameStatusStrings = [];

                activeMatchNodes.forEach((game) => {
                    const gameRaw = game.gameRaw || {};
                    const gamePk = String(gameRaw.gamePk);
                    const gameNum = gameRaw.gameNumber || 1;
                    const labelPrefix = activeMatchNodes.length > 1 ? `G${gameNum}: ` : '';
                    
                    const awayLineup = gameRaw.lineups?.awayPlayers || [];
                    const awayProj = game.projectedLineups?.away?.battingOrder || [];
                    const awayProjP = game.projectedLineups?.away?.startingPitcher || {};
                    const awayOffP = gameRaw.teams?.away?.probablePitcher || {};

                    let isAway = false;
                    if (
                        awayLineup.some(p => String(p.id) === PLAYER_ID) ||
                        awayProj.some(p => String(p.id) === PLAYER_ID) ||
                        String(awayProjP.id) === PLAYER_ID ||
                        String(awayOffP.id) === PLAYER_ID
                    ) { isAway = true; }
                    
                    const teamSide = isAway ? "away" : "home";
                    const oppSide = isAway ? "home" : "away";
                    const sideLabelUpper = isAway ? "AWAY" : "HOME";
                    
                    const tracking = game.lineupTracking || {};
                    const trackingNode = tracking[teamSide] || {};
                    const oppPitcherName = gameRaw.teams?.[oppSide]?.probablePitcher?.fullName || "TBD";
                    
                    // Batting Order Position Math
                    let isConfirmed = trackingNode.status === "OFFICIAL";
                    let slotIndex = -1;
                    
                    if (isConfirmed && trackingNode.hash) {
                        slotIndex = trackingNode.hash.split('-').indexOf(PLAYER_ID);
                    }
                    if (slotIndex === -1) {
                        const projectedList = game.projectedLineups?.[teamSide]?.battingOrder || [];
                        slotIndex = projectedList.findIndex(p => String(p.id) === PLAYER_ID);
                    }

                    // Construct Badge UI Cores
                    let badgeHtml = '';
                    const isStartingPitcher = String(gameRaw.teams?.[teamSide]?.probablePitcher?.id) === PLAYER_ID || 
                                              String(game.projectedLineups?.[teamSide]?.startingPitcher?.id) === PLAYER_ID;

                    if (isStartingPitcher) {
                        badgeHtml = `<div class="badge status-badge-confirmed p-2 w-100 shadow-sm text-uppercase">${labelPrefix}Starting Pitcher</div>`;
                    } else {
                        if (isConfirmed && slotIndex !== -1) {
                            badgeHtml = `<div class="badge status-badge-confirmed p-2 w-100 shadow-sm text-uppercase">${labelPrefix}Batting #${slotIndex + 1}</div>`;
                        } else if (slotIndex !== -1) {
                            badgeHtml = `<div class="badge status-badge-projected p-2 w-100 shadow-sm text-uppercase text-dark">${labelPrefix}Projected #${slotIndex + 1}</div>`;
                        } else {
                            badgeHtml = `<div class="badge status-badge-scratched p-2 w-100 shadow-sm text-uppercase">${labelPrefix}Not Projected to Start</div>`;
                        }
                    }
                    badgeZone.innerHTML += badgeHtml;

                    // Compile Real-Time Match Data Loops
                    const activeLiveGame = liveData[gamePk];
                    if (activeLiveGame) {
                        if (activeLiveGame.status === "Final") {
                            globalGameStatusStrings.push(`${labelPrefix}Final`);
                        } else {
                            globalGameStatusStrings.push(`${labelPrefix}${activeLiveGame.half || ''} ${activeLiveGame.inning ? activeLiveGame.inning.replace(/\D/g, '') : ''}`);
                        }

                        const playerBox = activeLiveGame.players?.[sideLabelUpper]?.[`ID${PLAYER_ID}`];
                        const profile = playerBox?.batting || playerBox?.pitching;
                        
                        if (playerBox && profile?.summary) {
                            liveConsoleZone.innerHTML += `
                            <div class="p-3 border-bottom" style="background-color: #edf4f8;">
                                <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
                                    <div>
                                        <span class="badge bg-primary text-uppercase me-2" style="font-size:0.65rem;">${labelPrefix}Box Score</span>
                                        <strong class="text-dark" style="font-size: 0.9rem;">${profile.summary}</strong>
                                    </div>
                                    <div class="d-flex align-items-center gap-3">
                                        <div class="bg-white border rounded px-3 py-1 shadow-sm text-center">
                                            <span class="text-muted d-block" style="font-size: 0.55rem; font-weight:700;">DK Pts</span>
                                            <span class="dk-accent" style="font-size: 1rem;">${playerBox.dk_pts.toFixed(1)}</span>
                                        </div>
                                        <div class="bg-white border rounded px-3 py-1 shadow-sm text-center">
                                            <span class="text-muted d-block" style="font-size: 0.55rem; font-weight:700;">FD Pts</span>
                                            <span class="fd-accent" style="font-size: 1rem;">${playerBox.fd_pts.toFixed(1)}</span>
                                        </div>
                                    </div>
                                </div>
                            </div>`;
                        }
                    } else { globalGameStatusStrings.push(`${labelPrefix}Scheduled`); }

                    // DYNAMIC HR PREDICTOR DATA ENGINE
                    if (masterDataProfile && !masterDataProfile.is_pitcher) {
                        // Access your unique main page formula calculation variables out of the daily payload nodes
                        const pDeepStats = game.deepStats[PLAYER_ID] || {};
                        const pitcherDeepStats = game.deepStats[String(gameRaw.teams?.[oppSide]?.probablePitcher?.id)] || {};
                        
                        let baseScore = 10.0; // Default League Baseline Context Matchup 
                        
                        // Calculate dynamically using your main script formula variables if populated
                        if (pDeepStats.split_vR && game.lineupHandedness?.[String(gameRaw.teams?.[oppSide]?.probablePitcher?.id)] === 'R') {
                            baseScore += (pDeepStats.split_vR.hr || 0) * 0.8;
                        } else if (pDeepStats.split_vL) {
                            baseScore += (pDeepStats.split_vL.hr || 0) * 0.8;
                        }
                        
                        if (game.parkStats) {
                            const hrFactor = isAway ? (game.parkStats.hr_l || 1.0) : (game.parkStats.hr_r || 1.0);
                            baseScore = baseScore * hrFactor;
                        }

                        // Set display configurations matching thresholds
                        let ratingLabel = "AVERAGE MATCHUP";
                        let barColorClass = "bg-primary";
                        let progressPct = Math.min(Math.max((baseScore / 35.0) * 100, 15), 100);

                        if (baseScore >= 22.0) { ratingLabel = "ELITE POWER PLAY"; barColorClass = "bg-danger text-white"; }
                        else if (baseScore >= 14.0) { ratingLabel = "HIGH PROBABILITY"; barColorClass = "bg-success text-white"; }
                        else if (baseScore < 6.0) { ratingLabel = "LOW PROBABILITY"; barColorClass = "bg-secondary text-white"; }

                        hrZone.innerHTML += `
                        <div class="border rounded p-3 bg-white shadow-sm mb-2">
                            <div class="d-flex justify-content-between align-items-center border-bottom pb-2 mb-2">
                                <div class="d-flex align-items-center gap-2">
                                    <span class="fw-bold text-dark" style="font-size: 0.85rem;">🚀 ${labelPrefix}Home Run Power Predictor</span>
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
                    }

                    // BvP Layout Render Block
                    const pDeepStats = game.deepStats[PLAYER_ID] || {};
                    const bvp = pDeepStats.bvp || {};
                    
                    if (bvp && bvp.ab > 0) {
                        bvpZone.innerHTML += `
                        <div class="border rounded p-3 bg-white shadow-sm mb-2">
                            <div class="fw-bold text-dark border-bottom pb-2 mb-2 d-flex justify-content-between align-items-center" style="font-size: 0.85rem;">
                                <span>⚔️ ${labelPrefix}Lifetime Matchup Analysis</span>
                                <span class="badge bg-primary">vs. ${oppPitcherName}</span>
                            </div>
                            <div class="row text-center g-2 pt-1">
                                <div class="col-3 border-end"><span class="text-muted d-block" style="font-size: 0.6rem; font-weight:700;">AT BATS</span><strong class="text-dark">${bvp.ab}</strong></div>
                                <div class="col-3 border-end"><span class="text-muted d-block" style="font-size: 0.6rem; font-weight:700;">HITS</span><strong class="text-dark">${bvp.hits}</strong></div>
                                <div class="col-3 border-end"><span class="text-muted d-block" style="font-size: 0.6rem; font-weight:700;">HOME RUNS</span><strong class="text-dark">${bvp.hr}</strong></div>
                                <div class="col-3"><span class="text-muted d-block" style="font-size: 0.6rem; font-weight:700;">OPS</span><strong class="text-success">${bvp.ops}</strong></div>
                            </div>
                        </div>`;
                    } else {
                        bvpZone.innerHTML += `
                        <div class="border rounded p-2 text-center text-muted fst-italic bg-white shadow-sm mb-2" style="font-size: 0.8rem;">
                            🚫 ${labelPrefix}No previous history recorded against starting pitcher <strong>${oppPitcherName}</strong>.
                        </div>`;
                    }
                });

                safeHtml('live-game-state-label', `<strong>Game Status:</strong> ${globalGameStatusStrings.join(' | ')}`);
            } else {
                safeHtml('bvp-cards-container', `<div class="border rounded p-3 text-center text-muted fst-italic bg-white shadow-sm" style="font-size: 0.8rem;">🚫 No active matchup setup or lifetime history verified against today's starting pitcher.</div>`);
            }
        }
    } catch(e) { console.error("Error evaluating live tracking loops.", e); }
}

window.addEventListener('DOMContentLoaded', loadPlayerProfileData);
