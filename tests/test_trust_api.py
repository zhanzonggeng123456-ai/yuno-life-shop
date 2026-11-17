"""Security and lost-response integration tests, isolated from deployed data."""
import json
from contextlib import closing
from test_mobile_api import Mobile, fresh
from app import db as d


def test_recovery_rotates_consumes_and_revokes_all_sessions():
    u = Mobile('recover@example.jp')
    second = u.post('/login', {'email':u.email,'password':u.password})['access_token']
    u.post('/account/recovery-code', {'password':'incorrect'}, expected=403)
    first = u.post('/account/recovery-code', {'password':u.password})['recovery_code']
    code = u.post('/account/recovery-code', {'password':u.password})['recovery_code']
    with closing(d.connect()) as c:
        row = c.execute('SELECT * FROM account_recovery WHERE user_id=?',(u.id,)).fetchone()
        assert code != row['code_hash'] and first != row['code_hash']
    args={'email':u.email,'new_password':'Replacement123!','recovery_code':first}
    u.post('/account/reset-password',args,expected=400)
    args['recovery_code']=code
    assert u.post('/account/reset-password',args)['sessions_revoked']
    for token in (u.token, second):
        headers={'Authorization':'Bearer '+token}
        for version in ('v1','v2'):
            assert u.client.get(f'/api/{version}/me',headers=headers).status_code==401
    u.post('/account/reset-password',args,expected=400)
    u.post('/login',{'email':u.email,'password':u.password},expected=401)
    assert u.post('/login',{'email':u.email,'password':'Replacement123!'})['access_token']


def test_delete_anonymizes_revokes_and_retains_other_owners():
    u, other = Mobile('delete@example.jp'), Mobile('other@example.jp')
    lid, other_lid = u.listing(), other.listing()
    u.post('/account/recovery-code',{'password':u.password})
    u.post('/listings/'+str(lid)+'/photos/add',files={'images':('owned.png',b'img','image/png')})
    # Use a draft too, which must be erased alongside listing images.
    draft=u.post('/oneclick/upload',{'name':'camera'},files={'photos':('draft.png',b'img','image/png')})
    with closing(d.connect()) as c:
        files=[r['filename'] for r in c.execute('SELECT filename FROM images WHERE listing_id=?',(lid,))]
        row=c.execute('SELECT photo FROM oneclick_drafts WHERE user_id=?',(u.id,)).fetchone()
        files.append(row['photo'])
    assert files
    u.post('/account/delete',{'password':'bad','confirmation':'DELETE'},expected=403)
    u.post('/account/delete',{'password':u.password,'confirmation':'NO'},expected=400)
    result=u.post('/account/delete',{'password':u.password,'confirmation':'DELETE'})
    assert result['deleted'] and result['transaction_records_retained']
    assert u.client.get('/api/v2/me',headers=u.headers).status_code==401
    for file in files:
        assert u.client.get('/uploads/'+file).status_code==404
    assert other.get('/listings/'+str(other_lid))['id']==other_lid
    assert u.client.get('/api/v2/listings/'+str(lid)).status_code==404
    with closing(d.connect()) as c:
        row=c.execute('SELECT * FROM users WHERE id=?',(u.id,)).fetchone()
        assert row['is_active']==0 and row['email']!=u.email and row['phone']==''
        for table in ('sessions','account_recovery','oneclick_drafts'):
            assert not c.execute('SELECT 1 FROM '+table+' WHERE user_id=?',(u.id,)).fetchone()
        assert c.execute("SELECT 1 FROM audit_log WHERE actor_id=? AND action='account_deleted'",(u.id,)).fetchone()


def test_blocks_apply_both_directions_and_existing_order_survives():
    seller,buyer=Mobile('seller@example.jp'),Mobile('buyer@example.jp')
    lid=seller.listing()
    order=buyer.post('/listings/'+str(lid)+'/buy')['next']
    lid2=seller.listing()
    seller.post('/account/blocked/'+str(buyer.id),{'blocked':True})
    assert buyer.get('/listings')['items']==[]
    buyer.post('/listings/'+str(lid2)+'/buy',expected=409)
    assert buyer.get(order)['id']
    seller.post('/account/blocked/'+str(buyer.id),{'blocked':False})
    assert buyer.get('/listings')['items']


def test_report_resolution_is_restricted_and_idempotent():
    seller, reporter, admin=Mobile('seller@example.jp'),Mobile('reporter@example.jp'),Mobile('admin@example.jp','admin')
    lid=seller.listing()
    data={'target_type':'listing','target_id':lid,'reason':'counterfeit','details':'Please review'}
    rid=reporter.post('/reports',data)['id']
    assert reporter.post('/reports',data)['id']==rid
    reporter.post(f'/admin/reports/{rid}/resolve',{'decision':'upheld','note':'checked'},expected=403)
    assert admin.post(f'/admin/reports/{rid}/resolve',{'decision':'upheld','note':'checked'})['status']=='upheld'
    assert admin.post(f'/admin/reports/{rid}/resolve',{'decision':'dismissed','note':'again'})['status']=='upheld'
    assert reporter.client.get('/api/v2/listings/'+str(lid)).status_code==404
    assert seller.get('/listings/'+str(lid))['status']=='moderation_hold'
    reporter.post('/reports',{'target_type':'message','target_id':999,'reason':'privacy'},expected=404)


def test_upload_replay_creates_one_draft_and_adds_one_batch():
    u=Mobile('photos@example.jp')
    data={'name':'camera','upload_key':'lost_ack_1'}
    photo={'photos':('photo.png',b'img','image/png')}
    first=u.post('/oneclick/upload',data,files=photo)['next']
    assert u.post('/oneclick/upload',data,files=photo)['next']==first
    did=int(first.split('/')[-1])
    for _ in range(2):
        u.post(first+'/photos/add',{'upload_key':'lost_ack_2'},files=photo)
    u.post(first+'/details',{'name':'corrected camera','text':'new description','condition':'fair'})
    stranger=Mobile('photo-stranger@example.jp')
    stranger.post(first+'/details',{'name':'not mine'},expected=403)
    result=u.get(first)
    assert result['name']=='corrected camera' and result['text']=='new description'
    assert len(result['photos'])==2
    u.post(first+'/photos/add',{'upload_key':'lost_ack_1'},files=photo,expected=409)
    with closing(d.connect()) as c:
        assert c.execute('SELECT COUNT(*) n FROM oneclick_drafts WHERE user_id=?',(u.id,)).fetchone()['n']==1
        assert c.execute('SELECT COUNT(*) n FROM draft_upload_requests WHERE user_id=?',(u.id,)).fetchone()['n']==2


def test_content_filter_normalizes_spaced_prohibited_text():
    u=Mobile('content@example.jp')
    u.post('/listings/new',{'category_slug':'appliance','title_ja':'児 童 ポ ル ノ','price':1000},expected=400)


def test_blocked_messages_and_auction_mutations_cannot_bypass_policy():
    from datetime import datetime, timedelta, timezone
    seller,buyer,stranger=Mobile('auction-seller@example.jp'),Mobile('auction-buyer@example.jp'),Mobile('stranger@example.jp')
    lid=seller.listing()
    thread=f'/messages/{lid}/{buyer.id}'
    seller.post(thread,{'body':'Hello','receiver_id':buyer.id})
    with closing(d.connect()) as c:
        mid=c.execute('SELECT id FROM messages WHERE listing_id=?',(lid,)).fetchone()['id']
    stranger.post('/reports',{'target_type':'message','target_id':mid,'reason':'privacy'},expected=404)
    buyer.post('/reports',{'target_type':'message','target_id':mid,'reason':'harassment'})
    ends=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
    auction=seller.post(f'/listings/{lid}/auction',{'start_price':1000,'reserve_price':0,'min_increment':100,'buy_now_price':5000,'ends_at':ends,'deposit_required':1,'deposit_amount':100})['next']
    seller.post('/account/blocked/'+str(buyer.id),{'blocked':True})
    buyer.post(thread,{'body':'Blocked','receiver_id':seller.id},expected=409)
    seller.post(thread,{'body':'Also blocked','receiver_id':buyer.id},expected=409)
    assert buyer.get('/auctions')['items']==[]
    for action,args in [('bid',{'amount':1000}),('deposit',{}),('buy-now',{})]:
        buyer.post(auction+'/'+action,args,expected=409)
    seller.post('/account/blocked/'+str(buyer.id),{'blocked':False})
    assert buyer.get('/auctions')['items']
    buyer.post(auction+'/deposit')


def test_deletion_refuses_running_analysis_and_preserves_transaction_audit():
    from app.security import now_tokyo
    seller,buyer=Mobile('keep-seller@example.jp'),Mobile('keep-buyer@example.jp')
    lid=seller.listing()
    order=buyer.post(f'/listings/{lid}/buy')['next']
    with closing(d.connect()) as c:
        c.execute("INSERT INTO ai_jobs(user_id,kind,status,created_at,updated_at) VALUES(?,?,'running',?,?)",(seller.id,'oneclick_recognize',now_tokyo(),now_tokyo()))
        c.commit()
    seller.post('/account/delete',{'password':seller.password,'confirmation':'DELETE'},expected=409)
    assert seller.get('/me')['id']==seller.id
    with closing(d.connect()) as c:
        c.execute("UPDATE ai_jobs SET status='done' WHERE user_id=?",(seller.id,)); c.commit()
    seller.post('/account/delete',{'password':seller.password,'confirmation':'DELETE'})
    assert buyer.get(order)['id']
    with closing(d.connect()) as c:
        assert c.execute('SELECT 1 FROM order_audit WHERE order_id=?',(int(order.split('/')[-1]),)).fetchone()
