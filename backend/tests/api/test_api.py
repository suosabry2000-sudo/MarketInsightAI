from fastapi.testclient import TestClient
from app.main import create_app
from app.market_data.fake_provider import FakeMarketDataProvider


def client(auth=False):
    return TestClient(create_app(provider=FakeMarketDataProvider(),auth_required=auth,token_secret="x"*32))

def test_health_quote_chart_forecast_and_reports():
    with client() as c:
        assert c.get('/health').json()=={'status':'ok'}
        q=c.get('/quotes/AAPL'); assert q.status_code==200 and q.json()['ticker']=='AAPL'
        chart=c.get('/charts/AAPL?range=1M'); assert chart.status_code==200 and len(chart.json()['bars'])>0
        fc=c.get('/forecasts/AAPL'); assert fc.status_code==200
        body=fc.json(); assert body['bear_target']<body['base_target']<body['bull_target']; assert len(body['daily_rows'])==5
        for path in ('technical','fundamentals','news','verification'):
            r=c.get(f'/{path}/AAPL'); assert r.status_code==200, (path,r.text)

def test_stock_search_and_market_overview():
    with client() as c:
        r=c.get('/stocks/search?q=Apple'); assert r.status_code==200 and r.json()['results'][0]['ticker']=='AAPL'
        m=c.get('/markets/overview'); assert m.status_code==200 and {'indexes','top_gainers','top_losers','most_active'} <= set(m.json())

def test_weekly_scanner_exposes_monday_live_and_friday_cases():
    with client() as c:
        r=c.get('/scanner/weekly?tickers=AAPL,NVDA&sort=opportunity'); assert r.status_code==200
        body=r.json(); assert len(body['stocks'])==2
        row=body['stocks'][0]
        for key in ('monday_reference','live_price','friday_bear','friday_base','friday_bull','confidence','opportunity_score'):
            assert key in row

def test_device_auth_protects_watchlist_and_alerts():
    with client(auth=True) as c:
        assert c.get('/watchlist').status_code==401
        session=c.post('/auth/device',json={'installation_id':'test-installation-123'}); assert session.status_code==200
        token=session.json()['access_token']; headers={'Authorization':f'Bearer {token}'}
        assert c.post('/watchlist',json={'ticker':'AAPL'},headers=headers).status_code==200
        assert c.get('/watchlist',headers=headers).json()['tickers']==['AAPL']
        pref={'ticker':'AAPL','alert_type':'PRICE_ABOVE','enabled':True,'price_threshold':320,'minimum_confidence':75,'minimum_expected_move_pct':3}
        assert c.post('/alerts/preferences',json=pref,headers=headers).status_code==200
        assert len(c.get('/alerts/preferences',headers=headers).json())==1

def test_price_alert_without_threshold_is_rejected():
    with client() as c:
        r=c.post('/alerts/preferences',json={'ticker':'AAPL','alert_type':'PRICE_ABOVE'})
        assert r.status_code==422


def test_api_uses_sql_store_for_user_data_forecasts_and_accuracy(tmp_path):
    from app.database.store import SqlStore
    app=create_app(provider=FakeMarketDataProvider()); store=SqlStore(f"sqlite:///{tmp_path/'app.db'}"); app.state.sql_store=store
    try:
        with TestClient(app) as c:
            assert c.post('/watchlist',json={'ticker':'NVDA'}).status_code==200
            assert c.get('/watchlist').json()['tickers']==['NVDA']
            pref={'ticker':'AAPL','alert_type':'PRICE_ABOVE','price_threshold':320}
            assert c.post('/alerts/preferences',json=pref).status_code==200
            assert c.get('/alerts/preferences').json()[0]['price_threshold']==320
            before=store.accuracy('AAPL')['sample_count']
            assert c.get('/forecasts/AAPL').status_code==200
            assert len(store.pending_forecasts())==before+1
    finally:store.close()


def test_stock_catalog_pages_through_large_provider_universe():
    class LargeCatalogProvider(FakeMarketDataProvider):
        async def list_assets(self):
            return [
                {"ticker": f"T{i:04d}", "company": f"Test Company {i}", "exchange": "NASDAQ", "sector": None}
                for i in range(350)
            ]

    with TestClient(create_app(provider=LargeCatalogProvider())) as c:
        r = c.get('/stocks/catalog?offset=100&limit=200')
        assert r.status_code == 200
        body = r.json()
        assert body['total'] == 350
        assert len(body['results']) == 200
        assert body['results'][0]['ticker'] == 'T0100'
        assert body['results'][-1]['ticker'] == 'T0299'
        assert body['has_more'] is True
