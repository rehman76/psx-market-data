
import argparse
import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

parser = argparse.ArgumentParser()
parser.add_argument("--status", default="publish/status.json")
parser.add_argument("--symbols", nargs="+", default=["MCB", "SYS", "KOHE"])
parser.add_argument("--require-today", action="store_true")
args = parser.parse_args()

with open(args.status, encoding="utf-8") as f:
    status = json.load(f)

today = datetime.now(ZoneInfo("Asia/Karachi")).date().isoformat()
latest = status.get("latest_trade_dates", {})

print("Pakistan date:", today)

stale = []
for symbol in args.symbols:
    trade_date = latest.get(symbol)
    print(f"{symbol}: latest={trade_date or 'MISSING'}")
    if trade_date != today:
        stale.append(symbol)

if stale:
    print("WARNING: Fresh closing data unavailable for:", ", ".join(stale))
    if args.require_today:
        sys.exit(1)
else:
    print("PASS: All requested symbols have today's closing data.")
