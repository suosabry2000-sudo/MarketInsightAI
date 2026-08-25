from datetime import datetime,timezone,timedelta
import pytest
from app.domain.models import Quote,DataQuality
from app.live.cache import LiveStateCache
from app.live.websocket import QuoteHub

class RedisFake:
    def __init__(self):self.data={};self.published=[]
    async def set(self,k,v,ex=None):self.data[k]=v
    async def get(self,k):return self.data.get(k)
    async def publish(self,c,v):self.published.append((c,v))

def q(ts=None):
    ts=ts or datetime.now(timezone.utc)
    return Quote(ticker='AAPL',price=310.8,provider='fixture',provider_timestamp=ts,normalized_timestamp=ts,market_session='OPEN',freshness_seconds=0,data_quality=DataQuality.VERIFIED,feed_scope='TEST_FIXTURE')

@pytest.mark.asyncio
async def test_live_cache_round_trip_and_rejects_stale_quote():
    now=datetime(2026,8,24,18,tzinfo=timezone.utc); redis=RedisFake(); cache=LiveStateCache(redis,quote_ttl_seconds=30,clock=lambda:now)
    await cache.set_quote(q(now)); assert (await cache.get_quote('aapl')).price==310.8
    redis.data[cache.quote_key('AAPL')]=q(now-timedelta(seconds=31)).model_dump_json()
    assert await cache.get_quote('AAPL') is None

@pytest.mark.asyncio
async def test_quote_hub_only_emits_subscribed_ticker():
    hub=QuoteHub(); queue=hub.register(); hub.subscribe(queue,['AAPL'])
    await hub.publish(q()); assert (await queue.get()).ticker=='AAPL'
    nv=q().model_copy(update={'ticker':'NVDA'}); await hub.publish(nv)
    assert queue.empty()
    hub.unregister(queue)


def test_websocket_subscription_receives_only_subscribed_quote():
    import asyncio
    from fastapi.testclient import TestClient
    from app.main import create_app
    app=create_app()
    with TestClient(app) as client:
        with client.websocket_connect('/ws/quotes') as ws:
            ws.send_json({'type':'subscribe','tickers':['AAPL']})
            asyncio.run(app.state.quote_hub.publish(q()))
            message=ws.receive_json()
            assert message['ticker']=='AAPL'

@pytest.mark.asyncio
async def test_stream_manager_publishes_provider_quotes_to_cache_and_hub():
    from app.live.stream_manager import StreamManager
    from app.market_data.fake_provider import FakeMarketDataProvider
    provider=FakeMarketDataProvider(); redis=RedisFake(); cache=LiveStateCache(redis); hub=QuoteHub()
    queue=hub.register(); hub.subscribe(queue,['AAPL'])
    manager=StreamManager(provider,cache,hub,poll_interval=.01)
    task=__import__('asyncio').create_task(manager.run_once(['AAPL']))
    quote=await __import__('asyncio').wait_for(queue.get(),timeout=1)
    task.cancel()
    assert quote.ticker=='AAPL'
    assert await cache.get_quote('AAPL') is not None
