# Portal Nexy · NexyDAO

A private, empty workspace shell for NexyDAO. Only Google sign-in, the workspace frame and sign-out remain. No application pages, broker connections, order controls or trading workers.

## Build and validate

```powershell
python tools/build_ui.py
python -m unittest discover -s tests -v
node --check portal-auth.js
node --check portal-shell.js
node tests/ui.cjs
```

The browser test uses Playwright and Microsoft Edge with mocked authentication. Only four explicitly allowlisted assets enter the public bundle. Never serve the repository root.

## Deployment

```powershell
firebase deploy --only hosting,firestore:rules --project portalnexy
```

Firestore rules deny all client data access. Historical server records, browser drafts and local account ledgers are not erased. Google authentication remains restricted to the existing founder account. Broker source, launch/install/reset tools, strategies, trading documentation and cached Python modules have been removed. The retired Windows trading tasks were unregistered during conversion; no matching local trading worker was running.

The `agents/` directory contains dormant general business assistants. None are launched or connected by this shell. A pre-conversion source backup stays local in ignored `.firebase/retirement-backup/` and is never published or pushed.
