from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import credentials, firestore

from trading_backend.common import is_firestore_quota_error, log
from trading_backend.models import RuntimeConfig
from trading_backend.runtime.worker import RuntimeWorker


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "trading_backend" / ".env")

RUNTIME_IDS = ("paper", "live")


class TradingBackendService:
    def __init__(self) -> None:
        self.poll_secs = int(os.getenv("POLL_SECS", "5"))
        self.db = self._init_firestore()
        self.workers = {
            runtime_id: RuntimeWorker(
                self.db,
                RuntimeConfig(
                    runtime_id=runtime_id,
                    strategy_name=os.getenv(f"{runtime_id.upper()}_STRATEGY_NAME", os.getenv("STRATEGY_NAME", f"NexyCapitals {runtime_id.title()} Swing v1.2")),
                    bot_version=os.getenv(f"{runtime_id.upper()}_BOT_VERSION", os.getenv("BOT_VERSION", "v1.2.0")),
                    use_mock_broker=os.getenv(f"{runtime_id.upper()}_USE_MOCK_BROKER", os.getenv("USE_MOCK_BROKER", "false")).lower() == "true",
                    poll_secs=self.poll_secs,
                    metadata_path=os.getenv(f"{runtime_id.upper()}_WATCHLIST_PATH"),
                    sqlite_path=os.getenv(f"{runtime_id.upper()}_SQLITE_PATH"),
                    backtest_lookback_days=int(os.getenv(f"{runtime_id.upper()}_BACKTEST_LOOKBACK_DAYS", os.getenv("BACKTEST_LOOKBACK_DAYS", "756"))),
                ),
            )
            for runtime_id in RUNTIME_IDS
        }

    def _init_firestore(self):
        service_account = os.getenv("FIREBASE_SERVICE_ACCOUNT", "../agents/serviceAccount.json")
        service_account_path = Path(service_account)
        if not service_account_path.is_absolute():
            service_account_path = (Path(__file__).resolve().parent / service_account_path).resolve()
        if not firebase_admin._apps:
            cred = credentials.Certificate(str(service_account_path))
            firebase_admin.initialize_app(cred)
        return firestore.client()

    def run(self) -> None:
        for runtime_id in self.workers:
            log(f"{runtime_id}: runtime worker ready.")
        while True:
            for runtime_id, worker in self.workers.items():
                try:
                    worker.process_control()
                    worker.publish()
                except Exception as exc:
                    log(f"{runtime_id}: loop error: {exc}")
                    if is_firestore_quota_error(exc):
                        time.sleep(max(self.poll_secs, 15))
                finally:
                    worker.flush_write_counts()
            time.sleep(self.poll_secs)

    def shutdown(self) -> None:
        for worker in self.workers.values():
            try:
                worker.broker.disconnect()
            except Exception:
                pass


def main() -> int:
    service = TradingBackendService()
    try:
        service.run()
    except KeyboardInterrupt:
        log("Stopping trading backend.")
        service.shutdown()
        return 0
    except Exception as exc:
        log(f"Fatal error: {exc}")
        service.shutdown()
        return 1


if __name__ == "__main__":
    sys.exit(main())
