# PSX source-evidence audit

The research-validation feed can now include `publish/source_verification.json`.
It is an **audit trail**, not proof that an external source is authentic.

## Default scheduled workflow

The workflow calls `scripts/source_verification.py` without an evidence file.
Its output records `NO_INDEPENDENT_EVIDENCE` for each configured symbol.
It never treats imported `psxdata` rows or inferred market-code mappings as
independent official verification.

## Optional manually provided evidence

An authorized reviewer can prepare a local JSON array. Example **fictional
numbers, not PSX quotes**:

```json
[
  {
    "symbol": "MCB",
    "trade_date": "2026-10-14",
    "open": 370.0,
    "high": 375.0,
    "low": 365.0,
    "close": 372.0,
    "volume": 200000,
    "source_url": "https://dps.psx.com.pk/company/MCB",
    "captured_at_utc": "2026-10-15T10:00:00Z"
  }
]
```

Run in a trusted local environment:

```bash
python scripts/source_verification.py \
  --db state/psx_ohlcv.sqlite \
  --discovery publish/discovery_watchlist.json \
  --evidence reviewed_dps_observations.json \
  --out publish/source_verification.json
```

Do not place licensed or restricted source records in publicly published files
without permission. A source URL only identifies the claimed source; it does
not prove the supplied numbers were independently captured or authenticated.
The auditor compares OHLC within PKR 0.005 and volume exactly, and records
missing local candles. Duplicates, unknown stocks, future-dated evidence,
malformed OHLCV and non-DPS hosts are rejected.

All matching observations are labeled
`MATCHED_SUBMITTED_EVIDENCE` (unattested). No `independently_verified`
or `trade_eligible` field is ever set true by this tool. Fundamentals,
corporate actions, licensed source provenance, and official calendar checks
are still separate requirements.

To enable genuine independent DPS verification, implement a **separately
authorized and tested capture adapter** with source-specific provenance and
an independently reviewed trust policy. Do not mislabel submitted JSON as
officially verified merely because its URL contains the official domain.
