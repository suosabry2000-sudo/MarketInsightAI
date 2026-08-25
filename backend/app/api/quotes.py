from fastapi import APIRouter,Depends,HTTPException
from app.market_data.service import MarketDataService,get_market_data_provider
router=APIRouter(prefix='/quotes',tags=['quotes'])
@router.get('/{ticker}')
async def quote(ticker:str,provider=Depends(get_market_data_provider)):
    try:return await MarketDataService(provider).get_quote(ticker)
    except (KeyError,ValueError) as e:raise HTTPException(404 if isinstance(e,KeyError) else 422,str(e))
