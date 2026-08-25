from datetime import datetime,timezone
import httpx,pytest
from app.notifications.fcm import FcmSender,FcmMessage
from app.api.alerts import AlertPreference,AlertType,AlertContext,evaluate_alert

@pytest.mark.asyncio
async def test_fcm_http_v1_payload_has_navigation_and_no_credentials():
    captured={}
    def handler(req:httpx.Request):captured['auth']=req.headers['authorization'];captured['json']=__import__('json').loads(req.content);return httpx.Response(200,json={'name':'projects/x/messages/1'})
    async def token():return 'oauth-token'
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        s=FcmSender('project-x',token,client=c);r=await s.send(FcmMessage('device-token','AAPL','WEEKLY_OPPORTUNITY',datetime.now(timezone.utc),'stock/AAPL','AAPL opportunity','Confidence 80%'))
    assert r['name'];assert captured['auth']=='Bearer oauth-token';data=captured['json']['message']['data'];assert data['ticker']=='AAPL' and data['navigation_target']=='stock/AAPL'
    assert 'oauth-token' not in str(captured['json'])

def test_alert_evaluation_covers_price_confidence_opportunity_and_events():
    assert evaluate_alert(AlertPreference(ticker='AAPL',alert_type=AlertType.PRICE_ABOVE,price_threshold=320,minimum_confidence=0),AlertContext(price=321,confidence=80))
    assert evaluate_alert(AlertPreference(alert_type=AlertType.CONFIDENCE_THRESHOLD,minimum_confidence=75),AlertContext(confidence=76))
    assert evaluate_alert(AlertPreference(alert_type=AlertType.WEEKLY_OPPORTUNITY,minimum_expected_move_pct=3,minimum_confidence=0),AlertContext(expected_move_pct=-4,confidence=80))
    assert evaluate_alert(AlertPreference(alert_type=AlertType.BREAKING_NEWS,minimum_confidence=0),AlertContext(breaking_news=True))
    assert evaluate_alert(AlertPreference(alert_type=AlertType.EARNINGS_APPROACHING,minimum_confidence=0),AlertContext(earnings_approaching=True))
