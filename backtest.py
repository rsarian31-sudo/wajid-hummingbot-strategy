"""
Standalone historical backtester for Wajid Liquidity Strategy V1.

CSV columns:
timestamp,open,high,low,close,volume

Uses closed candles only and supports 4H/15M/5M context, TP1-TP4
partial exits, SL, fees, concurrent positions, and cumulative R.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from typing import List
import pandas as pd
from wajid_liquidity_signal import detect_signal

def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"timestamp", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.set_index("timestamp").sort_index()

def ohlcv_resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = {"open":"first","high":"max","low":"min","close":"last"}
    if "volume" in df.columns:
        agg["volume"] = "sum"
    return df.resample(rule, label="right", closed="right").agg(agg).dropna()

def run_backtest(df_5m, df_15m=None, df_4h=None, fee_rate=0.0004, max_open_trades=3):
    trades: List[dict] = []
    open_positions: List[dict] = []

    for i in range(25, len(df_5m)):
        candle = df_5m.iloc[i]
        closed_5m = df_5m.iloc[:i+1]

        still_open = []
        for pos in open_positions:
            side = pos["side"]
            hit_sl = candle["low"] <= pos["stop"] if side == "LONG" else candle["high"] >= pos["stop"]
            if hit_sl:
                r = pos["realized_r"] - pos["remaining"] - fee_rate * 2
                trades.append({**pos["meta"], "exit_time": candle.name.isoformat(),
                               "tps_hit": pos["tps_hit"], "realized_r": r, "exit_reason":"SL"})
                continue

            while pos["next_tp"] < 4:
                tp = pos["tps"][pos["next_tp"]]
                if candle["low"] <= tp <= candle["high"]:
                    pos["realized_r"] += 0.25 * (pos["next_tp"] + 1)
                    pos["remaining"] -= 0.25
                    pos["tps_hit"] += 1
                    pos["next_tp"] += 1
                else:
                    break

            if pos["tps_hit"] == 4:
                trades.append({**pos["meta"], "exit_time": candle.name.isoformat(),
                               "tps_hit":4, "realized_r":pos["realized_r"]-fee_rate*2,
                               "exit_reason":"TP4"})
            else:
                still_open.append(pos)
        open_positions = still_open

        if len(open_positions) >= max_open_trades:
            continue

        t15 = df_15m.loc[df_15m.index <= candle.name] if df_15m is not None else None
        t4h = df_4h.loc[df_4h.index <= candle.name] if df_4h is not None else None
        signal = detect_signal(closed_5m, t15, t4h)
        if signal is None:
            continue

        risk = abs(signal.entry - signal.stop)
        if risk <= 0:
            continue
        open_positions.append({
            "side":signal.side, "stop":signal.stop,
            "tps":[signal.tp1,signal.tp2,signal.tp3,signal.tp4],
            "next_tp":0, "remaining":1.0, "tps_hit":0, "realized_r":0.0,
            "meta":{"entry_time":candle.name.isoformat(),"side":signal.side,
                    "entry":signal.entry,"stop":signal.stop,"tp1":signal.tp1,
                    "tp2":signal.tp2,"tp3":signal.tp3,"tp4":signal.tp4}
        })

    last = df_5m.iloc[-1]
    for pos in open_positions:
        risk = abs(pos["meta"]["entry"] - pos["stop"])
        move_r = ((last["close"]-pos["meta"]["entry"])/risk
                  if pos["side"]=="LONG" else (pos["meta"]["entry"]-last["close"])/risk)
        trades.append({**pos["meta"],"exit_time":df_5m.index[-1].isoformat(),
                       "tps_hit":pos["tps_hit"],
                       "realized_r":pos["realized_r"]+pos["remaining"]*move_r-fee_rate*2,
                       "exit_reason":"END_OF_DATA"})

    result = pd.DataFrame(trades)
    if result.empty:
        return result, {"trades":0,"win_rate_pct":0.0,"net_r":0.0,"avg_r":0.0,
                         "profit_factor":0.0,"max_drawdown_r":0.0,
                         "tp1_plus_trades":0,"tp2_plus_trades":0,"tp3_plus_trades":0,"tp4_trades":0}

    result["cum_r"] = result["realized_r"].cumsum()
    wins = result.loc[result["realized_r"] > 0, "realized_r"]
    losses = result.loc[result["realized_r"] < 0, "realized_r"]
    dd = result["cum_r"] - result["cum_r"].cummax()
    stats = {
        "trades":int(len(result)),
        "win_rate_pct":round(float((result["realized_r"]>0).mean()*100),2),
        "net_r":round(float(result["realized_r"].sum()),4),
        "avg_r":round(float(result["realized_r"].mean()),4),
        "profit_factor":round(float(wins.sum()/abs(losses.sum())),4) if len(losses) else float("inf"),
        "max_drawdown_r":round(float(dd.min()),4),
        "tp1_plus_trades":int((result["tps_hit"]>=1).sum()),
        "tp2_plus_trades":int((result["tps_hit"]>=2).sum()),
        "tp3_plus_trades":int((result["tps_hit"]>=3).sum()),
        "tp4_trades":int((result["tps_hit"]>=4).sum())
    }
    return result, stats

def main():
    p=argparse.ArgumentParser()
    p.add_argument("csv")
    p.add_argument("--out",default="backtest_trades.csv")
    p.add_argument("--fee",type=float,default=0.0004)
    p.add_argument("--max-open",type=int,default=3)
    a=p.parse_args()
    base=load_csv(a.csv)
    trades,stats=run_backtest(base,ohlcv_resample(base,"15min"),ohlcv_resample(base,"4h"),a.fee,a.max_open)
    trades.to_csv(a.out,index=False)
    print("=== Wajid Liquidity V1 Backtest ===")
    for k,v in stats.items(): print(f"{k}: {v}")
    print(f"saved: {Path(a.out).resolve()}")

if __name__=="__main__":
    main()
