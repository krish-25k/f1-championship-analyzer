from markupsafe import Markup
from flask import Flask, render_template, request, jsonify, session
import pandas as pd
import datetime
import plotly.express as px
import plotly.graph_objects as go
import plotly.utils
import json

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)