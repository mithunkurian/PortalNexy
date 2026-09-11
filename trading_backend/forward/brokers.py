"""Paper-only adapters. No configurable live HTTP endpoint and no fabricated fills."""
import json
import math
import os
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from urllib.parse import urlencode, quote
from urllib.error import HTTPError
from .rules import Blocked, UTC, dt, iso, enforce_account


def number(value):
    result = float(value)
    if not math.isfinite(result):
        raise Blocked('Broker supplied a non-finite number')
    return result


class IBPaper:
    name = 'IBKR paper'

    def __init__(self):
        from ib_insync import IB
        self.ib = IB()
        self.ib.RequestTimeout = 15
        self.account = os.getenv('FORWARD_IB_ACCOUNT', '')
        self.allowlist = set(filter(None, os.getenv('FORWARD_IB_PAPER_ALLOWLIST', '').split(',')))
        self.contracts = {}
        self.details = {}
        # Avoid the library logging order payloads/account data to unattended logs.
        import logging
        logging.getLogger('ib_insync').setLevel(logging.CRITICAL)

    def connect(self):
        enforce_account(self.account, self.allowlist)
        # Additional safeguard, never a substitute for the exact allowlist.
        if not self.account.startswith('DU'):
            raise Blocked('IBKR account must be a verified DU paper account')
        if not self.ib.isConnected():
            self.contracts.clear()
            self.ib.connect(os.getenv('FORWARD_IB_HOST', '127.0.0.1'),
                int(os.getenv('FORWARD_IB_PORT', '7497')),
                clientId=int(os.getenv('FORWARD_IB_CLIENT_ID', '71')),
                timeout=12, readonly=False, account=self.account)
        self.check_account()

    def check_account(self):
        enforce_account(self.account, self.allowlist)
        if not self.ib.isConnected() or self.account not in self.ib.managedAccounts():
            raise Blocked('IBKR disconnected or selected account unavailable')

    def contract(self, symbol):
        from ib_insync import Stock
        exchanges = {'SPY': 'ARCA', 'EFA': 'ARCA', 'EEM': 'ARCA', 'TLT': 'NASDAQ', 'GLD': 'ARCA'}
        if symbol not in exchanges:
            raise Blocked('IBKR execution adapter supports only the verified ETF universe')
        if symbol not in self.contracts:
            candidate = Stock(symbol, 'SMART', 'USD', primaryExchange=exchanges[symbol])
            matches = self.ib.reqContractDetails(candidate)
            if len(matches) != 1:
                raise Blocked(f'{symbol}: ambiguous/unavailable contract')
            d = matches[0]; c = d.contract
            if c.symbol != symbol or c.secType != 'STK' or c.currency != 'USD' or c.primaryExchange != exchanges[symbol] or not c.conId:
                raise Blocked(f'{symbol}: contract identity/exchange/currency mismatch')
            self.contracts[symbol] = c
        # Refresh trading sessions each day; contract identity is rechecked on reconnect.
        d = self.ib.reqContractDetails(self.contracts[symbol])[0]
        self.details[symbol] = d
        return self.contracts[symbol]

    def quote(self, symbol):
        c = self.contract(symbol)
        self.ib.reqMarketDataType(1)
        ticker = self.ib.reqMktData(c, '', False, False)
        try:
            self.ib.sleep(2)
            d = self.details[symbol]
            now = datetime.now(UTC)
            sessions = d.liquidSessions()
            market_open = any(s.start.astimezone(UTC) <= now < s.end.astimezone(UTC) for s in sessions)
            return dict(bid=number(ticker.bid), ask=number(ticker.ask),
                        timestamp=iso(ticker.time) if ticker.time else None,
                        delayed=ticker.marketDataType != 1, market_open=market_open,
                        contract_id=c.conId, exchange=c.primaryExchange, currency=c.currency,
                        source='IBKR streaming subscription')
        finally:
            self.ib.cancelMktData(c)

    def history(self, symbol, end_date):
        # Empty endDateTime obtains current bars; the signal selector discards all dates after cutoff.
        bars = self.ib.reqHistoricalData(self.contract(symbol), endDateTime='', durationStr='2 Y',
            barSizeSetting='1 day', whatToShow='TRADES', useRTH=True, formatDate=1)
        return {str(b.date)[:10]: number(b.close) for b in bars if str(b.date)[:10] <= end_date}

    def snapshot(self, known, inception):
        from ib_insync import ExecutionFilter
        self.check_account()
        self.ib.reqAccountUpdates(self.account)
        values = self.ib.accountValues(self.account)
        cash = next((number(v.value) for v in values if v.tag == 'CashBalance' and v.currency == 'USD'), None)
        equity = next((number(v.value) for v in values if v.tag == 'NetLiquidation' and v.currency == 'BASE'), None)
        if cash is None:
            raise Blocked('IBKR USD cash balance unavailable')
        self.ib.reqPositions()
        positions = {p.contract.symbol: number(p.position) for p in self.ib.positions(self.account)}
        trades = self.ib.reqAllOpenOrders() + self.ib.reqCompletedOrders(apiOnly=False)
        orders = {}
        external = []
        for t in trades:
            if t.order.account != self.account:
                continue
            ref = t.order.orderRef
            status = t.orderStatus.status
            mapped = {'Filled':'filled','Cancelled':'cancelled','ApiCancelled':'cancelled','Inactive':'rejected'}.get(status, 'open')
            item = dict(id=ref, broker_id=str(t.order.permId or t.order.orderId), status=mapped,
                        filled=number(t.orderStatus.filled), symbol=t.contract.symbol)
            if ref in known:
                orders[ref] = item
            elif mapped == 'open':
                external.append(dict(symbol=t.contract.symbol, status=status))
        fills = []
        for f in self.ib.reqExecutions(ExecutionFilter(acctCode=self.account)):
            e = f.execution
            if e.orderRef not in known:
                continue
            fee = f.commissionReport.commission
            fills.append(dict(id=e.execId, order_id=e.orderRef, symbol=f.contract.symbol,
                quantity=number(e.shares), price=number(e.price), side='buy' if e.side == 'BOT' else 'sell',
                time=iso(e.time), fee=number(fee) if 0 <= fee < 1e20 and f.commissionReport.currency == 'USD' else None))
        return dict(account=self.account, cash=cash, broker_equity=equity, positions=positions,
                    orders=orders, fills=fills, external_orders=external, fees=[],
                    timestamp=iso(datetime.now(UTC)), currency='USD')

    def preflight(self, order):
        from ib_insync import LimitOrder
        self.check_account()
        c = self.contract(order['symbol'])
        trial = LimitOrder(order['side'].upper(), order['quantity'], order['limit'], account=self.account, tif='DAY')
        state = self.ib.whatIfOrder(c, trial)
        # A warning or missing calculation is not permission to trade.
        if state.warningText or not state.initMarginChange or abs(number(state.initMarginChange)) > 1e20:
            raise Blocked(f"{order['symbol']}: trading permission / what-if preflight failed")

    def submit(self, order):
        from ib_insync import LimitOrder
        self.check_account()
        if order['quantity'] <= 0 or int(order['quantity']) != order['quantity']:
            raise Blocked('IBKR ETF quantity must be positive whole shares')
        trade = self.ib.placeOrder(self.contract(order['symbol']), LimitOrder(
            order['side'].upper(), order['quantity'], order['limit'],
            account=self.account, orderRef=order['id'], tif='DAY', outsideRth=False))
        self.ib.sleep(1)
        return str(trade.order.orderId)

    def crypto_capability(self):
        """Read-only discovery plus what-if; never submits or silently maps to an ETF."""
        from ib_insync import Crypto, LimitOrder
        result = {}
        for symbol in ('BTC', 'ETH'):
            try:
                details = self.ib.reqContractDetails(Crypto(symbol, 'PAXOS', 'USD'))
                if len(details) != 1:
                    result[symbol] = 'Unavailable or ambiguous for this session'
                    continue
                state = self.ib.whatIfOrder(details[0].contract, LimitOrder('BUY', .001, 1,
                    account=self.account, tif='IOC'))
                result[symbol] = ('What-if rejected; paper execution not verified' if state.warningText
                    else 'Contract discovered; what-if alone does not certify paper execution support')
            except Exception:
                result[symbol] = 'Account/API capability could not be verified'
        return result

    def wait(self, seconds):
        self.ib.sleep(seconds)


class AlpacaPaper:
    name = 'Alpaca paper crypto'
    endpoint = 'https://paper-api.alpaca.markets'

    def __init__(self):
        self.account = os.getenv('FORWARD_ALPACA_ACCOUNT', '')
        self.allowlist = set(filter(None, os.getenv('FORWARD_ALPACA_PAPER_ALLOWLIST', '').split(',')))
        self.key = os.getenv('FORWARD_ALPACA_KEY', '')
        self.secret = os.getenv('FORWARD_ALPACA_SECRET', '')

    def request(self, path, params=None, data=None, market=False, missing=False):
        base = 'https://data.alpaca.markets' if market else self.endpoint
        url = base + path + ('?'+urlencode(params) if params else '')
        request = Request(url, data=json.dumps(data).encode() if data is not None else None,
            headers={'APCA-API-KEY-ID':self.key, 'APCA-API-SECRET-KEY':self.secret, 'Content-Type':'application/json'})
        try:
            with urlopen(request, timeout=20) as response:
                return json.load(response)
        except HTTPError as error:
            if missing and error.code == 404:
                return None
            raise Blocked(f'Alpaca request rejected (HTTP {error.code}); check permissions/configuration') from None
        except Exception:
            raise Blocked('Alpaca request unavailable; check connectivity and server configuration') from None

    def connect(self):
        enforce_account(self.account, self.allowlist)
        if not self.key or not self.secret:
            raise Blocked('Alpaca paper API credentials not configured')
        self.check_account()

    def check_account(self):
        a = self.request('/v2/account')
        enforce_account(a['id'], self.allowlist)
        if a['id'] != self.account or a.get('status') != 'ACTIVE' or a.get('trading_blocked') or a.get('account_blocked'):
            raise Blocked('Alpaca paper account identity or trading permission failed')
        if a.get('currency') != 'USD' or a.get('crypto_status') not in ('ACTIVE', 'APPROVED'):
            raise Blocked('Alpaca USD crypto permission unavailable')
        return a

    def asset(self, symbol):
        if symbol not in ('BTC/USD', 'ETH/USD'):
            raise Blocked('Unsupported direct crypto symbol')
        a = self.request('/v2/assets/'+quote(symbol, safe=''))
        if a.get('symbol') != symbol or a.get('class') != 'crypto' or a.get('exchange') != 'CRYPTO' or not a.get('tradable') or a.get('status') != 'active':
            raise Blocked(f'{symbol}: crypto identity/trading permission unavailable')
        return a

    def quote(self, symbol):
        self.asset(symbol)
        data = self.request('/v1beta3/crypto/us/latest/quotes', {'symbols':symbol}, market=True)['quotes'].get(symbol)
        if not data:
            raise Blocked(f'{symbol}: quote unavailable')
        return dict(bid=number(data['bp']), ask=number(data['ap']), timestamp=data['t'], delayed=False,
                    market_open=True, exchange='Alpaca crypto US', currency='USD', source='Alpaca crypto feed')

    def history(self, symbol, end_date):
        start = dt(end_date+'T00:00:00+00:00')-timedelta(days=230)
        end = dt(end_date+'T00:00:00+00:00')+timedelta(days=1)
        params = dict(symbols=symbol, timeframe='1Day', start=iso(start), end=iso(end), limit=1000)
        result = {}
        while True:
            data = self.request('/v1beta3/crypto/us/bars', params, market=True)
            for bar in data.get('bars', {}).get(symbol, []):
                result[bar['t'][:10]] = number(bar['c'])
            if not data.get('next_page_token'):
                return result
            params['page_token'] = data['next_page_token']

    def activities(self, kind, inception):
        params = dict(after=inception, direction='asc', page_size=100)
        result = []
        while True:
            page = self.request('/v2/account/activities/'+kind, params)
            result.extend(page)
            if len(page) < 100:
                return result
            params['page_token'] = page[-1]['id']

    def snapshot(self, known, inception):
        a = self.check_account()
        normal = lambda s: s.replace('BTCUSD','BTC/USD').replace('ETHUSD','ETH/USD')
        positions = {normal(p['symbol']): number(p['qty']) for p in self.request('/v2/positions')}
        external = [dict(symbol=normal(o['symbol']), status=o['status']) for o in self.request('/v2/orders', {'status':'open', 'limit':500})
                    if o['client_order_id'] not in known]
        orders, by_broker = {}, {}
        for ref in known:
            o = self.request('/v2/orders:by_client_order_id', {'client_order_id':ref}, missing=True)
            if not o:
                continue
            status = o['status']
            mapped = {'filled':'filled', 'canceled':'cancelled', 'expired':'cancelled', 'rejected':'rejected'}.get(status, 'open')
            orders[ref] = dict(id=ref, broker_id=o['id'], status=mapped, filled=number(o['filled_qty']), symbol=normal(o['symbol']))
            by_broker[o['id']] = ref
        fills = []
        for f in self.activities('FILL', inception):
            if f.get('order_id') not in by_broker:
                continue
            fills.append(dict(id=f['id'], order_id=by_broker[f['order_id']], symbol=normal(f['symbol']),
                quantity=number(f['qty']), price=number(f['price']), side=f['side'], time=f['transaction_time'], fee=0.))
        fees = []
        for f in self.activities('CFEE', inception) + self.activities('FEE', inception):
            symbol = normal(f.get('symbol',''))
            qty = abs(number(f.get('qty') or 0))
            amount = abs(number(f.get('net_amount') or 0))
            if qty and symbol in ('BTC/USD', 'ETH/USD'):
                fees.append(dict(id=f['id'], symbol=symbol, quantity=qty, usd=qty*number(f['price'])))
            elif amount:
                fees.append(dict(id=f['id'], usd=amount))
        return dict(account=a['id'], cash=number(a['cash']), broker_equity=number(a['equity']),
                    positions=positions, orders=orders, fills=fills, external_orders=external,
                    fees=fees, timestamp=iso(datetime.now(UTC)), currency='USD', costs_provisional=True)

    def preflight(self, order):
        self.check_account()
        a = self.asset(order['symbol'])
        minimum = number(a.get('min_order_size') or .0001)
        increment = number(a.get('min_trade_increment') or .00000001)
        if order['quantity'] < minimum or abs(order['quantity']/increment-round(order['quantity']/increment)) > 1e-5:
            raise Blocked('Crypto quantity violates broker minimum/increment')

    def submit(self, order):
        self.check_account()
        response = self.request('/v2/orders', data=dict(symbol=order['symbol'], qty=str(order['quantity']),
            side=order['side'], type='limit', limit_price=str(order['limit']), time_in_force='ioc',
            client_order_id=order['id']))
        return response['id']

    def wait(self, seconds):
        import time
        time.sleep(seconds)
