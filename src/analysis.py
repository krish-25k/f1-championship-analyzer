import pandas as pd

def driver_stats(df):
    """
    Calculates total points, wins, and podiums for each driver from a DataFrame.
    """
    # Handle empty dataframe
    if df.empty:
        return pd.DataFrame(columns=['Total_Points', 'Wins', 'Podiums'])
    
    # Group the DataFrame by the driver's name and aggregate the results.
    stats = df.groupby('Driver').agg(
        Total_Points=('points', 'sum'),
        Wins=('position', lambda pos: (pos == 1).sum()),
        Podiums=('position', lambda pos: pos.isin([1, 2, 3]).sum())
    )
    # Convert all calculated columns to simple integers and sort the table by Total Points.
    return stats.astype(int).sort_values(by='Total_Points', ascending=False)

def constructor_stats(df):
    """
    Calculates total points and wins for each constructor.
    """
    # Handle empty dataframe
    if df.empty:
        return pd.DataFrame(columns=['Total_Points', 'Wins'])
    
    # This is similar to driver_stats but groups by the constructor's name.
    stats = df.groupby('Constructor_name').agg(
        Total_Points=('points', 'sum'),
        Wins=('position', lambda pos: (pos == 1).sum())
    )
    return stats.astype(int).sort_values(by='Total_Points', ascending=False)

def cumulative_points(df):
    """
    Calculates the cumulative points progression for all drivers over the season.
    Fixed version with better error handling and debugging.
    """
    # Handle empty dataframe
    if df.empty:
        print("cumulative_points: DataFrame is empty")
        return pd.DataFrame()
    
    try:
        print(f"cumulative_points: Processing {len(df)} records")
        print(f"Columns: {df.columns.tolist()}")
        print(f"Unique rounds: {sorted(df['round'].unique())}")
        print(f"Unique drivers: {df['Driver'].nunique()}")
        
        # Create a pivot table with rounds as index and drivers as columns
        # Use sum to handle cases where a driver might have multiple entries per round
        pivot = df.pivot_table(
            index='round', 
            columns='Driver', 
            values='points', 
            aggfunc='sum',  # Sum points in case of duplicates
            fill_value=0
        )
        
        print(f"Pivot table created. Shape: {pivot.shape}")
        print(f"Sample pivot data:\n{pivot.head()}")
        
        # Calculate cumulative sum
        cumulative = pivot.cumsum()
        
        print(f"Cumulative sum calculated. Shape: {cumulative.shape}")
        print(f"Sample cumulative data:\n{cumulative.head()}")
        
        return cumulative
    
    except Exception as e:
        print(f"Error in cumulative_points: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()