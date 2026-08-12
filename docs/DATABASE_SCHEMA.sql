CREATE TABLE IF NOT EXISTS valuation_runs (
    run_id VARCHAR(64) PRIMARY KEY,
    dataset_name VARCHAR(255) NOT NULL,
    evaluation_year INTEGER NOT NULL,
    institute_code VARCHAR(100) NOT NULL,
    case_count INTEGER NOT NULL,
    variable_count INTEGER NOT NULL,
    total_usable_count INTEGER NOT NULL,
    total_value_krw DOUBLE PRECISION NOT NULL,
    profile_name VARCHAR(255) NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);
