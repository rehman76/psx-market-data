# Dated PSX closing-file URL templates

The explicit, authorized `PSX_AUTHORIZED_CLOSING_URL` variable may contain
exactly one `YYYY-MM-dd` or `YYYY-MM-DD` token **in the URL path**.

Example *template only* (not a verified endpoint):

```text
https://dps.psx.com.pk/download/mkt_summary/YYYY-MM-dd
```

The resolver expands the token using Pakistan local time and the existing
conservative `expected_weekday` rule:

- Before 17:00 Asia/Karachi, use the preceding completed weekday.
- From 17:00 onward, use the current weekday when it is Monday–Friday.
- On Saturday/Sunday, use Friday.
- The rule does **not** account for PSX market holidays, emergency closures,
  session extensions, or when files are actually published.

For example, at 16:15 PKT on October 15, 2026 the date becomes 2026-10-14.
At 17:15 PKT it becomes 2026-10-15. The source URL may still return a
landing page or an unsupported payload; changing the date does **not**
validate that PSX provides a file at that endpoint.

Only the approved `https://dps.psx.com.pk` hostname is permitted. Query
strings are left unchanged; values in URLs may contain secrets and are never
logged. Date-template resolution produces `download_session_date` in
`publish/status.json`, never the full resolved URL. The authorized evidence
capture step receives the resolved URL so provenance reflects the actual
request, but it remains **unattested**.

After merging, run GitHub Actions with the configured variable and the
`download_url` manual input empty. Examine:

- `status.json` -> `official_download_health` and `download_error`.
- `status.json` -> `download_session_date` when templating is active.
- `source_verification.json` -> independent validation remains pending,
  even if the URL resolves and a structurally valid closing file is returned.

If `NON_CLOSING_DOCUMENT` continues, verify the PSX-approved direct download
URL and its data-use permission. Do not guess additional paths or bypass a
403/login response. The resolver does not make any new HTTP requests beyond
the existing, explicitly authorized download.

The optional evidence capture remains disabled unless explicitly enabled
through the existing `PSX_DPS_EVIDENCE_CAPTURE_AUTHORIZED` variable.
