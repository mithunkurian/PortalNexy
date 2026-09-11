# Trading Backend

This service is the first authoritative backend publisher for NexyCapitals.

What it does now:

- Manages two persistent runtimes: `paper` and `live`
- Connects each runtime to IBKR through `ib_insync`
- Polls account, position, order, and fill state per runtime
- Writes normalized runtime state into Firestore under `runtimes/{runtimeId}/...`
- Consumes runtime control commands from the portal like `connect`, `disconnect`, `pause`, `resume`, and `stop`
- Publishes heartbeat and operational logs per runtime

What it does not do yet:

- Strategy scanning
- Order generation
- Hard execution/risk pipeline for new trades
- Backtest execution

## Run

Install dependencies:

```powershell
pip install -r trading_backend/requirements.txt
```

Set environment variables from `.env.example`, then start:

```powershell
python trading_backend/service.py
```

For UI development without IBKR, set `PAPER_USE_MOCK_BROKER=true` and/or `LIVE_USE_MOCK_BROKER=true`.
