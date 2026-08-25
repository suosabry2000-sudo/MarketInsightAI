from __future__ import annotations
from dataclasses import dataclass, replace
import math
import pandas as pd
from app.analysis.technical import analyze_technical, TechnicalResult
from app.analysis.fundamentals import analyze_fundamentals, FundamentalResult
from app.analysis.sentiment import analyze_news, SentimentResult
from app.analysis.momentum import analyze_momentum, MomentumResult
from app.analysis.macro import analyze_macro, MacroResult
from app.domain.models import DataQuality, Quote
from app.market_data.service import MarketDataService
from app.market_data.source_validator import ValidationResult, validate_sources
from app.prediction.hybrid import HybridInputs, build_forecast, compute_confidence

@dataclass(frozen=True)
class RiskResult:
    score: float
    label: str

@dataclass(frozen=True)
class HybridAnalysisBundle:
    quote: Quote
    forecast: object
    technical: TechnicalResult
    momentum: MomentumResult
    fundamental: FundamentalResult
    sentiment: SentimentResult
    macro: MacroResult
    validation: ValidationResult
    risk: RiskResult
    realized_volatility: float

def _frame(bars): return pd.DataFrame([{"timestamp":b.timestamp,"open":b.open,"high":b.high,"low":b.low,"close":b.close,"volume":b.volume} for b in bars])
def _downgrade(v:ValidationResult,reason:str):
    q=v.data_quality if v.data_quality!=DataQuality.VERIFIED else DataQuality.LIMITED
    return replace(v,data_quality=q,reasons=[*v.reasons,reason])

async def build_hybrid_analysis(provider,ticker:str,*,fundamental_data=None,news_events=None,fred_values=None,secondary_prices=None,evidence_service=None,market_ticker="SPY",sector_ticker=None,historical_accuracy=.65,event_risk=0):
    service=MarketDataService(provider); quote=await service.get_quote(ticker)
    if evidence_service is not None:
        ext=await evidence_service.analysis_context(ticker,as_of=quote.normalized_timestamp)
        if fundamental_data is None: fundamental_data=ext.get("fundamental_data")
        if news_events is None: news_events=ext.get("news_events")
        if fred_values is None: fred_values=ext.get("fred_values")
    bars=await service.get_bars(ticker,"1Day",260); frame=_frame(bars); technical=analyze_technical(frame)
    market_available=True
    try: market_frame=_frame(await service.get_bars(market_ticker,"1Day",260)) if market_ticker else frame
    except Exception: market_frame=frame; market_available=False
    sector_available=bool(sector_ticker)
    if sector_ticker:
        try: sector_frame=_frame(await service.get_bars(sector_ticker,"1Day",260))
        except Exception: sector_frame=market_frame; sector_available=False
    else: sector_frame=market_frame
    momentum=analyze_momentum(frame,market_frame,sector_frame)
    fundamental=analyze_fundamentals(dict(fundamental_data or {})); sentiment=analyze_news(list(news_events or []),quote.normalized_timestamp); macro=analyze_macro(market_frame,dict(fred_values or {}))
    completeness=min(1,len(frame)/200); prices=[quote.price,*(secondary_prices or [])]
    validation=validate_sources(prices=prices,freshness_seconds=[quote.freshness_seconds]*len(prices),history_completeness=completeness)
    if quote.data_quality==DataQuality.LIMITED and validation.data_quality==DataQuality.VERIFIED: validation=_downgrade(validation,"Market feed entitlement/coverage is limited")
    if not market_available: validation=_downgrade(validation,"Independent broad-market benchmark data is unavailable")
    # Missing a sector ETF is informative but not enough alone to invalidate a broad-market comparison.
    if fundamental_data is None: validation=_downgrade(validation,"Fundamental evidence is unavailable")
    if news_events is None: validation=_downgrade(validation,"News evidence source is unavailable")
    returns=frame["close"].pct_change().dropna(); realized=float(returns.std(ddof=0)*math.sqrt(252)) if len(returns) else 0
    atr=float(technical.indicators.get("atr_14",quote.price*.01)); atr_pct=max(.002,atr/quote.price)
    comps=[technical.score,momentum.score,fundamental.score,sentiment.score,macro.score]; std=float(pd.Series(comps).std(ddof=0)); agreement=max(0,1-std/50)
    component_completeness=min(technical.completeness,momentum.completeness,completeness,fundamental.completeness if fundamental_data is not None else .25)
    confidence=compute_confidence(model_agreement=agreement,data_quality=validation.data_quality,historical_accuracy=historical_accuracy,source_agreement=validation.source_agreement/100,market_stability=max(0,1-min(1,realized/.8)),news_certainty=sentiment.certainty/100,event_risk=event_risk,completeness=component_completeness)
    risk_score=min(100,realized*100+event_risk*40+(25 if validation.data_quality!=DataQuality.VERIFIED else 0)); risk=RiskResult(risk_score,"HIGH" if risk_score>=65 else "MEDIUM" if risk_score>=35 else "LOW")
    negative_tokens=("bear","below","negative","weak","decline","risk","inverted")
    evidence=[*technical.evidence,*momentum.evidence,*fundamental.evidence,*sentiment.evidence,*macro.evidence]
    neg=[x for x in evidence if any(t in x.lower() for t in negative_tokens)]; pos=[x for x in evidence if x not in neg]
    inp=HybridInputs(ticker=ticker.upper(),as_of=quote.normalized_timestamp,price=quote.price,technical=technical.score,momentum=momentum.score,fundamental=fundamental.score,sentiment=sentiment.score,macro=macro.score,realized_volatility=realized,atr_pct=atr_pct,positive=pos,negative=neg)
    fc=build_forecast(inp,data_quality=validation.data_quality,confidence=confidence)
    return HybridAnalysisBundle(quote,fc,technical,momentum,fundamental,sentiment,macro,validation,risk,realized)
