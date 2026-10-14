#!/usr/bin/env python3
"""Fetch PSX historical OHLCV with psxdata and merge it conservatively.

The collector never overwrites an existing row.  Incoming psxdata rows are
inserted as market_code REG only when the database has no row for the same
symbol and trade date.  Overlaps with official closing-file rows are compared
and reported as matches or discrepancies.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import importlib.metadata
import json
import math
from pathlib import Path
import sqlite3
import sys
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from psx_collector import connect

DEFAULT_SYMBOLS = ("MCB", "SYS", "KOHE")
EXPECTED_PSXDATA_VERSION = "1.2.0"
PSXDATA_MARKET_CODE = "REG"
SOURCE_PREFIX = f"psxdata:{EXPECTED_PSXDATA_VERSION}"
PRICE_TOLERANCE = 0.005


class ProviderVersionError(RuntimeError):
    """Raised when the installed psxdata version is not the pinned version."""


def parse_iso_date(value: str | date | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def parse_row_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "date") and callable(value.date):
        candidate = value.date()
        if isinstance(candidate, date):
            return candidate
    return date.fromisoformat(str(value).strip()[:10])


def finite_float(value: Any, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} is not finite")
    return number


def integer_volume(value: Any) -> int:
    number = finite_float(value, "volume")
    if number < 0:
        raise ValueError("negative volume")
    if not number.is_integer():
        raise ValueError("noninteger volume")
    return int(number)


def truthy(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and math.isnan(value):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def frame_records(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if getattr(frame, "empty", False):
        return []
    if hasattr(frame, "to_dict"):
        return list(frame.to_dict("records"))
    return [dict(row) for row in frame]


def expected_weekday(day: date) -> date:
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def business_lag(latest: date | None, expected: date) -> int | None:
    if latest is None:
        return None
    if latest > expected:
        return -1
    return sum(
        1
        for offset in range(1, (expected - latest).days + 1)
        if (latest + timedelta(days=offset)).weekday() < 5
    )


def latest_db_date(conn: sqlite3.Connection, symbol: str) -> date | None:
    row = conn.execute(
        "SELECT MAX(trade_date) FROM ohlcv WHERE symbol=? AND market_code != ?",
        (symbol, "40"),
    ).fetchone()
    return parse_iso_date(row[0]) if row and row[0] else None


def resolve_start(
    conn: sqlite3.Connection,
    symbol: str,
    mode: str,
    start: date | None,
    end: date,
    backfill_days: int,
    overlap_days: int,
) -> date:
    if start:
        return start
    if mode == "incremental":
        latest = latest_db_date(conn, symbol)
        if latest:
            return min(latest - timedelta(days=overlap_days), end)
    return end - timedelta(days=backfill_days)


def fetch_with_psxdata(
    symbol: str,
    *,
    start: str,
    end: str,
    cache: bool,
    allow_version_mismatch: bool = False,
) -> Any:
    version = importlib.metadata.version("psxdata")
    if version != EXPECTED_PSXDATA_VERSION and not allow_version_mismatch:
        raise ProviderVersionError(
            f"psxdata=={EXPECTED_PSXDATA_VERSION} is required; installed {version}"
        )
    import psxdata

    try:
        return psxdata.stocks(symbol, start=start, end=end, cache=cache)
    except TypeError as exc:
        if "cache" not in str(exc):
            raise
        return psxdata.stocks(symbol, start=start, end=end)


def validate_provider_rows(
    symbol: str,
    raw_rows: list[dict[str, Any]],
    *,
    start: date,
    end: date,
    today: date,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seen_dates: set[str] = set()
    provider_dates: list[date] = []
    valid_rows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    required = {"date", "open", "high", "low", "close", "volume"}
    anomaly_column_present = any("is_anomaly" in row for row in raw_rows)

    for index, row in enumerate(raw_rows, 1):
        try:
            missing = sorted(required - set(row))
            if missing:
                raise ValueError("missing columns: " + ", ".join(missing))

            trade_day = parse_row_date(row["date"])
            provider_dates.append(trade_day)
            iso_day = trade_day.isoformat()

            if trade_day < start or trade_day > end:
                raise ValueError("date outside requested range")
            if trade_day > today:
                raise ValueError("future trade date")
            if iso_day in seen_dates:
                duplicates.append({"row": index, "date": iso_day})
                continue
            seen_dates.add(iso_day)

            if truthy(row.get("is_anomaly")):
                anomalies.append({"row": index, "date": iso_day})
                continue

            open_, high, low, close = (
                finite_float(row["open"], "open"),
                finite_float(row["high"], "high"),
                finite_float(row["low"], "low"),
                finite_float(row["close"], "close"),
            )
            volume = integer_volume(row["volume"])

            if min(open_, high, low, close) <= 0:
                raise ValueError("nonpositive price")
            if not (low <= min(open_, close) <= max(open_, close) <= high):
                raise ValueError("inconsistent OHLC")

            valid_rows.append(
                {
                    "trade_date": iso_day,
                    "symbol": symbol,
                    "market_code": PSXDATA_MARKET_CODE,
                    "company": symbol,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                    "previous_close": None,
                    "source_file": f"{SOURCE_PREFIX}:{symbol}:{start.isoformat()}..{end.isoformat()}",
                }
            )
        except (TypeError, ValueError, OverflowError) as exc:
            rejected.append(
                {
                    "row": index,
                    "date": str(row.get("date", "")),
                    "reason": str(exc),
                }
            )

    chronological = provider_dates == sorted(provider_dates)
    valid_rows.sort(key=lambda row: row["trade_date"])
    return valid_rows, {
        "raw_rows": len(raw_rows),
        "valid_rows": len(valid_rows),
        "rejected_rows": len(rejected),
        "anomalies": len(anomalies),
        "duplicates": len(duplicates),
        "provider_chronological": chronological,
        "anomaly_column_present": anomaly_column_present,
        "sample_rejections": rejected[:20],
        "sample_anomalies": anomalies[:20],
        "sample_duplicates": duplicates[:20],
    }


def same_ohlcv(incoming: dict[str, Any], existing: sqlite3.Row | tuple[Any, ...]) -> bool:
    return (
        abs(float(incoming["open"]) - float(existing[3])) <= PRICE_TOLERANCE
        and abs(float(incoming["high"]) - float(existing[4])) <= PRICE_TOLERANCE
        and abs(float(incoming["low"]) - float(existing[5])) <= PRICE_TOLERANCE
        and abs(float(incoming["close"]) - float(existing[6])) <= PRICE_TOLERANCE
        and int(incoming["volume"]) == int(existing[7])
    )


def existing_snapshot(row: sqlite3.Row | tuple[Any, ...]) -> dict[str, Any]:
    return {
        "market_code": row[1],
        "source_file": row[2],
        "open": row[3],
        "high": row[4],
        "low": row[5],
        "close": row[6],
        "volume": row[7],
    }


def merge_valid_rows(
    conn: sqlite3.Connection,
    rows: list[dict[str, Any]],
    *,
    apply: bool,
) -> dict[str, Any]:
    inserted = 0
    skipped_existing = 0
    official_overlap_matches = 0
    official_discrepancies: list[dict[str, Any]] = []

    with conn:
        for row in rows:
            existing_rows = conn.execute(
                """
                SELECT trade_date, market_code, source_file, open, high, low, close, volume
                FROM ohlcv
                WHERE trade_date=? AND symbol=?
                ORDER BY market_code, source_file
                """,
                (row["trade_date"], row["symbol"]),
            ).fetchall()

            official_rows = [
                existing
                for existing in existing_rows
                if not str(existing[2]).startswith("psxdata:")
            ]
            if official_rows:
                if any(same_ohlcv(row, existing) for existing in official_rows):
                    official_overlap_matches += 1
                else:
                    official_discrepancies.append(
                        {
                            "date": row["trade_date"],
                            "symbol": row["symbol"],
                            "incoming": {
                                "open": row["open"],
                                "high": row["high"],
                                "low": row["low"],
                                "close": row["close"],
                                "volume": row["volume"],
                            },
                            "existing": [existing_snapshot(existing) for existing in official_rows],
                        }
                    )

            if existing_rows:
                skipped_existing += 1
                continue

            if apply:
                conn.execute(
                    """
                    INSERT INTO ohlcv(
                      trade_date, symbol, market_code, company, open, high, low,
                      close, volume, previous_close, source_file
                    )
                    VALUES (
                      :trade_date, :symbol, :market_code, :company, :open, :high,
                      :low, :close, :volume, :previous_close, :source_file
                    )
                    """,
                    row,
                )
            inserted += 1

    return {
        "inserted_rows": inserted if apply else 0,
        "candidate_insert_rows": inserted,
        "skipped_existing_rows": skipped_existing,
        "official_overlap_matches": official_overlap_matches,
        "official_discrepancies": len(official_discrepancies),
        "sample_official_discrepancies": official_discrepancies[:20],
    }


FetchCallable = Callable[..., Any]


def collect_psxdata_conn(
    conn: sqlite3.Connection,
    *,
    symbols: list[str] | tuple[str, ...] = DEFAULT_SYMBOLS,
    mode: str = "backfill",
    start: str | date | None = None,
    end: str | date | None = None,
    backfill_days: int = 430,
    overlap_days: int = 10,
    min_provider_sessions: int = 250,
    max_business_lag: int = 1,
    cache: bool = True,
    apply: bool = True,
    allow_version_mismatch: bool = False,
    fetcher: FetchCallable | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    end_day = parse_iso_date(end) or today
    explicit_start = parse_iso_date(start)
    expected = expected_weekday(end_day)
    fetcher = fetcher or fetch_with_psxdata

    report: dict[str, Any] = {
        "enabled": True,
        "provider": "psxdata",
        "required_version": EXPECTED_PSXDATA_VERSION,
        "mode": mode,
        "apply": apply,
        "cache": cache,
        "requested_end": end_day.isoformat(),
        "expected_latest_weekday": expected.isoformat(),
        "symbols": {},
        "totals": {
            "raw_rows": 0,
            "valid_rows": 0,
            "inserted_rows": 0,
            "candidate_insert_rows": 0,
            "skipped_existing_rows": 0,
            "official_overlap_matches": 0,
            "official_discrepancies": 0,
            "rejected_rows": 0,
            "anomalies": 0,
            "duplicates": 0,
            "fetch_failures": 0,
        },
    }

    for raw_symbol in symbols:
        symbol = raw_symbol.upper()
        symbol_start = resolve_start(
            conn,
            symbol,
            mode,
            explicit_start,
            end_day,
            backfill_days,
            overlap_days,
        )
        symbol_report: dict[str, Any] = {
            "requested_start": symbol_start.isoformat(),
            "requested_end": end_day.isoformat(),
            "ok": False,
        }

        try:
            frame = fetcher(
                symbol,
                start=symbol_start.isoformat(),
                end=end_day.isoformat(),
                cache=cache,
                allow_version_mismatch=allow_version_mismatch,
            )
            raw_rows = frame_records(frame)
            valid_rows, validation = validate_provider_rows(
                symbol,
                raw_rows,
                start=symbol_start,
                end=end_day,
                today=today,
            )
            merge = merge_valid_rows(conn, valid_rows, apply=apply)
            latest_provider = (
                parse_iso_date(valid_rows[-1]["trade_date"]) if valid_rows else None
            )
            lag = business_lag(latest_provider, expected)
            symbol_report.update(validation)
            symbol_report.update(merge)
            symbol_report.update(
                {
                    "latest_provider_date": latest_provider.isoformat()
                    if latest_provider
                    else None,
                    "weekday_lag": lag,
                    "stale": lag is None or lag > max_business_lag or lag < 0,
                    "insufficient_provider_sessions": len(valid_rows)
                    < min_provider_sessions,
                }
            )
            symbol_report["ok"] = (
                not symbol_report["stale"]
                and not symbol_report["insufficient_provider_sessions"]
            )
        except Exception as exc:  # Provider/network errors must be reported, not hidden.
            symbol_report.update(
                {
                    "fetch_error": f"{type(exc).__name__}: {exc}",
                    "raw_rows": 0,
                    "valid_rows": 0,
                    "stale": True,
                    "insufficient_provider_sessions": True,
                }
            )
            report["totals"]["fetch_failures"] += 1

        report["symbols"][symbol] = symbol_report
        for key in (
            "raw_rows",
            "valid_rows",
            "inserted_rows",
            "candidate_insert_rows",
            "skipped_existing_rows",
            "official_overlap_matches",
            "official_discrepancies",
            "rejected_rows",
            "anomalies",
            "duplicates",
        ):
            report["totals"][key] += int(symbol_report.get(key, 0) or 0)

    report["ok"] = all(item.get("ok") for item in report["symbols"].values())
    report["had_fetch_failures"] = report["totals"]["fetch_failures"] > 0
    report["had_invalid_rows"] = any(
        report["totals"][key] > 0 for key in ("rejected_rows", "anomalies", "duplicates")
    )
    report["had_official_discrepancies"] = (
        report["totals"]["official_discrepancies"] > 0
    )
    return report


def collect_psxdata_db(db: Path, **kwargs: Any) -> dict[str, Any]:
    db.parent.mkdir(parents=True, exist_ok=True)
    with connect(db) as conn:
        return collect_psxdata_conn(conn, **kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="state/psx_ohlcv.sqlite")
    parser.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS))
    parser.add_argument("--mode", choices=("backfill", "incremental"), default="backfill")
    parser.add_argument("--start", help="YYYY-MM-DD; default depends on mode")
    parser.add_argument("--end", help="YYYY-MM-DD; defaults to today")
    parser.add_argument("--backfill-days", type=int, default=430)
    parser.add_argument("--overlap-days", type=int, default=10)
    parser.add_argument("--min-provider-sessions", type=int, default=250)
    parser.add_argument("--max-business-lag", type=int, default=1)
    parser.add_argument("--report", default="publish/psxdata_status.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--allow-version-mismatch", action="store_true")
    args = parser.parse_args()

    report = collect_psxdata_db(
        Path(args.db),
        symbols=[symbol.upper() for symbol in args.symbols],
        mode=args.mode,
        start=args.start,
        end=args.end,
        backfill_days=args.backfill_days,
        overlap_days=args.overlap_days,
        min_provider_sessions=args.min_provider_sessions,
        max_business_lag=args.max_business_lag,
        cache=not args.no_cache,
        apply=not args.dry_run,
        allow_version_mismatch=args.allow_version_mismatch,
    )

    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
