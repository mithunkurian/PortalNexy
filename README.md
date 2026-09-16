# PortalNexy — forward paper experiments

ETF rotation on an explicitly allowlisted IBKR paper account and direct BTC/ETH momentum on an explicitly allowlisted Alpaca paper account. The existing navy/white portal, login, management pages, todos and chat remain. Old roadmap/design content is labeled as historical reference.

**The portal and Firestore rules have been deployed. Broker connectivity has been checked read-only; forward strategy execution and unattended operation are not yet verified. No Windows service task has been installed.**

## Implemented components

- `trading_backend/forward/`: paper-only service, adapters, frozen rules, durable SQLite order/fill ledger, scheduler and Firestore publisher.
- `index.html`, `forward.js`, `forward.css`: combined and per-strategy equity, cash, positions, net realised/unrealised P&L, costs, drawdown, actual equity history, buy-and-hold references, account/connection status, timestamps, schedules, orders, fills and decisions.
- `portal-management.js`, `portal-auth.js`: retained management and login. Firebase web configuration is public client configuration; broker keys and service-account secrets never enter browser assets.
- `trading_backend/app.py` and `python -m trading_backend.service` route only to the new service. Legacy worker/execution/IBKR classes fail closed. Old backtest, optimiser and strategy workflows are removed. The new service has no live-order or order-cancellation implementation.
- Historical Firestore `runtimes/*`, old SQLite databases, ignored research files and credentials are untouched. The new experiment reads none of their performance history.

## Dashboard

`dashboard.js` presents a compact overview with KPIs above an equity chart and account status. A single detail panel switches between active trades, waiting orders and fills, with five rows per page and one expanded record at a time. Asset, side and status filters affect this panel; strategy and time selectors control the overview. It provides Today, This Week, This Month, Last 30 Days and All Time filters, plus strategy selection. Dates use UTC, and weeks start Monday. Current attributed positions and waiting orders remain visible regardless of the date filter; stale snapshots are explicitly labelled and excluded from current totals.

Activity totals come from the complete SQLite experiment ledger, published to `forwardExperiments/{experiment}/service/dashboard`. Confirmed executions are mirrored idempotently to the experiment's `fills` collection, including later commission and order-status updates. The browser reads 100 records at a time; Load more retrieves older records, and the page states how many records are loaded before applying the strategy filter. New fill counts automatically reload the archive; Refresh fills also retrieves commission/status corrections. Totals update with service snapshots; fill tables show their last read time. Partial fills count as executions, and executed value is turnover, not P&L. Submission attempts include uncertain broker submissions. Neither historical simulations nor pre-inception records are included.

Deploy the UI bundle and run the updated Python service to populate this projection. Until the service publishes it, activity totals remain unavailable. The dashboard is read-only and does not start, cancel or modify orders.

## Versioned rules

These are new forward paper rules, not a reproduction or validation of an earlier backtest.

| | ETF rotation | Crypto momentum |
|---|---|---|
| Version | `etf-rotation-weekly-validation-1.0.0` | `crypto-momentum-1.0.0` |
| Universe | SPY, EFA, EEM, TLT, GLD, subject to verification | BTC/USD, ETH/USD, direct assets |
| Qualify | Positive 126-session momentum; close above 200-session SMA | Positive 90-day momentum; close above 200-day SMA |
| Select | Top two qualifying assets, equal target dollar weights | Strongest qualifying asset |
| Evaluate | First NYSE session close of each week + 5 minutes, temporary workflow-validation cadence | 00:05 UTC using the completed prior UTC day |
| Execute | Following NYSE session, open + 1 minute until close − 5 minutes | After evaluation, before next 00:05 UTC evaluation |
| Orders | Whole-share monitored DAY limits; regular hours only | Fractional monitored GTC limits |

Both hold cash if nothing qualifies. Ties use symbol order. Current attributed equity funds new targets, reinvesting profits, with a 98% exposure cap and 2% cash/fee reserve. No leverage, shorts, fixed return requirement or drawdown rejection threshold. Quote age must be at most 60 seconds and spread at most 1%; delayed, missing or future-dated quotes block orders. Deltas below $5 are left as cash/dust. ETF quantities round down to whole shares; crypto to eight decimals, also subject to broker minimum/precision checks. Limits use current ask for buys and bid for sells, rounded to cents. Target quantities persist for the cycle. Sells precede buys, with confirmed fills/cash reconciled between orders. Partial terminal fills are not topped up in the same cycle.

The weekly ETF cadence is explicitly a temporary forward workflow test. After enough complete cycles validate scheduling, signals, orders, fills and reconciliation, return to monthly evaluation under a new frozen rule version; do not relabel weekly results as monthly-strategy results.

All candidates need complete 200-session/day warm-up and verified contracts. An unavailable ETF blocks the experiment with a reason; the service does not silently shrink the universe or substitute another asset. NYSE holidays/DST and IBKR contract liquid hours gate ETF execution. Inception requires fresh quotes. Start after an evaluation waits until the next scheduled evaluation. Historical prices are used only for indicators, never to backfill profits or fills.

## Account attribution and recovery

This version requires **clean, dedicated paper accounts**, one IBKR account for ETFs and one Alpaca account for crypto. Existing positions/open orders block inception without modifying them. Preserve the older account and records or independently arrange a clean account; this setup does not cancel orders or erase history. Allocations are strategy ledgers inside real broker accounts, not separate virtual broker accounts. Cash beyond each allocation remains unallocated inception cash and is excluded from performance. Combined totals require both strategies to have fresh, reconciled valuations; a missing strategy is not treated as zero.

Broker positions, cash, order states and execution IDs are authoritative. Fills are idempotent. Later IBKR commissions update the same execution; Alpaca FILL and CFEE/FEE activities are paginated, including fees deducted from acquired crypto. Costs remain provisional until reported. Average-cost accounting gives net realised and marked unrealised P&L. Allocated cash plus unallocated inception cash must match broker cash. Manual trades, transfers, distributions, corporate actions or incomplete fees halt new submissions pending reconciliation. This version does **not** automatically classify dividend/interest/transfer cash changes; it does not count unexplained cash as profit. Resolve discrepancies from broker statements, not by editing balances to bypass a gate.

Per-strategy drawdown uses inception observations; combined drawdown uses all matched five-minute observations since both strategies started. Charts show the latest 500 samples. Buy-and-hold references start from observed inception quotes: an equal-weight five-ETF basket and 50/50 BTC/ETH. References exclude fees and distributions, are not broker positions, and contain no historical simulated gains.

SQLite uses WAL and FULL durability. Each intention commits **before** broker submission. Stable experiment/strategy/cycle/symbol/side IDs prevent duplicates. If submission times out or a persisted order cannot be found, the strategy blocks instead of retrying automatically. Long outages may exceed broker execution-history retention; missing receipts require statement-assisted reconciliation. Preserve and back up the ledger. A local process lock plus Firestore ownership lease prevents concurrent engines; a ledger ID prevents an empty database from overwriting an existing experiment. Restore the original database to recover; never delete/rename it to bypass a gate.

Pause stops **new submissions only**. Holdings stay invested; outstanding orders stay active and may fill. Reconciliation continues while paused. Resume reconciles first; skipped evaluations wait for the next schedule. A pause cannot recall an order already accepted by the broker. A final pre-submit check checks the latest pause command and lease. Missed windows are logged; past-price fills are never invented. Browser and ChatGPT sessions do not run the engine.

Execution policy `marketable-limit-reprice-1.0.0` applies to both strategies. Crypto uses a GTC limit and ETFs use a regular-hours DAY limit. The service reconciles continuously and, while an unfilled remainder is open, may replace its limit no more than once per minute using a fresh broker quote. Buy limits cannot rise more than 1% above the initial limit; sell limits cannot fall more than 1% below it. Position sizing reserves this execution buffer in addition to the strategy's 2% cash reserve. The service cancels any remainder when its execution window expires: the daily crypto deadline or five minutes before the ETF session close. Every replacement intent and broker ID is durable, so restart recovery reconciles the full replacement chain before another action.

## Windows setup: first forward test

1. Stop any old **PortalNexy backend service/task** before starting this branch. Leave Gateway, holdings and broker orders alone. Do not run an older checkout concurrently. No matching PortalNexy Python process was found during the implementation's local process check.

2. In PowerShell:

   ```powershell
   cd C:\Users\Mithu\PortalNexy
   py -3.12 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r trading_backend\requirements.txt
   Copy-Item trading_backend\.env.example trading_backend\.env.forward
   ```

   If `.env.forward` exists, edit it instead of overwriting it. The service reads only this new configuration, never the old `.env`, `LIVE_*`, `PAPER_*` or mock settings.

3. Log into **IBKR paper** in TWS/Gateway and verify its actual `DU...` account identity. Enable socket API clients and API trading for that paper session, allow localhost, select an unused client ID, and check the configured port. Typical defaults are TWS paper 7497 and Gateway paper 4002; a port is not proof of paper identity. Verify USD cash, US ETF trading permissions and market-data subscriptions. Account/jurisdiction restrictions may prevent some ETFs; there is no automatic substitute.

4. Edit `.env.forward`: set `FORWARD_IB_ACCOUNT` and `FORWARD_IB_PAPER_ALLOWLIST` to the exact verified DU ID; `FORWARD_IB_PORT` and `FORWARD_IB_CLIENT_ID` to session settings; `FORWARD_ETF_USD` to your chosen positive allocation within actual USD cash. Set `FORWARD_FIREBASE_CREDENTIALS` to an absolute server-side service-account JSON path, preferably outside the repository, for the portal's Firebase project. Keep `FORWARD_EXPERIMENT=forward-v1` for this first experiment. Accounts, allocations, broker and rules freeze at inception.

5. Run the read-only broker preflight:

   ```powershell
   .\.venv\Scripts\python.exe -m trading_backend.forward.service --preflight --strategy etf
   ```

   This checks account identity, cash, contracts, quotes and what-if permissions without submitting orders. It also probes direct BTC/ETH contracts/what-if capability. What-if success alone does not certify paper execution. **This account's direct IBKR crypto support remains unverified until a connected check.** The shipped crypto route is explicitly Alpaca paper; no crypto ETFs or fabricated fills are substituted. IBKR reporting support does not automatically enable another execution path.

6. For crypto, enable an Alpaca **paper** account with direct crypto permission. Set paper API credentials in `FORWARD_ALPACA_KEY` and `FORWARD_ALPACA_SECRET`; set `FORWARD_ALPACA_ACCOUNT` and `FORWARD_ALPACA_PAPER_ALLOWLIST` to the exact account **UUID** returned by `/v2/account`; set `FORWARD_CRYPTO_USD` within USD cash. The adapter hardcodes the paper trading endpoint. Run:

   ```powershell
   .\.venv\Scripts\python.exe -m trading_backend.forward.service --preflight --strategy crypto
   ```

   ETF can operate independently while crypto awaits configuration. Start crypto only after its preflight passes.

7. Review and apply `firestore.rules` before browser controls work. Rules make historical runtimes read-only, deny client balance/fill writes and allow founder-authenticated start/pause/resume commands only. **No rules were deployed.** When you explicitly choose to apply them, run `firebase deploy --only firestore:rules`; hosting deployment is a separate decision.

8. Build/preview only public assets:

   ```powershell
   .\.venv\Scripts\python.exe tools\build_ui.py
   .\.venv\Scripts\python.exe -m http.server 8080 --bind 127.0.0.1 --directory public
   ```

   Open `http://localhost:8080`, authorize localhost in Firebase Auth if required, and use the existing founder login. The build copies only six public assets and refuses unexpected files in `public/`. Do not serve the repository root.

9. In another PowerShell window:

   ```powershell
   .\.venv\Scripts\python.exe -m trading_backend.forward.service
   ```

   In Paper Trading, inspect account identity, connection, quote times and errors. Click **Start experiment** for each configured strategy. Verify acknowledgement, inception and reconciliation. The first ETF order waits for the next monthly evaluation; crypto waits for the next daily evaluation. Verify the first order/fill independently in the paper broker account. Closing the browser or ChatGPT leaves the service running.

10. After connected verification, optionally register the background task:

    ```powershell
    .\tools\install-paper-service.ps1
    Start-ScheduledTask -TaskName 'PortalNexy Forward Paper'
    ```

    Stop the foreground service first. Registration does not start the task. It starts at user logon and restarts on failure; Windows must remain logged in, awake and online, with Gateway authenticated. Browser/ChatGPT may close. Gateway reauthentication remains an external prerequisite. No task was installed by this change. Verify first fill and restart reconciliation against the actual paper account before treating unattended operation as active.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools\build_ui.py
node --check forward.js
node --check portal-management.js
node --check portal-auth.js
```

Backend tests use isolated broker fixtures and temporary SQLite databases. `tests/ui.cjs` uses Playwright and installed Edge, with Firebase mocked **only inside the test**. Install Playwright for development (`npm install --no-save --package-lock=false playwright`) or use a bundled `NODE_PATH`, then run `node tests/ui.cjs`. Checks cover desktop/mobile layouts, management navigation, empty states and the exact new command path, without real Firestore writes. Offline tests do not verify real broker login, subscriptions, permissions, fills or deployed Firestore rules.

## Adapter references

- [IBKR paper accounts and limitations](https://www.ibkrguides.com/clientportal/aboutpapertradingaccounts.htm): account permissions/subscriptions and paper execution behavior.
- [IBKR API market data](https://www.interactivebrokers.com/campus/trading-lessons/python-receiving-market-data/): subscriptions and live/delayed data.
- [Alpaca crypto trading](https://docs.alpaca.markets/us/docs/crypto-trading): direct crypto, limit/IOC support, precision and asset-denominated fees.
- [Alpaca account activities](https://docs.alpaca.markets/us/docs/account-activities): FILL, CFEE and FEE reconciliation.
