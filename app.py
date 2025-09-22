from markupsafe import Markup
from flask import Flask, render_template, request, jsonify
import pandas as pd
import datetime
import plotly.graph_objects as go
import plotly.utils
import json
import requests
import wikipedia

# Import custom functions
from src.data import fetch_race_results_with_retry
from src.analysis import driver_stats, constructor_stats, cumulative_points

# Initialize the Flask application
app = Flask(__name__)
app.secret_key = 'f1_analyzer_secret_key'

# Cache for storing data
data_cache = {}

def get_season_data(season):
    """Get season data with caching."""
    if season not in data_cache:
        print(f"Fetching data for season {season}")
        df = fetch_race_results_with_retry(season)
        data_cache[season] = df
    else:
        print(f"Using cached data for season {season}")
    return data_cache[season]

def get_driver_details_from_wikipedia(driver_name):
    """Fetch driver photo and biography from Wikipedia with better image selection."""
    try:
        # Use a targeted search to find the correct page
        search_results = wikipedia.search(f"{driver_name} Formula 1 driver")
        if not search_results:
            search_results = wikipedia.search(f"{driver_name} racing driver")
        if not search_results:
            search_results = wikipedia.search(driver_name)
        
        if not search_results:
            return None, None
        
        page = wikipedia.page(search_results[0], auto_suggest=False)
        
        # Get a better image URL and summary
        image_url = find_best_driver_image(page.images, driver_name)
        summary = page.summary
        
        return image_url, summary
        
    except (wikipedia.exceptions.PageError, wikipedia.exceptions.DisambiguationError) as e:
        print(f"Wikipedia search failed for {driver_name}: {e}")
        return None, f"Could not find a definitive biography for {driver_name}."
    except Exception as e:
        print(f"An unexpected error occurred while fetching from Wikipedia: {e}")
        return None, "An error occurred while fetching the driver's biography."

def find_best_driver_image(image_urls, driver_name):
    """Find the best driver image from Wikipedia images."""
    if not image_urls:
        return None
    
    # Keywords that suggest a driver photo
    good_keywords = ['portrait', 'headshot', 'driver', 'racing', 'formula', 'f1', 'head', 'face']
    # Keywords that suggest non-driver photos
    bad_keywords = ['car', 'logo', 'track', 'circuit', 'garage', 'pit', 'helmet', 'trophy', 'flag', 'map']
    
    # Score images based on filename
    scored_images = []
    
    for img_url in image_urls:
        if not img_url:
            continue
            
        # Extract filename from URL
        filename = img_url.lower().split('/')[-1] if '/' in img_url else img_url.lower()
        
        score = 0
        
        # Prefer JPG/JPEG images (usually photos)
        if any(ext in filename for ext in ['.jpg', '.jpeg']):
            score += 10
        
        # Avoid SVG files (usually logos/graphics)
        if '.svg' in filename:
            score -= 20
        
        # Check for driver name in filename
        name_parts = driver_name.lower().split()
        for part in name_parts:
            if part in filename:
                score += 15
        
        # Check for good keywords
        for keyword in good_keywords:
            if keyword in filename:
                score += 5
        
        # Check for bad keywords
        for keyword in bad_keywords:
            if keyword in filename:
                score -= 10
        
        # Prefer images that are not too small (based on common naming patterns)
        if any(size in filename for size in ['thumb', '150px', '200px']):
            score -= 5
        
        scored_images.append((score, img_url))
    
    # Sort by score (highest first) and return the best one
    scored_images.sort(reverse=True, key=lambda x: x[0])
    
    if scored_images and scored_images[0][0] > -10:  # Only return if score is reasonable
        return scored_images[0][1]
    
    # Fallback: return first JPG/JPEG image if available
    for img_url in image_urls:
        if img_url and any(ext in img_url.lower() for ext in ['.jpg', '.jpeg']):
            return img_url
    
    # Last resort: return first image
    return image_urls[0] if image_urls else None

def get_driver_season_details(driver_name, season):
    """Get detailed results and bio for a driver in a season."""
    df = get_season_data(season)
    if df.empty:
        return None
    
    driver_data = df[df['Driver'] == driver_name].copy()
    if driver_data.empty:
        return None
    
    # Sort by round to ensure proper order
    driver_data = driver_data.sort_values('round')
    
    # Get driver bio and photo from Wikipedia
    image_url, bio_description = get_driver_details_from_wikipedia(driver_name)

    # Basic stats
    total_points = driver_data['points'].sum()
    wins = (driver_data['position'] == 1).sum()
    podiums = driver_data['position'].isin([1, 2, 3]).sum()
    
    return {
        'name': driver_name,
        'season': season,
        'constructor': driver_data['Constructor_name'].iloc[0],
        'total_points': int(total_points),
        'wins': int(wins),
        'podiums': int(podiums),
        'races_completed': len(driver_data),
        'race_results': driver_data.to_dict('records'),
        'image_url': image_url,
        'bio': {
            'description': bio_description,
            'nationality': "See bio",
            'birthdate': "See bio",
            'career_highlights': [],
            'teams': []
        }
    }
    
@app.route('/')
@app.route('/<int:season>')
def index(season=None):
    current_year = datetime.datetime.now().year
    season = season or current_year
    seasons = list(range(current_year, 1949, -1))
    
    df = get_season_data(season)
    if df.empty:
        return render_template('index.html', error=f"No data for {season}.", seasons=seasons, selected_season=season)

    driver_table = driver_stats(df).to_html(classes='table table-striped')
    constructor_table = constructor_stats(df).to_html(classes='table table-striped')
    
    return render_template('index.html',
                           selected_season=season,
                           seasons=seasons,
                           driver_table=driver_table,
                           constructor_table=constructor_table)

@app.route('/points-progression')
@app.route('/points-progression/<int:season>')
def points_progression(season=None):
    """Points progression analysis page."""
    current_year = datetime.datetime.now().year
    season = season or current_year
    seasons = list(range(current_year, 1949, -1))
    
    df = get_season_data(season)
    if df.empty:
        return render_template('points_progression.html', 
                             error=f"No data for {season}.", 
                             seasons=seasons, 
                             selected_season=season,
                             drivers=[],
                             races=[])
    
    # Get drivers and races for the season
    drivers = driver_stats(df).reset_index()
    drivers_list = [{'name': row['Driver'], 'points': int(row['Total_Points'])} 
                   for _, row in drivers.iterrows()]
    
    races_list = df[['round', 'raceName']].drop_duplicates().sort_values('round')
    races = [{'round': int(row['round'])} for _, row in races_list.iterrows()]
    
    return render_template('points_progression.html',
                         selected_season=season,
                         seasons=seasons,
                         drivers=drivers_list,
                         races=races)

@app.route('/api/points-progression')
def api_points_progression():
    """API endpoint for points progression data."""
    try:
        season = request.args.get('season')
        selected_drivers = request.args.getlist('drivers')
        up_to_round = request.args.get('up_to_round')
        
        print(f"API called with season={season}, drivers={selected_drivers}, up_to_round={up_to_round}")
        
        if not season or not selected_drivers:
            return jsonify({'error': 'Season and drivers are required'}), 400
        
        df = get_season_data(int(season))
        if df.empty:
            return jsonify({'error': f'No data available for season {season}'}), 404
        
        print(f"Data loaded for season {season}, total records: {len(df)}")
        
        # Filter by selected drivers
        filtered_df = df[df['Driver'].isin(selected_drivers)].copy()
        print(f"Filtered to selected drivers: {len(filtered_df)} records")
        
        # Filter by round if specified
        if up_to_round:
            filtered_df = filtered_df[filtered_df['round'] <= int(up_to_round)]
            print(f"Filtered to round {up_to_round}: {len(filtered_df)} records")
        
        if filtered_df.empty:
            return jsonify({'error': 'No data found for selected criteria'}), 404
        
        # Create points progression manually
        progression_data = {}
        all_rounds = sorted(filtered_df['round'].unique())
        print(f"Processing rounds: {all_rounds}")
        
        for driver in selected_drivers:
            driver_data = filtered_df[filtered_df['Driver'] == driver].sort_values('round')
            print(f"Processing {driver}: {len(driver_data)} races")
            
            # Initialize with zeros for all rounds
            driver_points = {round_num: 0 for round_num in all_rounds}
            
            # Fill in actual points
            for _, row in driver_data.iterrows():
                driver_points[row['round']] = row['points']
            
            # Calculate cumulative points
            cumulative = []
            total = 0
            for round_num in all_rounds:
                total += driver_points[round_num]
                cumulative.append(total)
            
            progression_data[driver] = {
                'rounds': all_rounds,
                'cumulative': cumulative,
                'per_race': [driver_points[r] for r in all_rounds]
            }
            print(f"{driver} final points: {cumulative[-1] if cumulative else 0}")
        
        # Create the chart
        fig = go.Figure()
        
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                 '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        
        for i, driver in enumerate(selected_drivers):
            if driver in progression_data:
                data = progression_data[driver]
                fig.add_trace(go.Scatter(
                    x=data['rounds'],
                    y=data['cumulative'],
                    mode='lines+markers',
                    name=driver,
                    line=dict(width=3, color=colors[i % len(colors)]),
                    marker=dict(size=6),
                    hovertemplate=f'<b>{driver}</b><br>Round %{{x}}<br>Points: %{{y}}<extra></extra>'
                ))
        
        fig.update_layout(
            title=f'{season} F1 Championship Points Progression',
            xaxis_title='Race Round',
            yaxis_title='Cumulative Points',
            plot_bgcolor='white',
            height=600,
            margin=dict(l=50, r=50, t=70, b=50),
            legend=dict(
                x=0.02,
                y=0.98,
                bgcolor='rgba(255,255,255,0.8)',
                bordercolor='gray',
                borderwidth=1
            ),
            xaxis=dict(
                showgrid=True,
                gridcolor='lightgray',
                tickmode='linear',
                tick0=1,
                dtick=1
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='lightgray'
            )
        )
        
        chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return jsonify({'chart': chart_json})
        
    except Exception as e:
        print(f"Error in points progression API: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/driver/<driver_name>/<int:season>')
def driver_detail(driver_name, season):
    """Display detailed driver information."""
    driver_details = get_driver_season_details(driver_name, season)
    if not driver_details:
        return render_template('driver_detail.html', error=f"No data for {driver_name} in {season}.")
    
    # Create improved points progression chart
    race_results = driver_details['race_results']
    if race_results:
        # Sort results by round to ensure proper order
        sorted_results = sorted(race_results, key=lambda x: x['round'])
        
        rounds = [race['round'] for race in sorted_results]
        race_names = [f"R{race['round']}" for race in sorted_results]
        points_per_race = [race['points'] for race in sorted_results]
        positions = [race['position'] for race in sorted_results]
        
        # Calculate cumulative points correctly
        cumulative_points_list = []
        total = 0
        for points in points_per_race:
            total += points
            cumulative_points_list.append(total)
        
        # Create the chart with both cumulative and per-race data
        fig = go.Figure()
        
        # Add cumulative points line
        fig.add_trace(go.Scatter(
            x=rounds, 
            y=cumulative_points_list,
            mode='lines+markers',
            name='Cumulative Points',
            line=dict(width=3, color='#1f77b4'),
            marker=dict(size=8),
            hovertemplate='<b>Round %{x}</b><br>Cumulative Points: %{y}<br>Position: %{customdata}<extra></extra>',
            customdata=positions
        ))
        
        # Add points per race bars (on secondary y-axis)
        fig.add_trace(go.Bar(
            x=rounds,
            y=points_per_race,
            name='Points per Race',
            yaxis='y2',
            opacity=0.6,
            marker_color='#ff7f0e',
            hovertemplate='<b>Round %{x}</b><br>Points Scored: %{y}<br>Position: %{customdata}<extra></extra>',
            customdata=positions
        ))
        
        # Update layout with proper styling
        fig.update_layout(
            title=dict(
                text=f'{driver_name} - {season} Season Points Progression',
                x=0.5,
                font=dict(size=18)
            ),
            xaxis=dict(
                title='Race Round',
                tickmode='linear',
                tick0=1,
                dtick=1,
                showgrid=True,
                gridcolor='lightgray'
            ),
            yaxis=dict(
                title='Cumulative Points',
                showgrid=True,
                gridcolor='lightgray'
            ),
            yaxis2=dict(
                title='Points per Race',
                overlaying='y',
                side='right',
                showgrid=False
            ),
            plot_bgcolor='white',
            height=500,
            margin=dict(l=50, r=50, t=70, b=50),
            legend=dict(
                x=0.02,
                y=0.98,
                bgcolor='rgba(255,255,255,0.8)',
                bordercolor='gray',
                borderwidth=1
            )
        )
        
        driver_details['chart_json'] = Markup(json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder))
    
    return render_template('driver_detail.html', driver=driver_details)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)