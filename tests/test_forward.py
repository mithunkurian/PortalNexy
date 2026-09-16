import copy
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from trading_backend.forward.rules import RULES, Blocked, UTC, dt, iso, slots, signal, warmup_dates, validate_quote, enforce_account
from trading_backend.forward.store import Store
from trading_backend.forward.engine import Engine
from trading_backend.forward.brokers import IBPaper, AlpacaPaper


class Clock(datetime):
    current = dt('2026-09-11T00:06:00+00:00')
    @classmethod
    def now(cls, tz=None):
        return cls.current


class Broker:
    name='test-paper';account='DU_TEST'
    def __init__(self):
        self.allowed={'DU_TEST'};self.submissions=[];self.positions={};self.orders={};self.fills=[]
        self.cash=10000.;self.delayed=False;self.old=False;self.external=[];self.failing=False;self.ask=100.;self.replacements=[];self.cancellations=[]
    def connect(self):enforce_account(self.account,self.allowed)
    def snapshot(self,known,inception):
        return dict(account=self.account,cash=self.cash,positions=self.positions,orders=copy.deepcopy(self.orders),
                    fills=copy.deepcopy(self.fills),external_orders=self.external,fees=[],timestamp=iso(Clock.current))
    def quote(self,s):
        return dict(bid=self.ask-.01,ask=self.ask,timestamp=iso(Clock.current-timedelta(seconds=120) if self.old else Clock.current),
                    delayed=self.delayed,market_open=True)
    def history(self,s,end):
        return {day:100+i for i,day in enumerate(warmup_dates('crypto' if '/' in s else 'etf',end))}
    def preflight(self,o):self.connect()
    def submit(self,o):
        self.connect();self.submissions.append(copy.deepcopy(o))
        if self.failing:raise TimeoutError('secret-bearing transport text must never escape')
        self.orders[o['id']]={**o,'status':'open','filled':0}
        return 'broker-'+o['id']
    def replace(self,o,limit):
        self.replacements.append((o['id'],limit));self.orders[o['id']].update(limit=limit,status='open')
        return 'replacement-'+str(len(self.replacements))
    def cancel(self,o):
        self.cancellations.append(o['id']);self.orders[o['id']]['status']='cancelled'
    def fill(self,o,qty,price=100,fee=1,terminal=False):
        self.fills.append(dict(id='execution-'+str(len(self.fills)),order_id=o['id'],symbol=o['symbol'],
            quantity=qty,price=price,side=o['side'],time=iso(Clock.current),fee=fee))
        sign=1 if o['side']=='buy' else -1
        self.positions[o['symbol']]=self.positions.get(o['symbol'],0)+qty*sign
        self.cash-=qty*price*sign+fee
        self.orders[o['id']]['filled']+=qty
        self.orders[o['id']]['status']='filled' if terminal else 'open'


class ForwardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(str(Path(self.tmp.name)/'paper.sqlite3'));self.addCleanup(self.store.db.close)
        self.broker=Broker();self.engine=Engine(self.store,'crypto',self.broker,1000,'test-v1')
        Clock.current=dt('2026-09-11T00:06:00+00:00')
        self.patch=patch('trading_backend.forward.engine.datetime',Clock);self.patch.start();self.addCleanup(self.patch.stop)
    def start(self):self.engine.control('start');self.engine.step(Clock.current)
    def next_day(self):Clock.current+=timedelta(days=1);self.engine.step(Clock.current)
    def test_account_allowlist_required(self):
        for account,allowed in [('DU_TEST',set()),('U_LIVE',{'DU_TEST'}),('DU_OTHER',{'DU_TEST'})]:
            with self.assertRaises(Blocked):enforce_account(account,allowed)
    def test_wrong_account_never_starts(self):
        self.broker.allowed=set();self.start();self.assertIsNone(self.engine.state['inception']);self.assertFalse(self.broker.submissions)
    def test_no_inception_history_backfill(self):
        self.start();self.assertFalse(self.broker.submissions)
        self.assertEqual(self.engine.state['portfolio']['equity'],1000)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM history').fetchone()[0],1)
    def test_initial_old_holdings_preserved_and_excluded(self):
        self.broker.positions={'SPY':5};self.start();self.assertIsNone(self.engine.state['inception']);self.assertEqual(self.broker.positions,{'SPY':5})
    def test_external_orders_block_without_cancel(self):
        self.broker.external=[{'symbol':'SPY'}];self.start();self.assertIsNone(self.engine.state['inception']);self.assertEqual(len(self.broker.external),1)
    def test_crypto_completed_day_timing(self):
        days=list(slots('crypto',dt('2026-09-11T00:00:00Z'),dt('2026-09-11T23:00:00Z')))
        self.assertEqual(days[0]['signal_date'],'2026-09-10');self.assertEqual(dt(days[0]['evaluate']).minute,5)
    def test_etf_weekly_holiday_and_following_session(self):
        result=list(slots('etf',dt('2026-01-01T00:00:00Z'),dt('2026-01-06T00:00:00Z')))[0]
        self.assertEqual(result['key'],'2025-W52')
        holiday_week=[s for s in slots('etf',dt('2026-01-18T00:00:00Z'),dt('2026-01-22T00:00:00Z')) if s['key']=='2026-W04'][0]
        self.assertEqual(holiday_week['signal_date'],'2026-01-20');self.assertEqual(dt(holiday_week['execute']).date().isoformat(),'2026-01-21')
        self.assertGreater(dt(result['execute']),dt(result['evaluate']))
    def test_etf_has_one_cycle_per_week(self):
        result=list(slots('etf',dt('2026-09-01T00:00:00Z'),dt('2026-09-30T00:00:00Z')))
        keys=[s['key'] for s in result]
        self.assertEqual(len(keys),len(set(keys)))
        self.assertIn('2026-W37',keys);self.assertIn('2026-W38',keys)
    def test_etf_dst_schedule(self):
        jan=list(slots('etf',dt('2026-01-01T00:00:00Z'),dt('2026-01-02T00:00:00Z')))[0]
        jul=list(slots('etf',dt('2026-07-01T00:00:00Z'),dt('2026-07-02T00:00:00Z')))[0]
        self.assertEqual(dt(jan['execute']).hour,14);self.assertEqual(dt(jul['execute']).hour,13)
    def test_signal_positive_and_trend_required(self):
        dates=warmup_dates('crypto','2026-09-10')
        hist={'BTC/USD':{d:100+i for i,d in enumerate(dates)},'ETH/USD':{d:200 for d in dates}}
        selected,_=signal(RULES['crypto'],hist,dates);self.assertEqual(selected,['BTC/USD'])
        hist['BTC/USD']={d:300-i for i,d in enumerate(dates)}
        self.assertEqual(signal(RULES['crypto'],hist,dates)[0],[])
    def test_incomplete_warmup_rejected(self):
        with self.assertRaises(Blocked):signal(RULES['crypto'],{},warmup_dates('crypto','2026-09-10'))
    def test_future_bars_not_used(self):
        dates=warmup_dates('crypto','2026-09-10');hist={s:{d:100 for d in dates} for s in RULES['crypto'].symbols}
        for h in hist.values():h['2026-09-11']=100000
        self.assertEqual(signal(RULES['crypto'],hist,dates)[0],[])
    def test_duplicate_submission_prevented(self):
        self.start();self.next_day();self.engine.step(Clock.current);self.assertEqual(len(self.broker.submissions),1)
    def test_ambiguous_submit_never_retried_after_restart(self):
        self.start();self.broker.failing=True;self.next_day();self.assertEqual(len(self.broker.submissions),1)
        self.engine=Engine(self.store,'crypto',self.broker,1000,'test-v1');self.engine.step(Clock.current)
        self.assertEqual(len(self.broker.submissions),1);self.assertIn('Uncertain',self.engine.state['error'])
        self.assertNotIn('secret-bearing',str(self.engine.state))
    def test_partial_fill_reconciled_exactly_once(self):
        self.start();self.next_day();o=self.broker.submissions[0];self.broker.fill(o,2)
        self.engine.step(Clock.current);self.engine.step(Clock.current)
        p=self.store.portfolio('crypto',1000,{'BTC/USD':self.broker.quote('BTC/USD')})
        self.assertEqual(p['cash'],799);self.assertEqual(p['positions'][0]['quantity'],2);self.assertEqual(p['costs'],1)
        self.assertEqual(len(self.broker.submissions),1)
    def test_restart_preserves_mode_and_partial_holdings(self):
        self.start();self.next_day();self.broker.fill(self.broker.submissions[0],2)
        self.engine.control('pause');self.engine.step(Clock.current)
        again=Engine(self.store,'crypto',self.broker,1000,'test-v1');again.step(Clock.current)
        self.assertEqual(again.state['mode'],'paused');self.assertEqual(again.state['portfolio']['positions'][0]['quantity'],2)
    def test_pause_skips_new_orders_but_keeps_holdings(self):
        self.start();self.engine.control('pause');self.next_day();self.assertEqual(self.broker.submissions,[])
        self.assertEqual(self.store.get('cycle:crypto:2026-09-12')['status'],'paused')
        self.engine.control('resume');self.engine.step(Clock.current);self.assertEqual(self.broker.submissions,[])
    def test_pause_racing_preflight_blocks_submission(self):
        self.start();self.engine.before_submit=lambda: (_ for _ in ()).throw(Blocked('Pause requested'))
        self.next_day();self.assertFalse(self.broker.submissions)
    def test_stale_and_delayed_data(self):
        self.start();self.broker.old=True;self.next_day();self.assertFalse(self.broker.submissions)
        self.broker.old=False;self.broker.delayed=True;self.engine.step(Clock.current);self.assertIn('Delayed',self.engine.state['error'])
    def test_market_hours_and_bad_spreads(self):
        q=self.broker.quote('BTC/USD')
        for bad in ({'market_open':False},{'bid':float('nan')},{'ask':110},{'timestamp':iso(Clock.current+timedelta(seconds=1))}):
            with self.assertRaises(Blocked):validate_quote({**q,**bad},Clock.current)
    def test_missing_cycles_recorded_not_past_fills(self):
        self.start();Clock.current+=timedelta(days=4);self.engine.step(Clock.current)
        self.assertEqual(self.store.get('cycle:crypto:2026-09-12')['status'],'missed')
        self.assertEqual(len(self.broker.submissions),1);self.assertEqual(self.broker.submissions[0]['created_at'],iso(Clock.current))
    def test_configuration_frozen_on_restart(self):
        self.start()
        with self.assertRaises(Blocked):Engine(self.store,'crypto',self.broker,2000,'test-v1')
    def test_configuration_can_be_completed_before_inception(self):
        self.engine.save()
        next_engine=Engine(self.store,'crypto',self.broker,2000,'test-v1')
        self.assertEqual(next_engine.state['capital'],2000)
    def test_accounting_realised_unrealised_fees(self):
        for f in [dict(id='1',symbol='SPY',side='buy',quantity=10,price=100,fee=1,time='2026-09-01'),dict(id='2',symbol='SPY',side='sell',quantity=4,price=110,fee=1,time='2026-09-02')]:self.store.record('fills','etf',f)
        p=self.store.portfolio('etf',2000,{'SPY':{'bid':119,'ask':121}})
        self.assertEqual(p['cash'],1438);self.assertEqual(p['realised'],38);self.assertEqual(p['unrealised'],120);self.assertEqual(p['equity'],2158)
    def test_crypto_asset_fee_accounting(self):
        self.store.record('fills','crypto',dict(id='1',symbol='BTC/USD',side='buy',quantity=1,price=100,fee=0,time='2026-09-01'))
        self.store.put('fees:crypto',[dict(id='fee',symbol='BTC/USD',quantity=.01,usd=1)])
        p=self.store.portfolio('crypto',1000,{'BTC/USD':{'bid':100,'ask':100}})
        self.assertAlmostEqual(p['equity'],999);self.assertAlmostEqual(p['positions'][0]['quantity'],.99)
    def test_reconciliation_mismatch_blocks(self):
        self.start();self.broker.positions={'BTC/USD':3};self.next_day();self.assertIn('differ',self.engine.state['error']);self.assertFalse(self.broker.submissions)
    def test_missing_execution_blocks(self):
        self.start();self.next_day();o=self.broker.submissions[0];self.broker.orders[o['id']]['filled']=1
        self.engine.step(Clock.current);self.assertIn('incomplete',self.engine.state['error'])
    def test_retired_runtime_cannot_execute(self):
        from trading_backend.broker.ibkr import IBKRBrokerAdapter,MockBrokerAdapter
        from trading_backend.runtime.worker import RuntimeWorker
        for cls in (IBKRBrokerAdapter,MockBrokerAdapter,RuntimeWorker):
            with self.assertRaises(RuntimeError):cls('live')
    def test_alpaca_cannot_use_live_endpoint(self):self.assertEqual(AlpacaPaper.endpoint,'https://paper-api.alpaca.markets')
    def test_terminal_partial_fill_not_topped_up_in_same_cycle(self):
        self.start();self.next_day();o=self.broker.submissions[0];self.broker.fill(o,2)
        self.broker.orders[o['id']]['status']='cancelled'
        self.engine.step(Clock.current);self.engine.step(Clock.current)
        self.assertEqual(len(self.broker.submissions),1)
        self.assertEqual(self.store.get('cycle:crypto:2026-09-12')['status'],'done')
    def test_reconnect_does_not_duplicate_open_order(self):
        self.start();self.next_day();self.broker.allowed=set();self.engine.step(Clock.current)
        self.broker.allowed={'DU_TEST'};self.engine.step(Clock.current)
        self.assertEqual(len(self.broker.submissions),1)
    def test_crypto_open_limit_reprices_once_per_minute_with_cap(self):
        self.start();self.next_day();order=self.broker.submissions[0]
        self.assertEqual(order['execution_policy'],'marketable-limit-reprice-1.0.0')
        Clock.current+=timedelta(seconds=61);self.broker.ask=100.5;self.engine.step(Clock.current)
        self.assertEqual(len(self.broker.replacements),1);self.assertEqual(self.broker.replacements[0][1],100.55)
        self.engine.step(Clock.current);self.assertEqual(len(self.broker.replacements),1)
        Clock.current+=timedelta(seconds=61);self.broker.ask=120;self.engine.step(Clock.current)
        self.assertEqual(self.broker.replacements[-1][1],101.0)
    def test_crypto_reprice_survives_restart_without_duplicate_submit(self):
        self.start();self.next_day();Clock.current+=timedelta(seconds=61);self.broker.ask=100.5
        again=Engine(self.store,'crypto',self.broker,1000,'test-v1');again.step(Clock.current)
        self.assertEqual(len(self.broker.submissions),1);self.assertEqual(len(self.broker.replacements),1)
    def test_etf_open_limit_uses_same_monitored_reprice_policy(self):
        engine=Engine(self.store,'etf',self.broker,1000,'test-v1')
        order=dict(id='etf-order',strategy='etf',symbol='SPY',side='buy',quantity=1,limit=100,
            status='submitted',execution_policy='marketable-limit-reprice-1.0.0',initial_limit=100,
            price_ceiling=101,price_floor=None,last_reprice_at=iso(Clock.current),reprice_count=0,
            execution_deadline=iso(Clock.current+timedelta(hours=1)))
        self.broker.orders[order['id']]={**order,'filled':0}
        self.store.record('orders','etf',order)
        Clock.current+=timedelta(seconds=61);self.broker.ask=100.5
        engine.manage_open_order(order,{'SPY':self.broker.quote('SPY')},Clock.current)
        self.assertEqual(self.broker.replacements,[('etf-order',100.55)])
        self.assertEqual(self.store.records('orders','etf')[0]['execution_policy'],'marketable-limit-reprice-1.0.0')
    def test_cancelled_legacy_ioc_gets_one_safe_policy_upgrade(self):
        self.start();self.next_day();old=self.broker.submissions[0]
        self.broker.orders[old['id']]['status']='cancelled'
        stored=self.store.records('orders','crypto')[0];stored['status']='cancelled';stored['filled']=0
        for key in ('execution_policy','execution_deadline','last_reprice_at'):
            stored.pop(key,None);self.broker.orders[old['id']].pop(key,None)
        self.store.record('orders','crypto',stored)
        self.engine.step(Clock.current)
        self.assertEqual(len(self.broker.submissions),2)
        self.assertTrue(self.broker.submissions[1]['id'].endswith('-r1'))
        self.assertEqual(self.broker.submissions[1]['upgrades_order'],old['id'])
        self.engine.step(Clock.current);self.assertEqual(len(self.broker.submissions),2)
    def test_cash_adjustments_block_instead_of_inventing_profit(self):
        self.start();self.broker.cash+=20;self.next_day()
        self.assertIn('Broker cash differs',self.engine.state['error']);self.assertFalse(self.broker.submissions)
    def test_combined_drawdown_uses_full_history(self):
        import json
        for i,value in enumerate((1000,1200,900)):
            for strategy in ('etf','crypto'):
                self.store.db.execute('INSERT INTO history VALUES (?,?,?)',(f'2026-09-0{i+1}',strategy,json.dumps(dict(time=f'2026-09-0{i+1}',equity=value,benchmark=1000))))
        state=dict(updated_at=iso(Clock.current),inception=iso(Clock.current),portfolio=dict(equity=900,cash=900,realised=-100,unrealised=0,costs=0,positions=[]),benchmark=1000)
        for strategy in ('etf','crypto'):self.store.put('strategy:'+strategy,state)
        summary=self.store.combined(Clock.current)
        self.assertEqual(summary['max_drawdown'],-25);self.assertEqual(summary['portfolio']['equity'],1800)
    def test_partial_strategy_does_not_invent_combined_total(self):
        self.start();self.assertIsNone(self.store.combined(Clock.current)['portfolio'])
    def test_ib_account_identity_rechecked(self):
        with patch.dict('os.environ',{'FORWARD_IB_ACCOUNT':'U_LIVE','FORWARD_IB_PAPER_ALLOWLIST':'DU_TEST'}):
            broker=IBPaper()
            with self.assertRaises(Blocked):broker.connect()


if __name__=='__main__':unittest.main()
