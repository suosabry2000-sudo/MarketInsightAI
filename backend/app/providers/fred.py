from __future__ import annotations
from datetime import datetime
import httpx

class FredProvider:
    SERIES={"FEDFUNDS":"FEDFUNDS","CPI_YOY":"CPIAUCSL","YIELD_CURVE_10Y2Y":"T10Y2Y"}
    def __init__(self,api_key:str,client=None): self.api_key=api_key; self._client=client or httpx.AsyncClient(base_url="https://api.stlouisfed.org",timeout=15)
    async def get_latest_value(self,series_id:str,as_of:datetime):
        r=await self._client.get("/fred/series/observations",params={"series_id":series_id,"api_key":self.api_key,"file_type":"json","observation_end":as_of.date().isoformat(),"realtime_end":as_of.date().isoformat(),"sort_order":"desc"}); r.raise_for_status()
        for x in r.json().get("observations",[]):
            if x.get("value") in {None,"."}:continue
            observed=datetime.fromisoformat(x["date"]).date(); realtime=datetime.fromisoformat(x.get("realtime_start",x["date"])).date()
            if observed<=as_of.date() and realtime<=as_of.date(): return float(x["value"])
        return None
    async def get_macro_values(self,as_of:datetime)->dict[str,float|None]:
        return {key:await self.get_latest_value(sid,as_of) for key,sid in self.SERIES.items()}
    async def aclose(self): await self._client.aclose()
