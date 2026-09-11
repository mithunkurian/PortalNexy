# NexyCapitals Trading Firestore Schema

This repository now treats Firestore as the portal read model for the trading system.

## Product boundary

- The portal is a trading operations cockpit.
- The trading backend is the only system that should publish broker, portfolio, and risk state.
- The frontend may issue control intents, but it should not compute or invent trading state.
- The legacy `agents/` subsystem is retained only as historical reference and is not part of the trading architecture.

## Runtimes

The system now uses persistent server-side runtimes rather than a single global mode toggle.

Examples:

- `runtimes/paper/...`
- `runtimes/live/...`

These are not browser sessions. They are durable backend-owned operating lanes.

## Runtime collections

### `runtimes/{runtimeId}/system/status`

- `runtime_id`: `paper` or `live`
- `runtime_label`
- `bot_state`: `RUNNING`, `PAUSED`, or `STOPPED`
- `desired_connection`: boolean
- `ibkr_connected`: boolean
- `strategy_name`
- `bot_version`
- `open_positions_count`
- `pending_orders_count`
- `last_heartbeat`
- `updated_at`

### `runtimes/{runtimeId}/control/current`

- `action`: `connect`, `disconnect`, `pause`, `stop`, or `resume`
- `issued_at`
- `acknowledged_at`
- `processed_by`

### `runtimes/{runtimeId}/finance/account`

- `net_liquidation`
- `cash`
- `buying_power`
- `unrealised_pnl`
- `realised_pnl`
- `today_pnl`
- `today_pnl_pct`
- `week_pnl`
- `month_pnl`
- `fees_today`
- `fees_month`
- `total_fees`
- `total_trades`
- `win_rate_pct`
- `max_drawdown_pct`
- `updated_at`

### `runtimes/{runtimeId}/risk/state`

- `daily_pnl_pct`
- `open_risk_pct`
- `exposure_pct`
- `max_dd_pct`
- `open_positions`
- `trades_today`
- `updated_at`

### `runtimes/{runtimeId}/positions/{symbol}`

- `symbol`
- `side`
- `quantity`
- `avg_cost`
- `market_price`
- `market_value`
- `unrealised_pnl`
- `stop_price`
- `entry_date`
- `age`
- `updated_at`

### `runtimes/{runtimeId}/orders/{order_id}`

- `symbol`
- `action`
- `quantity`
- `order_type`
- `limit_price`
- `aux_price`
- `status`
- `timestamp`
- `updated_at`

### `runtimes/{runtimeId}/trades/{execution_id}`

- `symbol`
- `action`
- `quantity`
- `fill_price`
- `pnl`
- `commission`
- `timestamp`

### `runtimes/{runtimeId}/backtests/{run_id}`

Reserved for the backtesting service.

### `runtimes/{runtimeId}/logs/{event_id}`

- `category`: `info`, `order`, `risk`, `error`, `ai`
- `level`: `info`, `warn`, `error`
- `message`
- `detail`
- `source`
- `timestamp`

### `todos/{todo_id}`

Portal-managed project tracking.
