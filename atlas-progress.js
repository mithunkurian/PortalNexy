"use strict";
window.ATLAS_TRACKER = {
  "revision": "fd6a9542e8f6cd96c74f444a806e91034c198e73",
  "branch": "main",
  "progress": {
    "updated": "2026-11-11",
    "budgetHours": 18,
    "recordedHours": null,
    "milestones": [
      {
        "id": "M1",
        "name": "Environment setup",
        "budget": 1,
        "status": "Complete",
        "evidence": "Cloud installation, 18 offline tests and real OpenAI probe passed. User reported VM constrained installation, pip check, 18 tests and real OpenAI probe passed. No orders submitted.",
        "next": "M2: validate IBKR quote/API entitlements within existing subscriptions.",
        "features": [
          {
            "id": "M1.1",
            "name": "Project folder and Git repository",
            "status": "Complete"
          },
          {
            "id": "M1.2",
            "name": "Python environment and dependencies",
            "status": "Complete"
          },
          {
            "id": "M1.3",
            "name": "OpenAI configuration and connectivity",
            "status": "Complete"
          }
        ]
      },
      {
        "id": "M2",
        "name": "Market intelligence",
        "budget": 2,
        "status": "In progress",
        "evidence": "Read-only discovery/screening and normalized news/context implemented. M2.3 accepted: direct VM at 13:38 UTC verified one fresh BRFUPDN text article, publication epoch 12:26:23 UTC, no article issues and one normalized usable news input. Combined context correctly remained incomplete because the AAPL quote was stale. Regular-hours quote/screening acceptance and strategy-filter choices remain open. No article text printed, inference request or orders.",
        "next": "Agent: obtain accepted regular-hours quote/screening samples; retain source freshness/contract gates. News component acceptance passed; each future analysis still requires fresh complete context. Strategy filters remain undecided. Existing subscriptions only.",
        "features": [
          {
            "id": "M2.1",
            "name": "Market-data API integration",
            "status": "In progress",
            "implementationStatus": "Implemented; acceptance pending",
            "acceptanceGate": "Agent: fresh regular-hours quote acceptance."
          },
          {
            "id": "M2.2",
            "name": "NASDAQ stock screening",
            "status": "In progress",
            "implementationStatus": "Implemented; acceptance pending",
            "acceptanceGate": "Agent: regular-hours screening acceptance; strategy filter decisions remain open."
          },
          {
            "id": "M2.3",
            "name": "News and catalysts",
            "status": "Complete",
            "implementationStatus": "Implemented; live included-news validation passed",
            "acceptanceGate": "Complete: directly verified timestamped included-provider text and normalized usable input on VM; freshness is rechecked per use."
          }
        ]
      },
      {
        "id": "M3",
        "name": "AI trading engine",
        "budget": 2,
        "status": "In progress",
        "evidence": "Strategy draft/review, bounded structured analysis and Pydantic proposal validation implemented. Windows: 233 tests passed in 13.86s; direct VM: 233 passed in 15.25s. VM strategy review shows analysis disabled; draft analyze CLI rejected before broker/key/API access. M3.3 deterministic validation acceptance complete. M3.1 strategy decisions/approval and M3.2 actual structured API acceptance remain pending. No real inference request, risk approval or order.",
        "next": "Continue independent deterministic risk controls with unapproved/unset monetary limits. Strategy approval and fresh context precede actual M3.2 inference; M3.3 validation does not authorize risk or orders.",
        "features": [
          {
            "id": "M3.1",
            "name": "Configurable strategy and prompts",
            "status": "In progress",
            "implementationStatus": "Implemented; acceptance pending",
            "acceptanceGate": "Operator strategy decisions/approval remain open; no values assumed."
          },
          {
            "id": "M3.2",
            "name": "OpenAI analysis",
            "status": "In progress",
            "implementationStatus": "Implemented; acceptance pending",
            "acceptanceGate": "Agent: real structured-output API acceptance with approved strategy and fresh verified context."
          },
          {
            "id": "M3.3",
            "name": "Pydantic trading-plan validation",
            "status": "Complete",
            "implementationStatus": "Implemented and deterministic validation passed",
            "acceptanceGate": "Complete: local/VM schema, context-binding and fail-closed SDK/CLI tests; financial risk remains M4."
          }
        ]
      },
      {
        "id": "M4",
        "name": "Risk management",
        "budget": 2,
        "status": "In progress",
        "evidence": "Independent sizing/reservations and persistent loss stop implemented. User selected daily loss cap of 5% of verified capital in open positions; explicitly approved proposed first-position capital as the initial basis with verified flat state, no pending risk and no loss. Windows 366 tests passed in 14.50s; direct VM 366 passed in 15.22s and pip check passed. Other independent limits/approval and trusted M5 adapters remain pending. No actual portfolio promotion or orders.",
        "next": "Dynamic policy VM validation passed; obtain remaining per-trade/position limits and approval. Verified M5 portfolio/session/rules and outcome reconciliation remain required.",
        "features": [
          {
            "id": "M4.1",
            "name": "Position sizing and capital limits",
            "status": "In progress",
            "implementationStatus": "Core implemented; operational acceptance pending",
            "acceptanceGate": "Agent: VM sizing tests; approved limits and verified broker portfolio data before use."
          },
          {
            "id": "M4.2",
            "name": "Independent risk validation",
            "status": "In progress",
            "implementationStatus": "Core implemented; operational acceptance pending",
            "acceptanceGate": "Agent: VM rejection tests; actual paper/rule/session verification and M5/M6 integration pending."
          },
          {
            "id": "M4.3",
            "name": "Duplicate prevention and kill switch",
            "status": "In progress",
            "implementationStatus": "Core implemented; operational acceptance pending",
            "acceptanceGate": "Agent: VM persistence/concurrency tests; broker reconciliation and authenticated stop integration pending."
          }
        ]
      },
      {
        "id": "M5",
        "name": "IBKR integration",
        "budget": 3,
        "status": "In progress",
        "evidence": "Read-only non-binding order/fill/position observation and transactional local SQLite persistence implemented. Windows 312 tests passed in 17.65s; direct VM 312 passed in 13.57s and pip check passed. Actual VM observation at 14:01 UTC succeeded: zero positions, open orders and returned executions. No broker order changes, trusted risk-state promotion, P&L inference or hold release.",
        "next": "Continue lifecycle reconciliation and trusted portfolio/session inputs before execution. M5.2 remains disabled pending approved risk limits.",
        "features": [
          {
            "id": "M5.1",
            "name": "Existing Gateway API connection",
            "status": "Complete"
          },
          {
            "id": "M5.2",
            "name": "Paper-trading orders",
            "status": "Not started"
          },
          {
            "id": "M5.3",
            "name": "Orders, fills and positions",
            "status": "In progress",
            "implementationStatus": "Read-only observation foundation implemented",
            "acceptanceGate": "Actual read-only VM observation passed; complete lifecycle reconciliation and trusted portfolio acceptance remain pending."
          }
        ]
      },
      {
        "id": "M6",
        "name": "Automation and monitoring",
        "budget": 2,
        "status": "In progress",
        "evidence": "Contract-specific regular-session diagnostic implemented using verified liquidHours and explicit market timezone aliases. Windows 348 tests passed in 14.46s; direct VM 348 passed in 14.67s and pip check passed. Actual VM at 14:10 UTC verified current date covered, session closed and next reported opening 14:30 UTC. No scheduler, reports, monitoring or orders enabled.",
        "next": "Implement persisted 10:15 market-local scheduling and stop/run deduplication before operational acceptance; calendar diagnostic acceptance passed.",
        "features": [
          {
            "id": "M6.1",
            "name": "Trading-day scheduling",
            "status": "In progress",
            "implementationStatus": "Read-only session calendar foundation implemented",
            "acceptanceGate": "Actual VM calendar diagnostic passed; scheduler/duplicate/stop integration and operational acceptance remain pending."
          },
          {
            "id": "M6.2",
            "name": "Logging and error handling",
            "status": "Not started"
          },
          {
            "id": "M6.3",
            "name": "Notifications and reports",
            "status": "Not started"
          }
        ]
      },
      {
        "id": "M7",
        "name": "Testing and commissioning",
        "budget": 3,
        "status": "Not started",
        "evidence": "366 offline tests passed on Windows and directly on VM. Real read-only included news, context, broker observation and regular-session diagnostics executed. End-to-end order lifecycle and paper commissioning remain pending; foundation tests do not complete M7.",
        "next": "Run integration tests and paper-trading commissioning.",
        "features": [
          {
            "id": "M7.1",
            "name": "End-to-end integration tests",
            "status": "Not started"
          },
          {
            "id": "M7.2",
            "name": "Paper-trading evaluation",
            "status": "Not started"
          },
          {
            "id": "M7.3",
            "name": "Readiness review and defects",
            "status": "Not started"
          }
        ]
      },
      {
        "id": "M8",
        "name": "Trading dashboard and controls",
        "budget": 3,
        "status": "Not started",
        "evidence": "This development tracker is separate from the planned trading dashboard.",
        "next": "Build authenticated status, P&L, positions and safe controls.",
        "features": [
          {
            "id": "M8.1",
            "name": "System status, balance and P&L",
            "status": "Not started"
          },
          {
            "id": "M8.2",
            "name": "Activity and decision monitor",
            "status": "Not started"
          },
          {
            "id": "M8.3",
            "name": "Positions and trade history",
            "status": "Not started"
          },
          {
            "id": "M8.4",
            "name": "Performance metrics",
            "status": "Not started"
          },
          {
            "id": "M8.5",
            "name": "Schedule monitor",
            "status": "Not started"
          },
          {
            "id": "M8.6",
            "name": "Pause, resume and emergency stop",
            "status": "Not started"
          },
          {
            "id": "M8.7",
            "name": "Safe configuration editing",
            "status": "Not started"
          },
          {
            "id": "M8.8",
            "name": "Authenticated private access",
            "status": "Not started"
          }
        ]
      }
    ],
    "checks": [
      "VM prerequisites verified by user",
      "IBKR read-only connectivity passed on VM",
      "Paper account prefix detected; no orders submitted",
      "Gateway login manual and development tracker pushed to GitHub",
      "Repository rule saved: update the development dashboard with every development commit, PR and feature completion",
      "M1 continuation prompt and detailed development tracker saved under docs; historical time remains unrecorded",
      "Cloud M1.2: constrained editable install, pip check, package imports and 18 tests passed; browser rendered four phases and 29 features.",
      "Measured development work this session: 2.8 minutes at validation checkpoint; historical hours remain unknown.",
      "2026-11-10: real authenticated OpenAI Responses probe passed in the published cloud environment; no broker connection or orders submitted.",
      "User-reported VM validation: constrained package installation succeeded; pip check found no broken requirements; 18 tests passed in 1.74s; real OpenAI connectivity passed.",
      "M2 scope agreed: existing IBKR subscriptions only; no additional paid data/news services or Level 2 dependency. Current M2 handover saved in docs.",
      "2026-11-10 M2.1: 55 cloud tests passed; dependency check passed. Mocked broker lifecycle, delayed/frozen/unconfirmed rejection, stale/missing/future timestamps, SDK timestamp regression, cleanup, disconnect and news-unavailable behavior tested. No real broker request executed in cloud.",
      "M2 session measured checkpoint: 6.6 minutes of continuous work, 21:38:33\u201321:45:07 UTC. Historical time and total remaining budget remain unknown.",
      "User-reported VM M2: 55 tests passed in 12.52s; repeated actual check-ibkr timeouts, exit 1. No successful quote or entitlement validation.",
      "Cloud timeout-diagnostic fix: 62 tests and pip check passed; mocked connection, broker-time and contract-detail failures verify safe stages, numeric API codes, redaction and disconnect. No direct VM access.",
      "Measured diagnostic-fix checkpoint: 1.8 minutes, 21:58:10\u201321:59:55 UTC on 2026-11-10. Historical project time and total remaining budget remain unknown.",
      "User-reported VM 2026-11-10 22:02 UTC: actual broker connection/time and real-time AAPL callback succeeded; stale broker-supplied BidAsk timestamp rejected. After regular hours (17:02 New York). News providers advertised; no articles requested. Exit 1. Earlier connection timeout cause remains unconfirmed.",
      "User-reported VM 2026-11-10 22:03 UTC: broker_time 22:03:43Z, AAPL real-time BidAsk source_time 22:03:28Z, received_at 22:03:45.329926Z (17.3 seconds old at receipt). stale_bid_ask rejected; exit 1. After regular NASDAQ hours; no orders or news articles requested.",
      "2026-11-11 Windows development: constrained editable installation succeeded; pip check passed; full offline suite 116 passed in 19.96s. Earlier test attempts preceded completion of dependency installation; final checks ran after installation completed.",
      "M2.2 screening: synthetic unsupported-contract, stale/future/missing/malformed quote, duplicate, threshold/boundary, no-order and mocked read-only lifecycle tests passed. CLI invalid-range smoke check exited 1 before connecting. No actual VM or broker requests executed.",
      "Measured continuous development checkpoint: 7.9 minutes, 2026-11-11 08:55:19\u201309:03:15 UTC, including local environment setup and automated validation. Historical engineering totals and remaining budget remain unknown.",
      "2026-11-11 continued development: 158 Windows offline tests passed in 29.34s; pip check passed. Scanner metadata/contract checks, subscription cancellation, discovery-to-screening bounds, included-provider news restrictions, duplicate/time/body/error handling and sanitized failures tested with mocks. Direct read-only VM SSH succeeded; VM checkout was clean before deployment.",
      "2026-11-11: PortalNexy Development Tracker page prepared for ATLAS with eight milestones/29 features, readable expandable evidence, search/status filters and latest public GitHub tracker refresh plus labelled bundled fallback. Portal checks: eight Python tests and desktop/mobile browser QA passed (mocked auth/GitHub responses); actual public tracker endpoint HTTP 200. Firebase deployment pending authentication; this does not complete M8.",
      "2026-11-11: PortalNexy saved local branch integrated with ATLAS Development Tracker, preserving Agentic Architecture, Communication Room, Agent Activity Monitor and Ledger previews, cache-control settings and founder access. Combined build: 10 allowlisted assets; eight Python tests and desktop/mobile browser QA passed across all seven pages with mocked auth. Firebase publishing remains pending; use firebase.cmd on Windows.",
      "2026-11-11: User reported successful Firebase deployment of the combined PortalNexy pages. Requested metro-line visualization restored in source: four phase routes, eight collapsible milestone stations, 29 feature stops, green completions and a blinking amber current stop (steady with reduced motion). Eight portal Python tests and all-page desktop/mobile browser QA passed, including keyboard collapse/expand and animation checks. Metro revision still needs hosting deployment; M2.1/M8 unchanged.",
      "Direct VM 2026-11-11: deployed 6e2161e; 158 tests passed in 14.97s; pip check passed. Initial broker probes failed before Gateway startup (no Java process or API listener). Started Gateway on existing VNC desktop; user completed paper session; port 4002 then listened.",
      "Direct VM 2026-11-11 09:21 UTC: NASDAQ TOP_PERC_GAIN five-result discovery verified three common-stock contracts and rejected two; no quotes/orders requested by discovery. Combined premarket run at 09:23 UTC accepted two source-fresh quotes and rejected one stale quote. This is not regular-hours M2.1 acceptance or strategy approval.",
      "Direct VM included-news probe: three BRFG/BRFUPDN text-body requests succeeded. All historical headline timestamps lacked zones, explicitly flagged unverified; no article text printed or sent to AI. Strategy news remains disabled.",
      "2026-11-11 follow-up: 163 Windows tests passed in 13.67s and pip check passed. Live tickNews epoch capture, UTC preservation, invalid/stale/future time rejection, stream cancellation and callback restoration tested with synthetic inputs. No timezone/unit guessing.",
      "Measured continuous development checkpoint: 18.9 minutes, 2026-11-11 09:06:13\u201309:25:08 UTC, including implementation, testing, deployment and brief desktop handoff. Historical engineering totals and remaining budget remain unknown.",
      "Direct VM deployed 46e7888: 163 tests passed in 13.71s. First live-news probe retrieved bodies but rejected publication times; investigation found tickNews fixed millisecond units in IBKR published C++ sample. Conversion corrected from seconds to milliseconds and synthetic live capture now exercises the real SDK decoder. No invalid timestamp was accepted.",
      "Windows millisecond correction: full 163 tests passed in 13.78s, including real SDK decoder live-news capture; tracker retains pending corrected VM acceptance.",
      "Direct VM after 8e4e6cd: 163 tests passed in 12.78s. Corrected live-news epochs parsed successfully, but sampled initial cached headlines were stale and correctly rejected (exit 1); no bodies requested for stale stories. Follow-up bounded live buffer now selects newest valid stories from at most 50 distinct callbacks, retaining at most three body requests and the unchanged 24-hour diagnostic age limit.",
      "Windows newest-valid headline selection: 164 tests passed in 13.96s, including real SDK decoder stale-cache regression; pending VM confirmation.",
      "Final direct VM after deployment of 12a9ff1: full suite 164 passed in 12.22s. Actual eight-second live-news sample decoded millisecond publication epochs; only stale headlines were available, so no text bodies were requested for them and probe exited 1. No retries, age-limit relaxation, orders or paid additions. Historical text-body access evidence is separate; fresh strategy news remains unavailable.",
      "2026-11-11 PortalNexy DT review release: PortalNexy 86c6b9e published through Firebase Hosting; ten allowlisted assets. Bundled ATLAS snapshot 2d9f3e3 includes current M2.3 and 164-test/direct-VM evidence. Milestone percentages explicitly count fully accepted features: M2 0/3 (0% accepted), all three remain In progress; no estimated implementation percentage or milestone progress invented. Eight Python tests and desktop/mobile Edge browser QA passed with mocked auth/GitHub; actual hosted tracker/script bytes match tested build. Public GitHub tracker endpoint returned HTTP 404, so the deployed bundled snapshot supplies the review data. No broker or trading changes; M8 remains Not started.",
      "2026-11-11 continued implementation: 191 Windows tests passed in 13.25s and pip check passed. Normalized feed, untrusted content separation, script stripping, consumption-time expiry, broker-error rejection, quote/news contract binding, settings/schema/override validation and disabled-market boundaries tested. Offline review command passed; no strategy values invented. Future authorized subscriptions and Swedish/Nordic expansion requirement saved in AGENTS/handover/settings documentation; only NASDAQ_US enabled. New actual VM validation pending.",
      "Final Windows integration suite: 193 tests passed, including broker-symbol mismatch rejection before quote/news requests; settings review and unchanged dependency checks passed. Context summaries omit the quote-only news placeholder and retain redacted authoritative news metadata.",
      "Direct VM after 931c21c deployment: full 193 tests passed in 12.46s; pip check passed. Actual context-ibkr --settings draft completed at 2026-11-11 09:59 UTC: stale AAPL quote and stale included-provider headlines rejected; zero usable news, incomplete intelligence input, exit 1. Typed feed/context integration is now implemented and VM-tested. No AI calls, raw news text output, orders, subscription purchases or Nordic-market activation. Remaining data acceptance is distinct from completed implementation.",
      "Measured continuous implementation checkpoint: 13.3 minutes, 2026-11-11 09:46:33\u201309:59:48 UTC, covering implementation, tests and VM deployment/validation. Historical engineering totals and remaining budget remain unknown.",
      "2026-11-11 PortalNexy d147cf8 deployed: bundled ATLAS f35bd61 snapshot shows 193-test/VM context evidence plus separate implementation status and named acceptance gate for each M2 feature. Eight portal Python tests, syntax and desktop/mobile Edge QA passed with mocked auth/GitHub. Direct HTTPS byte comparison verified hosted tracker data, UI script and CSS against the tested build. Only ten allowlisted assets published; no auth/Firestore/trading changes. Feature acceptance and recordedHours unchanged; future subscriptions/Nordic requirement retained.",
      "Direct VM 2026-11-11 10:10 UTC: integrated context rejected stale AAPL quote and stale included headlines; news reported request error 10197. Official IBKR error table associates 10197 with competing data sessions, but user reports no other live session. Cause unconfirmed. VM paper Gateway/VNC/SSH should remain open; no logout or subscription change made.",
      "2026-11-11 M3 Windows: full suite 233 passed in 13.86s; pip check passed. Strategy JSON/review and strict proposal schema implemented. Actual pinned Responses parser exercised with mocked HTTP: bounded request/store false/no retries, untrusted news separation, refusal/incomplete/network/HTTP rejection, symbol/market/currency/contract/evidence checks, data expiry and changed-context rejection. No real inference request or order; strategy remains unapproved.",
      "Direct VM after 8963e48: 233 tests passed in 15.25s; review-strategy returned analysis_enabled false; analyze-ibkr with draft exited 1 with draft/incomplete rejection before broker/key/API access. M3.3 acceptance criteria in docs/strategy-and-plan-validation.md satisfied using deterministic tests and real SDK/mock HTTP. No real inference request or order; M3.1/M3.2 remain In progress.",
      "2026-11-11 M4 Windows: 281 tests passed in 27.56s; pip check passed. New risk tests use synthetic limits/state only and real temporary SQLite databases: sizing/caps/fees/slippage, paper/session/identity/currency/ticks/evidence/age rejection, default stop/restart persistence, duplicate proposals/symbols, eight-way duplicate and shared-capacity concurrency, policy changes, corrupt storage and draft review/stop CLI. All order_authorized properties remain false; no operational ledger was armed or portfolio loaded.",
      "Direct VM after 5da67d7: 281 tests passed in 14.14s, pip check passed, actual review-risk CLI reported risk_policy_enabled false and every monetary/approval decision missing. No operational portfolio loaded or risk ledger armed. Follow-up daily-loss latch added so verified breaches persist across recovery; invalid/stale/currency-mismatched state cannot latch. New final local/VM validation recorded when run.",
      "Final Windows M4 latch suite: 287 tests passed in 14.54s, including durable daily-loss stop across restart/P&L recovery and monitor-only breach handling. No new dependency or operational activation; corrected follow-up VM acceptance pending deployment.",
      "Direct VM 2026-11-11 13:38 UTC: included BRFUPDN article publication time 12:26:23 UTC verified via live millisecond epoch; text body accessible, zero issues, normalized usable-news count 1. M2.3 acceptance passed. Combined context exited 1 solely with stale AAPL quote; quote/regular-hours gates remain closed. No 10197 in this sample; earlier cause unconfirmed. No article text or actual inference/order.",
      "Direct VM after e54d853: 287 tests passed in 13.64s and review-risk confirmed disabled policy. User subsequently supplied initial paper allocation; implemented editable base allocation and optional capped reinvestment from verified realized-net-profit baseline. Monetary allocation does not approve risk, alter broker cash or raise independent risk limits. Windows 295 tests passed in 13.59s; new VM validation pending.",
      "2026-11-11 M5 Windows: 312 tests passed in 17.65s; pip check passed. Synthetic read-only observations and real temporary SQLite tests cover scope/timeouts, non-binding requests, execution corrections, idempotency, unknown fees, late commission, transaction rollback and missing-order retention. Direct VM risk review confirms configurable USD 20,000 allocation, reinvestment off, remaining limits unset and execution disabled.",
      "2026-11-11 direct VM after 8658723: 312 tests passed in 13.57s; pip check passed. Actual check-broker-state at 14:01 UTC returned one paper-prefix candidate, zero positions/open orders/returned executions and informational codes 2104/2106/2158. No private database requested, account identifier printed, risk-state promotion or order action. Empty returned history does not establish complete execution history or verified paper mode.",
      "2026-11-11 PortalNexy 95abb9b pushed and Firebase Hosting deployed. Bundled ATLAS 7dfec33 shows M2.3 and M3.3 accepted, M2 1/3 (33%) accepted and current M5.3. Eight portal tests, JavaScript syntax and desktop/mobile browser QA passed (mocked auth/GitHub); all 10 actual hosted assets matched local SHA-256 bytes. This hosting audit does not change feature acceptance or complete M8.",
      "2026-11-11 Windows session calendar: 348 tests passed in 14.46s. Added read-only check-session client 96 with NASDAQ contract identity, liquidHours-only parsing, enabled-profile timezone aliases, DST-safe UTC conversion, explicit closed/unknown dates, half-days/gaps, inclusive opening/exclusive close, 60-second metadata receipt age and bounded failure handling. No fixed Stockholm offset, holiday inference, scheduler or order authorization. Actual VM validation pending.",
      "2026-11-11 direct VM after f295c10: 348 tests passed in 14.67s and pip check passed. Actual check-session at 14:10 UTC verified AAPL contract identity, America/New_York timezone, fresh received metadata/current-date coverage, regular session closed and next reported open 14:30 UTC. No fallback calendar, scheduler, risk-state promotion or orders. User specified maximum loss 5% of total invested; scope (portfolio/trade/day) and denominator require clarification before configuration.",
      "2026-11-11 user clarified 5% means total daily loss relative to capital in open positions. Implemented explicit fraction policy, mutually exclusive fixed cap, verified distinct invested-capital input, dynamic sizing capacity and durable monitor stop. Unknown/zero basis fails closed, zero P&L does not spuriously stop, negative P&L at zero basis latches. Allocation/cash/marked exposure cannot substitute. Windows 358 tests passed in 14.94s; direct VM validation pending. No per-trade limit or initial-entry exception inferred.",
      "Final Windows daily-policy suite: 366 passed in 14.50s. User approved proposed first-position capital for the initial 5% daily-loss basis. Implemented explicit flag/default false, configured true in unapproved draft. Initial entry needs verified zero invested capital/flat state, no pending exposure/reservations and no loss; downside plus fees/slippage must fit 5% of proposed entry notional and every other cap. Atomic hold prevents a second bootstrap; restart/negative-P&L controls remain intact. New direct VM validation pending.",
      "Direct VM after 6596be7: 366 tests passed in 15.22s and pip check passed. Actual risk review reports editable USD 20,000 allocation, daily_loss_basis open_position_capital, fraction 0.05, approved initial-position basis flag true, reinvestment false and aggregate policy/order authorization false. Other independent limits remain unset; no operational ledger armed or portfolio promoted."
    ],
    "blockers": [
      "M2.1 awaits a fresh accepted VM sample during 09:30\u201316:00 America/New_York. Latest historical user-reported real-time samples were stale after hours. Direct SSH access is now established.",
      "M2.2 implementation and diagnostic settings review are available; regular-hours screening acceptance and agreement on strategy-specific filters remain pending.",
      "Strategy and risk limits not agreed",
      "Historical engineering time is unknown; total remaining hours cannot be calculated.",
      "M3 actual analysis disabled: strategy decisions/approval remain unset and fresh verified context is unavailable. M4 deterministic controls exist; verified broker integration and order authorization remain disabled.",
      "M4 operational use disabled: risk.draft.json has configurable base allocation but remaining limits/approval are unset; M5 verified portfolio/paper/contract rules, M6 session proof and broker outcome reconciliation are not implemented. A local reservation is not order permission.",
      "Daily-loss scope/denominator confirmed: 5% of capital in open positions. User approved proposed first-position basis with verified flat state/no pending commitments/no daily loss. Unknown capital or ineligible zero basis blocks entries. Independent per-trade/position limits and aggregate approval remain unset."
    ],
    "currentFeature": "M4.1",
    "phases": [
      {
        "id": "P1",
        "name": "Market intelligence",
        "milestones": [
          "M1",
          "M2",
          "M3"
        ]
      },
      {
        "id": "P2",
        "name": "Risk & execution",
        "milestones": [
          "M4",
          "M5"
        ]
      },
      {
        "id": "P3",
        "name": "Automation & commissioning",
        "milestones": [
          "M6",
          "M7"
        ]
      },
      {
        "id": "P4",
        "name": "Web dashboard & controls",
        "milestones": [
          "M8"
        ]
      }
    ]
  }
};
