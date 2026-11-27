# PortalNEXY · Nexy workspace

Founder workspace for Nexy, the autonomous trading unit. Overview and Development Journal present the NexyDAO tracker as a milestone map, searchable evidence timeline and expandable acceptance queue. Google sign-in remains restricted to the founder. The portal is informational and has no broker control route. ATLAS paper execution is supervised independently on its VM.

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

Browser tests require Playwright and its Chromium browser, and mock authentication. Set `PLAYWRIGHT_CHANNEL=msedge` to use Microsoft Edge instead. Only eleven allowlisted assets enter the public bundle. Never serve the repository root.

## Deploy

```powershell
python tools/build_ui.py
firebase.cmd deploy --only hosting --project portalnexy
```

Firestore rules permit the verified founder Google account to read one private ATLAS telemetry document. A dedicated custom-auth publisher can only create/update that document; all other client data access is denied. Historical records and browser drafts are preserved. Portal broker source, trading workers and order controls remain retired. Dormant business assistants in `agents/` are not connected. An ignored pre-conversion backup stays local in `.firebase/retirement-backup/`.

## ATLAS Development Tracker

The **Development Tracker** navigation page (`#development-tracker`) presents the
separate ATLAS paper-trading MVP: a metro-line map with eight collapsible milestone stations and the current committed feature set.
Completed stops are green; the current stop blinks amber. Reduced-motion users
get a steady current marker. Four phase groups, expand/collapse-all, saved
expansion state, search/status filters, evidence and next gates remain available. Overview and Development Journal
continue to describe NexyDAO; their strategy assumptions do not apply to ATLAS.
Founder sign-in and the absence of portal trading controls remain in place.
Each feature shows its maintained engineering completion and remaining-work estimates. Milestone estimates use the equally weighted mean of their features; accepted feature counts are separate. These estimates are not measured hours or proof of trading readiness. Implementation evidence and pending validation remain visible below each stop.
Feature rows also show implementation status and the named acceptance gate/owner
when provided by the ATLAS snapshot.

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
only publish sanitized tracker data. The tracker is separate from ATLAS's live monitoring page and does not change the engineering milestones or risk controls.

For an existing local PortalNexy checkout already authenticated with Firebase:

```powershell
cd C:\Users\Mithu\PortalNexy
git pull --ff-only
python tools/build_ui.py
firebase.cmd deploy --only hosting --project portalnexy
```

If Firebase reports no login, run `firebase.cmd login` locally and deploy again.
Never paste Firebase tokens into chat. Hosting-only deployment leaves Firestore
rules/data unchanged. Open `https://portalnexy.web.app/#development-tracker` and
hard-refresh after deployment. Portal sources pushed to GitHub alone do not
publish Firebase Hosting; no deployment automation is configured in this repo.

## Communication Room preview

The Communication Room is a design skeleton with labelled sample agent messages, local replies/topics and agent mention pickers. Posts live in page memory and reset on reload. No agent API, broker or backend delivery is connected. Timestamps use Europe/Stockholm.

## Agent Activity Monitor preview

Read-only sample board with agent cards, graphical run intervals, period/agent filters and selectable run history. Running/waiting examples are frozen at the labelled snapshot. Estimates with missing values are labelled unavailable. No event stream or agent backend is connected.

## Ledger preview

Read-only illustrative USD financial board with transactions, account balances, profit/revenue reconciliation and costs. Figures are design fixtures, not live broker balances or NexyDAO returns. API estimates and externally paid cost allocations do not debit simulation cash. Brokerage fees are included in basis/realized profit and are not deducted twice. No account backend is connected.


## ATLAS live monitor

Open **ATLAS Dashboard** in the left panel, or
[the direct page](https://portalnexy.web.app/#atlas-dashboard), using the founder
Google account. This is actual private VM telemetry, separate from the sample
Agent Activity Monitor and Ledger boards. It shows paper status, allocated
capital, owned P&L/exposure/risk, strategy performance, commissioning history,
fills, schedule, jobs, control outcomes, activity and analysis decisions.

The VM publishes an allowlisted document to `atlas_operator_live_v1/current`
every ten seconds. Browser authenticated GET polling runs every five seconds
while visible. Rules check verified founder email and Google provider; a
roleless dedicated custom-auth signer can write only this document. Financial
payloads never enter static assets or local storage. Source age over fifteen
seconds or relay age over thirty seconds hides current financial values.
Cloud refresh never renews broker-source age or resumes trading.

The page is read-only. Stop, Resume, Emergency and settings stay on the private
VM dashboard. There is no portal command collection. Existing legacy
collections remain denied. Key/config files stay owner-only on the VM;
credentials are never part of the hosting bundle.

The default page focuses on today's eight-stage activity timeline and the
capital/P&L cards. Stage buttons provide recorded status, scheduled/actual times,
counts and next requirements. The rail becomes vertical on phones. Positions,
trade history, activity, decisions, performance and read-only settings open in
native accessible dialogs that retain focus through refresh and clear on logout.
Dates use readable Stockholm time without seconds; scheduled analysis also
shows New York time. Only the scheduled-start countdown is calculated; execution
duration remains unknown without evidence. No-trade outcomes skip execution;
daily analysis completion does not imply active trades are closed.

After a failed daily job, stages that never ran show Skipped. The failed-stage
dialog can show allowlisted failure categories, source boundaries and API codes
when the VM recorded them. Codes may include informational messages and are not
by themselves a cause. Older failures keep their cause unknown; a screening
failure is distinct from a completed AI NO_TRADE decision. No failure replays
the consumed daily claim or resumes entries.

Decisions also shows a daily explanation of at most four sentences. Future
zero-candidate summaries use recorded broker price bounds, NASDAQ/USD common-stock
verification and fixed rejection counts, and name the later checks not reached.
Today's legacy run has no saved per-filter breakdown; the explanation explicitly
keeps the exact reason unknown. Current settings never substitute for past evidence.

The private paper worker can opt into fresh fifteen-minute opportunities from
10:15 until before 13:00 New York (last slot 12:45), with the original daily claim
and later slot claims kept separately. Scans require a flat book, no unresolved
holds, fresh broker-calendar/source gates and independent enabled risk. Missing
a slot never catches up or replays it. New scans pause while owned commitments
are monitored, and position supervision continues after the scan cutoff.

The native worker records minute-level Hold / Exit-trigger / Unconfirmed reviews.
The daily flow uses one horizontal blue main line with circular, clickable stations.
A pink no-entry branch returns through the next eligible slot and flat/readiness
checks; a green Hold branch returns to health review without another order. Exit
continues to reconciliation and attempt resolution. Route colors describe logic;
station status colors remain actual recorded evidence. Eight original stage
dialogs and a distinct current-health station remain. Narrow screens pan the
same readable map instead of squeezing labels or stacking separate route cards.
A Hold requires fresh protection/risk evidence bound to the same owned book;
stale reviews, changed commitments or unavailable broker/relay sources show
Unconfirmed. An exit trigger is not terminal-flat proof. Stop/target, daily loss
and recorded expiry/close deadlines remain independent; no model overrides them.
Source recovery never automatically rearms entries. Real open-position review
acceptance remains separate from synthetic tests and a flat-book live display.

The VM's auxiliary daily stage events are scoped to its pinned book and New York
market day. Missing old events stay unknown; failures and missed windows never
trigger replay. Current order activity comes from durable strategy entry attempts,
with terminal/retired intentions, matching totals and zero active holds required
for a completed daily workflow. Commissioning checks remain separate. Pipeline
states beyond the actual observed waiting/paused view are validated with
synthetic tests until a genuine eligible scheduled run occurs.

Validation:

```powershell
python tests/rules_remote.py
node tests/atlas_live.cjs
```

The rules test uses the existing gcloud login in process memory to execute
allow/deny tests against proposed rules without database writes. Browser QA
uses synthetic auth/data. Actual Nov20 acceptance additionally verified the
signed-in founder Edge page, VM publisher authentication/write and HTTP 403
for anonymous/publisher reads, historical reads and command writes.
The later daily-workflow enhancement also passed isolated browser QA against
the deployed hosting URL with synthetic auth/data. Set
`ATLAS_TEST_BASE_URL=https://portalnexy.web.app/` before running the private
browser test. Real eight-stage VM publication was verified separately.
The existing owner tab could not be refreshed by its desktop helper; no new
owner-window acceptance is claimed for the enhanced layout.
Deploy rule changes explicitly with `firebase.cmd deploy --only firestore:rules
--project portalnexy`; hosting-only releases do not update access rules.
