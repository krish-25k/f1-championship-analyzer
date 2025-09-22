from markupsafe import Markup
from flask import Flask, render_template, request, jsonify
import pandas as pd
import datetime
import plotly.graph_objects as go
import plotly.utils
import json
import requests
import wikipedia
import urllib.parse
import re # Import regex for cleaner search terms

# Import custom functions (assuming these are in src/data.py and src/analysis.py)
from src.data import fetch_race_results_with_retry
from src.analysis import driver_stats, constructor_stats, cumulative_points

# Initialize the Flask application
app = Flask(__name__)
app.secret_key = 'f1_analyzer_secret_key'

# Cache for storing data
data_cache = {}
image_cache = {}

def get_season_data(season):
    """Get season data with caching."""
    if season not in data_cache:
        print(f"Fetching data for season {season}")
        df = fetch_race_results_with_retry(season)
        data_cache[season] = df
    else:
        print(f"Using cached data for season {season}")
    return data_cache[season]

def get_f1_logo_from_wikipedia():
    """Fetch F1 logo from Wikipedia."""
    cache_key = 'f1_logo'
    if cache_key in image_cache:
        return image_cache[cache_key]

    try:
        search_results = wikipedia.search("Formula 1")
        if search_results:
            page = wikipedia.page(search_results[0])
            for img_url in page.images:
                if img_url and any(keyword in img_url.lower() for keyword in ['logo', 'f1', 'formula']) and '.svg' in img_url.lower():
                    image_cache[cache_key] = img_url
                    return img_url
            for img_url in page.images:
                if img_url and 'f1' in img_url.lower():
                    image_cache[cache_key] = img_url
                    return img_url
    except Exception as e:
        print(f"Error fetching F1 logo: {e}")

    fallback_url = "https://upload.wikimedia.org/wikipedia/commons/3/33/F1.svg"
    image_cache[cache_key] = fallback_url
    return fallback_url

def get_team_image_from_wikipedia(team_name, season):
    """Fetch team/constructor image from Wikipedia, prioritizing logos/cars."""
    cache_key = f"team_image_{team_name}_{season}"
    if cache_key in image_cache:
        return image_cache[cache_key]

    try:
        # Clean team name for better search, removing common F1 suffixes
        clean_team = re.sub(r'(f1 team|racing team|team|f1|gp)$', '', team_name, flags=re.IGNORECASE).strip()
        
        # Broader search terms
        search_terms = [
            f"{clean_team} F1 car {season}",
            f"{clean_team} F1 team logo",
            f"{clean_team} Formula 1",
            clean_team
        ]
        
        best_image_url = None
        max_score = -1

        for term in search_terms:
            try:
                search_results = wikipedia.search(term, results=5) # Limit results
                if not search_results:
                    continue
                
                # Iterate through the top search results to find the most relevant page
                for s_res in search_results:
                    try:
                        page = wikipedia.page(s_res, auto_suggest=True) # Use auto_suggest
                        
                        for img_url in page.images:
                            if not img_url: continue

                            filename = img_url.lower()
                            current_score = 0

                            # Prioritize SVG for logos, JPG for cars/photos
                            if '.svg' in filename and 'logo' in filename: current_score += 30
                            if any(ext in filename for ext in ['.jpg', '.jpeg']) and any(k in filename for k in ['car', 'livery', 'vehicle']): current_score += 25
                            
                            # Keywords for relevance
                            if clean_team.lower() in filename: current_score += 10
                            if str(season) in filename: current_score += 10
                            if any(k in filename for k in ['logo', 'emblem']): current_score += 15
                            if any(k in filename for k in ['car', 'livery']): current_score += 15
                            if any(k in filename for k in ['f1', 'formula']): current_score += 5

                            # Keywords to avoid
                            if any(k in filename for k in ['map', 'track', 'circuit', 'driver', 'person', 'flag']): current_score -= 20
                            if 'thumbnail' in filename or '200px' in filename: current_score -= 10 # Avoid small thumbs

                            if current_score > max_score:
                                max_score = current_score
                                best_image_url = img_url
                                if max_score >= 30: # If we found a good logo/car, we can stop early
                                    break
                        if max_score >= 30:
                            break # Break from search_results loop too
                    except wikipedia.exceptions.PageError:
                        continue # Page not found, try next search result
                    except wikipedia.exceptions.DisambiguationError:
                        continue # Disambiguation, skip for now to simplify
            except Exception as search_e:
                print(f"Error during Wikipedia search for {term}: {search_e}")
                continue

        image_cache[cache_key] = best_image_url
        return best_image_url

    except Exception as e:
        print(f"Error fetching team image for {team_name}: {e}")

    image_cache[cache_key] = None
    return None

def get_driver_details_from_wikipedia(driver_name):
    """Fetch driver photo and biography from Wikipedia with better image selection."""
    cache_key = f"driver_bio_{driver_name}"
    if cache_key in image_cache:
        return image_cache[cache_key]['image_url'], image_cache[cache_key]['summary']

    try:
        search_results = wikipedia.search(f"{driver_name} Formula 1 driver")
        if not search_results:
            search_results = wikipedia.search(f"{driver_name} racing driver")
        if not search_results:
            search_results = wikipedia.search(driver_name)

        if not search_results:
            return None, None

        page = wikipedia.page(search_results[0], auto_suggest=False)

        image_url = find_best_driver_image(page.images, driver_name)
        summary = page.summary

        image_cache[cache_key] = {'image_url': image_url, 'summary': summary}
        return image_url, summary

    except (wikipedia.exceptions.PageError, wikipedia.exceptions.DisambiguationError) as e:
        print(f"Wikipedia search failed for {driver_name}: {e}")
        return None, f"Could not find a definitive biography for {driver_name}."
    except Exception as e:
        print(f"An unexpected error occurred while fetching from Wikipedia for {driver_name}: {e}")
        return None, "An error occurred while fetching the driver's biography."

def find_best_driver_image(image_urls, driver_name):
    """Find the best driver image from Wikipedia images."""
    if not image_urls:
        return None

    good_keywords = ['portrait', 'headshot', 'driver', 'racing', 'formula', 'f1', 'head', 'face']
    bad_keywords = ['car', 'logo', 'track', 'circuit', 'garage', 'pit', 'helmet', 'trophy', 'flag', 'map', 'emblem']

    scored_images = []
    for img_url in image_urls:
        if not img_url: continue

        filename = img_url.lower().split('/')[-1] if '/' in img_url else img_url.lower()
        score = 0

        if any(ext in filename for ext in ['.jpg', '.jpeg']): score += 10
        if '.svg' in filename: score -= 20

        name_parts = driver_name.lower().split()
        for part in name_parts:
            if part in filename: score += 15

        for keyword in good_keywords:
            if keyword in filename: score += 5
        for keyword in bad_keywords:
            if keyword in filename: score -= 10

        if any(size in filename for size in ['thumb', '150px', '200px']): score -= 5

        scored_images.append((score, img_url))

    scored_images.sort(reverse=True, key=lambda x: x[0])

    if scored_images and scored_images[0][0] > -10:
        return scored_images[0][1]

    for img_url in image_urls:
        if img_url and any(ext in img_url.lower() for ext in ['.jpg', '.jpeg']):
            return img_url

    return image_urls[0] if image_urls else None

def get_driver_season_details(driver_name, season):
    """Get detailed results and bio for a driver in a season."""
    df = get_season_data(season)
    if df.empty:
        return None

    driver_data = df[df['Driver'] == driver_name].copy()
    if driver_data.empty:
        return None

    driver_data = driver_data.sort_values('round')

    image_url, bio_description = get_driver_details_from_wikipedia(driver_name)

    constructor_name = driver_data['Constructor_name'].iloc[0]
    team_image = get_team_image_from_wikipedia(constructor_name, season)

    total_points = driver_data['points'].sum()
    wins = (driver_data['position'] == 1).sum()
    podiums = driver_data['position'].isin([1, 2, 3]).sum()

    return {
        'name': driver_name,
        'season': season,
        'constructor': constructor_name,
        'team_image': team_image,
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

def get_team_season_details(team_name, season):
    """Get detailed results for a team in a season."""
    df = get_season_data(season)
    if df.empty:
        return None

    team_data = df[df['Constructor_name'] == team_name].copy()
    if team_data.empty:
        return None

    team_image = get_team_image_from_wikipedia(team_name, season)

    total_points = team_data['points'].sum()
    wins = (team_data['position'] == 1).sum()

    # Get unique drivers for the team in the current season
    drivers_in_season = team_data['Driver'].unique().tolist()

    return {
        'name': team_name,
        'season': season,
        'team_image': team_image,
        'total_points': int(total_points),
        'wins': int(wins),
        'drivers': drivers_in_season, # This is the list of drivers
        'race_results': team_data.to_dict('records') # Full race results for the team
    }


@app.route('/api/f1-logo')
def api_f1_logo():
    logo_url = get_f1_logo_from_wikipedia()
    return jsonify({'logo_url': logo_url})

@app.route('/api/team-image/<team_name>/<int:season>')
def api_team_image(team_name, season):
    team_image = get_team_image_from_wikipedia(urllib.parse.unquote(team_name), season)
    return jsonify({'team_image': team_image})

@app.route('/')
@app.route('/<int:season>')
def index(season=None):
    current_year = datetime.datetime.now().year
    season = season or current_year
    seasons = list(range(current_year, 1949, -1))

    df = get_season_data(season)
    if df.empty:
        return render_template('index.html', error=f"No data for {season}.", seasons=seasons, selected_season=season)

    f1_logo = get_f1_logo_from_wikipedia()

    driver_table = driver_stats(df).to_html(classes='table table-striped')
    constructor_table = constructor_stats(df).to_html(classes='table table-striped')

    return render_template('index.html',
                           selected_season=season,
                           seasons=seasons,
                           driver_table=driver_table,
                           constructor_table=constructor_table,
                           f1_logo=f1_logo)

@app.route('/points-progression')
@app.route('/points-progression/<int:season>')
def points_progression(season=None):
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

    f1_logo = get_f1_logo_from_wikipedia()

    drivers = driver_stats(df).reset_index()
    drivers_list = [{'name': row['Driver'], 'points': int(row['Total_Points'])}
                   for _, row in drivers.iterrows()]

    races_list = df[['round', 'raceName']].drop_duplicates().sort_values('round')
    races = [{'round': int(row['round'])} for _, row in races_list.iterrows()]

    return render_template('points_progression.html',
                         selected_season=season,
                         seasons=seasons,
                         drivers=drivers_list,
                         races=races,
                         f1_logo=f1_logo)

@app.route('/api/points-progression')
def api_points_progression():
    try:
        season = request.args.get('season')
        selected_drivers = request.args.getlist('drivers')
        up_to_round = request.args.get('up_to_round')

        if not season or not selected_drivers:
            return jsonify({'error': 'Season and drivers are required'}), 400

        df = get_season_data(int(season))
        if df.empty:
            return jsonify({'error': f'No data available for season {season}'}), 404

        filtered_df = df[df['Driver'].isin(selected_drivers)].copy()

        if up_to_round:
            filtered_df = filtered_df[filtered_df['round'] <= int(up_to_round)]

        if filtered_df.empty:
            return jsonify({'error': 'No data found for selected criteria'}), 404

        progression_data = {}
        all_rounds = sorted(filtered_df['round'].unique())

        for driver in selected_drivers:
            driver_data = filtered_df[filtered_df['Driver'] == driver].sort_values('round')
            
            driver_points = {round_num: 0 for round_num in all_rounds}
            for _, row in driver_data.iterrows():
                driver_points[row['round']] = row['points']

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
    driver_details = get_driver_season_details(driver_name, season)
    if not driver_details:
        return render_template('driver_detail.html', error=f"No data for {driver_name} in {season}.")

    race_results = driver_details['race_results']
    if race_results:
        sorted_results = sorted(race_results, key=lambda x: x['round'])

        rounds = [race['round'] for race in sorted_results]
        points_per_race = [race['points'] for race in sorted_results]
        positions = [race['position'] for race in sorted_results]

        cumulative_points_list = []
        total = 0
        for points in points_per_race:
            total += points
            cumulative_points_list.append(total)

        fig = go.Figure()

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

@app.route('/team/<team_name>/<int:season>')
def team_detail(team_name, season):
    team_details = get_team_season_details(team_name, season)
    if not team_details:
        return render_template('team_detail.html', error=f"No data for {team_name} in {season}.")

    # Create points progression chart for the team
    race_results = team_details['race_results']
    if race_results:
        df_team_results = pd.DataFrame(race_results)
        
        # Ensure 'points' column is numeric, coercing errors to NaN then filling with 0
        df_team_results['points'] = pd.to_numeric(df_team_results['points'], errors='coerce').fillna(0)
        
        # Group by round and sum points for the team
        team_points_per_round = df_team_results.groupby('round')['points'].sum().reset_index()
        
        # Calculate cumulative points
        team_points_per_round['cumulative_points'] = team_points_per_round['points'].cumsum()

        fig = go.Figure()
        
        # Cumulative points trace
        fig.add_trace(go.Scatter(
            x=team_points_per_round['round'],
            y=team_points_per_round['cumulative_points'],
            mode='lines+markers',
            name='Cumulative Points',
            line=dict(width=3, color='#1f77b4'), # Blue for cumulative
            marker=dict(size=8),
            hovertemplate='<b>Round %{x}</b><br>Cumulative Points: %{y}<extra></extra>'
        ))
        
        # Points per race bar chart
        fig.add_trace(go.Bar(
            x=team_points_per_round['round'],
            y=team_points_per_round['points'],
            name='Points per Race',
            yaxis='y2', # Use a secondary y-axis
            opacity=0.6,
            marker_color='#ff7f0e', # Orange for points per race
            hovertemplate='<b>Round %{x}</b><br>Points Scored: %{y}<extra></extra>'
        ))

        fig.update_layout(
            title=dict(
                text=f'{team_name} - {season} Season Points Progression',
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
            yaxis2=dict( # Secondary Y-axis definition
                title='Points per Race',
                overlaying='y', # Overlay on the primary y-axis
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

        team_details['chart_json'] = Markup(json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder))

    return render_template('team_detail.html', team=team_details)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)