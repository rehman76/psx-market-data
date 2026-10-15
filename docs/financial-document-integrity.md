# Financial PDF integrity and conservative sector review

This phase builds on the existing `fundamental_review.json` output. It does
**not** claim independent authentication of PSX filings, OCR of PDF financial
statements, or approved trading signals.

## Local report integrity

`scripts/financial_document_integrity.py` accepts a financial-review JSON
and, optionally, a local folder of `SYMBOL.pdf` files. A report's SHA-256
must equal the `report_sha256` value recorded with the disclosure-derived
figures. The script checks the `%PDF-` header, calculates the digest from
actual file bytes, rejects symlinks, and limits each report to 40 MB.

Example:

```bash
python scripts/financial_document_integrity.py \
  --fundamentals publish/fundamental_review.json \
  --reports-dir reviewed_reports \
  --out publish/financial_document_integrity.json
```

This is a **local byte-integrity** test only. PDFs can be fabricated, and
hashes in user-provided records are not independent PSX attestations.
Consequently, even `DOCUMENT_BYTES_MATCH` is not an issuer authentication
or proof that the entered EPS, cash flow, or dividend figures appear in the
document. No raw PDF is published to the GitHub Actions artifact.

With no supplied financial figures, the default workflow outputs
`NO_DISCLOSURE` for every configured symbol, which is the correct state.

## Bank classification safeguards

The fundamental review recognizes MCB, UBL, HBL, BAFL, and MEBL as banks
for the limited purpose of suppressing industrial-style net profit margin
and operating-cash-flow/net-income ratios. It explicitly marks
`SECTOR_SPECIFIC_VALIDATION_PENDING` for all populated disclosures.
ROE and EPS arithmetic may be displayed as **unattested calculations**,
not as a banking adequacy review. Loan provisioning, non-performing loans,
capital adequacy, interest and fee income, and regulatory disclosures
require an additional separately sourced model.

Other symbols remain `NON_BANK_UNCLASSIFIED` until a verified taxonomy is
available. Financial, insurance, holding, energy and industrial businesses
may have incompatible financial statement formats. Nothing is automatically
categorized as fundamentally sound.

## Outstanding requirements

- Authorized, traceable ingestion of *actual* PSX financial disclosures
- Authentication that reports were published by the claimed issuer/exchange
- Independent, source-specific extraction and human/automated reconciliation
  of reported figures, including restatements and per-share adjustments
- Proper sector taxonomy and bank-specific financial measures
- Official market-data verification, corporate actions, risk management

Until these exist, `fundamentals_verified=false` and
`trade_eligible=false` remain unchanged. Do not use ratios here as
standalone buy or sell recommendations.
