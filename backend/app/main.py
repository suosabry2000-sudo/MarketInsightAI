from __future__ import annotations
import secrets
from fastapi import FastAPI
from app.settings import Settings
from app.market_data.factory import create_market_data_provider
from app.security.auth import TokenService
from app.security.rate_limit import InMemoryRateLimiter,RateLimitMiddleware
from app.api import auth,quotes,charts,forecasts,stocks,markets,scanner,watchlist,alerts,accuracy,reports
from app.live.websocket import QuoteHub, router as websocket_router

def create_app(provider=None,*,auth_required=False,token_secret=None,rate_limit_requests=500):
    app=FastAPI(title='Market Insight AI API',version='1.0.0')
    app.state.market_data_provider=provider or create_market_data_provider();app.state.auth_required=auth_required;app.state.token_service=TokenService(token_secret or secrets.token_urlsafe(32));app.state.watchlists={};app.state.alert_preferences={};app.state.push_tokens={};app.state.quote_hub=QuoteHub()
    app.add_middleware(RateLimitMiddleware,limiter=InMemoryRateLimiter(rate_limit_requests,60))
    @app.get('/health')
    def health():return {'status':'ok'}
    for r in (auth.router,quotes.router,charts.router,forecasts.router,stocks.router,markets.router,scanner.router,watchlist.router,alerts.router,accuracy.router,reports.tech,reports.fundamentals,reports.news,reports.verification,websocket_router):app.include_router(r)
    return app

def create_app_from_settings(settings=None):
    s=(settings or Settings()).validate_production(); production=s.APP_ENV.lower()=='production'; app=create_app(provider=create_market_data_provider(s),auth_required=production,token_secret=s.TOKEN_SECRET or secrets.token_urlsafe(32),rate_limit_requests=s.RATE_LIMIT_REQUESTS)
    from app.providers.factory import create_evidence_service
    evidence=create_evidence_service(s)
    if evidence:app.state.evidence_service=evidence
    if s.DATABASE_URL:
        from app.database.store import SqlStore
        app.state.sql_store=SqlStore(s.DATABASE_URL)
    if s.REDIS_URL:
        import asyncio
        import contextlib
        import redis.asyncio as redis_async
        from app.live.cache import LiveStateCache
        from app.live.stream_manager import StreamManager
        redis_client=redis_async.from_url(s.REDIS_URL)
        cache=LiveStateCache(redis_client,scanner_ttl_seconds=max(60,s.SCANNER_REFRESH_SECONDS*2))
        app.state.redis=redis_client
        app.state.scanner_cache=cache
        manager=StreamManager(app.state.market_data_provider,cache,app.state.quote_hub)
        app.state.stream_manager=manager
        async def _start_stream():
            app.state.stream_task=asyncio.create_task(manager.run_forever())
        async def _stop_stream():
            manager.stop()
            task=getattr(app.state,'stream_task',None)
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            closer=getattr(redis_client,'aclose',None)
            if callable(closer):
                await closer()
        app.router.add_event_handler('startup',_start_stream)
        app.router.add_event_handler('shutdown',_stop_stream)
    return app

app=create_app_from_settings()
