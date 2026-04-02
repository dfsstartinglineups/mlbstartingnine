// ==========================================
// CONFIGURATION
// ==========================================
const DEFAULT_DATE = new Date().toLocaleDateString('en-CA');
let ALL_GAMES_DATA = []; 
let GLOBAL_SLATES = { fanduel: [], draftkings: [] }; 

let savedLineupState = localStorage.getItem('futbolLineupsExpanded');
let globalLineupsExpanded = savedLineupState !== null ? savedLineupState === 'true' : true;

const X_SVG_PATH = "M12.6.75h2.454l-5.36 6.142L16 15.25h-4.937l-3.867-5.07-4.425 5.07H.316l5.733-6.57L0 .75h5.063l3.495 4.633L12.601.75Zm-.86 13.028h1.36L4.323 2.145H2.865l8.875 11.633Z";

// --- CSS INJECTIONS FOR LEADERBOARD & CONTROLS ---
const style = document.createElement('style');
style.innerHTML = `
    .leaderboard-tab {
        font-size: 0.7rem; font-weight: 700; color: #adb5bd; cursor: pointer;
        padding: 8px 0; text-align: center; text-transform: uppercase; letter-spacing: 0.5px;
        border-bottom: 2px solid transparent; transition: all 0.2s ease;
    }
    .leaderboard-tab.active { color: #0d6efd; border-bottom: 2px solid #0d6efd; }
    .leaderboard-tab:hover:not(.active) { color: #495057; }
    .list-view::-webkit-scrollbar { width: 4px; }
    .list-view::-webkit-scrollbar-thumb { background-color: #dee2e6; border-radius: 4px; }
    
    .dk-btn-label { color: #6c9d2f; border-color: #6c9d2f; background-color: #fff; }
    .dk-btn-label:hover { color: #fff; background-color: #6c9d2f; border-color: #6c9d2f; }
    .btn-check:checked + .dk-btn-label { background-color: #6c9d2f !important; border-color: #6c9d2f !important; color: #fff !important; }

    /* NEW POSITIONAL BUTTON STYLES */
    .pos-filter-btn { font-size: 0.65rem; font-weight: 700; padding: 3px 10px; border-radius: 12px; border: 1px solid #dee2e6; color: #6c757d; background: #fff; cursor: pointer; transition: all 0.2s; white-space: nowrap; }
    .pos-filter-btn:hover { background: #e9ecef; }
    .pos-filter-btn.active { background: #343a40; color: #fff; border-color: #343a40; }
    .hide-scrollbar::-webkit-scrollbar { display: none; }
    .hide-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
`;
document.head.appendChild(style);

// NEW GLOBALS FOR TOP PLAYS & LIVE DATA
window.TOP_PLAYS_DATA = null;
window.CURRENT_TOP_PLAYS_POS = 'ALL';
let LIVE_GAMES_DATA = {};
let livePollInterval;

// ==========================================
// 1. DEEP LINK SCROLLING
// ==========================================
function handleHashNavigation() {
    if (window.location.hash) {
        setTimeout(() => {
            const targetId = window.location.hash.substring(1);
            const targetCard = document.getElementById(targetId);
            
            if (targetCard) {
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

// ==========================================
// 2. DATA FETCHING & SLATE HELPERS
// ==========================================
async function pollLiveData(dateToFetch) {
    try {
        const response = await fetch(`data/LIVE/live_mlb_${dateToFetch}.json?v=` + new Date().getTime(), { cache: 'no-store' });
        if (response.ok) {
            LIVE_GAMES_DATA = await response.json();
        } else {
            LIVE_GAMES_DATA = {}; // Clear if file doesn't exist (e.g., future dates)
        }
        // Re-render the Top Plays list silently to update the checkmarks
        if (window.CURRENT_TOP_PLAYS_POS) window.updateTopPlaysView(); 
    } catch (e) {
        LIVE_GAMES_DATA = {}; // Clear on network error
        if (window.CURRENT_TOP_PLAYS_POS) window.updateTopPlaysView();
        console.log("Live MLB data not available yet.");
    }
}

function ensureDFSControls() {
    if (!document.getElementById('dfs-controls-row')) {
        const container = document.getElementById('games-container');
        if (container && container.parentNode) {
            const controlsHtml = `
                <div id="dfs-controls-row" class="w-100 d-flex align-items-center mb-3 gap-2 px-2">
                    <div class="btn-group shadow-sm flex-shrink-0" role="group">
                        <input type="radio" class="btn-check dfs-toggle" name="dfsPlatform" id="btn-fd" value="fd" checked>
                        <label class="btn btn-outline-primary fw-bold px-3 py-1" for="btn-fd" style="font-size: 0.85rem;">FD</label>
                        
                        <input type="radio" class="btn-check dfs-toggle" name="dfsPlatform" id="btn-dk" value="dk">
                        <label class="btn fw-bold px-3 py-1 dk-btn-label" for="btn-dk" style="font-size: 0.85rem;">DK</label>
                    </div>
                    <select id="slate-selector" class="form-select form-select-sm fw-bold shadow-sm" style="width: auto; min-width: 180px; cursor: pointer; font-size: 0.85rem; border-color: #ced4da; color: #212529;">
                        <option value="all">All Slates</option>
                    </select>
                </div>
            `;
            container.insertAdjacentHTML('beforebegin', controlsHtml);
            
            document.querySelectorAll('.dfs-toggle').forEach(radio => radio.addEventListener('change', () => {
                populateSlates();
                renderGames();
            }));
            document.getElementById('slate-selector').addEventListener('change', renderGames);
        }
    }
}

function populateSlates() {
    const platformNode = document.querySelector('input[name="dfsPlatform"]:checked');
    const platform = platformNode ? platformNode.value : 'fd';
    const platKey = platform === 'dk' ? 'draftkings' : 'fanduel';
    
    const selector = document.getElementById('slate-selector');
    if (!selector) return;
    
    const currentVal = selector.value;
    selector.innerHTML = '<option value="all">All Slates</option>';
    
    const datePicker = document.getElementById('date-picker');
    const dateToFetch = datePicker ? datePicker.value : DEFAULT_DATE;
    
    let dateObj = new Date();
    if (dateToFetch && dateToFetch.includes('-')) {
        const [y, m, d] = dateToFetch.split('-');
        dateObj = new Date(y, m - 1, d);
    }
    const dayOfWeek = dateObj.toLocaleDateString('en-US', { weekday: 'short' }).toUpperCase();

    if (GLOBAL_SLATES[platKey] && Array.isArray(GLOBAL_SLATES[platKey])) {
        GLOBAL_SLATES[platKey].forEach(slate => {
            const upperName = slate.name.toUpperCase();
            const days = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];
            const containsADay = days.some(day => upperName.includes(day));
            
            if (upperName.includes(dayOfWeek) || !containsADay) {
                const opt = document.createElement('option');
                opt.value = slate.id;
                opt.textContent = slate.name;
                selector.appendChild(opt);
            }
        });
    }
    
    if(Array.from(selector.options).some(opt => opt.value === currentVal)) selector.value = currentVal;
    else selector.value = 'all';
}

function hasSlatePlayers(game, platform, selectedSlate) {
    if (selectedSlate === 'all') return true; 
    const checkRoster = (players) => {
        if (!players) return false;
        return players.some(p => {
            if (!p) return false;
            const slatesDict = platform === 'dk' ? (p.dk_slates || {}) : (p.fd_slates || {});
            return !!slatesDict[selectedSlate];
        });
    };
    
    const pl = game.projectedLineups || {};
    return checkRoster([pl.away?.startingPitcher]) || checkRoster(pl.away?.battingOrder) || 
           checkRoster([pl.home?.startingPitcher]) || checkRoster(pl.home?.battingOrder);
}

function hasAnyDfsSalaries(game, platform) {
    const checkRoster = (players) => {
        if (!players) return false;
        return players.some(p => {
            if (!p) return false;
            return (platform === 'dk' ? (p.dk_salary || 0) : (p.salary || 0)) > 0;
        });
    };
    const pl = game.projectedLineups || {};
    return checkRoster([pl.away?.startingPitcher]) || checkRoster(pl.away?.battingOrder) || 
           checkRoster([pl.home?.startingPitcher]) || checkRoster(pl.home?.battingOrder);
}

async function init(dateToFetch, isSilentRefresh = false) {
    if (window.updatePageMetadata && !isSilentRefresh) window.updatePageMetadata(dateToFetch); 
    
    const container = document.getElementById('games-container');
    const datePicker = document.getElementById('date-picker');
    
    if (datePicker && !isSilentRefresh) datePicker.value = dateToFetch;

    // Only show the loading spinner if this is a manual/initial load, NOT a background refresh
    if (container && !isSilentRefresh) {
        ALL_GAMES_DATA = [];  // Clear old games
        LIVE_GAMES_DATA = {}; // Clear old live stats immediately

        container.innerHTML = `
            <div class="col-12 text-center mt-5 pt-5">
                <div class="spinner-border text-primary" role="status"></div>
                <p class="mt-3 text-muted fw-bold">Loading Pitch Data...</p>
            </div>`;
    }
    
    try {
        const response = await fetch(`data/daily_files/games_${dateToFetch}.json?v=` + new Date().getTime());
        if (!response.ok) throw new Error("Local JSON not found");
        
        const rawData = await response.json();

        if (Array.isArray(rawData)) {
            ALL_GAMES_DATA = rawData;
            if(!isSilentRefresh) GLOBAL_SLATES = { fanduel: [], draftkings: [] };
        } else {
            ALL_GAMES_DATA = rawData.games || [];
            if(!isSilentRefresh) GLOBAL_SLATES = rawData.slates || { fanduel: [], draftkings: [] };
        }

        if(!isSilentRefresh) {
            ensureDFSControls();
            populateSlates();
        }

    } catch (error) {
        console.log(`No local file for ${dateToFetch}. Falling back to live API...`);
        try {
            const [year, month, day] = dateToFetch.split('-');
            const mlbApiDate = `${month}/${day}/${year}`;
            const mlbRes = await fetch(`https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=${mlbApiDate}&hydrate=probablePitcher,lineups`);
            if (!mlbRes.ok) throw new Error("MLB API Failed");
            
            const mlbData = await mlbRes.json();
            if (mlbData.dates && mlbData.dates.length > 0) {
                ALL_GAMES_DATA = mlbData.dates[0].games.map(game => {
                    return { gameRaw: game, lineupHandedness: {}, deepStats: {}, parkStats: null, hpUmpire: "TBD", umpStats: null };
                });
            }
            if(!isSilentRefresh) {
                ensureDFSControls();
                populateSlates();
            }
        } catch (fallbackError) {
            if (container && !isSilentRefresh) container.innerHTML = `<div class="col-12 text-center mt-5"><div class="alert alert-light border shadow-sm py-4"><h5 class="text-muted mb-0">Schedule pending for ${dateToFetch}</h5></div></div>`;
            return;
        }
    }

    if (ALL_GAMES_DATA.length === 0 && !isSilentRefresh) {
        container.innerHTML = `<div class="col-12 text-center mt-5"><div class="alert alert-light border shadow-sm py-4"><h5 class="text-muted mb-0">No games scheduled for ${dateToFetch}</h5></div></div>`;
        return;
    }

    // PASS THE FLAG HERE
    renderGames(isSilentRefresh); 
    
    // --- NEW: START LIVE POLLER ---
    if (!isSilentRefresh) {
        pollLiveData(dateToFetch);
        clearInterval(livePollInterval);
        livePollInterval = setInterval(() => pollLiveData(dateToFetch), 30000);
    }
    
    if (!isSilentRefresh) handleHashNavigation();
}

// ==========================================
// 3. LEADERBOARD BUILDERS
// ==========================================
window.setTopPlaysPos = function(el) {
    document.querySelectorAll('.pos-filter-btn').forEach(b => b.classList.remove('active'));
    el.classList.add('active');
    window.CURRENT_TOP_PLAYS_POS = el.getAttribute('data-pos');
    window.updateTopPlaysView();
};

window.setTopPlaysTab = function(el) {
    document.querySelectorAll('.leaderboard-tab').forEach(t => t.classList.remove('active'));
    el.classList.add('active');
    window.updateTopPlaysView();
};

window.updateTopPlaysView = function() {
    if (!window.TOP_PLAYS_DATA) return;

    const pos = window.CURRENT_TOP_PLAYS_POS || 'ALL';
    let tabEl = document.querySelector('.leaderboard-tab.active');
    let tab = tabEl ? tabEl.getAttribute('data-tab') : 'value';

    const bvpTab = document.querySelector('.leaderboard-tab[data-tab="bvp"]');
    const hrTab = document.querySelector('.leaderboard-tab[data-tab="hr"]');

    // 1. Quarantining Pitchers & Tabs
    if (pos === 'P') {
        if (bvpTab) bvpTab.style.display = 'none';
        if (hrTab) hrTab.style.display = 'none';
        if (tab === 'bvp' || tab === 'hr') {
            tab = 'value';
            document.querySelector('.leaderboard-tab[data-tab="value"]').classList.add('active');
            if (tabEl) tabEl.classList.remove('active');
        }
    } else {
        if (bvpTab) bvpTab.style.display = 'block';
        if (hrTab) hrTab.style.display = 'block';
    }

    const platform = window.TOP_PLAYS_DATA.platform;
    const posKey = platform === 'dk' ? 'dk_positions' : 'fd_positions';

    // 2. Select Source Array (Pitchers are permanently separated from ALL)
    let sourceArray = [];
    if (pos === 'P') {
        sourceArray = window.TOP_PLAYS_DATA.pitchers;
    } else {
        if (tab === 'value' || tab === 'proj') sourceArray = window.TOP_PLAYS_DATA.hitters;
        else if (tab === 'bvp') sourceArray = window.TOP_PLAYS_DATA.bvp;
        else if (tab === 'hr') sourceArray = window.TOP_PLAYS_DATA.hr;
    }

    // 3. Filter by Position
    let filtered = sourceArray;
    if (pos !== 'ALL' && pos !== 'P') {
        const targetPositions = pos.split('/'); 
        
        filtered = sourceArray.filter(p => {
            const pPos = p[posKey] || '';
            if (!pPos) return false;
            const playerPositions = pPos.split('/'); 
            return targetPositions.some(targetPos => playerPositions.includes(targetPos));
        });
    }

    // 4. Sort by Active Metric
    let sorted = [...filtered];
    if (tab === 'value') sorted.sort((a, b) => (b.value || 0) - (a.value || 0));
    else if (tab === 'proj') sorted.sort((a, b) => (b.proj || 0) - (a.proj || 0));
    else if (tab === 'bvp') sorted.sort((a, b) => parseFloat(b.bvp.ops || 0) - parseFloat(a.bvp.ops || 0));
    else if (tab === 'hr') sorted.sort((a, b) => (b.hrScore || 0) - (a.hrScore || 0));

    // 5. Render top 20
    const top20 = sorted.slice(0, 20);
    const listContainer = document.getElementById('view-top-plays-list');
    if (listContainer) listContainer.innerHTML = window.buildTopPlaysListHtml(top20, tab, platform);
};

window.buildTopPlaysListHtml = function(players, mode, platform) {
    if (players.length === 0) return `<div class="p-3 text-center text-muted fw-bold" style="font-size:0.8rem;">No players found for this selection.</div>`;
    const posKey = platform === 'dk' ? 'dk_positions' : 'fd_positions';

    return players.map((p, index) => {
        const photoHtml = `<img src="${p.photo}" style="width: 48px; height: 48px; border-radius: 50%; object-fit: cover; border: 1px solid #dee2e6; background: #fff;" onerror="this.onerror=null; this.src='data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iI2FkYjViZCI+PHBhdGggZD0iTTEyIDJDMi42NCAyIDIgNi42NCAyIDEyeiIvPjwvc3ZnPg==';">`;
        const teamBadge = p.teamLogo ? `<img src="${p.teamLogo}" style="width: 20px; height: 20px; position: absolute; bottom: -2px; right: -4px; border-radius: 50%; background: #fff; border: 1px solid #dee2e6; object-fit: contain; padding: 1px;">` : '';
        
        let shortName = p.name;
        if (shortName.includes(' ')) shortName = `${shortName.charAt(0)}. ${shortName.split(' ').slice(1).join(' ')}`;

        let tabSpecificHtml = '';
        let displayPos = p[posKey] || p.pos;

        // ==========================================
        // 1. FETCH LIVE DATA FOR THE PLAYER
        // ==========================================
        let livePlayer = null;
        let liveGame = null;
        let isGameFinal = false;
        const pidStr = `ID${p.id}`; 
        
        for (const [gameId, lGame] of Object.entries(LIVE_GAMES_DATA || {})) {
            const awayPlayers = lGame.players?.AWAY || {};
            const homePlayers = lGame.players?.HOME || {};
            const lPlayer = awayPlayers[pidStr] || homePlayers[pidStr];
            
            if (lPlayer) {
                livePlayer = lPlayer;
                liveGame = lGame;
                isGameFinal = (lGame.status === 'Final');
                break; // Stop searching once found
            }
        }

        // ==========================================
        // 2. BUILD GAME STATUS BADGE
        // ==========================================
        let gameStatusBadge = '';
        if (liveGame) {
            if (isGameFinal) {
                gameStatusBadge = `<span class="badge bg-secondary ms-2" style="font-size:0.55rem; padding: 0.25em 0.4em;">Final</span>`;
            } else if (liveGame.status === 'Live' || liveGame.status === 'In Progress' || liveGame.inning) {
                let halfMap = { 'Top': 'T', 'Bottom': 'B' };
                let half = halfMap[liveGame.half] || '';
                let inn = (liveGame.inning || '').replace(/\D/g, ''); 
                let score = `${liveGame.away_score}-${liveGame.home_score}`;
                if(inn || score !== '0-0') {
                     gameStatusBadge = `<span class="badge bg-success ms-2" style="font-size:0.55rem; padding: 0.25em 0.4em;">${half}${inn} ${score}</span>`;
                }
            }
        }

        // ==========================================
        // 3. BUILD TAB-SPECIFIC CONTENT
        // ==========================================
        if (mode === 'bvp') {
            let avg = p.bvp.avg;
            if (!avg || avg === "-" || avg === ".000") {
                if(p.bvp.ab > 0) {
                    let calcAvg = p.bvp.hits / p.bvp.ab;
                    avg = calcAvg.toFixed(3).replace('0.', '.');
                } else {
                    avg = ".000";
                }
            }
            
            let opsDisplay = parseFloat(p.bvp.ops).toFixed(3).replace('0.', '.');
            let p_shortName = p.oppPitcher;
            if (p_shortName.includes(' ') && !p_shortName.includes("(Proj)")) {
                p_shortName = `${p_shortName.split(' ')[0].charAt(0)}. ${p_shortName.split(' ').slice(1).join(' ')}`;
            }

            tabSpecificHtml = `
                <div class="d-flex justify-content-between align-items-center">
                    <div class="fw-bold text-dark text-truncate pe-2" style="font-size: 0.95rem;" title="${p.name}">${shortName}</div>
                    <div class="text-end fw-bold text-dark" style="font-size: 1.0rem;">${opsDisplay} <span class="text-muted" style="font-size:0.6rem;">OPS</span></div>
                </div>
                <div class="text-muted text-truncate w-100" style="font-size: 0.72rem; margin-top: -2px;">
                    v. ${p_shortName} • ${p.bvp.hits}-${p.bvp.ab} • ${avg} • ${p.bvp.hr} HR
                </div>
            `;
            
        } else if (mode === 'hr') {
            let p_shortName = p.oppPitcher;
            if (p_shortName.includes(' ') && !p_shortName.includes("(Proj)")) {
                p_shortName = `${p_shortName.split(' ')[0].charAt(0)}. ${p_shortName.split(' ').slice(1).join(' ')}`;
            }
            
            let hrIcon = '';
            if (livePlayer) {
                if (livePlayer.batting && livePlayer.batting.homeRuns > 0) {
                    hrIcon = `<span title="Hit a Home Run Today!">✅</span>`;
                } else if (isGameFinal) {
                    hrIcon = `<span style="opacity: 0.5;" title="Game Final - No HR">❌</span>`;
                }
            }
            
            let pitcherSplitHtml = '';
            if (p.oppPitcherSplit && p.oppPitcherSplit.ab > 0) {
                pitcherSplitHtml = `<span>${p_shortName} v${p.activeBatSide}: ${p.oppPitcherSplit.ab} ABs • ${p.oppPitcherSplit.hr} HR</span>`;
            } else {
                pitcherSplitHtml = `<span>${p_shortName} v${p.activeBatSide}: No History</span>`;
            }
            
            tabSpecificHtml = `
                <div class="d-flex justify-content-between align-items-center">
                    <div class="d-flex align-items-center pe-2" style="min-width: 0;">
                        <div class="fw-bold text-dark text-truncate" style="font-size: 0.95rem;" title="${p.name}">${shortName}</div>
                        ${gameStatusBadge}
                    </div>
                    <div class="text-end d-flex align-items-center h-100" style="font-size: 1.2rem; min-height: 20px;">${hrIcon}</div>
                </div>
                <div class="d-flex flex-column text-muted w-100" style="font-size: 0.70rem; line-height: 1.3; margin-top: -2px;">
                    <span>Batter v${p.oppHand}: ${p.split.ab} ABs • ${p.split.hr} HR</span>
                    ${pitcherSplitHtml}
                    <span>BvP: ${p.bvp.ab} ABs • ${p.bvp.hr} HR</span>
                </div>
            `;
            
        } else {
            // mode === 'value' OR 'proj'
            const isValue = mode === 'value';
            const salFmt = p.salary > 0 ? (p.salary / 1000).toFixed(1).replace('.0', '') + 'K' : '-';
            
            // --- ROW 1: Name, Pos/Sal, & Projected ---
            let topMetric = isValue 
                ? `<div class="text-success fw-bold" style="font-size: 0.95rem;">${parseFloat(p.value || 0).toFixed(2)}x <span class="text-muted fw-normal" style="font-size:0.6rem;">Proj</span></div>` 
                : `<div class="text-primary fw-bold" style="font-size: 0.95rem;">${parseFloat(p.proj || 0).toFixed(1)} <span class="text-muted fw-normal" style="font-size:0.6rem;">Proj</span></div>`;

            // --- ROW 2: Live Stats & Actuals ---
            let actualPtsDisplay = `<div class="text-muted fw-bold" style="font-size: 0.95rem; opacity:0.4;">-- <span class="fw-normal" style="font-size:0.6rem;">Act</span></div>`;
            let liveStatHtml = '';
            
            if (livePlayer) {
                // Actual points and value calculations
                let actualPts = platform === 'dk' ? (livePlayer.dk_pts || 0) : (livePlayer.fd_pts || 0);
                let actualValue = p.salary > 0 ? actualPts / (p.salary / 1000) : 0;
                
                let bat = livePlayer.batting;
                let pit = livePlayer.pitching;
                
                // Track all stats that score or lose points
                let statParts = [];
                if (pit && pit.battersFaced > 0) {
                    statParts.push(`${pit.inningsPitched || '0.0'} IP`);
                    statParts.push(`${pit.strikeOuts || 0} K`);
                    statParts.push(`${pit.earnedRuns || 0} ER`);
                    // Removed Hits, BB, and HBP to save space on the UI for Pitchers
                    if (pit.wins > 0) statParts.push(`W`);
                } 
                else if (bat && (bat.plateAppearances > 0 || bat.atBats > 0)) {
                    statParts.push(`${bat.hits || 0}-${bat.atBats || 0}`);
                    if (bat.doubles > 0) statParts.push(`${bat.doubles} 2B`);
                    if (bat.triples > 0) statParts.push(`${bat.triples} 3B`);
                    if (bat.homeRuns > 0) statParts.push(`${bat.homeRuns} HR`);
                    if (bat.runs > 0) statParts.push(`${bat.runs} R`);
                    if (bat.rbi > 0) statParts.push(`${bat.rbi} RBI`);
                    if (bat.baseOnBalls > 0) statParts.push(`${bat.baseOnBalls} BB`);
                    if (bat.hitByPitch > 0) statParts.push(`${bat.hitByPitch} HBP`);
                    if (bat.stolenBases > 0) statParts.push(`${bat.stolenBases} SB`);
                }
                
                // Adjusting the bottom row layout to prepend the game status badge
                let bottomBadge = gameStatusBadge ? gameStatusBadge.replace('ms-2', 'me-2') : '';

                if (statParts.length > 0) {
                    let textColor = isGameFinal ? 'text-secondary' : 'text-success';
                    liveStatHtml = `${bottomBadge}<span class="${textColor} fw-bold text-truncate pe-2" style="font-size:0.70rem;">${statParts.join(', ')}</span>`;
                } else if (liveGame.status !== 'Preview' && liveGame.status !== 'Scheduled') {
                    liveStatHtml = `${bottomBadge}<span class="text-muted fst-italic text-truncate pe-2" style="font-size:0.70rem;">No stats recorded</span>`;
                } else if (bottomBadge) {
                     liveStatHtml = `${bottomBadge}`;
                }
                
                // Show actual points/value if the game has started
                if (liveGame.status !== 'Preview' && liveGame.status !== 'Scheduled') {
                    if (isValue) {
                        actualPtsDisplay = `<div class="text-dark fw-bold" style="font-size: 0.95rem;">${actualValue.toFixed(2)}x <span class="text-muted fw-normal" style="font-size:0.6rem;">Act</span></div>`;
                    } else {
                        actualPtsDisplay = `<div class="text-dark fw-bold" style="font-size: 0.95rem;">${actualPts.toFixed(1)} <span class="text-muted fw-normal" style="font-size:0.6rem;">Act</span></div>`;
                    }
                }
            }

            tabSpecificHtml = `
                <div class="d-flex justify-content-between align-items-center w-100">
                    <div class="d-flex align-items-baseline text-truncate pe-2" style="min-width: 0;">
                        <div class="fw-bold text-dark text-truncate me-1" style="font-size: 0.95rem;" title="${p.name}">${shortName}</div>
                        <div class="text-muted ms-1" style="font-size: 0.70rem; white-space: nowrap;">${displayPos} • ${salFmt}</div>
                    </div>
                    <div class="text-end flex-shrink-0 ms-2">${topMetric}</div>
                </div>
                
                <div class="d-flex justify-content-between align-items-center w-100 mt-1">
                    <div class="d-flex align-items-center text-truncate" style="min-width: 0; flex-grow: 1;">${liveStatHtml}</div>
                    <div class="text-end flex-shrink-0 ms-auto ps-2">${actualPtsDisplay}</div>
                </div>
            `;
        }

        return `
        <div class="d-flex align-items-center py-2 border-bottom user-select-none" style="transition: background-color 0.2s;" onmouseover="this.style.backgroundColor='#f8f9fa'" onmouseout="this.style.backgroundColor='transparent'">
            <div class="fw-bold text-muted me-2 text-end flex-shrink-0" style="font-size: 0.85rem; width: 22px;">${index + 1}.</div>
            <div class="me-3 position-relative flex-shrink-0">
                ${photoHtml}
                ${teamBadge}
            </div>
            
            <div class="d-flex flex-column justify-content-center w-100" style="min-width: 0;">
                ${tabSpecificHtml}
            </div>
        </div>`;
    }).join('');
};

function buildTopPlaysCard(filteredGames, platform, selectedSlate) {
    let allHitters = [];
    let allPitchers = [];
    let allBvP = []; 
    let allHR = []; 
    
    filteredGames.forEach(game => {
        // --- NEW: SKIP POSTPONED/CANCELLED GAMES FOR TOP PLAYS ---
        const gameState = game.gameRaw?.status?.detailedState || '';
        if (['Postponed', 'Delayed', 'Suspended', 'Cancelled', 'Delayed Start'].includes(gameState)) {
            return; // Skip this iteration, keeping these players off the leaderboard
        }
        // ---------------------------------------------------------
        const pl = game.gameRaw?.teams || {}; 
        const awayAbbr = pl.away?.team?.abbreviation || pl.away?.team?.name?.substring(0,3).toUpperCase();
        const homeAbbr = pl.home?.team?.abbreviation || pl.home?.team?.name?.substring(0,3).toUpperCase();
        const awayLogo = `https://www.mlbstatic.com/team-logos/team-cap-on-light/${pl.away?.team?.id}.svg`;
        const homeLogo = `https://www.mlbstatic.com/team-logos/team-cap-on-light/${pl.home?.team?.id}.svg`;
        
        const deepStats = game.deepStats || {};
        const handDict = game.lineupHandedness || {};
        const parkStats = game.parkStats || null; 

        let posMap = {};
        if (game.gamePositions) {
            Object.assign(posMap, game.gamePositions);
        }
        if (game.gameRaw?.lineups?.awayPlayers) {
            game.gameRaw.lineups.awayPlayers.forEach(p => {
                if (p.primaryPosition?.abbreviation) posMap[p.id] = p.primaryPosition.abbreviation;
            });
        }
        if (game.gameRaw?.lineups?.homePlayers) {
            game.gameRaw.lineups.homePlayers.forEach(p => {
                if (p.primaryPosition?.abbreviation) posMap[p.id] = p.primaryPosition.abbreviation;
            });
        }

        const extract = (roster, teamAbbr, teamLogo, isPitcher, opposingPitcherName, opposingPitcherHand, opposingPitcherId) => {
            if (!roster) return;
            let arr = Array.isArray(roster) ? roster : [roster];
            arr.forEach(p => {
                if (!p) return;
                let sal = 0, proj = 0, val = 0;
                const slatesDict = platform === 'dk' ? (p.dk_slates || {}) : (p.fd_slates || {});
                
                if (selectedSlate !== 'all' && slatesDict[selectedSlate]) {
                    sal = slatesDict[selectedSlate].salary; proj = slatesDict[selectedSlate].proj; val = slatesDict[selectedSlate].value;
                } else if (selectedSlate === 'all') {
                    sal = platform === 'dk' ? (p.dk_salary || 0) : (p.salary || 0); 
                    proj = platform === 'dk' ? (p.dk_proj || 0) : (p.proj || 0); 
                    val = platform === 'dk' ? (p.dk_value || 0) : (p.value || 0);
                }
                
                let name = p.name || p.fullName || 'Unknown';
                let photo = `https://img.mlbstatic.com/mlb-photos/image/upload/d_people:brooks:default/w_180,q_auto:best/v1/people/${p.id}/headshot/67/current`;
                let fieldPos = isPitcher ? 'P' : (posMap[p.id] || 'B');
                
                // Grab DFS Positions!
                let fd_pos = p.fd_positions || '';
                let dk_pos = p.dk_positions || '';
                
                if (sal > 0 || proj > 0) {
                    let listToPush = isPitcher ? allPitchers : allHitters;
                    listToPush.push({ id: p.id || name, name, pos: fieldPos, fd_positions: fd_pos, dk_positions: dk_pos, teamAbbrev: teamAbbr, teamLogo, photo, salary: sal, proj, value: val });
                }

                if (!isPitcher && p.id && deepStats[String(p.id)]) {
                    const bvpStats = deepStats[String(p.id)].bvp;
                    
                    if (bvpStats && bvpStats.ab >= 5) {
                        allBvP.push({
                            id: p.id, name: name, pos: fieldPos, fd_positions: fd_pos, dk_positions: dk_pos, teamAbbrev: teamAbbr,
                            teamLogo: teamLogo, photo: photo, bvp: bvpStats, oppPitcher: opposingPitcherName || "Unknown"
                        });
                    }
                    
                    let batterHand = handDict[String(p.id)] || 'R'; 
                    let activeBatSide = batterHand;
                    if (batterHand === 'S') activeBatSide = opposingPitcherHand === 'L' ? 'R' : 'L';

                    let splitStats = opposingPitcherHand === 'L' ? deepStats[String(p.id)].split_vL : deepStats[String(p.id)].split_vR;
                    let splitHrRate = 0;
                    let bvpHrRate = 0;
                    let oppPitcherHrRate = 0;
                    let oppPitcherSplit = null;
                    
                    if (splitStats && splitStats.ab >= 10) splitHrRate = splitStats.hr / splitStats.ab;
                    if (bvpStats && bvpStats.ab > 0) bvpHrRate = bvpStats.hr / bvpStats.ab;
                    
                    // Pitcher HR Rate given up to this batter's active side
                    if (opposingPitcherId && deepStats[String(opposingPitcherId)]) {
                        let oppPitcherStats = deepStats[String(opposingPitcherId)];
                        oppPitcherSplit = activeBatSide === 'L' ? oppPitcherStats.split_vL : oppPitcherStats.split_vR;
                        
                        if (oppPitcherSplit && oppPitcherSplit.ab >= 10) {
                            oppPitcherHrRate = oppPitcherSplit.hr / oppPitcherSplit.ab;
                        }
                    }
                    
                    let baseHrScore = splitHrRate + bvpHrRate + oppPitcherHrRate;
                    let finalHrScore = baseHrScore;
                    
                    if (baseHrScore > 0 && parkStats) {
                        let parkFactor = activeBatSide === 'L' ? parkStats.hr_l : parkStats.hr_r;
                        if (parkFactor) finalHrScore = baseHrScore * (parkFactor / 100);
                    }
                    
                    if (finalHrScore > 0) {
                        allHR.push({
                            id: p.id, name: name, pos: fieldPos, fd_positions: fd_pos, dk_positions: dk_pos, teamAbbrev: teamAbbr,
                            teamLogo: teamLogo, photo: photo, 
                            bvp: bvpStats || {ab: 0, hr: 0}, 
                            split: splitStats || {ab: 0, hr: 0},
                            oppPitcher: opposingPitcherName || "Unknown",
                            oppHand: opposingPitcherHand,
                            oppPitcherSplit: oppPitcherSplit || {ab: 0, hr: 0},
                            activeBatSide: activeBatSide,
                            hrScore: finalHrScore 
                        });
                    }
                }
            });
        };
        
        const line = game.projectedLineups || {};
        let awayPitcherName = line.away?.startingPitcher?.name || game.gameRaw?.teams?.away?.probablePitcher?.fullName || "TBD";
        let homePitcherName = line.home?.startingPitcher?.name || game.gameRaw?.teams?.home?.probablePitcher?.fullName || "TBD";
        let awayPitcherHand = game.gameRaw?.teams?.away?.probablePitcher?.pitchHand?.code || 'R';
        let homePitcherHand = game.gameRaw?.teams?.home?.probablePitcher?.pitchHand?.code || 'R';
        
        let awayPitcherId = line.away?.startingPitcher?.id || game.gameRaw?.teams?.away?.probablePitcher?.id || null;
        let homePitcherId = line.home?.startingPitcher?.id || game.gameRaw?.teams?.home?.probablePitcher?.id || null;

        extract(line.away?.startingPitcher, awayAbbr, awayLogo, true, null, null, null);
        extract(line.away?.battingOrder, awayAbbr, awayLogo, false, homePitcherName, homePitcherHand, homePitcherId);
        extract(line.home?.startingPitcher, homeAbbr, homeLogo, true, null, null, null);
        extract(line.home?.battingOrder, homeAbbr, homeLogo, false, awayPitcherName, awayPitcherHand, awayPitcherId);
    });

    if (allHitters.length === 0 && allPitchers.length === 0) return '';
    
    // Save to Global Variables for fast filtering
    window.TOP_PLAYS_DATA = {
        hitters: Array.from(new Map(allHitters.map(p => [p.id, p])).values()),
        pitchers: Array.from(new Map(allPitchers.map(p => [p.id, p])).values()),
        bvp: Array.from(new Map(allBvP.map(p => [p.id, p])).values()),
        hr: Array.from(new Map(allHR.map(p => [p.id, p])).values()),
        platform: platform
    };

    // Determine Buttons based on Platform
    const posButtonsFD = ['ALL', 'P', 'C/1B', '2B', '3B', 'SS', 'OF'];
    const posButtonsDK = ['ALL', 'P', 'C', '1B', '2B', '3B', 'SS', 'OF'];
    const buttonsToUse = platform === 'dk' ? posButtonsDK : posButtonsFD;

    // Reset fallback if platform switches
    let activePos = window.CURRENT_TOP_PLAYS_POS || 'ALL';
    if (!buttonsToUse.includes(activePos)) activePos = 'ALL';
    window.CURRENT_TOP_PLAYS_POS = activePos;

    const buttonsHtml = buttonsToUse.map(pos => `<button class="pos-filter-btn ${pos === activePos ? 'active' : ''}" data-pos="${pos}" onclick="window.setTopPlaysPos(this)">${pos}</button>`).join('');

    return `
    <div class="col-md-6 col-lg-6 col-xl-4 px-1 mb-3">
        <div class="card shadow-sm border overflow-hidden h-100" style="background-color: #fff; border-radius: 6px; border-color: #dee2e6 !important;">
            <div class="card-header bg-dark text-white py-2 d-flex justify-content-between align-items-center">
                <h6 class="mb-0 fw-bold" style="font-size: 0.85rem;">⭐ Top Plays</h6>
                <span class="badge bg-secondary" style="font-size: 0.6rem;">${platform === 'dk' ? 'DraftKings' : 'FanDuel'}</span>
            </div>
            
            <div class="bg-light border-bottom d-flex align-items-center px-2 py-2 overflow-auto hide-scrollbar gap-1">
                ${buttonsHtml}
            </div>

            <div class="bg-light border-bottom d-flex justify-content-center align-items-center px-2 py-0">
                <div class="d-flex w-100">
                    <div class="leaderboard-tab active w-100" style="width: 25%;" data-tab="value" onclick="window.setTopPlaysTab(this)">VALUE</div>
                    <div class="leaderboard-tab w-100" style="width: 25%;" data-tab="proj" onclick="window.setTopPlaysTab(this)">PROJ</div>
                    <div class="leaderboard-tab w-100" style="width: 25%;" data-tab="bvp" onclick="window.setTopPlaysTab(this)">BVP</div>
                    <div class="leaderboard-tab w-100" style="width: 25%;" data-tab="hr" onclick="window.setTopPlaysTab(this)">HR</div>
                </div>
            </div>
            
            <div class="card-body p-0">
                <div id="view-top-plays-list" class="px-2 list-view" style="max-height: 380px; overflow-y: auto;">
                    </div>
            </div>
        </div>
    </div>`;
}

// ==========================================
// 4. RENDERING ENGINE
// ==========================================
function renderGames(isSilentRefresh = false) {
    const container = document.getElementById('games-container');
    if (!container) return;
    
    // --- 1. CAPTURE STATE (Only if silently refreshing) ---
    let scrollY = 0;
    let activeTopPlaysTab = 'value'; // Default fallback
    let openStatsIds = [];
    let expandedCardIds = [];
    let listViewScrollPositions = {}; 

    if (isSilentRefresh) {
        scrollY = window.scrollY;
        
        // Capture Top Plays Tab
        const activeTabEl = document.querySelector('.leaderboard-tab.active');
        if (activeTabEl) activeTopPlaysTab = activeTabEl.getAttribute('data-tab');

        // Capture inner scroll positions of the Top Plays lists
        document.querySelectorAll('.list-view').forEach(el => {
            if (el.id) listViewScrollPositions[el.id] = el.scrollTop;
        });

        // Capture Individual Expanded Players
        document.querySelectorAll('.stats-collapse:not(.d-none)').forEach(el => {
            if (el.id) openStatsIds.push(el.id);
        });

        // Capture Fully Expanded Cards (Card toggle buttons)
        document.querySelectorAll('.card-toggle-btn').forEach(btn => {
            if (btn.textContent.includes('[-]')) {
                const card = btn.closest('.lineup-card');
                if (card && card.id) expandedCardIds.push(card.id);
            }
        });
    }
    // ------------------------------------------------------

    // Keep controls intact, clear out the games & leaderboard underneath
    container.innerHTML = '';

    const platformNode = document.querySelector('input[name="dfsPlatform"]:checked');
    const platform = platformNode ? platformNode.value : 'fd';
    const selectedSlate = document.getElementById('slate-selector')?.value || 'all';

    const searchInput = document.getElementById('team-search');
    const searchText = searchInput ? searchInput.value.toLowerCase() : '';

    let filteredGames = ALL_GAMES_DATA.filter(item => {
        const g = item.gameRaw;
        const matchString = (g.teams.away.team.name + " " + g.teams.home.team.name).toLowerCase();
        return matchString.includes(searchText);
    });

    if (selectedSlate !== 'all') {
        filteredGames = filteredGames.filter(item => hasSlatePlayers(item, platform, selectedSlate));
    }

    if (filteredGames.length === 0) {
        container.innerHTML = `<div class="col-12 text-center py-5 text-muted fw-bold">No games match your filters.</div>`;
        return;
    }

    // Insert Leaderboard if no search
    if (!searchText) {
        const topPlaysHtml = buildTopPlaysCard(filteredGames, platform, selectedSlate);
        if (topPlaysHtml) {
            container.insertAdjacentHTML('beforeend', topPlaysHtml);
            window.updateTopPlaysView(); // Fire the dynamic renderer!
        }
    }

    let sortedGames = [...filteredGames].sort((a, b) => {
        const isFinalA = a.gameRaw.status.abstractGameState === 'Final';
        const isFinalB = b.gameRaw.status.abstractGameState === 'Final';
        if (isFinalA && !isFinalB) return 1; 
        if (!isFinalA && isFinalB) return -1; 
        return new Date(a.gameRaw.gameDate) - new Date(b.gameRaw.gameDate);
    });

    sortedGames.forEach(item => container.appendChild(createGameCard(item, platform, selectedSlate)));

    // --- 2. RESTORE STATE (Only if silently refreshing) ---
    if (isSilentRefresh) {
        // Restore Top Plays Tab (Positional Button state is handled by window.CURRENT_TOP_PLAYS_POS globally)
        const newActiveTab = document.querySelector(`.leaderboard-tab[data-tab="${activeTopPlaysTab}"]`);
        if (newActiveTab) {
            window.setTopPlaysTab(newActiveTab); // This also triggers the redraw
        } else {
            window.updateTopPlaysView(); // Failsafe
        }

        // Restore inner scroll positions for Top Plays lists
        Object.keys(listViewScrollPositions).forEach(id => {
            const listEl = document.getElementById(id);
            if (listEl) listEl.scrollTop = listViewScrollPositions[id];
        });

        // Restore Expanded Players
        openStatsIds.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.remove('d-none');
        });

        // Restore "Collapse Matchups" Button Text
        expandedCardIds.forEach(id => {
            const card = document.getElementById(id);
            if (card) {
                const btn = card.querySelector('.card-toggle-btn');
                if (btn) btn.textContent = '[-] Collapse Matchups';
            }
        });

        // Restore main window Scroll Position seamlessly
        window.scrollTo(0, scrollY);
    }
    // ------------------------------------------------------
}

function createGameCard(data, platform, selectedSlate) {
    const game = data.gameRaw;
    const handDict = data.lineupHandedness || {}; 
    const deepStats = data.deepStats || {};
    const parkStats = data.parkStats; 
    const hpUmpire = data.hpUmpire || "TBD"; 
    const umpStats = data.umpStats;

    const gameCard = document.createElement('div');
    gameCard.className = 'col-md-6 col-lg-6 col-xl-4 px-1 mb-3';

    const awayNameFull = game.teams.away.team.name;
    const homeNameFull = game.teams.home.team.name;
    
    let awayName = game.teams.away.team.teamName || awayNameFull.split(' ').pop();
    let homeName = game.teams.home.team.teamName || homeNameFull.split(' ').pop();

    if (awayNameFull.includes('Red Sox')) awayName = 'Red Sox';
    if (awayNameFull.includes('White Sox')) awayName = 'White Sox';
    if (awayNameFull.includes('Blue Jays')) awayName = 'Blue Jays';
    if (awayName === 'Diamondbacks') awayName = 'Dbacks';

    if (homeNameFull.includes('Red Sox')) homeName = 'Red Sox';
    if (homeNameFull.includes('White Sox')) homeName = 'White Sox';
    if (homeNameFull.includes('Blue Jays')) homeName = 'Blue Jays';
    if (homeName === 'Diamondbacks') homeName = 'Dbacks';

    const awayId = game.teams.away.team.id;
    const homeId = game.teams.home.team.id;
    const venueName = game.venue.name;
    const gameDateObj = new Date(game.gameDate);
    const gameTime = gameDateObj.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    const gameDateShort = gameDateObj.toLocaleDateString('en-US', { month: 'numeric', day: 'numeric' });

    const awayLogo = `https://www.mlbstatic.com/team-logos/team-cap-on-light/${awayId}.svg`;
    const homeLogo = `https://www.mlbstatic.com/team-logos/team-cap-on-light/${homeId}.svg`;

    const displayVenueName = venueName;
    let rightSideHtml = '';
    
    if (parkStats) {
        const uSize = "0.70rem"; 
        const getParkBadge = (factor) => {
            const diff = factor - 100;
            const absDiff = Math.abs(diff);
            const style = `font-family:sans-serif; font-size:${uSize}; font-weight:600; text-shadow:0px 0px 1px rgba(0,0,0,0.1);`;
            if (diff > 0) return `<span class="text-success" style="${style}">+${absDiff}%</span>`;
            if (diff < 0) return `<span class="text-danger" style="${style}">-${absDiff}%</span>`;
            return `<span class="text-muted" style="${style}">0%</span>`;
        };

        const labelStyle = `font-family:sans-serif; font-size:${uSize}; font-weight:normal; color:#495057; display: inline-block; width: 42px; text-align: right; padding-right: 4px;`;
        const sepStyle = `font-family:sans-serif; font-size:0.65rem; font-weight:normal; color:#adb5bd; margin:0 3px;`; 
        const sBlock = (val, lbl) => `<div class="d-flex align-items-baseline">${val}<span style="font-size:0.65rem; font-family:sans-serif; font-weight:normal; color:#6c757d; margin-left:1px;">${lbl}</span></div>`;

        rightSideHtml = `
            <div class="d-flex align-items-center ms-auto">
                <div class="text-muted fw-bold text-uppercase text-end" style="font-size: 0.70rem; letter-spacing: 0.5px; max-width: 85px; white-space: normal; line-height: 1.1;">
                    ${displayVenueName}
                </div>
                <div class="d-flex flex-column justify-content-center border-start ps-2 ms-2" style="font-family:sans-serif; line-height:1.2;">
                    <div class="d-flex align-items-baseline w-100 mb-1"><span style="${labelStyle}">R:</span>${getParkBadge(parkStats.runs)}</div>
                    <div class="d-flex align-items-baseline w-100 mb-1"><span style="${labelStyle}">HR:</span>${sBlock(getParkBadge(parkStats.hr_l), 'L')}<span style="${sepStyle}">/</span>${sBlock(getParkBadge(parkStats.hr_r), 'R')}</div>
                    <div class="d-flex align-items-baseline w-100"><span style="${labelStyle}">wOBA:</span>${sBlock(getParkBadge(parkStats.woba_l), 'L')}<span style="${sepStyle}">/</span>${sBlock(getParkBadge(parkStats.woba_r), 'R')}</div>
                </div>
            </div>`;
    } else {
        rightSideHtml = `<div class="text-muted fw-bold text-uppercase text-end ms-auto" style="font-size: 0.70rem; letter-spacing: 0.5px; line-height: 1.1;">${displayVenueName}</div>`;
    }

    // --- ODDS ENGINE ---
    const oddsData = data.odds; 
    let mlAway = '', mlHome = '';
    let rawAwayOdds = "TBD", rawHomeOdds = "TBD", rawTotal = "TBD";

    if (oddsData && oddsData.bookmakers && oddsData.bookmakers.length > 0) {
        let h2hMarket = null, totalsMarket = null;
        for (const bookie of oddsData.bookmakers) {
            if (!h2hMarket) h2hMarket = bookie.markets.find(m => m.key === 'h2h');
            if (!totalsMarket) totalsMarket = bookie.markets.find(m => m.key === 'totals');
            if (h2hMarket && totalsMarket) break; 
        }
        if (h2hMarket) {
            const awayOutcome = h2hMarket.outcomes.find(o => o.name === awayNameFull);
            const homeOutcome = h2hMarket.outcomes.find(o => o.name === homeNameFull);
            if (awayOutcome && awayOutcome.price) {
                mlAway = `<span class="badge bg-light text-dark border ms-1" style="font-size: 0.70rem; vertical-align: middle;">${awayOutcome.price > 0 ? '+'+awayOutcome.price : awayOutcome.price}</span>`;
                rawAwayOdds = awayOutcome.price > 0 ? '+'+awayOutcome.price : awayOutcome.price; 
            }
            if (homeOutcome && homeOutcome.price) {
                mlHome = `<span class="badge bg-light text-dark border ms-1" style="font-size: 0.70rem; vertical-align: middle;">${homeOutcome.price > 0 ? '+'+homeOutcome.price : homeOutcome.price}</span>`;
                rawHomeOdds = homeOutcome.price > 0 ? '+'+homeOutcome.price : homeOutcome.price; 
            }
        }
        if (totalsMarket && totalsMarket.outcomes.length > 0) rawTotal = totalsMarket.outcomes[0].point; 
    }

    // --- MERGE DFS DATA FOR PITCHERS ---
    let awayPitcher = "TBD", homePitcher = "TBD"; 
    let awayPitcherHand = 'R', homePitcherHand = 'R'; 
    let awayPitcherObj = data.projectedLineups?.away?.startingPitcher;
    if (awayPitcherObj) awayPitcherObj = { ...awayPitcherObj }; 
    
    let homePitcherObj = data.projectedLineups?.home?.startingPitcher;
    if (homePitcherObj) homePitcherObj = { ...homePitcherObj }; 
    
    if (game.teams.away.probablePitcher) {
        awayPitcherHand = game.teams.away.probablePitcher.pitchHand?.code || 'R';
        let offId = String(game.teams.away.probablePitcher.id);
        let offName = game.teams.away.probablePitcher.fullName.toLowerCase().replace(/[^a-z]/g, '');
        
        let matchesProj = false;
        if (awayPitcherObj) {
            let projId = String(awayPitcherObj.id);
            let projName = (awayPitcherObj.name || "").toLowerCase().replace(/[^a-z]/g, '');
            if (projId === offId || projName === offName) matchesProj = true;
        }

        if (matchesProj) {
            awayPitcherObj.id = offId;
            awayPitcherObj.name = game.teams.away.probablePitcher.fullName;
            awayPitcherObj.order = "P";
        } else {
            awayPitcherObj = { id: offId, name: game.teams.away.probablePitcher.fullName, order: "P" };
        }
        awayPitcher = game.teams.away.probablePitcher.fullName + ` (${awayPitcherHand})`;
    } else if (awayPitcherObj) {
        awayPitcher = awayPitcherObj.name + " (Proj)";
    }

    if (game.teams.home.probablePitcher) {
        homePitcherHand = game.teams.home.probablePitcher.pitchHand?.code || 'R';
        let offId = String(game.teams.home.probablePitcher.id);
        let offName = game.teams.home.probablePitcher.fullName.toLowerCase().replace(/[^a-z]/g, '');
        
        let matchesProj = false;
        if (homePitcherObj) {
            let projId = String(homePitcherObj.id);
            let projName = (homePitcherObj.name || "").toLowerCase().replace(/[^a-z]/g, '');
            if (projId === offId || projName === offName) matchesProj = true;
        }

        if (matchesProj) {
            homePitcherObj.id = offId;
            homePitcherObj.name = game.teams.home.probablePitcher.fullName;
            homePitcherObj.order = "P";
        } else {
            homePitcherObj = { id: offId, name: game.teams.home.probablePitcher.fullName, order: "P" };
        }
        homePitcher = game.teams.home.probablePitcher.fullName + ` (${homePitcherHand})`;
    } else if (homePitcherObj) {
        homePitcher = homePitcherObj.name + " (Proj)";
    }

    // --- GAME STATUS LOGIC (Replaces the Time Badge) ---
    const gameState = game.status.abstractGameState; 
    const detailedState = game.status.detailedState; 
    let timeBadgeHtml = `<span class="badge bg-white text-dark shadow-sm border px-2 py-1" style="font-size: 0.70rem;">${gameTime}</span>`;

    if (['Postponed', 'Delayed', 'Suspended', 'Cancelled', 'Delayed Start'].includes(detailedState)) {
        timeBadgeHtml = `<span class="badge bg-danger text-white shadow-sm border px-2 py-1" style="font-size: 0.70rem;">${detailedState}</span>`;
    } else if (gameState === 'Live') {
        const awayScore = game.linescore?.teams?.away?.runs ?? game.teams.away.score ?? 0;
        const homeScore = game.linescore?.teams?.home?.runs ?? game.teams.home.score ?? 0;
        const inning = game.linescore?.currentInning || '';
        let half = game.linescore?.inningHalf || ''; 
        let inningStr = ((half === 'Top' ? 'T' : (half === 'Bottom' ? 'B' : '')) + inning) || 'Live';
        timeBadgeHtml = `<span class="badge bg-primary text-white shadow-sm border px-2 py-1" style="font-size: 0.70rem;">${inningStr} ${awayScore}-${homeScore}</span>`;
    } else if (gameState === 'Final') {
        const awayScore = game.linescore?.teams?.away?.runs ?? game.teams.away.score ?? 0;
        const homeScore = game.linescore?.teams?.home?.runs ?? game.teams.home.score ?? 0;
        timeBadgeHtml = `<span class="badge bg-dark text-white shadow-sm border px-2 py-1" style="font-size: 0.70rem;">F ${awayScore}-${homeScore}</span>`;
    }

    let ouHtml = rawTotal !== "TBD" ? `<span class="badge bg-secondary text-white shadow-sm border px-2 py-1 ms-2" style="font-size: 0.70rem;">O/U ${rawTotal}</span>` : '';

    // NEW SLEEK HEADER (Replaces the large image header)
    const newHeaderHtml = `
        <div class="d-flex justify-content-between align-items-center mb-1 w-100 mt-2 px-1" style="font-size: 0.95rem; font-weight: bold; letter-spacing: -0.3px;">
            <div class="d-flex align-items-center text-start text-truncate" style="width: 48%;">
                <img src="${awayLogo}" alt="${awayName}" style="height: 30px; width: 30px; margin-right: 6px; flex-shrink: 0;">
                <span class="text-truncate">${awayName} ${mlAway}</span>
            </div>
            <div class="text-muted fw-bold text-center flex-shrink-0" style="font-size: 0.85rem; width: 4%;">@</div>
            <div class="d-flex align-items-center justify-content-end text-end text-truncate" style="width: 48%;">
                <img src="${homeLogo}" alt="${homeName}" style="height: 30px; width: 30px; margin-right: 6px; flex-shrink: 0;">
                <span class="text-truncate">${homeName} ${mlHome}</span>
            </div>
        </div>
    `;

    const buildLineupList = (playersArray, opposingPitcherHand, startingPitcherObj, ownPitcherHand) => {
        let displayArray = playersArray ? [...playersArray] : [];
        
        // INJECT PITCHER AT THE TOP
        if (startingPitcherObj) {
            const pitcherWithOrder = { ...startingPitcherObj, order: "P" };
            if (displayArray.length === 0 || displayArray[0].order !== "P") {
                displayArray.unshift(pitcherWithOrder);
            }
        }
        
        if (displayArray.length === 0) return `<div class="p-4 text-center text-muted small fw-bold">Lineup not yet posted</div>`;
        
        const listItems = displayArray.map((p, index) => {
            let playerName = p.fullName || p.name;
            let abbrName = playerName.includes(' ') ? `${playerName.split(' ')[0].charAt(0)}. ${playerName.split(' ').slice(1).join(' ')}` : playerName;
            
            const pidStr = String(p.id);

            // Fetch handedness (Fall back to the pitcher's own hand if they are the pitcher)
            let batCode = p.order === "P" ? ownPitcherHand : (handDict[pidStr] || "");
            const handText = batCode ? `<span class="text-muted fw-normal">(${batCode}) </span>` : "";
            
            const gamePos = (data.gamePositions && data.gamePositions[pidStr]) ? data.gamePositions[pidStr] : "";
            
            // Render "P" instead of order number for the pitcher
            const prefixText = p.order === "P" ? "P" : (gamePos ? gamePos : `${p.order || index}.`);
            const prefixColor = p.order === "P" ? "text-primary" : "text-muted";
            const rowHighlight = p.order === "P" ? "background-color: #f4f8fb;" : "";
            
            // --- DFS STATS ---
            let showStats = false, salFmt = '-', projFmt = '-', valFmt = '-';
            const slatesDict = platform === 'dk' ? (p.dk_slates || {}) : (p.fd_slates || {});
            let sal = 0, proj = 0, val = 0;
            
            if (selectedSlate !== 'all' && slatesDict[selectedSlate]) {
                sal = slatesDict[selectedSlate].salary; proj = slatesDict[selectedSlate].proj; val = slatesDict[selectedSlate].value; showStats = true;
            } else if (selectedSlate === 'all') {
                sal = platform === 'dk' ? (p.dk_salary || 0) : (p.salary || 0); proj = platform === 'dk' ? (p.dk_proj || 0) : (p.proj || 0); val = platform === 'dk' ? (p.dk_value || 0) : (p.value || 0);
                if (sal > 0 || proj > 0) showStats = true;
            }
            
            if (showStats) {
                salFmt = sal > 0 ? (sal / 1000).toFixed(1).replace('.0', '') + 'K' : '-';
                projFmt = proj > 0 ? proj.toFixed(1) : '-';
                valFmt = val > 0 ? val.toFixed(2) : '-';
            }

            const dfsHtml = showStats ? `
                <div class="d-flex align-items-center justify-content-end text-muted flex-shrink-0 pe-1" style="width: 40%; font-size: 0.55rem; letter-spacing: -0.4px;">
                    <span class="text-end fw-normal pe-2" style="width: 40%;">${salFmt}</span>
                    <span class="text-end text-primary fw-normal pe-2" style="width: 30%;">${projFmt}</span>
                    <span class="text-end text-success fw-normal" style="width: 30%;">${valFmt}</span>
                </div>` : `<div style="width: 40%;"></div>`;

            // --- BvP & SPLITS ---
            let statsHtml = '';
            const pStats = deepStats[pidStr];
            
            if (p.order === "P") {
                if (pStats && pStats.split_vL && pStats.split_vR) {
                    const formatRow = (split, label) => {
                        if (split.ab > 0) {
                            const avgStr = split.avg.length > 4 ? split.avg.substring(0, 4) : split.avg;
                            const opsStr = split.ops.length > 4 ? split.ops.substring(0, 4) : split.ops;
                            return `
                            <div class="d-flex align-items-center justify-content-start" style="font-size: 0.65rem; line-height: 1.5;">
                                <span class="text-muted fw-bold" style="display: inline-block; width: 18px;">${label}:</span>
                                <div class="d-flex align-items-center text-dark" style="font-family: SFMono-Regular, Consolas, monospace; letter-spacing: -0.5px;">
                                    <span style="display: inline-block; width: 24px;">${avgStr}</span><span class="text-muted" style="font-size: 0.45rem; margin: 0 1px;">•</span>
                                    <span style="display: inline-block; width: 24px;">${opsStr}</span><span class="text-muted" style="font-size: 0.45rem; margin: 0 1px;">•</span>
                                    <span style="display: inline-block; width: 24px;">${split.hr}HR</span><span class="text-muted" style="font-size: 0.45rem; margin: 0 1px;">•</span>
                                    <span>${split.k}K</span>
                                </div>
                            </div>`;
                        }
                        return `<div class="d-flex align-items-center justify-content-start" style="font-size: 0.65rem; line-height: 1.5;"><span class="text-muted fw-bold" style="display: inline-block; width: 18px;">${label}:</span><span class="text-muted fst-italic">No History</span></div>`;
                    };
                    statsHtml = `<div class="mt-1 p-1 rounded w-100 mx-auto" style="background-color: #f8f9fa; border: 1px solid #e9ecef;">${formatRow(pStats.split_vL, 'vL')}${formatRow(pStats.split_vR, 'vR')}</div>`;
                } else {
                    statsHtml = `<div class="mt-1 p-1 rounded text-center text-muted fst-italic w-100" style="background-color: #f8f9fa; font-size: 0.60rem; border: 1px solid #e9ecef;">Pitching data pending...</div>`;
                }
            } else {
                if (pStats && pStats.bvp) {
                    const bvp = pStats.bvp;
                    const split = opposingPitcherHand === 'L' ? pStats.split_vL : pStats.split_vR;
                    let bvpText = "No History", bvpClass = "text-muted"; 
                    if (bvp.ab > 0) { bvpText = `${bvp.hits}-${bvp.ab}•${bvp.hr}HR•${bvp.ops}OPS`; bvpClass = "text-dark"; }
                    let splitText = "No History", splitClass = "text-muted";
                    if (split && split.ab > 0) { splitText = `${split.avg}•${split.hr}HR•${split.ops}OPS`; splitClass = "text-dark"; }

                    statsHtml = `
                        <div class="mt-1 p-1 rounded text-start w-100" style="background-color: #f8f9fa; font-size: 0.65rem; border: 1px solid #e9ecef; line-height: 1.3;">
                            <div class="d-flex mb-1 align-items-center"><span class="text-muted fw-bold" style="min-width: 20px;">vP:</span><span class="${bvpClass} text-truncate">${bvpText}</span></div>
                            <div class="d-flex align-items-center"><span class="text-muted fw-bold" style="min-width: 20px;">v${opposingPitcherHand}:</span><span class="${splitClass} text-truncate">${splitText}</span></div>
                        </div>`;
                } else {
                    statsHtml = `<div class="mt-1 p-1 rounded text-start text-muted fst-italic w-100" style="background-color: #f8f9fa; font-size: 0.65rem; border: 1px solid #e9ecef;">Matchup data pending...</div>`;
                }
            }

            return `
                <li class="d-flex flex-column w-100 px-0 py-1 border-bottom player-toggle" style="cursor: pointer; transition: background-color 0.2s; ${rowHighlight}" onmouseover="this.style.backgroundColor='#f0f4f8'" onmouseout="this.style.backgroundColor='transparent'" data-target="stats-${game.gamePk}-${pidStr}">
                    <div class="d-flex justify-content-between align-items-center w-100">
                        <div class="d-flex align-items-center text-truncate ps-1" style="width: 60%;">
                            <span class="${prefixColor} fw-normal text-start flex-shrink-0" style="font-size: 0.60rem; width: 16px; margin-right: 4px;">${prefixText}</span>
                            <span class="text-truncate" style="font-size: 0.70rem;" title="${playerName}">
                                ${handText}<span class="batter-name fw-bold text-dark">${abbrName}</span>
                            </span>
                        </div>
                        ${dfsHtml}
                    </div>
                    <div id="stats-${game.gamePk}-${pidStr}" class="stats-collapse d-none w-100 mt-1 px-1">${statsHtml}</div>
                </li>`;
        }).join('');
        
        return `<div class="w-100 m-0 p-0"><ul class="batting-order w-100 m-0 p-0" style="list-style-type: none;">${listItems}</ul></div>`;
    };

    // --- MERGE DFS DATA FOR OFFICIAL LINEUPS ---
    let awayProjected = data.projectedLineups?.away?.battingOrder || [];
    let homeProjected = data.projectedLineups?.home?.battingOrder || [];

    let awayPlayers = game.lineups?.awayPlayers?.length > 0 ? game.lineups.awayPlayers : awayProjected;
    let homePlayers = game.lineups?.homePlayers?.length > 0 ? game.lineups.homePlayers : homeProjected;
    
    let isAwayOfficial = game.lineups?.awayPlayers?.length > 0;
    let isHomeOfficial = game.lineups?.homePlayers?.length > 0;

    // Smart Match: ID first, fallback to clean name string
    if (isAwayOfficial && awayProjected.length > 0) {
        const projMap = {};
        awayProjected.forEach(p => { 
            if (p && p.id) projMap[String(p.id)] = p; 
            if (p && p.name) projMap[p.name.toLowerCase().replace(/[^a-z]/g, '')] = p;
        });
        awayPlayers = awayPlayers.map(p => {
            const pid = String(p.id);
            const pname = (p.fullName || p.name || "").toLowerCase().replace(/[^a-z]/g, '');
            return projMap[pid] ? { ...projMap[pid], ...p } : (projMap[pname] ? { ...projMap[pname], ...p } : p);
        });
    }

    if (isHomeOfficial && homeProjected.length > 0) {
        const projMap = {};
        homeProjected.forEach(p => { 
            if (p && p.id) projMap[String(p.id)] = p; 
            if (p && p.name) projMap[p.name.toLowerCase().replace(/[^a-z]/g, '')] = p;
        });
        homePlayers = homePlayers.map(p => {
            const pid = String(p.id);
            const pname = (p.fullName || p.name || "").toLowerCase().replace(/[^a-z]/g, '');
            return projMap[pid] ? { ...projMap[pid], ...p } : (projMap[pname] ? { ...projMap[pname], ...p } : p);
        });
    }

    // --- SMART LINEUP STATUS BANNER ---
    const tracking = data.lineupTracking || { away: {}, home: {} };

    const getStatusBanner = (side, isOfficial, hasPlayers) => {
        if (!hasPlayers) return '';
        const track = tracking[side] || {};

        if (isOfficial) {
            if (track.status === 'MODIFIED') {
                return `<div class="text-center py-1 fw-bold text-white w-100 border-bottom" style="background-color: #dc3545; font-size: 0.75rem; letter-spacing: 0.5px;">
                            ⚠️ LATE SWAP <span style="font-size:0.65rem; opacity:0.9; font-weight:normal;">(${track.modifiedAt})</span>
                        </div>`;
            } else {
                let timeStr = track.officialAt ? ` <span style="font-size:0.65rem; opacity:0.9; font-weight:normal;">(${track.officialAt})</span>` : '';
                return `<div class="text-center py-1 fw-bold text-white w-100 border-bottom" style="background-color: #198754; font-size: 0.75rem; letter-spacing: 0.5px;">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" class="me-1" style="vertical-align: -2px;"><polyline points="20 6 9 17 4 12"></polyline></svg> OFFICIAL${timeStr}
                        </div>`;
            }
        } else {
            return `<div class="text-center py-1 fw-bold text-dark w-100 border-bottom" style="background-color: #ffecb5; font-size: 0.75rem; letter-spacing: 0.5px;">
                        <span style="font-size: 0.7rem; vertical-align: 0px;">⏳</span> PROJECTED
                    </div>`;
        }
    };

    const awayBanner = getStatusBanner('away', isAwayOfficial, awayPlayers.length > 0);
    const homeBanner = getStatusBanner('home', isHomeOfficial, homePlayers.length > 0);
    
    // Inject the pitcher objects and their handedness into the lineup build function
    const awayLineupHtml = buildLineupList(awayPlayers, homePitcherHand, awayPitcherObj, awayPitcherHand);
    const homeLineupHtml = buildLineupList(homePlayers, awayPitcherHand, homePitcherObj, homePitcherHand);

    const hasAnySlatePlayer = hasAnyDfsSalaries(data, platform);
    let missingSlateHtml = '';
    const platKey = platform === 'dk' ? 'draftkings' : 'fanduel';
    
    if (!hasAnySlatePlayer && selectedSlate === 'all') {
        if (GLOBAL_SLATES[platKey] && GLOBAL_SLATES[platKey].length > 0) {
            missingSlateHtml = `<div class="w-100 text-center py-1 fw-bold text-white bg-secondary border-top" style="font-size: 0.65rem;">🚫 Game not included in ${platform === 'dk' ? 'DK' : 'FD'} slates</div>`;
        } else {
            missingSlateHtml = `<div class="w-100 text-center py-1 fw-bold text-dark border-top" style="font-size: 0.65rem; background-color: #ffecb5;">⏳ ${platform === 'dk' ? 'DK' : 'FD'} salaries & slates pending...</div>`;
        }
    }

    const X_ICON_SVG = `<svg xmlns="http://www.w3.org/2000/svg" class="x-icon" viewBox="0 0 16 16"><path d="${X_SVG_PATH}"/></svg>`;
    const generateTweetText = (teamName, tPitcher, tOdds, oPitcher, oOdds, total, players) => {
        let text = `⚾ ${gameDateShort} ${teamName} Lineup${total !== 'TBD' ? ` • O/U ${total}` : ''}\nSP: ${tPitcher}${tOdds !== 'TBD' ? ` [${tOdds}]` : ''}\nvs ${oPitcher}${oOdds !== 'TBD' ? ` [${oOdds}]` : ''}\n\n`;
        text += players.map((p, i) => `${i+1}. ${p.fullName || p.name} ${(data.gamePositions && data.gamePositions[p.id]) ? `(${data.gamePositions[p.id]})` : ''} ${handDict[p.id] ? `(${handDict[p.id]})` : ''}`.replace(/  +/g, ' ').trim()).join('\n'); 
        return text + `\n\n#${teamName.replace(/\s+/g, '')}Lineup #MLB #DFS`;
    };

    let awayTweetBtn = game.lineups?.awayPlayers?.length > 0 ? `<button class="x-btn tweet-trigger" data-tweet="${encodeURIComponent(generateTweetText(awayName, awayPitcher, rawAwayOdds, homePitcher, rawHomeOdds, rawTotal, game.lineups.awayPlayers))}">${X_ICON_SVG}</button>` : '';
    let homeTweetBtn = game.lineups?.homePlayers?.length > 0 ? `<button class="x-btn tweet-trigger" data-tweet="${encodeURIComponent(generateTweetText(homeName, homePitcher, rawHomeOdds, awayPitcher, rawAwayOdds, rawTotal, game.lineups.homePlayers))}">${X_ICON_SVG}</button>` : '';

    let displayUmpire = hpUmpire !== "TBD" && hpUmpire.includes(' ') ? `${hpUmpire.split(' ')[0].charAt(0)}. ${hpUmpire.split(' ').slice(1).join(' ')}` : hpUmpire;
    let umpString = `<span class="text-dark fw-bold">${displayUmpire}</span>`;
    if (umpStats) {
        let kColor = parseFloat(umpStats.k_rate) >= 23.0 ? "text-danger" : (parseFloat(umpStats.k_rate) <= 21.0 ? "text-success" : "text-dark");
        let bbColor = parseFloat(umpStats.bb_rate) >= 9.0 ? "text-success" : (parseFloat(umpStats.bb_rate) <= 7.5 ? "text-danger" : "text-dark");
        let rpgColor = parseFloat(umpStats.rpg) >= 9.5 ? "text-success" : (parseFloat(umpStats.rpg) <= 8.0 ? "text-danger" : "text-dark");
        umpString += `<span class="text-muted fw-normal" style="margin-left: 4px; letter-spacing: -0.2px;">(G: <span class="text-dark fw-bold">${umpStats.games}</span><span class="text-muted" style="margin: 0 3px;">•</span>K: <span class="${kColor} fw-bold">${umpStats.k_rate}</span><span class="text-muted" style="margin: 0 3px;">•</span>BB: <span class="${bbColor} fw-bold">${umpStats.bb_rate}</span><span class="text-muted" style="margin: 0 3px;">•</span>Runs: <span class="${rpgColor} fw-bold">${umpStats.rpg}</span>)</span>`;
    }

    gameCard.innerHTML = `
        <div class="lineup-card shadow-sm border rounded bg-white overflow-hidden h-100" style="border-color: #dee2e6 !important;" id="game-${game.gamePk}">
            <div class="p-2 pb-1" style="background-color: #edf4f8;">
                
                <div class="d-flex justify-content-between align-items-center mb-0 w-100 pb-1 border-white">
                    <div class="d-flex align-items-center flex-shrink-0">
                        ${timeBadgeHtml}
                        ${ouHtml}
                    </div>
                    ${rightSideHtml}
                </div>
                
                ${newHeaderHtml}

            </div>
            
            ${missingSlateHtml}

            <div class="bg-light border-top border-bottom d-flex justify-content-between align-items-center px-2 py-1">
                <div>${awayTweetBtn}</div>
                <div><button class="btn btn-sm btn-link text-decoration-none card-toggle-btn fw-bold text-muted py-0 m-0" style="font-size: 0.7rem;">[+] Expand Matchups</button></div>
                <div>${homeTweetBtn}</div>
            </div>
            
            <div class="row g-0 bg-white">
                <div class="col-6 border-end">
                    ${awayBanner}
                    ${awayLineupHtml}
                </div>
                <div class="col-6">
                    ${homeBanner}
                    ${homeLineupHtml}
                </div>
            </div>

            <div class="px-2 py-1 border-top border-bottom text-center text-truncate" style="background-color: #f8f9fa; font-size: 0.70rem; letter-spacing: 0.5px;">
                <span class="text-muted fw-bold text-uppercase">HP:</span> ${umpString}
            </div>

            <div class="p-2 text-center bg-white">
                <a href="https://weathermlb.com/#game-${game.gamePk}" target="_blank" class="btn btn-sm w-100 promo-btn" style="background-color: #f8f9fa; border: 1px solid #dee2e6; color: #0d6efd;">
                    🌧️ View Weather & Wind Impact
                </a>
            </div>
        </div>`;
    
    gameCard.querySelectorAll('.tweet-trigger').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation(); 
            openTweetModal(decodeURIComponent(btn.getAttribute('data-tweet')));
        });
    });

    return gameCard;
}

function openTweetModal(text) {
    const modalEl = document.getElementById('tweetModal');
    const textarea = document.getElementById('tweet-textarea');
    if(modalEl && textarea) {
        textarea.value = text;
        new bootstrap.Modal(modalEl).show();
    }
}

// ==========================================
// 5. EVENT LISTENERS & ACCORDION
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    init(DEFAULT_DATE);

    // --- 30 SECOND LIVE AUTO-REFRESH ---
    setInterval(() => {
        const datePicker = document.getElementById('date-picker');
        const currentDate = datePicker ? datePicker.value : DEFAULT_DATE;
        // Pass "true" so it updates data silently in the background without flashing the loading spinner
        init(currentDate, true); 
    }, 30000); 
    // -----------------------------------

    const searchInput = document.getElementById('team-search');
    if (searchInput) searchInput.addEventListener('input', renderGames);

    const datePicker = document.getElementById('date-picker');
    if (datePicker) {
        datePicker.value = DEFAULT_DATE;
        datePicker.addEventListener('change', (e) => {
            if (e.target.value) { e.target.blur(); init(e.target.value); } // Normal load with spinner
        });
    }

    const copyBtn = document.getElementById('copy-tweet-btn');
    if(copyBtn) {
        copyBtn.addEventListener('click', () => {
            const textarea = document.getElementById('tweet-textarea');
            textarea.select();
            navigator.clipboard.writeText(textarea.value).then(() => {
                const originalText = copyBtn.innerHTML;
                copyBtn.innerHTML = "✅ Copied to Clipboard!";
                copyBtn.classList.replace('btn-dark', 'btn-success');
                setTimeout(() => {
                    copyBtn.innerHTML = originalText;
                    copyBtn.classList.replace('btn-success', 'btn-dark');
                }, 2000);
            }).catch(err => alert("Failed to copy to clipboard."));
        });
    }

    document.addEventListener('click', (e) => {
        if (e.target.closest('.player-toggle')) {
            const row = e.target.closest('.player-toggle');
            const div = document.getElementById(row.getAttribute('data-target'));
            if (div) div.classList.toggle('d-none');
        }
        
        if (e.target.closest('.card-toggle-btn')) {
            const btn = e.target.closest('.card-toggle-btn');
            const card = btn.closest('.lineup-card');
            const isExp = btn.textContent.includes('+');
            card.querySelectorAll('.stats-collapse').forEach(d => isExp ? d.classList.remove('d-none') : d.classList.add('d-none'));
            btn.textContent = isExp ? '[-] Collapse Matchups' : '[+] Expand Matchups';
        }
        
        if (e.target.closest('#global-toggle-btn')) {
            const btn = e.target.closest('#global-toggle-btn');
            const isExp = btn.textContent.includes('+');
            document.querySelectorAll('.stats-collapse').forEach(d => isExp ? d.classList.remove('d-none') : d.classList.add('d-none'));
            document.querySelectorAll('.card-toggle-btn').forEach(b => b.textContent = isExp ? '[-] Collapse Matchups' : '[+] Expand Matchups');
            btn.textContent = isExp ? '[-] Collapse All' : '[+] Expand All';
        }
    });
});
