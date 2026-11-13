# Fivetran + Snowflake bill preflight

See which tables and connections contribute paid rows each month, and whether your metadata exports cover the questions a full bill report would ask.

On 12 November 2026 the seven SQL files each ran without error on one Snowflake trial account that we opened ourselves, against small hand-made tables shaped like the vendor's documented metadata tables. They have not run on real Fivetran data, a real customer's account or an invoice. Not affiliated with or endorsed by Fivetran or Snowflake.

## What the free preflight shows

Input presence, record counts, distinct observed dates, earliest/latest activity and declared coverage for every input; the loader-exclusion declaration; paid rows per table and connection by month; the share of rows marked free; and which full-report findings the coverage would support. It does not list removal candidates or calculate paid findings.

Five lines from the made-up sample JSON (these fields appear in the generated file):

```text
  "level": "preflight",
  "sample_notice": "made-up data, no real account",
  "free_rows": 1800000,
  "total_rows": 20400000,
  "free_share": "0.088235",
```

## Try the made-up example

Python 3.10+; standard library only, no packages to install. From this folder:

```sh
python3 generate_fixtures.py fixtures
python3 preflight.py fixtures --output sample/preflight-report
python3 -m unittest discover
```

Open `sample/preflight-report.html` locally. Each run also writes CSV and JSON with the same findings; CSV has a section column and a JSON-encoded value column so nested evidence is retained. The generator uses seed 149: six connections, sixty tables and three billing months. There is no pricing file or full-report code in this folder. HTML has inline styles, no scripts or remote assets.

## Run on your own metadata

1. Make a local `exports/` folder. Do not copy the synthetic `manifest.json` into it. Choose up to three **complete calendar billing months**; the shipped example window is August 1 through October 31, 2026. In every SQL file change both the start (`>=`) and exclusive end (`<`) dates together. End the window at least three hours before export to allow documented read-history latency; extra time may be needed if your metadata is delayed.
2. In the Snowflake worksheet use an existing role with permission to read the relevant metadata. Replace `META_DB.PLATFORM` in the SQL files with your existing Fivetran Platform schema. Nothing here provisions it or requests additional permissions. If it is absent, you cannot reconstruct prior billing/log history with this tool.
3. Run `sql/billing.sql`, `sql/connections.sql` and `sql/logs.sql` separately. Save each result, **with headers and without result truncation**, into `exports/billing.csv`, `exports/connections.csv`, and `exports/logs.csv`. The runner accepts upper- or lowercase CSV column headers. LOG exports omit message payloads and connection exports omit settings. Missing logs are allowed and limit explanations.
4. Pick one read path. **Before running either query, edit both marked settings:** replace `'LOADER_USER'` in `user_name NOT IN (...)` with the Snowflake user your loading tool signs in as (multiple quoted user names are allowed). Then change the separate `excluded_users_declared` constant from `'no'` to `'yes'`. Exclusions run inside the warehouse; no user-name column is exported. Keep the declaration column in the CSV. Missing declarations or any value other than `yes` block candidate findings. **Enterprise Edition or higher:** run `sql/reads-object.sql`, save `exports/reads.csv`. This uses base and direct objects in `ACCOUNT_USAGE.ACCESS_HISTORY`. **Standard Edition fallback:** run `sql/reads-query.sql`, save `exports/queries.csv`, and add `--read-path query` to runner commands. This matches relation references in query text with lower confidence; it does not resolve views to their base tables. The SQL strips single-quoted literals before export, but comments, dollar-quoted SQL and identifiers may still be sensitive metadata. Review the export locally. No query against customer table contents is shipped.
5. Run `sql/mapping.sql`, save `exports/mapping.csv`. Replace `WAREHOUSE_DB` with the actual destination database and verify **every** mapping. An unquoted `WAREHOUSE_DB` database (any letter case) is an input error. Its four billing identity columns must map to a unique three-part Snowflake object name. Use SQL quoting for case-sensitive names, for example `"Warehouse"."Sales"."Orders"`. Multiple destinations need their correct database separately. Renames, schema transformations and shared object names require human verification; duplicate or ambiguous mappings fail closed. Missing mappings limit what the full report could establish; verify all mappings before relying on its findings.
6. Run `sql/coverage.sql`, save `exports/coverage.csv`. Keep the selected read-path row. It records **requested dates**, not guaranteed history. For each input separately, only change `complete` from `false` to `true` after checking retention, full role visibility, ingestion/export completeness and latency for the entire stated window. Shorten its inclusive start/end dates to the history you can actually attest; re-export that input with the same bounds. Do not infer completeness from earliest/latest events. A complete export can have zero events. Only seven days of LOG are backfilled when the Platform connection is initially synced or re-synced.
7. Run the free check:

   ```sh
   python3 preflight.py exports --output reports/preflight
   # Standard Edition alternative:
   python3 preflight.py exports --read-path query --output reports/preflight
   ```

   Both preflight and full reports explain blocked read screening with these messages:

   - “loader statements were not excluded, so reads cannot be trusted”: edit the exclusion list and declaration in the chosen SQL query, then re-export.
   - “no mapped table appears in read history; the mapping or database name is probably wrong”: verify every destination mapping and database before re-exporting. This is a guard, not proof that the mapping is wrong.
   - “read history is empty”: a header-only export produces no candidates even with complete declared coverage and the declaration header present. Check the export, window, role visibility and exclusions; there is no per-row declaration to inspect.

   It shows input presence, row count, distinct observed dates, earliest/latest activity, declared coverage, paid rows per table and connection by month, and the overall share of rows marked free. It explains which full-report findings the coverage supports. It produces no per-table removal candidates, spikes or priced scenarios.

## Write-ups

- [Which tables you pay for](writeups/01-which-tables-you-pay-for.md): one query over the billing metadata already in your warehouse.
- [Find paid tables with no reads observed](writeups/02-tables-nobody-reads.md): where read history lives, what it misses, and who to ask before removing anything.

## What the paid report adds

The full download lists paid tables with no reads observed in the covered window, compares large monthly row increases with logged events, and models individual and combined removals using the buyer's contract terms. It distinguishes near-term costs from potential renewal costs and does not add alternative removal estimates together. It requires the same exports; costs also require the buyer's pricing terms. See the [full report example](sample/full-report-example.html), generated from made-up data and invented prices. Its generating code is sold separately.

## What the report can and cannot say

- **Every removal is a candidate, confirm with the table owner.** It says “no reads observed in N days.” It cannot see every indirect reader: shares, quarterly jobs, retention duties, other accounts and activity outside the window remain untested. A short quiet window is weak evidence.
- Loader DML that reads data can count as a read. Other automated readers (transformation jobs, backup or copy jobs, catalog or quality scanners) still count as reads and may hide tables with no business readers. You may add those users to the same warehouse exclusion list; confirm that shared service users do not also run business queries. The declaration is your attestation, not an independent check of the edited SQL.
- Object-level history requires Enterprise Edition or higher, retains up to 365 days and can lag three hours. Query history is available to all editions with the right privileges, retains up to 365 days and can lag 45 minutes. The similarly named Information Schema function covers only seven days. See [the dated documentation ledger](docs/sources.md).
- The query-text fallback is intentionally incomplete: it matches FROM/JOIN with three-part names or the query's database/schema context. It strips literals/comments locally and ignores unsuccessful queries. It can miss comma joins, CTE/view lineage, dynamic SQL, complex functions and cross-account reads, and may overcount CTE names that resemble tables. Query text can be truncated. Full SQL parsing and lineage reconstruction are not provided.
- Matching relies on names, not durable object IDs. Renames, dropped/recreated objects, quoted-name punctuation, case changes and destination naming rules can invalidate it. Mapping names remain strict: unsupported or non-three-part mappings are errors. Object read exports keep only table/view kinds; the runner skips unparseable or non-three-part read names, reports their count and up to five samples under coverage, and warns that a mapped table whose real name needs quoting could be affected. Verify those names manually before relying on candidates.
- A spike means at least twice the preceding calendar month's paid rows, with positive prior rows and complete billing coverage for both months. Zero-to-positive changes are not classified as spikes. A matching log is linked by connection and calendar month, **not by table or cause**. “Confirmed by evidence” confirms only that temporal co-occurrence. An unexplained spike may simply have missing event history. The confidence vocabulary reserves “consistent with a documented behaviour” for an interpretation supported by documented behaviour; this version deliberately makes no automatic such causal inference from event names.
- PAID is counted as paid; only documented free categories count as free. Unknown categories, duplicate billing grain and malformed inputs fail with a message. Future schema or category changes may require an update. Usage totals are not independently reconciled against `USAGE_COST` or invoices. Only the local per-connection pricing model estimates ingestion cost.
- **Lowering sync frequency alone is not a saving.** No automatic changes are suggested. Rates, completeness and business necessity must all be confirmed by people responsible for the bill and tables.


The Standard Edition query-text fallback has lower confidence than per-table read history. The paid pricing model also does not support shared account-wide commitments, pooled credits, all-units price curves, carry-forward credits, proration, refunds, or fixed-plus-overage contracts. Prices and renewal terms remain assumptions, not invoice guarantees; warehouse compute, transformations, taxes and other charges are excluded. Individual and combined removal estimates are alternatives, never additive.

## How to get the full report

US$149, one payment, for a download that is the same for every buyer. Write to handoverdesk@proton.me. Card checkout is not open yet.

## Privacy

Nothing leaves your machine. The tool makes no network calls and needs no account, signup, login, trial, API key, warehouse connection or credential. You run the read-only SQL yourself in your existing warehouse worksheet; those queries can consume warehouse compute. Metadata can identify sensitive systems. Do not email us your exports.

## Who is behind it

Handcraft makes small fixed-price tools for teams that want a second look at a recurring bill. This one covers Fivetran billed into Snowflake. Questions, corrections or removal requests: handoverdesk@proton.me.

Based on the vendors' public documentation.

On 12 November 2026 the seven SQL files each ran without error on one Snowflake trial account that we opened ourselves, against small hand-made tables shaped like the vendor's documented metadata tables. They have not run on real Fivetran data, a real customer's account or an invoice. In that run a query that only counted rows (`SELECT COUNT(*)`) left no entry in object-level read history, while column selects, a read through a view and a loader's MERGE were recorded; so a table that people only ever count can look unread. That is our observation, not a vendor statement. No invoice or real-account result has been checked. `docs/sources.md` retains the original documentation URLs and read date; saved vendor page text is deliberately excluded. `docs/sql-parse-check.txt` is the working tool's prior offline syntax check, not warehouse validation. Run `python3 -m unittest discover` to check the local preflight; the boundary test's initial failure is in `docs/tests-before-cut.txt`.
