# PSX pipeline — next operating steps

## What is proven
- Sample import: 1,055 accepted records; 15 rejected for inconsistent OHLC.
- MCB, SYS and KOHE each have only one confirmed trading session (2026-10-12).
- `psx-state` branch and SQLite file exist; inspect subsequent commits to verify persistence.
- No live download was attempted in the sample run.

## Before enabling daily downloads
1. Confirm a stable, authorized direct PSX daily-closing-file URL; **do not** use the interactive `/downloads` webpage as if it were the file URL.
2. Check terms and permissions for automated retrieval, private storage and redistribution. Keep `publish_pages` off.
3. Set the repository variable `PSX_AUTHORIZED_CLOSING_URL` only after verifying it returns the expected closing-file bytes.
4. Run manually with `bootstrap_sample=false` and `publish_pages=false`.
5. Inspect logs for `download_attempted: true`, `download_succeeded: true`, new trade dates, and import errors.
6. Verify a new `psx-state` commit and that repeated runs do not duplicate records.

## Check historical coverage
From a checkout of the state branch or with the SQLite file copied to `state/psx_ohlcv.sqlite`:

```bash
python scripts/verify_pipeline.py --db state/psx_ohlcv.sqlite --symbols MCB SYS KOHE --min-sessions 50
```

An exit code of 1 indicates stale/insufficient coverage, not necessarily a broken workflow. With one sample day this check should fail intentionally.

## Market-wide screening
Continue storing all symbols in the SQLite database. Only screen symbols with enough valid sessions and liquidity; exclude inconsistent, suspended and illiquid securities and handle corporate actions. Avoid BUY/SELL recommendations based solely on one-day candles.

## ChatGPT integration
A GitHub Actions artifact is not automatically available to scheduled ChatGPT reports. Use a verified, authorized and accessible feed or supported connector. Do not turn on public Pages until rights are confirmed.
