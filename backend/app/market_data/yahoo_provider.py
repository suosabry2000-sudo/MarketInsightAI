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


def _asset_type(company: str) -> str:
    name = company.lower()
    fund_markers = (" etf", "exchange traded fund", "ishares", "spdr ", "vanguard ", "vaneck ", "proshares ", "direxion ", "invesco ")
    return "ETF" if any(marker in name for marker in fund_markers) else "STOCK"


def _market_change_pct(price: float, previous_close: Any) -> float | None:
    try:
        prev = float(previous_close)
    except (TypeError, ValueError):
        return None
    if prev <= 0:
        return None
    return (price - prev) / prev * 100.0


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
            change_pct=_market_change_pct(float(price), meta.get("chartPreviousClose") or meta.get("previousClose")),
        )

    async def get_quotes(self, tickers: list[str]) -> dict[str, Quote]:
        symbols = list(dict.fromkeys(x.upper().strip() for x in tickers if x.strip()))
        now = datetime.now(timezone.utc)
        semaphore = asyncio.Semaphore(6)

        async def fetch_chunk(chunk: list[str]) -> dict[str, Quote]:
            async with semaphore:
                try:
                    response = await self._client.get(
                        "https://query1.finance.yahoo.com/v7/finance/spark",
                        params={"symbols": ",".join(chunk), "range": "1d", "interval": "1d", "includePrePost": "true"},
                        headers={"User-Agent": "Mozilla/5.0 MarketInsightAI/1.0"},
                    )
                    response.raise_for_status()
                    results = ((response.json() or {}).get("spark") or {}).get("result") or []
                except Exception:
                    return {}

            chunk_quotes: dict[str, Quote] = {}
            for result in results:
                symbol = str(result.get("symbol") or "").upper()
                responses = result.get("response") or []
                if not symbol or not responses:
                    continue
                meta = responses[0].get("meta") or {}
                price = meta.get("regularMarketPrice")
                if price is None:
                    closes = (((responses[0].get("indicators") or {}).get("quote") or [{}])[0].get("close") or [])
                    closes = [x for x in closes if x is not None]
                    price = closes[-1] if closes else None
                if price is None:
                    continue
                market_time = meta.get("regularMarketTime")
                pts = _utc_from_epoch(market_time) if market_time else now
                chunk_quotes[symbol] = Quote(
                    ticker=symbol, price=float(price), currency=str(meta.get("currency") or "USD"), provider="yahoo",
                    provider_timestamp=pts, normalized_timestamp=now, market_session=_session(now),
                    freshness_seconds=max(0.0, (now - pts).total_seconds()), data_quality=self.quality,
                    feed_scope=self.feed_scope, feed_label=self.feed_label, consolidated=False,
                    change_pct=_market_change_pct(float(price), meta.get("chartPreviousClose") or meta.get("previousClose")),
                )
            return chunk_quotes

        chunks = [symbols[i:i + 50] for i in range(0, len(symbols), 50)]
        output: dict[str, Quote] = {}
        for part in await asyncio.gather(*(fetch_chunk(chunk) for chunk in chunks)):
            output.update(part)

        missing = [symbol for symbol in symbols if symbol not in output]
        fallback_semaphore = asyncio.Semaphore(8)

        async def fallback(symbol: str):
            async with fallback_semaphore:
                try:
                    return symbol, await self.get_quote(symbol)
                except Exception:
                    return symbol, None

        if missing:
            for symbol, quote in await asyncio.gather(*(fallback(symbol) for symbol in missing)):
                if quote is not None:
                    output[symbol] = quote
        return output

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

    @staticmethod
    def _parse_nasdaq_directory(text: str, *, nasdaq_listed: bool) -> list[dict]:
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            return []
        headers = lines[0].split("|")
        rows: list[dict] = []
        for line in lines[1:]:
            if line.startswith("File Creation Time"):
                continue
            values = line.split("|")
            if len(values) < len(headers):
                values += [""] * (len(headers) - len(values))
            row = dict(zip(headers, values))
            test_issue = str(row.get("Test Issue") or "N").strip().upper()
            if test_issue == "Y":
                continue
            if nasdaq_listed:
                ticker = str(row.get("Symbol") or "").upper().strip()
                company = str(row.get("Security Name") or "").strip()
                exchange = "NASDAQ"
            else:
                ticker = str(row.get("ACT Symbol") or row.get("NASDAQ Symbol") or "").upper().strip()
                company = str(row.get("Security Name") or "").strip()
                exchange = {
                    "N": "NYSE", "A": "NYSE AMERICAN", "P": "NYSE ARCA",
                    "Z": "CBOE", "V": "IEX",
                }.get(str(row.get("Exchange") or "").strip().upper(), "")
            if not ticker or not company or not exchange:
                continue
            etf = str(row.get("ETF") or "").strip().upper() == "Y"
            rows.append({
                "ticker": ticker, "company": company, "exchange": exchange,
                "sector": None, "asset_type": "ETF" if etf else _asset_type(company),
            })
        return rows

    async def _nasdaq_symbol_catalog(self) -> list[dict]:
        headers = {"User-Agent": "Mozilla/5.0 MarketInsightAI/2.0", "Accept": "text/plain,*/*"}
        urls = [
            ("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt", True),
            ("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt", False),
        ]

        async def fetch(url: str, is_nasdaq: bool):
            response = await self._client.get(url, headers=headers)
            response.raise_for_status()
            return self._parse_nasdaq_directory(response.text, nasdaq_listed=is_nasdaq)

        parts = await asyncio.gather(*(fetch(url, flag) for url, flag in urls))
        seen: set[str] = set()
        out: list[dict] = []
        for item in [row for part in parts for row in part]:
            ticker = item["ticker"]
            if ticker in seen:
                continue
            seen.add(ticker)
            out.append(item)
        return sorted(out, key=lambda item: item["ticker"])

    async def _sec_symbol_catalog(self) -> list[dict]:
        response = await self._client.get(
            "https://www.sec.gov/files/company_tickers_exchange.json",
            headers={
                "User-Agent": self.sec_user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        payload = response.json()
        fields = payload.get("fields") or []
        rows = payload.get("data") or []
        try:
            ticker_i, name_i, exchange_i = fields.index("ticker"), fields.index("name"), fields.index("exchange")
        except ValueError as exc:
            raise YahooMarketDataProviderError("SEC stock catalog schema changed") from exc
        allowed = {"NASDAQ", "NYSE", "NYSE AMERICAN", "NYSE ARCA"}
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
            out.append({"ticker": ticker, "company": company, "exchange": exchange, "sector": None, "asset_type": _asset_type(company)})
        return sorted(out, key=lambda item: item["ticker"])

    async def list_assets(self) -> list[dict]:
        errors: list[str] = []
        try:
            items = await self._nasdaq_symbol_catalog()
            if items:
                return items
            errors.append("Nasdaq catalog empty")
        except Exception as exc:
            errors.append(f"Nasdaq catalog failed: {exc.__class__.__name__}")
        try:
            items = await self._sec_symbol_catalog()
            if items:
                return items
            errors.append("SEC catalog empty")
        except Exception as exc:
            errors.append(f"SEC catalog failed: {exc.__class__.__name__}")
        raise YahooMarketDataProviderError("; ".join(errors) or "No symbol catalog available")

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
