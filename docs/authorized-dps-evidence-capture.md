# Optional authorized PSX DPS closing-file evidence capture

**Default: disabled.** This optional workflow only processes a direct PSX closing
file when an operator has established that automated downloading and internal
comparison are permitted. It does not discover, guess, or scrape download URLs.

## Prerequisites

1. Independently review PSX data access rights and confirm the exact direct
   `https://dps.psx.com.pk/...` closing-file download URL.
2. Supply the authorized URL through workflow-dispatch `download_url` or
   repository variable `PSX_AUTHORIZED_CLOSING_URL`. Prefer a restricted
   configuration mechanism if the URL contains sensitive query credentials.
3. Set repository variable `PSX_DPS_EVIDENCE_CAPTURE_AUTHORIZED=true` **only
   after authorization and a valid URL are in place**.
4. Run the workflow. Its pipeline step downloads the file once; the adapter
   reads that same downloaded file without making any new network requests.

If configured authorization or file acquisition fails, the capture step and
the workflow are marked failed **after private diagnostic artifacts upload**.
The missing evidence must never cause a false VERIFIED status.

## Result

`publish/dps_evidence_manifest.json` records file SHA-256, byte count, the
PSX source URL without query or fragment, capture timestamp, session cutoff
and evidence counts. Raw extracted evidence is kept under `RUNNER_TEMP` and
is not added to the uploaded workflow artifact.

`publish/source_verification.json` compares a recent OHLCV observation for
each configured symbol to the stored research candle, reporting
`MATCHED_SUBMITTED_EVIDENCE`, `MISMATCH` or `LOCAL_CANDLE_MISSING`.
The comparison checks price within PKR 0.005 and volume exactly.

**A match is NOT independent authentication**: the same official file may
have been imported into the local database earlier in the same workflow.
The result therefore retains `independently_verified=false`,
`official_psx_dps_verification_complete=false`, and `trade_eligible=0`.
A reviewer must assess source permission, provenance, market-code equivalence,
corporate actions and actual source independence before changing any trust
status.

No default workflow run attempts this capture. Public Pages publishing is
disabled when the evidence capture opt-in is enabled, even if public
redistribution would otherwise have been permitted.

The default research pipeline still creates `source_verification.json`
containing `NO_INDEPENDENT_EVIDENCE` entries when no evidence was captured.
