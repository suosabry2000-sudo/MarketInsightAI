from fastapi import APIRouter,Depends,HTTPException,Request
from app.market_data.service import get_market_data_provider,normalize_ticker
from app.prediction.service import build_hybrid_analysis
router=APIRouter(prefix='/forecasts',tags=['forecasts'])
@router.get('/{ticker}')
async def forecast(ticker:str,request:Request,provider=Depends(get_market_data_provider)):
    try:
        symbol=normalize_ticker(ticker); bundle=await build_hybrid_analysis(provider,symbol,evidence_service=getattr(request.app.state,'evidence_service',None))
        store=getattr(request.app.state,'sql_store',None)
        if store is not None:
            from datetime import datetime,timezone
            from app.prediction.calendar import get_week_sessions
            sessions=get_week_sessions(bundle.quote.normalized_timestamp.date())
            reference=bundle.quote.price
            getter=getattr(provider,'get_weekly_reference',None)
            if callable(getter):
                try:reference=(await getter(symbol,sessions.reference_session)).price
                except Exception:pass
            store.save_forecast(ticker=symbol,created_at=datetime.now(timezone.utc),as_of=bundle.forecast.as_of,model_version=bundle.forecast.model_version,bear=bundle.forecast.bear_target,base=bundle.forecast.base_target,bull=bundle.forecast.bull_target,bull_probability=bundle.forecast.bull_probability,bear_probability=bundle.forecast.bear_probability,confidence=bundle.forecast.confidence,validation=bundle.forecast.data_quality.value,target_session=sessions.target_session,reference_price=reference)
        return bundle.forecast
    except KeyError as e:raise HTTPException(404,f'ticker {ticker.upper()} not found') from e
    except ValueError as e:raise HTTPException(422,str(e)) from e
