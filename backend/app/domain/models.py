from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from pydantic import BaseModel, Field


class DataQuality(str, Enum):
    VERIFIED = "VERIFIED"
    LIMITED = "LIMITED"
    STALE = "STALE"
    DATA_CONFLICT = "DATA_CONFLICT"
    NO_RELIABLE_FORECAST = "NO RELIABLE FORECAST"


class Quote(BaseModel):
    ticker: str
    price: float = Field(gt=0)
    currency: str = "USD"
    provider: str
    provider_timestamp: datetime
    normalized_timestamp: datetime
    market_session: str
    freshness_seconds: float = Field(ge=0)
    data_quality: DataQuality
    feed_scope: str
    feed_label: str | None = None
    consolidated: bool = False


class PriceBar(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = Field(ge=0)


class ChartSeries(BaseModel):
    ticker: str
    range: str
    bars: list[PriceBar]


class DailyForecastRow(BaseModel):
    date: date
    low: float
    high: float
    base: float
    bull_probability: float
    confidence: float


class Forecast(BaseModel):
    ticker: str
    model_version: str
    as_of: datetime
    expected_low: float
    expected_high: float
    bear_target: float
    base_target: float
    bull_target: float
    bull_probability: float = Field(ge=0, le=1)
    bear_probability: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=100)
    risk: str
    data_quality: DataQuality
    explanation: str
    tomorrow_open: float | None = None
    tomorrow_low: float | None = None
    tomorrow_high: float | None = None
    tomorrow_close: float | None = None
    daily_rows: list[DailyForecastRow] = []


class WeeklyScannerRow(BaseModel):
    ticker: str
    monday_reference: float
    live_price: float
    friday_bear: float
    friday_base: float
    friday_bull: float
    expected_move_pct: float
    expected_move_from_live_pct: float
    bull_probability: float
    bear_probability: float
    confidence: float
    opportunity_score: float
    signal: str
    risk: str
    data_quality: DataQuality
    reference_quality: DataQuality = DataQuality.VERIFIED
    exchange: str | None = None
    sector: str | None = None
    index_memberships: list[str] = []
    themes: list[str] = []
    market_cap_bucket: str | None = None
    most_active: bool = False
    volatility: float = 0.0


class WeeklyScannerResponse(BaseModel):
    market_status: str
    generated_at: datetime
    reference_session: date
    target_session: date
    stocks: list[WeeklyScannerRow]
