CREATE TABLE IF NOT EXISTS towers (
    line_id TEXT NOT NULL,
    longitude REAL,
    latitude REAL,
    height_m REAL,
    tower_type TEXT,
    material TEXT,
    risk_level TEXT,
    collected_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    example1 TEXT,
    example2 TEXT,
    example3 TEXT,
    example4 TEXT,
    example5 TEXT
);

CREATE TABLE IF NOT EXISTS geology_records (
    humidity_percent REAL,
    illumination_lux REAL,
    pressure_kpa REAL,
    rainfall_mm REAL,
    temperature_c REAL,
    wind_direction_deg REAL,
    wind_speed_mps REAL,
    soil_moisture_percent REAL,
    soil_temperature_c REAL,
    collected_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    example1 TEXT,
    example2 TEXT,
    example3 TEXT,
    example4 TEXT,
    example5 TEXT
);

CREATE TABLE IF NOT EXISTS schema_field_descriptions (
    table_name TEXT NOT NULL,
    field_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    data_type TEXT NOT NULL,
    description TEXT NOT NULL,
    is_required INTEGER NOT NULL DEFAULT 0,
    is_primary_key INTEGER NOT NULL DEFAULT 0,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(table_name, field_name)
);

CREATE INDEX IF NOT EXISTS idx_towers_line_id ON towers(line_id);
CREATE INDEX IF NOT EXISTS idx_towers_risk_level ON towers(risk_level);
CREATE INDEX IF NOT EXISTS idx_towers_collected_at ON towers(collected_at);
CREATE INDEX IF NOT EXISTS idx_geology_records_collected_at ON geology_records(collected_at);
