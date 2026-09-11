from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from trading_backend.common import utc_now
from trading_backend.models import RuntimeConfig


class AuditLogger:
    def __init__(self, config: RuntimeConfig) -> None:
        default_path = Path(__file__).resolve().parent.parent / "state" / f"{config.runtime_id}.sqlite3"
        self.db_path = Path(config.sqlite_path) if config.sqlite_path else default_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.conn.executescript(
            """
            create table if not exists runtime_events (
              id integer primary key autoincrement,
              ts_utc text not null,
              runtime_id text not null,
              category text not null,
              event_type text not null,
              level text not null,
              symbol text,
              order_id text,
              parent_order_id text,
              trade_id text,
              message text not null,
              detail_json text
            );
            create table if not exists session_state (
              key text primary key,
              value_json text not null,
              updated_at_utc text not null
            );
            create table if not exists risk_checks (
              id integer primary key autoincrement,
              ts_utc text not null,
              runtime_id text not null,
              symbol text,
              passed integer not null,
              reason text not null,
              checks_json text not null
            );
            create table if not exists backtest_runs (
              id integer primary key autoincrement,
              run_id text not null unique,
              ts_utc text not null,
              runtime_id text not null,
              strategy text not null,
              period text not null,
              return_pct real not null,
              sharpe real not null,
              max_dd real not null,
              trades integer not null,
              win_rate_pct real not null,
              status text not null,
              notes text,
              symbols_tested integer not null,
              payload_json text not null
            );
            create table if not exists research_loops (
              id integer primary key autoincrement,
              loop_id text not null unique,
              ts_utc text not null,
              runtime_id text not null,
              family_id text not null,
              strategy_key text not null,
              result text not null,
              strategy_score real not null,
              annual_return_pct real not null,
              return_pct real not null,
              max_drawdown_pct real not null,
              sharpe real not null,
              trades integer not null,
              win_rate_pct real not null,
              target_met integer not null,
              decision text not null,
              new_strategy_id text,
              payload_json text not null
            );
            """
        )
        self.conn.commit()

    def log_event(
        self,
        runtime_id: str,
        category: str,
        event_type: str,
        level: str,
        message: str,
        detail: dict[str, Any] | None = None,
        symbol: str | None = None,
        order_id: str | None = None,
        parent_order_id: str | None = None,
        trade_id: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            insert into runtime_events (
              ts_utc, runtime_id, category, event_type, level, symbol, order_id, parent_order_id, trade_id, message, detail_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                utc_now().isoformat(),
                runtime_id,
                category,
                event_type,
                level,
                symbol,
                order_id,
                parent_order_id,
                trade_id,
                message,
                json.dumps(detail or {}, default=str),
            ),
        )
        self.conn.commit()

    def log_risk_check(self, runtime_id: str, symbol: str | None, passed: bool, reason: str, checks: dict[str, Any]) -> None:
        self.conn.execute(
            "insert into risk_checks (ts_utc, runtime_id, symbol, passed, reason, checks_json) values (?, ?, ?, ?, ?, ?)",
            (utc_now().isoformat(), runtime_id, symbol, int(passed), reason, json.dumps(checks, default=str)),
        )
        self.conn.commit()

    def save_state(self, key: str, value: dict[str, Any]) -> None:
        self.conn.execute(
            """
            insert into session_state (key, value_json, updated_at_utc)
            values (?, ?, ?)
            on conflict(key) do update set value_json=excluded.value_json, updated_at_utc=excluded.updated_at_utc
            """,
            (key, json.dumps(value, default=str), utc_now().isoformat()),
        )
        self.conn.commit()

    def load_state(self, key: str) -> dict[str, Any] | None:
        row = self.conn.execute("select value_json from session_state where key = ?", (key,)).fetchone()
        if not row:
            return None
        return json.loads(row["value_json"])

    def recent_events(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "select ts_utc, category, event_type, level, symbol, order_id, trade_id, message, detail_json from runtime_events order by id desc limit ?",
            (limit,),
        ).fetchall()
        return [
            {
                "timestamp": row["ts_utc"],
                "category": row["category"],
                "event_type": row["event_type"],
                "level": row["level"],
                "symbol": row["symbol"],
                "order_id": row["order_id"],
                "trade_id": row["trade_id"],
                "message": row["message"],
                "detail": json.loads(row["detail_json"] or "{}"),
            }
            for row in rows
        ]

    def save_backtest_run(self, payload: dict[str, Any]) -> None:
        self.conn.execute(
            """
            insert into backtest_runs (
              run_id, ts_utc, runtime_id, strategy, period, return_pct, sharpe, max_dd, trades, win_rate_pct, status, notes, symbols_tested, payload_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(run_id) do update set
              ts_utc=excluded.ts_utc,
              runtime_id=excluded.runtime_id,
              strategy=excluded.strategy,
              period=excluded.period,
              return_pct=excluded.return_pct,
              sharpe=excluded.sharpe,
              max_dd=excluded.max_dd,
              trades=excluded.trades,
              win_rate_pct=excluded.win_rate_pct,
              status=excluded.status,
              notes=excluded.notes,
              symbols_tested=excluded.symbols_tested,
              payload_json=excluded.payload_json
            """,
            (
                payload["run_id"],
                payload["timestamp"],
                payload["runtime_id"],
                payload["strategy"],
                payload["period"],
                payload["return_pct"],
                payload["sharpe"],
                payload["max_dd"],
                payload["trades"],
                payload["win_rate_pct"],
                payload["status"],
                payload.get("notes"),
                payload.get("symbols_tested", 0),
                json.dumps(payload, default=str),
            ),
        )
        self.conn.commit()

    def clear_backtest_runs(self, runtime_id: str) -> None:
        self.conn.execute("delete from backtest_runs where runtime_id = ?", (runtime_id,))
        self.conn.commit()

    def save_research_loop(self, runtime_id: str, payload: dict[str, Any]) -> None:
        self.conn.execute(
            """
            insert into research_loops (
              loop_id, ts_utc, runtime_id, family_id, strategy_key, result, strategy_score,
              annual_return_pct, return_pct, max_drawdown_pct, sharpe, trades, win_rate_pct,
              target_met, decision, new_strategy_id, payload_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(loop_id) do update set
              ts_utc=excluded.ts_utc,
              runtime_id=excluded.runtime_id,
              family_id=excluded.family_id,
              strategy_key=excluded.strategy_key,
              result=excluded.result,
              strategy_score=excluded.strategy_score,
              annual_return_pct=excluded.annual_return_pct,
              return_pct=excluded.return_pct,
              max_drawdown_pct=excluded.max_drawdown_pct,
              sharpe=excluded.sharpe,
              trades=excluded.trades,
              win_rate_pct=excluded.win_rate_pct,
              target_met=excluded.target_met,
              decision=excluded.decision,
              new_strategy_id=excluded.new_strategy_id,
              payload_json=excluded.payload_json
            """,
            (
                payload["loop_id"],
                payload["timestamp"],
                runtime_id,
                payload["family_id"],
                payload["strategy_key"],
                payload["result"],
                payload["strategy_score"],
                payload["annual_return_pct"],
                payload["return_pct"],
                payload["max_drawdown_pct"],
                payload["sharpe"],
                payload["trades"],
                payload["win_rate_pct"],
                int(bool(payload["target_met"])),
                payload["decision"],
                payload.get("new_strategy_id"),
                json.dumps(payload, default=str),
            ),
        )
        self.conn.commit()
