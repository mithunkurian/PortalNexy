from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from trading_backend.common import log, safe_float, utc_now
from trading_backend.models import BrokerSnapshot

try:
    from ib_insync import IB, MarketOrder, Stock, StopOrder  # type: ignore
except Exception:  # pragma: no cover
    IB = None
    MarketOrder = None
    Stock = None
    StopOrder = None


class BrokerAdapter:
    def connect(self) -> None:
        raise NotImplementedError

    def disconnect(self) -> None:
        raise NotImplementedError

    def get_snapshot(self) -> BrokerSnapshot:
        raise NotImplementedError

    def cancel_all_orders(self) -> dict[str, Any]:
        raise NotImplementedError

    def cancel_entry_orders(self) -> dict[str, Any]:
        raise NotImplementedError

    def close_all_positions(self) -> dict[str, Any]:
        raise NotImplementedError

    def fetch_daily_bars(self, symbol: str, lookback_days: int = 260) -> list[dict[str, Any]]:
        raise NotImplementedError

    def fetch_quote(self, symbol: str) -> dict[str, Any]:
        raise NotImplementedError

    def fetch_intraday_bars(self, symbol: str, trading_day) -> list[dict[str, Any]]:
        raise NotImplementedError

    def fetch_intraday_bars_range(self, symbol: str, start_day, end_day, bar_size: str = "1 min") -> list[dict[str, Any]]:
        raise NotImplementedError

    def submit_stop_entry(self, symbol: str, quantity: int, stop_price: float) -> dict[str, Any]:
        raise NotImplementedError

    def submit_protective_stop(self, symbol: str, quantity: int, stop_price: float) -> dict[str, Any]:
        raise NotImplementedError

    def submit_market_exit(self, symbol: str, action: str, quantity: int) -> dict[str, Any]:
        raise NotImplementedError


class MockBrokerAdapter(BrokerAdapter):
    def __init__(self, runtime_id: str) -> None:
        self.runtime_id = runtime_id
        self.connected = False

    def connect(self) -> None:
        self.connected = True
        log(f"{self.runtime_id}: mock broker connected.")

    def disconnect(self) -> None:
        self.connected = False

    def get_snapshot(self) -> BrokerSnapshot:
        return BrokerSnapshot(
            connected=self.connected,
            account={
                "net_liquidation": 1000.0,
                "cash": 1000.0,
                "buying_power": 1000.0,
                "unrealised_pnl": 0.0,
                "realised_pnl": 0.0,
                "today_pnl": 0.0,
                "today_pnl_pct": 0.0,
                "week_pnl": 0.0,
                "month_pnl": 0.0,
                "fees_today": 0.0,
                "fees_month": 0.0,
                "total_fees": 0.0,
                "total_trades": 0,
                "win_rate_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "total_market_value": 0.0,
                "currency": "USD",
            },
        )

    def cancel_all_orders(self) -> dict[str, Any]:
        return {"cancelled_orders": 0}

    def cancel_entry_orders(self) -> dict[str, Any]:
        return {"cancelled_orders": 0}

    def close_all_positions(self) -> dict[str, Any]:
        return {"submitted_close_orders": 0}

    def fetch_daily_bars(self, symbol: str, lookback_days: int = 260) -> list[dict[str, Any]]:
        return []

    def fetch_quote(self, symbol: str) -> dict[str, Any]:
        return {"last": 100.0, "bid": 99.95, "ask": 100.05, "timestamp": utc_now()}

    def fetch_intraday_bars(self, symbol: str, trading_day) -> list[dict[str, Any]]:
        return []

    def fetch_intraday_bars_range(self, symbol: str, start_day, end_day, bar_size: str = "1 min") -> list[dict[str, Any]]:
        return []

    def submit_stop_entry(self, symbol: str, quantity: int, stop_price: float) -> dict[str, Any]:
        return {"order_id": f"mock-entry-{uuid4().hex[:10]}", "symbol": symbol, "quantity": quantity, "stop_price": stop_price, "status": "SUBMITTED"}

    def submit_protective_stop(self, symbol: str, quantity: int, stop_price: float) -> dict[str, Any]:
        return {"order_id": f"mock-stop-{uuid4().hex[:10]}", "symbol": symbol, "quantity": quantity, "stop_price": stop_price, "status": "SUBMITTED"}

    def submit_market_exit(self, symbol: str, action: str, quantity: int) -> dict[str, Any]:
        return {"order_id": f"mock-exit-{uuid4().hex[:10]}", "symbol": symbol, "quantity": quantity, "status": "SUBMITTED"}


class IBKRBrokerAdapter(BrokerAdapter):
    def __init__(self, runtime_id: str) -> None:
        if IB is None:
            raise RuntimeError("ib_insync is not installed.")
        self.runtime_id = runtime_id
        self.ib = IB()
        prefix = runtime_id.upper()
        self.host = os.getenv(f"{prefix}_IBKR_HOST", os.getenv("IBKR_HOST", "127.0.0.1"))
        self.port = int(os.getenv(f"{prefix}_IBKR_PORT", os.getenv("IBKR_PORT", "7497" if runtime_id == "paper" else "7496")))
        self.client_id = int(os.getenv(f"{prefix}_IBKR_CLIENT_ID", "19" if runtime_id == "paper" else "29"))

    def _ensure_connected(self) -> None:
        if not self.ib.isConnected():
            self.connect()

    def _stock(self, symbol: str, currency: str = "USD"):
        if Stock is None:
            raise RuntimeError("ib_insync Stock helper is unavailable.")
        contract = Stock(symbol, "SMART", currency)
        self.ib.qualifyContracts(contract)
        return contract

    def connect(self) -> None:
        if not self.ib.isConnected():
            self.ib.connect(self.host, self.port, clientId=self.client_id, readonly=False)
        log(f"{self.runtime_id}: connected to IBKR at {self.host}:{self.port} with client id {self.client_id}.")

    def disconnect(self) -> None:
        if self.ib.isConnected():
            self.ib.disconnect()

    def get_snapshot(self) -> BrokerSnapshot:
        if not self.ib.isConnected():
            return BrokerSnapshot(connected=False)
        summary_items = self.ib.accountSummary()
        positions = self.ib.positions()
        open_trades = self.ib.openTrades()
        fills = self.ib.fills()
        summary_map: dict[str, Any] = {}
        for item in summary_items:
            summary_map[item.tag] = safe_float(item.value, default=item.value)
        position_rows: list[dict[str, Any]] = []
        total_market_value = 0.0
        total_unrealised = 0.0
        for pos in positions:
            symbol = getattr(pos.contract, "symbol", "UNKNOWN")
            market_price = safe_float(getattr(pos, "marketPrice", 0.0))
            market_value = safe_float(getattr(pos, "marketValue", market_price * safe_float(pos.position)))
            unrealised = safe_float(getattr(pos, "unrealizedPNL", 0.0))
            total_market_value += market_value
            total_unrealised += unrealised
            position_rows.append(
                {
                    "symbol": symbol,
                    "side": "LONG" if safe_float(pos.position) >= 0 else "SHORT",
                    "quantity": safe_float(pos.position),
                    "avg_cost": safe_float(getattr(pos, "avgCost", 0.0)),
                    "market_price": market_price,
                    "market_value": market_value,
                    "unrealised_pnl": unrealised,
                    "stop_price": None,
                    "entry_date": None,
                    "age": "Live",
                    "sector": None,
                }
            )
        order_rows: list[dict[str, Any]] = []
        for trade in open_trades:
            contract = trade.contract
            order = trade.order
            order_rows.append(
                {
                    "order_id": str(order.orderId),
                    "symbol": getattr(contract, "symbol", "UNKNOWN"),
                    "action": getattr(order, "action", None),
                    "quantity": safe_float(getattr(order, "totalQuantity", 0.0)),
                    "order_type": getattr(order, "orderType", None),
                    "limit_price": safe_float(getattr(order, "lmtPrice", 0.0)),
                    "aux_price": safe_float(getattr(order, "auxPrice", 0.0)),
                    "status": str(getattr(trade.orderStatus, "status", "UNKNOWN")).upper(),
                    "timestamp": utc_now(),
                }
            )
        trade_rows: list[dict[str, Any]] = []
        total_commissions = 0.0
        winning_trades = 0
        closed_trade_count = 0
        for fill in fills:
            execution = fill.execution
            commission = safe_float(getattr(fill.commissionReport, "commission", 0.0))
            total_commissions += commission
            pnl = safe_float(getattr(fill.commissionReport, "realizedPNL", 0.0))
            if pnl > 0:
                winning_trades += 1
            closed_trade_count += 1
            exec_time = execution.time
            exec_time = exec_time.replace(tzinfo=timezone.utc) if exec_time.tzinfo is None else exec_time.astimezone(timezone.utc)
            trade_rows.append(
                {
                    "execution_id": execution.execId,
                    "symbol": getattr(fill.contract, "symbol", "UNKNOWN"),
                    "action": execution.side,
                    "quantity": safe_float(execution.shares),
                    "fill_price": safe_float(execution.price),
                    "pnl": pnl,
                    "commission": commission,
                    "timestamp": exec_time,
                }
            )
        net_liq = safe_float(summary_map.get("NetLiquidation"))
        realized = safe_float(summary_map.get("RealizedPnL"))
        unrealized = safe_float(summary_map.get("UnrealizedPnL"), default=total_unrealised)
        today_pnl = realized + unrealized
        today_pnl_pct = (today_pnl / net_liq * 100.0) if net_liq else 0.0
        win_rate = (winning_trades / closed_trade_count * 100.0) if closed_trade_count else 0.0
        return BrokerSnapshot(
            connected=True,
            account={
                "net_liquidation": net_liq,
                "cash": safe_float(summary_map.get("TotalCashValue")),
                "buying_power": safe_float(summary_map.get("BuyingPower")),
                "unrealised_pnl": unrealized,
                "realised_pnl": realized,
                "today_pnl": today_pnl,
                "today_pnl_pct": today_pnl_pct,
                "week_pnl": 0.0,
                "month_pnl": 0.0,
                "fees_today": total_commissions,
                "fees_month": total_commissions,
                "total_fees": total_commissions,
                "total_trades": closed_trade_count,
                "win_rate_pct": win_rate,
                "max_drawdown_pct": 0.0,
                "total_market_value": total_market_value,
                "currency": "USD",
            },
            positions=position_rows,
            orders=order_rows,
            trades=trade_rows,
        )

    def cancel_all_orders(self) -> dict[str, Any]:
        if not self.ib.isConnected():
            return {"cancelled_orders": 0}
        open_trades = self.ib.openTrades()
        cancelled = 0
        try:
            self.ib.reqGlobalCancel()
        except Exception:
            pass
        for trade in open_trades:
            try:
                self.ib.cancelOrder(trade.order)
                cancelled += 1
            except Exception:
                continue
        if cancelled:
            self.ib.sleep(1.0)
        return {"cancelled_orders": cancelled}

    def cancel_entry_orders(self) -> dict[str, Any]:
        if not self.ib.isConnected():
            return {"cancelled_orders": 0}
        cancelled = 0
        for trade in self.ib.openTrades():
            try:
                if str(getattr(trade.order, "action", "")).upper() == "BUY":
                    self.ib.cancelOrder(trade.order)
                    cancelled += 1
            except Exception:
                continue
        if cancelled:
            self.ib.sleep(1.0)
        return {"cancelled_orders": cancelled}

    def close_all_positions(self) -> dict[str, Any]:
        if not self.ib.isConnected():
            return {"submitted_close_orders": 0}
        if MarketOrder is None or Stock is None:
            raise RuntimeError("ib_insync order helpers are unavailable.")
        submitted = 0
        for pos in self.ib.positions():
            qty = safe_float(pos.position)
            if qty == 0:
                continue
            action = "SELL" if qty > 0 else "BUY"
            symbol = getattr(pos.contract, "symbol", "UNKNOWN")
            currency = getattr(pos.contract, "currency", "USD") or "USD"
            try:
                contract = self._stock(symbol, currency)
                order = MarketOrder(action, abs(qty))
                order.tif = "DAY"
                order.outsideRth = True
                self.ib.placeOrder(contract, order)
                submitted += 1
                log(f"{self.runtime_id}: flatten submitted {action} {abs(qty)} {symbol}.")
            except Exception as exc:
                log(f"{self.runtime_id}: flatten failed for {symbol}: {exc}")
        if submitted:
            self.ib.sleep(0.5)
        return {"submitted_close_orders": submitted}

    def fetch_daily_bars(self, symbol: str, lookback_days: int = 260) -> list[dict[str, Any]]:
        self._ensure_connected()
        contract = self._stock(symbol)
        duration_str = f"{max(lookback_days, 30)} D"
        if lookback_days > 365:
            years = max(2, (lookback_days + 251) // 252)
            duration_str = f"{years} Y"
        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr=duration_str,
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
        )
        rows: list[dict[str, Any]] = []
        for bar in bars:
            bar_date = bar.date.date() if hasattr(bar.date, "date") else datetime.fromisoformat(str(bar.date)).date()
            rows.append({"date": bar_date, "open": safe_float(bar.open), "high": safe_float(bar.high), "low": safe_float(bar.low), "close": safe_float(bar.close), "volume": safe_float(bar.volume)})
        return rows

    def fetch_quote(self, symbol: str) -> dict[str, Any]:
        self._ensure_connected()
        contract = self._stock(symbol)
        ticker = self.ib.reqMktData(contract, "", False, False)
        self.ib.sleep(1.0)
        quote = {
            "last": safe_float(getattr(ticker, "last", 0.0), safe_float(getattr(ticker, "close", 0.0))),
            "bid": safe_float(getattr(ticker, "bid", 0.0)),
            "ask": safe_float(getattr(ticker, "ask", 0.0)),
            "timestamp": utc_now(),
        }
        self.ib.cancelMktData(contract)
        return quote

    def fetch_intraday_bars(self, symbol: str, trading_day) -> list[dict[str, Any]]:
        self._ensure_connected()
        contract = self._stock(symbol)
        end_dt = datetime.combine(trading_day + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime=end_dt.strftime("%Y%m%d %H:%M:%S UTC"),
            durationStr="2 D",
            barSizeSetting="1 min",
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
        )
        rows: list[dict[str, Any]] = []
        for bar in bars:
            bar_dt = bar.date
            if isinstance(bar_dt, str):
                try:
                    bar_dt = datetime.strptime(bar_dt, "%Y%m%d  %H:%M:%S")
                except ValueError:
                    bar_dt = datetime.fromisoformat(bar_dt)
            if bar_dt.tzinfo is None:
                bar_dt = bar_dt.replace(tzinfo=timezone.utc)
            rows.append(
                {
                    "timestamp": bar_dt,
                    "open": safe_float(bar.open),
                    "high": safe_float(bar.high),
                    "low": safe_float(bar.low),
                    "close": safe_float(bar.close),
                    "volume": safe_float(bar.volume),
                }
            )
        return rows

    def fetch_intraday_bars_range(self, symbol: str, start_day, end_day, bar_size: str = "1 min") -> list[dict[str, Any]]:
        self._ensure_connected()
        contract = self._stock(symbol)
        rows: list[dict[str, Any]] = []
        current_end = end_day
        seen: set[tuple[datetime, float, float, float, float, float]] = set()
        chunk_days = 6 if bar_size == "1 min" else 29
        duration_str = "7 D" if bar_size == "1 min" else "30 D"

        while current_end >= start_day:
            chunk_start = max(start_day, current_end - timedelta(days=chunk_days))
            end_dt = datetime.combine(current_end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_dt.strftime("%Y%m%d %H:%M:%S UTC"),
                durationStr=duration_str,
                barSizeSetting=bar_size,
                whatToShow="TRADES",
                useRTH=True,
                formatDate=1,
            )
            for bar in bars:
                bar_dt = bar.date
                if isinstance(bar_dt, str):
                    try:
                        bar_dt = datetime.strptime(bar_dt, "%Y%m%d  %H:%M:%S")
                    except ValueError:
                        bar_dt = datetime.fromisoformat(bar_dt)
                if bar_dt.tzinfo is None:
                    bar_dt = bar_dt.replace(tzinfo=timezone.utc)
                key = (
                    bar_dt,
                    safe_float(bar.open),
                    safe_float(bar.high),
                    safe_float(bar.low),
                    safe_float(bar.close),
                    safe_float(bar.volume),
                )
                bar_day = bar_dt.astimezone(timezone.utc).date()
                if chunk_start <= bar_day <= end_day and key not in seen:
                    rows.append(
                        {
                            "timestamp": bar_dt,
                            "open": key[1],
                            "high": key[2],
                            "low": key[3],
                            "close": key[4],
                            "volume": key[5],
                        }
                    )
                    seen.add(key)
            current_end = chunk_start - timedelta(days=1)
        rows.sort(key=lambda row: row["timestamp"])
        return rows

    def submit_stop_entry(self, symbol: str, quantity: int, stop_price: float) -> dict[str, Any]:
        if StopOrder is None:
            raise RuntimeError("ib_insync StopOrder helper is unavailable.")
        contract = self._stock(symbol)
        order = StopOrder("BUY", quantity, stop_price)
        order.tif = "DAY"
        order.outsideRth = True
        trade = self.ib.placeOrder(contract, order)
        self.ib.sleep(0.5)
        return {"order_id": str(getattr(trade.order, "orderId", "")), "symbol": symbol, "quantity": quantity, "stop_price": stop_price, "status": str(getattr(trade.orderStatus, 'status', 'SUBMITTED')).upper()}

    def submit_protective_stop(self, symbol: str, quantity: int, stop_price: float) -> dict[str, Any]:
        if StopOrder is None:
            raise RuntimeError("ib_insync StopOrder helper is unavailable.")
        contract = self._stock(symbol)
        order = StopOrder("SELL", quantity, stop_price)
        order.tif = "GTC"
        order.outsideRth = True
        trade = self.ib.placeOrder(contract, order)
        self.ib.sleep(0.5)
        return {"order_id": str(getattr(trade.order, "orderId", "")), "symbol": symbol, "quantity": quantity, "stop_price": stop_price, "status": str(getattr(trade.orderStatus, 'status', 'SUBMITTED')).upper()}

    def submit_market_exit(self, symbol: str, action: str, quantity: int) -> dict[str, Any]:
        if MarketOrder is None:
            raise RuntimeError("ib_insync MarketOrder helper is unavailable.")
        contract = self._stock(symbol)
        order = MarketOrder(action, quantity)
        order.tif = "DAY"
        order.outsideRth = True
        trade = self.ib.placeOrder(contract, order)
        self.ib.sleep(0.5)
        return {"order_id": str(getattr(trade.order, "orderId", "")), "symbol": symbol, "quantity": quantity, "status": str(getattr(trade.orderStatus, 'status', 'SUBMITTED')).upper()}
