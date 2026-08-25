from datetime import date,datetime,timezone
import pytest
from app.domain.models import DataQuality,WeeklyScannerResponse,WeeklyScannerRow
from app.workers.scanner import ScannerWorker,resolve_scanner_tickers
from app.workers.outcomes import OutcomeWorker

class Cache:
    def __init__(self,existing=None):self.value=existing
    async def get_scanner_snapshot(self,u):return self.value
    async def set_scanner_snapshot(self,u,v):self.value=v

def snap(q=DataQuality.VERIFIED):
    return WeeklyScannerResponse(market_status='OPEN',generated_at=datetime(2026,8,24,tzinfo=timezone.utc),reference_session=date(2026,8,24),target_session=date(2026,8,28),stocks=[WeeklyScannerRow(ticker='AAPL',monday_reference=310,live_price=311,friday_bear=300,friday_base=315,friday_bull=322,expected_move_pct=1.6,expected_move_from_live_pct=1.2,bull_probability=.65,bear_probability=.35,confidence=72,opportunity_score=70,signal='BULLISH',risk='MEDIUM',data_quality=q)])

@pytest.mark.asyncio
async def test_scanner_worker_batches_and_preserves_stale_snapshot_on_failure():
    calls=[]
    async def compute(provider,batch,sort):calls.append(batch);return snap()
    c=Cache();w=ScannerWorker(object(),c,batch_size=1,compute=compute);r=await w.run('all-us',['AAPL','NVDA']);assert calls==[['AAPL'],['NVDA']] and len(r.stocks)==2
    prev=r
    async def fail(*a,**k):raise RuntimeError('down')
    w=ScannerWorker(object(),c,compute=fail);r=await w.run('all-us',['AAPL']);assert r.generated_at==prev.generated_at and all(x.data_quality==DataQuality.STALE for x in r.stocks)

@pytest.mark.asyncio
async def test_resolve_scanner_tickers_uses_full_provider_catalog_and_override(monkeypatch):
    class P:
        async def list_assets(self):return [{'ticker':'AAPL'},{'ticker':'NVDA'},{'ticker':'aapl'}]
    monkeypatch.delenv('SCANNER_TICKERS',raising=False);assert await resolve_scanner_tickers(P())==['AAPL','NVDA']
    monkeypatch.setenv('SCANNER_TICKERS','MSFT,AAPL,MSFT');assert await resolve_scanner_tickers(P())==['MSFT','AAPL']


def test_outcome_worker_only_scores_after_target_close(tmp_path):
    from app.database.store import SqlStore
    s=SqlStore(f"sqlite:///{tmp_path/'x.db'}");fid=s.save_forecast(ticker='AAPL',created_at=datetime(2026,8,24,tzinfo=timezone.utc),as_of=datetime(2026,8,24,tzinfo=timezone.utc),model_version='hybrid-v1.0',bear=300,base=315,bull=322,bull_probability=.65,bear_probability=.35,confidence=80,validation='VERIFIED',target_session=date(2026,8,28),reference_price=310)
    worker=OutcomeWorker(s)
    assert not worker.record_if_due(fid,316,datetime(2026,8,28,15,0,tzinfo=timezone.utc))
    assert worker.record_if_due(fid,316,datetime(2026,8,28,21,0,tzinfo=timezone.utc))
    s.close()
