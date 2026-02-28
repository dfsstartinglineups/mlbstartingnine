// ==========================================
// CONFIGURATION
// ==========================================
const DEFAULT_DATE = new Date().toLocaleDateString('en-CA');
let ALL_GAMES_DATA = []; 

// ==========================================
// DYNAMIC SEO ENGINE
// ==========================================
function updateSEO(selectedDateStr) {
    // 1. Format the date (e.g., "Feb 28, 2026")
    const [year, month, day] = selectedDateStr.split('-');
    const dateObj = new Date(year, month - 1, day);
    const formattedDate = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    
    // 2. Determine if we are in Spring Training (Before March 25, 2026)
    const openingDay = new Date(2026, 2, 25); 
    
    let titlePrefix = "MLB Starting Lineups & Odds";
    let descPrefix = "Live MLB starting lineups, probable pitchers, moneylines, and totals";
    
    if (dateObj < openingDay) {
        titlePrefix = "MLB Spring Training Lineups & Odds";
        descPrefix = "Live MLB Spring Training starting lineups, probable pitchers, live odds, and totals";
    }
    
    // 3. Inject the Date and Season Type into the DOM
    document.title = `${titlePrefix} for ${formattedDate} | BvP Matchups`;
    
    const descTag = document.getElementById('dynamic-desc');
    if (descTag) {
        descTag.setAttribute('content', `${descPrefix}. Plus daily Batter vs. Pitcher (BvP) matchups and career splits for ${formattedDate}. Built for DFS, fantasy baseball, and sports bettors.`);
    }
}

// ==========================================
// 1. MAIN APP LOGIC
// ==========================================
async function fetchLocalOdds() {
    try {
        const response = await fetch('https://weathermlb.com/data/odds.json?v=' + new Date().getTime()); 
        if (response.ok) {
            const fileData = await response.json();
            return fileData.odds;
        }
    } catch (e) { console.log("Error fetching cross-domain odds:", e); }
    return null; 
}

async function fetchMatchupsData() {
    try {
        const response = await fetch('data/matchups.json?v=' + new Date().getTime()); 
        if (response.ok) {
            return await response.json();
        }
    } catch (e) { console.log("No matchups.json found."); }
    return null;
}

async function init(dateToFetch) {
    updateSEO(dateToFetch); // Instantly update Title and Meta tags!
    
    const container = document.getElementById('games-container');
    const datePicker = document.getElementById('date-picker');
    
    ALL_GAMES_DATA = [];
    if (datePicker) datePicker.value = dateToFetch;

    if (container) {
        container.innerHTML = `
            <div class="col-12 text-center mt-5 pt-5">
                <div class="spinner-border text-primary" role="status"></div>
                <p class="mt-3 text-muted fw-bold">Loading Lineups & Matchups...</p>
            </div>`;
    }
    
    const MLB_API_URL = `https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=${dateToFetch}&hydrate=linescore,probablePitcher,lineups,person`;
    
    try {
        const scheduleResponse = await fetch(MLB_API_URL);
        const scheduleData = await scheduleResponse.json();

        if (scheduleData.totalGames === 0) {
            container.innerHTML = `
                <div class="col-12 text-center mt-5">
                    <div class="alert alert-light border shadow-sm py-4">
                        <h5 class="text-muted mb-0">No games scheduled for ${dateToFetch}</h5>
                    </div>
                </div>`;
            return;
        }

        const rawGames = scheduleData.dates[0].games;
        
        const [dailyOddsData, matchupsData] = await Promise.all([
            fetchLocalOdds(),
            fetchMatchupsData()
        ]);
        
        const cachedGames = matchupsData?.games || {};

        for (let i = 0; i < rawGames.length; i++) {
            const game = rawGames[i];

            let gameOdds = null;
            if (dailyOddsData) {
                gameOdds = dailyOddsData.find(o => 
                    o.home_team === game.teams.home.team.name && 
                    o.away_team === game.teams.away.team.name
                );
            }

            let lineupHandedness = {};
            const awayLineup = game.lineups?.awayPlayers || [];
            const homeLineup = game.lineups?.homePlayers || [];
            const lineupIds = [...awayLineup, ...homeLineup].map(p => p.id);

            if (lineupIds.length > 0) {
                try {
                    const peopleRes = await fetch(`https://statsapi.mlb.com/api/v1/people?personIds=${lineupIds.join(',')}`);
                    const peopleData = await peopleRes.json();
                    if (peopleData.people) {
                        peopleData.people.forEach(person => {
                            lineupHandedness[person.id] = person.batSide?.code || "";
                        });
                    }
                } catch (e) { console.log("Failed to fetch lineup handedness"); }
            }

            ALL_GAMES_DATA.push({
                gameRaw: game,
                odds: gameOdds,
                lineupHandedness: lineupHandedness,
                deepStats: cachedGames[game.gamePk] || {} 
            });
        }

        renderGames();

    } catch (error) {
        console.error("❌ ERROR:", error);
        container.innerHTML = `<div class="col-12 text-center mt-5"><div class="alert alert-danger">Failed to load schedule.</div></div>`;
    }
}

// ==========================================
// 2. RENDERING ENGINE
// ==========================================
function renderGames() {
    const container = document.getElementById('games-container');
    container.innerHTML = '';

    let sortedGames = [...ALL_GAMES_DATA].sort((a, b) => {
        return new Date(a.gameRaw.gameDate) - new Date(b.gameRaw.gameDate);
    });

    sortedGames.forEach(item => {
        container.appendChild(createGameCard(item));
    });
}

function createGameCard(data) {
    const game = data.gameRaw;
    const handDict = data.lineupHandedness || {}; 
    const deepStats = data.deepStats || {};

    const gameCard = document.createElement('div');
    // Reduced spacing between columns from mb-3 to mb-2
    gameCard.className = 'col-md-6 col-lg-6 col-xl-4 mb-2';

    // Store the full names for odds matching
    const awayNameFull = game.teams.away.team.name;
    const homeNameFull = game.teams.home.team.name;
    
    // Extract short team names (e.g., "Pirates" instead of "Pittsburgh Pirates")
    let awayName = game.teams.away.team.teamName || awayNameFull.split(' ').pop();
    let homeName = game.teams.home.team.teamName || homeNameFull.split(' ').pop();

    // Catch long names to prevent UI breaking
    if (awayName === 'Diamondbacks') awayName = 'Dbacks';
    if (homeName === 'Diamondbacks') homeName = 'Dbacks';

    const awayId = game.teams.away.team.id;
    const homeId = game.teams.home.team.id;
    const venueName = game.venue.name;
    const gameTime = new Date(game.gameDate).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

    const awayLogo = `https://www.mlbstatic.com/team-logos/team-cap-on-light/${awayId}.svg`;
    const homeLogo = `https://www.mlbstatic.com/team-logos/team-cap-on-light/${homeId}.svg`;

    let awayPitcher = "TBD";
    let awayPitcherHand = 'R'; 
    if (game.teams.away.probablePitcher) {
        awayPitcherHand = game.teams.away.probablePitcher.pitchHand?.code || 'R';
        awayPitcher = game.teams.away.probablePitcher.fullName + ` (${awayPitcherHand})`;
    }

    let homePitcher = "TBD";
    let homePitcherHand = 'R'; 
    if (game.teams.home.probablePitcher) {
        homePitcherHand = game.teams.home.probablePitcher.pitchHand?.code || 'R';
        homePitcher = game.teams.home.probablePitcher.fullName + ` (${homePitcherHand})`;
    }

    // --- LINEUPS BUILDER (ULTRA-COMPACT) ---
    const buildLineupList = (playersArray, opposingPitcherHand) => {
        if (!playersArray || playersArray.length === 0) {
            return `<div class="p-4 text-center text-muted small fw-bold">Lineup not yet posted</div>`;
        }
        
        const listItems = playersArray.map((p, index) => {
            // 1. Abbreviate Name & Append Handedness (e.g., "O. Cruz (L)")
            let abbrName = p.fullName;
            const nameParts = p.fullName.split(' ');
            if (nameParts.length > 1) {
                abbrName = `${nameParts[0].charAt(0)}. ${nameParts.slice(1).join(' ')}`;
            }
            
            const batCode = handDict[p.id] || "";
            const handText = batCode ? ` <span class="text-muted fw-normal" style="font-size: 0.75rem;">(${batCode})</span>` : "";
            
            let statsHtml = '';
            const pStats = deepStats[p.id];
            
            if (pStats) {
                const bvp = pStats.bvp;
                const split = opposingPitcherHand === 'L' ? pStats.split_vL : pStats.split_vR;
                
                // 4. Maximum Compact Stat Formatting
                let bvpText = "No History";
                let bvpClass = "text-muted"; 
                if (bvp.ab > 0) {
                    bvpText = `${bvp.hits}-${bvp.ab}•${bvp.hr}HR•${bvp.ops}OPS`;
                    bvpClass = "text-dark"; 
                }

                let splitText = "No History";
                let splitClass = "text-muted";
                if (split.ab > 0) {
                    splitText = `${split.avg}•${split.hr}HR•${split.ops}OPS`;
                    splitClass = "text-dark"; 
                }

                // Micro-labels and tight padding
                statsHtml = `
                    <div class="mt-1 p-1 rounded text-start w-100" style="background-color: #f8f9fa; font-size: 0.65rem; border: 1px solid #e9ecef; line-height: 1.3;">
                        <div class="d-flex mb-1 align-items-center">
                            <span class="text-muted fw-bold" style="min-width: 20px;">vP:</span>
                            <span class="${bvpClass} text-truncate">${bvpText}</span>
                        </div>
                        <div class="d-flex align-items-center">
                            <span class="text-muted fw-bold" style="min-width: 20px;">v${opposingPitcherHand}:</span>
                            <span class="${splitClass} text-truncate">${splitText}</span>
                        </div>
                    </div>
                `;
            } else {
                statsHtml = `<div class="mt-1 p-1 rounded text-start text-muted fst-italic w-100" style="background-color: #f8f9fa; font-size: 0.65rem; border: 1px solid #e9ecef;">Matchup data pending...</div>`;
            }

            // Compressed vertical padding (py-1)
            return `<li class="d-flex flex-column w-100 px-2 py-1 border-bottom">
                        <div class="d-flex justify-content-between align-items-center w-100 player-toggle" style="cursor: pointer;" data-target="stats-${game.gamePk}-${p.id}">
                            <div class="text-truncate pe-1">
                                <span class="order-num text-muted fw-bold me-1" style="font-size: 0.7rem;">${index + 1}.</span> 
                                <span class="batter-name fw-bold text-dark" style="font-size: 0.85rem;" title="${p.fullName}">${abbrName}${handText}</span>
                            </div>
                            <div>
                                <span class="badge bg-light text-secondary border toggle-icon" style="width: 24px;">+</span>
                            </div>
                        </div>
                        <div id="stats-${game.gamePk}-${p.id}" class="stats-collapse d-none w-100">
                            ${statsHtml}
                        </div>
                    </li>`;
        }).join('');
        return `<ul class="batting-order w-100 m-0 p-0" style="list-style-type: none;">${listItems}</ul>`;
    };

    const awayLineupHtml = buildLineupList(game.lineups?.awayPlayers, homePitcherHand);
    const homeLineupHtml = buildLineupList(game.lineups?.homePlayers, awayPitcherHand);

    // --- ODDS LOGIC ---
    const oddsData = data.odds; 
    let mlAway = "", mlHome = "", totalHtml = `<div class="text-muted small fw-bold pt-2">@</div>`;
    
    if (oddsData && oddsData.bookmakers && oddsData.bookmakers.length > 0) {
        const bookie = oddsData.bookmakers[0];
        const h2hMarket = bookie.markets.find(m => m.key === 'h2h');
        const totalsMarket = bookie.markets.find(m => m.key === 'totals');
        
        if (h2hMarket) {
            // Find odds using the full team names
            const awayOutcome = h2hMarket.outcomes.find(o => o.name === awayNameFull);
            const homeOutcome = h2hMarket.outcomes.find(o => o.name === homeNameFull);
            
            if (awayOutcome) {
                const price = awayOutcome.price > 0 ? `+${awayOutcome.price}` : awayOutcome.price;
                mlAway = `<span class="badge bg-light text-dark border ms-1" style="font-size: 0.70rem; vertical-align: middle;">${price}</span>`;
            }
            if (homeOutcome) {
                const price = homeOutcome.price > 0 ? `+${homeOutcome.price}` : homeOutcome.price;
                mlHome = `<span class="badge bg-light text-dark border ms-1" style="font-size: 0.70rem; vertical-align: middle;">${price}</span>`;
            }
        }
        
        if (totalsMarket && totalsMarket.outcomes.length > 0) {
            const total = totalsMarket.outcomes[0].point;
            // Compressed vertical padding & margin
            totalHtml = `
                <div class="d-flex flex-column justify-content-center align-items-center pt-1">
                    <div class="text-muted small fw-bold mb-0 lh-1">@</div>
                    <div class="badge bg-secondary text-white mt-1" style="font-size: 0.65rem; letter-spacing: 0.5px;">O/U ${total}</div>
                </div>`;
        }
    }

    // --- CARD RENDER ---
    gameCard.innerHTML = `
        <div class="lineup-card shadow-sm" style="margin-bottom: 8px;">
            
            <div class="p-2 pb-1" style="background-color: #edf4f8;">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="badge bg-white text-dark shadow-sm border px-2 py-1" style="font-size: 0.75rem;">${gameTime}</span>
                    <span class="text-muted fw-bold text-uppercase text-truncate" style="font-size: 0.7rem; max-width: 180px; letter-spacing: 0.5px;">${venueName}</span>
                </div>
                
                <div class="d-flex justify-content-between align-items-center px-1">
                    <div class="text-center" style="width: 42%;"> 
                        <img src="${awayLogo}" alt="${awayName}" class="team-logo mb-1" style="width: 45px; height: 45px;" onerror="this.style.display='none'">
                        <div class="fw-bold lh-1 text-dark d-flex justify-content-center align-items-center flex-wrap" style="font-size: 0.9rem; letter-spacing: -0.2px;">
                            ${awayName} ${mlAway}
                        </div>
                        <div class="text-muted mt-1 fw-bold" style="font-size: 0.75rem;">${awayPitcher}</div>
                    </div>
                    
                    <div class="text-center" style="width: 16%;">
                        ${totalHtml}
                    </div>
                    
                    <div class="text-center" style="width: 42%;"> 
                        <img src="${homeLogo}" alt="${homeName}" class="team-logo mb-1" style="width: 45px; height: 45px;" onerror="this.style.display='none'">
                        <div class="fw-bold lh-1 text-dark d-flex justify-content-center align-items-center flex-wrap" style="font-size: 0.9rem; letter-spacing: -0.2px;">
                            ${homeName} ${mlHome}
                        </div>
                        <div class="text-muted mt-1 fw-bold" style="font-size: 0.75rem;">${homePitcher}</div>
                    </div>
                </div>
            </div>

            <div class="bg-light border-top border-bottom text-center">
                <button class="btn btn-sm btn-link text-decoration-none card-toggle-btn fw-bold text-muted py-1 m-0" style="font-size: 0.7rem;">[+] Expand Matchups</button>
            </div>
            
            <div class="row g-0 bg-white">
                <div class="col-6 border-end">
                    ${awayLineupHtml}
                </div>
                <div class="col-6">
                    ${homeLineupHtml}
                </div>
            </div>

            <div class="p-2 border-top text-center bg-white">
                <a href="https://weathermlb.com" target="_blank" class="btn btn-sm w-100 promo-btn" style="background-color: #f8f9fa; border: 1px solid #dee2e6; color: #0d6efd;">
                    🌧️ View Weather & Wind Impact
                </a>
            </div>
        </div>`;
    
    return gameCard;
}

// ==========================================
// 3. LISTENERS & ACCORDION LOGIC
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    init(DEFAULT_DATE);

    const datePicker = document.getElementById('date-picker');
    if (datePicker) {
        datePicker.value = DEFAULT_DATE;
        datePicker.addEventListener('change', (e) => {
            if (e.target.value) {
                e.target.blur(); 
                init(e.target.value);
            }
        });
    }

    // --- UNIVERSAL TOGGLE LISTENER ---
    document.addEventListener('click', (e) => {
        
        // 1. Individual Player Clicked
        if (e.target.closest('.player-toggle')) {
            const toggleRow = e.target.closest('.player-toggle');
            const targetId = toggleRow.getAttribute('data-target');
            const statsDiv = document.getElementById(targetId);
            const icon = toggleRow.querySelector('.toggle-icon');
            
            if (statsDiv.classList.contains('d-none')) {
                statsDiv.classList.remove('d-none');
                icon.textContent = '-';
            } else {
                statsDiv.classList.add('d-none');
                icon.textContent = '+';
            }
        }
        
        // 2. Card Level "Expand Matchups" Clicked
        if (e.target.closest('.card-toggle-btn')) {
            const btn = e.target.closest('.card-toggle-btn');
            const card = btn.closest('.lineup-card');
            const statsDivs = card.querySelectorAll('.stats-collapse');
            const icons = card.querySelectorAll('.toggle-icon');
            
            const isExpanding = btn.textContent.includes('+');
            
            statsDivs.forEach(div => {
                if (isExpanding) div.classList.remove('d-none');
                else div.classList.add('d-none');
            });
            
            icons.forEach(icon => { icon.textContent = isExpanding ? '-' : '+'; });
            btn.textContent = isExpanding ? '[-] Collapse Matchups' : '[+] Expand Matchups';
        }
        
        // 3. Global Header "Expand All" Clicked
        if (e.target.closest('#global-toggle-btn')) {
            const btn = e.target.closest('#global-toggle-btn');
            const isExpanding = btn.textContent.includes('+');
            
            document.querySelectorAll('.stats-collapse').forEach(div => {
                if (isExpanding) div.classList.remove('d-none');
                else div.classList.add('d-none');
            });
            
            document.querySelectorAll('.toggle-icon').forEach(icon => { 
                icon.textContent = isExpanding ? '-' : '+'; 
            });
            
            document.querySelectorAll('.card-toggle-btn').forEach(cardBtn => {
                cardBtn.textContent = isExpanding ? '[-] Collapse Matchups' : '[+] Expand Matchups';
            });
            
            btn.textContent = isExpanding ? '[-] Collapse All' : '[+] Expand All';
        }
    });
});
