from dataclasses import dataclass

@dataclass(frozen=True)
class FundamentalResult:
    score: float
    category: str
    completeness: float
    metrics: dict
    evidence: list[str]

def analyze_fundamentals(data:dict)->FundamentalResult:
    if not data: return FundamentalResult(50,"NEUTRAL",0,{},["Fundamental evidence unavailable"])
    score=50.0; ev=[]
    rg=data.get("revenue_growth"); eg=data.get("eps_growth"); margin=data.get("operating_margin"); fcf=data.get("free_cash_flow"); dc=data.get("debt_to_cash"); pe=data.get("pe")
    if rg is not None: score += max(-12,min(12,float(rg)*80)); ev.append(f"Revenue growth {float(rg)*100:.1f}%")
    if eg is not None: score += max(-12,min(12,float(eg)*70)); ev.append(f"EPS growth {float(eg)*100:.1f}%")
    if margin is not None: score += max(-10,min(10,(float(margin)-.12)*40)); ev.append(f"Operating margin {float(margin)*100:.1f}%")
    if fcf is not None: score += 6 if float(fcf)>0 else -8
    if dc is not None: score += 6 if float(dc)<1 else (-8 if float(dc)>3 else 0)
    if pe is not None: score += 4 if 0<float(pe)<35 else (-6 if float(pe)>70 else 0)
    score=max(0,min(100,score)); cat="STRONG" if score>=75 else "GOOD" if score>=60 else "NEUTRAL" if score>=40 else "WEAK"
    fields=(rg,eg,margin,fcf,dc,pe); return FundamentalResult(score,cat,sum(x is not None for x in fields)/len(fields),data,ev)
