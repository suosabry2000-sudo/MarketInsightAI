from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
import exchange_calendars as xcals
import pandas as pd
from app.domain.models import DataQuality

ET = ZoneInfo("America/New_York")

@dataclass(frozen=True)
class WeekSessions:
    reference_session: date
    target_session: date

@dataclass(frozen=True)
class ReferenceResult:
    price: float
    data_quality: DataQuality


def get_week_sessions(day: date) -> WeekSessions:
    cal = xcals.get_calendar("XNYS")
    monday = day - timedelta(days=day.weekday())
    friday = monday + timedelta(days=4)
    sessions = cal.sessions_in_range(pd.Timestamp(monday), pd.Timestamp(friday))
    if not len(sessions):
        raise ValueError("week has no U.S. trading sessions")
    return WeekSessions(sessions[0].date(), sessions[-1].date())


def establish_reference_with_quality(frame: pd.DataFrame) -> ReferenceResult:
    if frame.empty:
        raise ValueError("reference frame is empty")
    work = frame.copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], utc=True).dt.tz_convert(ET)
    clock = work["timestamp"].dt.time
    window = work[(clock >= time(9, 35)) & (clock <= time(9, 45))]
    if window.empty:
        raise ValueError("09:35-09:45 reference window is unavailable")
    volume = window["volume"].astype(float).clip(lower=0)
    if float(volume.sum()) > 0:
        price = float((window["close"].astype(float) * volume).sum() / volume.sum())
    else:
        price = float(window["close"].astype(float).mean())
    return ReferenceResult(price, DataQuality.VERIFIED)
