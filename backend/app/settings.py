from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "development"
    MARKET_PROVIDER: str = "fake"
    MODEL_VERSION: str = "hybrid-v1.0"
    APCA_API_KEY_ID: str | None = None
    APCA_API_SECRET_KEY: str | None = None
    ALPACA_DATA_FEED: str = "iex"
    ALPACA_SIP_ENTITLED: bool = False
    SEC_USER_AGENT: str | None = None
    FRED_API_KEY: str | None = None
    REDIS_URL: str | None = None
    DATABASE_URL: str | None = None
    TOKEN_SECRET: str | None = None
    TOKEN_TTL_SECONDS: int = 900
    RATE_LIMIT_REQUESTS: int = 120
    SCANNER_REFRESH_SECONDS: int = 300

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=True)

    def validate_production(self) -> "Settings":
        if self.APP_ENV.strip().lower() != "production":
            return self
        missing: list[str] = []
        for name in ("DATABASE_URL", "REDIS_URL", "TOKEN_SECRET"):
            if not getattr(self, name):
                missing.append(name)
        provider = self.MARKET_PROVIDER.strip().lower()
        if provider not in {"alpaca", "yahoo"}:
            missing.append("MARKET_PROVIDER=alpaca|yahoo")
        elif provider == "alpaca":
            for name in ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY"):
                if not getattr(self, name):
                    missing.append(name)
        if missing:
            raise ValueError("production configuration missing: " + ", ".join(missing))
        return self
