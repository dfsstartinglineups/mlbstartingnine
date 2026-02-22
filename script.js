// ==========================================
// CONFIGURATION
// ==========================================
const DEFAULT_DATE = new Date().toLocaleDateString('en-CA');
let ALL_GAMES_DATA = []; 

// ==========================================
// 1. MAIN APP LOGIC
// ==========================================
async function fetchLocalOdds() {
    try {
        const response = await fetch('data/odds.json?v=' + new Date().getTime()); 
        if (response.ok) {
            const fileData = await response.json();
            return fileData.odds;
        }
        return null;
    } catch (e) {
        return null; 
    }
}

async function init(dateToFetch) {
    const container = document.getElementById('games-container');
    const datePicker = document.getElementById('date-picker');
    
    ALL_GAMES_DATA = [];
    if (datePicker) datePicker.value = dateToFetch;

    if (container) {
        container.innerHTML = `
            <div class="col-12 text-center mt-5 pt-5">
                <div class="spinner-border text-primary" role="status"></div>
                <p class="mt-3 text-muted fw-bold">Loading Lineups...</p>
            </div>`;
    }
    
    const MLB_API_URL = `https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=${dateToFetch}&hydrate=linescore,probablePitcher,lineups`;
    
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
        let dailyOddsData = await fetchLocalOdds();
        
        for (let i = 0; i < rawGames.length; i++) {
            const game = rawGames[i];

            let gameOdds = null;
            if (dailyOddsData) {
                gameOdds = dailyOddsData.find(o => 
                    o.home_team === game.teams.home.team.name && 
                    o.away_team === game.teams.away.team.name
                );
            }

            // --- FETCH LINEUP HANDEDNESS ---
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
                lineupHandedness: lineupHandedness
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

    // Sort by time
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

    const gameCard = document.createElement('div');
    gameCard.className = 'col-md-6 col-lg-6 col-xl-4';

    const awayName = game.teams.away.team.name;
    const homeName = game.teams.home.team.name;
    const gameTime = new Date(game.gameDate).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

    let awayPitcher = "TBD";
    let awayPitcherHand = "";
    if (game.teams.away.probablePitcher) {
        awayPitcher = game.teams.away.probablePitcher.fullName;
        awayPitcherHand = game.teams.away.probablePitcher.pitchHand?.code || "";
    }

    let homePitcher = "TBD";
    let homePitcherHand = "";
    if (game.teams.home.probablePitcher) {
        homePitcher = game.teams.home.probablePitcher.fullName;
        homePitcherHand = game.teams.home.probablePitcher.pitchHand?.code || "";
    }

    const buildLineupList = (playersArray) => {
        if (!playersArray || playersArray.length === 0) {
            return `<div class="p-4 text-center text-muted small fw-bold">Lineup not yet posted</div>`;
        }
        
        const listItems = playersArray.map((p, index) => {
            const batCode = handDict[p.id] || "";
            const handBadge = batCode ? `<span class="batter-hand">${batCode}</span>` : "";
            return `<li>
                        <div><span class="order-num">${index + 1}.</span> <span class="batter-name">${p.fullName}</span></div>
                        ${handBadge}
                    </li>`;
        }).join('');
        return `<ul class="batting-order">${listItems}</ul>`;
    };

    const awayLineupHtml = buildLineupList(game.lineups?.awayPlayers);
    const homeLineupHtml = buildLineupList(game.lineups?.homePlayers);

    const oddsData = data.odds; 
    let oddsHtml = `<div class="text-center small text-muted py-2 border-top">Odds TBD</div>`;
    
    if (oddsData && oddsData.bookmakers && oddsData.bookmakers.length > 0) {
        const bookie = oddsData.bookmakers[0];
        const h2hMarket = bookie.markets.find(m => m.key === 'h2h');
        const totalsMarket = bookie.markets.find(m => m.key === 'totals');
        
        let mlAway = "TBD", mlHome = "TBD", total = "TBD";
        
        if (h2hMarket) {
            const awayOutcome = h2hMarket.outcomes.find(o => o.name === awayName);
            const homeOutcome = h2hMarket.outcomes.find(o => o.name === homeName);
            if (awayOutcome) mlAway = awayOutcome.price > 0 ? `+${awayOutcome.price}` : awayOutcome.price;
            if (homeOutcome) mlHome = homeOutcome.price > 0 ? `+${homeOutcome.price}` : homeOutcome.price;
        }
        if (totalsMarket && totalsMarket.outcomes.length > 0) total = totalsMarket.outcomes[0].point;
        
        oddsHtml = `
            <div class="d-flex justify-content-between align-items-center py-2 px-3 border-top bg-light" style="font-size: 0.8rem;">
                <span class="fw-bold text-muted">Moneyline: <span class="text-dark">${mlAway} | ${mlHome}</span></span>
                <span class="fw-bold text-muted">Total: <span class="text-dark">O/U ${total}</span></span>
            </div>`;
    }

    gameCard.innerHTML = `
        <div class="lineup-card">
            <div class="d-flex justify-content-between align-items-center p-2 border-bottom bg-light">
                <span class="badge bg-dark">${gameTime}</span>
                <span class="small fw-bold text-muted text-uppercase">${awayName} @ ${homeName}</span>
            </div>
            
            <div class="row g-0">
                <div class="col-6 border-end">
                    <div class="pitcher-block">
                        <div class="text-uppercase text-muted" style="font-size: 0.65rem; font-weight: 800; letter-spacing: 0.5px;">Starting Pitcher</div>
                        <div class="pitcher-name mt-1">${awayPitcher}</div>
                        ${awayPitcherHand ? `<span class="pitcher-hand mt-1 d-inline-block">Throws ${awayPitcherHand}</span>` : ''}
                    </div>
                    ${awayLineupHtml}
                </div>
                
                <div class="col-6">
                    <div class="pitcher-block">
                        <div class="text-uppercase text-muted" style="font-size: 0.65rem; font-weight: 800; letter-spacing: 0.5px;">Starting Pitcher</div>
                        <div class="pitcher-name mt-1">${homePitcher}</div>
                        ${homePitcherHand ? `<span class="pitcher-hand mt-1 d-inline-block">Throws ${homePitcherHand}</span>` : ''}
                    </div>
                    ${homeLineupHtml}
                </div>
            </div>
            
            ${oddsHtml}

            <div class="p-2 border-top text-center">
                <a href="https://weathermlb.com" target="_blank" class="btn btn-sm btn-outline-primary w-100 promo-btn">
                    🌧️ View Weather & Wind Impact
                </a>
            </div>
        </div>`;
    
    return gameCard;
}

// ==========================================
// 3. LISTENERS
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
});
