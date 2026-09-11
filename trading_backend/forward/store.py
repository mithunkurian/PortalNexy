import json
import sqlite3
from datetime import datetime
from pathlib import Path
from .rules import UTC, iso, dt, Blocked


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
          PRAGMA journal_mode=WAL;
          PRAGMA synchronous=FULL;
          CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, strategy TEXT, payload TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS fills (id TEXT PRIMARY KEY, strategy TEXT, payload TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, time TEXT, strategy TEXT, kind TEXT, detail TEXT);
          CREATE TABLE IF NOT EXISTS history (time TEXT, strategy TEXT, payload TEXT, PRIMARY KEY(time,strategy));
          CREATE TABLE IF NOT EXISTS commands (id TEXT PRIMARY KEY);
        ''')

    def get(self, key, default=None):
        row = self.db.execute('SELECT value FROM kv WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key, value):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO kv VALUES (?,?)', (key, json.dumps(value, allow_nan=False)))

    def event(self, strategy, kind, detail):
        with self.db:
            self.db.execute('INSERT INTO events(time,strategy,kind,detail) VALUES (?,?,?,?)',
                            (iso(datetime.now(UTC)), strategy, kind, json.dumps(detail, allow_nan=False)))

    def records(self, table, strategy):
        if table not in ('orders', 'fills'):
            raise ValueError(table)
        return [json.loads(r[0]) for r in self.db.execute(
            f'SELECT payload FROM {table} WHERE strategy=? ORDER BY rowid', (strategy,))]

    def record(self, table, strategy, payload):
        if table not in ('orders', 'fills'):
            raise ValueError(table)
        with self.db:
            self.db.execute(f'INSERT OR REPLACE INTO {table} VALUES (?,?,?)',
                            (payload['id'], strategy, json.dumps(payload, allow_nan=False)))

    def intent(self, strategy, payload):
        # Commit BEFORE any broker call. An uncertain result is never automatically resubmitted.
        with self.db:
            result = self.db.execute('INSERT OR IGNORE INTO orders VALUES (?,?,?)',
                (payload['id'], strategy, json.dumps(payload, allow_nan=False)))
        return result.rowcount == 1

    def portfolio(self, strategy, capital, quotes):
        cash, realised, fees = capital, 0., 0.
        positions = {}
        fees_pending = False
        for f in sorted(self.records('fills', strategy), key=lambda f: (f['time'], f['id'])):
            s = f['symbol']; qty = f['quantity']; price = f['price']
            p = positions.setdefault(s, {'quantity': 0., 'basis': 0.})
            fee = f.get('fee')
            fees_pending |= fee is None
            fee = fee or 0.
            fees += fee
            if f['side'] == 'buy':
                p['quantity'] += qty
                p['basis'] += qty*price
                cash -= qty*price + fee
            else:
                if qty > p['quantity']+1e-7:
                    raise Blocked('Fill attribution would create a short position')
                basis = p['basis'] * qty / p['quantity'] if p['quantity'] else 0
                p['quantity'] -= qty; p['basis'] -= basis
                realised += qty*price-basis
                cash += qty*price-fee
        # Crypto fee activities can debit the acquired asset, not USD.
        for fee in self.get('fees:'+strategy, []):
            fees += fee['usd']
            if fee.get('symbol'):
                p = positions.setdefault(fee['symbol'], {'quantity': 0., 'basis': 0.})
                if fee['quantity'] > p['quantity']+1e-7:
                    raise Blocked('Asset fee exceeds attributed holdings')
                basis = p['basis']*fee['quantity']/p['quantity'] if p['quantity'] else 0
                p['quantity'] -= fee['quantity']; p['basis'] -= basis
                realised += fee['usd']-basis
            else:
                cash -= fee['usd']
        market_value = unrealised = 0.
        priced = True
        result = []
        for symbol, p in positions.items():
            if abs(p['quantity']) < 1e-8:
                continue
            q = quotes.get(symbol)
            mark = (q['bid']+q['ask'])/2 if q else None
            value = p['quantity']*mark if mark else None
            priced &= value is not None
            if value is not None:
                market_value += value; unrealised += value-p['basis']
            result.append(dict(symbol=symbol, **p, price=mark, market_value=value))
        return dict(cash=cash, realised=realised-fees, unrealised=unrealised if priced else None,
                    costs=fees, costs_pending=fees_pending, positions=result,
                    equity=cash+market_value if priced else None)

    def combined(self, now):
        states = [self.get('strategy:'+s, {}) for s in ('etf','crypto')]
        valid = all(s.get('portfolio') and not s.get('valuation_stale') and s.get('inception') and
                    0 <= (now-dt(s['updated_at'])).total_seconds() < 180 for s in states)
        portfolio = None
        if valid:
            portfolio = {k: sum(s['portfolio'][k] for s in states) for k in
                         ('equity','cash','realised','unrealised','costs')}
            portfolio['positions'] = [dict(strategy=key, **p) for key,s in zip(('etf','crypto'),states)
                                      for p in s['portfolio']['positions']]
        history = []
        peak = None
        maximum = drawdown = None
        for row in self.db.execute('''SELECT a.payload,b.payload FROM history a JOIN history b ON a.time=b.time
                                      WHERE a.strategy='etf' AND b.strategy='crypto' ORDER BY a.time'''):
            a,b = [json.loads(value) for value in row]
            value = a['equity']+b['equity']
            peak = max(peak or value,value)
            drawdown = (value/peak-1)*100
            maximum = min(maximum or 0,drawdown)
            history.append(dict(time=max(a['time'],b['time']),equity=value,benchmark=a['benchmark']+b['benchmark']))
        return dict(updated_at=iso(now),portfolio=portfolio,history=history[-500:],
                    benchmark=sum(s['benchmark'] for s in states) if valid else None,
                    drawdown=drawdown if valid else None,max_drawdown=maximum if valid else None)
