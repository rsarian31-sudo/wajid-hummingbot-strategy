"""
Download Binance USD-M BTCUSDT 5m historical klines.

Uses Binance's public data archive rather than the Futures REST API.
"""

from __future__ import annotations

import argparse
import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

BASE = "https://data.binance.vision/data/futures/um/monthly/klines"


def parse_date(value: str) -> pd.Timestamp:
    return pd.Timestamp(value, tz="UTC").normalize()


def month_starts(start: pd.Timestamp, end: pd.Timestamp):
    cur = start.replace(day=1)
    while cur < end:
        yield cur
        cur = cur + pd.offsets.MonthBegin(1)


def read_kline_csv(fh) -> pd.DataFrame:
    raw = pd.read_csv(fh, header=None)

    # Binance archive files can contain a header row. Support both variants.
    first = str(raw.iloc[0, 0]).strip().lower() if len(raw) else ""
    if first in {"open_time", "open time", "timestamp"}:
        raw = raw.iloc[1:].reset_index(drop=True)

    if raw.shape[1] < 6:
        raise RuntimeError(f"Unexpected kline schema: {raw.shape[1]} columns")

    raw = raw.iloc[:, :6].copy()
    raw.columns = ["timestamp", "open", "high", "low", "close", "volume"]
    raw["timestamp"] = pd.to_numeric(raw["timestamp"], errors="coerce")
    raw["timestamp"] = pd.to_datetime(
        raw["timestamp"], unit="ms", utc=True, errors="coerce"
    )

    for col in ["open", "high", "low", "close", "volume"]:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")

    return raw.dropna(
        subset=["timestamp", "open", "high", "low", "close", "volume"]
    )


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
                frames.append(read_kline_csv(fh))

    if not frames:
        raise RuntimeError("No monthly data returned")

    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates("timestamp").sort_values("timestamp")
    df = df[(df["timestamp"] >= start_ts) & (df["timestamp"] < end_ts)]

    if df.empty:
        raise RuntimeError("Downloaded archive contained no candles in requested range")

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
