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
    disaster_type TEXT,
    longitude TEXT,
    latitude TEXT,
    clay_content_percent REAL,
    silt_content_percent REAL,
    sand_content_percent REAL,
    soil_moisture_percent REAL,
    porosity_percent REAL,
    permeability_mm_h REAL,
    cohesion_kpa REAL,
    soil_thickness_m REAL,
    bedrock_depth_m REAL,
    slope_degree REAL,
    aspect_degree REAL,
    relative_relief_m REAL,
    terrain_relief_m_per_km2 REAL,
    twi REAL,
    tri REAL,
    ndvi REAL,
    vegetation_coverage_percent REAL,
    lai_m2_m2 REAL,
    canopy_coverage_percent REAL,
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
CREATE INDEX IF NOT EXISTS idx_geology_records_created_at ON geology_records(created_at);
