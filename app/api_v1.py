"""Native mobile JSON boundary. Existing HTML commands remain the business authority.

Read models use the existing schema; mutations execute the existing ASGI routes,
so validation, role checks, audits, rate limits and payment semantics stay shared.
No HTML is returned to, parsed by, or rendered in the mobile application.
"""
import json
import re
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from . import db as d
from . import main as legacy
from .security import can_operate, can_admin, can_appraise, now_tokyo
from .market import category_stats, listing_price_moves, profit_report, weekly_curve
from .mobile_overview import marketplace_overview
from .aijobs import get_job
from .auctions import compute_price, min_next_bid
from .oneclick import detail_checklist_for


class JsonRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()
        async def handler(request):
            try:
                return await original(request)
            except StarletteHTTPException as exc:
                return JSONResponse({'error':str(exc.detail)}, status_code=exc.status_code)
            except RequestValidationError:
                return JSONResponse({'error':'invalid_request'},status_code=422)
            except (ValueError, TypeError, KeyError):
                return JSONResponse({'error':'invalid_request'}, status_code=400)
        return handler


router = APIRouter(prefix='/api/v1', route_class=JsonRoute)
PUBLIC_FIELDS = ('id','display_name','role','region','created_at')

def user(request, optional=False):
    header = request.headers.get('authorization','')
    if not header.startswith('Bearer '):
        if optional: return None
        raise HTTPException(401,'login_required')
    token=header[7:]
    with d.connect() as c:
        row=c.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires_at>=?',(token,now_tokyo())).fetchone()
    if not row: raise HTTPException(401,'session_expired')
    return row


def clean(row):
    if row is None: return None
    value=dict(row)
    for key in ('pw_hash','salt','token','idempotency_key','phone'):
        value.pop(key,None)
    for key in list(value):
        if key.endswith('_json'):
            try: value[key[:-5]]=json.loads(value.pop(key) or '{}')
            except ValueError: value[key[:-5]]={}
    return value


def photos(c,lid):
    return [dict(r) | {'url':'/uploads/'+r['filename']} for r in c.execute('SELECT * FROM images WHERE listing_id=? ORDER BY sort,id',(lid,))]


def listing(c,row):
    out=clean(row)
    out['photos']=photos(c,row['id'])
    out['effective_price']=legacy.effective_price(row)
    out['seller']=clean(c.execute('SELECT id,display_name,role FROM users WHERE id=?',(row['seller_id'],)).fetchone())
    return out


def action(path,zh,ja,fields=None):
    return {'path':path,'label':{'zh':zh,'ja':ja},'fields':fields or {}}


def fields_for(path):
    # FastAPI's existing request model supplies names/defaults/required metadata.
    for route in legacy.app.routes:
        if not isinstance(route,APIRoute) or 'POST' not in route.methods: continue
        if route.path_regex.fullmatch(path):
            fields={}
            for f in route.dependant.body_params:
                if f.name in ('image','images','photo','photos'): continue
                default=f.default
                required=f.field_info.is_required()
                fields[f.name]={'required':required,'default':None if required else default,
                                'type':'number' if f.field_info.annotation in (int,float) else 'text'}
            return fields
    return {}


def command(path,zh,ja,defaults=None):
    fields=fields_for(path)
    for key,value in (defaults or {}).items():
        if key in fields: fields[key]['default']=value
    return action(path,zh,ja,fields)


@router.get('/config')
def config():
    with d.connect() as c:
        categories=[clean(r) for r in c.execute('SELECT * FROM categories ORDER BY id')]
        regions=json.loads(d.get_setting(c,'regions') or '[]')
        services=d.effective_service_prices(d.get_setting(c,'service_prices'))
        commission=legacy.commission_rate(c)
        delivery_rules=json.loads(d.get_setting(c,'delivery_rules') or '{}')
    return {'name':'Yuno Life','currency':'JPY','timezone':'Asia/Tokyo','max_photos':10,
            'categories':categories,'regions':regions,'services':services,'commission_rate':commission,'delivery_rules':delivery_rules,'simulated':True,
            'languages':['system','zh','ja'],'valuation_disclaimer':'此报价为AI根据现实数据做出的估价，用户可以根据自身另行填写'}


@router.get('/listings')
def listings(request:Request,q:str='',category:str='',region:str='',price_min:int=0,price_max:int=1000000000,only_platform:bool=False):
    if price_min<0 or price_max<price_min: raise HTTPException(400,'bad_price_filter')
    with d.connect() as c:
        sql="SELECT l.* FROM listings l JOIN categories cat ON cat.id=l.category_id WHERE l.status='active' AND l.price BETWEEN ? AND ?"
        args=[price_min,price_max]
        if q:
            sql+=' AND (l.title_ja LIKE ? OR l.title_zh LIKE ?)'; args += ['%'+q+'%']*2
        if category: sql+=' AND cat.slug=?';args.append(category)
        if region: sql+=' AND l.region=?';args.append(region)
        if only_platform: sql+=' AND l.is_platform_owned=1'
        sql+=' ORDER BY l.is_featured DESC,l.id DESC LIMIT 200'
        return {'items':[listing(c,r) for r in c.execute(sql,args)]}


@router.get('/listings/{lid}')
def listing_detail(request:Request,lid:int):
    u=user(request,True)
    with d.connect() as c:
        row=c.execute('SELECT * FROM listings WHERE id=?',(lid,)).fetchone()
        if not row: raise HTTPException(404,'not_found')
        out=listing(c,row)
        out['category']=clean(d.category_by_id(c,row['category_id']))
        out['review']=clean(c.execute('SELECT * FROM hv_reviews WHERE listing_id=?',(lid,)).fetchone())
        out['auction']=clean(c.execute('SELECT * FROM auctions WHERE listing_id=?',(lid,)).fetchone())
        out['actions']=[]
        if u and row['status']=='active':
            if u['id']==row['seller_id']:
                out['actions'] += [command(f'/buyback/new','申请平台买断','買取申込',{'listing_id':lid}),command(f'/listings/{lid}/auction','发起拍卖','オークション出品')]
            else:
                out['actions'] += [command(f'/listings/{lid}/buy','立即购买','購入'), command(f'/listings/{lid}/offer','议价','価格交渉')]
        out['checklist']=detail_checklist_for(out['category']['slug'])
        if u:
            out['thread_buyer_id']=u['id'] if u['id']!=row['seller_id'] else None
            followed=c.execute('SELECT id FROM listing_follows WHERE user_id=? AND listing_id=?',(u['id'],lid)).fetchone()
            out['actions'].append(command(f'/listings/{lid}/'+('unfollow' if followed else 'follow'),'取消关注' if followed else '关注','フォロー解除' if followed else 'フォロー'))
        return out


@router.get('/me')
def me(request:Request):
    u=user(request)
    with d.connect() as c:
        out={k:u[k] for k in PUBLIC_FIELDS};out['email']=u['email']
        out['listings']=[listing(c,r) for r in c.execute('SELECT * FROM listings WHERE seller_id=? ORDER BY id DESC',(u['id'],))]
        for table,where in [('orders','buyer_id=? OR seller_id=?'),('buybacks','seller_id=?'),('service_orders','user_id=?'),('oneclick_drafts','user_id=?')]:
            args=(u['id'],u['id']) if table=='orders' else (u['id'],)
            out[table]=[clean(r) for r in c.execute(f'SELECT * FROM {table} WHERE {where} ORDER BY id DESC',args)]
        out['following']=[listing(c,r) for r in c.execute('SELECT l.* FROM listings l JOIN listing_follows f ON f.listing_id=l.id WHERE f.user_id=? ORDER BY f.id DESC',(u['id'],))]
        for order in out['orders']:
            row=c.execute('SELECT * FROM listings WHERE id=?',(order['listing_id'],)).fetchone()
            order['listing']=listing(c,row) if row else None
        out['offers']=[clean(r) for r in c.execute('SELECT o.* FROM offers o JOIN listings l ON l.id=o.listing_id WHERE o.buyer_id=? OR l.seller_id=? ORDER BY o.id DESC',(u['id'],u['id']))]
        out['threads']=[dict(r) for r in c.execute('SELECT DISTINCT m.listing_id,m.buyer_id,l.title_ja,l.title_zh FROM messages m JOIN listings l ON l.id=m.listing_id WHERE m.buyer_id=? OR l.seller_id=?',(u['id'],u['id']))]
        out['deliveries']=[clean(r) for r in c.execute('SELECT dl.* FROM deliveries dl JOIN orders o ON o.id=dl.order_id WHERE o.buyer_id=? OR o.seller_id=? OR dl.courier_id=? ORDER BY dl.id DESC',(u['id'],u['id'],u['id']))]
        if u['role']=='courier':
            out['deliveries']=[clean(r) for r in c.execute("SELECT * FROM deliveries WHERE status='requested' OR courier_id=? ORDER BY id DESC",(u['id'],))]
        if u['role']=='appraiser':
            out['buybacks']=[clean(r) for r in c.execute("SELECT * FROM buybacks WHERE status='pickup_scheduled' ORDER BY id DESC")]
        return out


@router.get('/orders')
def orders(request:Request): return {'items':me(request)['orders']}


@router.get('/market')
def market():
    with d.connect() as c:
        return {'overview':marketplace_overview(c,legacy.effective_price),'moves':listing_price_moves(c),'categories':category_stats(c),'curve':weekly_curve(c),'basis':{'zh':'平台真实订单；首次与最近成交价比较；挂牌价不计入涨跌。','ja':'実取引の初回価格と最新価格を比較。出品価格は対象外。'}}


@router.get('/auctions')
def auctions():
    with d.connect() as c:
        return {'items':[clean(r) for r in c.execute('SELECT a.*,l.title_ja,l.title_zh FROM auctions a JOIN listings l ON l.id=a.listing_id ORDER BY a.id DESC')]}


@router.get('/ai-jobs/{jid}')
def job(request:Request,jid:int):
    u=user(request)
    with d.connect() as c: out=get_job(c,jid)
    if not out: raise HTTPException(404,'not_found')
    if out['user_id']!=u['id'] and not can_operate(u): raise HTTPException(403,'forbidden')
    return out


@router.get('/oneclick/{did}')
def draft(request:Request,did:int):
    u=user(request)
    with d.connect() as c:
        row=legacy._draft_or_403(c,did,u)
        out=clean(row)
        names,dr=legacy._draft_photos(row)
        out['photos']=[{'url':'/uploads/'+name,'filename':name,'id':i} for i,name in enumerate(names)]
        out['draft']=dr
        out['actions']=[command(f'/oneclick/{did}/model','确认精确型号','型番確認')]
        return out


@router.get('/messages/{lid}/{bid}')
def messages(request:Request,lid:int,bid:int):
    u=user(request)
    with d.connect() as c:
        row=c.execute('SELECT * FROM listings WHERE id=?',(lid,)).fetchone()
        if not row or u['id'] not in (bid,row['seller_id']): raise HTTPException(403,'forbidden')
        return {'items':[clean(r) for r in c.execute('SELECT m.*,u.display_name FROM messages m JOIN users u ON u.id=m.sender_id WHERE listing_id=? AND buyer_id=? ORDER BY m.id',(lid,bid))],
                'receiver_id':row['seller_id'] if u['id']==bid else bid,
                'action':command(f'/messages/{lid}/{bid}','发送','送信')}


@router.get('/admin/{section}')
def admin(request:Request,section:str):
    u=user(request)
    if not can_operate(u): raise HTTPException(403,'forbidden')
    mapping={'users':'users','listings':'listings','buybacks':'buybacks','orders':'orders','inventory':'inventory','auctions':'auctions','deliveries':'deliveries','services':'service_orders','refunds':'refunds','disputes':'disputes','high-value':'hv_reviews','alerts':'alerts','suggestions':'price_suggestions','audit':'audit_log','expenses':'expenses'}
    with d.connect() as c:
        if section=='profit': return profit_report(c)
        if section=='settings':
            if not can_admin(u): raise HTTPException(403,'forbidden')
            return {'items':[clean(r) for r in c.execute('SELECT * FROM settings')], 'actions':[command('/admin/settings','保存参数','設定保存')]}
        if section not in mapping: raise HTTPException(404,'not_found')
        items=[]
        for row in c.execute('SELECT * FROM '+mapping[section]+' ORDER BY '+('id DESC' if section!='settings' else 'key')+' LIMIT 200'):
            value=clean(row);value['actions']=[];i=row['id']
            if section=='users' and can_admin(u): value['actions']=[command(f'/admin/users/{i}/role','修改角色','ロール変更')]
            if section=='listings': value['actions']=[command(f'/admin/listings/{i}/toggle','上下架','公開切替')]
            if section=='high-value': value['actions']=[command(f'/admin/high-value/{i}/review','人工审核','審査')]
            if section=='alerts': value['actions']=[command(f'/admin/alerts/{i}/ack','确认处理','確認')]
            if section=='suggestions': value['actions']=[command(f'/admin/suggestions/{i}/approve','批准调价','価格承認'),command(f'/admin/suggestions/{i}/reject','驳回','却下')]
            items.append(value)
        actions=[]
        if section=='expenses' and can_admin(u): actions=[command('/admin/expenses','登记费用','経費登録')]
        if section=='alerts': actions=[command('/admin/agents/run-anomalies','异常扫描','異常検知')]
        if section=='suggestions': actions=[command('/admin/agents/run-pricing','生成调价建议','価格提案')]
        return {'items':items,'actions':actions}


@router.get('/{resource}/{rid}')
def detail(request:Request,resource:str,rid:int):
    mapping={'orders':'orders','offers':'offers','buyback':'buybacks','services':'service_orders','deliveries':'deliveries','refunds':'refunds','disputes':'disputes','auctions':'auctions','users':'users'}
    if resource not in mapping: raise HTTPException(404,'not_found')
    u=user(request,resource in ('auctions','users'))
    with d.connect() as c:
        row=c.execute('SELECT * FROM '+mapping[resource]+' WHERE id=?',(rid,)).fetchone()
        if not row: raise HTTPException(404,'not_found')
        out=clean(row);out['actions']=[]
        if resource=='users':
            return {k:row[k] for k in PUBLIC_FIELDS} | {'reviews':[clean(r) for r in c.execute('SELECT * FROM reviews WHERE reviewee_id=?',(rid,))]}
        if resource=='auctions':
            item=c.execute('SELECT * FROM listings WHERE id=?',(row['listing_id'],)).fetchone()
            bids=c.execute('SELECT * FROM bids WHERE auction_id=? ORDER BY id',(rid,)).fetchall()
            price,leader=compute_price(row,bids)
            out.update({'listing':listing(c,item),'current_price':price,'leader_id':leader,'minimum_bid':min_next_bid(row,bids),'bids':[{'id':b['id'],'bidder_id':b['bidder_id'],'amount':b['amount'],'created_at':b['created_at']} for b in bids]})
            if u and row['status']=='active' and u['id']!=item['seller_id']:
                out['actions']=[command(f'/auctions/{rid}/bid','竞价（模拟）','入札（模擬）',{'amount':out['minimum_bid']})]
                if row['deposit_required']: out['actions'].append(command(f'/auctions/{rid}/deposit','保证金（模拟）','保証金（模擬）'))
                if row['buy_now_price']: out['actions'].append(command(f'/auctions/{rid}/buy-now','一口价购买','即決'))
            if u and can_operate(u): out['actions'].append(command(f'/auctions/{rid}/settle','结算（模拟）','精算（模擬）'))
            return out
        participants=[]
        order=None
        if resource in ('orders','offers'):
            item=c.execute('SELECT * FROM listings WHERE id=?',(row['listing_id'],)).fetchone()
            participants=[row['buyer_id'],item['seller_id']];out['listing']=listing(c,item)
        elif resource=='buyback': participants=[row['seller_id']]
        elif resource=='services': participants=[row['user_id']]
        else:
            order=c.execute('SELECT * FROM orders WHERE id=?',(row['order_id'],)).fetchone()
            participants=[order['buyer_id'],order['seller_id']]
            if resource=='deliveries': participants.append(row['courier_id'])
        courier=u['role']=='courier' and resource=='deliveries'
        if u['id'] not in participants and not can_operate(u) and not courier and not (resource=='buyback' and can_appraise(u)): raise HTTPException(403,'forbidden')
        if resource=='orders':
            status=row['status']
            buyer=u['id']==row['buyer_id'] or can_operate(u)
            if buyer and status=='pending_payment': out['actions'] += [command(f'/orders/{rid}/pay','模拟支付 · 不会扣款','模擬決済 · 請求なし'),command(f'/orders/{rid}/cancel','取消订单','注文取消')]
            if buyer and status=='paid': out['actions'].append(command(f'/orders/{rid}/complete','确认收货（模拟）','受取確認（模擬）'))
            if status in ('paid','completed'):
                out['actions'] += [command(f'/orders/{rid}/delivery-request','配送预约（模拟）','配達予約（模擬）',{'kind':'buyer_delivery'}),command(f'/orders/{rid}/refund','申请退款（模拟）','返金申請（模擬）'),command(f'/orders/{rid}/dispute','发起争议','紛争申立')]
            if status=='completed': out['actions'].append(command(f'/orders/{rid}/review','评价','レビュー',{'rating':5}))
            out['audit']=[clean(r) for r in c.execute('SELECT * FROM order_audit WHERE order_id=? ORDER BY id',(rid,))]
            out['refunds']=[clean(r) for r in c.execute('SELECT * FROM refunds WHERE order_id=?',(rid,))]
            out['disputes']=[clean(r) for r in c.execute('SELECT * FROM disputes WHERE order_id=?',(rid,))]
        if resource=='offers':
            if u['id']==item['seller_id'] and row['status']=='pending': out['actions']=[command(f'/offers/{rid}/accept','接受','承諾'),command(f'/offers/{rid}/reject','拒绝','拒否'),command(f'/offers/{rid}/counter','还价','再提案')]
            if u['id']==row['buyer_id'] and row['status']=='countered': out['actions']=[command(f'/offers/{rid}/accept-counter','接受还价','再提案に同意')]
        if resource=='buyback':
            transitions={'reviewing':['quote'],'submitted':['review','reject'],'estimated':['review','reject'],'quoted':['reject'],'pickup_scheduled':['inspect'],'inspected':['pay']}
            labels={'review':('审核','審査'),'reject':('拒绝','拒否'),'quote':('报价','見積'),'inspect':('验货','検品'),'pay':('收购付款（模拟）','買取決済（模擬）')}
            if can_operate(u):
                for op in transitions.get(row['status'],[]): out['actions'].append(command(f'/buyback/{rid}/{op}',*labels[op]))
            if u['id']==row['seller_id']:
                if row['status']=='quoted': out['actions'].append(command(f'/buyback/{rid}/accept','接受报价','見積承諾'))
                if row['status']=='accepted': out['actions'].append(command(f'/buyback/{rid}/pickup','预约取货','集荷予約'))
        if resource=='buyback' and u['role']=='appraiser' and row['status']=='pickup_scheduled':
            out['actions'].append(command(f'/buyback/{rid}/inspect','验货','検品'))
        if resource=='services':
            if can_operate(u):
                for state,op in [('requested','confirm'),('confirmed','start'),('in_progress','complete')]:
                    if row['status']==state: out['actions'].append(command(f'/services/{rid}/{op}',{'confirm':'确认','start':'开始','complete':'完成'}[op],{'confirm':'確認','start':'開始','complete':'完了'}[op]))
            if row['status'] in ('requested','confirmed'): out['actions'].append(command(f'/services/{rid}/cancel','取消','取消'))
        if resource=='deliveries':
            if can_operate(u) or courier:
                for state,op,zh,ja in [('requested','assign','接单','受注'),('assigned','pickup','取货完成','集荷完了'),('picked_up','deliver','交付完成','配達完了')]:
                    if row['status']==state: out['actions'].append(command(f'/deliveries/{rid}/{op}',zh+'（模拟）',ja+'（模擬）'))
            if row['status']=='delivered' and u['id']==order['buyer_id']: out['actions'].append(command(f'/deliveries/{rid}/confirm','确认交付','配達確認'))
        if resource in ('refunds','disputes') and can_operate(u) and row['status'] in ('requested','open'):
            out['actions'].append(command(f'/{resource}/{rid}/decide','人工裁决','手動判断'))
        return out


@router.get('/rules')
def rules():
    # Public rule content, kept aligned with the existing legal pages.
    return {'items':[
      {'key':'terms','zh':'条款：平台以坂户市为起点，价格含税。卖家对描述负责，禁止虚假描述。支付和配送均为模拟，不产生真实扣款。','ja':'利用規約：坂戸市を起点に提供。表示価格は税込。出品者は説明に責任を負います。決済・配送は模擬です。'},
      {'key':'privacy','zh':'隐私：注册信息仅用于交易联系和账号管理。照片与商品信息本地保存，不发送给付费 API。','ja':'プライバシー：登録情報は取引連絡とアカウント管理に使用。写真はローカル保存、有料APIへ送信しません。'},
      {'key':'returns','zh':'退货争议：订单页申请退款或争议，由运营人工裁决，结果与审计记录可查询。','ja':'返品・紛争：注文から申請。運営が手動で判断し、結果を記録します。'},
      {'key':'prohibited','zh':'禁售：违法物品、赃物、假冒伪造商品、危险品、依法禁止交易的物品。','ja':'禁止物：違法品、盗品、偽造品、危険物、法令上取引禁止の物品。'}]}


async def proxy(request:Request,path:str):
    public=path in ('/login','/register')
    if not public: user(request)
    headers={'host':request.headers.get('host','localhost'),'accept':'application/json'}
    if request.headers.get('authorization','').startswith('Bearer '): headers['cookie']='yuno_session='+request.headers['authorization'][7:]
    if request.headers.get('origin'): headers['origin']=request.headers['origin']
    ct=request.headers.get('content-type','')
    kwargs={}
    if 'application/json' in ct:
        data=await request.json()
        if not isinstance(data,dict): raise HTTPException(400,'object_required')
        kwargs['data']={k:str(v) for k,v in data.items() if v is not None}
    else:
        kwargs['content']=await request.body()
        if ct: headers['content-type']=ct
    transport=httpx.ASGITransport(app=legacy.app,client=(request.client.host if request.client else '127.0.0.1',12345))
    async with httpx.AsyncClient(transport=transport,base_url='http://'+headers['host'],follow_redirects=False) as client:
        response=await client.post(path,headers=headers,**kwargs)
    if response.status_code>=400:
        try: error=response.json().get('detail','request_rejected')
        except (ValueError,AttributeError): error='request_rejected'
        return JSONResponse({'error':error},status_code=response.status_code)
    if 'application/json' in response.headers.get('content-type',''):
        return JSONResponse(response.json(),status_code=response.status_code)
    location=response.headers.get('location','')
    message=parse_qs(urlsplit(location).query).get('msg',[''])[0]
    if public:
        cookie=SimpleCookie();cookie.load(response.headers.get('set-cookie',''))
        if 'yuno_session' not in cookie:
            return JSONResponse({'error':message or 'authentication_failed'},status_code=401 if path=='/login' else 400)
        token=cookie['yuno_session'].value
        return {'access_token':token,'token_type':'bearer'}
    if message != 'already_paid' and re.search(r'(^|_)(invalid|bad|cannot|own|not|needs|pending|forbidden|conflict|requires|failed|error|out_of_range)(_|$)',message):
        return JSONResponse({'error':message,'next':location.split('?')[0]},status_code=409)
    # Redirect messages are business outcomes, not proof of success. Clients show
    # the result and reload authoritative resources after every command.
    return {'next':location.split('?')[0], 'message':message, 'simulated':True}



@router.post('/oneclick/{did}/photos/reorder')
async def reorder_draft(request:Request,did:int):
    u=user(request)
    payload=await request.json()
    order=payload.get('order')
    with d.connect() as c:
        row=legacy._draft_or_403(c,did,u)
        if row['status']=='published': raise HTTPException(409,'already_published')
        names,dr=legacy._draft_photos(row)
        if not isinstance(order,list) or any(type(i) is not int for i in order) or sorted(order)!=list(range(len(names))):
            raise HTTPException(400,'invalid_photo_order')
        legacy._set_draft_photos(c,did,[names[i] for i in order],row)
        c.commit()
    return {'next':f'/oneclick/{did}','message':'photos_reordered'}


@router.post('/oneclick/{did}/photos/{idx}/replace')
async def replace_draft_photo(request:Request,did:int,idx:int):
    u=user(request)
    form=await request.form()
    with d.connect() as c:
        row=legacy._draft_or_403(c,did,u)
        if row['status']=='published': raise HTTPException(409,'already_published')
        names,dr=legacy._draft_photos(row)
        if idx<0 or idx>=len(names): raise HTTPException(404,'photo_not_found')
        blobs=await legacy._read_uploads([form.get('photo')])
        if len(blobs)!=1: raise HTTPException(400,'photo_required')
        legacy._save_upload_blobs(blobs)
        names[idx]=blobs[0][0]
        legacy._set_draft_photos(c,did,names,row)
        c.commit()
    return {'next':f'/oneclick/{did}','message':'photo_replaced'}


@router.post('/support')
async def support(request:Request):
    user(request)
    payload=await request.json()
    question=str(payload.get('question',''))
    legacy._check_text(question,2000,required=True)
    result=legacy.support_agent(question)
    return {'answer_zh':result['answer'].replace('已转人工客服处理。','请通过站内消息联系运营。'),
            'answer_ja':'ローカルルール案内：決済と配送は模擬です。返品・紛争は注文から申請してください。手数料は7〜10%、配送は150円〜です。個別の判断は運営へお問い合わせください。',
            'note':'local_rules_only'}


def register_commands():
    # Reuse every existing POST path under /api/v1; no generic arbitrary proxy.
    routes=[r for r in legacy.app.routes if isinstance(r,APIRoute) and 'POST' in r.methods and not r.path.startswith('/api/')]
    for route in routes:
        async def endpoint(request:Request,_route=route):
            path=_route.path
            for key,value in request.path_params.items(): path=path.replace('{'+key+'}',str(value))
            return await proxy(request,path)
        # Avoid exposing captured APIRoute as a FastAPI query parameter.
        import inspect
        endpoint.__signature__=inspect.Signature([inspect.Parameter('request',inspect.Parameter.POSITIONAL_OR_KEYWORD,annotation=Request)])
        router.add_api_route(route.path,endpoint,methods=['POST'],name='mobile_'+route.name)
register_commands()
