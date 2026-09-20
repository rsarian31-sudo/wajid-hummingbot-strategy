"""
Wajid Liquidity Strategy V2.

Signal flow:
4H structure bias -> 15M structure confirmation -> 5M liquidity sweep
-> 5M MSS/BOS -> entry with sweep-based SL -> TP1-TP4 at 1R-4R.

Only completed candles are used. The final row supplied to detect_signal()
is treated as the currently-forming candle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Signal:
    side: str
    entry: float
    stop: float
    tp1: float
    tp2: float
    tp3: float
    tp4: float
    reason: str


def _closed(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) < 3:
        return pd.DataFrame(columns=df.columns)
    return df.iloc[:-1]


def _atr(df: pd.DataFrame, period: int = 14) -> float:
    closed = _closed(df.tail(period + 25))
    if len(closed) < 3:
        return 0.0
    prev_close = closed["close"].shift(1)
    tr = pd.concat(
        [
            closed["high"] - closed["low"],
            (closed["high"] - prev_close).abs(),
            (closed["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    value = tr.rolling(period, min_periods=max(3, period // 2)).mean().iloc[-1]
    if pd.notna(value) and value > 0:
        return float(value)
    fallback = (closed["high"] - closed["low"]).tail(20).mean()
    return float(fallback) if pd.notna(fallback) and fallback > 0 else 0.0


def _swing_points(df: pd.DataFrame, left: int = 2, right: int = 2):
    """Return confirmed swing highs/lows using vectorized numpy windows."""
    width = left + right + 1
    if len(df) < width:
        return [], []

    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    high_windows = np.lib.stride_tricks.sliding_window_view(highs, width)
    low_windows = np.lib.stride_tricks.sliding_window_view(lows, width)

    center_high = high_windows[:, left]
    center_low = low_windows[:, left]
    high_mask = (
        (center_high > np.max(high_windows[:, :left], axis=1))
        & (center_high >= np.max(high_windows[:, left + 1 :], axis=1))
    )
    low_mask = (
        (center_low < np.min(low_windows[:, :left], axis=1))
        & (center_low <= np.min(low_windows[:, left + 1 :], axis=1))
    )

    offset = left
    high_indices = np.flatnonzero(high_mask) + offset
    low_indices = np.flatnonzero(low_mask) + offset
    return (
        [(int(i), float(highs[i])) for i in high_indices],
        [(int(i), float(lows[i])) for i in low_indices],
    )


def _structure_bias(df: pd.DataFrame) -> Optional[str]:
    # Only recent structure is needed; bounding this window keeps the
    # historical backtest linear rather than repeatedly scanning all history.
    closed = _closed(df.tail(121))
    if len(closed) < 10:
        return None
    highs, lows = _swing_points(closed)
    if len(highs) < 2 or len(lows) < 2:
        return None
    higher_high = highs[-1][1] > highs[-2][1]
    higher_low = lows[-1][1] > lows[-2][1]
    lower_high = highs[-1][1] < highs[-2][1]
    lower_low = lows[-1][1] < lows[-2][1]
    if higher_high and higher_low:
        return "LONG"
    if lower_high and lower_low:
        return "SHORT"
    return None


def _latest_swing_before(df: pd.DataFrame, side: str) -> Optional[float]:
    highs, lows = _swing_points(df.tail(81))
    points = highs if side == "HIGH" else lows
    return points[-1][1] if points else None


def detect_signal(
    candles_5m: pd.DataFrame,
    candles_15m: Optional[pd.DataFrame] = None,
    candles_4h: Optional[pd.DataFrame] = None,
    rr_levels=(1.0, 2.0, 3.0, 4.0),
    sweep_lookback: int = 12,
    atr_buffer: float = 0.10,
) -> Optional[Signal]:
    required = {"open", "high", "low", "close"}
    if not required.issubset(candles_5m.columns):
        raise ValueError(f"candles_5m must contain {sorted(required)}")

    df = candles_5m.copy()
    if len(df) < 30:
        return None

    closed = _closed(df)
    c = closed.iloc[-1]
    pre = closed.iloc[:-1]
    if len(pre) < 10:
        return None

    long_filter = True
    short_filter = True

    if candles_15m is not None:
        bias15 = _structure_bias(candles_15m)
        if bias15 is not None:
            long_filter &= bias15 == "LONG"
            short_filter &= bias15 == "SHORT"

    if candles_4h is not None:
        bias4h = _structure_bias(candles_4h)
        if bias4h is not None:
            long_filter &= bias4h == "LONG"
            short_filter &= bias4h == "SHORT"

    recent = pre.tail(sweep_lookback)
    prior_high = float(recent["high"].max())
    prior_low = float(recent["low"].min())

    # Sweep must occur through recent liquidity and close back inside the range.
    bullish_sweep = float(c["low"]) < prior_low and float(c["close"]) > prior_low
    bearish_sweep = float(c["high"]) > prior_high and float(c["close"]) < prior_high

    # MSS/BOS must break a confirmed swing, not merely the previous candle.
    swing_high = _latest_swing_before(pre, "HIGH")
    swing_low = _latest_swing_before(pre, "LOW")
    bullish_mss = swing_high is not None and float(c["close"]) > swing_high
    bearish_mss = swing_low is not None and float(c["close"]) < swing_low

    atr = max(_atr(df), 1e-12)

    if bullish_sweep and bullish_mss and long_filter:
        entry = float(c["close"])
        stop = min(float(c["low"]), prior_low) - atr * atr_buffer
        risk = entry - stop
        if risk <= 0:
            return None
        return Signal(
            "LONG",
            entry,
            stop,
            entry + risk * rr_levels[0],
            entry + risk * rr_levels[1],
            entry + risk * rr_levels[2],
            entry + risk * rr_levels[3],
            "4H/15M bullish structure + 5M sell-side liquidity sweep + confirmed MSS/BOS",
        )

    if bearish_sweep and bearish_mss and short_filter:
        entry = float(c["close"])
        stop = max(float(c["high"]), prior_high) + atr * atr_buffer
        risk = stop - entry
        if risk <= 0:
            return None
        return Signal(
            "SHORT",
            entry,
            stop,
            entry - risk * rr_levels[0],
            entry - risk * rr_levels[1],
            entry - risk * rr_levels[2],
            entry - risk * rr_levels[3],
            "4H/15M bearish structure + 5M buy-side liquidity sweep + confirmed MSS/BOS",
        )

    return None
