# Forward paper storage and operator boundaries

The service owns `trading_backend/state/forward-<experiment>.sqlite3` (WAL/FULL) and
the separate Firestore namespace below. It does not import or mutate historical
`runtimes/live`, `runtimes/paper`, `paper.sqlite3` or `live.sqlite3` records.

| Firestore path | Writer | Purpose |
|---|---|---|
| `forward/current` | Service | Current experiment pointer and heartbeat |
| `forwardExperiments/{id}/strategies/{etf,crypto}` | Service | Frozen configuration, inception, valuation, latest orders/fills/events, 500 samples |
| `forwardExperiments/{id}/commands/{etf,crypto}` | Authenticated founder | Request ID, action (start/pause/resume), server timestamp only |
| `forwardExperiments/{id}/service/lease` | Service transaction | Owner, ledger identity, expiry |
| `forwardExperiments/{id}/service/summary` | Service | Combined allocation metrics and full-history drawdown |
| `forwardExperiments/{id}/journal/{eventId}` | Service | Persistent signals, order intentions, status, fills, errors and missed cycles |
| `forwardExperiments/{id}/history/{strategy_timestamp}` | Service | Forward-only observed equity/reference history |

Browser writes to portfolios, fills, strategy settings and historical controls are
denied by the new rules. Firebase Admin bypasses rules; keep its credentials on the
service machine. Changing this code does not update already-deployed Firestore rules.

SQLite tables: `kv` (frozen strategy state, cycle decisions, mirror cursors, ledger
identity), `orders` (stable order references and broker receipt/state), `fills`
(unique execution IDs), `events` (append-only decisions), `history` (five-minute
observations), `commands` (processed request IDs). Firestore mirroring is retried
from persisted cursors; no broker submission depends on a successful mirror write.
Submission DOES require a valid Firestore lease and a final pause check.

For backups use SQLite's backup API or stop the service and copy the database and
associated WAL/SHM files together. Keep the same experiment ID, rule version,
account IDs, capital and ledger. A missing local ledger is an operator issue,
not permission to recreate starting balances. The full broker statement remains
the authority if execution retention no longer covers an outage. This release has
no automatic statement-import or unexplained cash-adjustment workflow; it blocks
rather than inventing attribution. Dividends, interest, transfers, manual trades,
corporate actions, corrected executions and missing fees require reconciliation.

Account clean-start enforcement intentionally leaves old orders and holdings
untouched. Pause also leaves all outstanding orders and holdings untouched. DAY
or IOC expiry is performed by the broker according to the order's original TIF.
The engine never sends cancellation or liquidation requests as cleanup.

IBKR direct crypto contract discovery and what-if probes are informational, not
proof of paper execution support. The explicit crypto adapter is Alpaca paper;
the actual account's permission and data checks are still required. No automatic
crypto ETF substitution exists.
