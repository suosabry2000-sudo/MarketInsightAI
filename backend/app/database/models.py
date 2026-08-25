from __future__ import annotations
from datetime import date,datetime
from sqlalchemy import Boolean,Date,DateTime,Float,Integer,String,UniqueConstraint
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column
class Base(DeclarativeBase):pass
class WatchlistModel(Base):
    __tablename__='watchlist';__table_args__=(UniqueConstraint('principal','ticker'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True);principal:Mapped[str]=mapped_column(String(160),index=True);ticker:Mapped[str]=mapped_column(String(10))
class AlertModel(Base):
    __tablename__='alerts';__table_args__=(UniqueConstraint('principal','ticker_key','alert_type'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True);principal:Mapped[str]=mapped_column(String(160),index=True);ticker_key:Mapped[str]=mapped_column(String(10),default='');ticker:Mapped[str|None]=mapped_column(String(10),nullable=True);alert_type:Mapped[str]=mapped_column(String(40));enabled:Mapped[bool]=mapped_column(Boolean,default=True);price_threshold:Mapped[float|None]=mapped_column(Float,nullable=True);minimum_confidence:Mapped[int]=mapped_column(Integer,default=75);minimum_expected_move_pct:Mapped[float]=mapped_column(Float,default=3)
class PushTokenModel(Base):
    __tablename__='push_tokens';__table_args__=(UniqueConstraint('principal','token'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True);principal:Mapped[str]=mapped_column(String(160),index=True);token:Mapped[str]=mapped_column(String(4096));platform:Mapped[str]=mapped_column(String(20),default='android')
class ForecastModel(Base):
    __tablename__='forecasts'
    id:Mapped[int]=mapped_column(Integer,primary_key=True);ticker:Mapped[str]=mapped_column(String(10),index=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True);as_of:Mapped[datetime]=mapped_column(DateTime(timezone=True));model_version:Mapped[str]=mapped_column(String(64));bear:Mapped[float]=mapped_column(Float);base:Mapped[float]=mapped_column(Float);bull:Mapped[float]=mapped_column(Float);bull_probability:Mapped[float]=mapped_column(Float);bear_probability:Mapped[float]=mapped_column(Float);confidence:Mapped[float]=mapped_column(Float);validation:Mapped[str]=mapped_column(String(32));target_session:Mapped[date|None]=mapped_column(Date,nullable=True);reference_price:Mapped[float|None]=mapped_column(Float,nullable=True);realized_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);realized_close:Mapped[float|None]=mapped_column(Float,nullable=True);base_error_pct:Mapped[float|None]=mapped_column(Float,nullable=True);direction_correct:Mapped[bool|None]=mapped_column(Boolean,nullable=True);range_captured:Mapped[bool|None]=mapped_column(Boolean,nullable=True)
