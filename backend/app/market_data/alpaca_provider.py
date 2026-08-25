from __future__ import annotations
import json
from datetime import date, datetime, time, timezone
from typing import AsyncIterator, Any
from zoneinfo import ZoneInfo
import httpx
import pandas as pd
from app.domain.models import DataQuality, PriceBar, Quote
from app.prediction.calendar import ReferenceResult, establish_reference_with_quality
from app.market_data.feed_entitlement import resolve_feed_entitlement

ET=ZoneInfo("America/New_York")
class MarketDataProviderError(RuntimeError): pass
class ProviderAuthenticationError(MarketDataProviderError): pass
class ProviderUnavailableError(MarketDataProviderError): pass
class ProviderPayloadError(MarketDataProviderError): pass

def _ts(value:str)->datetime:
    return datetime.fromisoformat(value.replace("Z","+00:00"))

def _session(now:datetime)->str:
    et=now.astimezone(ET); t=et.time()
    if et.weekday()>=5: return "CLOSED"
    if t < time(9,30): return "PRE-MARKET"
    if t < time(16): return "OPEN"
    if t < time(20): return "AFTER HOURS"
    return "CLOSED"

class AlpacaMarketDataProvider:
    def __init__(self, *, api_key:str, api_secret:str, feed:str="iex", sip_entitled:bool=False, client:Any|None=None, ws_connect=None):
        feed=feed.lower().strip()
        entitlement = resolve_feed_entitlement(feed, sip_entitled=sip_entitled)
        self.feed=feed; self.sip_entitled=sip_entitled; self._entitlement=entitlement
        self._headers={"APCA-API-KEY-ID":api_key,"APCA-API-SECRET-KEY":api_secret}
        self._client=client or httpx.AsyncClient(base_url="https://data.alpaca.markets",timeout=15)
        self._ws_connect=ws_connect

    @property
    def feed_scope(self): return self._entitlement.scope
    @property
    def quality(self): return DataQuality.VERIFIED if self.feed=="sip" else DataQuality.LIMITED
    @property
    def consolidated(self): return self._entitlement.consolidated
    @property
    def feed_label(self): return self._entitlement.display_label

    async def _json(self,path,params=None):
        try: r=await self._client.get(path,params=params,headers=self._headers)
        except (httpx.TimeoutException,httpx.TransportError) as e: raise ProviderUnavailableError("Alpaca unavailable") from e
        if r.status_code in {401,403}: raise ProviderAuthenticationError("Alpaca authentication/entitlement rejected")
        if r.status_code>=500: raise ProviderUnavailableError(f"Alpaca returned {r.status_code}")
        if r.status_code>=400: raise MarketDataProviderError(f"Alpaca request failed {r.status_code}")
        try:return r.json()
        except ValueError as e: raise ProviderPayloadError("Alpaca returned invalid JSON") from e

    async def get_quote(self,ticker:str)->Quote:
        p=await self._json(f"/v2/stocks/{ticker}/trades/latest",{"feed":self.feed})
        trade=p.get("trade") or {}; price=float(trade["p"]); pts=_ts(trade["t"]); now=datetime.now(timezone.utc)
        return Quote(ticker=ticker,price=price,provider="alpaca",provider_timestamp=pts,normalized_timestamp=now,
                     market_session=_session(now),freshness_seconds=max(0,(now-pts).total_seconds()),data_quality=self.quality,
                     feed_scope=self.feed_scope,feed_label=self.feed_label,consolidated=self.consolidated)

    async def get_bars(self,ticker:str,timeframe:str,limit:int)->list[PriceBar]:
        if limit<=0: raise ValueError("limit must be positive")
        p=await self._json(f"/v2/stocks/{ticker}/bars",{"feed":self.feed,"timeframe":timeframe,"limit":limit,"adjustment":"all","sort":"asc"})
        raw=p.get("bars");
        if not isinstance(raw,list): raise ProviderPayloadError("bars are missing")
        return [PriceBar(timestamp=_ts(x["t"]),open=float(x["o"]),high=float(x["h"]),low=float(x["l"]),close=float(x["c"]),volume=float(x["v"])) for x in raw]

    async def get_weekly_reference(self,ticker:str,session_date:date)->ReferenceResult:
        bars=await self.get_bars(ticker,"1Min",2500)
        rows=[{"timestamp":b.timestamp,"close":b.close,"volume":b.volume} for b in bars if b.timestamp.astimezone(ET).date()==session_date]
        if rows:
            try:return establish_reference_with_quality(pd.DataFrame(rows))
            except ValueError: pass
        return ReferenceResult((await self.get_quote(ticker)).price,DataQuality.LIMITED)

    async def list_assets(self)->list[dict]:
        try:r=await self._client.get("https://paper-api.alpaca.markets/v2/assets",params={"status":"active","asset_class":"us_equity"},headers=self._headers)
        except (httpx.TimeoutException,httpx.TransportError) as e: raise ProviderUnavailableError("Alpaca asset catalog unavailable") from e
        if r.status_code in {401,403}: raise ProviderAuthenticationError("Alpaca asset catalog authentication rejected")
        r.raise_for_status(); payload=r.json(); out=[]
        for x in payload if isinstance(payload,list) else []:
            symbol=str(x.get("symbol","")).upper().strip(); name=str(x.get("name","")).strip(); exch=str(x.get("exchange","")).upper().strip()
            if x.get("status")=="active" and x.get("tradable") and symbol and name and exch and exch!="OTC":
                out.append({"ticker":symbol,"company":name,"exchange":exch,"sector":None})
        return sorted(out,key=lambda x:x["ticker"])

    async def stream_quotes(self,tickers:list[str])->AsyncIterator[Quote]:
        if self._ws_connect is None:
            import websockets
            connector=websockets.connect
        else: connector=self._ws_connect
        symbols=sorted({x.upper() for x in tickers})
        async with connector(f"wss://stream.data.alpaca.markets/v2/{self.feed}",open_timeout=10,close_timeout=5) as ws:
            await ws.send(json.dumps({"action":"auth","key":self._headers["APCA-API-KEY-ID"],"secret":self._headers["APCA-API-SECRET-KEY"]}))
            authed=False
            async for raw in ws:
                events=json.loads(raw); events=events if isinstance(events,list) else [events]
                for e in events:
                    if e.get("T")=="success" and e.get("msg")=="authenticated": authed=True; await ws.send(json.dumps({"action":"subscribe","trades":symbols})); continue
                    if e.get("T")=="error": raise MarketDataProviderError(str(e.get("msg","stream error")))
                    if e.get("T")!="t": continue
                    pts=_ts(e["t"]); now=datetime.now(timezone.utc)
                    yield Quote(ticker=str(e["S"]).upper(),price=float(e["p"]),provider="alpaca",provider_timestamp=pts,normalized_timestamp=now,
                                market_session=_session(now),freshness_seconds=max(0,(now-pts).total_seconds()),data_quality=self.quality,
                                feed_scope=self.feed_scope,feed_label=self.feed_label,consolidated=self.consolidated)

    async def aclose(self): await self._client.aclose()
