from datetime import datetime, timezone
import pytest
from app.domain.models import DataQuality
from app.prediction.hybrid import HybridInputs, weighted_score, build_forecast, compute_confidence, opportunity_score


def inputs(**overrides):
    base=dict(ticker="AAPL",as_of=datetime(2026,8,24,18,tzinfo=timezone.utc),price=310.8,
              technical=80,momentum=70,fundamental=60,sentiment=50,macro=40,
              realized_volatility=.25,atr_pct=.02,positive=["trend strong"],negative=["resistance nearby"])
    base.update(overrides); return HybridInputs(**base)

def test_hybrid_weights_are_exact_35_20_15_15_15():
    assert weighted_score(inputs()) == pytest.approx(64.5)

def test_forecast_targets_are_ordered_and_probabilities_sum_to_one():
    f=build_forecast(inputs())
    assert f.bear_target < f.base_target < f.bull_target
    assert f.expected_low < f.expected_high
    assert f.bull_probability + f.bear_probability == pytest.approx(1.0)
    assert len(f.daily_rows)==5

def test_data_conflict_suspends_forecast_and_confidence_is_separate_from_direction():
    confidence=compute_confidence(model_agreement=.9,data_quality=DataQuality.DATA_CONFLICT,historical_accuracy=.8,source_agreement=.3,market_stability=.8,news_certainty=.7,event_risk=0,completeness=.9)
    assert confidence < 50
    f=build_forecast(inputs(),data_quality=DataQuality.DATA_CONFLICT,confidence=confidence)
    assert f.data_quality == DataQuality.NO_RELIABLE_FORECAST
    assert f.confidence == confidence

def test_opportunity_score_penalizes_risk_and_low_data_quality():
    good=opportunity_score(5,80,95,25)
    poor=opportunity_score(5,80,50,80)
    assert 0<=poor<good<=100
