from datetime import datetime, timezone
import httpx, pytest
from app.providers.sec import SecProvider
from app.providers.news import AlpacaNewsProvider
from app.providers.fred import FredProvider
from app.providers.evidence import EvidenceService

@pytest.mark.asyncio
async def test_sec_resolves_cik_and_normalizes_growth_metrics():
    def handler(req:httpx.Request):
        if req.url.path.endswith("company_tickers.json"):
            return httpx.Response(200,json={"0":{"ticker":"AAPL","cik_str":320193,"title":"Apple Inc."}})
        assert "CIK0000320193" in req.url.path
        return httpx.Response(200,json={"facts":{"us-gaap":{
            "Revenues":{"units":{"USD":[{"fy":2025,"fp":"FY","form":"10-K","val":100},{"fy":2026,"fp":"FY","form":"10-K","val":120}]}},
            "NetIncomeLoss":{"units":{"USD":[{"fy":2026,"fp":"FY","form":"10-K","val":25}]}},
            "EarningsPerShareDiluted":{"units":{"USD/shares":[{"fy":2025,"fp":"FY","form":"10-K","val":5},{"fy":2026,"fp":"FY","form":"10-K","val":6}]}},
            "OperatingIncomeLoss":{"units":{"USD":[{"fy":2026,"fp":"FY","form":"10-K","val":30}]}},
            "CashAndCashEquivalentsAtCarryingValue":{"units":{"USD":[{"fy":2026,"fp":"FY","form":"10-K","val":50}]}},
            "LongTermDebt":{"units":{"USD":[{"fy":2026,"fp":"FY","form":"10-K","val":20}]}},
        }}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        p=SecProvider("MarketInsight test@example.com",client=c)
        data=await p.get_normalized_fundamentals("AAPL",as_of=datetime(2026,8,24,tzinfo=timezone.utc))
    assert data["revenue_growth"] == pytest.approx(.20)
    assert data["eps_growth"] == pytest.approx(.20)
    assert data["operating_margin"] == pytest.approx(.25)
    assert data["debt_to_cash"] == pytest.approx(.4)

@pytest.mark.asyncio
async def test_alpaca_news_filters_future_and_derives_app_sentiment():
    def handler(req):
        return httpx.Response(200,json={"news":[
          {"headline":"Apple earnings beat estimates","author":"Reuters","created_at":"2026-08-24T17:00:00Z","symbols":["AAPL"]},
          {"headline":"Apple lawsuit risk rises","author":"Other","created_at":"2026-08-24T19:00:00Z","symbols":["AAPL"]},
        ]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler),base_url="https://data.alpaca.markets") as c:
        p=AlpacaNewsProvider("id","secret",client=c)
        out=await p.get_events("AAPL",start=datetime(2026,8,20,tzinfo=timezone.utc),end=datetime(2026,8,24,18,tzinfo=timezone.utc))
    assert len(out)==1 and out[0].sentiment>0 and out[0].material

@pytest.mark.asyncio
async def test_fred_returns_only_values_available_by_asof():
    def handler(req):
        series=req.url.params["series_id"]
        return httpx.Response(200,json={"observations":[
            {"date":"2026-07-01","realtime_start":"2026-07-01","value":"4.25" if series=="FEDFUNDS" else "2.8"},
            {"date":"2026-09-01","realtime_start":"2026-09-01","value":"99"},
        ]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler),base_url="https://api.stlouisfed.org") as c:
        p=FredProvider("key",client=c)
        vals=await p.get_macro_values(datetime(2026,8,24,tzinfo=timezone.utc))
    assert vals["FEDFUNDS"]==4.25 and vals["CPI_YOY"]==2.8

@pytest.mark.asyncio
async def test_evidence_service_fails_soft_without_fabricated_neutral_values():
    class Broken:
        async def get_normalized_fundamentals(self,*a,**k): raise RuntimeError()
        async def get_events(self,*a,**k): raise RuntimeError()
        async def get_macro_values(self,*a,**k): raise RuntimeError()
    b=Broken(); service=EvidenceService(sec=b,news=b,fred=b)
    out=await service.analysis_context("AAPL",as_of=datetime.now(timezone.utc))
    assert out=={"fundamental_data":None,"news_events":None,"fred_values":None}
