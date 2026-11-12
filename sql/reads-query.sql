-- Standard Edition fallback. Save as queries.csv, NOT reads.csv.
-- Lower confidence: SQL text is not lineage; view reads may hide base tables.
-- Strip single-quoted literals in the warehouse before export. Only metadata
-- is queried. Query text can still contain sensitive comments/identifiers;
-- review the local export, keep it local, never upload it.
-- EDIT 2: change 'no' to 'yes' ONLY after editing the exclusion list below.
-- This declaration is exported; user names are not exported.
SELECT 'no' AS excluded_users_declared, query_id, start_time, database_name, schema_name, execution_status,
       REGEXP_REPLACE(query_text, $$'(''|[^'])*'$$, ' ') AS query_text
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= '2026-08-01'::TIMESTAMP_TZ
  AND start_time < '2026-11-01'::TIMESTAMP_TZ
  AND execution_status = 'SUCCESS'
  -- EDIT 1: replace LOADER_USER with the Snowflake user your loader uses.
  -- Add more users as comma-separated quoted values, e.g. 'USER_A', 'USER_B'.
  -- You may also exclude transformation, backup/copy, catalog/quality users.
  AND user_name NOT IN ('LOADER_USER');
