"""
Download Binance USD-M BTCUSDT 5m klines into the CSV format used by backtest.py.
No API key is required for public market data.

Example:
python download_binance_5m.py --start 2026-01-01 --end 2026-02-01 --out data/btcusdt_5m.csv
"""
from __future__ import annotations
import argparse
import time
from datetime import datetime, timezone
import requests
import pandas as pd

URL="https://fapi.binance.com/fapi/v1/klines"

def ms(s):
    return int(datetime.fromisoformat(s.replace("Z","+00:00")).replace(tzinfo=timezone.utc).timestamp()*1000)

def download(symbol,start,end,out):
    start_ms=ms(start+"T00:00:00Z") if len(start)==10 else ms(start)
    end_ms=ms(end+"T00:00:00Z") if len(end)==10 else ms(end)
    rows=[]
    cursor=start_ms
    while cursor < end_ms:
        params={"symbol":symbol,"interval":"5m","startTime":cursor,"endTime":end_ms,"limit":1500}
        r=requests.get(URL,params=params,timeout=30)
        r.raise_for_status()
        batch=r.json()
        if not batch: break
        rows.extend(batch)
        cursor=int(batch[-1][0])+5*60*1000
        print(f"downloaded {len(rows)} candles")
        if len(batch)<1500: break
        time.sleep(0.15)
    cols=["timestamp","open","high","low","close","volume","close_time","quote_volume","trades","taker_base","taker_quote","ignore"]
    df=pd.DataFrame(rows,columns=cols)
    if df.empty: raise RuntimeError("No candles returned")
    df=df.drop_duplicates("timestamp")
    df["timestamp"]=pd.to_datetime(df["timestamp"],unit="ms",utc=True)
    for c in ["open","high","low","close","volume"]:
        df[c]=pd.to_numeric(df[c])
    df[["timestamp","open","high","low","close","volume"]].to_csv(out,index=False)
    print(f"saved {len(df)} candles -> {out}")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--symbol",default="BTCUSDT")
    p.add_argument("--start",required=True)
    p.add_argument("--end",required=True)
    p.add_argument("--out",default="data/btcusdt_5m.csv")
    a=p.parse_args()
    download(a.symbol,a.start,a.end,a.out)
