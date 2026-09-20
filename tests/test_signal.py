import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from wajid_liquidity_signal_v2 import detect_signal


def test_bullish_sweep_breaks_confirmed_swing():
    rows = []
    for i in range(30):
        rows.append(
            {
                "open": 100.0,
                "high": 100.8,
                "low": 99.6,
                "close": 100.2,
            }
        )

    rows.extend(
        [
            {"open": 100.0, "high": 101.0, "low": 99.5, "close": 100.0},
            {"open": 100.0, "high": 100.8, "low": 99.7, "close": 100.2},
            {"open": 100.2, "high": 102.0, "low": 100.0, "close": 101.0},
            {"open": 101.0, "high": 101.0, "low": 99.8, "close": 100.0},
            {"open": 100.0, "high": 100.9, "low": 99.6, "close": 100.0},
            {"open": 100.0, "high": 100.8, "low": 98.8, "close": 99.5},
            {"open": 99.5, "high": 101.0, "low": 99.2, "close": 100.0},
            {"open": 100.0, "high": 100.9, "low": 99.5, "close": 100.2},
            # Completed candle: sweeps sell-side liquidity and closes above
            # the confirmed swing high at 102.0.
            {"open": 100.2, "high": 102.5, "low": 98.0, "close": 102.2},
            # Current/forming candle; V2 must ignore it.
            {"open": 102.2, "high": 102.6, "low": 101.8, "close": 102.3},
        ]
    )

    signal = detect_signal(pd.DataFrame(rows))

    assert signal is not None
    assert signal.side == "LONG"
    assert "confirmed MSS/BOS" in signal.reason
    assert signal.tp4 > signal.tp3 > signal.tp2 > signal.tp1 > signal.entry > signal.stop


def test_forming_candle_is_not_used():
    rows = []
    for _ in range(30):
        rows.append({"open": 100.0, "high": 100.8, "low": 99.6, "close": 100.2})
    rows.append({"open": 100.2, "high": 101.0, "low": 99.0, "close": 100.5})
    rows.append({"open": 100.5, "high": 105.0, "low": 98.0, "close": 104.0})
    # This row would create a false break if the forming candle were used.
    rows.append({"open": 104.0, "high": 110.0, "low": 90.0, "close": 109.0})

    signal = detect_signal(pd.DataFrame(rows))
    assert signal is None
