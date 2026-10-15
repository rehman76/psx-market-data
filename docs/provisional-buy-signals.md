# Human-review provisional BUY candidates

The PSX pipeline now proposes technical **BUY candidates**, even when official independent source verification is pending. The output is `publish/provisional_buy_signals.json`.

There are three distinct concepts:

- `PROVISIONAL_BUY_CANDIDATE`: **research data only**, current completed-session price > MA20 > MA50, RSI14 50–70, relative volume >= 1.0. This does not claim breakout or justify immediate entry. It is a candidate worth manually investigating.
- `EARLY_BUY_WATCH`: **exactly three of the four** completed-session technical screening criteria pass. This is an earlier and weaker research idea requiring manual investigation; the failed check is displayed. It is not a confirmed BUY or actionable entry.\n- `WAIT_FOR_TECHNICAL_CONFIRMATION`: fresh technical data exist but fewer than three provisional-screen criteria pass.
- `INSUFFICIENT_DATA`: stale or incomplete inputs; cannot derive a provisional signal.

For every symbol, the report includes `screening_checks`, `screening_passed`, and `screening_total` so an early signal cannot conceal its failed check; dated research price, relevant support/reference 20-session low, resistance/reference 20-session high, research indicators and missing evidence. The future break-above-high confirmation requires >=1.5x relative volume, RSI >50 and improving MACD. The breakout trigger is ALWAYS marked **not yet triggered**, because the system doesn't have independently verified next-session candles.

The report never fabricates executable entry/stop/target prices, claims 2:1 R:R has been achieved, approves shares or places orders. Use `price_reconciliation.json` to check market-price conflicts and `source_verification.json` to assess independently authenticated evidence.

## Manual verification checklist

1. Verify ticker, correct market/board, date and price on the official PSX DPS company page.
2. Check latest session close and volume, market depth/spread and whether the breakout held.
3. Review financial results, company notices and liquidity.
4. Define actual entry, stop/invalidation and reachable target; demand reward/risk >=2:1 and <=1% equity risk for swing positions.
5. Confirm available cash and position/sector concentration.

These screening flags are **decision support**, not automated recommendations or trading permissions. The user decides whether to buy after review.
