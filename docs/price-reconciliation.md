# Price provenance and source reconciliation

The pipeline now emits `publish/price_reconciliation.json` after the official source audit and before the research coordinator.

For the October 15, 2026 session, the user confirmed **MCB PKR 371.08** and **SYS PKR 115.96** in chat. These are recorded in `config/user_confirmed_prices.json` and clearly marked `USER_CONFIRMED_IN_CHAT_NOT_OFFICIAL`. The exact observation clock time, price adjustment basis and final-close nature were not independently attested; retain that limitation.

For each covered stock, the report separates:
- **Research:** the dated discovery provider value (not official);
- **User confirmation:** manually recorded dated market price, if one exists;
- **Independent official PSX price:** null until an authenticated independent quote observation, symbol, market/session code, actual price, and date are captured in an approved official evidence workflow.

Date-specific comparison: same-session absolute differences > PKR 0.005 become `RESEARCH_USER_PRICE_DISCREPANCY`; matching values are `MATCHED_USER_CONFIRMATION_UNATTESTED`. A previously confirmed quote is never substituted for the current market session. Neither matches nor independently_verified flags alone promote an official price. No underlying candles/technical indicators are modified.

Add this report to scheduled PSX analyses and show all three provenance categories, with flags for discrepancies. Keep any trade-size gate closed without fresh independently verified relevant PSX market quotes and sufficient financial/risk inputs.

No scraping, broker orders or release of proprietary market feed data was introduced. Review PR tests and a GitHub Actions artifact before merging.
