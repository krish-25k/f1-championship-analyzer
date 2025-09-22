from markupsafe import Markup
from flask import Flask, render_template, request, jsonify, session
import pandas as pd
import datetime
import plotly.express as px
import plotly.graph_objects as go
import plotly.utils
import json
import requests
import re
from urllib.parse import quote

# Import our custom functions
try:
    from src.data import fetch_race_results_with_retry
    from src.analysis import driver_stats, constructor_stats, cumulative_points
except ImportError:
    # Fallback for direct import
    from data import fetch_race_results_with_retry
    from analysis import driver_stats, constructor_stats, cumulative_points

# Initialize the Flask application
app = Flask(__name__)
app.secret_key = 'f1_analyzer_secret_key'  # For session management

# Cache for storing data to avoid repeated API calls
data_cache = {}

def get_season_data(season):
    """
    Get season data with caching to improve performance
    """
    if season not in data_cache:
        print(f"Fetching fresh data for season {season}")
        df = fetch_race_results_with_retry(season)
        data_cache[season] = df
    else:
        print(f"Using cached data for season {season}")
    
    return data_cache[season]

def get_driver_wikipedia_image(driver_name, season):
    """
    Fetch driver image from Wikipedia with fallback to default
    """
    try:
        # Clean driver name for Wikipedia search
        search_name = driver_name.replace(' ', '_')
        
        # Try different Wikipedia search strategies
        search_queries = [
            f"{search_name}_(racing_driver)",
            f"{search_name}_(Formula_One)",
            f"{search_name}",
            f"{search_name}_(driver)"
        ]
        
        for search_query in search_queries:
            try:
                # Wikipedia API to get page info
                wiki_api = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(search_query)}"
                response = requests.get(wiki_api, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check if we have a thumbnail image
                    if 'thumbnail' in data and 'source' in data['thumbnail']:
                        image_url = data['thumbnail']['source']
                        # Get higher resolution image
                        if 'originalimage' in data and 'source' in data['originalimage']:
                            image_url = data['originalimage']['source']
                        
                        print(f"Found Wikipedia image for {driver_name}: {image_url}")
                        return image_url
                        
            except Exception as e:
                print(f"Error searching for {search_query}: {e}")
                continue
        
        print(f"No Wikipedia image found for {driver_name}")
        return None
        
    except Exception as e:
        print(f"Error fetching image for {driver_name}: {e}")
        return None

def get_driver_season_details(driver_name, season):
    """
    Get detailed race-by-race results for a specific driver in a season
    """
    try:
        df = get_season_data(season)
        if df.empty:
            return None
        
        # Filter for specific driver
        driver_data = df[df['Driver'] == driver_name].copy()
        
        if driver_data.empty:
            return None
        
        # Sort by round
        driver_data = driver_data.sort_values('round')
        
        # Calculate season statistics
        total_points = driver_data['points'].sum()
        wins = len(driver_data[driver_data['position'] == 1])
        podiums = len(driver_data[driver_data['position'].isin([1, 2, 3])])
        races_completed = len(driver_data)
        
        # Get constructor info (assuming driver didn't change teams mid-season)
        constructor = driver_data['Constructor_name'].iloc[0]
        
        # Get driver image
        driver_image = get_driver_wikipedia_image(driver_name, season)
        
        return {
            'name': driver_name,
            'season': season,
            'constructor': constructor,
            'total_points': int(total_points),
            'wins': wins,
            'podiums': podiums,
            'races_completed': races_completed,
            'race_results': driver_data.to_dict('records'),
            'image_url': driver_image
        }
        
    except Exception as e:
        print(f"Error getting driver details for {driver_name}: {e}")
        return None

def get_available_drivers(season):
    """
    Gets all available drivers for a season with their total points
    """
    try:
        df = get_season_data(season)
        if df.empty:
            return []
        
        # Get driver stats to show total points
        driver_df = driver_stats(df)
        drivers_with_points = []
        
        for driver_name in driver_df.index:
            total_points = int(driver_df.loc[driver_name, 'Total_Points'])
            drivers_with_points.append({
                'name': driver_name,
                'points': total_points
            })
        
        # Sort by points descending
        drivers_with_points.sort(key=lambda x: x['points'], reverse=True)
        return drivers_with_points
        
    except Exception as e:
        print(f"Error getting drivers: {e}")
        return []

def get_race_list_with_details(season):
    """
    Gets race list with additional details from the results data
    """
    try:
        df = get_season_data(season)
        if df.empty:
            return []
        
        races = []
        for round_num, race_data in df.groupby('round'):
            race_info = race_data.iloc[0]
            races.append({
                'round': int(round_num),
                'raceName': race_info['raceName'],
                'date': race_info.get('date', 'Unknown'),
                'circuit': race_info.get('Circuit_circuitName', 'Unknown')
            })
        
        return sorted(races, key=lambda x: x['round'])
        
    except Exception as e:
        print(f"Error getting race list: {e}")
        return []

@app.route('/')
@app.route('/<int:season>')
def index(season=None):
    current_year = datetime.datetime.now().year
    if season is None:
        season = current_year
    
    # Create a list of years for the dropdown (1950 to current year)
    seasons = list(range(current_year, 1949, -1))

    # Fetch Data with caching
    print(f"Loading season overview for: {season}")
    df = get_season_data(season)

    # Handle Cases with No Data
    if df.empty:
        error_message = f"No data available for the {season} season. Please select another year."
        print(error_message)
        return render_template('index.html', error=error_message, seasons=seasons, 
                              selected_season=season,
                              driver_table="", constructor_table="")

    # Perform Analysis
    driver_df = driver_stats(df)
    constructor_df = constructor_stats(df)

    # Prepare Data for Display (just tables, no chart on main page)
    driver_table = driver_df.to_html(classes='table table-striped', index=True)
    constructor_table = constructor_df.to_html(classes='table table-striped', index=True)

    # Render the Final Page (removed cumulative chart)
    return render_template(
        'index.html',
        selected_season=season,
        seasons=seasons,
        driver_table=driver_table,
        constructor_table=constructor_table
    )

@app.route('/points-progression')
@app.route('/points-progression/<int:season>')
def points_progression(season=None):
    current_year = datetime.datetime.now().year
    if season is None:
        season = current_year
    
    seasons = list(range(current_year, 1949, -1))  # All seasons available
    races = get_race_list_with_details(season)
    drivers = get_available_drivers(season)
    
    return render_template(
        'points_progression.html',
        selected_season=season,
        seasons=seasons,
        races=races,
        drivers=drivers
    )

@app.route('/driver/<driver_name>/<int:season>')
def driver_detail(driver_name, season):
    """
    Display detailed information about a specific driver in a season
    """
    try:
        # Get driver details
        driver_details = get_driver_season_details(driver_name, season)
        
        if not driver_details:
            return render_template('driver_detail.html', 
                                 error=f"No data found for {driver_name} in {season} season.")
        
        # Create race-by-race points progression chart
        race_results = driver_details['race_results']
        if race_results:
            rounds = [race['round'] for race in race_results]
            points = [race['points'] for race in race_results]
            cumulative_points = []
            total = 0
            for p in points:
                total += p
                cumulative_points.append(total)
            
            # Create chart
            fig = go.Figure()
            
            # Add cumulative points line
            fig.add_trace(go.Scatter(
                x=rounds,
                y=cumulative_points,
                mode='lines+markers',
                name='Cumulative Points',
                line=dict(color='#e60000', width=3),
                marker=dict(size=8, color='#e60000'),
                hovertemplate='Round %{x}<br>Total Points: %{y}<extra></extra>'
            ))
            
            # Add race points as bars
            fig.add_trace(go.Bar(
                x=rounds,
                y=points,
                name='Points per Race',
                opacity=0.6,
                marker_color='#1e90ff',
                hovertemplate='Round %{x}<br>Points: %{y}<extra></extra>',
                yaxis='y2'
            ))
            
            fig.update_layout(
                title=f'{driver_name} - {season} Season Points Progression',
                xaxis_title='Race Round',
                yaxis_title='Cumulative Points',
                yaxis2=dict(
                    title='Points per Race',
                    overlaying='y',
                    side='right'
                ),
                height=400,
                showlegend=True,
                plot_bgcolor='white',
                paper_bgcolor='white',
                hovermode='x unified'
            )
            
            chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
            driver_details['chart_json'] = Markup(chart_json)
        else:
            driver_details['chart_json'] = Markup("{}")
        
        return render_template('driver_detail.html', driver=driver_details)
        
    except Exception as e:
        print(f"Error in driver detail route: {e}")
        return render_template('driver_detail.html', 
                             error=f"Error loading data for {driver_name}.")

@app.route('/api/points-progression')
def points_progression_api():
    season = request.args.get('season', type=int)
    selected_drivers = request.args.getlist('drivers')
    up_to_round = request.args.get('up_to_round', type=int)
    
    if not all([season, selected_drivers]):
        return jsonify({'error': 'Missing required parameters'}), 400
    
    try:
        # Fetch season data (using cache)
        df = get_season_data(season)
        
        if df.empty:
            return jsonify({'error': 'No data found for this season'}), 404
        
        print(f"Processing data: {len(df)} records for {len(selected_drivers)} drivers")
        
        # Filter up to specific round if specified
        if up_to_round:
            df = df[df['round'] <= up_to_round]
            print(f"Filtered to round {up_to_round}: {len(df)} records")
        
        # Get cumulative points
        cum_points_df = cumulative_points(df)
        
        if cum_points_df.empty:
            return jsonify({'error': 'No points data could be calculated'}), 404
        
        print(f"Cumulative points calculated. Shape: {cum_points_df.shape}")
        print(f"Available drivers: {list(cum_points_df.columns)}")
        print(f"Requested drivers: {selected_drivers}")
        
        # Filter for selected drivers (check exact matches)
        available_drivers = []
        for driver in selected_drivers:
            if driver in cum_points_df.columns:
                available_drivers.append(driver)
            else:
                print(f"Driver '{driver}' not found in data")
        
        if not available_drivers:
            return jsonify({'error': 'None of the selected drivers found in this season'}), 404
        
        print(f"Found {len(available_drivers)} matching drivers: {available_drivers}")
        
        # Create the points progression chart
        fig = go.Figure()
        
        # Add a line for each driver
        for driver in available_drivers:
            driver_points = cum_points_df[driver]
            rounds = driver_points.index.tolist()
            points = driver_points.values.tolist()
            
            print(f"{driver}: rounds={rounds}, points={points}")
            
            fig.add_trace(go.Scatter(
                x=rounds,
                y=points,
                mode='lines+markers',
                name=driver,
                line=dict(width=3),
                marker=dict(size=8),
                hovertemplate=f'<b>{driver}</b><br>' +
                              'Round: %{x}<br>' +
                              'Points: %{y}<br>' +
                              '<extra></extra>'
            ))
        
        # Get race info for better x-axis
        try:
            race_info = df[['round', 'raceName']].drop_duplicates().set_index('round')
            tickvals = sorted(df['round'].unique())
            ticktext = [f"R{r}" for r in tickvals]
        except:
            tickvals = sorted(cum_points_df.index.tolist())
            ticktext = [f"R{r}" for r in tickvals]
        
        # Customize the chart
        fig.update_layout(
            title=f'Championship Points Progression - {season} Season',
            xaxis_title='Race Round',
            yaxis_title='Cumulative Points',
            hovermode='x unified',
            height=600,
            showlegend=True,
            plot_bgcolor='white',
            paper_bgcolor='white',
            xaxis=dict(
                tickmode='array',
                tickvals=tickvals,
                ticktext=ticktext,
                showgrid=True,
                gridcolor='lightgray'
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='lightgray',
                rangemode='tozero'
            ),
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor="rgba(255,255,255,0.8)",
                bordercolor="gray",
                borderwidth=1
            )
        )
        
        # Convert to JSON
        chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        
        return jsonify({
            'chart': chart_json,
            'season': season,
            'drivers': available_drivers,
            'total_rounds': len(tickvals)
        })
        
    except Exception as e:
        print(f"Error in points progression API: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/driver-image/<driver_name>/<int:season>')
def get_driver_image_api(driver_name, season):
    """
    API endpoint to get driver image (for AJAX loading)
    """
    try:
        image_url = get_driver_wikipedia_image(driver_name, season)
        return jsonify({
            'image_url': image_url,
            'driver_name': driver_name
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'driver_name': driver_name
        })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)