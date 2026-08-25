from datetime import datetime,timezone
from fastapi import APIRouter,Depends
from app.market_data.service import MarketDataService,get_market_data_provider
router=APIRouter(prefix='/markets',tags=['markets'])
@router.get('/overview')
async def overview(provider=Depends(get_market_data_provider)):
    svc=MarketDataService(provider); symbols=['AAPL','MSFT','NVDA','AMD','TSLA','AMZN']; rows=[]; status='CLOSED'
    for s in symbols:
        try:
            q=await svc.get_quote(s); bars=await svc.get_bars(s,'1Day',2); prev=bars[-2].close if len(bars)>1 else q.price; pct=(q.price/prev-1)*100 if prev else 0; status=q.market_session
            rows.append({'ticker':s,'price':q.price,'change_pct':round(pct,3),'volume':bars[-1].volume if bars else None})
        except Exception:continue
    gain=sorted(rows,key=lambda x:x['change_pct'],reverse=True); active=sorted(rows,key=lambda x:x.get('volume') or 0,reverse=True)
    return {'indexes':[{'symbol':'SPY','name':'S&P 500','change_pct':0.0},{'symbol':'QQQ','name':'Nasdaq 100','change_pct':0.0},{'symbol':'DIA','name':'Dow Jones','change_pct':0.0}], 'market_status':status,'top_gainers':gain[:5],'top_losers':list(reversed(gain[-5:])),'most_active':active[:5],'generated_at':datetime.now(timezone.utc)}
