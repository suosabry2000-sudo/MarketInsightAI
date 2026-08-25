from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import math
from app.domain.models import DataQuality, DailyForecastRow, Forecast

WEIGHTS={"technical":.35,"momentum":.20,"fundamental":.15,"sentiment":.15,"macro":.15}
QUALITY={DataQuality.VERIFIED:1.0,DataQuality.LIMITED:.72,DataQuality.STALE:.45,DataQuality.DATA_CONFLICT:.20,DataQuality.NO_RELIABLE_FORECAST:.10}

@dataclass(frozen=True)
class HybridInputs:
    ticker:str; as_of:datetime; price:float
    technical:float; momentum:float; fundamental:float; sentiment:float; macro:float
    realized_volatility:float; atr_pct:float
    positive:list[str]; negative:list[str]

def weighted_score(i:HybridInputs)->float:
    return sum(getattr(i,k)*w for k,w in WEIGHTS.items())

def compute_confidence(*,model_agreement:float,data_quality:DataQuality,historical_accuracy:float,source_agreement:float,market_stability:float,news_certainty:float,event_risk:float,completeness:float)->float:
    raw=(.25*model_agreement+.20*QUALITY[data_quality]+.20*historical_accuracy+.15*source_agreement+.10*market_stability+.10*news_certainty)
    raw *= max(.2,min(1,completeness)); raw *= max(.25,1-min(1,event_risk)*.45)
    score=max(5,min(95,raw*100))
    if data_quality == DataQuality.DATA_CONFLICT:
        score=min(score,45)
    if data_quality == DataQuality.NO_RELIABLE_FORECAST:
        score=min(score,35)
    return round(score,2)

def opportunity_score(expected_move_pct:float,confidence:float,data_quality_score:float,risk_score:float)->float:
    move=min(15,abs(expected_move_pct))/15
    return round(max(0,min(100,100*move*(confidence/100)*(data_quality_score/100)*(1-min(100,risk_score)/125))),2)

def _next_weekdays(day:date,count=5):
    out=[]; cur=day
    while len(out)<count:
        cur += timedelta(days=1)
        if cur.weekday()<5: out.append(cur)
    return out

def build_forecast(i:HybridInputs,*,data_quality:DataQuality=DataQuality.VERIFIED,confidence:float=70)->Forecast:
    score=weighted_score(i); direction=(score-50)/50
    # Cap a five-session base move to keep forecasts probabilistic/conservative.
    base_return=max(-.12,min(.12,direction*(.022 + min(.06,i.realized_volatility*.08))))
    base=i.price*(1+base_return)
    width=max(i.price*.008,i.price*i.atr_pct*2.2,i.price*min(.08,max(.015,i.realized_volatility/math.sqrt(52)*1.35)))
    bear=max(.01,base-width); bull=base+width
    bull_prob=max(.08,min(.92,.5+direction*.30)); bear_prob=1-bull_prob
    quality=data_quality
    if data_quality in {DataQuality.DATA_CONFLICT,DataQuality.NO_RELIABLE_FORECAST}:
        quality=DataQuality.NO_RELIABLE_FORECAST
    rows=[]
    for n,d in enumerate(_next_weekdays(i.as_of.date(),5),1):
        ratio=n/5; center=i.price+(base-i.price)*ratio; daily_width=width*math.sqrt(ratio)*.75
        rows.append(DailyForecastRow(date=d,low=max(.01,center-daily_width),high=center+daily_width,base=center,bull_probability=bull_prob,confidence=max(5,confidence-(n-1)*1.2)))
    reason=("Moderately bullish" if bull_prob>=.55 else "Moderately bearish" if bull_prob<=.45 else "Neutral")+" hybrid signal. "+"; ".join((i.positive[:2]+i.negative[:2]) or ["Evidence is limited"])
    tom=rows[0]
    return Forecast(ticker=i.ticker,model_version="hybrid-v1.0",as_of=i.as_of,expected_low=bear,expected_high=bull,bear_target=bear,base_target=base,bull_target=bull,
                    bull_probability=round(bull_prob,4),bear_probability=round(bear_prob,4),confidence=confidence,risk="HIGH" if i.realized_volatility>.55 else "MEDIUM" if i.realized_volatility>.28 else "LOW",
                    data_quality=quality,explanation=reason,tomorrow_open=(i.price+tom.base)/2,tomorrow_low=tom.low,tomorrow_high=tom.high,tomorrow_close=tom.base,daily_rows=rows)
