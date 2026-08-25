from datetime import date,datetime,timezone
from pathlib import Path
from app.database.store import SqlStore
from app.api.alerts import AlertPreference,AlertType,PushToken


def test_watchlist_alerts_and_push_tokens_persist(tmp_path):
    url=f"sqlite:///{tmp_path/'db.sqlite'}"; s=SqlStore(url)
    s.add_watchlist('device:1','aapl')
    s.save_alert('device:1',AlertPreference(ticker='AAPL',alert_type=AlertType.PRICE_ABOVE,price_threshold=320))
    s.register_push('device:1',PushToken(token='12345678'))
    s.close(); s=SqlStore(url)
    assert s.list_watchlist('device:1')==['AAPL']
    assert s.list_alerts('device:1')[0].price_threshold==320
    assert s.list_push_tokens('device:1')==['12345678']
    s.close()

def test_forecast_outcome_is_scored_once_and_accuracy_is_computed(tmp_path):
    s=SqlStore(f"sqlite:///{tmp_path/'db.sqlite'}")
    fid=s.save_forecast(ticker='AAPL',created_at=datetime(2026,8,24,14,tzinfo=timezone.utc),as_of=datetime(2026,8,24,14,tzinfo=timezone.utc),model_version='hybrid-v1.0',bear=304,base=315,bull=322,bull_probability=.67,bear_probability=.33,confidence=80,validation='VERIFIED',target_session=date(2026,8,28),reference_price=310)
    assert s.record_outcome(fid,realized_at=datetime(2026,8,28,20,1,tzinfo=timezone.utc),realized_close=316)
    assert not s.record_outcome(fid,realized_at=datetime(2026,8,28,20,2,tzinfo=timezone.utc),realized_close=318)
    report=s.accuracy('AAPL',now=datetime(2026,8,29,tzinfo=timezone.utc))
    assert report['sample_count']==1
    assert report['direction_accuracy_30d']==100
    assert report['range_capture_pct']==100
    assert 0 < report['average_target_error_pct'] < 1
    s.close()


def test_normalize_url_forces_psycopg3_for_railway_postgresql_url():
    from app.database.store import normalize_url
    assert normalize_url('postgresql://user:pass@db:5432/app') == 'postgresql+psycopg://user:pass@db:5432/app'
