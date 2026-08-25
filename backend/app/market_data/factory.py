from app.settings import Settings
from app.market_data.fake_provider import FakeMarketDataProvider
from app.market_data.alpaca_provider import AlpacaMarketDataProvider
from app.market_data.yahoo_provider import YahooMarketDataProvider

def create_market_data_provider(settings:Settings|None=None):
    s=settings or Settings()
    provider=s.MARKET_PROVIDER.lower().strip()
    if provider=="alpaca":
        if not s.APCA_API_KEY_ID or not s.APCA_API_SECRET_KEY: raise ValueError("Alpaca credentials are required")
        return AlpacaMarketDataProvider(api_key=s.APCA_API_KEY_ID,api_secret=s.APCA_API_SECRET_KEY,feed=s.ALPACA_DATA_FEED,sip_entitled=s.ALPACA_SIP_ENTITLED)
    if provider=="yahoo":
        return YahooMarketDataProvider(sec_user_agent=s.SEC_USER_AGENT)
    return FakeMarketDataProvider()
