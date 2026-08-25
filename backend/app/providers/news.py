from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class NewsEvent:
    headline: str
    publisher: str
    published_at: datetime
    sentiment: float
    relevance: float
    importance: float
    material: bool

import re
import httpx

_POSITIVE=("beat","beats","upgrade","growth","record","strong","surge","approval","raises guidance","profit")
_NEGATIVE=("miss","misses","downgrade","lawsuit","risk","decline","weak","cuts guidance","probe","recall","loss")

def headline_sentiment(headline:str)->float:
    text=headline.lower(); pos=sum(token in text for token in _POSITIVE); neg=sum(token in text for token in _NEGATIVE)
    if pos==neg:return 0.0
    return max(-1.0,min(1.0,(pos-neg)/max(1,pos+neg)))

class AlpacaNewsProvider:
    def __init__(self,api_key:str,api_secret:str,client=None):
        self._client=client or httpx.AsyncClient(base_url="https://data.alpaca.markets",timeout=15)
        self._headers={"APCA-API-KEY-ID":api_key,"APCA-API-SECRET-KEY":api_secret}
    async def get_events(self,ticker:str,*,start:datetime,end:datetime)->list[NewsEvent]:
        r=await self._client.get("/v1beta1/news",params={"symbols":ticker.upper(),"start":start.isoformat(),"end":end.isoformat(),"limit":50,"sort":"desc"},headers=self._headers)
        r.raise_for_status(); out=[]
        for row in r.json().get("news",[]):
            created=datetime.fromisoformat(str(row.get("created_at","")).replace("Z","+00:00"))
            if created < start or created > end: continue
            headline=str(row.get("headline","")).strip()
            if not headline: continue
            sentiment=headline_sentiment(headline)
            lower=headline.lower(); material=any(x in lower for x in ("earnings","guidance","acquisition","merger","lawsuit","probe","recall","approval","sec ","fda "))
            importance=.9 if material else .5; relevance=.95 if ticker.upper() in [str(s).upper() for s in row.get("symbols",[])] else .7
            out.append(NewsEvent(headline,str(row.get("author") or row.get("source") or "Financial news"),created,sentiment,relevance,importance,material))
        return out
    async def aclose(self): await self._client.aclose()
