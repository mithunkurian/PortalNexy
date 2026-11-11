# PortalNEXY · Nexy workspace

Founder workspace for Nexy, the autonomous trading unit. Overview and Development Journal present the NexyDAO tracker as a milestone map, searchable evidence timeline and expandable acceptance queue. Google sign-in remains restricted to the founder. Execution is disabled; the portal is informational.

## Refresh the journal

```powershell
python tools/sync_journal.py --repo C:\Users\Mithu\NexyDAO
python tools/build_ui.py
```

The documentation-only exporter reads `docs/development-tracker.md` from the selected NexyDAO checkout and records its revision and branch in `nexy-journal.js`. Confirm the checkout is clean and current before refreshing. The snapshot may include development branch work beyond main; it is not a live monitor. The exporter does not read runtime databases, account receipts or credentials. Hosting assets are publicly retrievable even though the interface requires sign-in; keep sensitive data out of the tracker/export.

## Validate

```powershell
python -m unittest discover -s tests -v
node --check portal-auth.js
node --check portal-shell.js
node --check nexy-journal.js
node tests/ui.cjs
```

Browser tests require Playwright and Microsoft Edge, and mock authentication. Only eight allowlisted assets enter the public bundle. Never serve the repository root.

## Deploy

```powershell
firebase deploy --only "hosting,firestore:rules" --project portalnexy
```

Firestore rules deny all client data access. Historical records and browser drafts are preserved. Broker source, trading workers and order controls remain retired. Dormant business assistants in `agents/` are not connected. An ignored pre-conversion backup stays local in `.firebase/retirement-backup/`.

## Communication Room preview

The Communication Room is a design skeleton with labelled sample agent messages, local replies/topics and agent mention pickers. Posts live in page memory and reset on reload. No agent API, broker or backend delivery is connected. Timestamps use Europe/Stockholm.

## Agent Activity Monitor preview

Read-only sample board with agent cards, graphical run intervals, period/agent filters and selectable run history. Running/waiting examples are frozen at the labelled snapshot. Estimates with missing values are labelled unavailable. No event stream or agent backend is connected.

## Ledger preview

Read-only illustrative USD financial board with transactions, account balances, profit/revenue reconciliation and costs. Figures are design fixtures, not live broker balances or NexyDAO returns. API estimates and externally paid cost allocations do not debit simulation cash. Brokerage fees are included in basis/realized profit and are not deducted twice. No account backend is connected.
