# Wajid Hummingbot Strategy

Experimental Hummingbot Strategy V2 project for the Wajid Liquidity system.

## V1 scope

The first milestone is **signal validation only**. No live orders are placed.

Planned flow:

**4H bias → 15M structure → 5M liquidity sweep → MSS/BOS → OB/FVG → entry → SL → TP1/TP2/TP3/TP4**

The initial detector is intentionally conservative and uses closed candles only. It is a prototype, not a profitability guarantee.

## Files

- `wajid_liquidity_signal.py` — exchange-independent signal engine prototype.
- Future Hummingbot integration will use Strategy V2 / Controllers and Position Executors.

## Validation plan

1. Unit-test signal detection.
2. Connect Hummingbot candle feeds.
3. Run historical/backtest evaluation.
4. Paper trade.
5. Only after validation consider live execution.

## Hummingbot commands later

For a configurable V2 script, Hummingbot uses:

```text
create --v2-config <script_name>
start --v2 <config_file_name.yml>
```

Controllers are intended for the production-grade version.

## Important

This repository is experimental. A backtest or paper result does not guarantee future live performance.
