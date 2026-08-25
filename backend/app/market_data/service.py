from __future__ import annotations
import re
from fastapi import Request
from app.domain.models import Quote, PriceBar
from app.market_data.provider import MarketDataProvider

_TICKER = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")

def normalize_ticker(value: str) -> str:
    ticker = value.strip().upper()
    if not _TICKER.fullmatch(ticker):
        raise ValueError("invalid ticker")
    return ticker

class MarketDataService:
    def __init__(self, provider: MarketDataProvider): self.provider = provider
    async def get_quote(self, ticker: str) -> Quote: return await self.provider.get_quote(normalize_ticker(ticker))
    async def get_bars(self, ticker: str, timeframe: str, limit: int) -> list[PriceBar]:
        return await self.provider.get_bars(normalize_ticker(ticker), timeframe, limit)

def get_market_data_provider(request: Request) -> MarketDataProvider:
    return request.app.state.market_data_provider
