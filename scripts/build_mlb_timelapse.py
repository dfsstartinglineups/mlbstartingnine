import os
import asyncio
import http.server
import socketserver
import threading
from datetime import datetime
from playwright.async_api import async_playwright
from moviepy.editor import VideoFileClip

# ==========================================
# CONFIGURATION & INPUTS
# ==========================================
TEAM_ID = os.environ.get("TEAM_ID", "147")
START_DATE = os.environ.get("START_DATE", "2026-04-01")
END_DATE = os.environ.get("END_DATE", "2026-05-01")
OUTPUT_DIR = "videos"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==========================================
# LOCAL HTTP SERVER
# ==========================================
# Playwright blocks local JSON fetching due to CORS security.
# We spin up a silent local server to serve the HTML and data directory.
def start_server():
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Suppress HTTP logging
    httpd = socketserver.TCPServer(("", 8080), QuietHandler)
    httpd.serve_forever()

# ==========================================
# PLAYWRIGHT AUTOMATION
# ==========================================
async def record_mlb_timelapse():
    # Calculate exactly how long to record based on 1 second per day
    d1 = datetime.strptime(START_DATE, "%Y-%m-%d")
    d2 = datetime.strptime(END_DATE, "%Y-%m-%d")
    days = (d2 - d1).days + 1
    
    # 1 second per frame + 4 seconds buffer to allow data to compile
    wait_time = (days * 1.0) + 4.0 
    
    print(f"🎥 Recording {days} days of MLB lineups (Waiting {wait_time}s)...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1080, 'height': 1350},
            record_video_dir=OUTPUT_DIR,
            record_video_size={"width": 1080, "height": 1350}
        )
        page = await context.new_page()
        
        # Navigate to the local server
        await page.goto("http://localhost:8080/mlb_animation.html", wait_until="networkidle")
        
        # Hide the UI controls so they don't appear in the final MP4
        await page.evaluate("""
            const controls = document.getElementById('controls');
            if(controls) { controls.style.display = 'none'; }
        """)

        # Inject the GitHub Action parameters directly into the DOM and trigger the function
        await page.evaluate(f"""
            document.getElementById('team-selector').value = '{TEAM_ID}';
            document.getElementById('start-date').value = '{START_DATE}';
            document.getElementById('end-date').value = '{END_DATE}';
            runTimelapse();
        """)
        
        # Wait for the entire animation to play out
        await asyncio.sleep(wait_time)
        
        video_path = await page.video.path()
        await context.close()
        await browser.close()
        
        return video_path

# ==========================================
# EXECUTION
# ==========================================
if __name__ == "__main__":
    # Start the local server in the background
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Run the headless browser recording
    raw_webm = asyncio.run(record_mlb_timelapse())
    
    # Convert Playwright's default WebM to standard MP4
    print("🎬 Converting WebM to MP4...")
    final_output = os.path.join(OUTPUT_DIR, f"mlb_timelapse_{TEAM_ID}_{START_DATE}_to_{END_DATE}.mp4")
    
    clip = VideoFileClip(raw_webm)
    clip.write_videofile(final_output, codec="libx264", audio=False, fps=30, logger=None)
    clip.close()
    
    # Clean up the raw webm file
    if os.path.exists(raw_webm):
        os.remove(raw_webm)
        
    print(f"🏆 Final MLB Timelapse Video ready: {final_output}")
