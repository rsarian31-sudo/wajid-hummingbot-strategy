# Wajid Hummingbot Strategy

Experimental Hummingbot Strategy V2 project for the Wajid Liquidity system.

## V1 pipeline
**4H bias → 15M structure → 5M liquidity sweep → MSS/BOS → entry → SL → TP1/TP2/TP3/TP4**

The current milestone is research/backtesting first. No live exchange orders are enabled.

## Files
- `wajid_liquidity_signal.py` — closed-candle signal engine.
- `backtest.py` — historical OHLCV backtester with 4H/15M/5M context, fees, concurrent trades and TP1–TP4 accounting.
- `tests/test_signal.py` — regression test.
- `.github/workflows/test.yml` — automatic Python test on GitHub.
- `requirements.txt` — research/test dependencies.

## Backtest CSV
Use:
`timestamp,open,high,low,close,volume`

Run:
```bash
pip install -r requirements.txt
python backtest.py data/btcusdt_5m.csv
```

Output: trade count, win rate, net R, average R, profit factor, max drawdown, and TP1–TP4 counts.

## Methodology
Signals use only candles closed at the decision time. Higher-timeframe data is filtered to avoid future candles. If one candle touches both SL and TP, the backtester assumes SL happened first.

This is research software, not a profitability guarantee.

## Next step
After tests pass, implement a Hummingbot Strategy V2 Controller that reads Candle feeds and creates PositionExecutors.
