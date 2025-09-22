import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def fetch_race_results(season):
    """
    Optimized F1 race results fetcher with better performance and complete points
    """
    try:
        print(f"Loading optimized data for season {season}...")
        start_time = time.time()
        
        base_url = "https://api.jolpi.ca/ergast/f1"
        
        # Get race list first
        races_response = requests.get(f"{base_url}/{season}.json?limit=30", timeout=20)
        races_response.raise_for_status()
        
        races_data = races_response.json()['MRData']['RaceTable']['Races']
        
        if not races_data:
            print(f"No races found for season {season}")
            return pd.DataFrame()
        
        print(f"Found {len(races_data)} races for season {season}")
        
        # Collect all race data efficiently
        all_results_data = []
        failed_rounds = []
        
        def fetch_optimized_race_data(race):
            """Optimized function to fetch race data quickly"""
            try:
                round_num = race['round']
                race_name = race['raceName']
                race_date = race['date']
                circuit_name = race['Circuit']['circuitName']
                
                # Fetch main race results
                results = fetch_single_race_optimized(season, round_num, race_name, race_date, circuit_name)
                
                # For recent seasons, try to get sprint data
                if int(season) >= 2021:
                    sprint_results = fetch_sprint_optimized(season, round_num, race_name, race_date, circuit_name)
                    results.extend(sprint_results)
                
                return results, round_num
                
            except Exception as e:
                print(f"✗ Failed round {race['round']}: {e}")
                return [], race['round']
        
        # Use optimized parallel processing
        print(f"Fetching race data with optimized threading...")
        with ThreadPoolExecutor(max_workers=4) as executor:  # Reduced workers for better stability
            future_to_race = {executor.submit(fetch_optimized_race_data, race): race for race in races_data}
            
            for future in as_completed(future_to_race):
                race_results, round_num = future.result()
                if race_results:
                    all_results_data.extend(race_results)
                else:
                    failed_rounds.append(round_num)

        # Quick retry for failed rounds
        if failed_rounds and len(failed_rounds) <= 3:  # Only retry if few failures
            print(f"⚠️  Retrying {len(failed_rounds)} failed rounds...")
            for round_num in failed_rounds:
                try:
                    race = next(r for r in races_data if r['round'] == str(round_num))
                    retry_results, _ = fetch_optimized_race_data(race)
                    if retry_results:
                        all_results_data.extend(retry_results)
                        print(f"✓ Retry successful for round {round_num}")
                except:
                    continue

        if not all_results_data:
            print(f"No race results found for season {season}")
            return pd.DataFrame()
            
        result_df = pd.DataFrame(all_results_data)
        
        # Quick data cleaning
        result_df = result_df.dropna(subset=['Driver', 'Constructor_name', 'position'])
        result_df['points'] = pd.to_numeric(result_df['points'], errors='coerce').fillna(0)
        result_df = result_df.sort_values(['round', 'position']).reset_index(drop=True)
        
        elapsed_time = time.time() - start_time
        unique_rounds = result_df['round'].nunique()
        unique_drivers = result_df['Driver'].nunique()
        total_points = result_df['points'].sum()
        
        print(f"✅ Successfully fetched {len(result_df)} results from {unique_rounds} rounds")
        print(f"   Season {season}: {unique_drivers} drivers, {total_points} total points distributed")
        print(f"   Completed in {elapsed_time:.2f} seconds")
        
        return result_df
        
    except Exception as e:
        print(f"Error fetching data for season {season}: {e}")
        return pd.DataFrame()

def fetch_single_race_optimized(season, round_num, race_name, race_date, circuit_name):
    """
    Optimized single race results fetcher
    """
    try:
        base_url = "https://api.jolpi.ca/ergast/f1"
        response = requests.get(f"{base_url}/{season}/{round_num}/results.json?limit=30", timeout=15)
        response.raise_for_status()
        
        race_results = response.json()['MRData']['RaceTable']['Races']
        if not race_results:
            return []
            
        results = race_results[0]['Results']
        race_data = []
        
        for result in results:
            try:
                race_data.append({
                    'raceName': race_name,
                    'round': int(round_num),
                    'date': race_date,
                    'Circuit_circuitName': circuit_name,
                    'Driver': result['Driver']['givenName'] + ' ' + result['Driver']['familyName'],
                    'Constructor_name': result['Constructor']['name'],
                    'points': float(result.get('points', 0)),
                    'position': int(result['position']),
                    'race_type': 'Race'
                })
            except (ValueError, KeyError) as e:
                print(f"Skipping invalid result in round {round_num}: {e}")
                continue
        
        print(f"✓ R{round_num}: {race_name} ({len(race_data)} results)")
        return race_data
        
    except Exception as e:
        print(f"✗ Failed race results for round {round_num}: {e}")
        return []

def fetch_sprint_optimized(season, round_num, race_name, race_date, circuit_name):
    """
    Optimized sprint race results fetcher
    """
    try:
        base_url = "https://api.jolpi.ca/ergast/f1"
        response = requests.get(f"{base_url}/{season}/{round_num}/sprint.json?limit=30", timeout=10)
        
        if response.status_code == 200:
            sprint_data = response.json()['MRData']['RaceTable']['Races']
            if sprint_data and 'SprintResults' in sprint_data[0]:
                sprint_results = sprint_data[0]['SprintResults']
                race_data = []
                
                for result in sprint_results:
                    try:
                        race_data.append({
                            'raceName': f"{race_name} (Sprint)",
                            'round': int(round_num),
                            'date': race_date,
                            'Circuit_circuitName': circuit_name,
                            'Driver': result['Driver']['givenName'] + ' ' + result['Driver']['familyName'],
                            'Constructor_name': result['Constructor']['name'],
                            'points': float(result.get('points', 0)),
                            'position': int(result['position']),
                            'race_type': 'Sprint'
                        })
                    except (ValueError, KeyError):
                        continue
                
                if race_data:
                    print(f"✓ R{round_num}: Sprint ({len(race_data)} results)")
                return race_data
        
        return []
        
    except Exception:
        # Sprint races don't exist for all rounds
        return []

def fetch_race_results_with_retry(season, max_retries=2):
    """
    Optimized wrapper function with faster retry logic
    """
    for attempt in range(max_retries + 1):
        try:
            df = fetch_race_results(season)
            
            if not df.empty:
                # Quick validation
                unique_rounds = df['round'].nunique()
                total_results = len(df)
                drivers_count = df['Driver'].nunique()
                total_points = df['points'].sum()
                
                print(f"Validation: {unique_rounds} rounds, {total_results} results, {drivers_count} drivers, {total_points} points")
                
                # Accept if we have reasonable data
                if total_results >= unique_rounds * 10:  # At least ~10 drivers per round minimum
                    return df
                else:
                    print(f"Attempt {attempt + 1}: Insufficient data quality, retrying...")
            else:
                print(f"Attempt {attempt + 1}: No data returned, retrying...")
                
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
        
        if attempt < max_retries:
            wait_time = 1  # Reduced wait time
            print(f"Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)
    
    print(f"All attempts failed for season {season}")
    return pd.DataFrame()