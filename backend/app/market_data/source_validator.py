from __future__ import annotations
from dataclasses import dataclass
from app.domain.models import DataQuality

@dataclass(frozen=True)
class ValidationResult:
    data_quality: DataQuality
    source_agreement: float
    completeness: float
    reasons: list[str]

def validate_sources(*,prices:list[float],freshness_seconds:list[float],history_completeness:float)->ValidationResult:
    reasons=[]; quality=DataQuality.VERIFIED
    if not prices: return ValidationResult(DataQuality.NO_RELIABLE_FORECAST,0,history_completeness,["No market prices available"])
    mean=sum(prices)/len(prices); spread=(max(prices)-min(prices))/mean if mean else 1
    agreement=max(0,100-spread*1000)
    if spread>.02: quality=DataQuality.DATA_CONFLICT; reasons.append("Independent price sources materially disagree")
    if any(x>120 for x in freshness_seconds): quality=DataQuality.STALE if quality==DataQuality.VERIFIED else quality; reasons.append("Market price is stale")
    if history_completeness<.7 and quality==DataQuality.VERIFIED: quality=DataQuality.LIMITED; reasons.append("Price history is incomplete")
    return ValidationResult(quality,agreement,history_completeness,reasons)
