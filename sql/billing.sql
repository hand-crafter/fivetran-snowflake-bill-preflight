-- Save as billing.csv, with column headers. Replace META_DB.PLATFORM.
-- All export files must use the same requested calendar window.
-- Dates below select three complete months; replace both endpoints together.
SELECT destination_id, connection_name, schema_name, table_name,
       measured_date, sync_type, free_type, incremental_rows, updated_at
FROM META_DB.PLATFORM.INCREMENTAL_MAR
WHERE measured_date >= '2026-08-01'::DATE
  AND measured_date < '2026-11-01'::DATE;
