from datetime import datetime,timezone
from fastapi import APIRouter,Request
router=APIRouter(prefix='/accuracy',tags=['accuracy'])
@router.get('/{ticker}')
def accuracy(ticker:str,request:Request):
    store=getattr(request.app.state,'sql_store',None)
    if store:return store.accuracy(ticker)
    return {'ticker':ticker.upper(),'generated_at':datetime.now(timezone.utc),'direction_accuracy_7d':0.0,'direction_accuracy_30d':0.0,'direction_accuracy_90d':0.0,'average_target_error_pct':0.0,'median_target_error_pct':0.0,'range_capture_pct':0.0,'high_confidence_accuracy_pct':0.0,'sample_count':0,'history':[],'note':'Accuracy appears after realized forecast outcomes are recorded.'}
