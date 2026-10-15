# PSX research coordinator (review-only)

Run `scripts/research_coordinator.py` after the discovery, technical, source,
fundamental and document-integrity stages.

The coordinator reads the **existing** 30-symbol research universe and writes
`publish/research_agenda.json` plus `publish/recommendation_register.json`.
GitHub Actions uploads both with the private research feed. The latter is also
stored on `psx-state`, creating an incremental, dated WATCH history.

## Official PSX company-page validation

For a known validated ticker, an operator can use
`https://dps.psx.com.pk/company/MCB`,
`https://dps.psx.com.pk/company/SYS`, or the generated
`https://dps.psx.com.pk/company/{TICKER}`.

**Use tickers, not literal company-name strings**; the link is a *review pointer*,
not evidence of a completed official quote fetch. The page could be
temporarily unavailable, blocked to automation, display intraday quotes,
or disagree with a provider's close because of timestamps or adjusted-price
basis. Record exact quote date, market code, type, currency and observation
time in an independently reviewed evidence workflow before comparison.
Only trust official PSX page data when access is permitted; do not bypass
anti-bot controls or use guessed private APIs. The existing direct closing-file
404 issue is distinct from availability of individual company pages.

## Research and safety

- A dated candidate receives **WATCH**, even when zero stocks are
  trade-eligible. Other symbols remain DATA_PENDING.
- A shortlist ranks five non-held WATCH names by the existing explicitly
  research-only discovery score. It does not invent entry prices, BUY/SELL
  recommendations or placed stop orders.
- `missing_requirements` explains independent official quote, issuer filing,
  document authenticity and market-code mapping gaps for each stock.
- Dated observation counts increase at most once per session, even if the
  GitHub workflow retries several times.
- A new untrusted JSON register is never treated as authenticated price data.
- No broker connector, trade authorization, automatic trading or public
  redistribution is added.

If either coordinator output or tests fail, the build fails and the
watchlist cannot quietly pretend to be valid.

The first successful run initializes history from its own dated observations;
past reports are **not backfilled** or fabricated.
