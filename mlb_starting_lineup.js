/**
 * ============================================================================
 * MLB STARTING 9 - MASTER TEAM LINEUP ENGINE (mlb_starting_lineup.js)
 * Compact Dugout Scorecard: Short Names, Visible Watermark, & Dynamic Date.
 * ============================================================================
 */

// ==========================================
// 1. MASTER THEME DICTIONARY
// ==========================================
const TEAM_THEMES = {
    108: { name: "Angels", paperBg: "#f4f1ea", paperLine: "rgba(186, 0, 33, 0.35)", markerInk: "#ba0021" },
    109: { name: "Diamondbacks", paperBg: "#f4f1ea", paperLine: "rgba(167, 25, 48, 0.35)", markerInk: "#a71930" },
    110: { name: "Orioles", paperBg: "#f4f1ea", paperLine: "rgba(223, 70, 1, 0.35)", markerInk: "#df4601" },
    111: { name: "Red Sox", paperBg: "#f4f1ea", paperLine: "rgba(189, 48, 57, 0.35)", markerInk: "#bd3039" },
    112: { name: "Cubs", paperBg: "#f4f1ea", paperLine: "rgba(14, 51, 134, 0.35)", markerInk: "#0e3386" },
    113: { name: "Reds", paperBg: "#f4f1ea", paperLine: "rgba(198, 1, 31, 0.35)", markerInk: "#c6011f" },
    114: { name: "Guardians", paperBg: "#f4f1ea", paperLine: "rgba(227, 25, 55, 0.35)", markerInk: "#e31937" },
    115: { name: "Rockies", paperBg: "#f4f1ea", paperLine: "rgba(51, 0, 111, 0.35)", markerInk: "#33006f" },
    116: { name: "Tigers", paperBg: "#f4f1ea", paperLine: "rgba(12, 35, 64, 0.35)", markerInk: "#0c2340" },
    117: { name: "Astros", paperBg: "#f4f1ea", paperLine: "rgba(235, 110, 31, 0.35)", markerInk: "#eb6e1f" },
    118: { name: "Royals", paperBg: "#f4f1ea", paperLine: "rgba(0, 70, 135, 0.35)", markerInk: "#004687" },
    119: { name: "Dodgers", paperBg: "#f4f1ea", paperLine: "rgba(0, 90, 156, 0.35)", markerInk: "#005a9c" },
    120: { name: "Nationals", paperBg: "#f4f1ea", paperLine: "rgba(171, 0, 3, 0.35)", markerInk: "#ab0003" },
    121: { name: "Mets", paperBg: "#f4f1ea", paperLine: "rgba(255, 89, 16, 0.35)", markerInk: "#ff5910" },
    133: { name: "Athletics", paperBg: "#f4f1ea", paperLine: "rgba(0, 56, 49, 0.35)", markerInk: "#003831" },
    134: { name: "Pirates", paperBg: "#f4f1ea", paperLine: "rgba(253, 184, 39, 0.45)", markerInk: "#fdb827" },
    135: { name: "Padres", paperBg: "#f4f1ea", paperLine: "rgba(47, 36, 29, 0.35)", markerInk: "#2f241d" },
    136: { name: "Mariners", paperBg: "#f4f1ea", paperLine: "rgba(0, 92, 92, 0.35)", markerInk: "#005c5c" },
    137: { name: "Giants", paperBg: "#f4f1ea", paperLine: "rgba(253, 90, 30, 0.35)", markerInk: "#fd5a1e" },
    138: { name: "Cardinals", paperBg: "#f4f1ea", paperLine: "rgba(196, 30, 58, 0.35)", markerInk: "#c41e3a" },
    139: { name: "Rays", paperBg: "#f4f1ea", paperLine: "rgba(9, 44, 87, 0.35)", markerInk: "#092c57" },
    140: { name: "Rangers", paperBg: "#f4f1ea", paperLine: "rgba(0, 50, 120, 0.35)", markerInk: "#003278" },
    141: { name: "Blue Jays", paperBg: "#f4f1ea", paperLine: "rgba(19, 74, 142, 0.35)", markerInk: "#134a8e" },
    142: { name: "Twins", paperBg: "#f4f1ea", paperLine: "rgba(0, 43, 92, 0.35)", markerInk: "#002b5c" },
    143: { name: "Phillies", paperBg: "#f4f1ea", paperLine: "rgba(232, 24, 40, 0.35)", markerInk: "#e81828" },
    144: { name: "Braves", paperBg: "#f4f1ea", paperLine: "rgba(206, 17, 65, 0.35)", markerInk: "#ce1141" },
    145: { name: "White Sox", paperBg: "#f4f1ea", paperLine: "rgba(39, 37, 31, 0.35)", markerInk: "#27251f" },
    146: { name: "Marlins", paperBg: "#f4f1ea", paperLine: "rgba(0, 163, 224, 0.35)", markerInk: "#00a3e0" },
    147: { name: "Yankees", paperBg: "#f4f1ea", paperLine: "rgba(12, 35, 64, 0.35)", markerInk: "#0c2340" }
};

let dailySlateData = null;
let currentTargetId = window.TARGET_TEAM_ID || 119;
let currentTargetSlug = window.TARGET_TEAM_SLUG || "los-angeles-dodgers";
let currentTargetName = window.TARGET_TEAM_NAME || "Los Angeles Dodgers";

function getHeadshotUrl(personId) {
    if (!personId) return "https://www.mlbstatic.com/team-logos/100.svg";
    return `https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/${personId}/headshot/67/current`;
}

// 🛡️ THE PITCHER FIX: Dynamically grabs handedness and ignores projected pitchers if MLB announces an official one
function getSafePitcher(gameData, sideKey, gameNum) {
    const raw = gameData.gameRaw || {};
    const proj = gameData.projectedLineups?.[sideKey]?.startingPitcher || {};
    const official = raw.teams?.[sideKey]?.probablePitcher;
    const handMap = gameData.lineupHandedness || {};

    // 1. If MLB officially announced the pitcher, ALWAYS trust MLB over the projection site.
    if (official && official.fullName) {
        return {
            id: official.id,
            name: official.fullName,
            hand: handMap[official.id] || (proj.id === official.id ? proj.hand : "")
        };
    }
    
    // 2. If no official MLB pitcher, but it's Game 1, trust the backend projection.
    if (gameNum === 1 && proj && proj.name) {
        return {
            id: proj.id,
            name: proj.name,
            hand: handMap[proj.id] || proj.hand || ""
        };
    }
    
    // 3. 🛡️ DOUBLEHEADER SHIELD: If Game 2 and no official MLB pitcher, DO NOT trust projections!
    return { id: null, name: "TBD / Bullpen Game", hand: "" };
}

function getShortTeamName(fullName, mlbTeamNameNode) {
    let short = mlbTeamNameNode || fullName.split(' ').pop();
    if (fullName.includes('Red Sox')) short = 'Red Sox';
    if (fullName.includes('White Sox')) short = 'White Sox';
    if (fullName.includes('Blue Jays')) short = 'Blue Jays';
    if (short === 'Diamondbacks') short = 'D-Backs';
    return short.toUpperCase();
}

// ==========================================
// 2. INITIALIZATION
// ==========================================
document.addEventListener("DOMContentLoaded", async () => {
    buildHeaderAndFooter();
    
    // Sync browser time to EST so files always load correctly across timezones
    const estDateString = new Intl.DateTimeFormat('en-US', {
        timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit'
    }).format(new Date());
    const [mm, dd, yyyy] = estDateString.split('/');
    const todayStr = `${yyyy}-${mm}-${dd}`;

    try {
        const res = await fetch(`/data/daily_files/games_${todayStr}.json?v=${new Date().getTime()}`);
        if (!res.ok) throw new Error("Daily slate JSON not found.");
        dailySlateData = await res.json();
    } catch (err) {
        console.warn("Could not load local JSON slate:", err);
    }

    populateTeamDropdown();
    renderTeamPage();
});

// ==========================================
// 3. UI BUILDERS (HEADER & FOOTER)
// ==========================================
function buildHeaderAndFooter() {
    const headerContainer = document.getElementById("header-container");
    if (headerContainer) {
        headerContainer.innerHTML = `
            <header style="background: #121212; border-bottom: 1px solid #222; padding: 12px 15px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <a href="/" style="text-decoration: none; display: flex; align-items: center; gap: 8px;">
                        <img src="/logo.webp" alt="MLB Starting 9 Logo" style="height: 36px; width: auto; border-radius: 6px;" onerror="this.style.display='none'">
                        <div>
                            <span style="font-family: 'Bebas Neue', cursive; font-size: 24px; color: #fff; letter-spacing: 1px; line-height: 1;">MLB STARTING 9</span>
                            <div style="font-family: 'Montserrat', sans-serif; font-size: 9px; color: #00e676; font-weight: 700; letter-spacing: 0.5px;">DAILY FANTASY STATS & LINEUPS</div>
                        </div>
                    </a>
                </div>
                
                <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                    <a href="/" style="font-family: 'Montserrat', sans-serif; font-size: 12px; color: #aaa; text-decoration: none; border: 1px solid #333; padding: 6px 12px; border-radius: 6px; transition: all 0.2s; white-space: nowrap;" onmouseover="this.style.borderColor='#00e676'; this.style.color='#fff'" onmouseout="this.style.borderColor='#333'; this.style.color='#aaa'">
                        &larr; Back to Slate
                    </a>
                    
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <label for="team-selector" style="font-family: 'Montserrat', sans-serif; font-size: 11px; color: #888; text-transform: uppercase; font-weight: 600; display: none;">Team:</label>
                        <select id="team-selector" onchange="handleTeamSwitch(this)" style="background: #1e1e1e; color: #fff; border: 1px solid #444; padding: 6px 10px; border-radius: 6px; font-family: 'Montserrat', sans-serif; font-size: 12px; outline: none; cursor: pointer; max-width: 220px;">
                            <option value="">Loading teams...</option>
                        </select>
                    </div>
                </div>
            </header>
        `;
    }

    const footerContainer = document.getElementById("footer-container");
    if (footerContainer) {
        footerContainer.innerHTML = `
            <footer style="background: #0a0a0a; border-top: 1px solid #1a1a1a; padding: 25px 15px; text-align: center; margin-top: 40px; font-family: 'Montserrat', sans-serif;">
                <p style="color: #666; font-size: 11px; margin: 0 0 8px 0;">
                    &copy; ${new Date().getFullYear()} MLB Starting 9. All rights reserved. Real-time data from official MLB sources.
                </p>
                <p style="color: #444; font-size: 10px; max-width: 550px; margin: 0 auto; line-height: 1.4;">
                    Disclaimer: This website is for informational and entertainment purposes only. Not affiliated with or endorsed by Major League Baseball or any MLB franchise.
                </p>
            </footer>
        `;
    }
}

function populateTeamDropdown() {
    const selector = document.getElementById("team-selector");
    if (!selector || !dailySlateData || !dailySlateData.games) return;

    let optionsHtml = "";
    const playingTeams = [];
    const addedTeamIds = new Set(); 

    dailySlateData.games.forEach(game => {
        const raw = game.gameRaw || {};
        const tracking = game.lineupTracking || {};
        
        ['away', 'home'].forEach(side => {
            const teamObj = raw.teams?.[side]?.team;
            if (!teamObj) return;

            if (addedTeamIds.has(teamObj.id)) return;
            addedTeamIds.add(teamObj.id);

            const status = tracking[side]?.status || "NONE";
            const badge = (status === "OFFICIAL" || status === "MODIFIED") ? "✓" : "⏳";
            const oppSide = side === 'away' ? 'home' : 'away';
            const oppName = raw.teams?.[oppSide]?.team?.name || "OPP";
            const vsSymbol = side === 'away' ? `@ ${oppName}` : `vs ${oppName}`;
            const slug = getSlugFromId(teamObj.id);

            playingTeams.push({
                id: teamObj.id,
                name: teamObj.name,
                slug: slug,
                label: `[${badge}] ${teamObj.name} (${vsSymbol})`
            });
        });
    });

    playingTeams.sort((a, b) => a.name.localeCompare(b.name));

    playingTeams.forEach(t => {
        const isSelected = (t.id === currentTargetId) ? "selected" : "";
        optionsHtml += `<option value="${t.id}" data-slug="${t.slug}" data-name="${t.name}" ${isSelected}>${t.label}</option>`;
    });

    selector.innerHTML = optionsHtml;
}

// ==========================================
// 4. CORE ENGINE: RENDER SCORECARD
// ==========================================
function renderTeamPage() {
    const captureArea = document.getElementById("capture-area");
    if (!captureArea) return;

    const theme = TEAM_THEMES[currentTargetId] || { name: currentTargetName, paperBg: "#f4f1ea", paperLine: "rgba(0,0,0,0.2)", markerInk: "#111" };
    document.documentElement.style.setProperty('--paper-bg', theme.paperBg);
    document.documentElement.style.setProperty('--paper-line', theme.paperLine);
    document.documentElement.style.setProperty('--marker-ink', theme.markerInk);

    let targetGame = null;
    let targetSide = null;
    let isDoubleHeader = false;
    let gameNum = 1;

    if (dailySlateData && dailySlateData.games) {
        let game1 = null;
        let game2 = null;

        // 1. Explicitly isolate Today's Game 1 and Game 2 by their true MLB game numbers
        for (const g of dailySlateData.games) {
            const raw = g.gameRaw || {};
            if (raw.teams?.away?.team?.id === currentTargetId || raw.teams?.home?.team?.id === currentTargetId) {
                const gNum = raw.gameNumber || 1;
                
                if (gNum === 1 && !game1) {
                    game1 = g;
                } else if (gNum === 2 && !game2) {
                    game2 = g;
                }
            }
        }

        // 2. Doubleheader Auto-Flip Routing Logic
        if (game1) {
            targetGame = game1;
            targetSide = targetGame.gameRaw.teams?.away?.team?.id === currentTargetId ? 'away' : 'home';
            gameNum = 1;

            if (game2) {
                isDoubleHeader = true;
                const status1 = game1.gameRaw?.status?.abstractGameState || "";
                
                if (status1 === "Final" || status1 === "Game Over") {
                    targetGame = game2;
                    targetSide = targetGame.gameRaw.teams?.away?.team?.id === currentTargetId ? 'away' : 'home';
                    gameNum = 2;
                }
            }
        } else if (game2) {
            targetGame = game2;
            targetSide = targetGame.gameRaw.teams?.away?.team?.id === currentTargetId ? 'away' : 'home';
            gameNum = 2;
        }
    }

    // OFF-DAY FALLBACK
    if (!targetGame || !targetSide) {
        captureArea.innerHTML = `
            <div style="max-width: 550px; margin: 30px auto; background: var(--paper-bg); border: 2px dashed var(--marker-ink); border-radius: 10px; padding: 35px 20px; text-align: center; font-family: 'Montserrat', sans-serif; color: #222; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
                <img src="https://www.mlbstatic.com/team-logos/${currentTargetId}.svg" style="height: 70px; margin-bottom: 12px; opacity: 0.8;">
                <h1 style="font-family: 'Bebas Neue', cursive; font-size: 32px; color: var(--marker-ink); margin: 0;">NO GAME SCHEDULED TODAY</h1>
                <p style="font-size: 14px; color: #555; margin-top: 8px;">The ${currentTargetName} have an off-day or their game has been postponed.</p>
                <a href="/" style="display: inline-block; margin-top: 18px; background: var(--marker-ink); color: #fff; padding: 8px 18px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 12px;">View Full Slate &rarr;</a>
            </div>
        `;
        return;
    }

    const raw = targetGame.gameRaw || {};
    const oppSide = targetSide === 'away' ? 'home' : 'away';
    const oppTeamObj = raw.teams?.[oppSide]?.team || { name: "Opponent" };
    const tracking = targetGame.lineupTracking?.[targetSide] || {};
    const projData = targetGame.projectedLineups?.[targetSide] || {};
    
    const posMap = targetGame.gamePositions || {};
    const handMap = targetGame.lineupHandedness || {};

    const shortName = getShortTeamName(currentTargetName, raw.teams?.[targetSide]?.team?.teamName);
    const oppShortName = getShortTeamName(oppTeamObj.name, oppTeamObj.teamName);

    const gameDateRaw = raw.officialDate || new Date().toISOString().split('T')[0];
    const [yy, mm, dd] = gameDateRaw.split('-');
    const dObj = new Date(yy, mm - 1, dd);
    let displayDate = dObj.toLocaleDateString('en-US', { weekday: 'short', month: 'long', day: 'numeric' }).toUpperCase();
    
    if (isDoubleHeader) {
        displayDate += ` &nbsp;•&nbsp; <span style="color: #ff1744;">GAME ${gameNum}</span>`;
    }
    
    const status = tracking.status || "NONE";
    let badgeHtml = "";
    if (status === "OFFICIAL") {
        const timeStr = tracking.officialAt ? ` (${tracking.officialAt})` : "";
        badgeHtml = `<span style="background: #00e676; color: #000; font-weight: 800; font-size: 10px; padding: 3px 8px; border-radius: 20px; letter-spacing: 0.5px; display: inline-block; box-shadow: 0 0 8px rgba(0, 230, 118, 0.4);">✓ OFFICIAL STARTING 9${timeStr}</span>`;
    } else if (status === "MODIFIED") {
        badgeHtml = `<span style="background: #ff1744; color: #fff; font-weight: 800; font-size: 10px; padding: 3px 8px; border-radius: 20px; letter-spacing: 0.5px; display: inline-block; box-shadow: 0 0 8px rgba(255, 23, 68, 0.4);">🚨 MODIFIED / LATE SCRATCH</span>`;
    } else {
        badgeHtml = `<span style="background: #ffb300; color: #000; font-weight: 800; font-size: 10px; padding: 3px 8px; border-radius: 20px; letter-spacing: 0.5px; display: inline-block;">⏳ PROJECTED BATTING ORDER</span>`;
    }

    const vsSymbol = targetSide === 'away' ? `@ ${oppShortName}` : `vs ${oppShortName}`;
    const venueName = raw.venue?.name || "Stadium";
    let oddsStr = "";
    if (targetGame.odds && targetGame.odds.moneyline) {
        const ml = targetGame.odds.moneyline[targetSide];
        const mlFormat = ml > 0 ? `+${ml}` : ml;
        const ou = targetGame.odds.overUnder ? ` • O/U ${targetGame.odds.overUnder}` : "";
        if (ml) oddsStr = `<div style="font-family: 'Roboto Mono', monospace; font-size: 11px; color: #555; margin-top: 3px;">Vegas Line: ${mlFormat}${ou}</div>`;
    }

    // 4. BUILD COMPACT VISUAL CARD 
    let cardHtml = `
        <div style="max-width: 580px; width: 94%; margin: 15px auto; background: var(--paper-bg); border-radius: 10px; padding: 18px 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.7), inset 0 0 30px rgba(0,0,0,0.03); position: relative; overflow: hidden; border: 1px solid #bbb; color: var(--marker-ink); box-sizing: border-box;">
            
            <img src="https://www.mlbstatic.com/team-logos/${currentTargetId}.svg" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 420px; height: 420px; object-fit: contain; opacity: 0.09; pointer-events: none; z-index: 0;">

            <div style="display: flex; align-items: center; gap: 14px; border-bottom: 2.5px solid var(--marker-ink); padding-bottom: 12px; margin-bottom: 10px; position: relative; z-index: 1;">
                <img src="https://www.mlbstatic.com/team-logos/${currentTargetId}.svg" alt="${currentTargetName} Logo" style="height: 56px; width: 56px; filter: drop-shadow(1px 3px 4px rgba(0,0,0,0.2)); flex-shrink: 0;">
                <div style="overflow: hidden; width: 100%;">
                    
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 2px;">
                        ${badgeHtml}
                        <span style="font-family: 'Montserrat', sans-serif; font-size: 10px; font-weight: 700; color: #666; letter-spacing: 0.5px;">${displayDate}</span>
                    </div>

                    <h1 style="font-family: 'Permanent Marker', cursive; font-size: clamp(26px, 7vw, 38px); color: var(--marker-ink); margin: 0; line-height: 0.95; letter-spacing: 0.5px; text-transform: uppercase; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${shortName}</h1>
                    
                    <div style="font-family: 'Caveat', cursive; font-size: clamp(16px, 4vw, 19px); color: #4a4f58; font-weight: 700; margin-top: 2px;">${vsSymbol} <span style="font-family: 'Montserrat', sans-serif; font-size: 11px; font-weight: 600; color: #777;">| ${venueName}</span></div>
                    ${oddsStr}
                </div>
            </div>

            <div style="position: relative; z-index: 1;">
                <div style="font-family: 'Montserrat', sans-serif; font-size: 10px; text-transform: uppercase; color: #666; font-weight: 700; letter-spacing: 1px; margin-bottom: 4px; border-bottom: 1px dashed var(--paper-line); padding-bottom: 3px;">Batting Order</div>
    `;

    // 🛡️ THE LINEUP SOURCE FIX: If official, grab the official lineup. Otherwise, grab projections.
    const isOfficial = (status === "OFFICIAL" || status === "MODIFIED");
    const batters = (isOfficial && raw.lineups && raw.lineups[`${targetSide}Players`]) 
        ? raw.lineups[`${targetSide}Players`] 
        : (projData.battingOrder || []);

    if (batters.length === 0) {
        cardHtml += `<div style="padding: 15px; text-align: center; font-family: 'Montserrat', sans-serif; color: #666; font-style: italic;">Batting order not populated yet.</div>`;
    } else {
        batters.forEach((b, idx) => {
            const playerName = b.name || b.fullName || "Unknown";
            const pos = posMap[b.id] || posMap[String(b.id)] || b.fd_positions || b.dk_positions || "DH";
            const hand = handMap[b.id] || handMap[String(b.id)] || b.hand || "";
            const handDisplay = hand ? `(${hand}) ` : "";
            const headshot = getHeadshotUrl(b.id);
            
            cardHtml += `
                <div style="display: flex; align-items: center; border-bottom: 1px solid var(--paper-line); height: 42px; position: relative; z-index: 2; transition: background 0.15s; padding: 0 4px;" onmouseover="this.style.background='rgba(0,0,0,0.03)'" onmouseout="this.style.background='transparent'">
                    
                    <div style="width: 32px; height: 100%; display: flex; justify-content: center; align-items: center; border-right: 1px solid var(--paper-line); font-family: 'Permanent Marker', cursive; font-size: 17px; color: var(--marker-ink); flex-shrink: 0;">
                        ${idx + 1}
                    </div>
                    
                    <div style="width: 44px; height: 100%; display: flex; justify-content: center; align-items: center; border-right: 1px solid var(--paper-line); flex-shrink: 0;">
                        <div style="width: 32px; height: 32px; border-radius: 50%; background: #e0dcd3; overflow: hidden; border: 1.5px solid var(--marker-ink); border-radius: 255px 15px 225px 15px/15px 225px 15px 255px; display: flex; justify-content: center; align-items: center;">
                            <img src="${headshot}" style="width: 100%; height: 100%; object-fit: cover; object-position: center;" crossorigin="anonymous" onerror="this.src='https://www.mlbstatic.com/team-logos/100.svg'">
                        </div>
                    </div>
                    
                    <div style="flex-grow: 1; height: 100%; display: flex; align-items: center; padding-left: 10px; font-family: 'Permanent Marker', cursive; font-size: clamp(15px, 3.8vw, 17px); text-transform: uppercase; letter-spacing: 0.5px; color: #1a1e24; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        <span style="font-family: 'Caveat', cursive; font-size: clamp(15px, 3.8vw, 17px); color: #4a4f58; opacity: 0.85; font-weight: 700; text-transform: none;">${handDisplay}</span>${playerName}
                    </div>
                    
                    <div style="width: 50px; height: 100%; display: flex; justify-content: center; align-items: center; font-family: 'Caveat', cursive; font-size: 19px; font-weight: 700; color: #4a4f58; flex-shrink: 0;">
                        ${pos}
                    </div>

                </div>
            `;
        });
    }

    const safePitcher = getSafePitcher(targetGame, targetSide, gameNum);
    const pName = safePitcher.name;
    const pHand = safePitcher.hand ? `(${safePitcher.hand}) ` : "";
    const pHeadshot = getHeadshotUrl(safePitcher.id);

    cardHtml += `
            </div>
            
            <div style="margin-top: 12px; position: relative; z-index: 1;">
                <div style="font-family: 'Caveat', cursive; font-size: 17px; color: #4a4f58; font-weight: 700; margin-bottom: 2px; padding-left: 4px;">Starting Pitcher</div>
                
                <div style="display: flex; align-items: center; border: 1.5px solid var(--marker-ink); background-color: rgba(0,0,0,0.03); border-radius: 6px; height: 50px; overflow: hidden; box-shadow: 0 2px 6px rgba(0,0,0,0.04); padding: 0 4px;">
                    
                    <div style="width: 36px; height: 100%; display: flex; justify-content: center; align-items: center; border-right: 1px solid var(--paper-line); font-family: 'Permanent Marker', cursive; font-size: 16px; color: var(--marker-ink); background: rgba(0,0,0,0.04); flex-shrink: 0;">
                        SP
                    </div>
                    
                    <div style="width: 48px; height: 100%; display: flex; justify-content: center; align-items: center; border-right: 1px solid var(--paper-line); flex-shrink: 0;">
                        <div style="width: 36px; height: 36px; border-radius: 50%; background: #e0dcd3; overflow: hidden; border: 1.5px solid var(--marker-ink); border-radius: 255px 15px 225px 15px/15px 225px 15px 255px; display: flex; justify-content: center; align-items: center;">
                            <img src="${pHeadshot}" style="width: 100%; height: 100%; object-fit: cover; object-position: center;" crossorigin="anonymous" onerror="this.src='https://www.mlbstatic.com/team-logos/100.svg'">
                        </div>
                    </div>
                    
                    <div style="flex-grow: 1; height: 100%; display: flex; align-items: center; padding-left: 10px; font-family: 'Permanent Marker', cursive; font-size: clamp(16px, 4vw, 18px); text-transform: uppercase; letter-spacing: 0.5px; color: #1a1e24; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        <span style="font-family: 'Caveat', cursive; font-size: clamp(16px, 4vw, 18px); color: #4a4f58; opacity: 0.85; font-weight: 700; text-transform: none;">${pHand}</span>${pName}
                    </div>
                    
                    <div style="width: 50px; height: 100%; display: flex; justify-content: center; align-items: center; font-family: 'Caveat', cursive; font-size: 19px; font-weight: 700; color: #4a4f58; flex-shrink: 0;">
                        SP
                    </div>

                </div>
            </div>

        </div>
    `;

    captureArea.innerHTML = cardHtml;

    // Pass the active batters array to keep the Analytics synced with the display
    renderAnalyticsSection(targetGame, targetSide, batters, gameNum);
}

// ==========================================
// 5. DYNAMIC TEAM SWITCHING
// ==========================================
function handleTeamSwitch(selectElement) {
    const selectedOption = selectElement.options[selectElement.selectedIndex];
    if (!selectedOption || !selectedOption.value) return;

    const newId = parseInt(selectedOption.value);
    const newSlug = selectedOption.getAttribute("data-slug");
    const newName = selectedOption.getAttribute("data-name");

    currentTargetId = newId;
    currentTargetSlug = newSlug;
    currentTargetName = newName;
    window.TARGET_TEAM_ID = newId;
    window.TARGET_TEAM_SLUG = newSlug;
    window.TARGET_TEAM_NAME = newName;

    const newUrl = `/lineups/${newSlug}/`;
    window.history.pushState({ teamId: newId }, "", newUrl);
    
    document.title = `${newName} Starting Lineup Today | Batting Order & Pitcher`;
    renderTeamPage();
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
        147: "new-york-yankees"
    };
    return slugMap[id] || "los-angeles-dodgers";
}

// ==========================================
// 6. RENDER ADVANCED ANALYTICS SECTION
// ==========================================
function renderAnalyticsSection(targetGame, targetSide, batters, gameNum) {
    const container = document.getElementById("public-analytics-section");
    if (!container) return;

    if (!targetGame || !targetGame.deepStats) {
        container.innerHTML = "";
        return;
    }

    const deepStats = targetGame.deepStats || {};
    const umpStats = targetGame.umpStats || {};
    const parkStats = targetGame.parkStats || {};
    
    // Identify Opposing Pitcher using safe doubleheader logic
    const oppSide = targetSide === 'away' ? 'home' : 'away';
    const oppPitcher = getSafePitcher(targetGame, oppSide, gameNum);
    const pStats = oppPitcher.id ? deepStats[oppPitcher.id] : null;
    const pitcherHand = oppPitcher.hand || 'R'; 
    
    // --- CSS STYLES FOR THE DATA VAULT ---
    const tableCSS = `
        <style>
            .stat-container { max-width: 580px; width: 94%; margin: 10px auto 40px auto; font-family: 'Montserrat', sans-serif; }
            .stat-card { background: #1a1d24; border: 1px solid #2d323b; border-radius: 10px; margin-bottom: 25px; overflow: hidden; box-shadow: 0 8px 20px rgba(0,0,0,0.4); }
            .stat-header { background: #22262e; padding: 12px 15px; border-bottom: 2px solid var(--marker-ink, #444); color: #fff; font-weight: 700; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; display: flex; align-items: center; justify-content: space-between; }
            .stat-table { width: 100%; border-collapse: collapse; color: #ddd; font-size: 12px; }
            .stat-table th { background: #15171c; padding: 10px; text-align: center; color: #8892a3; font-weight: 600; text-transform: uppercase; font-size: 10px; border-bottom: 1px solid #2d323b; }
            .stat-table th:first-child, .stat-table td:first-child { text-align: left; padding-left: 15px; font-weight: 600; color: #fff; }
            .stat-table td { padding: 10px; text-align: center; border-bottom: 1px solid #252933; }
            .stat-table tr:last-child td { border-bottom: none; }
            .stat-table tr:hover { background: rgba(255,255,255,0.03); }
            .highlight-text { color: #00e676; font-weight: 700; }
            .env-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; padding: 15px; }
            .env-box { background: #15171c; border-radius: 8px; padding: 12px; border: 1px solid #252933; }
            .env-title { font-size: 10px; color: #8892a3; text-transform: uppercase; font-weight: 700; margin-bottom: 8px; border-bottom: 1px solid #2d323b; padding-bottom: 4px; }
            .env-row { display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px; color: #ddd; }
        </style>
    `;

    // 1. BUILD DFS TABLE
    let dfsRows = '';
    batters.forEach(b => {
        const playerName = b.name || b.fullName || "Unknown";
        const fdSal = b.salary ? `$${b.salary}` : '-';
        const fdProj = b.proj ? parseFloat(b.proj).toFixed(1) : '-';
        const dkSal = b.dk_salary ? `$${b.dk_salary}` : '-';
        const dkProj = b.dk_proj ? parseFloat(b.dk_proj).toFixed(1) : '-';
        const pos = b.fd_positions || b.dk_positions || 'FLEX';
        
        dfsRows += `<tr>
            <td>${playerName}</td>
            <td style="color: #8892a3;">${pos}</td>
            <td>${fdSal}</td>
            <td class="highlight-text">${fdProj}</td>
            <td>${dkSal}</td>
            <td class="highlight-text">${dkProj}</td>
        </tr>`;
    });

    // 2. BUILD PITCHER TABLE
    let pitcherHtml = '';
    if (pStats) {
        const vL = pStats.split_vL || {};
        const vR = pStats.split_vR || {};
        const season = pStats.season || {};
        pitcherHtml = `
        <div class="stat-card">
            <div class="stat-header">Opposing Pitcher: ${oppPitcher.name || 'TBD'}</div>
            <table class="stat-table">
                <thead><tr><th>Split</th><th>AVG</th><th>OPS</th><th>HR</th><th>K</th></tr></thead>
                <tbody>
                    <tr>
                        <td>vs LHB</td>
                        <td>${vL.avg || '-'}</td>
                        <td class="${vL.ops > '.750' ? 'highlight-text' : ''}">${vL.ops || '-'}</td>
                        <td>${vL.hr || '-'}</td>
                        <td>${vL.k || '-'}</td>
                    </tr>
                    <tr>
                        <td>vs RHB</td>
                        <td>${vR.avg || '-'}</td>
                        <td class="${vR.ops > '.750' ? 'highlight-text' : ''}">${vR.ops || '-'}</td>
                        <td>${vR.hr || '-'}</td>
                        <td>${vR.k || '-'}</td>
                    </tr>
                </tbody>
            </table>
            <div style="background: #15171c; padding: 10px 15px; font-size: 11px; color: #8892a3; border-top: 1px solid #2d323b; display: flex; gap: 15px; justify-content: center;">
                <span><strong>SEASON:</strong></span>
                <span>${season.ip || 0} IP</span>
                <span>${season.era || '-'} ERA</span>
                <span>${season.whip || '-'} WHIP</span>
                <span>${season.k || '-'} SO</span>
            </div>
        </div>`;
    } else {
        pitcherHtml = `
        <div class="stat-card">
            <div class="stat-header">Opposing Pitcher: TBD / Bullpen Game</div>
            <div style="padding: 20px; text-align: center; color: #8892a3; font-size: 13px;">Advanced split stats will populate once an official starting pitcher is announced.</div>
        </div>`;
    }

    // 3. BUILD BATTER SPLITS TABLE
    let splitRows = '';
    batters.forEach(b => {
        const playerName = b.name || b.fullName || "Unknown";
        const bStats = deepStats[b.id] || {};
        const splitData = pitcherHand === 'L' ? (bStats.split_vL || {}) : (bStats.split_vR || {});
        const ops = splitData.ops || '-';
        const bvp = bStats.bvp || {};
        const bvpAb = bvp.ab !== undefined ? bvp.ab : '-';
        const bvpAvg = bvp.avg || '-';
        const bvpHr = bvp.hr !== undefined ? bvp.hr : '-';
        
        splitRows += `<tr>
            <td>${playerName}</td>
            <td class="${ops > '.800' ? 'highlight-text' : ''}">${ops}</td>
            <td>${bvpAb}</td>
            <td>${bvpAvg}</td>
            <td style="color: ${bvpHr > 0 ? '#ff1744' : 'inherit'}; font-weight: ${bvpHr > 0 ? '700' : '400'};">${bvpHr}</td>
        </tr>`;
    });

    // 4. BUILD ENVIRONMENT HTML
    const envHtml = `
    <div class="stat-card">
        <div class="stat-header">Game Environment</div>
        <div class="env-grid">
            <div class="env-box">
                <div class="env-title">Park Factors (100 = Avg)</div>
                <div class="env-row"><span>Runs:</span> <span class="${parkStats.runs > 102 ? 'highlight-text' : ''}">${parkStats.runs || '-'}</span></div>
                <div class="env-row"><span>HR (LHB):</span> <span>${parkStats.hr_l || '-'}</span></div>
                <div class="env-row"><span>HR (RHB):</span> <span>${parkStats.hr_r || '-'}</span></div>
            </div>
            <div class="env-box">
                <div class="env-title">Umpire: ${targetGame.hpUmpire || 'TBD'}</div>
                <div class="env-row"><span>K Rate:</span> <span>${umpStats.k_rate || '-'}</span></div>
                <div class="env-row"><span>BB Rate:</span> <span>${umpStats.bb_rate || '-'}</span></div>
                <div class="env-row"><span>Runs/Game:</span> <span>${umpStats.rpg || '-'}</span></div>
            </div>
        </div>
    </div>`;

    // INJECT INTO DOM
    container.innerHTML = tableCSS + `
    <div class="stat-container">
        <div class="stat-card">
            <div class="stat-header">DFS Projections & Pricing</div>
            <table class="stat-table">
                <thead><tr><th>Batter</th><th>Pos</th><th>FD $</th><th>FD Proj</th><th>DK $</th><th>DK Proj</th></tr></thead>
                <tbody>${dfsRows}</tbody>
            </table>
        </div>
        ${pitcherHtml}
        <div class="stat-card">
            <div class="stat-header">Batter Splits & BvP</div>
            <table class="stat-table">
                <thead><tr><th>Batter</th><th>vs ${pitcherHand}HP (OPS)</th><th>BvP AB</th><th>BvP AVG</th><th>BvP HR</th></tr></thead>
                <tbody>${splitRows}</tbody>
            </table>
        </div>
        ${envHtml}
    </div>
    `;
}
