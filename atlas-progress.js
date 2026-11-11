"use strict";
window.ATLAS_TRACKER = {
  "revision": "619c7a8aa11fdf93b0fd86a3a563b351e03b3efd",
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
        "evidence": "M2.1 implemented; 62 cloud tests and pip check passed. Separately user-reported VM: 55 tests passed in 12.52s; actual connection, broker time and real-time AAPL callback confirmed. Latest 2026-11-10 22:03 UTC sample was 17.3 seconds old at receipt, correctly rejected as stale (exit 1). Earlier 22:02 UTC sample was about 67 seconds old. Both after regular hours. News providers advertised; article access unverified.",
        "next": "Obtain a fresh accepted read-only VM sample during 09:30\u201316:00 America/New_York before completing M2.1; then implement NASDAQ common-stock screening and verify included news articles. Define strategy and independent risk limits before trading decisions or orders. Existing subscriptions only.",
        "features": [
          {
            "id": "M2.1",
            "name": "Market-data API integration",
            "status": "In progress"
          },
          {
            "id": "M2.2",
            "name": "NASDAQ stock screening",
            "status": "Not started"
          },
          {
            "id": "M2.3",
            "name": "News and catalysts",
            "status": "Not started"
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
        "evidence": "62 cloud diagnostic tests passed; separately user-reported VM: 55 tests passed and real-time quote callbacks with stale-data rejection confirmed. End-to-end trading integration and paper commissioning remain pending.",
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
      "2026-11-11: PortalNexy Development Tracker page prepared for ATLAS with eight milestones/29 features, readable expandable evidence, search/status filters and latest public GitHub tracker refresh plus labelled bundled fallback. Portal checks: eight Python tests and desktop/mobile browser QA passed (mocked auth/GitHub responses); actual public tracker endpoint HTTP 200. Firebase deployment pending authentication; this does not complete M8."
    ],
    "blockers": [
      "M2.1 awaits a fresh accepted VM sample during 09:30\u201316:00 America/New_York. Latest real-time samples were stale after regular hours. Direct Codex-to-VM access remains unconfigured.",
      "Included news articles remain unavailable/unverified; advertised provider metadata alone does not establish entitlement.",
      "Strategy and risk limits not agreed",
      "Historical engineering time is unknown; total remaining hours cannot be calculated.",
      "PortalNexy hosting release pending: Firebase deployment authentication is unavailable in the cloud workspace. Local PortalNexy checkout can build and deploy hosting-only after pulling."
    ],
    "currentFeature": "M2.1",
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
