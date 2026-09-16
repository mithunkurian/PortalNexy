from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math

UTC = timezone.utc


class Blocked(RuntimeError):
    """Safe, credential-free reason suitable for the decision log."""


@dataclass(frozen=True)
class Rule:
    version: str
    symbols: tuple[str, ...]
    lookback: int
    count: int
    reserve: float = .02
    exposure: float = .98


RULES = {
    'etf': Rule('etf-rotation-weekly-validation-1.0.0', ('SPY', 'EFA', 'EEM', 'TLT', 'GLD'), 126, 2),
    'crypto': Rule('crypto-momentum-1.0.0', ('BTC/USD', 'ETH/USD'), 90, 1),
}


def iso(value):
    return value.astimezone(UTC).isoformat()


def dt(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(UTC)


def signal(rule, histories, expected_dates):
    """Only complete, contiguous, expected sessions/days enter indicators."""
    ranked, decisions = [], []
    dates = expected_dates[-max(200, rule.lookback + 1):]
    if len(dates) < 200:
        raise Blocked('Insufficient warm-up calendar')
    for symbol in rule.symbols:
        bars = histories.get(symbol, {})
        if any(d not in bars for d in dates):
            raise Blocked(f'{symbol}: missing completed warm-up bars')
        closes = [float(bars[d]) for d in dates]
        if any(not math.isfinite(v) or v <= 0 for v in closes):
            raise Blocked(f'{symbol}: invalid historical price')
        momentum = closes[-1] / closes[-1-rule.lookback] - 1
        average = sum(closes[-200:]) / 200
        qualifies = momentum > 0 and closes[-1] > average
        decisions.append(dict(symbol=symbol, momentum=momentum, sma200=average,
                              close=closes[-1], qualifies=qualifies,
                              reason='Positive momentum and price above SMA' if qualifies else
                              '; '.join(reason for condition,reason in (
                                  (momentum<=0,'Momentum is not positive'),
                                  (closes[-1]<=average,'Price is not above the 200-period average')) if condition)))
        if qualifies:
            ranked.append((momentum, symbol))
    selected = [s for _, s in sorted(ranked, key=lambda x: (-x[0], x[1]))[:rule.count]]
    return selected, decisions


def slots(strategy, start, end):
    """Evaluation time, execution window, and signal date; all UTC."""
    if strategy == 'crypto':
        day = start.date()
        while day <= end.date() + timedelta(days=2):
            evaluation = datetime.combine(day, datetime.min.time(), UTC) + timedelta(minutes=5)
            yield dict(key=day.isoformat(), evaluate=iso(evaluation),
                       execute=iso(evaluation), expires=iso(evaluation + timedelta(days=1)),
                       signal_date=(day-timedelta(days=1)).isoformat())
            day += timedelta(days=1)
    else:
        import pandas_market_calendars as mcal
        calendar = mcal.get_calendar('NYSE')
        schedule = calendar.schedule(start_date=start.date()-timedelta(days=10),
                                     end_date=end.date()+timedelta(days=21))
        seen = set()
        rows = list(schedule.iterrows())
        for i, (day, row) in enumerate(rows[:-1]):
            year, week, _ = day.isocalendar()
            period = f'{year}-W{week:02d}'
            if period in seen:
                continue
            seen.add(period)
            following = rows[i+1][1]
            yield dict(key=period, evaluate=iso(row.market_close.to_pydatetime()+timedelta(minutes=5)),
                       execute=iso(following.market_open.to_pydatetime()+timedelta(minutes=1)),
                       expires=iso(following.market_close.to_pydatetime()-timedelta(minutes=5)),
                       signal_date=day.date().isoformat())


def warmup_dates(strategy, signal_date):
    end = dt(signal_date+'T00:00:00+00:00').date()
    if strategy == 'crypto':
        return [(end-timedelta(days=i)).isoformat() for i in reversed(range(200))]
    import pandas_market_calendars as mcal
    return [d.date().isoformat() for d in mcal.get_calendar('NYSE').valid_days(
        start_date=end-timedelta(days=420), end_date=end)][-200:]


def validate_quote(q, now):
    if q.get('delayed'):
        raise Blocked('Delayed market data: orders disabled')
    if not q.get('timestamp') or not 0 <= (now-dt(q['timestamp'])).total_seconds() <= 60:
        raise Blocked('Stale or future market quote')
    if not all(math.isfinite(q.get(k, 0)) and q.get(k, 0) > 0 for k in ('bid', 'ask')):
        raise Blocked('Missing bid/ask subscription or quote')
    if q['ask'] < q['bid'] or (q['ask']/q['bid']-1) > .01:
        raise Blocked('Invalid or excessive spread')
    if not q.get('market_open'):
        raise Blocked('Outside verified trading hours')


def enforce_account(account, allowlist):
    if not allowlist or account not in allowlist:
        raise Blocked('Connected account is not explicitly paper-allowlisted')
