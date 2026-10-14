# psxdata source and permission notes

This repository pins `psxdata==1.2.0` for optional historical OHLCV backfill and daily catch-up of MCB, SYS, and KOHE.

## Upstream package verification

- PyPI lists `psxdata` 1.2.0 as released on September 30, 2026, requiring Python 3.11+, with MIT license metadata, source and homepage links to `https://github.com/mtauha/psxdata`, and PyPI trusted-publishing provenance for the release artifacts.
- The upstream README describes `psxdata.stocks(symbol, start, end)` as returning historical OHLCV data and documents package-level validation, duplicate/future-date checks, exponential backoff, and local disk caching.
- The upstream LICENSE is MIT for the software package. That license covers the package code, not necessarily Pakistan Stock Exchange market-data redistribution or automated collection rights.

## Automated-use policy

Do not assume that installing an MIT-licensed client library grants permission to automate PSX data collection or republish OHLCV data. Enable the GitHub Actions integration only after the repository owner has verified that the intended automated use is allowed.

The workflow requires repository variable `PSXDATA_AUTOMATED_USE_AUTHORIZED=true` before it installs `psxdata` or runs the collector. Keep the variable unset otherwise; the official closing-file importer and freshness diagnostics still run.

## Merge policy

Rows from `psxdata` are stored with `market_code='REG'` and `source_file` beginning with `psxdata:1.2.0`. The collector inserts a psxdata row only when the database has no row for the same symbol and trade date. It compares overlapping psxdata rows with existing official closing-file rows, reports discrepancies in `publish/psxdata_status.json` and `publish/status.json`, and never overwrites existing records.
