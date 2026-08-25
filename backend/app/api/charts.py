from fastapi import APIRouter,Depends,HTTPException,Query
from app.domain.models import ChartSeries
from app.market_data.service import MarketDataService,get_market_data_provider,normalize_ticker
router=APIRouter(prefix='/charts',tags=['charts'])
RANGES={'1D':('1Min',390),'1W':('15Min',160),'1M':('1Day',30),'3M':('1Day',90),'6M':('1Day',180),'1Y':('1Day',260),'5Y':('1Day',1300),'MAX':('1Day',2500)}
@router.get('/{ticker}',response_model=ChartSeries)
async def chart(ticker:str,range:str=Query('1M'),provider=Depends(get_market_data_provider)):
    if range not in RANGES:raise HTTPException(422,'unsupported range')
    tf,limit=RANGES[range]
    try:bars=await MarketDataService(provider).get_bars(ticker,tf,limit)
    except (KeyError,ValueError) as e:raise HTTPException(404 if isinstance(e,KeyError) else 422,str(e))
    return ChartSeries(ticker=normalize_ticker(ticker),range=range,bars=bars)
