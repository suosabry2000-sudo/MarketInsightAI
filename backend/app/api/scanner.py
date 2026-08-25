from __future__ import annotations
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter,Depends,HTTPException,Query,Request
from app.domain.models import DataQuality,WeeklyScannerResponse,WeeklyScannerRow
from app.market_data.service import get_market_data_provider,normalize_ticker
from app.prediction.calendar import get_week_sessions,ReferenceResult
from app.prediction.hybrid import opportunity_score
from app.prediction.service import build_hybrid_analysis
from app.api.stocks import DEFAULT
ET=ZoneInfo('America/New_York'); router=APIRouter(prefix='/scanner',tags=['scanner'])
QUALITY={DataQuality.VERIFIED:100,DataQuality.LIMITED:72,DataQuality.STALE:45,DataQuality.DATA_CONFLICT:20,DataQuality.NO_RELIABLE_FORECAST:10}
def _signal(p):return 'STRONG BULLISH' if p>=.70 else 'BULLISH' if p>=.55 else 'STRONG BEARISH' if p<=.30 else 'BEARISH' if p<=.45 else 'NEUTRAL'
def _sort(rows,key):
    if key=='expected_gain':return sorted(rows,key=lambda x:x.expected_move_pct,reverse=True)
    if key=='expected_drop':return sorted(rows,key=lambda x:x.expected_move_pct)
    if key=='confidence':return sorted(rows,key=lambda x:x.confidence,reverse=True)
    if key=='bullish':return sorted(rows,key=lambda x:x.bull_probability,reverse=True)
    if key=='bearish':return sorted(rows,key=lambda x:x.bear_probability,reverse=True)
    if key=='ticker':return sorted(rows,key=lambda x:x.ticker)
    return sorted(rows,key=lambda x:x.opportunity_score,reverse=True)
async def build_scanner_snapshot(provider,tickers:list[str],sort='opportunity',*,evidence_service=None,catalog=None):
    now=datetime.now(ET); sessions=get_week_sessions(now.date()); rows=[]; status='CLOSED'; meta={x['ticker']:x for x in (catalog or DEFAULT)}
    for raw in tickers:
        ticker=normalize_ticker(raw); b=await build_hybrid_analysis(provider,ticker,evidence_service=evidence_service); q,f=b.quote,b.forecast; status=q.market_session
        getter=getattr(provider,'get_weekly_reference',None)
        if callable(getter):
            try:ref=await getter(ticker,sessions.reference_session)
            except Exception:ref=ReferenceResult(q.price,DataQuality.LIMITED)
        else:ref=ReferenceResult(q.price,DataQuality.LIMITED)
        ref_price=ref.price; move=(f.base_target/ref_price-1)*100; live_move=(f.base_target/q.price-1)*100; risk_score=b.risk.score
        md=meta.get(ticker,{})
        rows.append(WeeklyScannerRow(ticker=ticker,monday_reference=round(ref_price,4),live_price=round(q.price,4),friday_bear=round(f.bear_target,4),friday_base=round(f.base_target,4),friday_bull=round(f.bull_target,4),expected_move_pct=round(move,4),expected_move_from_live_pct=round(live_move,4),bull_probability=f.bull_probability,bear_probability=f.bear_probability,confidence=f.confidence,opportunity_score=opportunity_score(move,f.confidence,QUALITY[f.data_quality],risk_score),signal=_signal(f.bull_probability),risk=f.risk,data_quality=f.data_quality,reference_quality=ref.data_quality,exchange=md.get('exchange'),sector=md.get('sector'),index_memberships=md.get('index_memberships',[]),themes=md.get('themes',[]),market_cap_bucket=md.get('market_cap_bucket'),most_active=md.get('most_active',False),volatility=b.realized_volatility))
    return WeeklyScannerResponse(market_status=status,generated_at=now,reference_session=sessions.reference_session,target_session=sessions.target_session,stocks=_sort(rows,sort))
@router.get('/weekly')
async def weekly(request:Request,tickers:str=Query('AAPL'),sort:str=Query('opportunity'),provider=Depends(get_market_data_provider)):
    values=[x.strip() for x in tickers.split(',') if x.strip()]
    if not values or len(values)>100:raise HTTPException(422,'request 1 to 100 tickers')
    cache=getattr(request.app.state,'scanner_cache',None); key='tickers-'+'-'.join(sorted({x.upper() for x in values}))
    if cache:
        found=await cache.get_scanner_snapshot(key)
        if found:return found.model_copy(update={'stocks':_sort(found.stocks,sort)})
    return await build_scanner_snapshot(provider,values,sort,evidence_service=getattr(request.app.state,'evidence_service',None),catalog=getattr(request.app.state,'stock_catalog',None))
