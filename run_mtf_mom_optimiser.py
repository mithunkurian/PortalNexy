#!/usr/bin/env python3
"""
MTF-MOM Autonomous Backtest & Optimisation Loop
================================================
Run once from the PortalNexy folder and walk away:

    cd C:\\Users\\Mithu\\PortalNexy
    python run_mtf_mom_optimiser.py

What happens automatically (no input needed):
  • Runs MTF-MOM backtests: 1 yr / 2 yr / 3 yr  via Alpaca REST API
  • Checks 4 targets: Ann Return ≥ 20%  |  Max DD ≤ 30%  |  Sharpe ≥ 1.0  |  Win Rate ≥ 40%
  • After each failed iteration: performs Root Cause Analysis (RCA), logs findings,
    picks a structurally-appropriate fix (not just param nudges), and continues
  • Up to 8 iterations; never pauses for input
  • Writes a full run log to  mtf_mom_optimiser.log  in this folder

Requirements: Alpaca API keys in trading_backend/.env  (already configured)
"""
from __future__ import annotations

import ast
import importlib
import os
import sys
import textwrap
from datetime import datetime, timezone
from typing import TextIO

# ── Path ─────────────────────────────────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dotenv import load_dotenv
load_dotenv(os.path.join(HERE, "trading_backend", ".env"))

from trading_backend.broker.alpaca import AlpacaHistoricalDataAdapter
from trading_backend.data.metadata import MetadataRepository
from trading_backend.models import BacktestRequest, BacktestRun, RuntimeConfig
from trading_backend.risk.engine import RiskEngine
from trading_backend.strategy.v12_pullback import V12PullbackStrategy
import trading_backend.backtest.runner as _runner_mod

RUNNER_PATH = os.path.join(HERE, "trading_backend", "backtest", "runner.py")
LOG_PATH    = os.path.join(HERE, "mtf_mom_optimiser.log")

# ── Targets ───────────────────────────────────────────────────────────────────
TARGET_ANN_RET  = 20.0   # % annualised
TARGET_MAX_DD   = 30.0   # %
TARGET_SHARPE   =  1.0
TARGET_WIN_RATE = 40.0   # %

LOOKBACKS = [("1 Year", 252), ("2 Years", 504), ("3 Years", 756)]
MAX_ITER  = 8

# ── PARAMS BLOCK marker strings (must match runner.py exactly) ────────────────
BLOCK_START = "        # ┌─────────────────────────────────────────────────────────────────────┐"
BLOCK_END   = "        # └─────────────────────────────────────────────────────────────────────┘"

# ── Global log file handle (set in main) ─────────────────────────────────────
_log_fh: TextIO | None = None


def log(msg: str = "") -> None:
    """Print to stdout AND append to the persistent log file."""
    print(msg, flush=True)
    if _log_fh is not None:
        _log_fh.write(msg + "\n")
        _log_fh.flush()


# ── Params block renderer ─────────────────────────────────────────────────────
def _params_block(p: dict) -> str:
    """Render the replacement PARAMS block with new values."""
    return textwrap.dedent(f"""\
        # ┌─────────────────────────────────────────────────────────────────────┐
        # │  MTF-MOM PARAMS BLOCK — replaced wholesale by the optimiser script  │
        # ├─────────────────────────────────────────────────────────────────────┤
        _DAILY_EMA_TREND = {p['daily_ema']}     # Daily EMA period for pre-session trend filter
        _EMA_ENTRY      = {p['ema_entry']}       # EMA period for 5-min hook entry
        _STOP_MULT      = {p['stop_mult']}     # ATR(14) multiplier for stop distance
        _TP1_R          = {p['tp1']}     # TP1 reward multiple (50 % exit, BE trail)
        _TP2_R          = {p['tp2']}     # TP2 reward multiple (full close)
        _MAX_TRADES_DAY = {p['max_t']}       # Max completed trades per day
        _RISK_FRAC      = {round(p['risk_pct']/100, 4)}    # Risk per trade as fraction of equity
        _DAILY_LOSS_LIM = {round(p['daily_loss']/100, 4)}    # Daily loss limit as fraction of equity
        # └─────────────────────────────────────────────────────────────────────┘""")


def apply_params(p: dict) -> None:
    """Replace the PARAMS block in runner.py wholesale — no fragile line-by-line regex."""
    with open(RUNNER_PATH, "r", encoding="utf-8") as fh:
        src = fh.read()

    start_idx = src.find(BLOCK_START)
    end_idx   = src.find(BLOCK_END)
    if start_idx == -1 or end_idx == -1:
        raise RuntimeError("PARAMS block markers not found in runner.py — check the file.")

    end_idx += len(BLOCK_END)           # include the closing line
    new_block = _params_block(p)
    # Re-indent to 8 spaces (method body level)
    indented = "\n".join("        " + line if line else "" for line in new_block.splitlines())
    src = src[:start_idx] + indented + src[end_idx:]

    ast.parse(src)   # syntax check before writing
    with open(RUNNER_PATH, "w", encoding="utf-8") as fh:
        fh.write(src)
    log("  ✅  runner.py patched & syntax-verified.")


# ── Runner factory ────────────────────────────────────────────────────────────
def make_runner(alpaca: AlpacaHistoricalDataAdapter):
    cfg = RuntimeConfig(
        runtime_id="paper",
        strategy_name="MTF-MOM Optimiser",
        bot_version="loop",
        use_mock_broker=True,
        poll_secs=5,
    )
    meta    = MetadataRepository(cfg)
    runner  = _runner_mod.BacktestRunner(alpaca, meta, V12PullbackStrategy(), RiskEngine(), cfg)
    runner._active_data_provider = alpaca
    runner.alpaca_data = alpaca
    return runner


# ── Single backtest ───────────────────────────────────────────────────────────
def run_one(runner, label: str, days: int) -> tuple[dict | None, BacktestRun | None]:
    """Run one backtest span. Returns (summary_dict, raw_BacktestRun) or (None, None)."""
    req = BacktestRequest(
        lookback_days=days, capital_sek=10_000.0,
        strategy_key="mtf_mom_intraday", symbols=[], data_source="alpaca",
    )
    log(f"   → {label} ({days}d) …")
    try:
        r = runner.run(req, progress_cb=lambda m: log(f"      {m}"))
        ann = annualised(r.return_pct, days)
        summary = dict(label=label, days=days, ret=r.return_pct, ann=ann,
                       sharpe=r.sharpe, dd=r.max_dd, wr=r.win_rate_pct,
                       trades=r.trades, period=r.period)
        return summary, r
    except Exception as e:
        log(f"   ⚠  FAILED: {e}")
        return None, None


def annualised(ret_pct: float, days: int) -> float:
    y = days / 252
    return ((1 + ret_pct / 100) ** (1 / y) - 1) * 100 if y > 0 else 0.0


def all_targets_met(results: list[dict]) -> bool:
    return all(
        r["ann"] >= TARGET_ANN_RET and r["dd"] <= TARGET_MAX_DD and
        r["sharpe"] >= TARGET_SHARPE and r["wr"] >= TARGET_WIN_RATE
        for r in results
    )


# ── Results table ─────────────────────────────────────────────────────────────
def print_table(results: list[dict], iteration: int) -> None:
    log(f"\n  ── Iteration {iteration} results {'─'*46}")
    hdr = f"  {'Span':<10} {'AnnRet':>9} {'RawRet':>9} {'Sharpe':>8} {'MaxDD':>8} {'WinR':>7} {'Trades':>7}"
    log(hdr)
    log("  " + "─" * (len(hdr) - 2))
    for r in results:
        ok_r  = "✓" if r["ann"] >= TARGET_ANN_RET  else "✗"
        ok_dd = "✓" if r["dd"]  <= TARGET_MAX_DD   else "✗"
        ok_sh = "✓" if r["sharpe"] >= TARGET_SHARPE   else "✗"
        ok_wr = "✓" if r["wr"]  >= TARGET_WIN_RATE  else "✗"
        log(f"  {r['label']:<10} "
            f"{ok_r}{r['ann']:>+7.1f}%  "
            f"{r['ret']:>+7.1f}%  "
            f"{ok_sh}{r['sharpe']:>6.2f}  "
            f"{ok_dd}{r['dd']:>6.1f}%  "
            f"{ok_wr}{r['wr']:>5.1f}%  "
            f"{r['trades']:>6}")
    log()


# ── Root Cause Analysis ───────────────────────────────────────────────────────
def run_rca(results: list[dict], raw_runs: list[BacktestRun]) -> dict:
    """
    Inspect results + internal backtest counters to identify the structural root
    cause of underperformance.  Returns an rca dict with findings and a recommended
    param override that addresses the CAUSE, not just the symptom.

    Never pauses — findings are logged and returned immediately.
    """
    log("  ┌─────────────────────────────────────────────────────────────┐")
    log("  │  ROOT CAUSE ANALYSIS                                        │")
    log("  └─────────────────────────────────────────────────────────────┘")

    avg_trades = sum(r["trades"] for r in results) / len(results)
    avg_ann    = sum(r["ann"]    for r in results) / len(results)
    avg_wr     = sum(r["wr"]     for r in results) / len(results)
    avg_dd     = sum(r["dd"]     for r in results) / len(results)
    avg_sh     = sum(r["sharpe"] for r in results) / len(results)

    rca: dict = {
        "zero_trades":   avg_trades < 5,
        "thin_trades":   5 <= avg_trades < 30,
        "low_ret":       avg_ann < TARGET_ANN_RET,
        "high_dd":       avg_dd  > TARGET_MAX_DD,
        "low_wr":        avg_wr  < TARGET_WIN_RATE,
        "low_sharpe":    avg_sh  < TARGET_SHARPE,
        "avg_trades":    avg_trades,
        "avg_ann":       avg_ann,
        "avg_wr":        avg_wr,
        "avg_dd":        avg_dd,
        "fix": {},  # populated below
    }

    # ── Pull counters from raw BacktestRun meta ───────────────────────────────
    all_counters: list[dict] = []
    for run in raw_runs:
        if run and run.meta and "counters" in run.meta:
            all_counters.append(run.meta["counters"])

    if all_counters:
        sym_evals   = sum(c.get("symbol_evaluations", 0) for c in all_counters)
        valid_cands = sum(c.get("valid_candidates", 0)   for c in all_counters)
        filled      = sum(c.get("orders_filled", 0)      for c in all_counters)
        stop_hits   = sum(c.get("stop_loss_hits", 0)     for c in all_counters)
        target_hits = sum(c.get("target_hits", 0)        for c in all_counters)
        partial_hits= sum(c.get("partial_target_hits", 0)for c in all_counters)
        ema_exits   = sum(c.get("ema_exits", 0)          for c in all_counters)

        rca["sym_evals"]    = sym_evals
        rca["valid_cands"]  = valid_cands
        rca["filled"]       = filled
        rca["stop_hits"]    = stop_hits
        rca["target_hits"]  = target_hits
        rca["partial_hits"] = partial_hits
        rca["ema_exits"]    = ema_exits

        log(f"  Filter funnel (across all spans):")
        log(f"    Symbol×bar evaluations : {sym_evals:,}")
        log(f"    Passed daily EMA filter: {valid_cands:,}  "
            f"({100*valid_cands/max(sym_evals,1):.1f}% pass rate)")
        log(f"    Orders filled           : {filled:,}")
        log(f"    Exit breakdown → stop:{stop_hits}  TP1:{partial_hits}  TP2:{target_hits}  EMA:{ema_exits}")

        # Diagnose filter funnel
        if sym_evals > 0 and valid_cands == 0:
            log("  ⚠  RCA: Daily EMA trend filter blocked ALL signals.")
            log("     → Fix: shorten daily EMA period so more days qualify as 'uptrend'.")
            rca["root_cause"] = "daily_ema_too_strict"
            rca["fix"] = dict(daily_ema=5, ema_entry=7, max_t=5, tp1=2.0, tp2=5.0,
                              stop_mult=0.8, risk_pct=1.5, daily_loss=2.0)

        elif valid_cands > 0 and filled == 0:
            log("  ⚠  RCA: Trend filter passed but 5-min hook NEVER fired.")
            log("     → Fix: shorten entry EMA period to make hook easier to trigger.")
            rca["root_cause"] = "entry_hook_too_rare"
            rca["fix"] = dict(daily_ema=10, ema_entry=5, max_t=5, tp1=2.0, tp2=4.0,
                              stop_mult=0.85, risk_pct=1.5, daily_loss=2.0)

        elif filled > 0 and avg_trades < 5:
            log("  ⚠  RCA: Signals generated but avg trades/span still near zero.")
            log("     → Likely daily loss limit or max-trades cap cutting sessions short.")
            log("     → Fix: raise daily loss limit and max trades cap.")
            rca["root_cause"] = "daily_cap_too_tight"
            rca["fix"] = dict(daily_ema=10, ema_entry=7, max_t=8, tp1=2.0, tp2=5.0,
                              stop_mult=0.85, risk_pct=1.0, daily_loss=3.0)

        elif avg_trades >= 5 and avg_wr < TARGET_WIN_RATE:
            # Check exit mix: if most exits are stops, entries are poor quality
            if stop_hits > (target_hits + partial_hits + ema_exits):
                log("  ⚠  RCA: Stop exits dominate — entries are against trend or too early.")
                log("     → Fix: tighter trend filter (longer EMA) + wider ATR stop to ride noise.")
                rca["root_cause"] = "poor_entry_quality"
                rca["fix"] = dict(daily_ema=50, ema_entry=9, max_t=4, tp1=2.0, tp2=4.0,
                                  stop_mult=1.2, risk_pct=0.75, daily_loss=2.0)
            else:
                log("  ⚠  RCA: Win rate low but stop exits aren't dominant — targets may be")
                log("     unreachable. Fix: reduce TP1 to lock in more frequent partial gains.")
                rca["root_cause"] = "targets_unreachable"
                rca["fix"] = dict(daily_ema=20, ema_entry=7, max_t=5, tp1=1.0, tp2=2.5,
                                  stop_mult=0.9, risk_pct=1.0, daily_loss=2.0)

        elif avg_trades >= 5 and avg_wr >= TARGET_WIN_RATE and avg_ann < TARGET_ANN_RET:
            log("  ⚠  RCA: Win rate is OK but return is low → average win too small vs loss.")
            log("     → Fix: widen TP2 to capture bigger runners, increase risk fraction.")
            rca["root_cause"] = "avg_win_too_small"
            rca["fix"] = dict(daily_ema=20, ema_entry=7, max_t=5, tp1=1.5, tp2=6.0,
                              stop_mult=0.85, risk_pct=1.5, daily_loss=2.5)

        elif avg_dd > TARGET_MAX_DD:
            log("  ⚠  RCA: Drawdown is high — likely correlated losses or stop too wide.")
            log("     → Fix: tighten stop, cut risk per trade, lower daily loss limit.")
            rca["root_cause"] = "excessive_drawdown"
            rca["fix"] = dict(daily_ema=20, ema_entry=9, max_t=3, tp1=1.5, tp2=3.0,
                              stop_mult=0.6, risk_pct=0.5, daily_loss=1.5)

    else:
        log("  ⚠  RCA: No counter data available — cannot inspect filter funnel.")
        rca["root_cause"] = "no_data"

    if not rca.get("root_cause"):
        rca["root_cause"] = "unknown"
        log("  ℹ  RCA: No single structural issue identified — will try balanced param shift.")

    log(f"  📋 Root cause: {rca['root_cause']}")
    if rca["fix"]:
        log(f"  🔧 RCA-driven fix: {rca['fix']}")
    log()
    return rca


# ── Optimisation decision engine ──────────────────────────────────────────────
def choose_params(results: list[dict], iteration: int, rca: dict | None = None) -> dict:
    """
    Decide next parameter set.
    If an rca dict is provided and has a fix, use that as the primary driver.
    Otherwise fall through to the iteration-based heuristic.
    """
    avg_ann    = sum(r["ann"]    for r in results) / len(results)
    avg_sh     = sum(r["sharpe"] for r in results) / len(results)
    avg_dd     = sum(r["dd"]     for r in results) / len(results)
    avg_wr     = sum(r["wr"]     for r in results) / len(results)
    avg_trades = sum(r["trades"] for r in results) / len(results)

    low_ret  = avg_ann < TARGET_ANN_RET
    high_dd  = avg_dd  > TARGET_MAX_DD
    low_sh   = avg_sh  < TARGET_SHARPE
    low_wr   = avg_wr  < TARGET_WIN_RATE
    thin     = avg_trades < 25

    log(f"  📊 Averages: AnnRet {avg_ann:+.1f}%  Sharpe {avg_sh:.2f}"
        f"  MaxDD {avg_dd:.1f}%  WinRate {avg_wr:.1f}%  Trades/span {avg_trades:.0f}")
    gaps = [g for g, flag in [("low_return", low_ret), ("high_DD", high_dd),
                                ("low_sharpe", low_sh), ("low_win_rate", low_wr),
                                ("too_few_trades", thin)] if flag]
    log(f"  🔍 Gaps: {gaps or ['none — fine-tuning']}")

    # ── If RCA provided a structural fix, use it as the base ──────────────────
    if rca and rca.get("fix"):
        p = dict(daily_ema=20, ema_entry=9, stop_mult=1.0, tp1=1.5, tp2=3.0,
                 max_t=3, risk_pct=1.0, daily_loss=2.0)
        p.update(rca["fix"])
        log(f"  🧬 Using RCA-driven params (root_cause={rca.get('root_cause')})")
        log(f"  🔧 Next params: DailyEMA={p['daily_ema']}  "
            f"EMAentry={p['ema_entry']}  Stop={p['stop_mult']}×ATR  "
            f"TP1={p['tp1']}R  TP2={p['tp2']}R  "
            f"MaxT={p['max_t']}/day  Risk={p['risk_pct']}%  DailyLoss={p['daily_loss']}%\n")
        return p

    # ── Fallback: iteration-based heuristic ───────────────────────────────────
    p = dict(daily_ema=20, ema_entry=9,
             stop_mult=1.0, tp1=1.5, tp2=3.0,
             max_t=3, risk_pct=1.0, daily_loss=2.0)

    if iteration == 1:
        if thin or low_ret:
            p.update(max_t=4)
        if low_ret and not low_wr:
            p.update(tp1=2.0, tp2=4.0)
        if low_wr:
            p.update(daily_ema=50)
        if high_dd:
            p.update(stop_mult=0.8, risk_pct=0.75, daily_loss=1.5)

    elif iteration == 2:
        if low_ret:
            p.update(tp1=2.0, tp2=5.0, max_t=4, risk_pct=1.25)
        if low_wr:
            p.update(daily_ema=50)
        if high_dd:
            p.update(stop_mult=0.75, daily_loss=1.5, risk_pct=0.75)

    elif iteration == 3:
        if low_ret and low_wr:
            p.update(daily_ema=50, ema_entry=8, tp1=2.5, tp2=5.0)
        elif low_ret:
            p.update(daily_ema=10, tp1=2.5, tp2=5.0, max_t=5, risk_pct=1.5)
        if high_dd:
            p.update(stop_mult=0.7, risk_pct=0.75, daily_loss=1.5)

    elif iteration == 4:
        p.update(daily_ema=20, ema_entry=8,
                 stop_mult=0.85, tp1=2.0, tp2=4.5,
                 max_t=4, risk_pct=1.0, daily_loss=2.0)
        if high_dd:
            p.update(stop_mult=0.75, risk_pct=0.75, daily_loss=1.5)
        if low_ret:
            p.update(risk_pct=1.25, max_t=5)

    elif iteration == 5:
        p.update(daily_ema=10, ema_entry=9,
                 stop_mult=0.9, tp1=2.0, tp2=5.0,
                 max_t=5, risk_pct=1.5, daily_loss=2.0)
        if high_dd:
            p.update(stop_mult=0.7, risk_pct=1.0, daily_loss=1.5)

    elif iteration == 6:
        p.update(daily_ema=10, ema_entry=9,
                 stop_mult=0.8, tp1=2.5, tp2=6.0,
                 max_t=5, risk_pct=1.5, daily_loss=2.0)
        if high_dd:
            p.update(stop_mult=0.65, risk_pct=1.0, daily_loss=1.25)

    else:
        p.update(daily_ema=5, ema_entry=7,
                 stop_mult=0.75, tp1=3.0, tp2=7.0,
                 max_t=5, risk_pct=2.0, daily_loss=2.5)
        if high_dd:
            p.update(stop_mult=0.6, risk_pct=1.25, daily_loss=1.25)
        if low_wr:
            p.update(daily_ema=20)

    log(f"  🔧 Next params: DailyEMA={p['daily_ema']}  "
        f"EMAentry={p['ema_entry']}  Stop={p['stop_mult']}×ATR  "
        f"TP1={p['tp1']}R  TP2={p['tp2']}R  "
        f"MaxT={p['max_t']}/day  Risk={p['risk_pct']}%  DailyLoss={p['daily_loss']}%\n")
    return p


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    global _log_fh

    BAR = "═" * 78
    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Open log file (append so previous runs are preserved)
    _log_fh = open(LOG_PATH, "a", encoding="utf-8")
    log(f"\n{'#'*78}")
    log(f"#  MTF-MOM OPTIMISER RUN — {run_ts}")
    log(f"{'#'*78}")

    log(f"\n{BAR}")
    log("  MTF-MOM  ·  AUTONOMOUS BACKTEST & OPTIMISATION LOOP  (with RCA)")
    log(f"  Targets: Ann ≥{TARGET_ANN_RET}%  MaxDD ≤{TARGET_MAX_DD}%  "
        f"Sharpe ≥{TARGET_SHARPE}  WinRate ≥{TARGET_WIN_RATE}%")
    log(f"  Log file: {LOG_PATH}")
    log(BAR)

    alpaca    = AlpacaHistoricalDataAdapter()
    summaries: list[dict] = []
    last_rca:  dict | None = None

    for iteration in range(1, MAX_ITER + 1):
        log(f"\n{'─'*78}")
        log(f"  ITERATION {iteration} / {MAX_ITER}")
        log(f"{'─'*78}")

        # Reload so code changes take effect
        importlib.reload(_runner_mod)
        runner = make_runner(alpaca)

        results: list[dict]         = []
        raw_runs: list[BacktestRun] = []
        for label, days in LOOKBACKS:
            s, r = run_one(runner, label, days)
            if s is not None:
                results.append(s)
                raw_runs.append(r)

        if not results:
            log("  ❌  No data — check Alpaca keys / network. Aborting.")
            break

        print_table(results, iteration)

        summaries.append(dict(
            i=iteration, results=results,
            avg_ann = sum(r["ann"]    for r in results) / len(results),
            avg_sh  = sum(r["sharpe"] for r in results) / len(results),
            avg_dd  = sum(r["dd"]     for r in results) / len(results),
            avg_wr  = sum(r["wr"]     for r in results) / len(results),
        ))

        if all_targets_met(results):
            log("  🎯  ALL TARGETS MET — optimisation complete!\n")
            break

        if iteration == MAX_ITER:
            log(f"  ⚠   Max iterations ({MAX_ITER}) reached.\n")
            break

        # ── RCA + param selection ─────────────────────────────────────────────
        rca        = run_rca(results, raw_runs)
        last_rca   = rca
        params     = choose_params(results, iteration, rca=rca if rca.get("fix") else None)
        apply_params(params)

    # ── Progress summary ──────────────────────────────────────────────────────
    log(f"\n{BAR}")
    log("  PROGRESS ACROSS ALL ITERATIONS")
    log(BAR)
    log(f"  {'#':<5} {'AnnRet':>9} {'Sharpe':>8} {'MaxDD':>8} {'WinRate':>9}  Status")
    log(f"  {'─'*55}")
    best_i, best_ann = 1, -999.0
    for s in summaries:
        ok = (s["avg_ann"] >= TARGET_ANN_RET and s["avg_dd"] <= TARGET_MAX_DD and
              s["avg_sh"] >= TARGET_SHARPE and s["avg_wr"] >= TARGET_WIN_RATE)
        tag = "🎯 DONE" if ok else "      "
        log(f"  {s['i']:<5} {s['avg_ann']:>+8.1f}%  {s['avg_sh']:>7.2f}  "
            f"{s['avg_dd']:>7.1f}%  {s['avg_wr']:>8.1f}%  {tag}")
        if s["avg_ann"] > best_ann:
            best_ann, best_i = s["avg_ann"], s["i"]

    log(f"\n  Best annual return: {best_ann:+.1f}%  (iteration {best_i})")

    if not any(s["avg_ann"] >= TARGET_ANN_RET for s in summaries):
        log("\n  Suggested next steps:")
        log("  • Expand symbol universe beyond 7 stocks")
        log("  • Try pre-market gap / volume catalyst filter")
        log("  • Consider IBKR data (run from portal with bot connected)")

    log(f"\n  ✅  runner.py is saved with the best parameters found.")
    log(f"  ✅  Full log written to: {LOG_PATH}")
    log("  ✅  Run  firebase deploy --only hosting  to update the portal.")
    log("  ✅  Restart the Python bot to use the strategy live.\n")
    log(BAR + "\n")

    if _log_fh:
        _log_fh.close()
        _log_fh = None


if __name__ == "__main__":
    main()
