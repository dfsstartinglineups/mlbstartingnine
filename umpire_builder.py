import pybaseball as pyb
import pandas as pd
import requests
import json
import os
from datetime import datetime, timedelta

# Enable caching to prevent re-fetching the same data on retries
pyb.cache.enable()

def get_date_chunks(start_date, end_date, chunk_days=30):
    """Break the date range into smaller chunks to prevent Statcast timeouts."""
    curr = start_date
    while curr < end_date:
        next_date = min(curr + timedelta(days=chunk_days), end_date)
        yield curr.strftime('%Y-%m-%d'), next_date.strftime('%Y-%m-%d')
        curr = next_date + timedelta(days=1)

def build_umpire_json():
    today = datetime.today()
    start_dt_obj = today - timedelta(days=365)
    
    all_chunks = []
    
    # 1. Fetch data in chunks to avoid "ParserError" / Timeouts
    print(f"Fetching 365 days of data in monthly chunks...")
    for s, e in get_date_chunks(start_dt_obj, today):
        try:
            print(f"  Pulling: {s} to {e}")
            chunk_df = pyb.statcast(s, e)
            if not chunk_df.empty:
                all_chunks.append(chunk_df)
        except Exception as err:
            print(f"  Error pulling {s} to {e}: {err}. Skipping chunk.")

    if not all_chunks:
        print("No data retrieved. Exiting.")
        return

    df = pd.concat(all_chunks, ignore_index=True)
    
    # 2. Filter to only the final pitch of each at-bat
    at_bats = df.dropna(subset=['events'])
    
    # 3. Calculate K's and BB's per game
    print("Calculating metrics...")
    game_data = at_bats.groupby('game_pk').agg(
        total_pa=('events', 'count'),
        strikeouts=('events', lambda x: x.isin(['strikeout', 'strikeout_double_play']).sum()),
        walks=('events', lambda x: (x == 'walk').sum())
    ).reset_index()
    
    umpire_dict = {}
    
    # 4. Map game_pk to the Home Plate Umpire via MLB API
    print(f"Mapping {len(game_data)} games to umpires...")
    for game_pk in game_data['game_pk'].unique():
        try:
            url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
            res = requests.get(url, timeout=10).json()
            
            officials = res.get('liveData', {}).get('boxscore', {}).get('officials', [])
            hp_umpire = next((o['official']['fullName'] for o in officials if o['officialType'] == 'Home Plate'), None)
            
            linescore = res.get('liveData', {}).get('linescore', {})
            away_runs = linescore.get('teams', {}).get('away', {}).get('runs', 0)
            home_runs = linescore.get('teams', {}).get('home', {}).get('runs', 0)
            total_runs = away_runs + home_runs
            
            if hp_umpire:
                if hp_umpire not in umpire_dict:
                    umpire_dict[hp_umpire] = {'games': 0, 'pa': 0, 'k': 0, 'bb': 0, 'runs': 0}
                
                game_row = game_data[game_data['game_pk'] == game_pk].iloc[0]
                umpire_dict[hp_umpire]['games'] += 1
                umpire_dict[hp_umpire]['pa'] += int(game_row['total_pa'])
                umpire_dict[hp_umpire]['k'] += int(game_row['strikeouts'])
                umpire_dict[hp_umpire]['bb'] += int(game_row['walks'])
                umpire_dict[hp_umpire]['runs'] += total_runs
                
        except Exception:
            continue

    # 5. Calculate Final Rates
    final_output = {}
    for ump, stats in umpire_dict.items():
        if stats['games'] > 0 and stats['pa'] > 0:
            k_rate = (stats['k'] / stats['pa']) * 100
            bb_rate = (stats['bb'] / stats['pa']) * 100
            rpg = stats['runs'] / stats['games']
            
            final_output[ump] = {
                "k_rate": f"{k_rate:.1f}%",
                "bb_rate": f"{bb_rate:.1f}%",
                "rpg": f"{rpg:.1f}",
                "games": stats['games']
            }

    os.makedirs('data', exist_ok=True)
    with open('data/umpires.json', 'w') as f:
        json.dump({"umpires": final_output}, f, indent=4)
        
    print(f"Success! Processed {len(final_output)} umpires.")

if __name__ == "__main__":
    build_umpire_json()
