import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def fetch_race_results(season):
    """
    Fetches F1 race results from the Jolpica API with reliable parallel requests.
    """
    try:
        print(f"Loading data for season {season}...")
        start_time = time.time()
        
        # Updated API endpoint - Jolpica F1 API
        base_url = "https://api.jolpi.ca/ergast/f1"
        
        # Get the list of races for the season first
        races_response = requests.get(f"{base_url}/{season}.json", timeout=30)
        races_response.raise_for_status()
        
        races_data = races_response.json()['MRData']['RaceTable']['Races']
        
        if not races_data:
            print(f"No races found for season {season}")
            return pd.DataFrame()
        
        print(f"Found {len(races_data)} races for season {season}")
        
        # Use parallel requests to fetch race results much faster
        results_data = []
        failed_rounds = []
        
        def fetch_single_race_results(race):
            """Helper function to fetch results for a single race"""
            try:
                round_num = race['round']
                response = requests.get(f"{base_url}/{season}/{round_num}/results.json", timeout=30)
                response.raise_for_status()
                
                race_results = response.json()['MRData']['RaceTable']['Races']
                if not race_results:
                    return [], round_num
                    
                results = race_results[0]['Results']
                race_data = []
                
                for result in results:
                    race_data.append({
                        'raceName': race['raceName'],
                        'round': int(round_num),
                        'date': race['date'],
                        'Circuit_circuitName': race['Circuit']['circuitName'],
                        'Driver': result['Driver']['givenName'] + ' ' + result['Driver']['familyName'],
                        'Constructor_name': result['Constructor']['name'],
                        'points': float(result['points']),
                        'position': int(result['position'])
                    })
                
                print(f"✓ Round {round_num}: {race['raceName']} ({len(race_data)} results)")
                return race_data, round_num
                
            except Exception as e:
                print(f"✗ Failed round {race['round']}: {e}")
                return [], race['round']
        
        # Use ThreadPoolExecutor to make parallel requests
        print(f"Fetching results for all races in parallel...")
        with ThreadPoolExecutor(max_workers=8) as executor:  # Increased workers for faster loading
            future_to_race = {executor.submit(fetch_single_race_results, race): race for race in races_data}
            
            for future in as_completed(future_to_race):
                race_results, round_num = future.result()
                if race_results:
                    results_data.extend(race_results)
                else:
                    failed_rounds.append(round_num)

        if failed_rounds:
            print(f"⚠️  Failed to fetch data for rounds: {failed_rounds}")

        if not results_data:
            print(f"No race results found for season {season}")
            return pd.DataFrame()
            
        result_df = pd.DataFrame(results_data)
        
        # Sort by round and position for better organization
        result_df = result_df.sort_values(['round', 'position']).reset_index(drop=True)
        
        elapsed_time = time.time() - start_time
        unique_rounds = result_df['round'].nunique()
        unique_drivers = result_df['Driver'].nunique()
        
        print(f"✅ Successfully fetched {len(result_df)} results from {unique_rounds} rounds")
        print(f"   Season {season}: {unique_drivers} drivers, completed in {elapsed_time:.2f} seconds")
        
        return result_df
        
    except requests.exceptions.Timeout:
        print(f"Request timed out while fetching data for season {season}")
        return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()
    except KeyError as e:
        print(f"Data structure error - missing key: {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return pd.DataFrame()


def fetch_race_results_with_retry(season, max_retries=2):
    """
    Wrapper function that retries fetching data if it fails or returns incomplete data.
    """
    for attempt in range(max_retries + 1):
        try:
            df = fetch_race_results(season)
            
            if not df.empty:
                # Basic validation - check if we have a reasonable amount of data
                unique_rounds = df['round'].nunique()
                total_results = len(df)
                
                print(f"Validation: {unique_rounds} rounds, {total_results} total results")
                
                # Accept the data if we have at least some results
                # (some seasons might be incomplete if they're ongoing)
                if total_results > 0:
                    return df
                else:
                    print(f"Attempt {attempt + 1}: Got empty results, retrying...")
            else:
                print(f"Attempt {attempt + 1}: No data returned, retrying...")
                
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
        
        if attempt < max_retries:
            print(f"Waiting 2 seconds before retry...")
            time.sleep(2)
    
    print(f"All attempts failed for season {season}")
    return pd.DataFrame()