"""Background paper service. Run with python -m trading_backend.forward.service."""
import argparse
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from .rules import Blocked, UTC, iso
from .store import Store
from .engine import Engine
from .brokers import IBPaper, AlpacaPaper

ROOT = Path(__file__).resolve().parents[2]


class ProcessLock:
    def __init__(self, path):
        self.file = open(path, 'a+b')
        self.file.seek(0); self.file.write(b'0'); self.file.flush(); self.file.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Blocked('Another engine owns this local ledger') from None


class Publisher:
    def __init__(self, experiment, store):
        import firebase_admin
        from firebase_admin import credentials, firestore
        path = os.getenv('FORWARD_FIREBASE_CREDENTIALS', '')
        if not path:
            raise Blocked('FORWARD_FIREBASE_CREDENTIALS is required')
        try:
            if not firebase_admin._apps:
                firebase_admin.initialize_app(credentials.Certificate(path))
            self.db = firestore.client()
        except Exception:
            raise Blocked('Firebase initialization failed; verify server credential file and project') from None
        self.root = self.db.collection('forwardExperiments').document(experiment)
        self.store = store
        self.owner = str(uuid.uuid4())
        self.lease = self.root.collection('service').document('lease')
        self.experiment = experiment
        self.ledger_id = self.store.get('ledger_id') or str(uuid.uuid4())
        self.store.put('ledger_id', self.ledger_id)

    def acquire(self):
        from firebase_admin import firestore
        @firestore.transactional
        def update(transaction):
            snap = self.lease.get(transaction=transaction)
            data = snap.to_dict() or {}
            if data.get('ledger_id') and data['ledger_id'] != self.ledger_id:
                raise Blocked('Experiment belongs to another ledger; restore the original SQLite backup')
            now = datetime.now(UTC)
            if data.get('owner') != self.owner and data.get('expires') and data['expires'] > now:
                raise Blocked('Another service owns the Firestore experiment lease')
            transaction.set(self.lease, dict(owner=self.owner, ledger_id=self.ledger_id, expires=now+timedelta(seconds=120)))
        update(self.db.transaction())

    def guard(self, strategy):
        data = self.lease.get().to_dict() or {}
        if data.get('owner') != self.owner or data.get('expires',datetime.min.replace(tzinfo=UTC)) <= datetime.now(UTC):
            raise Blocked('Service lease expired; order blocked')
        command = self.root.collection('commands').document(strategy).get().to_dict() or {}
        if command.get('action') == 'pause':
            raise Blocked('Pause requested; no new submission')

    def command(self, engine):
        ref = self.root.collection('commands').document(engine.strategy)
        data = ref.get().to_dict() or {}
        command_id = data.get('id')
        if not command_id or self.store.db.execute('SELECT 1 FROM commands WHERE id=?',(command_id,)).fetchone():
            return
        status = 'applied'
        try:
            issued = data.get('issued_at')
            if not issued or not 0 <= (datetime.now(UTC)-issued).total_seconds() <= 120:
                raise Blocked('Command expired; request again while service is connected')
            engine.control(data.get('action'))
        except Blocked as error:
            status = str(error)
        with self.store.db:
            self.store.db.execute('INSERT OR IGNORE INTO commands VALUES (?)',(command_id,))
        engine.state['last_command'] = dict(id=command_id, status=status)
        engine.save()

    def publish(self, engine):
        strategy = engine.strategy
        state = dict(engine.state)
        state['orders'] = self.store.records('orders',strategy)[-100:]
        state['fills'] = self.store.records('fills',strategy)[-100:]
        state['history'] = [json.loads(r[0]) for r in self.store.db.execute(
            'SELECT payload FROM history WHERE strategy=? ORDER BY time DESC LIMIT 500',(strategy,))][::-1]
        state['events'] = [dict(id=r['id'], time=r['time'], kind=r['kind'], detail=json.loads(r['detail']))
            for r in self.store.db.execute('SELECT * FROM events WHERE strategy=? ORDER BY id DESC LIMIT 60',(strategy,))]
        self.root.collection('strategies').document(strategy).set(state)
        self.root.collection('service').document('summary').set(self.store.combined(datetime.now(UTC)))
        cursor = self.store.get('published_events',0)
        rows = self.store.db.execute('SELECT * FROM events WHERE id>? ORDER BY id LIMIT 200',(cursor,)).fetchall()
        if rows:
            batch = self.db.batch()
            for row in rows:
                batch.set(self.root.collection('journal').document(str(row['id'])),
                    dict(id=row['id'],time=row['time'],strategy=row['strategy'],kind=row['kind'],detail=json.loads(row['detail'])))
            batch.commit()
            self.store.put('published_events',rows[-1]['id'])
        cursor = self.store.get('published_history:'+strategy,'')
        rows = self.store.db.execute('SELECT time,payload FROM history WHERE strategy=? AND time>? ORDER BY time LIMIT 200',
                                    (strategy,cursor)).fetchall()
        if rows:
            batch = self.db.batch()
            for row in rows:
                batch.set(self.root.collection('history').document(strategy+'_'+row['time']),
                          dict(strategy=strategy,**json.loads(row['payload'])))
            batch.commit(); self.store.put('published_history:'+strategy,rows[-1]['time'])
        self.db.collection('forward').document('current').set(dict(experiment=self.experiment,updated_at=iso(datetime.now(UTC))))


def main():
    from dotenv import load_dotenv
    load_dotenv(ROOT/'trading_backend'/'.env.forward')
    parser = argparse.ArgumentParser()
    parser.add_argument('--preflight', action='store_true', help='Read-only broker checks; never starts strategies')
    parser.add_argument('--strategy', choices=('etf','crypto','all'),default='all',help='Preflight scope only')
    args = parser.parse_args()
    experiment = os.getenv('FORWARD_EXPERIMENT','forward-v1')
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,48}',experiment):
        raise Blocked('Invalid experiment identifier')
    path = ROOT/'trading_backend'/'state'/('forward-'+experiment+'.sqlite3')
    path.parent.mkdir(parents=True,exist_ok=True)
    lock = ProcessLock(str(path)+'.lock')
    store = Store(path)
    brokers = {'etf':IBPaper(),'crypto':AlpacaPaper()}
    engines = [Engine(store,s,b,float(os.getenv('FORWARD_'+s.upper()+'_USD','0')),experiment) for s,b in brokers.items()]
    if args.preflight:
        failed = False
        for engine in engines:
            if args.strategy not in ('all',engine.strategy):
                continue
            try:
                engine.broker.connect()
                snapshot = engine.broker.snapshot({},iso(datetime.now(UTC)))
                result = dict(strategy=engine.strategy,connected=True,account=snapshot['account'],
                    currency=snapshot['currency'],cash=snapshot['cash'],existing_positions=snapshot['positions'],
                    existing_orders=snapshot['external_orders'])
                result['quotes'] = {s:engine.broker.quote(s) for s in engine.rule.symbols}
                for symbol,q in result['quotes'].items():
                    from .rules import validate_quote
                    validate_quote({**q,'market_open':True},datetime.now(UTC))
                    engine.broker.preflight(dict(symbol=symbol,side='buy',quantity=1 if engine.strategy=='etf' else .001,limit=round(q['ask'],2)))
                result['permissions'] = 'preflight passed; execution still gated by market hours and reconciliation'
                if engine.strategy == 'etf':
                    result['direct_crypto_probe'] = engine.broker.crypto_capability()
                print(json.dumps(result))
            except Blocked as error:
                failed = True
                print(json.dumps(dict(strategy=engine.strategy,connected=False,reason=str(error))))
            except Exception:
                failed = True
                print(json.dumps(dict(strategy=engine.strategy,connected=False,reason='Connection/API check failed')))
        return 1 if failed else 0
    publisher = Publisher(experiment,store)
    for engine in engines:
        engine.before_submit = lambda s=engine.strategy: publisher.guard(s)
    while True:
        for engine in engines:
            try:
                publisher.acquire()
                publisher.command(engine)
                engine.step()
                publisher.publish(engine)
            except Exception:
                logging.error('Paper service cycle unavailable; verify Firestore credentials/connectivity and lease')
        brokers['etf'].wait(15)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Blocked as error:
        print(str(error))
        raise SystemExit(1)
