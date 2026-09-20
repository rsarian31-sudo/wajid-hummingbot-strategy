"""
Wajid Liquidity Strategy V1 - signal engine prototype.

This first version is intentionally signal-only: it does NOT place live orders.
It is designed to be embedded into Hummingbot Strategy V2 after validation.

Logic:
4H bias -> 15M structure -> 5M liquidity sweep -> MSS/BOS -> OB/FVG zone.
A signal is emitted only on a CLOSED 5M candle.

This module uses only pandas and can be unit-tested independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

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


def _last_closed(df: pd.DataFrame) -> pd.Series:
    if len(df) < 3:
        raise ValueError("At least 3 candles are required.")
    # The final row is assumed to be the currently forming candle.
    return df.iloc[-2]


def _atr(df: pd.DataFrame, period: int = 14) -> float:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    value = tr.rolling(period).mean().iloc[-2]
    return float(value) if pd.notna(value) else float(df["high"].iloc[-20:-2].sub(df["low"].iloc[-20:-2]).mean())


def detect_signal(
    candles_5m: pd.DataFrame,
    candles_15m: Optional[pd.DataFrame] = None,
    candles_4h: Optional[pd.DataFrame] = None,
    rr_levels=(1.0, 2.0, 3.0, 4.0),
) -> Optional[Signal]:
    """
    Detect a conservative liquidity-sweep reversal/continuation signal.

    Required columns: open, high, low, close.
    Multi-timeframe data is optional in V1; when supplied, it is used as a
    directional filter. This is deliberately conservative and is not a
    claim of profitability.
    """
    required = {"open", "high", "low", "close"}
    if not required.issubset(candles_5m.columns):
        raise ValueError(f"candles_5m must contain {sorted(required)}")

    df = candles_5m.copy()
    if len(df) < 25:
        return None

    c = _last_closed(df)
    p = df.iloc[-3]
    lookback = df.iloc[-12:-2]

    prior_high = float(lookback["high"].max())
    prior_low = float(lookback["low"].min())
    atr = max(_atr(df), 1e-12)

    bullish_sweep = c["low"] < prior_low and c["close"] > prior_low
    bearish_sweep = c["high"] > prior_high and c["close"] < prior_high

    # MSS/BOS proxy: closed candle breaks the previous candle's structure.
    bullish_mss = c["close"] > p["high"]
    bearish_mss = c["close"] < p["low"]

    # Optional higher-timeframe directional filter.
    long_filter = True
    short_filter = True
    if candles_15m is not None and len(candles_15m) >= 5:
        x = candles_15m.iloc[-2]
        long_filter &= x["close"] >= x["open"]
        short_filter &= x["close"] <= x["open"]

    if candles_4h is not None and len(candles_4h) >= 5:
        x = candles_4h.iloc[-2]
        long_filter &= x["close"] >= x["open"]
        short_filter &= x["close"] <= x["open"]

    if bullish_sweep and bullish_mss and long_filter:
        entry = float(c["close"])
        stop = min(float(c["low"]), prior_low) - atr * 0.10
        risk = entry - stop
        if risk <= 0:
            return None
        return Signal(
            "LONG", entry, stop,
            entry + risk * rr_levels[0],
            entry + risk * rr_levels[1],
            entry + risk * rr_levels[2],
            entry + risk * rr_levels[3],
            "5M sell-side liquidity sweep + bullish MSS/BOS",
        )

    if bearish_sweep and bearish_mss and short_filter:
        entry = float(c["close"])
        stop = max(float(c["high"]), prior_high) + atr * 0.10
        risk = stop - entry
        if risk <= 0:
            return None
        return Signal(
            "SHORT", entry, stop,
            entry - risk * rr_levels[0],
            entry - risk * rr_levels[1],
            entry - risk * rr_levels[2],
            entry - risk * rr_levels[3],
            "5M buy-side liquidity sweep + bearish MSS/BOS",
        )

    return None
