from __future__ import annotations
import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import AsyncIterator
from app.domain.models import DataQuality, PriceBar, Quote
from app.prediction.calendar import ReferenceResult

SEED = {
    "AAPL": (310.80, "Apple Inc."), "MSFT": (521.30, "Microsoft Corporation"),
    "NVDA": (194.20, "NVIDIA Corporation"), "AMD": (182.40, "Advanced Micro Devices, Inc."),
    "TSLA": (345.00, "Tesla, Inc."), "AMZN": (235.00, "Amazon.com, Inc."),
    "GOOGL": (205.00, "Alphabet Inc."), "META": (755.00, "Meta Platforms, Inc."),
    "SPY": (650.0, "SPDR S&P 500 ETF Trust"), "QQQ": (575.0, "Invesco QQQ Trust"),
}

class FakeMarketDataProvider:
    def __init__(self, quotes=None, bars=None, weekly_references=None):
        self.quotes = quotes or {}
        self.bars = bars or {}
        self.weekly_references = weekly_references or {}

    async def get_quote(self, ticker: str) -> Quote:
        if ticker in self.quotes: return self.quotes[ticker]
        if ticker not in SEED: raise KeyError(ticker)
        price = SEED[ticker][0]; now = datetime.now(timezone.utc)
        return Quote(ticker=ticker, price=price, provider="fixture", provider_timestamp=now,
                     normalized_timestamp=now, market_session="OPEN", freshness_seconds=0,
                     data_quality=DataQuality.VERIFIED, feed_scope="TEST_FIXTURE", feed_label="Fixture")

    async def get_bars(self, ticker: str, timeframe: str, limit: int) -> list[PriceBar]:
        if ticker in self.bars: return self.bars[ticker][-limit:]
        if ticker not in SEED: raise KeyError(ticker)
        price=SEED[ticker][0]; now=datetime.now(timezone.utc)
        count=max(30, min(limit,260)); out=[]
        for i in range(count):
            x=i-(count-1); close=price*(1+x*0.0012) + ((i%7)-3)*price*0.0006
            out.append(PriceBar(timestamp=now-timedelta(days=count-1-i),open=close*.998,high=close*1.006,low=close*.994,close=close,volume=1_000_000+i*5000))
        return out

    async def get_weekly_reference(self, ticker: str, session_date: date) -> ReferenceResult:
        value=self.weekly_references.get(ticker)
        if value is None: value=(await self.get_quote(ticker)).price*.997
        return ReferenceResult(float(value), DataQuality.VERIFIED)

    async def list_assets(self) -> list[dict]:
        return [{"ticker":k,"company":v[1],"exchange":"NASDAQ" if k not in {"SPY"} else "NYSEARCA","sector":"Technology" if k in {"AAPL","MSFT","NVDA","AMD","GOOGL","META"} else None} for k,v in SEED.items() if k not in {"SPY","QQQ"}]

    async def stream_quotes(self, tickers: list[str]) -> AsyncIterator[Quote]:
        while True:
            for ticker in tickers: yield await self.get_quote(ticker)
            await asyncio.sleep(1)
