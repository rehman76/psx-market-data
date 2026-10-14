"""Conservative Karachi-local weekday freshness checks (holidays not inferred)."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def expected_weekday(now=None):
    now = now or datetime.now(ZoneInfo('Asia/Karachi'))
    target = now.date() if now.hour >= 17 else now.date() - timedelta(days=1)
    while target.weekday() >= 5:
        target -= timedelta(days=1)
    return target


def assess(conn, symbols, min_sessions=50, max_business_lag=1, now=None):
    now = now or datetime.now(ZoneInfo('Asia/Karachi'))
    target = expected_weekday(now)
    status = {'checked_at_pkt': now.isoformat(), 'expected_latest_weekday': target.isoformat(),
              'stocks': {}, 'fresh': False, 'status': 'unavailable',
              'note': 'Weekday-based check, not a verified PSX trading calendar; holidays are not inferred.'}
    for symbol in symbols:
        latest, sessions = conn.execute(
            '''SELECT MAX(trade_date), COUNT(DISTINCT trade_date) FROM ohlcv
               WHERE symbol=? AND market_code != '40' AND open>0 AND high>0 AND low>0 AND close>0
                 AND volume>=0 AND low<=open AND open<=high AND low<=close AND close<=high''',
            (symbol.upper(),)).fetchone()
        lag = None
        if latest:
            day = date.fromisoformat(latest)
            lag = sum((day + timedelta(days=n)).weekday() < 5
                      for n in range(1, max(0, (target-day).days)+1))
        reason = ('missing' if not latest else 'insufficient_history' if sessions < min_sessions
                  else 'future_dated' if date.fromisoformat(latest) > target
                  else 'stale' if lag > max_business_lag else 'fresh')
        status['stocks'][symbol.upper()] = {'latest': latest, 'sessions': sessions,
                                           'weekday_lag': lag, 'fresh': reason == 'fresh', 'status': reason}
    status['fresh'] = len(status['stocks']) == len(symbols) and all(v['fresh'] for v in status['stocks'].values())
    status['status'] = 'fresh' if status['fresh'] else 'stale_or_insufficient'
    return status
