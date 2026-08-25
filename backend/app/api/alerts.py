from enum import Enum
from pydantic import BaseModel,Field,model_validator
from fastapi import APIRouter,Depends,Request
from app.security.auth import require_principal
router=APIRouter(prefix='/alerts',tags=['alerts'])
class AlertType(str,Enum):
    PRICE_ABOVE='PRICE_ABOVE';PRICE_BELOW='PRICE_BELOW';SIGNAL_CHANGE='SIGNAL_CHANGE';CONFIDENCE_THRESHOLD='CONFIDENCE_THRESHOLD';WEEKLY_OPPORTUNITY='WEEKLY_OPPORTUNITY';BREAKING_NEWS='BREAKING_NEWS';EARNINGS_APPROACHING='EARNINGS_APPROACHING'
class AlertPreference(BaseModel):
    ticker:str|None=Field(None,max_length=10);alert_type:AlertType;enabled:bool=True;price_threshold:float|None=Field(None,gt=0);minimum_confidence:int=Field(75,ge=0,le=100);minimum_expected_move_pct:float=Field(3,ge=0)
    @model_validator(mode='after')
    def valid(self):
        if self.alert_type in {AlertType.PRICE_ABOVE,AlertType.PRICE_BELOW} and self.price_threshold is None:raise ValueError('price_threshold is required for price alerts')
        if self.ticker:self.ticker=self.ticker.upper()
        return self
class PushToken(BaseModel):token:str=Field(min_length=8,max_length=4096);platform:str='android'
class AlertContext(BaseModel):price:float|None=None;signal_changed:bool=False;confidence:float|None=None;expected_move_pct:float|None=None;breaking_news:bool=False;earnings_approaching:bool=False
def evaluate_alert(p:AlertPreference,c:AlertContext):
    if not p.enabled:return False
    if c.confidence is not None and c.confidence<p.minimum_confidence:return False
    if p.alert_type==AlertType.PRICE_ABOVE:return c.price is not None and c.price>=p.price_threshold
    if p.alert_type==AlertType.PRICE_BELOW:return c.price is not None and c.price<=p.price_threshold
    if p.alert_type==AlertType.SIGNAL_CHANGE:return c.signal_changed
    if p.alert_type==AlertType.CONFIDENCE_THRESHOLD:return c.confidence is not None and c.confidence>=p.minimum_confidence
    if p.alert_type==AlertType.WEEKLY_OPPORTUNITY:return c.expected_move_pct is not None and abs(c.expected_move_pct)>=p.minimum_expected_move_pct
    if p.alert_type==AlertType.BREAKING_NEWS:return c.breaking_news
    if p.alert_type==AlertType.EARNINGS_APPROACHING:return c.earnings_approaching
    return False
@router.get('/preferences')
def prefs(request:Request,principal:str=Depends(require_principal)):
    store=getattr(request.app.state,'sql_store',None)
    return store.list_alerts(principal) if store else list(request.app.state.alert_preferences.get(principal,{}).values())
@router.post('/preferences')
def save(p:AlertPreference,request:Request,principal:str=Depends(require_principal)):
    store=getattr(request.app.state,'sql_store',None)
    if store:return store.save_alert(principal,p)
    request.app.state.alert_preferences.setdefault(principal,{})[(p.ticker,p.alert_type.value)]=p;return p
@router.post('/push-token')
def token(p:PushToken,request:Request,principal:str=Depends(require_principal)):
    store=getattr(request.app.state,'sql_store',None)
    if store:store.register_push(principal,p)
    else:request.app.state.push_tokens.setdefault(principal,set()).add(p.token)
    return {'status':'registered'}
