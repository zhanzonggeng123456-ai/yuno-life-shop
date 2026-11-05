"""Mobile JSON contracts and real workflow integration; no paid/external APIs."""
import secrets
import os
import tempfile

if "YUNO_DB_PATH" not in os.environ:
    _tmp=tempfile.mkdtemp(prefix="yuno_mobile_test_")
    os.environ["YUNO_DB_PATH"]=os.path.join(_tmp,"test.db")
    os.environ["YUNO_UPLOAD_DIR"]=os.path.join(_tmp,"uploads")
import time
from datetime import datetime,timedelta,timezone

import pytest
from fastapi.testclient import TestClient
from app import db as d
from app.main import app
from app.security import reset_rate_limits

@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    # Always isolate even when a developer exports a production DB path.
    monkeypatch.setattr(d, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(d, "UPLOAD_DIR", tmp_path / "uploads")
    d.init_db();reset_rate_limits()
    yield

class Mobile:
    def __init__(self,email,role='user'):
        self.client=TestClient(app)
        self.email=email;self.password=secrets.token_urlsafe(15)
        response=self.client.post('/api/v1/register',json={'email':email,'password':self.password,'display_name':'Mobile tester'})
        assert response.status_code==200,response.text
        self.token=response.json()['access_token']
        self.headers={'Authorization':'Bearer '+self.token}
        self.id=self.get('/me')['id']
        if role!='user':
            with d.connect() as c:c.execute('UPDATE users SET role=? WHERE id=?',(role,self.id))
    def get(self,path):
        response=self.client.get('/api/v1'+path,headers=self.headers)
        assert response.status_code==200,response.text
        assert response.headers['content-type'].startswith('application/json')
        return response.json()
    def post(self,path,data=None,expected=200,files=None):
        kwargs={'data':data or {},'files':files} if files else {'json':data or {}}
        response=self.client.post('/api/v1'+path,headers=self.headers,**kwargs)
        assert response.status_code==expected,response.text
        assert response.headers['content-type'].startswith('application/json')
        return response.json()
    def listing(self,price=6000):
        response=self.post('/listings/new',{'category_slug':'appliance','title_ja':'中古電子レンジ','title_zh':'二手微波炉','price':price,'region':'sakado'})
        return int(response['next'].split('/')[-1])


def test_config_services_and_public_reads():
    client=TestClient(app)
    config=client.get('/api/v1/config').json()
    assert config['max_photos']==10
    assert config['delivery_rules']['base']=={'S':150,'M':200,'L':250}
    assert {k:v['price'] for k,v in config['services'].items()}=={'cleaning_home':1500,'transport_small':500,'local_delivery':150}
    assert len(config['categories'])==13
    assert client.get('/api/v1/rules').status_code==200
    assert client.get('/api/v1/market').json()['moves']['up_count']==0


def test_auth_token_expiry_logout_and_no_secret_fields():
    u=Mobile('u@test.jp')
    me=u.get('/me');assert 'pw_hash' not in me and 'password' not in me and 'token' not in me
    cookie=TestClient(app);cookie.cookies.set('yuno_session',u.token)
    assert cookie.get('/api/v1/me').status_code==401
    u.post('/logout')
    assert u.client.get('/api/v1/me',headers=u.headers).status_code==401
    response=u.client.post('/api/v1/login',json={'email':u.email,'password':u.password})
    assert response.status_code==200
    token=response.json()['access_token']
    with d.connect() as c:c.execute("UPDATE sessions SET expires_at='2000-01-01' WHERE token=?",(token,))
    assert u.client.get('/api/v1/me',headers={'Authorization':'Bearer '+token}).status_code==401


def test_fixed_trade_review_refund_and_permissions():
    s=Mobile('s@test.jp');b=Mobile('b@test.jp');o=Mobile('o@test.jp');a=Mobile('a@test.jp','admin')
    lid=s.listing()
    data=b.get(f'/listings/{lid}')
    assert data['actions'] and data['category']['slug']=='appliance'
    b.post(f'/listings/{lid}/follow')
    assert b.get('/me')['following'][0]['id']==lid
    assert o.get('/me')['following']==[]
    oid=int(b.post(f'/listings/{lid}/buy')['next'].split('/')[-1])
    assert b.get('/orders')['items'][0]['listing']['id']==lid
    assert o.get('/orders')['items']==[]
    assert o.client.get(f'/api/v1/orders/{oid}',headers=o.headers).status_code==403
    b.post(f'/orders/{oid}/pay',{'idempotency_key':'api-test'})
    b.post(f'/orders/{oid}/pay',{'idempotency_key':'api-test'})
    b.post(f'/orders/{oid}/complete')
    assert b.get(f'/orders/{oid}')['status']=='completed'
    b.post(f'/orders/{oid}/review',{'rating':5,'comment':'ok'})
    assert b.get(f'/users/{s.id}')['reviews'][0]['rating']==5
    b.post(f'/orders/{oid}/refund',{'reason':'test','evidence':'test'})
    rid=b.get(f'/orders/{oid}')['refunds'][0]['id']
    a.post(f'/refunds/{rid}/decide',{'decision':'approved','decision_note':'test'})
    assert b.get(f'/orders/{oid}')['status']=='refunded'
    with d.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM payment_intents').fetchone()[0]==1


def test_offer_messages_and_spoofing_rejection():
    s=Mobile('s@test.jp');b=Mobile('b@test.jp');o=Mobile('o@test.jp')
    lid=s.listing()
    b.post(f'/listings/{lid}/offer',{'amount':5000})
    oid=b.get('/me')['offers'][0]['id']
    s.post(f'/offers/{oid}/counter',{'counter_amount':5500})
    b.post(f'/offers/{oid}/accept-counter')
    assert b.get('/orders')['items'][0]['goods_amount']==5500
    b.post(f'/messages/{lid}/{b.id}',{'body':'hello','receiver_id':s.id})
    assert s.get(f'/messages/{lid}/{b.id}')['items'][0]['body']=='hello'
    assert o.client.get(f'/api/v1/messages/{lid}/{b.id}',headers=o.headers).status_code==403


def test_multiphoto_job_appraisal_model_publish_and_cover():
    s=Mobile('s@test.jp');o=Mobile('o@test.jp')
    files=[('photos',(f'{i}.jpg',b'image-test','image/jpeg')) for i in range(10)]
    response=s.post('/oneclick/upload',{'name':'Panasonic 電子レンジ','condition':'good'},files=files)
    did=int(response['next'].split('/')[-1])
    assert len(s.get(f'/oneclick/{did}')['photos'])==10
    s.post(f'/oneclick/{did}/photos/add',{},expected=400,files=[('photos',('extra.jpg',b'x','image/jpeg'))])
    assert o.client.get(f'/api/v1/oneclick/{did}',headers=o.headers).status_code==403
    s.post(f'/oneclick/{did}/photos/reorder',{'order':list(reversed(range(10)))})
    s.post(f'/oneclick/{did}/photos/0/replace',{},files=[('photo',('new.jpg',b'new','image/jpeg'))])
    task=s.post('/ai-jobs',{'kind':'oneclick_recognize','draft_id':did})
    for _ in range(100):
        job=s.get('/ai-jobs/'+str(task['job_id']))
        if job['status'] in ('done','failed'):break
        time.sleep(.01)
    assert job['status']=='done',job
    draft=s.get(f'/oneclick/{did}')
    assert draft['recognition']['photo_count']==10
    assert 'authenticity' not in draft['appraisal']
    assert draft['valuation']['low'] is None
    s.post(f'/oneclick/{did}/model',{'brand':'Panasonic','model':'NE-FL1A'})
    result=s.post(f'/oneclick/{did}/publish',{'category_slug':'appliance','title_ja':'中古電子レンジ','price':5000})
    lid=int(result['next'].split('/')[-1])
    item=s.get(f'/listings/{lid}')
    assert len(item['photos'])==10
    s.post(f'/listings/{lid}/photos/{item["photos"][-1]["id"]}/cover')
    assert s.get(f'/listings/{lid}')['photos'][0]['id']==item['photos'][-1]['id']


def test_auction_buyback_services_delivery_admin():
    s=Mobile('s@test.jp');b=Mobile('b@test.jp');a=Mobile('a@test.jp','admin')
    courier=Mobile('courier@test.jp','courier');appraiser=Mobile('appraiser@test.jp','appraiser')
    lid=s.listing()
    end=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
    aid=int(s.post(f'/listings/{lid}/auction',{'start_price':1000,'buy_now_price':6000,'ends_at':end})['next'].split('/')[-1])
    b.post(f'/auctions/{aid}/bid',{'amount':1000,'proxy_max':2000})
    assert b.get(f'/auctions/{aid}')['bids']
    oid=int(b.post(f'/auctions/{aid}/buy-now')['next'].split('/')[-1])
    b.post(f'/orders/{oid}/pay',{'idempotency_key':'auction-test'})
    did=int(b.post(f'/orders/{oid}/delivery-request',{'kind':'buyer_delivery'})['next'].split('/')[-1])
    assert any(r['id']==did for r in courier.get('/me')['deliveries'])
    assert courier.get(f'/deliveries/{did}')['actions'][0]['path'].endswith('/assign')
    courier.post(f'/deliveries/{did}/assign');courier.post(f'/deliveries/{did}/pickup');courier.post(f'/deliveries/{did}/deliver');b.post(f'/deliveries/{did}/confirm')
    assert b.get(f'/deliveries/{did}')['status']=='confirmed'
    lid=s.listing();bid=int(s.post('/buyback/new',{'listing_id':lid})['next'].split('/')[-1])
    a.post(f'/buyback/{bid}/review');a.post(f'/buyback/{bid}/quote',{'quote':1000});s.post(f'/buyback/{bid}/accept');s.post(f'/buyback/{bid}/pickup',{'pickup_at':end})
    assert any(r['id']==bid for r in appraiser.get('/me')['buybacks'])
    assert appraiser.get(f'/buyback/{bid}')['actions'][0]['path'].endswith('/inspect')
    appraiser.post(f'/buyback/{bid}/inspect',{'inspection_note':'test'});a.post(f'/buyback/{bid}/pay',{'resale_price':3500})
    assert a.get('/admin/inventory')['items']
    sid=int(b.post('/services/new',{'kind':'cleaning_home','hours':2})['next'].split('/')[-1])
    a.post(f'/services/{sid}/confirm');a.post(f'/services/{sid}/start');a.post(f'/services/{sid}/complete')
    assert b.get(f'/services/{sid}')['amount']==3000
    assert b.client.get('/api/v1/admin/users',headers=b.headers).status_code==403
    for section in ['users','listings','buybacks','orders','inventory','auctions','deliveries','services','refunds','disputes','high-value','profit','alerts','suggestions','expenses','audit','settings']:
        assert a.get('/admin/'+section) is not None


def test_invalid_json_and_business_rejection_are_json():
    u=Mobile('u@test.jp')
    lid=u.listing()
    u.post(f'/listings/{lid}/buy',expected=409)
    assert u.client.post('/api/v1/login',json={'email':u.email,'password':'wrong'}).status_code==401
    assert u.client.get('/api/v1/listings/999999',headers=u.headers).headers['content-type'].startswith('application/json')


def test_public_market_overview_excludes_demo_unpaid_and_keeps_periods_separate():
    s=Mobile('overview-s@test.jp');b=Mobile('overview-b@test.jp')
    lid=s.listing(6000)
    now=datetime.now(timezone.utc)
    records=[(6000,'paid',0,now),(4000,'completed',0,now),
             (2000,'paid',0,now-timedelta(days=40)),
             (3000,'completed',0,now-timedelta(days=40)),
             (90000,'paid',1,now),(999,'pending_payment',0,now)]
    with d.connect() as c:
        for amount,state,demo,created in records:
            c.execute('INSERT INTO orders(buyer_id,seller_id,listing_id,goods_amount,total,status,demo,created_at) VALUES(?,?,?,?,?,?,?,?)',
                      (b.id,s.id,lid,amount,amount,state,demo,created.isoformat()))
    response=TestClient(app).get('/api/v1/market')
    assert response.status_code==200
    summary=response.json()['overview']
    assert summary['gmv']==15000 and summary['paid_orders']==4 and summary['orders']==5
    assert summary['recent_30_volume']==10000 and summary['previous_30_volume']==5000
    assert summary['change_pct']==100.0
    assert summary['active_count']==1 and summary['active_asking_total']==6000
    assert len(summary['volume_curve'])==12
    assert sum(w['volume'] for w in summary['volume_curve'])==15000
    assert summary['volume_curve'][-1]['volume']==10000
    assert 'buyer_id' not in response.text and 'seller_id' not in response.text


def test_empty_market_overview_has_no_fabricated_change_or_curve():
    summary=TestClient(app).get('/api/v1/market').json()['overview']
    assert summary['gmv']==0 and summary['change_pct'] is None
    assert summary['orders']==0 and summary['active_count']==0
    assert all(w['volume']==0 for w in summary['volume_curve'])
