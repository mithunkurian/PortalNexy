# Forward Paper Service

The supported service is `python -m trading_backend.forward.service` from the repository root.
It runs only the new ETF and direct BTC/ETH forward paper experiments.
Legacy live, backtest and simulated broker workflows are retired; historical data remains untouched.

See [the root README](../README.md) for versioned rules, Windows setup, exact paper account allowlists,
read-only preflight, start/pause/resume behavior, tests, accounting limitations and recovery.
See [the storage schema](../docs/forward-paper-storage.md) for the new isolated Firestore and SQLite records.

Use `.env.example` to create the ignored `.env.forward`. The legacy `.env` is not read.
No connection or unattended operation is implied by installing this code.
