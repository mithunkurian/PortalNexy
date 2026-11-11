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

Browser tests require Playwright and its Chromium browser, and mock authentication. Set `PLAYWRIGHT_CHANNEL=msedge` to use Microsoft Edge instead. Only seven allowlisted assets enter the public bundle. Never serve the repository root.

## Deploy

```powershell
python tools/build_ui.py
firebase deploy --only hosting --project portalnexy
```

Firestore rules deny all client data access. Historical records and browser drafts are preserved. Broker source, trading workers and order controls remain retired. Dormant business assistants in `agents/` are not connected. An ignored pre-conversion backup stays local in `.firebase/retirement-backup/`.

## ATLAS Development Tracker

The **Development Tracker** navigation page (`#development-tracker`) presents the
separate ATLAS paper-trading MVP: eight milestones, 29 features, current work,
search/status filters, evidence and next gates. Overview and Development Journal
continue to describe NexyDAO; their strategy assumptions do not apply to ATLAS.
Founder sign-in and execution-disabled behavior remain in place.

The page reads the latest public ATLAS `main/dashboard/progress.json` on entry
and has a **Refresh latest status** button. Requests have an 8-second deadline,
no automatic retries and no credentials. If GitHub is unavailable, the page
explicitly shows the bundled snapshot (or last retrieved status). Source dates
and provenance remain visible. No IBKR, OpenAI or trading API is called.

Refresh the bundled fallback before a portal release:

```powershell
python tools/sync_atlas.py --repo C:\Users\Mithu\atlas
python tools/build_ui.py
```

The exporter reads only the committed `dashboard/progress.json` and refuses
uncommitted tracker changes. It never reads .env, runtime databases or broker
files. Status updates committed to ATLAS appear through the GitHub refresh
without another Firebase deployment; portal layout changes still need a release.
All bundled/static assets are publicly retrievable, as with the existing journal;
only publish sanitized tracker data. This page is not ATLAS's planned M8 trading
dashboard and does not change the engineering milestones or risk controls.

For an existing local PortalNexy checkout already authenticated with Firebase:

```powershell
cd C:\Users\Mithu\PortalNexy
git pull --ff-only
python tools/build_ui.py
firebase deploy --only hosting --project portalnexy
```

If Firebase reports no login, run `firebase login` locally and deploy again.
Never paste Firebase tokens into chat. Hosting-only deployment leaves Firestore
rules/data unchanged. Open `https://portalnexy.web.app/#development-tracker` and
hard-refresh after deployment. Portal sources pushed to GitHub alone do not
publish Firebase Hosting; no deployment automation is configured in this repo.
