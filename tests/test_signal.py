import pandas as pd
from wajid_liquidity_signal import detect_signal

def test_bullish_sweep_mss():
    rows=[]
    for i in range(30):
        base=100+i*0.05
        rows.append({"open":base,"high":base+0.4,"low":base-0.2,"close":base+0.2})
    rows[-3]={"open":101.0,"high":101.2,"low":100.5,"close":100.9}
    rows[-2]={"open":100.9,"high":101.0,"low":100.0,"close":100.8}
    rows[-1]={"open":100.8,"high":102.0,"low":100.7,"close":101.8}
    signal=detect_signal(pd.DataFrame(rows))
    assert signal is not None
    assert signal.side=="LONG"
    assert signal.tp4>signal.tp1>signal.entry>signal.stop
