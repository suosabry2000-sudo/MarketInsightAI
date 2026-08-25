from __future__ import annotations
from datetime import datetime,timedelta,timezone
from statistics import mean,median
from sqlalchemy import create_engine,delete,select
from sqlalchemy.orm import Session,sessionmaker
from app.database.models import Base,WatchlistModel,AlertModel,PushTokenModel,ForecastModel

def normalize_url(url:str):return url.replace('postgresql+psycopg2://','postgresql+psycopg://').replace('postgres://','postgresql+psycopg://').replace('postgresql://','postgresql+psycopg://')
class SqlStore:
    def __init__(self,url:str):self.engine=create_engine(normalize_url(url),pool_pre_ping=True);Base.metadata.create_all(self.engine);self.sessions=sessionmaker(bind=self.engine,expire_on_commit=False)
    def add_watchlist(self,principal,ticker):
        t=ticker.upper();
        with self.sessions() as s:
            if not s.scalar(select(WatchlistModel).where(WatchlistModel.principal==principal,WatchlistModel.ticker==t)):s.add(WatchlistModel(principal=principal,ticker=t));s.commit()
    def remove_watchlist(self,principal,ticker):
        with self.sessions() as s:s.execute(delete(WatchlistModel).where(WatchlistModel.principal==principal,WatchlistModel.ticker==ticker.upper()));s.commit()
    def list_watchlist(self,principal):
        with self.sessions() as s:return list(s.scalars(select(WatchlistModel.ticker).where(WatchlistModel.principal==principal).order_by(WatchlistModel.ticker)).all())
    def save_alert(self,principal,p):
        key=p.ticker.upper() if p.ticker else ''
        with self.sessions() as s:
            row=s.scalar(select(AlertModel).where(AlertModel.principal==principal,AlertModel.ticker_key==key,AlertModel.alert_type==p.alert_type.value))
            if not row:row=AlertModel(principal=principal,ticker_key=key,ticker=p.ticker.upper() if p.ticker else None,alert_type=p.alert_type.value);s.add(row)
            row.enabled=p.enabled;row.price_threshold=p.price_threshold;row.minimum_confidence=p.minimum_confidence;row.minimum_expected_move_pct=p.minimum_expected_move_pct;s.commit()
        return p
    def list_alerts(self,principal):
        from app.api.alerts import AlertPreference
        with self.sessions() as s:
            rows=s.scalars(select(AlertModel).where(AlertModel.principal==principal).order_by(AlertModel.id)).all();return [AlertPreference(ticker=r.ticker,alert_type=r.alert_type,enabled=r.enabled,price_threshold=r.price_threshold,minimum_confidence=r.minimum_confidence,minimum_expected_move_pct=r.minimum_expected_move_pct) for r in rows]
    def all_alerts(self):
        with self.sessions() as s:return [(r.principal,r) for r in s.scalars(select(AlertModel).where(AlertModel.enabled==True)).all()]
    def register_push(self,principal,p):
        with self.sessions() as s:
            if not s.scalar(select(PushTokenModel).where(PushTokenModel.principal==principal,PushTokenModel.token==p.token)):s.add(PushTokenModel(principal=principal,token=p.token,platform=p.platform));s.commit()
    def list_push_tokens(self,principal):
        with self.sessions() as s:return list(s.scalars(select(PushTokenModel.token).where(PushTokenModel.principal==principal)).all())
    def save_forecast(self,**k):
        with self.sessions() as s:r=ForecastModel(**k);s.add(r);s.commit();return r.id
    def pending_forecasts(self):
        with self.sessions() as s:return list(s.scalars(select(ForecastModel).where(ForecastModel.realized_close.is_(None),ForecastModel.target_session.is_not(None))).all())
    def record_outcome(self,fid:int,*,realized_at:datetime,realized_close:float):
        with self.sessions() as s:
            r=s.get(ForecastModel,fid)
            if not r:raise KeyError(fid)
            if r.realized_close is not None:return False
            ref=r.reference_price
            r.realized_at=realized_at;r.realized_close=realized_close;r.base_error_pct=abs(realized_close-r.base)/r.base*100;r.range_captured=r.bear<=realized_close<=r.bull
            r.direction_correct=None if ref is None else ((r.base>=ref)==(realized_close>=ref));s.commit();return True
    def accuracy(self,ticker:str,now:datetime|None=None):
        now=now or datetime.now(timezone.utc)
        with self.sessions() as s:rows=list(s.scalars(select(ForecastModel).where(ForecastModel.ticker==ticker.upper(),ForecastModel.realized_close.is_not(None)).order_by(ForecastModel.created_at.desc())).all())
        def aware(x):return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
        def acc(days):
            r=[x for x in rows if aware(x.realized_at)>=now-timedelta(days=days) and x.direction_correct is not None];return round(sum(bool(x.direction_correct) for x in r)/len(r)*100,2) if r else 0
        errors=[x.base_error_pct for x in rows if x.base_error_pct is not None];capt=[x.range_captured for x in rows if x.range_captured is not None];hi=[x for x in rows if x.confidence>=75 and x.direction_correct is not None]
        return {'ticker':ticker.upper(),'generated_at':now,'direction_accuracy_7d':acc(7),'direction_accuracy_30d':acc(30),'direction_accuracy_90d':acc(90),'average_target_error_pct':round(mean(errors),4) if errors else 0,'median_target_error_pct':round(median(errors),4) if errors else 0,'range_capture_pct':round(sum(bool(x) for x in capt)/len(capt)*100,2) if capt else 0,'high_confidence_accuracy_pct':round(sum(bool(x.direction_correct) for x in hi)/len(hi)*100,2) if hi else 0,'sample_count':len(rows),'history':[{'forecast_at':x.created_at,'target_session':x.target_session,'predicted_base':x.base,'actual_close':x.realized_close,'direction_correct':x.direction_correct,'base_error_pct':x.base_error_pct} for x in rows[:50]],'note':'Historical performance; not a guarantee of future results.'}
    def close(self):self.engine.dispose()
