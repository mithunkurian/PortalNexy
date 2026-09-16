import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from trading_backend.forward.brokers import IBPaper, AlpacaPaper
from trading_backend.forward.rules import Blocked, UTC
from trading_backend.forward.service import Publisher
from datetime import datetime, timedelta


class AdapterTests(unittest.TestCase):
    def ib(self):
        with patch.dict('os.environ',{'FORWARD_IB_ACCOUNT':'DU_TEST','FORWARD_IB_PAPER_ALLOWLIST':'DU_TEST'}):
            b=IBPaper()
        b.ib=Mock();b.ib.isConnected.return_value=True;b.ib.managedAccounts.return_value=['DU_TEST']
        return b
    def alpaca(self):
        with patch.dict('os.environ',{'FORWARD_ALPACA_ACCOUNT':'paper-uuid','FORWARD_ALPACA_PAPER_ALLOWLIST':'paper-uuid'}):
            return AlpacaPaper()
    def test_ib_checks_managed_account_not_port(self):
        b=self.ib();b.ib.managedAccounts.return_value=['U_LIVE']
        with self.assertRaises(Blocked):b.check_account()
        b.ib.placeOrder.assert_not_called()
    def test_ib_snapshot_uses_existing_account_stream(self):
        b=self.ib()
        b.ib.accountValues.return_value=[NS(tag='CashBalance',currency='USD',value='1000')]
        b.ib.positions.return_value=[]
        b.ib.reqAllOpenOrders.return_value=[]
        b.ib.reqCompletedOrders.return_value=[]
        b.ib.reqExecutions.return_value=[]
        snapshot=b.snapshot({},'2026-09-12T00:00:00Z')
        self.assertEqual(snapshot['cash'],1000)
        b.ib.reqAccountUpdates.assert_not_called()
        b.ib.reqPositions.assert_not_called()
    def test_ib_fx_cash_records_are_separate_from_security_positions(self):
        b=self.ib()
        b.ib.accountValues.return_value=[NS(tag='CashBalance',currency='USD',value='29783.92')]
        b.ib.positions.return_value=[
            NS(contract=NS(symbol='EUR',secType='CASH',currency='USD'),position=-20000),
            NS(contract=NS(symbol='SPY',secType='STK',currency='USD'),position=3)]
        b.ib.reqAllOpenOrders.return_value=[]
        b.ib.reqCompletedOrders.return_value=[]
        b.ib.reqExecutions.return_value=[]
        snapshot=b.snapshot({},'2026-09-14T00:00:00Z')
        self.assertEqual(snapshot['positions'],{'SPY':3})
        self.assertEqual(snapshot['fx_positions'],[dict(symbol='EUR',currency='USD',quantity=-20000)])
        self.assertEqual(snapshot['cash'],29783.92)
        b.ib.placeOrder.assert_not_called()
    def test_ib_contract_identity(self):
        b=self.ib();b.ib.reqContractDetails.return_value=[NS(contract=NS(symbol='SPY',secType='STK',currency='EUR',primaryExchange='ARCA',conId=12))]
        with self.assertRaises(Blocked):b.contract('SPY')
    def test_ib_no_crypto_order_path(self):
        b=self.ib()
        with self.assertRaises(Blocked):b.contract('BTC')
    def test_ib_whatif_warning_blocks(self):
        b=self.ib();b.contract=Mock(return_value=NS())
        b.ib.whatIfOrder.return_value=NS(warningText='Trading permission unavailable',initMarginChange='0')
        with self.assertRaises(Blocked):b.preflight(dict(symbol='SPY',side='buy',quantity=1,limit=100))
        b.ib.placeOrder.assert_not_called()
    def test_alpaca_wrong_account_blocks(self):
        b=self.alpaca();b.request=Mock(return_value={'id':'live-uuid'})
        with self.assertRaises(Blocked):b.check_account()
    def test_alpaca_trading_blocked(self):
        b=self.alpaca();b.request=Mock(return_value=dict(id='paper-uuid',status='ACTIVE',trading_blocked=True))
        with self.assertRaises(Blocked):b.check_account()
    def test_alpaca_crypto_permission_required(self):
        b=self.alpaca();b.request=Mock(return_value=dict(id='paper-uuid',status='ACTIVE',currency='USD',crypto_status='PENDING'))
        with self.assertRaises(Blocked):b.check_account()
    def test_alpaca_exchange_verified(self):
        b=self.alpaca();b.request=Mock(return_value={'symbol':'BTC/USD','class':'crypto','exchange':'OTHER','tradable':True,'status':'active'})
        with self.assertRaises(Blocked):b.asset('BTC/USD')
    def test_alpaca_activity_pagination(self):
        b=self.alpaca();b.request=Mock(side_effect=[[{'id':str(i)} for i in range(100)],[{'id':'last'}]])
        self.assertEqual(len(b.activities('FILL','2026-09-01')),101)
        self.assertEqual(b.request.call_args.args[1]['page_token'],'99')
    def test_alpaca_crypto_uses_gtc_and_supports_replace_cancel(self):
        b=self.alpaca();b.check_account=Mock();b.request=Mock(side_effect=[{'id':'first'},{'id':'second'},{}])
        order=dict(id='ref',symbol='ETH/USD',quantity=.1,side='buy',limit=2000,broker_id='first')
        self.assertEqual(b.submit(order),'first')
        self.assertEqual(b.request.call_args_list[0].kwargs['data']['time_in_force'],'gtc')
        self.assertEqual(b.replace(order,2001),'second')
        self.assertEqual(b.request.call_args_list[1].kwargs['method'],'PATCH')
        b.cancel(order);self.assertEqual(b.request.call_args_list[2].kwargs['method'],'DELETE')
    def test_lease_expiry_blocks_submission(self):
        p=Publisher.__new__(Publisher);p.owner='owner';p.lease=Mock()
        p.lease.get.return_value.to_dict.return_value=dict(owner='owner',expires=datetime.now(UTC)-timedelta(seconds=1))
        with self.assertRaises(Blocked):p.guard('etf')
    def test_other_service_owner_blocks_submission(self):
        p=Publisher.__new__(Publisher);p.owner='owner';p.lease=Mock()
        p.lease.get.return_value.to_dict.return_value=dict(owner='other',expires=datetime.now(UTC)+timedelta(seconds=60))
        with self.assertRaises(Blocked):p.guard('etf')
    def test_latest_pause_rechecked_before_order(self):
        p=Publisher.__new__(Publisher);p.owner='owner';p.lease=Mock();p.root=Mock()
        p.lease.get.return_value.to_dict.return_value=dict(owner='owner',expires=datetime.now(UTC)+timedelta(seconds=60))
        p.root.collection.return_value.document.return_value.get.return_value.to_dict.return_value={'action':'pause'}
        with self.assertRaises(Blocked):p.guard('etf')


if __name__=='__main__':unittest.main()
