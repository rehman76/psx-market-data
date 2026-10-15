# Fundamental disclosure research — intentionally fail closed

`scripts/fundamental_review.py` produces a separate
`publish/fundamental_review.json` report for the curated PSX research
universe. The **scheduled workflow does not scrape earnings reports or infer
missing figures**. By default all symbols are marked
`DISCLOSURE_MISSING`, and all have `fundamentals_verified=false` and
`trade_eligible=false`.

## Optional operator-reviewed input

An operator can prepare a JSON array of one disclosure per symbol from
documented, authorized corporate reports. This example uses **fictional
figures** and is *not* a statement of MCB financial results:

```json
[
  {
    "symbol": "MCB",
    "fiscal_period_end": "2026-06-30",
    "published_on": "2026-09-15",
    "report_url": "https://dps.psx.com.pk/company/MCB",
    "report_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "currency": "PKR",
    "units": "PKR_absolute",
    "net_income": 1000000,
    "equity": 6000000,
    "total_assets": 10000000,
    "total_liabilities": 4000000,
    "revenue": 5000000,
    "operating_cash_flow": 1200000,
    "shares_outstanding": 100000,
    "dividend_per_share": 1.5,
    "eps_reported": 10
  }
]
```

Provide metrics in **absolute Pakistani rupees**, not thousands/millions.
Make fiscal-period basis, parent-vs-consolidated reporting, per-share
adjustments, restatements, and report currency consistent before entering
data. A URL or claimed SHA-256 does not authenticate the underlying report.

```bash
python scripts/fundamental_review.py \
  --discovery publish/discovery_watchlist.json \
  --disclosures reviewed_financial_figures.json \
  --out publish/fundamental_review.json
```

## Scope and limitations

The validator checks date bounds, numeric types, source-document reference,
rough balance-sheet equality, EPS arithmetic and a 240-calendar-day report
age threshold. It computes simple margins, ROE and cash-conversion ratios
only when meaningful denominators exist. It does not fetch official reports,
verify share counts, corporate actions, audit qualifications, announcement
timeliness, dividend eligibility, or source authenticity.

**This generic metric set is not a sector-specific valuation model.**
Banks, insurers, holding companies and investment companies may require
different financial metrics. Profitability ratios from quarterly vs annual
filings are not interchangeable. Do not extrapolate quarterly EPS as
annual EPS or compute P/E using prices without corporate-action adjustment.

A populated report remains `DOCUMENT_UNATTESTED` or
`NEEDS_REVIEW`; neither permits a BUY/SELL recommendation.
Independent official PSX price verification, document authentication,
market-code confirmation, and portfolio risk limits are separate gates.

The default Actions workflow produces a private research artifact and does
not accept arbitrary external financial inputs. A future authorized
integration should add a permission-reviewed, source-specific filing parser
and tests before changing verification statuses.
