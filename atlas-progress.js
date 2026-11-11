"use strict";
window.ATLAS_TRACKER = {
  "revision": "f35bd61e84850b12f36dfa3d4fbfbea355c6af89",
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
        "evidence": "Current off-market implementation is integrated and deployed: NASDAQ discovery/screening, typed normalized news, consumption-time freshness and same-symbol/broker-contract context binding, plus offline diagnostic settings review. Windows: 193 tests passed in 12.17s; directly executed VM: 193 passed in 12.46s and pip check passed. Actual VM context at 09:59 UTC correctly rejected stale AAPL quote and stale headlines (exit 1), with no text leakage/orders. Earlier premarket screening accepted two fresh quotes and rejected one stale quote; included historical text access was verified. Only NASDAQ_US is enabled; later authorized subscriptions/Swedish/Nordic expansion boundaries are documented. Regular-hours/fresh-news acceptance and strategy decisions remain open.",
        "next": "Coding for this increment is complete. Agent: obtain regular-hours fresh quote/screening acceptance and an actually fresh included-provider article/context when available (news may arrive outside market hours). Reviewable screening draft is in config/screening.draft.json; strategy thresholds and independent risk limits remain undecided for subsequent strategy/risk work. No additional market/subscription is enabled.",
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
            "status": "In progress",
            "implementationStatus": "Implemented; acceptance pending",
            "acceptanceGate": "Agent: actual fresh timestamped news/context acceptance; no market-open requirement for news."
          }
        ]
      },
      {
        "id": "M3",
        "name": "AI trading engine",
        "budget": 2,
        "status": "Not started",
        "evidence": "OpenAI connectivity probe complete under M1; strategy analysis and trading-plan validation remain unimplemented.",
        "next": "Configure strategy and validate structured plans.",
        "features": [
          {
            "id": "M3.1",
            "name": "Configurable strategy and prompts",
            "status": "Not started"
          },
          {
            "id": "M3.2",
            "name": "OpenAI analysis",
            "status": "Not started"
          },
          {
            "id": "M3.3",
            "name": "Pydantic trading-plan validation",
            "status": "Not started"
          }
        ]
      },
      {
        "id": "M4",
        "name": "Risk management",
        "budget": 2,
        "status": "Not started",
        "evidence": "No deterministic risk engine implemented.",
        "next": "Agree risk limits; implement sizing, stale-data checks and kill switch.",
        "features": [
          {
            "id": "M4.1",
            "name": "Position sizing and capital limits",
            "status": "Not started"
          },
          {
            "id": "M4.2",
            "name": "Independent risk validation",
            "status": "Not started"
          },
          {
            "id": "M4.3",
            "name": "Duplicate prevention and kill switch",
            "status": "Not started"
          }
        ]
      },
      {
        "id": "M5",
        "name": "IBKR integration",
        "budget": 3,
        "status": "In progress",
        "evidence": "User-reported VM test: connected, one DU-prefixed account, broker time retrieved. No orders submitted.",
        "next": "Implement paper-only execution and order tracking after risk controls.",
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
            "status": "Not started"
          }
        ]
      },
      {
        "id": "M6",
        "name": "Automation and monitoring",
        "budget": 2,
        "status": "Not started",
        "evidence": "No scheduler, reports or automated monitoring implemented.",
        "next": "Schedule 10:15 America/New_York scans on US trading days.",
        "features": [
          {
            "id": "M6.1",
            "name": "Trading-day scheduling",
            "status": "Not started"
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
        "evidence": "193 offline tests passed on Windows and directly on VM. Real read-only market-context pipeline executed and rejected stale quote/news; prior premarket screening and included historical body access verified. End-to-end trading and paper commissioning remain pending; M7 is not completed.",
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
      "Measured continuous implementation checkpoint: 13.3 minutes, 2026-11-11 09:46:33\u201309:59:48 UTC, covering implementation, tests and VM deployment/validation. Historical engineering totals and remaining budget remain unknown."
    ],
    "blockers": [
      "M2.1 awaits a fresh accepted VM sample during 09:30\u201316:00 America/New_York. Latest historical user-reported real-time samples were stale after hours. Direct SSH access is now established.",
      "M2.2 implementation and diagnostic settings review are available; regular-hours screening acceptance and agreement on strategy-specific filters remain pending.",
      "Typed normalized news feed/context implementation is integrated and VM-tested. Actual fresh timestamped article/context acceptance remains pending; latest real quote/headline inputs were stale and rejected. News can arrive outside regular market hours.",
      "Strategy and risk limits not agreed",
      "Historical engineering time is unknown; total remaining hours cannot be calculated."
    ],
    "currentFeature": "M2.3",
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
