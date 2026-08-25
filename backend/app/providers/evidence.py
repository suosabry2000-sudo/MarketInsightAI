from __future__ import annotations
from datetime import datetime,timedelta,timezone
import logging
log=logging.getLogger("marketinsight.evidence")

class EvidenceService:
    def __init__(self,*,sec=None,news=None,fred=None): self.sec=sec; self.news=news; self.fred=fred
    async def analysis_context(self,ticker:str,*,as_of:datetime):
        cutoff=as_of if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
        out={"fundamental_data":None,"news_events":None,"fred_values":None}
        if self.sec:
            try:out["fundamental_data"]=await self.sec.get_normalized_fundamentals(ticker,as_of=cutoff)
            except Exception as e:log.warning("SEC evidence unavailable: %s",e.__class__.__name__)
        if self.news:
            try:out["news_events"]=await self.news.get_events(ticker,start=cutoff-timedelta(days=7),end=cutoff)
            except Exception as e:log.warning("News evidence unavailable: %s",e.__class__.__name__)
        if self.fred:
            try:out["fred_values"]=await self.fred.get_macro_values(cutoff)
            except Exception as e:log.warning("Macro evidence unavailable: %s",e.__class__.__name__)
        return out
    async def aclose(self):
        seen=set()
        for p in (self.sec,self.news,self.fred):
            if p and id(p) not in seen:
                seen.add(id(p)); close=getattr(p,"aclose",None)
                if callable(close):await close()
