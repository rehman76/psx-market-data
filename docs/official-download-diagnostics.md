# Official PSX closing-file download diagnostics

The optional, permission-gated direct closing-file URL is not assumed valid
merely because it has a dps.psx.com.pk hostname. The collector inspects the
actual response content and emits a **safe diagnostic code** to status.json
without revealing response bodies, supplied query credentials or an entire URL.

Examples:

| Code | Meaning / next step |
| --- | --- |
| NOT_CONFIGURED | No explicit official URL; no direct download attempted |
| NON_CLOSING_DOCUMENT | The endpoint sent HTML, XML or JSON rather than .lis |
| INVALID_CLOSING_ROWS | The response did not parse as a plausible PSX .lis closing file |
| INVALID_CLOSING_ZIP | The ZIP is corrupt or lacks a .lis file |
| UNSUPPORTED_UNIX_COMPRESS_Z | Response uses original UNIX compress (.Z), not the supported ZIP/raw .lis payload |
| HTTP_STATUS_403 | The endpoint denied access; recheck permission without bypassing restrictions |
| HTTP_STATUS_404 | The requested file was not present |
| REDIRECT_OUTSIDE_AUTHORIZED_HOST | Server redirected away from the permitted official host |
| DOWNLOAD_TRANSPORT_* | Connection error; inspect network/endpoint separately |

Only a verified, authorized, direct closing-file URL should be configured.
Do not guess paths, scrape login-protected content or use private credentials
in user-visible logs.

The collector accepts real ZIP archives with .lis members or parseable raw
.lis content. It allows a small number of malformed instrument rows, but it
will not save a page containing arbitrary pipe characters as a closing file.

The following are kept **separate** in status.json:

- `pipeline_status` describes whether the stored portfolio OHLCV is fresh.
- `official_download_health` describes the latest attempted direct file
  acquisition, including `DOWNLOAD_FAILED` or `NOT_CONFIGURED`.
- `data_quality_warnings` reminds consumers that downloaded-format validation
  alone is not independent PSX source authentication.

The optional official download may fail while authorized psxdata provides
fresh research observations. Such observations remain unverified for
trade-eligibility purposes. No BUY/SELL signals are enabled by this change.

## Before activating official evidence capture

Review `status.json` after the next workflow run. If it records
`NON_CLOSING_DOCUMENT`, the configured URL likely points to a web page
rather than an actual .lis archive. Confirm the correct direct URL and its
automated-use terms from the official source. With
`PSX_DPS_EVIDENCE_CAPTURE_AUTHORIZED` disabled, these diagnostics can be
deployed without enabling external capture.

Unit tests cover valid ZIP/raw candles, invalid HTML/JSON, wrong-host
redirects, UNIX .Z magic, HTTP denial and safe error strings.
