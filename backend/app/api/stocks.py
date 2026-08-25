from fastapi import APIRouter,Depends,Query,Request,HTTPException
from app.market_data.service import get_market_data_provider,MarketDataService,normalize_ticker
router=APIRouter(prefix='/stocks',tags=['stocks'])
DEFAULT=[
 {'ticker':'AAPL','company':'Apple Inc.','exchange':'NASDAQ','sector':'Technology','index_memberships':['S&P 500','Nasdaq'],'themes':['Technology','AI'],'market_cap_bucket':'Mega Cap','most_active':True},
 {'ticker':'MSFT','company':'Microsoft Corporation','exchange':'NASDAQ','sector':'Technology','index_memberships':['S&P 500','Nasdaq','Dow'],'themes':['Technology','AI'],'market_cap_bucket':'Mega Cap','most_active':True},
 {'ticker':'NVDA','company':'NVIDIA Corporation','exchange':'NASDAQ','sector':'Technology','index_memberships':['S&P 500','Nasdaq'],'themes':['Technology','AI','Semiconductors'],'market_cap_bucket':'Mega Cap','most_active':True},
 {'ticker':'AMD','company':'Advanced Micro Devices, Inc.','exchange':'NASDAQ','sector':'Technology','index_memberships':['S&P 500','Nasdaq'],'themes':['Technology','AI','Semiconductors'],'market_cap_bucket':'Mega Cap','most_active':True},
 {'ticker':'TSLA','company':'Tesla, Inc.','exchange':'NASDAQ','sector':'Consumer'},
 {'ticker':'AMZN','company':'Amazon.com, Inc.','exchange':'NASDAQ','sector':'Consumer'},
]
async def catalog(request:Request,provider):
    cached=getattr(request.app.state,'stock_catalog',None)
    if cached is not None:return list(cached)
    loader=getattr(provider,'list_assets',None)
    if callable(loader):
        try:items=await loader()
        except Exception:items=[]
        if items:request.app.state.stock_catalog=items;return list(items)
    return list(DEFAULT)
@router.get('/catalog')
async def list_catalog(request:Request,offset:int=Query(0,ge=0),limit:int=Query(500,ge=1,le=5000),provider=Depends(get_market_data_provider)):
    items=await catalog(request,provider)
    total=len(items); page=items[offset:offset+limit]
    return {'results':page,'total':total,'offset':offset,'limit':limit,'has_more':offset+len(page)<total}

@router.get('/search')
async def search(request:Request,q:str=Query(min_length=1,max_length=80),provider=Depends(get_market_data_provider)):
    needle=q.strip().lower(); items=await catalog(request,provider); matches=[x for x in items if needle in str(x.get('ticker','')).lower() or needle in str(x.get('company','')).lower()]
    matches.sort(key=lambda x:(0 if str(x.get('ticker','')).lower()==needle else 1,str(x.get('ticker',''))));return {'results':matches[:25]}
@router.get('/{ticker}')
async def stock(request:Request,ticker:str,provider=Depends(get_market_data_provider)):
    symbol=normalize_ticker(ticker); items=await catalog(request,provider); meta=next((x for x in items if str(x.get('ticker','')).upper()==symbol),None)
    if meta is None:raise HTTPException(404,f'ticker {symbol} not found')
    return {**meta,'latest':await MarketDataService(provider).get_quote(symbol)}
