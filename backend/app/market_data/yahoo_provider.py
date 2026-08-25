from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timezone
from typing import AsyncIterator, Any
from zoneinfo import ZoneInfo

import httpx
import pandas as pd

from app.domain.models import DataQuality, PriceBar, Quote
from app.prediction.calendar import ReferenceResult, establish_reference_with_quality

ET = ZoneInfo("America/New_York")


class YahooMarketDataProviderError(RuntimeError):
    pass


def _session(now: datetime) -> str:
    et = now.astimezone(ET)
    t = et.time()
    if et.weekday() >= 5:
        return "CLOSED"
    if t < time(9, 30):
        return "PRE-MARKET"
    if t < time(16, 0):
        return "OPEN"
    if t < time(20, 0):
        return "AFTER HOURS"
    return "CLOSED"


def _utc_from_epoch(value: Any) -> datetime:
    return datetime.fromtimestamp(float(value), tz=timezone.utc)


class YahooMarketDataProvider:
    """No-key public fallback market provider.

    This provider is intentionally labeled LIMITED and non-consolidated. It is useful for
    keeping the app functional before a paid/consolidated SIP entitlement is configured.
    """

    def __init__(self, *, client: httpx.AsyncClient | None = None, sec_user_agent: str | None = None):
        self._client = client or httpx.AsyncClient(timeout=15.0, follow_redirects=True)
        self.sec_user_agent = (sec_user_agent or "MarketInsightAI/1.0 github.com/suosabry2000-sudo").strip()
        self.feed_scope = "PUBLIC_WEB_FALLBACK"
        self.feed_label = "Yahoo Finance public market feed — may be delayed"
        self.consolidated = False
        self.quality = DataQuality.LIMITED

    async def _chart(self, ticker: str, *, range_value: str, interval: str) -> dict:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        try:
            response = await self._client.get(
                url,
                params={"range": range_value, "interval": interval, "includePrePost": "true", "events": "div,splits"},
                headers={"User-Agent": "Mozilla/5.0 MarketInsightAI/1.0"},
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise YahooMarketDataProviderError("Yahoo market data unavailable") from exc
        if response.status_code >= 400:
            raise YahooMarketDataProviderError(f"Yahoo market data returned {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise YahooMarketDataProviderError("Yahoo market data returned invalid JSON") from exc
        chart = payload.get("chart") if isinstance(payload, dict) else None
        result = (chart or {}).get("result") if isinstance(chart, dict) else None
        if not result or not isinstance(result, list) or not isinstance(result[0], dict):
            error = (chart or {}).get("error") if isinstance(chart, dict) else None
            raise YahooMarketDataProviderError(f"Yahoo market data missing chart result: {error}")
        return result[0]

    async def get_quote(self, ticker: str) -> Quote:
        result = await self._chart(ticker, range_value="1d", interval="1m")
        meta = result.get("meta") or {}
        price = meta.get("regularMarketPrice")
        if price is None:
            quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
            closes = [x for x in (quotes.get("close") or []) if x is not None]
            if closes:
                price = closes[-1]
        if price is None:
            raise YahooMarketDataProviderError("Yahoo quote is missing price")
        now = datetime.now(timezone.utc)
        market_time = meta.get("regularMarketTime")
        pts = _utc_from_epoch(market_time) if market_time else now
        return Quote(
            ticker=ticker.upper(),
            price=float(price),
            currency=str(meta.get("currency") or "USD"),
            provider="yahoo",
            provider_timestamp=pts,
            normalized_timestamp=now,
            market_session=_session(now),
            freshness_seconds=max(0.0, (now - pts).total_seconds()),
            data_quality=self.quality,
            feed_scope=self.feed_scope,
            feed_label=self.feed_label,
            consolidated=False,
        )

    async def get_bars(self, ticker: str, timeframe: str, limit: int) -> list[PriceBar]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        tf = timeframe.lower()
        if tf in {"1min", "1m"}:
            range_value, interval = "5d", "1m"
        elif tf in {"5min", "5m"}:
            range_value, interval = "1mo", "5m"
        elif tf in {"1hour", "1h", "60min"}:
            range_value, interval = "6mo", "1h"
        else:
            range_value, interval = ("2y", "1d") if limit <= 520 else ("10y", "1d")
        result = await self._chart(ticker, range_value=range_value, interval=interval)
        timestamps = result.get("timestamp") or []
        quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
        opens, highs, lows, closes, volumes = (
            quotes.get("open") or [],
            quotes.get("high") or [],
            quotes.get("low") or [],
            quotes.get("close") or [],
            quotes.get("volume") or [],
        )
        out: list[PriceBar] = []
        for i, ts in enumerate(timestamps):
            values = [seq[i] if i < len(seq) else None for seq in (opens, highs, lows, closes, volumes)]
            if any(v is None for v in values[:4]):
                continue
            out.append(
                PriceBar(
                    timestamp=_utc_from_epoch(ts),
                    open=float(values[0]),
                    high=float(values[1]),
                    low=float(values[2]),
                    close=float(values[3]),
                    volume=max(0.0, float(values[4] or 0.0)),
                )
            )
        if not out:
            raise YahooMarketDataProviderError("Yahoo bars are empty")
        return out[-limit:]

    async def get_weekly_reference(self, ticker: str, session_date: date) -> ReferenceResult:
        try:
            bars = await self.get_bars(ticker, "1Min", 2500)
            rows = [
                {"timestamp": b.timestamp, "close": b.close, "volume": b.volume}
                for b in bars
                if b.timestamp.astimezone(ET).date() == session_date
            ]
            if rows:
                return establish_reference_with_quality(pd.DataFrame(rows))
        except Exception:
            pass
        quote = await self.get_quote(ticker)
        return ReferenceResult(quote.price, DataQuality.LIMITED)

    async def list_assets(self) -> list[dict]:
        try:
            response = await self._client.get(
                "https://www.sec.gov/files/company_tickers_exchange.json",
                headers={
                    "User-Agent": self.sec_user_agent,
                    "Accept-Encoding": "gzip, deflate",
                    "Accept": "application/json",
                },
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise YahooMarketDataProviderError("SEC stock catalog unavailable") from exc
        if response.status_code >= 400:
            raise YahooMarketDataProviderError(f"SEC stock catalog returned {response.status_code}")
        payload = response.json()
        fields = payload.get("fields") or []
        rows = payload.get("data") or []
        try:
            ticker_i, name_i, exchange_i = fields.index("ticker"), fields.index("name"), fields.index("exchange")
        except ValueError as exc:
            raise YahooMarketDataProviderError("SEC stock catalog schema changed") from exc
        allowed = {"NASDAQ", "NYSE", "NYSE AMERICAN"}
        out: list[dict] = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, list) or max(ticker_i, name_i, exchange_i) >= len(row):
                continue
            ticker = str(row[ticker_i] or "").upper().strip()
            company = str(row[name_i] or "").strip()
            exchange_raw = str(row[exchange_i] or "").strip()
            exchange = "NASDAQ" if exchange_raw.lower() == "nasdaq" else exchange_raw.upper()
            if not ticker or not company or exchange not in allowed or ticker in seen:
                continue
            seen.add(ticker)
            out.append({"ticker": ticker, "company": company, "exchange": exchange, "sector": None})
        return sorted(out, key=lambda item: item["ticker"])

    async def stream_quotes(self, tickers: list[str]) -> AsyncIterator[Quote]:
        symbols = sorted({x.upper().strip() for x in tickers if x.strip()})
        while True:
            for ticker in symbols:
                try:
                    yield await self.get_quote(ticker)
                except Exception:
                    continue
            await asyncio.sleep(5)

    async def aclose(self) -> None:
        await self._client.aclose()
