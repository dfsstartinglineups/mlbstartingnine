import pybaseball as pyb
import pandas as pd
import requests
import json
from datetime import datetime, timedelta

def build_umpire_json():
    # 1. Smart Date Logic (Offseason vs Regular Season)
    today = datetime.today()
    
    # If we are in Jan, Feb, or March, pull the entire previous season for a baseline.
    if today.month < 4:
        start_dt = f"{today.year - 1}-03-25" 
        end_dt = f"{today.year - 1}-11-05"   
        print(f"Offseason detected. Pulling previous season data: {start_dt} to {end_dt}...")
    else:
        # If it's April or later, pull the last 90 calendar days
        start_dt = (today - timedelta(days=90)).strftime('%Y-%m-%d')
        end_dt = today.strftime('%Y-%m-%d')
        print(f"Mid-season detected. Pulling rolling 90-day data: {start_dt} to {end_dt}...")
        
    df = pyb.statcast(start_dt, end_dt)
    
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
    
    # 4. Map game_pk to the Home Plate Umpire and get actual Runs via MLB API
    print("Mapping umpires via MLB API (This takes a minute or two)...")
    for game_pk in game_data['game_pk'].unique():
        try:
            url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
            res = requests.get(url).json()
            
            # Extract Umpire
            officials = res.get('liveData', {}).get('boxscore', {}).get('officials', [])
            hp_umpire = next((o['official']['fullName'] for o in officials if o['officialType'] == 'Home Plate'), None)
            
            # Extract accurate total runs
            linescore = res.get('liveData', {}).get('linescore', {})
            away_runs = linescore.get('teams', {}).get('away', {}).get('runs', 0)
            home_runs = linescore.get('teams', {}).get('home', {}).get('runs', 0)
            total_runs = away_runs + home_runs
            
            if hp_umpire:
                if hp_umpire not in umpire_dict:
                    umpire_dict[hp_umpire] = {'games': 0, 'pa': 0, 'k': 0, 'bb': 0, 'runs': 0}
                
                # Add game stats to this umpire's running total
                game_row = game_data[game_data['game_pk'] == game_pk].iloc[0]
                umpire_dict[hp_umpire]['games'] += 1
                umpire_dict[hp_umpire]['pa'] += int(game_row['total_pa'])
                umpire_dict[hp_umpire]['k'] += int(game_row['strikeouts'])
                umpire_dict[hp_umpire]['bb'] += int(game_row['walks'])
                umpire_dict[hp_umpire]['runs'] += total_runs
                
        except Exception:
            continue

    # 5. Calculate Final Rates and Format JSON
    print("Formatting output...")
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

    # 6. Save to umpires.json
    with open('data/umpires.json', 'w') as f:
        json.dump({"umpires": final_output}, f, indent=4)
        
    print("Success! Saved to data/umpires.json")

if __name__ == "__main__":
    build_umpire_json()
