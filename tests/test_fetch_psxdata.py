import json
import os
from datetime import date
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

from psx_collector import connect
from scripts.fetch_psxdata import collect_psxdata_conn


class FetchPsxdataTest(unittest.TestCase):
    def test_validation_conflicts_and_insert_policy(self):
        rows = json.loads((ROOT / "tests" / "fixtures" / "psxdata_mcb_rows.json").read_text())

        def fake_fetcher(symbol, **_kwargs):
            self.assertEqual(symbol, "MCB")
            return rows

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "psx.sqlite"
            with connect(db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO ohlcv(
                      trade_date, symbol, market_code, company, open, high, low,
                      close, volume, previous_close, source_file
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "2026-10-08",
                        "MCB",
                        "0807",
                        "MCB Bank",
                        100.0,
                        101.0,
                        99.0,
                        100.25,
                        999,
                        None,
                        "official_20261008.lis",
                    ),
                )
                report = collect_psxdata_conn(
                    conn,
                    symbols=["MCB"],
                    start="2026-10-08",
                    end="2026-10-14",
                    min_provider_sessions=1,
                    fetcher=fake_fetcher,
                    today=date(2026, 10, 14),
                )

                official_close = conn.execute(
                    """
                    SELECT close FROM ohlcv
                    WHERE trade_date='2026-10-08'
                      AND symbol='MCB'
                      AND market_code='0807'
                    """
                ).fetchone()[0]
                self.assertEqual(official_close, 100.25)

                psxdata_rows = conn.execute(
                    """
                    SELECT trade_date, close FROM ohlcv
                    WHERE symbol='MCB' AND market_code='REG'
                    ORDER BY trade_date
                    """
                ).fetchall()
                self.assertEqual(psxdata_rows, [("2026-10-09", 107.0), ("2026-10-14", 114.0)])

        symbol_report = report["symbols"]["MCB"]
        self.assertEqual(symbol_report["raw_rows"], 6)
        self.assertEqual(symbol_report["valid_rows"], 3)
        self.assertEqual(symbol_report["duplicates"], 1)
        self.assertEqual(symbol_report["rejected_rows"], 1)
        self.assertEqual(symbol_report["anomalies"], 1)
        self.assertEqual(symbol_report["official_discrepancies"], 1)
        self.assertEqual(symbol_report["skipped_existing_rows"], 1)
        self.assertEqual(symbol_report["inserted_rows"], 2)
        self.assertFalse(symbol_report["stale"])

    @unittest.skipUnless(
        os.getenv("RUN_PSXDATA_LIVE") == "1",
        "set RUN_PSXDATA_LIVE=1 to run the live psxdata integration test",
    )
    def test_live_provider_returns_minimum_history_when_available(self):
        try:
            import psxdata  # noqa: F401
        except ModuleNotFoundError as exc:
            self.skipTest(f"psxdata is not installed: {exc}")

        with tempfile.TemporaryDirectory() as tmp:
            with connect(Path(tmp) / "psx.sqlite") as conn:
                report = collect_psxdata_conn(
                    conn,
                    symbols=["MCB", "SYS", "KOHE"],
                    mode="backfill",
                    backfill_days=430,
                    min_provider_sessions=250,
                    today=date.today(),
                )

        for symbol in ("MCB", "SYS", "KOHE"):
            self.assertGreaterEqual(report["symbols"][symbol]["valid_rows"], 250)
        self.assertFalse(report["had_fetch_failures"], report)


if __name__ == "__main__":
    unittest.main()
