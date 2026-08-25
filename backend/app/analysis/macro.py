from dataclasses import dataclass
import pandas as pd

@dataclass(frozen=True)
class MacroResult:
    score: float
    regime: str
    evidence: list[str]

def analyze_macro(market:pd.DataFrame,fred:dict[str,float|None])->MacroResult:
    c=market["close"].astype(float); trend=0 if len(c)<20 else float(c.iloc[-1]/c.iloc[-20]-1); score=50+trend*150
    fed=fred.get("FEDFUNDS"); cpi=fred.get("CPI_YOY"); curve=fred.get("YIELD_CURVE_10Y2Y")
    if fed is not None: score += 4 if fed<4 else -4
    if cpi is not None: score += 5 if cpi<3 else -5
    if curve is not None: score += 5 if curve>=0 else -8
    score=max(0,min(100,score)); regime="BULL" if score>=60 else "BEAR" if score<=40 else "NEUTRAL"
    return MacroResult(score,regime,[f"Broad market trend {trend*100:.2f}%",f"Fed funds {fed if fed is not None else 'n/a'}",f"CPI YoY {cpi if cpi is not None else 'n/a'}"])
