/**
 * ============================================================================
 * MLB STARTING 9 - MASTER TEAM LINEUP ENGINE (mlb_starting_lineup.js)
 * Fully upgraded with visual dugout card aesthetics, headshots, and centered watermark.
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

// Helper: Get Official MLB Headshot Image
function getHeadshotUrl(personId) {
    if (!personId) return "https://www.mlbstatic.com/team-logos/100.svg";
    return `https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/${personId}/headshot/67/current`;
}

// ==========================================
// 2. INITIALIZATION
// ==========================================
document.addEventListener("DOMContentLoaded", async () => {
    buildHeaderAndFooter();
    
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const todayStr = `${year}-${month}-${day}`;

    try {
        const res = await fetch(`../../data/games_${todayStr}.json?v=${now.getTime()}`);
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
            <header style="background: #121212; border-bottom: 1px solid #222; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
                <div style="display: flex; align-items: center; gap: 15px;">
                    <a href="../../index.html" style="text-decoration: none; display: flex; align-items: center; gap: 10px;">
                        <img src="../../logo.webp" alt="MLB Starting 9 Logo" style="height: 40px; width: auto; border-radius: 6px;" onerror="this.style.display='none'">
                        <div>
                            <span style="font-family: 'Bebas Neue', cursive; font-size: 26px; color: #fff; letter-spacing: 1px; line-height: 1;">MLB STARTING 9</span>
                            <div style="font-family: 'Montserrat', sans-serif; font-size: 10px; color: #00e676; font-weight: 700; letter-spacing: 0.5px;">DAILY FANTASY STATS & LINEUPS</div>
                        </div>
                    </a>
                </div>
                
                <div style="display: flex; align-items: center; gap: 15px;">
                    <a href="../../index.html" style="font-family: 'Montserrat', sans-serif; font-size: 13px; color: #aaa; text-decoration: none; border: 1px solid #333; padding: 8px 14px; border-radius: 6px; transition: all 0.2s;" onmouseover="this.style.borderColor='#00e676'; this.style.color='#fff'" onmouseout="this.style.borderColor='#333'; this.style.color='#aaa'">
                        &larr; Back to Daily Slate
                    </a>
                    
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <label for="team-selector" style="font-family: 'Montserrat', sans-serif; font-size: 12px; color: #888; text-transform: uppercase; font-weight: 600;">Switch Team:</label>
                        <select id="team-selector" onchange="handleTeamSwitch(this)" style="background: #1e1e1e; color: #fff; border: 1px solid #444; padding: 8px 12px; border-radius: 6px; font-family: 'Montserrat', sans-serif; font-size: 13px; outline: none; cursor: pointer;">
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
            <footer style="background: #0a0a0a; border-top: 1px solid #1a1a1a; padding: 30px 20px; text-align: center; margin-top: 50px; font-family: 'Montserrat', sans-serif;">
                <p style="color: #666; font-size: 12px; margin: 0 0 10px 0;">
                    &copy; ${new Date().getFullYear()} MLB Starting 9. All rights reserved. Data updated in real-time from official MLB sources.
                </p>
                <p style="color: #444; font-size: 11px; max-width: 600px; margin: 0 auto; line-height: 1.5;">
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

    dailySlateData.games.forEach(game => {
        const raw = game.gameRaw || {};
        const tracking = game.lineupTracking || {};
        
        ['away', 'home'].forEach(side => {
            const teamObj = raw.teams?.[side]?.team;
            if (!teamObj) return;

            const status = tracking[side]?.status || "NONE";
            const badge = (status === "OFFICIAL" || status === "MODIFIED") ? "✓ OFFICIAL" : "⏳ PROJ";
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

    if (dailySlateData && dailySlateData.games) {
        for (const g of dailySlateData.games) {
            const raw = g.gameRaw || {};
            if (raw.teams?.away?.team?.id === currentTargetId) {
                targetGame = g;
                targetSide = 'away';
                break;
            } else if (raw.teams?.home?.team?.id === currentTargetId) {
                targetGame = g;
                targetSide = 'home';
                break;
            }
        }
    }

    // OFF-DAY FALLBACK
    if (!targetGame || !targetSide) {
        captureArea.innerHTML = `
            <div style="max-width: 600px; margin: 40px auto; background: var(--paper-bg); border: 2px dashed var(--marker-ink); border-radius: 12px; padding: 40px 20px; text-align: center; font-family: 'Montserrat', sans-serif; color: #222; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                <img src="https://www.mlbstatic.com/team-logos/${currentTargetId}.svg" style="height: 80px; margin-bottom: 15px; opacity: 0.8;">
                <h1 style="font-family: 'Bebas Neue', cursive; font-size: 36px; color: var(--marker-ink); margin: 0;">NO GAME SCHEDULED TODAY</h1>
                <p style="font-size: 15px; color: #555; margin-top: 10px;">The ${currentTargetName} have an off-day or their game has been postponed.</p>
                <a href="../../index.html" style="display: inline-block; margin-top: 20px; background: var(--marker-ink); color: #fff; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 13px;">View Full MLB Slate &rarr;</a>
            </div>
        `;
        return;
    }

    const raw = targetGame.gameRaw || {};
    const oppSide = targetSide === 'away' ? 'home' : 'away';
    const oppTeamObj = raw.teams?.[oppSide]?.team || { name: "Opponent" };
    const tracking = targetGame.lineupTracking?.[targetSide] || {};
    const projData = targetGame.projectedLineups?.[targetSide] || {};
    
    // Status Badge Logic
    const status = tracking.status || "NONE";
    let badgeHtml = "";
    if (status === "OFFICIAL") {
        const timeStr = tracking.officialAt ? ` (${tracking.officialAt})` : "";
        badgeHtml = `<span style="background: #00e676; color: #000; font-weight: 800; font-size: 11px; padding: 4px 10px; border-radius: 20px; letter-spacing: 0.5px; display: inline-block; margin-bottom: 8px; box-shadow: 0 0 10px rgba(0, 230, 118, 0.4);">✓ OFFICIAL STARTING 9${timeStr}</span>`;
    } else if (status === "MODIFIED") {
        badgeHtml = `<span style="background: #ff1744; color: #fff; font-weight: 800; font-size: 11px; padding: 4px 10px; border-radius: 20px; letter-spacing: 0.5px; display: inline-block; margin-bottom: 8px; box-shadow: 0 0 10px rgba(255, 23, 68, 0.4);">🚨 LINEUP MODIFIED / LATE SCRATCH</span>`;
    } else {
        badgeHtml = `<span style="background: #ffb300; color: #000; font-weight: 800; font-size: 11px; padding: 4px 10px; border-radius: 20px; letter-spacing: 0.5px; display: inline-block; margin-bottom: 8px;">⏳ PROJECTED BATTING ORDER</span>`;
    }

    const vsSymbol = targetSide === 'away' ? `@ ${oppTeamObj.name}` : `vs ${oppTeamObj.name}`;
    const venueName = raw.venue?.name || "Stadium";
    let oddsStr = "";
    if (targetGame.odds && targetGame.odds.moneyline) {
        const ml = targetGame.odds.moneyline[targetSide];
        const mlFormat = ml > 0 ? `+${ml}` : ml;
        const ou = targetGame.odds.overUnder ? ` • O/U ${targetGame.odds.overUnder}` : "";
        if (ml) oddsStr = `<div style="font-family: 'Roboto Mono', monospace; font-size: 12px; color: #444; margin-top: 4px;">Vegas Line: ${mlFormat}${ou}</div>`;
    }

    // 4. BUILD VISUAL CARD WITH CENTERED WATERMARK & RICH DUGOUT AESTHETICS
    let cardHtml = `
        <div style="max-width: 680px; margin: 20px auto; background: var(--paper-bg); border-radius: 12px; padding: 30px; box-shadow: 0 20px 40px rgba(0,0,0,0.7), inset 0 0 40px rgba(0,0,0,0.04); position: relative; overflow: hidden; border: 1px solid #ccc; color: var(--marker-ink);">
            
            <img src="https://www.mlbstatic.com/team-logos/${currentTargetId}.svg" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 520px; height: 520px; object-fit: contain; opacity: 0.04; pointer-events: none; z-index: 0;">

            <div style="display: flex; align-items: center; gap: 20px; border-bottom: 3px solid var(--marker-ink); padding-bottom: 20px; margin-bottom: 15px; position: relative; z-index: 1;">
                <img src="https://www.mlbstatic.com/team-logos/${currentTargetId}.svg" alt="${currentTargetName} Logo" style="height: 80px; width: 80px; filter: drop-shadow(2px 4px 6px rgba(0,0,0,0.2)); flex-shrink: 0;">
                <div>
                    ${badgeHtml}
                    <h1 style="font-family: 'Permanent Marker', cursive; font-size: 40px; color: var(--marker-ink); margin: 0; line-height: 0.95; letter-spacing: 1px; text-transform: uppercase;">${currentTargetName}</h1>
                    <div style="font-family: 'Caveat', cursive; font-size: 22px; color: #4a4f58; font-weight: 700; margin-top: 4px;">${vsSymbol} <span style="font-family: 'Montserrat', sans-serif; font-size: 13px; font-weight: 600; color: #777;">| ${venueName}</span></div>
                    ${oddsStr}
                </div>
            </div>

            <div style="position: relative; z-index: 1;">
                <div style="font-family: 'Montserrat', sans-serif; font-size: 11px; text-transform: uppercase; color: #666; font-weight: 700; letter-spacing: 1px; margin-bottom: 8px; border-bottom: 1px dashed var(--paper-line); padding-bottom: 4px;">Batting Order</div>
    `;

    // Populate Batting Order with Photos & Dugout Grid
    const batters = projData.battingOrder || [];
    if (batters.length === 0) {
        cardHtml += `<div style="padding: 20px; text-align: center; font-family: 'Montserrat', sans-serif; color: #666; font-style: italic;">Batting order not populated yet.</div>`;
    } else {
        batters.forEach((b, idx) => {
            const pos = b.fd_positions || b.dk_positions || "FLEX";
            const sal = b.salary ? `$${b.salary}` : "";
            const hand = b.hand ? `(${b.hand})` : "";
            const headshot = getHeadshotUrl(b.id);
            
            cardHtml += `
                <div style="display: flex; align-items: center; border-bottom: 1.5px solid var(--paper-line); height: 64px; position: relative; z-index: 2; transition: background 0.15s;" onmouseover="this.style.background='rgba(0,0,0,0.03)'" onmouseout="this.style.background='transparent'">
                    
                    <div style="width: 45px; height: 100%; display: flex; justify-content: center; align-items: center; border-right: 1.5px solid var(--paper-line); font-family: 'Permanent Marker', cursive; font-size: 24px; color: var(--marker-ink); flex-shrink: 0;">
                        ${idx + 1}
                    </div>
                    
                    <div style="width: 65px; height: 100%; display: flex; justify-content: center; align-items: center; border-right: 1.5px solid var(--paper-line); flex-shrink: 0;">
                        <div style="width: 48px; height: 48px; border-radius: 50%; background: #e0dcd3; overflow: hidden; border: 2px solid var(--marker-ink); border-radius: 255px 15px 225px 15px/15px 225px 15px 255px; display: flex; justify-content: center; align-items: center;">
                            <img src="${headshot}" style="width: 100%; height: 100%; object-fit: cover; object-position: center;" crossorigin="anonymous" onerror="this.src='https://www.mlbstatic.com/team-logos/100.svg'">
                        </div>
                    </div>
                    
                    <div style="flex-grow: 1; height: 100%; display: flex; align-items: center; padding-left: 15px; border-right: 1.5px solid var(--paper-line); font-family: 'Permanent Marker', cursive; font-size: 22px; text-transform: uppercase; letter-spacing: 0.5px; color: #1a1e24; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        <span style="font-family: 'Caveat', cursive; font-size: 20px; color: #4a4f58; opacity: 0.85; margin-right: 8px; font-weight: 700; text-transform: none;">${hand}</span>${b.name}
                    </div>
                    
                    <div style="width: 65px; height: 100%; display: flex; justify-content: center; align-items: center; font-family: 'Caveat', cursive; font-size: 24px; font-weight: 700; color: #4a4f58; border-right: 1.5px solid var(--paper-line); flex-shrink: 0;">
                        ${pos}
                    </div>

                    <div style="width: 65px; height: 100%; display: flex; justify-content: center; align-items: center; font-family: 'Roboto Mono', monospace; font-size: 13px; font-weight: 700; color: #444; flex-shrink: 0;">
                        ${sal}
                    </div>

                </div>
            `;
        });
    }

    // Starting Pitcher Section
    const pitcher = projData.startingPitcher || {};
    const pName = pitcher.name || "To Be Determined";
    const pHand = pitcher.hand ? `(${pitcher.hand})` : "";
    const pSal = pitcher.salary ? `$${pitcher.salary}` : "";
    const pHeadshot = getHeadshotUrl(pitcher.id);

    cardHtml += `
            </div>
            
            <div style="margin-top: 15px; position: relative; z-index: 1;">
                <div style="font-family: 'Caveat', cursive; font-size: 22px; color: #4a4f58; font-weight: 700; margin-bottom: 4px; padding-left: 5px;">Starting Pitcher</div>
                
                <div style="display: flex; align-items: center; border: 2px solid var(--marker-ink); background-color: rgba(0,0,0,0.03); border-radius: 8px; height: 72px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                    
                    <div style="width: 50px; height: 100%; display: flex; justify-content: center; align-items: center; border-right: 1.5px solid var(--paper-line); font-family: 'Permanent Marker', cursive; font-size: 22px; color: var(--marker-ink); background: rgba(0,0,0,0.04); flex-shrink: 0;">
                        SP
                    </div>
                    
                    <div style="width: 70px; height: 100%; display: flex; justify-content: center; align-items: center; border-right: 1.5px solid var(--paper-line); flex-shrink: 0;">
                        <div style="width: 52px; height: 52px; border-radius: 50%; background: #e0dcd3; overflow: hidden; border: 2px solid var(--marker-ink); border-radius: 255px 15px 225px 15px/15px 225px 15px 255px; display: flex; justify-content: center; align-items: center;">
                            <img src="${pHeadshot}" style="width: 100%; height: 100%; object-fit: cover; object-position: center;" crossorigin="anonymous" onerror="this.src='https://www.mlbstatic.com/team-logos/100.svg'">
                        </div>
                    </div>
                    
                    <div style="flex-grow: 1; height: 100%; display: flex; align-items: center; padding-left: 15px; border-right: 1.5px solid var(--paper-line); font-family: 'Permanent Marker', cursive; font-size: 24px; text-transform: uppercase; letter-spacing: 0.5px; color: #1a1e24; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        <span style="font-family: 'Caveat', cursive; font-size: 20px; color: #4a4f58; opacity: 0.85; margin-right: 8px; font-weight: 700; text-transform: none;">${pHand}</span>${pName}
                    </div>
                    
                    <div style="width: 65px; height: 100%; display: flex; justify-content: center; align-items: center; font-family: 'Caveat', cursive; font-size: 24px; font-weight: 700; color: #4a4f58; border-right: 1.5px solid var(--paper-line); flex-shrink: 0;">
                        SP
                    </div>

                    <div style="width: 65px; height: 100%; display: flex; justify-content: center; align-items: center; font-family: 'Roboto Mono', monospace; font-size: 13px; font-weight: 700; color: #444; flex-shrink: 0;">
                        ${pSal}
                    </div>

                </div>
            </div>

        </div>
    `;

    captureArea.innerHTML = cardHtml;
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

    const newUrl = `../../lineups/${newSlug}/`;
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
