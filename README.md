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

Browser tests require Playwright and Microsoft Edge, and mock authentication. Only five allowlisted assets enter the public bundle. Never serve the repository root.

## Deploy

```powershell
firebase deploy --only "hosting,firestore:rules" --project portalnexy
```

Firestore rules deny all client data access. Historical records and browser drafts are preserved. Broker source, trading workers and order controls remain retired. Dormant business assistants in `agents/` are not connected. An ignored pre-conversion backup stays local in `.firebase/retirement-backup/`.
