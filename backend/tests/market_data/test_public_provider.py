from datetime import date, datetime, timezone

import httpx
import pytest

from app.domain.models import DataQuality
from app.market_data.factory import create_market_data_provider
from app.settings import Settings


@pytest.mark.asyncio
async def test_yahoo_provider_reads_quote_bars_and_sec_catalog_without_api_keys():
    from app.market_data.yahoo_provider import YahooMarketDataProvider

    def handler(req: httpx.Request):
        if req.url.host == "www.sec.gov":
            return httpx.Response(
                200,
                json={
                    "fields": ["cik", "name", "ticker", "exchange"],
                    "data": [
                        [320193, "Apple Inc.", "AAPL", "Nasdaq"],
                        [19617, "JPMorgan Chase & Co.", "JPM", "NYSE"],
                        [1, "OTC Example", "OTCX", "OTC"],
                    ],
                },
            )
        assert req.url.host == "query1.finance.yahoo.com"
        return httpx.Response(
            200,
            json={
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "symbol": "AAPL",
                                "currency": "USD",
                                "regularMarketPrice": 123.45,
                                "regularMarketTime": 1787605200,
                                "exchangeTimezoneName": "America/New_York",
                            },
                            "timestamp": [1787518800, 1787605200],
                            "indicators": {
                                "quote": [
                                    {
                                        "open": [120.0, 122.0],
                                        "high": [124.0, 125.0],
                                        "low": [119.0, 121.0],
                                        "close": [123.0, 123.45],
                                        "volume": [1000, 2000],
                                    }
                                ]
                            },
                        }
                    ],
                    "error": None,
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = YahooMarketDataProvider(client=client, sec_user_agent="MarketInsightAI test@example.com")
        quote = await provider.get_quote("AAPL")
        bars = await provider.get_bars("AAPL", "1Day", 2)
        assets = await provider.list_assets()

    assert quote.price == pytest.approx(123.45)
    assert quote.data_quality == DataQuality.LIMITED
    assert quote.consolidated is False
    assert "Yahoo" in quote.feed_label
    assert [b.close for b in bars] == [123.0, 123.45]
    assert [x["ticker"] for x in assets] == ["AAPL", "JPM"]


def test_factory_can_select_yahoo_without_alpaca_credentials():
    provider = create_market_data_provider(Settings(MARKET_PROVIDER="yahoo"))
    assert provider.__class__.__name__ == "YahooMarketDataProvider"


def test_production_validation_allows_yahoo_without_alpaca_credentials():
    settings = Settings(
        APP_ENV="production",
        MARKET_PROVIDER="yahoo",
        DATABASE_URL="postgresql://example",
        REDIS_URL="redis://example",
        TOKEN_SECRET="x" * 32,
    )
    assert settings.validate_production() is settings


@pytest.mark.asyncio
async def test_yahoo_provider_bulk_quotes_use_single_spark_request_for_multiple_symbols():
    from app.market_data.yahoo_provider import YahooMarketDataProvider

    calls = []

    def handler(req: httpx.Request):
        calls.append(str(req.url))
        assert req.url.path == "/v7/finance/spark"
        return httpx.Response(
            200,
            json={
                "spark": {
                    "result": [
                        {
                            "symbol": "AAPL",
                            "response": [{"meta": {"currency": "USD", "regularMarketPrice": 310.0, "chartPreviousClose": 300.0, "regularMarketTime": 1787605200}}],
                        },
                        {
                            "symbol": "MSFT",
                            "response": [{"meta": {"currency": "USD", "regularMarketPrice": 500.0, "chartPreviousClose": 490.0, "regularMarketTime": 1787605200}}],
                        },
                    ]
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = YahooMarketDataProvider(client=client, sec_user_agent="MarketInsightAI test@example.com")
        quotes = await provider.get_quotes(["AAPL", "MSFT"])

    assert len(calls) == 1
    assert quotes["AAPL"].price == pytest.approx(310.0)
    assert quotes["MSFT"].price == pytest.approx(500.0)
    assert quotes["AAPL"].change_pct == pytest.approx((310.0 - 300.0) / 300.0 * 100.0)


@pytest.mark.asyncio
async def test_yahoo_provider_uses_nasdaq_symbol_directories_when_sec_is_blocked():
    from app.market_data.yahoo_provider import YahooMarketDataProvider

    def handler(req: httpx.Request):
        if req.url.host == "www.nasdaqtrader.com" and req.url.path.endswith("/nasdaqlisted.txt"):
            return httpx.Response(
                200,
                text=(
                    "Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\n"
                    "AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N\n"
                    "QQQ|Invesco QQQ Trust, Series 1|G|N|N|100|Y|N\n"
                    "ZTEST|Test Security|S|Y|N|100|N|N\n"
                    "File Creation Time: 0825202620:00|||||||\n"
                ),
            )
        if req.url.host == "www.nasdaqtrader.com" and req.url.path.endswith("/otherlisted.txt"):
            return httpx.Response(
                200,
                text=(
                    "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol\n"
                    "JPM|JPMorgan Chase & Co. Common Stock|N|JPM|N|100|N|JPM\n"
                    "SPY|SPDR S&P 500 ETF Trust|P|SPY|Y|100|N|SPY\n"
                    "TESTX|Test Security|A|TESTX|N|100|Y|TESTX\n"
                    "File Creation Time: 0825202620:00|||||||\n"
                ),
            )
        if req.url.host == "www.sec.gov":
            return httpx.Response(403, text="blocked")
        raise AssertionError(str(req.url))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = YahooMarketDataProvider(client=client, sec_user_agent="MarketInsightAI test@example.com")
        assets = await provider.list_assets()

    assert [x["ticker"] for x in assets] == ["AAPL", "JPM", "QQQ", "SPY"]
    assert next(x for x in assets if x["ticker"] == "QQQ")["asset_type"] == "ETF"
    assert next(x for x in assets if x["ticker"] == "SPY")["exchange"] == "NYSE ARCA"
