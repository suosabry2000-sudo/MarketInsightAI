from __future__ import annotations
from datetime import datetime
import httpx

class SecProvider:
    def __init__(self,user_agent:str,client=None):
        if not user_agent.strip(): raise ValueError("SEC user agent is required")
        self._client=client or httpx.AsyncClient(timeout=15)
        self.headers={"User-Agent":user_agent,"Accept-Encoding":"gzip, deflate"}; self._ciks=None
    async def _json(self,url):
        r=await self._client.get(url,headers=self.headers); r.raise_for_status(); return r.json()
    async def resolve_cik(self,ticker:str)->int:
        if self._ciks is None:
            raw=await self._json("https://www.sec.gov/files/company_tickers.json")
            self._ciks={str(x["ticker"]).upper():int(x["cik_str"]) for x in raw.values()}
        if ticker.upper() not in self._ciks: raise KeyError(ticker)
        return self._ciks[ticker.upper()]
    @staticmethod
    def _annual(facts:dict,name:str,unit:str):
        rows=facts.get("us-gaap",{}).get(name,{}).get("units",{}).get(unit,[])
        values=[x for x in rows if x.get("form") in {"10-K","10-K/A"} and x.get("val") is not None]
        latest={}
        for row in values:
            fy=row.get("fy");
            if fy is not None: latest[int(fy)]=float(row["val"])
        return sorted(latest.items())
    async def get_normalized_fundamentals(self,ticker:str,*,as_of:datetime)->dict:
        cik=await self.resolve_cik(ticker); raw=await self._json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"); facts=raw.get("facts",{})
        rev=self._annual(facts,"Revenues","USD") or self._annual(facts,"RevenueFromContractWithCustomerExcludingAssessedTax","USD")
        eps=self._annual(facts,"EarningsPerShareDiluted","USD/shares")
        op=self._annual(facts,"OperatingIncomeLoss","USD"); cash=self._annual(facts,"CashAndCashEquivalentsAtCarryingValue","USD"); debt=self._annual(facts,"LongTermDebt","USD")
        ni=self._annual(facts,"NetIncomeLoss","USD")
        out={}
        if len(rev)>=2 and rev[-2][1]: out["revenue_growth"]=rev[-1][1]/rev[-2][1]-1
        if len(eps)>=2 and eps[-2][1]: out["eps_growth"]=eps[-1][1]/eps[-2][1]-1
        if rev and op and rev[-1][1]: out["operating_margin"]=op[-1][1]/rev[-1][1]
        if ni: out["net_income"]=ni[-1][1]
        if cash: out["cash"]=cash[-1][1]
        if debt: out["debt"]=debt[-1][1]
        if cash and cash[-1][1]>0: out["debt_to_cash"]=(debt[-1][1] if debt else 0)/cash[-1][1]
        return out
    async def aclose(self): await self._client.aclose()
