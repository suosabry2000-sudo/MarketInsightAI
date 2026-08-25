from __future__ import annotations
import os
from app.domain.models import DataQuality
from app.api.scanner import build_scanner_snapshot,_sort
from app.api.stocks import DEFAULT

async def resolve_scanner_tickers(provider):
    configured=os.getenv('SCANNER_TICKERS','').strip()
    if configured:return list(dict.fromkeys(x.strip().upper() for x in configured.split(',') if x.strip()))
    loader=getattr(provider,'list_assets',None)
    if callable(loader):
        try:assets=await loader()
        except Exception:assets=[]
        values=[];seen=set()
        for item in assets:
            ticker=str(item.get('ticker','')).strip().upper() if isinstance(item,dict) else ''
            if ticker and ticker not in seen:seen.add(ticker);values.append(ticker)
        if values:return values
    return [x['ticker'] for x in DEFAULT]

class ScannerWorker:
    def __init__(self,provider,cache,*,batch_size=50,compute=build_scanner_snapshot):self.provider=provider;self.cache=cache;self.batch_size=max(1,batch_size);self.compute=compute
    async def run(self,universe,tickers,sort='opportunity'):
        old=await self.cache.get_scanner_snapshot(universe)
        try:
            batches=[tickers[i:i+self.batch_size] for i in range(0,len(tickers),self.batch_size)]
            if not batches:raise ValueError('empty scanner universe')
            snaps=[await self.compute(self.provider,b,sort) for b in batches];first=snaps[0];result=first.model_copy(update={'stocks':_sort([row for s in snaps for row in s.stocks],sort)})
        except Exception:
            if old is None:raise
            result=old.model_copy(update={'stocks':[r.model_copy(update={'data_quality':DataQuality.STALE}) for r in old.stocks]})
        await self.cache.set_scanner_snapshot(universe,result);return result
