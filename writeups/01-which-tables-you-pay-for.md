# Find the tables behind your Fivetran row count

A monthly active row (MAR) is a distinct row that Fivetran syncs during a calendar month, identified by its primary key: the value that distinguishes it from other rows. Inserts, updates and captured deletes can count; repeated changes to the same row in that month count once. Rows classified as free are excluded from paid MAR. This measures activity, not every row stored in a table. See Fivetran's [definition and free categories](https://fivetran.com/docs/core-concepts/usage-based-pricing) (read 2026-11-12).

Prepared from the vendors' public documentation. Not affiliated with or endorsed by Fivetran or Snowflake.

## Start with the free numbers

You already have a per-table view. In Fivetran, the account's **Billing & Usage** area shows overall usage, while **Connection Details → Usage** shows a connection and its tables. A connection is one configured source-to-destination data feed. These views are described in [Monitor and Optimize Usage](https://fivetran.com/docs/core-concepts/usage-based-pricing/tracking-and-optimizing-usage) (read 2026-11-12).

For a repeatable query, use the metadata already delivered to your warehouse by the Fivetran Platform connection. Viewing usage has no additional Fivetran charge, and Fivetran says the Platform connection's MAR is free. Running warehouse queries uses warehouse compute, so this is not a promise of zero total cost. See [Monitor and Optimize Usage](https://fivetran.com/docs/core-concepts/usage-based-pricing/tracking-and-optimizing-usage) (read 2026-11-12).

The [Platform table reference](https://fivetran.com/docs/logs/fivetran-platform/table-reference) (read 2026-11-12) names the useful fields:

| Table | Columns to use | What it gives you |
|---|---|---|
| `INCREMENTAL_MAR` | `destination_id`, `connection_name`, `schema_name`, `table_name`, `measured_date`, `incremental_rows`, `free_type`, `sync_type`, `updated_at` | Daily row increments, table identity, billing category, sync category and update time |
| `USAGE_COST` | `measured_month`, `group_id`, `amount` | Monthly dollars per destination, not per table |
| `CREDITS_USED` | `measured_month`, `group_id`, `credits_consumed` | Monthly credits for credit-based billing |
| `TRANSFORMATION_RUNS` | `destination_id`, `job_id`, `measured_date`, `free_type`, `model_runs` | Transformation model runs, a separate usage measure |

Use the first table for the row ranking below. Keep the destination and connection in the result so identical table names in different feeds stay separate.

## Paste this query

Replace `META_DB.PLATFORM` with the database and schema containing your existing Platform tables. This read-only query follows `sql/billing.sql`, then groups its daily increments into months. It selects `PAID` explicitly using the [documented billing category](https://fivetran.com/docs/logs/fivetran-platform/table-reference) (read 2026-11-12).

The bounds select the last three complete calendar months and exclude the current partial month. Use a UTC session because [Fivetran measures MAR in UTC](https://fivetran.com/docs/core-concepts/usage-based-pricing/tracking-and-optimizing-usage) (read 2026-11-12).

```sql
SELECT
    DATE_TRUNC('MONTH', measured_date)::DATE AS billing_month,
    destination_id,
    connection_name,
    schema_name,
    table_name,
    SUM(incremental_rows) AS paid_rows
FROM META_DB.PLATFORM.INCREMENTAL_MAR
WHERE measured_date >= DATEADD(
          'MONTH', -3, DATE_TRUNC('MONTH', CURRENT_DATE()))
  AND measured_date < DATE_TRUNC('MONTH', CURRENT_DATE())
  AND free_type = 'PAID'
GROUP BY 1, 2, 3, 4, 5
ORDER BY paid_rows DESC, billing_month DESC,
         destination_id, connection_name, schema_name, table_name;
```

On November 12, 2026, those bounds cover August through October. The ranking is largest first across all three months. It sums row increments, not the number of records in the metadata table.

**Invented result excerpt: all names and numbers below are made up.**

| Month | Destination | Connection | Schema | Table | Paid rows |
|---|---|---|---|---|---:|
| 2026-10-01 | demo_dest | shop_feed | shop | order_events | 820,000 |
| 2026-09-01 | demo_dest | shop_feed | shop | order_events | 760,000 |
| 2026-08-01 | demo_dest | shop_feed | shop | order_events | 710,000 |
| 2026-10-01 | demo_dest | help_feed | help | ticket_changes | 240,000 |
| 2026-10-01 | demo_dest | shop_feed | shop | customers | 95,000 |

These are row counts, not allocated dollars. Treat the list as a starting point for checking ownership and purpose.

## Three easy mistakes

**1. Expecting fewer syncs to mean fewer paid rows.** Fivetran's Monitor and Optimize Usage page says:

> “makes no difference to your monthly active rows”

Source: [Monitor and Optimize Usage, Sync frequency](https://fivetran.com/docs/core-concepts/usage-based-pricing/tracking-and-optimizing-usage#syncfrequency) (read 2026-11-12). The statement refers to sync frequency: the count follows distinct changed rows, rather than how often you fetch them.

**2. Treating every synced row as paid.** Fivetran's Usage-Based Pricing page says:

> “Free MAR represents rows that are synced but do not count towards paid MAR.”

Source: [Usage-Based Pricing, Free MAR](https://fivetran.com/docs/core-concepts/usage-based-pricing#freemar) (read 2026-11-12). Its categories include initial syncs, connection trials, private-preview connectors excluding destinations, system tables, Platform connections, qualifying re-syncs, the troubleshooting window, legacy pricing plans, the Free plan and promotions. Re-sync eligibility has conditions; do not label all historical activity free. The query uses the recorded `PAID` category instead of guessing from sync type.

**3. Assuming a newly added Platform connection gives you a complete archive.** Its overview says:

> “we sync the previous 7 days' worth of data prior to the date of the initial sync”

Source: [Fivetran Platform Connector, Sync overview](https://fivetran.com/docs/logs/fivetran-platform#syncoverview) (read 2026-11-12). That backfill discussion concerns `LOG` and `CONNECTOR_SDK_LOG`, including a seven-day history on full re-sync. Treat the connection's initial sync as your collection starting point and verify earlier coverage. The cited page does not establish a universal earliest date for `INCREMENTAL_MAR`; seven days of event logs cannot prove three months of billing coverage. Missing months are not zero usage.

## What the ranking cannot answer

Paid-row counts cannot tell you whether anyone reads a table; that needs separate read history.

They also cannot tell you what removing a table would change on a bill with a commitment or minimum; that needs your contract terms and a bill calculation.

## Sources

- [Fivetran Usage-Based Pricing](https://fivetran.com/docs/core-concepts/usage-based-pricing) — read 2026-11-12.
- [Fivetran Monitor and Optimize Usage](https://fivetran.com/docs/core-concepts/usage-based-pricing/tracking-and-optimizing-usage) — read 2026-11-12.
- [Fivetran Platform table reference](https://fivetran.com/docs/logs/fivetran-platform/table-reference) — read 2026-11-12.
- [Fivetran Platform Connector](https://fivetran.com/docs/logs/fivetran-platform) — read 2026-11-12.

Check: the query parsed as one read-only SELECT with sqlglot 30.31.0, using the Snowflake dialect and the procedure in `docs/sql-parse-check.txt`. Parsing does not validate warehouse permissions or results. It has not been run against a warehouse. This tool has been checked only on made-up data.

The free preflight in this repository prints the same per-table view from exported files.  
The paid report (US$149, once) adds the read history and the bill scenarios.
