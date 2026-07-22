import os
import json
import requests
from datetime import datetime, timedelta, timezone

# ==========================================
# 1. CONFIGURATION
# ==========================================
QUEUE_FILE = "data/updates_queue.json"
DOMAIN = "mlbstartingnine.com"
BASE_URL = f"https://{DOMAIN}"
# Best practice is to pass the key from GitHub Secrets, but you can hardcode it here for now
INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY", "a8b4b6ed5a834ae88b5fc7a614662a4d") 
COOLDOWN_MINUTES = 10

def main():
    if not os.path.exists(QUEUE_FILE):
        print("Queue file not found. Nothing to ping.")
        return

    # Load the queue safely
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            queue_data = json.load(f)
    except Exception as e:
        print(f"Error reading queue: {e}")
        return

    last_sent_str = queue_data.get("last_sent", "2000-01-01T00:00:00")
    queued_urls = queue_data.get("urls", [])

    # Ensure uniqueness to avoid duplicate array items
    unique_urls = list(set(queued_urls))

    # ==========================================
    # 2. TIME COOLDOWN CHECK
    # ==========================================
    try:
        last_sent_time = datetime.fromisoformat(last_sent_str).replace(tzinfo=timezone.utc)
    except ValueError:
        last_sent_time = datetime(2000, 1, 1, tzinfo=timezone.utc)

    now_utc = datetime.now(timezone.utc)
    time_since_last = now_utc - last_sent_time

    if time_since_last < timedelta(minutes=COOLDOWN_MINUTES):
        print(f"Cooldown active. Last sent {time_since_last.total_seconds() / 60:.1f} minutes ago. Waiting for 10-minute threshold.")
        return

    if not unique_urls:
        print("10-minute threshold passed, but no URLs in the queue. Updating timestamp.")
        queue_data["last_sent"] = now_utc.isoformat(timespec='seconds')
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue_data, f, indent=2)
        return

    # ==========================================
    # 3. INDEXNOW API POST (BING/YAHOO/YANDEX)
    # ==========================================
    indexnow_payload = {
        "host": DOMAIN,
        "key": INDEXNOW_KEY,
        "keyLocation": f"https://{DOMAIN}/{INDEXNOW_KEY}.txt",
        "urlList": unique_urls
    }

    print(f"🚀 Pinging IndexNow with {len(unique_urls)} URLs...")
    print(f"📦 Payload being sent:\n{json.dumps(indexnow_payload, indent=2)}")

    headers = {"Content-Type": "application/json; charset=utf-8"}
    try:
        response = requests.post("https://api.indexnow.org/indexnow", json=indexnow_payload, headers=headers, timeout=10)
        print(f"✅ IndexNow Response Code: {response.status_code}")
        
        if response.status_code not in [200, 202]:
            print(f"⚠️ IndexNow Response Text: {response.text}")
    except Exception as e:
        print(f"❌ Error pinging IndexNow: {e}")

    # ==========================================
    # 4. CLEAR QUEUE & SAVE TIMESTAMP
    # ==========================================
    queue_data["last_sent"] = now_utc.isoformat(timespec='seconds')
    queue_data["urls"] = []  # Empty the queue now that they are sent

    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue_data, f, indent=2)
    
    print("Queue cleared and timestamp updated.")

if __name__ == "__main__":
    main()
