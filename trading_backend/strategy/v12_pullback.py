from __future__ import annotations

from statistics import mean

from trading_backend.data.market_data import DailyBar
from trading_backend.models import StrategyCandidate, WatchlistItem


def simple_moving_average(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return mean(values[-period:])


def exponential_moving_average(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = mean(values[:period])
    for value in values[period:]:
        ema = ((value - ema) * multiplier) + ema
    return ema


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for idx in range(1, period + 1):
        delta = values[idx] - values[idx - 1]
        gains.append(max(delta, 0))
        losses.append(abs(min(delta, 0)))
    avg_gain = mean(gains)
    avg_loss = mean(losses)
    for idx in range(period + 1, len(values)):
        delta = values[idx] - values[idx - 1]
        gain = max(delta, 0)
        loss = abs(min(delta, 0))
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(bars: list[DailyBar], period: int = 14) -> float | None:
    if len(bars) <= period:
        return None
    true_ranges: list[float] = []
    prev_close = bars[0].close
    for bar in bars[1:]:
        tr = max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close))
        true_ranges.append(tr)
        prev_close = bar.close
    if len(true_ranges) < period:
        return None
    return mean(true_ranges[-period:])


class V12PullbackStrategy:
    strategy_tag = "v1.2_pullback_long"

    def evaluate(self, item: WatchlistItem, bars: list[DailyBar]) -> tuple[StrategyCandidate | None, str]:
        if len(bars) < 220:
            return None, "Insufficient daily history."

        closes = [bar.close for bar in bars]
        volumes = [bar.volume for bar in bars]
        ma50 = simple_moving_average(closes, 50)
        ma200 = simple_moving_average(closes, 200)
        ema10 = exponential_moving_average(closes, 10)
        rsi14 = rsi(closes[-20:], 14)
        atr14 = atr(bars[-30:], 14)
        if None in {ma50, ma200, ema10, rsi14, atr14}:
            return None, "Indicator set incomplete."

        latest = bars[-1]
        prev = bars[-2]
        if latest.close <= ma50 or ma50 <= ma200:
            return None, "Trend regime filter failed."
        if latest.close <= 20:
            return None, "Price below 20 USD."
        if atr14 / latest.close > 0.03:
            return None, "ATR exceeds 3% of price."

        avg_volume = mean(volumes[-20:])
        if avg_volume < item.min_avg_volume:
            return None, "Average volume below configured minimum."

        pullback_days = 0
        for idx in range(len(closes) - 2, max(-1, len(closes) - 6), -1):
            if idx < 1:
                break
            if closes[idx] < closes[idx - 1]:
                pullback_days += 1
            else:
                break
        if pullback_days == 0 or pullback_days > 3:
            return None, "Pullback duration not within 1-3 days."
        if not (35 <= rsi14 <= 60):
            return None, "RSI not within 35-60."

        pullback_slice = bars[-(pullback_days + 1):-1]
        pullback_low = min(bar.low for bar in pullback_slice) if pullback_slice else prev.low
        stalled_days = sum(1 for bar in pullback_slice if abs(bar.close - pullback_low) / max(pullback_low, 0.01) < 0.01)
        if stalled_days > 3:
            return None, "Pullback stalled near support for too long."

        candle_range = latest.high - latest.low
        if candle_range <= 0:
            return None, "Invalid candle range."
        close_location = (latest.close - latest.low) / candle_range
        if latest.close <= prev.high:
            return None, "Close did not finish above previous day high."
        if close_location < 0.70:
            return None, "Close not in top 30% of candle range."
        if latest.volume < avg_volume * 1.2:
            return None, "Breakout volume below 1.2x average."

        entry_trigger_price = prev.high * 1.001
        stop_price = min(pullback_low, entry_trigger_price - atr14)
        risk_per_share = entry_trigger_price - stop_price
        if risk_per_share <= 0:
            return None, "Risk per share is non-positive."

        score = round((close_location * 50) + (latest.volume / max(avg_volume, 1) * 20) + ((latest.close / ma50) - 1) * 1000, 4)
        return StrategyCandidate(
            symbol=item.symbol,
            sector=item.sector,
            score=score,
            confidence_score=min(1.0, max(0.1, score / 100)),
            close=latest.close,
            previous_high=prev.high,
            previous_low=prev.low,
            pullback_low=pullback_low,
            atr=atr14,
            rsi=rsi14,
            ma50=ma50,
            ma200=ma200,
            ema10=ema10,
            avg_volume=avg_volume,
            breakout_volume=latest.volume,
            pullback_days=pullback_days,
            entry_trigger_price=entry_trigger_price,
            stop_price=stop_price,
            risk_per_share=risk_per_share,
            rationale=(
                f"{item.symbol} passed regime, pullback, breakout, and volume filters. "
                f"Pullback={pullback_days}d, RSI={rsi14:.1f}, ATR={atr14:.2f}, close_location={close_location:.2f}."
            ),
            setup_date=latest.date,
            valid_for_date=latest.date,
        ), "ok"
