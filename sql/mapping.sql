-- Save as mapping.csv. Replace WAREHOUSE_DB with the actual destination
-- database for each destination_id. Verify every mapping against metadata.
-- For quoted/case-sensitive names, edit object_name to preserve SQL quoting.
-- SOURCE_TABLE names are source metadata, not a reliable destination map.
SELECT DISTINCT destination_id, connection_name, schema_name, table_name,
       'WAREHOUSE_DB.' || schema_name || '.' || table_name AS object_name
FROM META_DB.PLATFORM.INCREMENTAL_MAR
WHERE measured_date >= '2026-08-01'::DATE
  AND measured_date < '2026-11-01'::DATE;
