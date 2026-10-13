# PSX verification workflow update

Copy `.github/workflows/psx-daily.yml` and `scripts/verify_pipeline.py` into the **existing** psx-market-data repository, preserving directory paths. Do not replace the collector, SQLite database, or psx-state branch.

On macOS terminal, from repository root:

```bash
git switch main
git pull origin main
git switch -c feature/psx-coverage-check
# Copy the two files into their matching paths.
python3 -m py_compile scripts/verify_pipeline.py
git add .github/workflows/psx-daily.yml scripts/verify_pipeline.py
git commit -m "Add PSX database coverage check to daily workflow"
git push -u origin feature/psx-coverage-check
```

Create a PR targeting main and merge after reviewing changes. Then manually run PSX closing data pipeline on main with `download_url` empty, `bootstrap_sample` unchecked, and `publish_pages` unchecked.

The new `Verify database coverage and freshness` step will currently return a warning / nonzero exit because only one session is stored. `continue-on-error: true` is deliberate, so the database can still be persisted and the artifact uploaded. The overall run may be green while this step shows a warning; do not interpret it as fresh market data.

To grow history, obtain additional authorized official PSX closing archives; do not assume an unverified automated URL. Do not enable public publishing without permission.
