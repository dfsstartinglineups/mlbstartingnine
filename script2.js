// ==========================================
// CONFIGURATION
// ==========================================
const DEFAULT_DATE = new Date().toLocaleDateString('en-CA');
let ALL_GAMES_DATA = []; 

let savedLineupState = localStorage.getItem('futbolLineupsExpanded');
let globalLineupsExpanded = savedLineupState !== null ? savedLineupState === 'true' : true;

const X_SVG_PATH = "M12.6.75h2.454l-5.36 6.142L16 15.25h-4.937l-3.867-5.07-4.425 5.07H.316l5.733-6.57L0 .75h5.063l3.495 4.633L12.601.75Zm-.86 13.028h1.36L4.323 2.145H2.865l8.875 11.633Z";

let PLAYER_DATABASE = null;

// Looks up the true, collision-proof database slug by raw numerical ID
function getPlayerSlug(id, defaultName) {
    if (id && PLAYER_DATABASE) {
        const dbKey = 'ID' + id;
        if (PLAYER_DATABASE[dbKey] && PLAYER_DATABASE[dbKey].slug) {
            return PLAYER_DATABASE[dbKey].slug;
        }
    }
    return slugify(defaultName);
}

// --- URL SLUG GENERATOR ---
// Accurately mirrors Python's string serialization loops for clean isolated directory matches
function slugify(text) {
    if (!text) return "";
    return text.toString().toLowerCase()
        .normalize('NFKD').replace(/[\u0300-\u036f]/g, '') // Strip accents (e.g., Domínguez -> dominguez)
        .replace(/[^\w\s-]/g, '')                          // Remove special characters and punctuation
        .replace(/[\s-]+/g, '-')                           // Convert spaces/dashes to single standard dashes
        .trim();
}

// --- CSS INJECTIONS FOR LEADERBOARD & CONTROLS ---
const style = document.createElement('style');
style.innerHTML = `
    .dk-btn-label { color: #6c9d2f; border-color: #6c9d2f; background-color: #fff; }
    .dk-btn-label:hover { color: #fff; background-color: #6c9d2f; border-color: #6c9d2f; }
    .btn-check:checked + .dk-btn-label { background-color: #6c9d2f !important; border-color: #6c9d2f !important; color: #fff !important; }
`;
document.head.appendChild(style);

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
// 2. DATA FETCHING & DFS MENU
// ==========================================
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
                    <!-- Redirects instantly on change -->
                    <select id="dfs-page-selector" class="form-select form-select-sm fw-bold shadow-sm" style="width: auto; min-width: 180px; cursor: pointer; font-size: 0.85rem; border-color: #ced4da; color: #212529;" onchange="if(this.value) window.location.href=this.value;">
                        <!-- Populated by JS -->
                    </select>
                </div>
            `;
            container.insertAdjacentHTML('beforebegin', controlsHtml);
            
            document.querySelectorAll('.dfs-toggle').forEach(radio => radio.addEventListener('change', () => {
                populateDFSLinks();
                renderGames(); // Re-render to update the FD/DK toggles inside the lineup cards
            }));
        }
    }
}

function populateDFSLinks() {
    const platformNode = document.querySelector('input[name="dfsPlatform"]:checked');
    const platform = platformNode ? platformNode.value : 'fd';
    
    const selector = document.getElementById('dfs-page-selector');
    if (!selector) return;
    
    selector.innerHTML = '<option value="">Top DFS Plays...</option>';
    
    const links = platform === 'dk' ? [
        { slug: "pitchers", label: "Pitchers" },
        { slug: "catchers", label: "Catchers" },
        { slug: "first-base", label: "First Base" },
        { slug: "second-base", label: "Second Base" },
        { slug: "third-base", label: "Third Base" },
        { slug: "shortstops", label: "Shortstops" },
        { slug: "outfielders", label: "Outfielders" },
        { slug: "util", label: "Util (All Hitters)" }
    ] : [
        { slug: "pitchers", label: "Pitchers" },
        { slug: "catchers-first-base", label: "C / 1B" },
        { slug: "second-base", label: "Second Base" },
        { slug: "third-base", label: "Third Base" },
        { slug: "shortstops", label: "Shortstops" },
        { slug: "outfielders", label: "Outfielders" },
        { slug: "util", label: "Utility" }
    ];
    
    const platSlug = platform === 'dk' ? 'draftkings' : 'fanduel';
    
    links.forEach(link => {
        const opt = document.createElement('option');
        opt.value = `/dfs/${platSlug}/top-${link.slug}/`;
        opt.textContent = link.label;
        selector.appendChild(opt);
    });
}

async function init(dateToFetch, isSilentRefresh = false) {
    if (window.updatePageMetadata && !isSilentRefresh) window.updatePageMetadata(dateToFetch); 
    
    const container = document.getElementById('games-container');
    const datePicker = document.getElementById('date-picker');
    
    if (datePicker && !isSilentRefresh) datePicker.value = dateToFetch;

    if (container && !isSilentRefresh) {
        ALL_GAMES_DATA = [];  

        container.innerHTML = `
            <div class="col-12 text-center mt-5 pt-5">
                <div class="spinner-border text-primary" role="status"></div>
                <p class="mt-3 text-muted fw-bold">Loading Pitch Data...</p>
            </div>`;
    }

    // --- FETCH PLAYER DATABASE ONCE ON INITIALIZATION ---
    if (!PLAYER_DATABASE) {
        try {
            const dbRes = await fetch('data/player_master_data.json');
            if (dbRes.ok) {
                PLAYER_DATABASE = await dbRes.json();
            }
        } catch (e) {
            console.error("Player DB could not be loaded into index view runtime memory:", e);
        }
    }
    
    try {
        const response = await fetch(`data/daily_files/games_${dateToFetch}.json?v=` + new Date().getTime());
        if (!response.ok) throw new Error("Local JSON not found");
        
        const rawData = await response.json();

        if (Array.isArray(rawData)) {
            ALL_GAMES_DATA = rawData;
        } else {
            ALL_GAMES_DATA = rawData.games || [];
        }

        if(!isSilentRefresh) {
            ensureDFSControls();
            populateDFSLinks();
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
                populateDFSLinks();
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

    renderGames(isSilentRefresh); 
    
    if (!isSilentRefresh) handleHashNavigation();
}

window.ACTIVE_GAME_TABS = window.ACTIVE_GAME_TABS || {};

window.switchGameTab = function(gamePk, tabName, btnEl) {
    const card = document.getElementById(`game-${gamePk}`);
    if (!card) return;
    
    const allBtns = card.querySelectorAll('.tab-btn');
    let isDeactivating = false;
    
    if (btnEl.classList.contains('active')) {
        btnEl.classList.remove('active', 'btn-primary', 'text-white');
        btnEl.classList.add('btn-outline-secondary', 'text-muted');
        isDeactivating = true;
    } else {
        allBtns.forEach(b => {
            b.classList.remove('active', 'btn-primary', 'text-white');
            b.classList.add('btn-outline-secondary', 'text-muted');
        });
        btnEl.classList.add('active', 'btn-primary', 'text-white');
        btnEl.classList.remove('btn-outline-secondary', 'text-muted');
    }

    const targetView = isDeactivating ? 'default' : tabName;
    window.ACTIVE_GAME_TABS[gamePk] = targetView;

    const allViews = card.querySelectorAll('.player-view');
    allViews.forEach(v => v.classList.add('d-none'));
    
    const targetViews = card.querySelectorAll(`.view-${targetView}`);
    targetViews.forEach(v => v.classList.remove('d-none'));
};

function adjustOverflowingNames() {
    requestAnimationFrame(() => {
        document.querySelectorAll('.batter-name').forEach(el => {
            if (el.scrollWidth > el.clientWidth) {
                const shortName = el.getAttribute('data-shortname');
                if (shortName && shortName !== el.textContent) {
                    el.textContent = shortName;
                }
            }
        });
    });
}

// ==========================================
// 3. RENDERING ENGINE
// ==========================================
function renderGames(isSilentRefresh = false) {
    const container = document.getElementById('games-container');
    if (!container) return;
    
    let scrollY = 0;
    let openStatsIds = [];
    let expandedCardIds = [];

     if (isSilentRefresh) {
        scrollY = window.scrollY;

        document.querySelectorAll('.stats-collapse:not(.d-none)').forEach(el => {
            if (el.id) openStatsIds.push(el.id);
        });

        document.querySelectorAll('.card-toggle-btn').forEach(btn => {
            if (btn.textContent.includes('[-]')) {
                const card = btn.closest('.lineup-card');
                if (card && card.id) expandedCardIds.push(card.id);
            }
        });
    }

    container.innerHTML = '';

    const searchInput = document.getElementById('team-search');
    const searchText = searchInput ? searchInput.value.toLowerCase() : '';

    let filteredGames = ALL_GAMES_DATA.filter(item => {
        const g = item.gameRaw;
        const matchString = (g.teams.away.team.name + " " + g.teams.home.team.name).toLowerCase();
        return matchString.includes(searchText);
    });

    if (filteredGames.length === 0) {
        container.innerHTML = `<div class="col-12 text-center py-5 text-muted fw-bold">No games match your filters.</div>`;
        return;
    }

    let sortedGames = [...filteredGames].sort((a, b) => {
        const getStatusWeight = (item) => {
            const status = item.gameRaw.status?.abstractGameState;
            const detailed = item.gameRaw.status?.detailedState || "";
            
            const inning = item.gameRaw.linescore?.currentInning || 0;
            const half = item.gameRaw.linescore?.inningHalf || "";

            if (status === "Final") return 2; 
            
            if (status === "Live" || detailed.includes("In Progress")) {
                if (inning === 0 || (inning === 1 && half === 'Top')) {
                    return 0; 
                }
                return 1; 
            }
            
            return 0; 
        };

        const weightA = getStatusWeight(a);
        const weightB = getStatusWeight(b);

        if (weightA !== weightB) {
            return weightA - weightB;
        }

        return new Date(a.gameRaw.gameDate) - new Date(b.gameRaw.gameDate);
    });

    sortedGames.forEach(item => container.appendChild(createGameCard(item)));

    adjustOverflowingNames();

    if (isSilentRefresh) {
        openStatsIds.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.remove('d-none');
        });

        expandedCardIds.forEach(id => {
            const card = document.getElementById(id);
            if (card) {
                const btn = card.querySelector('.card-toggle-btn');
                if (btn) btn.textContent = '[-] Collapse Matchups';
            }
        });

        window.scrollTo(0, scrollY);
    }
} 

function createGameCard(data) {
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

    const oddsData = data.odds; 
    let mlAway = '', mlHome = '';
    let rawTotal = "TBD";

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
                mlAway = `<div class="badge bg-light text-dark border" style="font-size: 0.60rem; padding: 2px 4px; font-family: monospace;">${awayOutcome.price > 0 ? '+'+awayOutcome.price : awayOutcome.price}</div>`;
            }
            if (homeOutcome && homeOutcome.price) {
                mlHome = `<div class="badge bg-light text-dark border" style="font-size: 0.60rem; padding: 2px 4px; font-family: monospace;">${homeOutcome.price > 0 ? '+'+homeOutcome.price : homeOutcome.price}</div>`;
            }
        }
        if (totalsMarket && totalsMarket.outcomes.length > 0) rawTotal = totalsMarket.outcomes[0].point; 
    }

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
    }

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

    const awayWins = game.teams.away.leagueRecord?.wins || 0;
    const awayLosses = game.teams.away.leagueRecord?.losses || 0;
    const homeWins = game.teams.home.leagueRecord?.wins || 0;
    const homeLosses = game.teams.home.leagueRecord?.losses || 0;
    
    const awayRecordHtml = `<span class="text-muted fw-normal ms-1" style="font-size: 0.70rem;">(${awayWins}-${awayLosses})</span>`;
    const homeRecordHtml = `<span class="text-muted fw-normal ms-1" style="font-size: 0.70rem;">(${homeWins}-${homeLosses})</span>`;

    // --- WRAPPED IN PITCHER HEAD CARDS ---
    const buildPitcherHeader = (pitcherObj, mlOdds, pHand) => {
        if (!pitcherObj || !pitcherObj.id) {
            return `<div class="d-flex align-items-center justify-content-center bg-light rounded border text-muted fst-italic w-100" style="height: 42px; font-size: 0.70rem;">TBD</div>`;
        }
        const pidStr = String(pitcherObj.id);
        const pStats = deepStats[pidStr]?.season || { w: 0, l: 0, era: "-", k: 0 };
        
        let playerName = pitcherObj.fullName || pitcherObj.name;
        let abbrName = playerName.includes(' ') ? `${playerName.split(' ')[0].charAt(0)}. ${playerName.split(' ').slice(1).join(' ')}` : playerName;
        
        const photoUrl = `https://img.mlbstatic.com/mlb-photos/image/upload/d_people:brooks:default/w_180,q_auto:best/v1/people/${pidStr}/headshot/67/current`;
        const photoHtml = `<img src="${photoUrl}" style="width: 24px; height: 24px; border-radius: 50%; object-fit: cover; border: 1px solid #dee2e6; background: #fff; margin-bottom: 2px;">`;
        
        const handText = pHand ? `<span class="text-muted fw-bold me-1" style="font-size:0.65rem;">(${pHand})</span>` : "";

        return `
        <div class="d-flex align-items-center bg-light rounded p-1 border w-100" style="min-height: 44px;">
            <div class="d-flex flex-column align-items-center justify-content-center me-2 flex-shrink-0" style="width: 32px;">
                ${photoHtml}
                ${mlOdds}
            </div>
            <div class="d-flex flex-column justify-content-center text-truncate w-100">
                <div class="d-flex align-items-center text-truncate w-100">
                    ${handText}
                    <a href="/players/${getPlayerSlug(pitcherObj.id, playerName)}/" class="fw-bold text-dark text-truncate text-decoration-none" style="font-size: 0.75rem;" title="${playerName}">${abbrName}</a>
                </div>
                <span class="text-muted" style="font-size: 0.65rem; margin-top: 1px;">${pStats.w}-${pStats.l} • ${pStats.era} • ${pStats.k || 0}K</span>
            </div>
        </div>`;
    };

    const newHeaderHtml = `
        <div class="d-flex justify-content-between w-100 mt-2 px-1">
            <div class="d-flex flex-column" style="width: 48%;">
                <div class="d-flex align-items-center text-truncate mb-1">
                    <img src="${awayLogo}" style="height: 24px; width: 24px; margin-right: 6px; flex-shrink: 0;">
                    <span class="fw-bold text-truncate" style="font-size: 0.95rem;">${awayName}</span>
                    ${awayRecordHtml}
                </div>
                ${buildPitcherHeader(awayPitcherObj, mlAway, awayPitcherHand)}
            </div>

            <div class="d-flex flex-column" style="width: 48%;">
                <div class="d-flex align-items-center text-truncate mb-1">
                    <img src="${homeLogo}" style="height: 24px; width: 24px; margin-right: 6px; flex-shrink: 0;">
                    <span class="fw-bold text-truncate" style="font-size: 0.95rem;">${homeName}</span>
                    ${homeRecordHtml}
                </div>
                ${buildPitcherHeader(homePitcherObj, mlHome, homePitcherHand)}
            </div>
        </div>
    `;

    window.ACTIVE_GAME_TABS = window.ACTIVE_GAME_TABS || {};
    const activeTab = window.ACTIVE_GAME_TABS[game.gamePk] || 'default';

    const getBtnClass = (tabName) => activeTab === tabName ? 'active btn-primary text-white' : 'btn-outline-secondary text-muted';
    const getViewClass = (tabName) => activeTab === tabName ? '' : 'd-none';

    const tabsHtml = `
        <div class="d-flex justify-content-center align-items-center gap-2 my-2 px-2 pb-2 border-bottom w-100">
            <button class="btn btn-sm fw-bold rounded-pill px-3 py-1 tab-btn flex-grow-1 ${getBtnClass('season')}" style="font-size: 0.65rem;" data-tab="season" onclick="switchGameTab('${game.gamePk}', 'season', this)">SEASON</button>
            <button class="btn btn-sm fw-bold rounded-pill px-3 py-1 tab-btn flex-grow-1 ${getBtnClass('vsp')}" style="font-size: 0.65rem;" data-tab="vsp" onclick="switchGameTab('${game.gamePk}', 'vsp', this)">VS P</button>
            <button class="btn btn-sm fw-bold rounded-pill px-3 py-1 tab-btn flex-grow-1 ${getBtnClass('splits')}" style="font-size: 0.65rem;" data-tab="splits" onclick="switchGameTab('${game.gamePk}', 'splits', this)">SPLITS</button>
            <button class="btn btn-sm fw-bold rounded-pill px-3 py-1 tab-btn flex-grow-1 ${getBtnClass('fd')}" style="font-size: 0.65rem;" data-tab="fd" onclick="switchGameTab('${game.gamePk}', 'fd', this)">FD</button>
            <button class="btn btn-sm fw-bold rounded-pill px-3 py-1 tab-btn flex-grow-1 ${getBtnClass('dk')}" style="font-size: 0.65rem;" data-tab="dk" onclick="switchGameTab('${game.gamePk}', 'dk', this)">DK</button>
        </div>
    `;

    // --- WRAPPED IN LINEUP GRID TILES ---
    const buildLineupList = (playersArray, opposingPitcherHand) => {
        let displayArray = playersArray ? [...playersArray] : [];
        if (displayArray.length === 0) return `<div class="p-4 text-center text-muted small fw-bold">Lineup not yet posted</div>`;
        
        const listItems = displayArray.map((p, index) => {
            const pidStr = String(p.id);
            let playerName = p.fullName || p.name;
            let abbrName = playerName.includes(' ') ? `${playerName.split(' ')[0].charAt(0)}. ${playerName.split(' ').slice(1).join(' ')}` : playerName;

            let batCode = handDict[pidStr] || "";
            const handText = batCode ? `<span class="text-muted fw-bold" style="font-size:0.60rem;">(${batCode})</span>` : "";
            
            const gamePos = (data.gamePositions && data.gamePositions[pidStr]) ? data.gamePositions[pidStr] : "";
            const prefixText = gamePos ? gamePos : `${p.order || index}.`;
            
            const photoUrl = `https://img.mlbstatic.com/mlb-photos/image/upload/d_people:brooks:default/w_180,q_auto:best/v1/people/${p.id}/headshot/67/current`;
            const photoHtml = `<img src="${photoUrl}" style="width: 26px; height: 26px; border-radius: 50%; object-fit: cover; border: 1px solid #dee2e6; background: #fff; margin-right: 6px;" onerror="this.onerror=null; this.src='data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iI2FkYjViZCI+PHBhdGggZD0iTTEyIDJDMi42NCAyIDIgNi42NCAyIDEyeiIvPjwvc3ZnPg==';">`;

            const topLineHtml = `
                <div class="d-flex align-items-center text-truncate w-100" style="padding-bottom: 2px;">
                    <span class="text-muted fw-bold text-center flex-shrink-0" style="font-size: 0.65rem; width: 22px; margin-right: 4px;">${prefixText}</span>
                    ${handText}
                    <a href="/players/${getPlayerSlug(p.id, playerName)}/" class="batter-name fw-bold text-dark text-truncate ms-1 text-decoration-none" style="font-size: 0.65rem;" title="${playerName}" data-shortname="${abbrName}">${playerName}</a>
                </div>`;

            const viewDefault = `
                <div class="d-flex align-items-center w-100">
                    <span class="text-muted fw-bold text-center flex-shrink-0" style="font-size: 0.65rem; width: 22px; margin-right: 4px;">${prefixText}</span>
                    ${photoHtml}
                    ${handText}
                    <a href="/players/${getPlayerSlug(p.id, playerName)}/" class="batter-name fw-bold text-dark text-truncate ms-1 text-decoration-none" style="font-size: 0.70rem;" title="${playerName}" data-shortname="${abbrName}">${playerName}</a>
                </div>`;

            const sStats = deepStats[pidStr]?.season || { avg: '-', ops: '-', hr: 0 };
            const viewSeason = `
                ${topLineHtml}
                <div class="text-muted text-truncate w-100" style="font-size: 0.60rem;">${sStats.avg} • ${sStats.ops} OPS • ${sStats.hr} HR</div>`;

            const bvp = deepStats[pidStr]?.bvp || { hits: 0, ab: 0, avg: '-', ops: '-', hr: 0 };
            const viewVsP = `
                ${topLineHtml}
                <div class="text-muted text-truncate w-100" style="font-size: 0.60rem;">${bvp.hits}-${bvp.ab} • ${bvp.avg} • ${bvp.ops} OPS • ${bvp.hr} HR</div>`;

            const split = opposingPitcherHand === 'L' ? deepStats[pidStr]?.split_vL : deepStats[pidStr]?.split_vR;
            const pSplit = split || { ab: 0, avg: '-', ops: '-', hr: 0 };
            const splitHits = (pSplit.ab > 0 && pSplit.avg !== '-') ? Math.round(parseFloat(pSplit.avg) * pSplit.ab) : 0;
            const viewSplits = `
                ${topLineHtml}
                <div class="text-muted text-truncate w-100" style="font-size: 0.60rem;">v${opposingPitcherHand}: ${splitHits}-${pSplit.ab}•${pSplit.avg}•${pSplit.ops}•${pSplit.hr} HR</div>`;

            // Stripped slate dependencies: falls back to default daily projection 
            const fdSal = p.salary || 0;
            const fdProj = p.proj || 0;
            const fdVal = p.value || 0;
            const fdSalStr = fdSal > 0 ? '$' + (fdSal/1000).toFixed(1).replace('.0','') + 'K' : '-';
            const viewFd = `
                ${topLineHtml}
                <div class="d-flex gap-2 text-muted text-truncate w-100" style="font-size: 0.60rem;">
                    <span>${fdSalStr}</span> 
                    <span class="text-primary fw-bold">Proj: ${fdProj > 0 ? parseFloat(fdProj).toFixed(1) : '-'}</span> 
                    <span class="text-success fw-bold">Value: ${fdVal > 0 ? parseFloat(fdVal).toFixed(1) + 'x' : '-'}</span>
                </div>`;

            const dkSal = p.dk_salary || 0;
            const dkProj = p.dk_proj || 0;
            const dkVal = p.dk_value || 0;
            const dkSalStr = dkSal > 0 ? '$' + (dkSal/1000).toFixed(1).replace('.0','') + 'K' : '-';
            const viewDk = `
                ${topLineHtml}
                <div class="d-flex gap-2 text-muted text-truncate w-100" style="font-size: 0.60rem;">
                    <span>${dkSalStr}</span> 
                    <span class="text-primary fw-bold">Proj: ${dkProj > 0 ? parseFloat(dkProj).toFixed(1) : '-'}</span> 
                    <span class="text-success fw-bold">Value: ${dkVal > 0 ? parseFloat(dkVal).toFixed(1) + 'x' : '-'}</span>
                </div>`;

            return `
                <li class="d-flex align-items-center w-100 px-2 py-1 border-bottom" style="min-height: 36px;">
                    <div class="d-flex align-items-center flex-grow-1 text-truncate w-100 lh-sm">
                        <div class="player-view view-default align-items-center w-100 ${getViewClass('default')}">${viewDefault}</div>
                        <div class="player-view view-season flex-column justify-content-center w-100 ${getViewClass('season')}">${viewSeason}</div>
                        <div class="player-view view-vsp flex-column justify-content-center w-100 ${getViewClass('vsp')}">${viewVsP}</div>
                        <div class="player-view view-splits flex-column justify-content-center w-100 ${getViewClass('splits')}">${viewSplits}</div>
                        <div class="player-view view-fd flex-column justify-content-center w-100 ${getViewClass('fd')}">${viewFd}</div>
                        <div class="player-view view-dk flex-column justify-content-center w-100 ${getViewClass('dk')}">${viewDk}</div>
                    </div>
                </li>`;
        }).join('');
        
        return `<div class="w-100 m-0 p-0"><ul class="batting-order w-100 m-0 p-0" style="list-style-type: none;">${listItems}</ul></div>`;
    };

    let awayProjected = data.projectedLineups?.away?.battingOrder || [];
    let homeProjected = data.projectedLineups?.home?.battingOrder || [];

    let awayPlayers = game.lineups?.awayPlayers?.length > 0 ? game.lineups.awayPlayers : awayProjected;
    let homePlayers = game.lineups?.homePlayers?.length > 0 ? game.lineups.homePlayers : homeProjected;
    
    let isAwayOfficial = game.lineups?.awayPlayers?.length > 0;
    let isHomeOfficial = game.lineups?.homePlayers?.length > 0;

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

    const tracking = data.lineupTracking || { away: {}, home: {} };

    const getStatusBanner = (side, isOfficial, hasPlayers) => {
        if (!hasPlayers) return '';
        const track = tracking[side] || {};

        if (isOfficial) {
            if (track.status === 'MODIFIED') {
                return `<div class="text-center py-1 fw-bold text-white w-100 border-bottom" style="background-color: #dc3545; font-size: 0.75rem; letter-spacing: 0.5px;">⚠️ LATE SWAP <span style="font-size:0.65rem; opacity:0.9; font-weight:normal;">(${track.modifiedAt})</span></div>`;
            } else {
                let timeStr = track.officialAt ? ` <span style="font-size:0.65rem; opacity:0.9; font-weight:normal;">(${track.officialAt})</span>` : '';
                return `<div class="text-center py-1 fw-bold text-white w-100 border-bottom" style="background-color: #198754; font-size: 0.75rem; letter-spacing: 0.5px;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" class="me-1" style="vertical-align: -2px;"><polyline points="20 6 9 17 4 12"></polyline></svg> OFFICIAL${timeStr}</div>`;
            }
        } else {
            return `<div class="text-center py-1 fw-bold text-dark w-100 border-bottom" style="background-color: #ffecb5; font-size: 0.75rem; letter-spacing: 0.5px;"><span style="font-size: 0.7rem; vertical-align: 0px;">⏳</span> PROJECTED</div>`;
        }
    };

    const awayBanner = getStatusBanner('away', isAwayOfficial, awayPlayers.length > 0);
    const homeBanner = getStatusBanner('home', isHomeOfficial, homePlayers.length > 0);
    
    const awayLineupHtml = buildLineupList(awayPlayers, homePitcherHand);
    const homeLineupHtml = buildLineupList(homePlayers, awayPitcherHand);

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
            
            ${tabsHtml}
            
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
// 4. EVENT LISTENERS
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    init(DEFAULT_DATE);

    setInterval(() => {
        const datePicker = document.getElementById('date-picker');
        const currentDate = datePicker ? datePicker.value : DEFAULT_DATE;
        init(currentDate, true); 
    }, 30000); 

    const searchInput = document.getElementById('team-search');
    if (searchInput) searchInput.addEventListener('input', renderGames);

    const datePicker = document.getElementById('date-picker');
    if (datePicker) {
        datePicker.value = DEFAULT_DATE;
        datePicker.addEventListener('change', (e) => {
            if (e.target.value) { e.target.blur(); init(e.target.value); } 
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
