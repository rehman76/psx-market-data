# Official source acquisition status in GitHub Actions

The official PSX Downloads page (<https://dps.psx.com.pk/downloads>) lists
**Market Summary (Closing) — ZIP**, but the public page alone does not
establish a licensed machine-readable direct URL, date convention, or access
permission. The previous run returned `HTTP_STATUS_404` for the configured
date-resolved `mkt_summary` path. The correct remedy is to confirm the
actual authorized direct link, not to guess alternative endpoint routes.

This change deliberately does **not** update the configured
`PSX_AUTHORIZED_CLOSING_URL` or enable `PSX_DPS_EVIDENCE_CAPTURE_AUTHORIZED`.

The workflow now attaches a sanitized **Official PSX source health** section
to its GitHub Actions step summary and uploads
`publish/official_source_health.md` as a diagnostic artifact.
The summary reports only fixed diagnostic codes and the already
reported completed-session date. Neither the URL nor response body is
included, so query credentials and web content are not exposed.

Interpret its separate states carefully:
- `FILE_FORMAT_ACCEPTED_NOT_AUTHENTICATED`: a structurally valid
  closing file was downloaded, but issuer authenticity and independent
  comparison are **not** established.
- `DOWNLOAD_FAILED`: a direct file request failed; inspect the
  sanitized code such as `HTTP_STATUS_404`.
- `NOT_CONFIGURED`: no direct PSX file URL was supplied.
- `FRESH` research data may come from an authorized secondary provider.
  It is **not** official DPS verification or evidence for a BUY/SELL decision.

The summary step is protected by unit tests and late workflow failure,
so a broken diagnostics generator cannot silently pass CI.

Operator action: confirm the correct Market Summary (Closing) ZIP URL
and data-use permission with PSX; update the existing variable only
after independent confirmation, then manually dispatch on `main`
with `download_url` empty. Do not turn on public data redistribution.
