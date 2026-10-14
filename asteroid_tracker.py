import sqlite3
import requests
import datetime
import pandas as pd
import matplotlib.pyplot as plt

DB_NAME = "neo_tracker.db"

def init_db():
    """Initializes the normalized SQLite relational database schema."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Asteroid master entity table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS asteroids (
        neo_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        absolute_magnitude REAL,
        estimated_diameter_min_km REAL,
        estimated_diameter_max_km REAL,
        is_potentially_hazardous INTEGER
    )
    """)
    
    # Close-approach events table (1-to-many relationship with foreign key)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS close_approaches (
        approach_id INTEGER PRIMARY KEY AUTOINCREMENT,
        neo_id TEXT,
        close_approach_date TEXT,
        epoch_date_close_approach INTEGER,
        relative_velocity_km_s REAL,
        miss_distance_km REAL,
        orbiting_body TEXT,
        FOREIGN KEY (neo_id) REFERENCES asteroids (neo_id)
    )
    """)
    
    conn.commit()
    conn.close()
    print("✓ SQLite schema initialized.")

def fetch_and_store_neo_data(days=7):
    """Fetches real-time NEO telemetry from NASA NeoWS and populates database."""
    today = datetime.date.today()
    start_date = today.strftime("%Y-%m-%d")
    end_date = (today + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    
    url = "https://api.nasa.gov/neo/rest/v1/feed"
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "api_key": "DEMO_KEY"
    }
    
    print(f"1. Fetching NASA NeoWS telemetry ({start_date} to {end_date})...")
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        raise Exception(f"NASA API query failed ({response.status_code}): {response.text}")
        
    data = response.json()
    neo_objects = data.get("near_earth_objects", {})
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    asteroid_count = 0
    approach_count = 0
    
    for date_str, items in neo_objects.items():
        for item in items:
            neo_id = item["id"]
            name = item["name"]
            abs_mag = float(item["absolute_magnitude_h"])
            diam_min = float(item["estimated_diameter"]["kilometers"]["estimated_diameter_min"])
            diam_max = float(item["estimated_diameter"]["kilometers"]["estimated_diameter_max"])
            is_pha = 1 if item["is_potentially_hazardous_asteroid"] else 0
            
            cursor.execute("""
            INSERT OR IGNORE INTO asteroids 
            (neo_id, name, absolute_magnitude, estimated_diameter_min_km, estimated_diameter_max_km, is_potentially_hazardous)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (neo_id, name, abs_mag, diam_min, diam_max, is_pha))
            asteroid_count += 1
            
            for ca in item["close_approach_data"]:
                c_date = ca["close_approach_date"]
                epoch_date = int(ca["epoch_date_close_approach"])
                rel_vel = float(ca["relative_velocity"]["kilometers_per_second"])
                miss_km = float(ca["miss_distance"]["kilometers"])
                orb_body = ca["orbiting_body"]
                
                cursor.execute("""
                INSERT INTO close_approaches 
                (neo_id, close_approach_date, epoch_date_close_approach, relative_velocity_km_s, miss_distance_km, orbiting_body)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (neo_id, c_date, epoch_date, rel_vel, miss_km, orb_body))
                approach_count += 1
                
    conn.commit()
    conn.close()
    print(f"✓ Ingested {asteroid_count} asteroids and {approach_count} close-approach records.")

def run_analytical_queries():
    """Executes SQL JOIN query to rank closest encounters."""
    conn = sqlite3.connect(DB_NAME)
    
    # 1 Lunar Distance (LD) ≈ 384,400 km
    query = """
    SELECT 
        a.name,
        ROUND((a.estimated_diameter_min_km + a.estimated_diameter_max_km) / 2.0 * 1000, 1) AS avg_diameter_m,
        ROUND(c.relative_velocity_km_s, 2) AS velocity_km_s,
        ROUND(c.miss_distance_km / 384400.0, 2) AS miss_dist_lunar,
        c.close_approach_date,
        a.is_potentially_hazardous
    FROM asteroids a
    JOIN close_approaches c ON a.neo_id = c.neo_id
    ORDER BY c.miss_distance_km ASC
    LIMIT 10;
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print("\n================ TOP 10 CLOSEST APPROACHES ================")
    print(df.to_string(index=False))
    print("===========================================================\n")
    return df

def plot_asteroid_risk(df):
    """Generates scatter visualization of proximity vs velocity."""
    plt.figure(figsize=(10, 6))
    
    haz = df[df["is_potentially_hazardous"] == 1]
    non_haz = df[df["is_potentially_hazardous"] == 0]
    
    plt.scatter(
        non_haz["miss_dist_lunar"], 
        non_haz["velocity_km_s"], 
        s=non_haz["avg_diameter_m"].clip(lower=20), 
        c="deepskyblue", 
        alpha=0.6, 
        edgecolors="black", 
        label="Non-Hazardous"
    )
    
    if not haz.empty:
        plt.scatter(
            haz["miss_dist_lunar"], 
            haz["velocity_km_s"], 
            s=haz["avg_diameter_m"].clip(lower=20), 
            c="crimson", 
            alpha=0.8, 
            edgecolors="black", 
            label="Potentially Hazardous (PHA)"
        )
        
    for _, row in df.head(5).iterrows():
        plt.annotate(
            row["name"], 
            (row["miss_dist_lunar"], row["velocity_km_s"]),
            textcoords="offset points", 
            xytext=(0, 10), 
            ha='center', 
            fontsize=8
        )
        
    plt.axvline(1.0, color="orange", linestyle="--", alpha=0.7, label="Lunar Distance (1 LD ≈ 384,400 km)")
    plt.title("NASA Near-Earth Asteroid Close Approaches (Upcoming 7 Days)", fontsize=12, fontweight='bold')
    plt.xlabel("Miss Distance (Lunar Distances)", fontsize=11)
    plt.ylabel("Relative Velocity (km/s)", fontsize=11)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(loc="upper right")
    plt.tight_layout()
    
    plt.savefig("asteroid_encounters.png", dpi=300)
    print("✓ Plot saved as 'asteroid_encounters.png'.")
    plt.show()

if __name__ == "__main__":
    init_db()
    fetch_and_store_neo_data(days=7)
    df_results = run_analytical_queries()
    plot_asteroid_risk(df_results)