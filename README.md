# NASA Near-Earth Object (NEO) & Orbital Risk Tracker

An automated data engineering pipeline and risk assessment engine that ingests real-time near-Earth asteroid telemetry from NASA's NeoWS (Near Earth Object Web Service) REST API, normalizes data into a relational SQLite schema, and executes analytical SQL queries to detect Potentially Hazardous Asteroids (PHAs).

---

## Technical Architecture

1. **Ingestion Layer:** REST API telemetry extraction with automated pagination handling over dynamic observation windows.
2. **Relational Database Schema (SQLite):**
   * `asteroids`: Master dimension table containing physical parameters (absolute magnitude $H$, estimated minimum/maximum diameter).
   * `close_approaches`: Fact table storing encounter kinetics (relative velocity, epoch timestamp, miss distance, orbiting body) linked via `neo_id` foreign key.
3. **Analytics Engine:** SQL multi-table joins computing metric lunar distances ($1\text{ LD} \approx 384,400\text{ km}$) and isolating objects meeting NASA PHA criteria ($H \le 22.0$ and Minimum Orbit Intersection Distance $\le 0.05\text{ AU}$).
4. **Orbital Visualization:** Multi-variable scatter visualization mapping proximity against relative velocity, with marker areas proportional to estimated mean diameter.

---

## Database Schema

```sql
CREATE TABLE asteroids (
    neo_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    absolute_magnitude REAL,
    estimated_diameter_min_km REAL,
    estimated_diameter_max_km REAL,
    is_potentially_hazardous INTEGER
);

CREATE TABLE close_approaches (
    approach_id INTEGER PRIMARY KEY AUTOINCREMENT,
    neo_id TEXT,
    close_approach_date TEXT,
    epoch_date_close_approach INTEGER,
    relative_velocity_km_s REAL,
    miss_distance_km REAL,
    orbiting_body TEXT,
    FOREIGN KEY (neo_id) REFERENCES asteroids (neo_id)
);