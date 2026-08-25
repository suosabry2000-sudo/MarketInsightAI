from datetime import datetime,time
from zoneinfo import ZoneInfo
ET=ZoneInfo('America/New_York')
class OutcomeWorker:
    def __init__(self,store):self.store=store
    def record_if_due(self,forecast_id:int,realized_close:float,realized_at:datetime):
        rows=[x for x in self.store.pending_forecasts() if x.id==forecast_id]
        if not rows:return False
        row=rows[0]
        if row.target_session is None:return False
        close=datetime.combine(row.target_session,time(16),tzinfo=ET);stamp=realized_at if realized_at.tzinfo else realized_at.replace(tzinfo=ET)
        if stamp.astimezone(ET)<close:return False
        return self.store.record_outcome(forecast_id,realized_at=realized_at,realized_close=realized_close)
