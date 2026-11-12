-- Save as logs.csv. Deliberately excludes message_data (may contain values).
SELECT id, time, connection_id, message_event
FROM META_DB.PLATFORM.LOG
WHERE time >= '2026-08-01'::TIMESTAMP_TZ
  AND time < '2026-11-01'::TIMESTAMP_TZ;
