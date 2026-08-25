from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class TechnicalResult:
    score: float
    completeness: float
    indicators: dict[str,float]
    evidence: list[str]

def _clip(x): return float(max(0,min(100,x)))

def analyze_technical(df:pd.DataFrame)->TechnicalResult:
    if df.empty or "close" not in df: return TechnicalResult(50,0,{},["No price history"])
    c=df["close"].astype(float); h=df["high"].astype(float); l=df["low"].astype(float)
    v=df["volume"].astype(float)
    ema12=c.ewm(span=12,adjust=False).mean(); ema26=c.ewm(span=26,adjust=False).mean(); macd=ema12-ema26
    delta=c.diff(); gain=delta.clip(lower=0).rolling(14).mean(); loss=(-delta.clip(upper=0)).rolling(14).mean(); rs=gain/(loss.replace(0,np.nan)); rsi=(100-(100/(1+rs))).fillna(50)
    prev=c.shift(1); tr=pd.concat([(h-l).abs(),(h-prev).abs(),(l-prev).abs()],axis=1).max(axis=1); atr=tr.rolling(14).mean().bfill()
    sma20=c.rolling(20).mean(); std20=c.rolling(20).std(ddof=0); bb_up=sma20+2*std20; bb_lo=sma20-2*std20
    def last(series,default=float(c.iloc[-1])):
        val=series.iloc[-1]; return default if pd.isna(val) else float(val)
    indicators={
        "rsi_14":last(rsi,50),"macd":last(macd,0),"ema_9":last(c.ewm(span=9,adjust=False).mean()),
        "ema_20":last(c.ewm(span=20,adjust=False).mean()),"ema_50":last(c.ewm(span=50,adjust=False).mean()),"ema_200":last(c.ewm(span=200,adjust=False).mean()),
        "sma_20":last(sma20),"sma_50":last(c.rolling(50).mean()),"sma_200":last(c.rolling(200).mean()),
        "atr_14":last(atr,max(.01,float(c.iloc[-1])*.01)),"bollinger_upper":last(bb_up),"bollinger_lower":last(bb_lo),
        "support":float(l.tail(min(20,len(l))).min()),"resistance":float(h.tail(min(20,len(h))).max()),
        "volume":float(v.iloc[-1]),"avg_volume_20":float(v.tail(min(20,len(v))).mean()),
        "roc_10":float((c.iloc[-1]/c.iloc[max(0,len(c)-11)]-1)*100) if len(c)>1 else 0,
    }
    price=float(c.iloc[-1]); score=50
    score += 10 if price>indicators["ema_20"] else -10
    score += 10 if price>indicators["ema_50"] else -10
    score += 8 if price>indicators["ema_200"] else -8
    score += 8 if indicators["macd"]>0 else -8
    score += 6 if 50<=indicators["rsi_14"]<=70 else (-5 if indicators["rsi_14"]>75 else 0)
    score += 5 if indicators["volume"]>=indicators["avg_volume_20"] else 0
    score += max(-5,min(5,indicators["roc_10"]/2))
    evidence=[f"Price {'above' if price>indicators['ema_20'] else 'below'} EMA20",f"MACD {'positive' if indicators['macd']>0 else 'negative'}",f"RSI {indicators['rsi_14']:.1f}"]
    return TechnicalResult(_clip(score),min(1,len(c)/200),indicators,evidence)
