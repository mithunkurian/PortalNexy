"""
Nexy HQ — Agent Orchestrator
Runs all 6 agents simultaneously, each in its own thread.
One process, one container, one Cloud Run deployment.
"""

import threading
import time
import signal
import sys
from datetime import datetime, timezone

from marketing_agent  import ARIAAgent
from legal_agent      import LEXAgent
from finance_agent    import FINAgent
from sales_agent      import REXAgent
from engineering_agent import DEVAgent
from research_agent   import UXRAgent


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] NEXY HQ › {msg}")


def run_agent(agent):
    """Run a single agent — restarts automatically on unexpected crash."""
    while True:
        try:
            agent.run()
        except Exception as e:
            agent.log(f"Crashed: {e}. Restarting in 60s…")
            time.sleep(60)


def main():
    agents = [
        ARIAAgent(),   # Marketing
        LEXAgent(),    # Legal
        FINAgent(),    # Finance
        REXAgent(),    # Sales
        DEVAgent(),    # Engineering
        UXRAgent(),    # User Research
    ]

    log("=" * 52)
    log("  NEXY HQ - All agents starting")
    log(f"  {len(agents)} agents online")
    log("=" * 52)

    threads = []
    for agent in agents:
        t = threading.Thread(
            target=run_agent,
            args=(agent,),
            name=agent.AGENT_NAME,
            daemon=True,
        )
        t.start()
        threads.append(t)
        log(f"  [OK] {agent.AGENT_NAME} - {agent.AGENT_ROLE} - started")
        time.sleep(0.5)  # stagger startup to avoid Firestore rate limits

    log("All agents running. Press Ctrl+C to stop.")

    # Graceful shutdown on SIGTERM (Cloud Run sends this before killing)
    def handle_shutdown(signum, frame):
        log("Shutdown signal received. Stopping agents…")
        for agent in agents:
            try:
                agent.set_status("idle")
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    # Keep main thread alive
    while True:
        time.sleep(30)
        alive = [t.name for t in threads if t.is_alive()]
        log(f"Heartbeat — {len(alive)}/6 agents alive: {', '.join(alive)}")


if __name__ == "__main__":
    main()
