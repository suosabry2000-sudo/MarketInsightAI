from datetime import datetime, timedelta, timezone
import pandas as pd
from app.analysis.technical import analyze_technical
from app.analysis.fundamentals import analyze_fundamentals
from app.analysis.sentiment import analyze_news
from app.analysis.macro import analyze_macro
from app.analysis.momentum import analyze_momentum
from app.providers.news import NewsEvent


def frame(trend=1.0, n=260):
    now=datetime(2026,8,24,tzinfo=timezone.utc)
    close=[100+i*trend*.15 for i in range(n)]
    return pd.DataFrame({"timestamp":[now-timedelta(days=n-1-i) for i in range(n)],"open":[x-.2 for x in close],"high":[x+.7 for x in close],"low":[x-.7 for x in close],"close":close,"volume":[1_000_000+i*1000 for i in range(n)]})


def test_technical_analysis_outputs_score_indicators_support_resistance():
    result=analyze_technical(frame())
    assert 0 <= result.score <= 100
    for key in ("rsi_14","macd","ema_20","ema_50","ema_200","sma_50","atr_14","bollinger_upper","support","resistance"):
        assert key in result.indicators
    assert result.indicators["support"] < result.indicators["resistance"]
    assert result.completeness > .9


def test_fundamental_analysis_rewards_profitable_growth_and_penalizes_debt():
    strong=analyze_fundamentals({"revenue_growth":.15,"eps_growth":.18,"operating_margin":.30,"free_cash_flow":100,"debt_to_cash":.4,"pe":25})
    weak=analyze_fundamentals({"revenue_growth":-.10,"eps_growth":-.20,"operating_margin":-.05,"free_cash_flow":-10,"debt_to_cash":5,"pe":80})
    assert strong.score > weak.score
    assert strong.category in {"STRONG","GOOD"}


def test_news_deduplicates_same_headline_and_weights_material_event():
    now=datetime(2026,8,24,18,tzinfo=timezone.utc)
    events=[
        NewsEvent("Apple earnings beat expectations","Reuters",now,0.8,.95,.95,True),
        NewsEvent("Apple earnings beat expectations","Other",now,0.8,.9,.9,True),
        NewsEvent("Analyst blog discusses Apple","Blog",now,-.2,.3,.2,False),
    ]
    result=analyze_news(events,now)
    assert result.cluster_count == 2
    assert result.score > 50
    assert result.certainty > 0


def test_macro_and_relative_momentum_are_bounded():
    stock=frame(1.1); market=frame(.4); sector=frame(.6)
    momentum=analyze_momentum(stock,market,sector)
    macro=analyze_macro(market,{"FEDFUNDS":4.25,"CPI_YOY":2.8,"YIELD_CURVE_10Y2Y":.4})
    assert 0 <= momentum.score <= 100
    assert 0 <= macro.score <= 100
    assert momentum.score > 50
