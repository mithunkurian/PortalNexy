"""Read-only dashboard projections from the complete durable experiment ledger."""
from datetime import timedelta
from .rules import UTC, dt, iso


def period_starts(now):
    now = now.astimezone(UTC)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return dict(today=today, week=today-timedelta(days=today.weekday()),
                month=today.replace(day=1), days30=today-timedelta(days=29), all=None)


def activity_summary(store, now):
    """Counts/notional are execution activity, never simulated P&L or order estimates."""
    periods = {}
    for name,start in period_starts(now).items():
        strategies = {}
        for strategy in ('etf','crypto'):
            state = store.get('strategy:'+strategy,{})
            inception = dt(state['inception']) if state.get('inception') else None
            lower = max(d for d in (start,inception) if d is not None) if start or inception else now
            fills = [f for f in store.records('fills',strategy) if inception and lower <= dt(f['time']) <= now]
            orders = [o for o in store.records('orders',strategy) if inception and lower <= dt(o['created_at']) <= now]
            strategies[strategy] = dict(started=bool(inception),fills=len(fills),
                executed_value=sum(f['quantity']*f['price'] for f in fills),
                buy_fills=sum(f['side']=='buy' for f in fills),sell_fills=sum(f['side']=='sell' for f in fills),
                orders_submitted=len(orders),orders_with_fills=len({f['order_id'] for f in fills}))
        strategies['all'] = {k:sum(strategies[s][k] for s in ('etf','crypto')) for k in
                            ('fills','executed_value','buy_fills','sell_fills','orders_submitted','orders_with_fills')}
        strategies['all']['started'] = any(strategies[s]['started'] for s in ('etf','crypto'))
        periods[name] = dict(start=iso(start) if start else None, **strategies)
    return dict(updated_at=iso(now),timezone='UTC',periods=periods,archive_ready=True)
