import hashlib
import math
from dataclasses import asdict
from datetime import datetime, timedelta
from .rules import RULES, Blocked, UTC, iso, dt, signal, slots, warmup_dates, validate_quote

TERMINAL = {'filled', 'cancelled', 'rejected'}
MONITORED_LIMIT_POLICY = 'marketable-limit-reprice-1.0.0'
REPRICE_SECONDS = 60
MAX_PRICE_DRIFT = .01


class Engine:
    def __init__(self, store, strategy, broker, capital, experiment):
        self.store, self.strategy, self.broker = store, strategy, broker
        self.capital, self.experiment = capital, experiment
        self.rule = RULES[strategy]
        self.before_submit = lambda: None
        self.key = 'strategy:'+strategy
        self.state = store.get(self.key, dict(mode='not_started', experiment=experiment,
            version=self.rule.version, rule=asdict(self.rule), capital=capital,
            account=broker.account, broker=broker.name, inception=None, last_success=None))
        if not self.state['inception']:
            self.state.update(experiment=experiment,version=self.rule.version,rule=asdict(self.rule),
                              capital=capital,account=broker.account,broker=broker.name)
        self.state['execution_policy'] = MONITORED_LIMIT_POLICY
        configured = dict(rule=asdict(self.rule), capital=capital, account=broker.account,
                          broker=broker.name, experiment=experiment)
        self.fingerprint = hashlib.sha256(__import__('json').dumps(configured, sort_keys=True).encode()).hexdigest()
        if self.state.get('fingerprint') and self.state['fingerprint'] != self.fingerprint:
            raise Blocked('Frozen experiment configuration changed; restore it or use a new experiment and clean allocation')

    def save(self):
        self.store.put(self.key, self.state)

    def control(self, action):
        if action not in ('start', 'pause', 'resume'):
            raise Blocked('Unsupported paper strategy command')
        if action == 'start' and self.state['inception']:
            raise Blocked('Experiment already started; use resume')
        if action == 'resume' and not self.state['inception']:
            raise Blocked('Start the experiment before resume')
        self.state['mode'] = 'paused' if action == 'pause' else 'running'
        self.save()
        self.store.event(self.strategy, 'control', dict(action=action,
            explanation='Pause stops NEW submissions only. Holdings and broker orders remain; fills are still reconciled.'))

    def reconcile(self, snap):
        known = {o['id']: o for o in self.store.records('orders', self.strategy)}
        for f in snap['fills']:
            if f['order_id'] not in known:
                raise Blocked('Unattributed execution received')
            intent = known[f['order_id']]
            if f['symbol'] != intent['symbol'] or f['side'] != intent['side'] or f['quantity'] <= 0 or f['price'] <= 0:
                raise Blocked('Execution does not match durable order intention')
            if dt(f['time']) < dt(self.state['inception']):
                raise Blocked('Pre-inception execution excluded')
            previous = {r['id']:r for r in self.store.records('fills', self.strategy)}.get(f['id'])
            if previous != f:
                self.store.record('fills', self.strategy, f)
                self.store.event(self.strategy, 'fill', f)
        self.store.put('fees:'+self.strategy, snap.get('fees', []))
        fills = self.store.records('fills', self.strategy)
        for ref, order in known.items():
            remote = snap['orders'].get(ref)
            if remote:
                accounted = sum(f['quantity'] for f in fills if f['order_id'] == ref)
                if abs(accounted-remote['filled']) > 1e-7:
                    raise Blocked('Broker executions incomplete; reconcile before resuming')
                updated = {**order, **remote}
                if updated != order:
                    self.store.record('orders', self.strategy, updated)
                    self.store.event(self.strategy, 'order_status', updated)
            elif order['status'] not in TERMINAL:
                raise Blocked('Uncertain submission / missing broker order: reconciliation required; automatic retry disabled')
        if snap['external_orders']:
            raise Blocked('Unattributed broker orders present; left untouched')

    def step(self, now=None):
        now = now or datetime.now(UTC)
        self.state['updated_at'] = iso(now)
        try:
            if self.state['inception']:
                self.schedule_clock(now)
            self.broker.connect()
            if self.strategy == 'etf' and hasattr(self.broker,'crypto_capability') and 'crypto_capability' not in self.state:
                self.state['crypto_capability'] = self.broker.crypto_capability()
            known = {o['id']:o for o in self.store.records('orders', self.strategy)}
            snap = self.broker.snapshot(known, self.state['inception'] or iso(now))
            self.state['connection'] = 'connected'
            self.state['broker_snapshot'] = {k:v for k,v in snap.items() if k not in ('fills','orders','fees')}
            if not self.state['inception']:
                if self.state['mode'] != 'running':
                    self.state['error'] = None
                    self.save(); return self.state
                if not math.isfinite(self.capital) or self.capital <= 0 or self.capital > snap['cash']:
                    raise Blocked('Configure a positive allocation within available USD broker cash')
                if snap['external_orders'] or any(abs(v)>1e-8 for v in snap['positions'].values()):
                    raise Blocked('New experiment requires a clean paper account; existing holdings/orders remain untouched')
                quotes = {s:self.broker.quote(s) for s in self.rule.symbols}
                for q in quotes.values():
                    # An inception benchmark needs fresh prices; execution hours are enforced later.
                    validate_quote({**q, 'market_open':True}, datetime.now(UTC))
                self.state.update(inception=iso(now), fingerprint=self.fingerprint,
                    unallocated_cash=snap['cash']-self.capital,
                    benchmark_start={s:(q['bid']+q['ask'])/2 for s,q in quotes.items()},
                    last_checked=iso(now), costs_provisional=self.strategy == 'crypto')
                self.save()
                self.store.event(self.strategy, 'inception', dict(capital=self.capital,
                    version=self.rule.version, account=self.broker.account,
                    description='USD strategy allocation within the actual paper account; warm-up profits excluded'))
            self.reconcile(snap)
            quotes = {}
            self.state['quotes'] = quotes
            for s in self.rule.symbols:
                quotes[s] = self.broker.quote(s)
                validate_quote({**quotes[s], 'market_open':True}, datetime.now(UTC))
            portfolio = self.store.portfolio(self.strategy, self.capital, quotes)
            expected = {p['symbol']:p['quantity'] for p in portfolio['positions']}
            if any(abs(snap['positions'].get(s,0)-expected.get(s,0)) > 1e-7 for s in set(snap['positions']) | set(expected)):
                raise Blocked('Broker holdings differ from attributed fills/fees; trading blocked until reconciled')
            # This account is dedicated to this allocation; unrelated cash stays unallocated.
            if abs(portfolio['cash']+self.state['unallocated_cash']-snap['cash']) > .02 or snap['cash'] < 0:
                raise Blocked('Broker cash differs from attributed cash plus inception reserve; reconcile fees, transfers or distributions')
            self.state['quotes'] = quotes
            self.state['data_timestamp'] = min(q['timestamp'] for q in quotes.values())
            self.state['portfolio'] = portfolio
            self.state['reconciliation'] = 'matched'
            self.state['error'] = None
            self.history(now, portfolio, quotes)
            self.schedule(now, portfolio, quotes, snap)
            self.state['last_reconciled'] = iso(now)
        except Blocked as error:
            self.fail(str(error))
        except Exception:
            # Never publish exception repr / response bodies, which may contain secrets.
            self.fail('Broker/service request failed; check connection, subscriptions and server configuration')
        self.save()
        return self.state

    def fail(self, reason):
        if self.state.get('error') != reason:
            self.store.event(self.strategy, 'error', dict(reason=reason))
        self.state['error'] = reason
        self.state['reconciliation'] = 'blocked'
        self.state['connection'] = 'unverified'
        self.state['valuation_stale'] = True

    def history(self, now, p, quotes):
        self.state['valuation_stale'] = False
        equity = p['equity']
        peak = max(self.state.get('peak', self.capital), equity)
        drawdown = (equity/peak-1)*100
        benchmark = self.capital*sum((quotes[s]['bid']+quotes[s]['ask'])/2/start
                          for s,start in self.state['benchmark_start'].items())/len(self.rule.symbols)
        self.state.update(peak=peak, drawdown=drawdown, max_drawdown=min(self.state.get('max_drawdown',0),drawdown),
                          benchmark=benchmark)
        # One real observation per five minutes, never historical simulated performance.
        bucket = iso(now.replace(minute=now.minute//5*5, second=0, microsecond=0))
        payload = dict(time=iso(now), equity=equity, benchmark=benchmark, cash=p['cash'], drawdown=drawdown)
        with self.store.db:
            self.store.db.execute('INSERT OR IGNORE INTO history VALUES (?,?,?)',
                                 (bucket, self.strategy, __import__('json').dumps(payload)))

    def schedule_clock(self, now):
        since = dt(self.state.get('last_checked',self.state['inception']))
        upcoming = list(slots(self.strategy,since-timedelta(days=2),now))
        future = next((s for s in upcoming if dt(s['evaluate'])>now),None)
        self.state['next_evaluation'] = future['evaluate'] if future else None
        for slot in upcoming:
            if dt(slot['evaluate']) < dt(self.state['inception']) or dt(slot['expires']) > now:
                continue
            key = 'cycle:'+self.strategy+':'+slot['key']
            previous = self.store.get(key,{})
            if previous.get('status') not in ('done','missed','paused'):
                self.store.put(key,dict(status='missed',slot=slot))
                self.store.event(self.strategy,'missed_cycle',slot)

    def schedule(self, now, portfolio, quotes, snap):
        inception = dt(self.state['inception'])
        since = dt(self.state.get('last_checked', self.state['inception']))
        all_slots = list(slots(self.strategy, since-timedelta(days=2), now))
        future = next((s for s in all_slots if dt(s['evaluate']) > now), None)
        self.state['next_evaluation'] = future['evaluate'] if future else None
        for slot in all_slots:
            evaluation = dt(slot['evaluate'])
            if evaluation < inception or evaluation > now:
                continue
            key = 'cycle:'+self.strategy+':'+slot['key']
            cycle = self.store.get(key)
            if cycle and cycle['status'] in ('done','missed','paused'):
                continue
            if now >= dt(slot['expires']):
                self.store.put(key, dict(status='missed', slot=slot))
                self.store.event(self.strategy, 'missed_cycle', slot)
                continue
            if self.state['mode'] != 'running':
                self.store.put(key, dict(status='paused', slot=slot))
                self.store.event(self.strategy, 'rejected', dict(reason='Paused at evaluation; cycle skipped', **slot))
                continue
            if not cycle:
                histories = {s:self.broker.history(s,slot['signal_date']) for s in self.rule.symbols}
                selected, decisions = signal(self.rule,histories,warmup_dates(self.strategy,slot['signal_date']))
                cycle = dict(status='evaluated', selected=selected, decisions=decisions, slot=slot)
                self.store.put(key, cycle)
                self.store.event(self.strategy, 'signal', dict(version=self.rule.version, **cycle))
            self.state['next_execution'] = slot['execute']
            if now < dt(slot['execute']):
                continue
            open_orders = [o for o in self.store.records('orders', self.strategy) if o['status'] not in TERMINAL]
            if open_orders:
                self.manage_open_order(open_orders[0],quotes,now)
                return
            if 'targets' not in cycle:
                budget = portfolio['equity']*self.rule.exposure
                target = {}
                for symbol in self.rule.symbols:
                    weight = 1/len(cycle['selected']) if symbol in cycle['selected'] else 0
                    execution_buffer = 1+MAX_PRICE_DRIFT
                    raw = budget*weight/(quotes[symbol]['ask']*execution_buffer)
                    target[symbol] = math.floor(raw) if self.strategy == 'etf' else math.floor(raw*1e8)/1e8
                cycle['targets'] = target
                self.store.put(key,cycle)
            holdings = {p['symbol']:p['quantity'] for p in portfolio['positions']}
            all_orders = self.store.records('orders',self.strategy)
            existing = {o['id'] for o in all_orders}
            # Sell first; one order at a time, reconcile actual proceeds before buying.
            differences = [(s, cycle['targets'][s]-holdings.get(s,0)) for s in self.rule.symbols]
            differences.sort(key=lambda item: (item[1] > 0, item[0]))
            for symbol, diff in differences:
                side = 'buy' if diff > 0 else 'sell'
                base_ref = 'pnx-'+hashlib.sha256(f'{self.experiment}:{self.strategy}:{slot["key"]}:{symbol}:{side}'.encode()).hexdigest()[:28]
                ref = base_ref
                related = [o for o in all_orders if o.get('cycle') == slot['key'] and
                           o.get('symbol') == symbol and o.get('side') == side]
                legacy_zero_fill = [o for o in related if o.get('status') == 'cancelled' and
                                    not o.get('filled') and o.get('execution_policy') != MONITORED_LIMIT_POLICY]
                if self.strategy == 'crypto' and legacy_zero_fill:
                    ref = base_ref+'-r1'
                if ref in existing or (related and not legacy_zero_fill) or abs(diff)*quotes[symbol]['ask'] < 5:
                    continue
                validate_quote(quotes[symbol], datetime.now(UTC))
                quantity = abs(diff)
                if self.strategy == 'etf':
                    quantity = math.floor(quantity)
                else:
                    quantity = math.floor(quantity*1e8)/1e8
                price = round(quotes[symbol]['ask'] if side == 'buy' else quotes[symbol]['bid'], 2)
                if not quantity:
                    continue
                if side == 'buy' and quantity*price > min(portfolio['cash']-portfolio['equity']*self.rule.reserve, snap['cash'])+1e-8:
                    self.store.event(self.strategy,'rejected',dict(symbol=symbol,reason='Insufficient cash after fee reserve'))
                    continue
                if side == 'sell' and quantity > holdings.get(symbol,0)+1e-8:
                    raise Blocked('Sell exceeds confirmed attributed holdings')
                order = dict(id=ref,strategy=self.strategy,symbol=symbol,side=side,quantity=quantity,
                    limit=price,status='uncertain',created_at=iso(datetime.now(UTC)),cycle=slot['key'])
                order.update(execution_policy=MONITORED_LIMIT_POLICY,initial_limit=price,
                    price_ceiling=round(price*(1+MAX_PRICE_DRIFT),2) if side == 'buy' else None,
                    price_floor=round(price*(1-MAX_PRICE_DRIFT),2) if side == 'sell' else None,
                    last_reprice_at=iso(datetime.now(UTC)),reprice_count=0,
                    execution_deadline=slot['expires'])
                if legacy_zero_fill:
                    order['upgrades_order'] = legacy_zero_fill[-1]['id']
                self.broker.preflight(order)
                self.before_submit()
                # Reject if lengthy preflight crossed the eligible execution window or quote TTL.
                validate_quote(quotes[symbol], datetime.now(UTC))
                if datetime.now(UTC) >= dt(slot['expires']):
                    raise Blocked('Execution window elapsed during preflight')
                if not self.store.intent(self.strategy,order):
                    raise Blocked('Duplicate order intention prevented')
                self.store.event(self.strategy,'submitted_intent',order)
                broker_id = self.broker.submit(order)
                order.update(broker_id=broker_id,broker_ids=[broker_id],status='submitted')
                self.store.record('orders',self.strategy,order)
                self.store.event(self.strategy,'submitted',order)
                self.state['execution_state'] = 'Order submitted; awaiting broker confirmation'
                return
            cycle['status'] = 'done'
            self.store.put(key,cycle)
            self.state['last_success'] = iso(datetime.now(UTC))
            self.state['next_execution'] = None
            self.state['execution_state'] = 'Cycle complete'
            self.store.event(self.strategy,'cycle_complete',dict(key=slot['key'],
                explanation='Confirmed fills only. Unfilled/rejected remainders wait for next scheduled evaluation.'))
        self.state['last_checked'] = iso(now)

    def manage_open_order(self, order, quotes, now):
        self.state['execution_state'] = 'Waiting for final broker order status; no new submission'
        if order.get('execution_policy') != MONITORED_LIMIT_POLICY:
            return
        if now >= dt(order['execution_deadline']):
            self.before_submit()
            order.update(status='cancel_uncertain',cancel_requested_at=iso(now))
            self.store.record('orders',self.strategy,order)
            self.store.event(self.strategy,'cancel_requested',dict(id=order['id'],reason='Execution window expired'))
            self.broker.cancel(order)
            self.state['execution_state'] = 'Execution window expired; cancellation awaiting broker confirmation'
            return
        if (now-dt(order['last_reprice_at'])).total_seconds() < REPRICE_SECONDS:
            return
        quote = quotes[order['symbol']]
        validate_quote(quote,datetime.now(UTC))
        if order['side'] == 'buy':
            desired = min(round(quote['ask']*1.0005,2),order['price_ceiling'])
        else:
            desired = max(round(quote['bid']*.9995,2),order['price_floor'])
        order['last_reprice_at'] = iso(now)
        if desired == order['limit']:
            self.store.record('orders',self.strategy,order)
            self.state['execution_state'] = 'Open limit order monitored; price cap reached or quote unchanged'
            return
        self.before_submit()
        previous = order['limit']
        order.update(status='replace_uncertain',pending_limit=desired)
        self.store.record('orders',self.strategy,order)
        self.store.event(self.strategy,'replace_intent',dict(id=order['id'],previous_limit=previous,new_limit=desired,
            filled=order.get('filled',0),explanation='Unfilled remainder repriced after one minute; bounded by 1% drift cap'))
        broker_id = self.broker.replace(order,desired)
        order.update(broker_id=broker_id,broker_ids=list(dict.fromkeys(order.get('broker_ids',[])+[broker_id])),
                     limit=desired,status='submitted',reprice_count=order.get('reprice_count',0)+1)
        order.pop('pending_limit',None)
        self.store.record('orders',self.strategy,order)
        self.store.event(self.strategy,'replaced',dict(id=order['id'],limit=desired,reprice_count=order['reprice_count']))
        self.state['execution_state'] = 'Open limit order repriced; awaiting broker confirmation'
