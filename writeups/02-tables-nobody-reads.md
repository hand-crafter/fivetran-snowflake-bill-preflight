# Find paid tables with no reads observed

Of the tables you pay to keep loaded, start with those for which no reads were observed lately. Bring that list to each table's owner. A quiet table may support an annual report or a duty that does not involve regular queries. Missing evidence may also reflect incomplete history. The result starts a conversation about purpose and coverage; it is never a verdict that a table can go.

Prepared with AI agents from the vendors' public documentation. Not affiliated with or endorsed by Fivetran or Snowflake.

## Two places to look for reads

Snowflake's Account Usage views contain metadata: records about activity, rather than the contents of your tables. Its [Account Usage overview](https://docs.snowflake.com/en/sql-reference/account-usage) (read 2026-11-12) lists edition requirements and access privileges. Use an existing role that can read the history; seeing the database does not establish that permission.

| History | What it tells you | Edition, retention and delay |
|---|---|---|
| `SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY` | Objects read, including base tables behind views | Enterprise Edition or higher; 365 days; delay up to 180 minutes (3 hours). [Reference](https://docs.snowflake.com/en/sql-reference/account-usage/access_history) (read 2026-11-12). |
| `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY` | Query text for matching table references, without resolved table dependencies | Every edition, subject to privileges; 365 days; delay up to 45 minutes. [Reference](https://docs.snowflake.com/en/sql-reference/account-usage/query_history) and [edition listing](https://docs.snowflake.com/en/sql-reference/account-usage) (both read 2026-11-12). |

A view is a saved query over other objects. Access history distinguishes objects named directly from the underlying tables supplying data; see Snowflake's [read example](https://docs.snowflake.com/en/user-guide/access-history#read) (read 2026-11-12). Query-text matching alone misses underlying tables read through views and other indirect reads. That limitation follows from comparing the two records; it is not evidence that the underlying table was quiet.

Do not confuse the Account Usage query history above with the similarly named Information Schema function. The latter covers only seven days, according to the [QUERY_HISTORY reference](https://docs.snowflake.com/en/sql-reference/account-usage/query_history) (read 2026-11-12).

## The loader can look like a reader

Snowflake's ACCESS_HISTORY page includes these exact excerpts under Read query notes:

> “DML operations that read data”

> “UPDATE, DELETE, and MERGE.”

Source for both excerpts: [ACCESS_HISTORY, Usage notes](https://docs.snowflake.com/en/sql-reference/account-usage/access_history#usage-notes) (read 2026-11-12). DML means statements that change data. The qualification matters: these statements must also read data to count here.

Our inference is that a loading tool's own work can make every loaded table look read. Counting all recorded readers can therefore hide the very tables this check aims to find. Leave out the Snowflake user the loading tool signs in as. This exclusion follows from the documentation; we have not confirmed its effect on a real account. It does not mean every merge always reads every destination table.

Other machine readers can hide a table no person uses: transformation jobs that build derived tables, backup or copy jobs, catalog scanners that inventory data, and data-quality scanners that check it. Review those identities separately. A transformation may feed an essential report. A shared machine user may also run business queries, so excluding it can hide useful reads too.

## Paste this query

This Enterprise Edition path follows `sql/reads-object.sql`. Replace `'LOADER_USER'` with the exact user your loader uses; include all loader identities if there are several. The query reads metadata only. Running it uses warehouse compute, as described in Snowflake's [warehouse overview](https://docs.snowflake.com/en/user-guide/warehouses-overview) (read 2026-11-12).

```sql
WITH access_rows AS (
    SELECT query_id, query_start_time,
           base_objects_accessed, direct_objects_accessed
    FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY
    WHERE query_start_time >= DATEADD('DAY', -90, CURRENT_TIMESTAMP())
      AND query_start_time < CURRENT_TIMESTAMP()
      AND user_name NOT IN ('LOADER_USER')
), objects AS (
    SELECT a.query_id, a.query_start_time,
           f.value:objectName::STRING AS object_name
    FROM access_rows a, LATERAL FLATTEN(input => a.base_objects_accessed) f
    WHERE UPPER(f.value:objectDomain::STRING) IN
          ('TABLE', 'EXTERNAL TABLE', 'VIEW', 'MATERIALIZED VIEW', 'ICEBERG TABLE')
    UNION
    SELECT a.query_id, a.query_start_time,
           f.value:objectName::STRING AS object_name
    FROM access_rows a, LATERAL FLATTEN(input => a.direct_objects_accessed) f
    WHERE UPPER(f.value:objectDomain::STRING) IN
          ('TABLE', 'EXTERNAL TABLE', 'VIEW', 'MATERIALIZED VIEW', 'ICEBERG TABLE')
)
SELECT DISTINCT query_id, query_start_time, object_name
FROM objects
WHERE object_name IS NOT NULL;
```

Compare this output with the paid-row ranking in [write-up 1](01-which-tables-you-pay-for.md) using an anti-join by table name: keep paid tables with no matching read, after mapping each billing table to its full destination database, schema and table name. Match names with care around case, quoting, renamed or re-created tables; a failed name match is not evidence of no reads.

The output retains a statement identifier and time alongside each object name. It combines direct and base objects, and keeps table and view kinds. It omits the tool's separate exclusion declaration column. The last three hours may still be arriving, given the documented delay above. Confirm complete coverage before interpreting an absence; an empty result needs investigation, not a removal list.

## What a quiet table still might be

- Read once a quarter or once a year: check the reporting calendar with its owner.
- Read by another account through a share: consumer queries are not visible to the provider in this history; see [data sharing notes](https://docs.snowflake.com/en/sql-reference/account-usage/access_history#usage-notes) (read 2026-11-12).
- Kept for a legal or audit duty: confirm the retention obligation before discussing removal.
- Read outside the window: ninety quiet days cannot establish its longer-term purpose.

## Sources

- [Snowflake ACCESS_HISTORY reference](https://docs.snowflake.com/en/sql-reference/account-usage/access_history) — read 2026-11-12.
- [Snowflake QUERY_HISTORY reference](https://docs.snowflake.com/en/sql-reference/account-usage/query_history) — read 2026-11-12.
- [Snowflake Account Usage overview](https://docs.snowflake.com/en/sql-reference/account-usage) — read 2026-11-12.
- [Snowflake Access History guide](https://docs.snowflake.com/en/user-guide/access-history) — read 2026-11-12.
- [Snowflake warehouse overview](https://docs.snowflake.com/en/user-guide/warehouses-overview) — read 2026-11-12.

Check: the query parsed as one read-only SELECT with sqlglot 30.31.0, using the Snowflake dialect and the procedure in `docs/sql-parse-check.txt`. Parsing does not validate warehouse permissions or results. It has not been run against a warehouse. This tool has been checked only on made-up data.

The free preflight in this repository tells you whether your exports can answer this question; it does not list the tables.  
The paid report (US$149, once) lists the paid tables with no reads observed and adds the bill scenarios.
