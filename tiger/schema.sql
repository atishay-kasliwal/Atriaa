-- Tiger Data (TimescaleDB) side of Atria: the vitals time series.
-- Supabase stays the system of record; the backend mirrors every vitals event here.
-- Safe to repeat:  psql "$TIGER_DATABASE_URL" -f tiger/schema.sql

CREATE TABLE IF NOT EXISTS vitals (
  observed_at timestamptz NOT NULL,
  patient_id  uuid        NOT NULL,
  run_id      text        NOT NULL,          -- 'live', 'run-xxxx' (replay) or 'history' (seed)
  event_key   text        NOT NULL,
  hr          int,
  spo2        int,
  pain        int,
  ingested_at timestamptz NOT NULL DEFAULT now(),
  -- A hypertable's unique keys must include the time column.
  UNIQUE (event_key, observed_at)
);

SELECT create_hypertable('vitals', by_range('observed_at', INTERVAL '1 day'), if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS vitals_patient_time_idx ON vitals (patient_id, observed_at DESC);

-- Columnar compression. Segments per run, ordered by patient then time, so each column
-- compresses as long runs of similar values. Per-patient reads go through the aggregates.
ALTER TABLE vitals SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'run_id',
  timescaledb.compress_orderby = 'patient_id, observed_at DESC'
);
SELECT add_compression_policy('vitals', INTERVAL '2 days', if_not_exists => TRUE);

-- Per-patient 5-minute trend buckets. Real-time (materialized_only = false), so a re-check
-- entered seconds ago is already in the answer.
CREATE MATERIALIZED VIEW IF NOT EXISTS vitals_5m
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
  time_bucket(INTERVAL '5 minutes', observed_at) AS bucket,
  run_id,
  patient_id,
  count(*)                  AS readings,
  round(avg(hr), 1)         AS hr_avg,
  max(hr)                   AS hr_max,
  min(spo2)                 AS spo2_min,
  round(avg(spo2), 1)       AS spo2_avg,
  max(pain)                 AS pain_max
FROM vitals
GROUP BY bucket, run_id, patient_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('vitals_5m',
  start_offset => INTERVAL '30 days',
  end_offset => INTERVAL '5 minutes',
  schedule_interval => INTERVAL '1 minute',
  if_not_exists => TRUE);

-- Ward-level hourly load, built on top of the 5-minute aggregate (hierarchical cagg).
CREATE MATERIALIZED VIEW IF NOT EXISTS vitals_hourly
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
  time_bucket(INTERVAL '1 hour', bucket) AS hour,
  sum(readings)                         AS readings,
  count(*)                              AS patient_buckets,
  round(avg(hr_avg), 1)                 AS hr_avg,
  min(spo2_min)                         AS spo2_min,
  sum(CASE WHEN spo2_min < 92 THEN 1 ELSE 0 END) AS low_spo2_buckets
FROM vitals_5m
GROUP BY hour
WITH NO DATA;

SELECT add_continuous_aggregate_policy('vitals_hourly',
  start_offset => INTERVAL '30 days',
  end_offset => INTERVAL '1 hour',
  schedule_interval => INTERVAL '5 minutes',
  if_not_exists => TRUE);
