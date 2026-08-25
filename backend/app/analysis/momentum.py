from dataclasses import dataclass
import pandas as pd

@dataclass(frozen=True)
class MomentumResult:
    score: float
    completeness: float
    evidence: list[str]

def _ret(df:pd.DataFrame,days=20):
    c=df["close"].astype(float); n=min(days,len(c)-1); return 0 if n<=0 else float(c.iloc[-1]/c.iloc[-1-n]-1)

def analyze_momentum(stock:pd.DataFrame,market:pd.DataFrame,sector:pd.DataFrame)->MomentumResult:
    sr=_ret(stock); mr=_ret(market); xr=_ret(sector); relative=(sr-mr)*100; sectorrel=(sr-xr)*100
    score=max(0,min(100,50+sr*180+relative*2+sectorrel))
    return MomentumResult(score,min(1,len(stock)/60),[f"20-session return {sr*100:.2f}%",f"Relative to market {relative:.2f}%",f"Relative to sector {sectorrel:.2f}%"])
