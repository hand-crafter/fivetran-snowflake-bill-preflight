-- Enterprise Edition or higher. Save as reads.csv.
-- Base objects include tables behind views. Direct objects also retain
-- directly accessed objects. This does not export column values or user names.
WITH access_rows AS (
    SELECT query_id, query_start_time,
           base_objects_accessed, direct_objects_accessed
    FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY
    WHERE query_start_time >= '2026-08-01'::TIMESTAMP_TZ
      AND query_start_time < '2026-11-01'::TIMESTAMP_TZ
      -- EDIT 1: replace LOADER_USER with the Snowflake user your loader uses.
      -- Add more users as comma-separated quoted values, e.g. 'USER_A', 'USER_B'.
      -- You may also exclude transformation, backup/copy, catalog/quality users.
      AND user_name NOT IN ('LOADER_USER')
), objects AS (
    SELECT a.query_id, a.query_start_time, f.value:objectName::STRING AS object_name
    FROM access_rows a, LATERAL FLATTEN(input => a.base_objects_accessed) f
    WHERE UPPER(f.value:objectDomain::STRING) IN
          ('TABLE', 'EXTERNAL TABLE', 'VIEW', 'MATERIALIZED VIEW', 'ICEBERG TABLE')
    UNION
    SELECT a.query_id, a.query_start_time, f.value:objectName::STRING AS object_name
    FROM access_rows a, LATERAL FLATTEN(input => a.direct_objects_accessed) f
    WHERE UPPER(f.value:objectDomain::STRING) IN
          ('TABLE', 'EXTERNAL TABLE', 'VIEW', 'MATERIALIZED VIEW', 'ICEBERG TABLE')
)
-- EDIT 2: change 'no' to 'yes' ONLY after editing the exclusion list above.
-- This declaration is exported; user names are not exported.
SELECT DISTINCT query_id, query_start_time, object_name,
       'no' AS excluded_users_declared
FROM objects
WHERE object_name IS NOT NULL;
