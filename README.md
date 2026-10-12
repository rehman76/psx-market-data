# PSX GitHub Actions collector and scheduled-analysis feed

## What is working

This project parses official PSX `.lis.Z` closing files (the provided example is actually a ZIP with `.lis` inside), imports validated OHLCV into a SQLite database, computes technical indicators when there is enough history, and produces `publish/psx_analysis_feed.json` and `publish/status.json`. The GitHub Actions workflow runs on a schedule, preserves SQLite on a dedicated `psx-state` branch, and uploads a JSON feed as a workflow artifact. A local end-to-end test uses the supplied October 12, 2026 file.

**Important:** Automatic download from PSX is **not yet working out of the box**. No verified direct closing-file URL or license to collect/republish PSX data has been established. Do not guess an endpoint, bypass restrictions, or assert that a newly generated feed contains new data. The script only downloads from a verified and authorized `https://dps.psx.com.pk/...` file URL you configure. A single fixed URL is **not** a general solution for each future trading date; for ongoing unattended collection you need an authorized daily URL resolver or licensed provider. The workflow currently regenerates existing data if no new file arrives.

## Setup (private GitHub repository)

1. Create a **private** GitHub repository and add the project files, including `.github/workflows/psx-daily.yml`. Avoid committing any price data unless permitted by the applicable PSX terms. The `sample/` file is for local verification and should be removed before committing if you do not have rights to store/share it in the repository.
2. Under **Settings → Actions → General → Workflow permissions**, allow **Read and write permissions** for `GITHUB_TOKEN` (or configure equivalent permissions). The workflow needs this to persist the SQLite file to `psx-state`.
3. From **Actions → PSX closing data pipeline → Run workflow**, execute a manual run. For an initial run, put at least one legitimately obtained closing file in `closing_files/` locally and import it, or provide an authorized direct PSX file URL in the manual-run field. Since `closing_files/` is gitignored, a cloud runner cannot see files sitting on your PC. For a one-time bootstrap you can select `bootstrap_sample=true` in the manual workflow, **only if you are permitted to store/use the uploaded example**; otherwise initialize `psx-state` with a legitimately acquired database through an approved transfer method. The included sample is used for local tests, not automatically imported by the production workflow.
4. Once the state branch exists, later runs load the prior SQLite database. Without a new authorized file, they will not gain new candles. Check `status.json` for `download_succeeded`, `latest_trade_dates`, `sessions`, and `new_download_missing`.
5. Schedule runs at 16:00, 16:10, 16:30 and 08:50 PKT on weekdays. GitHub may delay cron jobs. A 16:15 ChatGPT report must check the feed timestamp and last completed trade date and fall back if data are late.

## Optional verified automatic PSX download

If PSX authorizes automated retrieval and you have a real *direct* file URL, configure repository **Variables → Actions → `PSX_AUTHORIZED_CLOSING_URL`**. Do not use the `/downloads` HTML page as a direct file URL. The URL must return the actual closing file; the downloader rejects HTML. A dated URL must be refreshed appropriately by an authorized source. Alternatively, pass the URL to a manual `workflow_dispatch` run.

## Publishing to ChatGPT scheduled tasks

- By default, output is an **Actions artifact**, not a public website. ChatGPT scheduled tasks cannot access the private Actions artifact by themselves. The artifact is useful for manual validation and secure handoff.
- **Do not publish OHLCV publicly without confirming redistribution rights.** Only after authorization, configure **Settings → Pages → Source: GitHub Actions** and repository variable `PSX_ALLOW_PUBLIC_PUBLISH=true`, then use manual **Run workflow → publish_pages=true**. GitHub Pages availability for private repositories depends on plan/settings. The resulting public URL is typically `https://OWNER.github.io/REPO/psx_analysis_feed.json`, but you must confirm the *actual* URL from the deployment and verify it is reachable by ChatGPT. Publishing is deliberately disabled by default, including scheduled runs.
- Prefer an approved, authenticated API or connector if data are not permitted for public redistribution. Do not expose repository tokens in the feed or scheduled-task instructions.
- **Only after a real reachable feed URL is verified** update the four ChatGPT automations with it. A local script, private GitHub artifact, or guessed Pages URL is not accessible to ChatGPT. The current ChatGPT tasks are **not yet linked**.

## Feed validation policy for ChatGPT

At each run, fetch the configured feed URL and check `schema_version`, `generated_at_utc`, `collection_status`, each stock's `latest_trade_date`, `sessions`, `latest_ohlcv`, and `indicators`. If stale, missing, conflicting, or inaccessible, report the limitation and use FinHisaab/official sources with explicit provenance; do not claim independent indicators or issue a BUY based on missing evidence. Note: `generated_at_utc` is not the market-data timestamp; check each stock's last trade date.

## Local test

```bash
python -m unittest discover -s tests -v
mkdir -p closing_files
cp sample/20261012_new.lis.Z closing_files/
python scripts/run_pipeline.py --input closing_files --db state/psx_ohlcv.sqlite --publish publish
```

Inspect `publish/psx_analysis_feed.json`. With one trading day, MA50/RSI/MACD/ATR are null by design. To produce reliable indicators, import sufficient authorized history. Data are unadjusted; corporate actions and ticker/market-code changes require reconciliation.

## Limitations

- No verified unattended daily PSX download endpoint or permission has been supplied.
- GitHub scheduled workflows can run late, and files can be published after the expected close.
- Public hosting requires explicit legal/operational approval; GitHub Pages is off by default.
- The current feed includes only configured tracked symbols (MCB, SYS, KOHE), not a full-market ranking.
- The repository's `psx-state` branch stores the SQLite DB and must remain private/appropriately access-controlled.
