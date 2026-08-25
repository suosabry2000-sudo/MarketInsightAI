from datetime import datetime,timezone
from fastapi import APIRouter,Depends,Request
from app.market_data.service import get_market_data_provider
from app.api.stocks import catalog,_provider_quotes
router=APIRouter(prefix='/markets',tags=['markets'])

@router.get('/overview')
async def overview(request:Request,provider=Depends(get_market_data_provider)):
    items=await catalog(request,provider)
    # Home is a compact market snapshot; full browsing lives under /stocks/catalog.
    # Pull a broad rotating slice rather than the legacy fixed six-symbol list.
    candidates=[str(x.get('ticker','')).upper() for x in items if x.get('ticker')][:250]
    quotes=await _provider_quotes(provider,candidates)
    rows=[];status='CLOSED'
    for ticker in candidates:
        q=quotes.get(ticker)
        if q is None:continue
        status=q.market_session
        change=getattr(q,'change_pct',None)
        rows.append({'ticker':ticker,'price':q.price,'change_pct':round(float(change or 0.0),3),'volume':None})
    gain=sorted(rows,key=lambda x:x['change_pct'],reverse=True)
    active=sorted(rows,key=lambda x:abs(x['change_pct']),reverse=True)
    return {
        'indexes':[{'symbol':'SPY','name':'S&P 500','change_pct':0.0},{'symbol':'QQQ','name':'Nasdaq 100','change_pct':0.0},{'symbol':'DIA','name':'Dow Jones','change_pct':0.0}],
        'market_status':status,'catalog_total':len(items),'top_gainers':gain[:5],'top_losers':sorted(rows,key=lambda x:x['change_pct'])[:5],
        'most_active':active[:5],'generated_at':datetime.now(timezone.utc)
    }
