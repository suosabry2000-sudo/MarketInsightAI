from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.domain.models import DataQuality, Quote
from app.market_data.service import MarketDataService, get_market_data_provider, normalize_ticker

router = APIRouter(prefix="/stocks", tags=["stocks"])

DEFAULT = [
    {"ticker":"AAPL","company":"Apple Inc.","exchange":"NASDAQ","sector":"Technology","asset_type":"STOCK","index_memberships":["S&P 500","Nasdaq"],"themes":["Technology","AI"],"market_cap_bucket":"Mega Cap","most_active":True},
    {"ticker":"MSFT","company":"Microsoft Corporation","exchange":"NASDAQ","sector":"Technology","asset_type":"STOCK","index_memberships":["S&P 500","Nasdaq","Dow"],"themes":["Technology","AI"],"market_cap_bucket":"Mega Cap","most_active":True},
    {"ticker":"NVDA","company":"NVIDIA Corporation","exchange":"NASDAQ","sector":"Technology","asset_type":"STOCK","index_memberships":["S&P 500","Nasdaq"],"themes":["Technology","AI","Semiconductors"],"market_cap_bucket":"Mega Cap","most_active":True},
    {"ticker":"AMD","company":"Advanced Micro Devices, Inc.","exchange":"NASDAQ","sector":"Technology","asset_type":"STOCK","index_memberships":["S&P 500","Nasdaq"],"themes":["Technology","AI","Semiconductors"],"market_cap_bucket":"Mega Cap","most_active":True},
    {"ticker":"TSLA","company":"Tesla, Inc.","exchange":"NASDAQ","sector":"Consumer","asset_type":"STOCK"},
    {"ticker":"AMZN","company":"Amazon.com, Inc.","exchange":"NASDAQ","sector":"Consumer","asset_type":"STOCK"},
]


async def catalog(request: Request, provider):
    cached = getattr(request.app.state, "stock_catalog", None)
    if cached is not None:
        return list(cached)
    loader = getattr(provider, "list_assets", None)
    if callable(loader):
        try:
            items = await loader()
        except Exception:
            items = []
        if items:
            request.app.state.stock_catalog = items
            return list(items)
    return list(DEFAULT)


def _matches(item: dict[str, Any], *, q: str, exchange: str, sector: str, asset_type: str) -> bool:
    needle = q.strip().lower()
    if needle and needle not in str(item.get("ticker", "")).lower() and needle not in str(item.get("company", "")).lower():
        return False
    if exchange and exchange.upper() != "ALL" and str(item.get("exchange", "")).upper() != exchange.upper():
        return False
    if sector and sector.upper() != "ALL" and str(item.get("sector") or "").upper() != sector.upper():
        return False
    if asset_type and asset_type.upper() != "ALL" and str(item.get("asset_type") or "STOCK").upper() != asset_type.upper():
        return False
    return True


def _change_pct(quote: Quote) -> float | None:
    value = getattr(quote, "change_pct", None)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _enrich(item: dict[str, Any], quote: Quote | None) -> dict[str, Any]:
    base = {**item, "asset_type": str(item.get("asset_type") or "STOCK").upper(), "robinhood_verified": False}
    if quote is None:
        return {**base, "price": None, "change_pct": None, "price_status": "UNAVAILABLE", "data_quality": None}
    status = "STALE" if quote.data_quality in {DataQuality.STALE, DataQuality.DATA_CONFLICT, DataQuality.NO_RELIABLE_FORECAST} else "AVAILABLE"
    return {
        **base,
        "price": float(quote.price),
        "change_pct": _change_pct(quote),
        "price_status": status,
        "data_quality": quote.data_quality.value,
    }


async def _provider_quotes(provider, tickers: list[str]) -> dict[str, Quote]:
    symbols = list(dict.fromkeys(t.upper() for t in tickers if t))
    if not symbols:
        return {}
    bulk = getattr(provider, "get_quotes", None)
    if callable(bulk):
        try:
            values = await bulk(symbols)
            if isinstance(values, dict):
                return {str(k).upper(): v for k, v in values.items() if isinstance(v, Quote)}
        except Exception:
            pass

    semaphore = asyncio.Semaphore(8)

    async def one(symbol: str):
        async with semaphore:
            try:
                return symbol, await provider.get_quote(symbol)
            except Exception:
                return symbol, None

    rows = await asyncio.gather(*(one(s) for s in symbols))
    return {symbol: quote for symbol, quote in rows if quote is not None}


async def _quotes(request: Request, provider, tickers: list[str], ttl_seconds: int = 60) -> dict[str, Quote]:
    now = time.monotonic()
    cache = getattr(request.app.state, "catalog_quote_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        request.app.state.catalog_quote_cache = cache

    output: dict[str, Quote] = {}
    missing: list[str] = []
    for ticker in tickers:
        entry = cache.get(ticker)
        if isinstance(entry, tuple) and len(entry) == 2 and now - float(entry[0]) < ttl_seconds:
            output[ticker] = entry[1]
        else:
            missing.append(ticker)

    if missing:
        fresh = await _provider_quotes(provider, missing)
        for ticker, quote in fresh.items():
            cache[ticker] = (now, quote)
            output[ticker] = quote
    return output


@router.get("/catalog")
async def list_catalog(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=5000),
    sort: str = Query("symbol"),
    direction: str = Query("asc"),
    q: str = Query("", max_length=80),
    exchange: str = Query("ALL", max_length=40),
    sector: str = Query("ALL", max_length=80),
    asset_type: str = Query("ALL", max_length=20),
    provider=Depends(get_market_data_provider),
):
    items = [
        x for x in await catalog(request, provider)
        if _matches(x, q=q, exchange=exchange, sector=sector, asset_type=asset_type)
    ]
    sort_key = sort.strip().lower()
    descending = direction.strip().lower() == "desc"
    if sort_key not in {"symbol", "company", "price", "change"}:
        raise HTTPException(422, "unsupported catalog sort")

    total = len(items)
    if sort_key in {"price", "change"}:
        quotes = await _quotes(request, provider, [str(x.get("ticker", "")).upper() for x in items])
        enriched = [_enrich(x, quotes.get(str(x.get("ticker", "")).upper())) for x in items]
        field = "price" if sort_key == "price" else "change_pct"

        def numeric_key(row):
            value = row.get(field)
            missing = value is None
            number = float(value) if value is not None else 0.0
            return (missing, -number if descending else number, str(row.get("ticker", "")))

        enriched.sort(key=numeric_key)
        page = enriched[offset:offset + limit]
    else:
        field = "ticker" if sort_key == "symbol" else "company"
        items.sort(key=lambda x: str(x.get(field, "")).lower(), reverse=descending)
        raw_page = items[offset:offset + limit]
        quotes = await _quotes(request, provider, [str(x.get("ticker", "")).upper() for x in raw_page])
        page = [_enrich(x, quotes.get(str(x.get("ticker", "")).upper())) for x in raw_page]

    return {
        "results": page,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(page) < total,
        "sort": sort_key,
        "direction": "desc" if descending else "asc",
    }


@router.get("/search")
async def search(request: Request, q: str = Query(min_length=1, max_length=80), provider=Depends(get_market_data_provider)):
    needle = q.strip().lower()
    items = await catalog(request, provider)
    matches = [x for x in items if needle in str(x.get("ticker", "")).lower() or needle in str(x.get("company", "")).lower()]
    matches.sort(key=lambda x: (0 if str(x.get("ticker", "")).lower() == needle else 1, str(x.get("ticker", ""))))
    return {"results": matches[:25]}


@router.get("/{ticker}")
async def stock(request: Request, ticker: str, provider=Depends(get_market_data_provider)):
    symbol = normalize_ticker(ticker)
    items = await catalog(request, provider)
    meta = next((x for x in items if str(x.get("ticker", "")).upper() == symbol), None)
    if meta is None:
        raise HTTPException(404, f"ticker {symbol} not found")
    return {**meta, "latest": await MarketDataService(provider).get_quote(symbol)}
