"""
Download Binance USD-M BTCUSDT 5m historical klines.

The downloader uses Binance's public data archive rather than the Futures
REST API. This avoids exchange/API geo restrictions on GitHub-hosted runners.

Example:
python download_binance_5m.py --start 2026-01-01 --end 2026-02-01 --out data/btcusdt_5m.csv
"""
from __future__ import annotations

import argparse
import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

BASE = "https://data.binance.vision/data/futures/um/monthly/klines"


def parse_date(value: str) -> pd.Timestamp:
    ts = pd.Timestamp(value, tz="UTC")
    return ts.normalize()


def month_starts(start: pd.Timestamp, end: pd.Timestamp):
    cur = start.replace(day=1)
    while cur < end:
        yield cur
        cur = cur + pd.offsets.MonthBegin(1)


def download(symbol: str, start: str, end: str, out: str):
    start_ts = parse_date(start)
    end_ts = parse_date(end)
    if end_ts <= start_ts:
        raise ValueError("--end must be after --start")

    frames = []
    for month in month_starts(start_ts, end_ts):
        ym = month.strftime("%Y-%m")
        url = f"{BASE}/{symbol}/5m/{symbol}-5m-{ym}.zip"
        print(f"downloading {url}")
        response = requests.get(url, timeout=60)
        response.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            csv_names = [n for n in archive.namelist() if n.endswith(".csv")]
            if not csv_names:
                raise RuntimeError(f"No CSV found in {url}")
            with archive.open(csv_names[0]) as fh:
                raw = pd.read_csv(fh, header=None)

        # Binance kline archive schema:
        # open time, open, high, low, close, volume, close time,
        # quote volume, trades, taker buy base, taker buy quote, ignore
        raw = raw.iloc[:, :6]
        raw.columns = ["timestamp", "open", "high", "low", "close", "volume"]
        raw["timestamp"] = pd.to_datetime(raw["timestamp"], unit="ms", utc=True)
        for col in ["open", "high", "low", "close", "volume"]:
            raw[col] = pd.to_numeric(raw[col], errors="coerce")
        frames.append(raw.dropna())

    if not frames:
        raise RuntimeError("No monthly data returned")

    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates("timestamp").sort_values("timestamp")
    df = df[(df["timestamp"] >= start_ts) & (df["timestamp"] < end_ts)]

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"saved {len(df)} candles -> {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--out", default="data/btcusdt_5m.csv")
    args = parser.parse_args()
    download(args.symbol, args.start, args.end, args.out)
