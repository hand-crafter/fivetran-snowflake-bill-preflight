-- Save as coverage.csv. Keep only the chosen read path (reads OR queries).
-- These are REQUESTED dates, not a claim that the underlying history exists.
-- Leave complete=false unless you verified full retention, role visibility,
-- export completeness and latency for that input for this entire window.
-- Edit an individual CSV row to true only after that verification. A sparse
-- event export can be complete; min/max event dates alone cannot establish it.
SELECT 'billing' AS input, '2026-08-01' AS start_date,
       '2026-10-31' AS end_date, 'false' AS complete
UNION ALL SELECT 'logs', '2026-08-01', '2026-10-31', 'false'
UNION ALL SELECT 'reads', '2026-08-01', '2026-10-31', 'false'
UNION ALL SELECT 'queries', '2026-08-01', '2026-10-31', 'false';
