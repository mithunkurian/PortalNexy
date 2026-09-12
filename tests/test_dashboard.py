import unittest
from datetime import datetime
from unittest.mock import Mock
from trading_backend.forward.rules import UTC
from trading_backend.forward.store import Store
from trading_backend.forward.dashboard import activity_summary, period_starts
from trading_backend.forward.service import Publisher


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(':memory:')
        self.addCleanup(self.store.db.close)
        self.now = datetime(2026,9,14,12,tzinfo=UTC)
        self.store.put('strategy:etf',dict(inception='2026-09-01T00:00:00+00:00'))

    def fill(self, id, time, **extra):
        self.store.record('fills','etf',dict(id=id,order_id='one-order',time=time,
            symbol='SPY',side='buy',quantity=2,price=100,fee=None,**extra))

    def test_utc_boundaries_and_full_ledger(self):
        for i in range(120):
            self.fill(str(i),'2026-09-14T00:00:00+00:00')
        self.fill('yesterday','2026-09-13T23:59:59+00:00')
        self.fill('historic','2026-08-31T23:59:59+00:00')
        self.fill('future','2026-09-15T00:00:00+00:00')
        result=activity_summary(self.store,self.now)['periods']
        self.assertEqual(result['today']['etf']['fills'],120)
        self.assertEqual(result['week']['etf']['fills'],120)
        self.assertEqual(result['month']['all']['fills'],121)
        self.assertEqual(result['all']['all']['fills'],121)
        self.assertEqual(result['all']['all']['orders_with_fills'],1)
        self.assertEqual(result['all']['all']['executed_value'],24200)
        self.assertFalse(result['all']['crypto']['started'])

    def test_month_and_week_cross_year(self):
        starts=period_starts(datetime(2027,1,1,12,tzinfo=UTC))
        self.assertEqual(starts['week'].date().isoformat(),'2026-12-28')
        self.assertEqual(starts['month'].date().isoformat(),'2027-01-01')

    def test_archive_retries_and_fee_update(self):
        self.fill('execution','2026-09-14T01:00:00+00:00')
        publisher=Publisher.__new__(Publisher)
        publisher.store=self.store;publisher.root=Mock();publisher.db=Mock()
        publisher.db.batch.return_value.commit.side_effect=RuntimeError('offline')
        with self.assertRaises(RuntimeError):publisher.publish_fill_archive()
        publisher.db.batch.return_value.commit.side_effect=None
        publisher.publish_fill_archive()
        count=publisher.db.batch.return_value.set.call_count
        publisher.publish_fill_archive()
        self.assertEqual(publisher.db.batch.return_value.set.call_count,count)
        f=self.store.records('fills','etf')[0];f['fee']=1
        self.store.record('fills','etf',f);publisher.publish_fill_archive()
        self.assertEqual(publisher.db.batch.return_value.set.call_count,count+1)


if __name__=='__main__':unittest.main()
