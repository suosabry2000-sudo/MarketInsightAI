from datetime import datetime, timedelta, timezone
import pytest
from app.domain.models import DataQuality, PriceBar, Quote
from app.market_data.fake_provider import FakeMarketDataProvider
from app.prediction.service import build_hybrid_analysis


def fixture_provider():
    now=datetime.now(timezone.utc)
    quote=Quote(ticker="AAPL",price=310.8,provider="fixture",provider_timestamp=now,normalized_timestamp=now,market_session="OPEN",freshness_seconds=0,data_quality=DataQuality.VERIFIED,feed_scope="TEST_FIXTURE")
    spy=Quote(ticker="SPY",price=650,provider="fixture",provider_timestamp=now,normalized_timestamp=now,market_session="OPEN",freshness_seconds=0,data_quality=DataQuality.VERIFIED,feed_scope="TEST_FIXTURE")
    def bars(start):return [PriceBar(timestamp=now-timedelta(days=259-i),open=start+i*.1,high=start+i*.1+1,low=start+i*.1-1,close=start+i*.1+.3,volume=1_000_000+i*1000) for i in range(260)]
    return FakeMarketDataProvider(quotes={"AAPL":quote,"SPY":spy},bars={"AAPL":bars(285),"SPY":bars(620)})

@pytest.mark.asyncio
async def test_service_uses_external_evidence_and_exact_hybrid_components():
    class Evidence:
        async def analysis_context(self,ticker,as_of):
            assert ticker=="AAPL"
            return {"fundamental_data":{"revenue_growth":.12,"eps_growth":.10,"operating_margin":.25,"free_cash_flow":10,"debt_to_cash":.5},"news_events":[],"fred_values":{"FEDFUNDS":4.0,"CPI_YOY":2.7,"YIELD_CURVE_10Y2Y":.2}}
    bundle=await build_hybrid_analysis(fixture_provider(),"AAPL",evidence_service=Evidence())
    assert bundle.forecast.ticker=="AAPL"
    assert bundle.fundamental.completeness>0
    assert bundle.validation.data_quality in {DataQuality.VERIFIED,DataQuality.LIMITED}
    assert 0<=bundle.forecast.confidence<=100

@pytest.mark.asyncio
async def test_missing_evidence_downgrades_quality_instead_of_fabricating_neutral_verification():
    bundle=await build_hybrid_analysis(fixture_provider(),"AAPL",evidence_service=None)
    assert bundle.validation.data_quality == DataQuality.LIMITED
    assert any("Fundamental evidence is unavailable" in x for x in bundle.validation.reasons)
    assert any("News evidence source is unavailable" in x for x in bundle.validation.reasons)
