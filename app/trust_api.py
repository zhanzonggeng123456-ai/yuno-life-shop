"""Native account deletion, recovery codes, blocking, and moderation.

No email provider, paid API, or real transaction is invoked by these routes.
"""
import json
import secrets
from contextlib import closing

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from . import db, storage
from .security import (audit_log, can_operate, check_rate_limit, client_ip,
                       hash_password, now_tokyo, verify_password)

class PrivateJsonRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()
        async def handler(request):
            try:
                response = await original(request)
            except HTTPException as exc:
                response = JSONResponse({'error': exc.detail}, status_code=exc.status_code)
            response.headers['Cache-Control'] = 'no-store'
            return response
        return handler


router = APIRouter(prefix='/api/v2', route_class=PrivateJsonRoute)


def identity(request):
    token = request.headers.get('authorization', '')
    if not token.startswith('Bearer '):
        raise HTTPException(401, 'login_required')
    with closing(db.connect()) as c:
        row = c.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id '
                        'WHERE s.token=? AND s.expires_at>=? AND u.is_active=1',
                        (token[7:], now_tokyo())).fetchone()
    if not row:
        raise HTTPException(401, 'session_expired')
    return row


async def body(request):
    try:
        value = await request.json()
    except ValueError:
        raise HTTPException(400, 'invalid_request')
    if not isinstance(value, dict):
        raise HTTPException(400, 'invalid_request')
    return value


def text(value, key, maximum=1000):
    result = value.get(key, '')
    if not isinstance(result, str) or len(result) > maximum:
        raise HTTPException(400, 'invalid_request')
    return result


def sensitive_limit(request, user_id):
    if not check_rate_limit(f'trust:{client_ip(request)}:{user_id}', 8, 900):
        raise HTTPException(429, 'too_many_requests')


def require_password(user, value):
    if not verify_password(text(value, 'password'), user['salt'], user['pw_hash']):
        raise HTTPException(403, 'current_password_required')


@router.get('/account/security')
def security(request: Request):
    user = identity(request)
    with closing(db.connect()) as c:
        return {'has_recovery_code': c.execute('SELECT 1 FROM account_recovery WHERE user_id=?',
                                               (user['id'],)).fetchone() is not None}


@router.post('/account/recovery-code')
async def recovery_code(request: Request):
    user = identity(request)
    sensitive_limit(request, user['id'])
    require_password(user, await body(request))
    code = secrets.token_urlsafe(24)
    salt, code_hash = hash_password(code)
    with closing(db.connect()) as c:
        c.execute('BEGIN IMMEDIATE')
        current = c.execute('SELECT * FROM users WHERE id=? AND is_active=1',(user['id'],)).fetchone()
        if not current or current['pw_hash'] != user['pw_hash']:
            raise HTTPException(401,'session_expired')
        c.execute('INSERT INTO account_recovery(user_id,salt,code_hash) VALUES(?,?,?) '
                  'ON CONFLICT(user_id) DO UPDATE SET salt=excluded.salt,code_hash=excluded.code_hash',
                  (user['id'], salt, code_hash))
        audit_log(c, user['id'], 'recovery_code_rotated', 'user', user['id'])
        c.commit()
    return {'recovery_code': code, 'shown_once': True}


@router.post('/account/reset-password')
async def reset_password(request: Request):
    value = await body(request)
    email = text(value, 'email', 254).strip()
    code = text(value, 'recovery_code', 200)
    password = text(value, 'new_password', 1000)
    # Count both IP and account buckets; unknown addresses get the same error.
    if not check_rate_limit(f'recovery-ip:{client_ip(request)}', 10, 900) or not check_rate_limit(
            f'recovery-account:{email}', 5, 900):
        raise HTTPException(429, 'too_many_requests')
    if len(password) < 8:
        raise HTTPException(400, 'password_too_short')
    with closing(db.connect()) as c:
        c.execute('BEGIN IMMEDIATE')
        user = c.execute('SELECT u.id,r.salt,r.code_hash FROM users u JOIN account_recovery r '
                         'ON r.user_id=u.id WHERE u.email=? AND u.is_active=1', (email,)).fetchone()
        if not user or not verify_password(code, user['salt'], user['code_hash']):
            c.rollback()
            raise HTTPException(400, 'invalid_recovery')
        salt, pw_hash = hash_password(password)
        c.execute('UPDATE users SET salt=?,pw_hash=? WHERE id=?', (salt, pw_hash, user['id']))
        c.execute('DELETE FROM account_recovery WHERE user_id=?', (user['id'],))
        c.execute('DELETE FROM sessions WHERE user_id=?', (user['id'],))
        audit_log(c, user['id'], 'password_reset', 'user', user['id'])
        c.commit()
    return {'message': 'password_reset', 'sessions_revoked': True}


@router.get('/account/blocked')
def blocked_users(request: Request):
    user = identity(request)
    with closing(db.connect()) as c:
        return {'items': [dict(r) for r in c.execute(
            'SELECT u.id,u.display_name FROM user_blocks b JOIN users u ON u.id=b.blocked_id '
            'WHERE b.user_id=? ORDER BY b.created_at DESC', (user['id'],))]}


@router.post('/account/blocked/{uid}')
async def block_user(request: Request, uid: int):
    user = identity(request)
    value = await body(request)
    if uid == user['id']:
        raise HTTPException(400, 'cannot_block_self')
    if value.get('blocked') not in (True, False) or type(value.get('blocked')) is not bool:
        raise HTTPException(400, 'invalid_request')
    with closing(db.connect()) as c:
        if not c.execute('SELECT id FROM users WHERE id=?', (uid,)).fetchone():
            raise HTTPException(404, 'not_found')
        if value['blocked']:
            c.execute('INSERT OR IGNORE INTO user_blocks VALUES(?,?,?)', (user['id'], uid, now_tokyo()))
        else:
            c.execute('DELETE FROM user_blocks WHERE user_id=? AND blocked_id=?', (user['id'], uid))
        c.commit()
    return {'blocked': value['blocked']}


@router.post('/reports')
async def report(request: Request):
    user = identity(request)
    if not check_rate_limit(f'reports:{user["id"]}', 10, 3600):
        raise HTTPException(429, 'too_many_requests')
    value = await body(request)
    kind, target, reason = value.get('target_type'), value.get('target_id'), value.get('reason')
    if kind not in ('listing', 'message') or type(target) is not int or target < 1 or reason not in (
            'illegal', 'counterfeit', 'harassment', 'privacy', 'other'):
        raise HTTPException(400, 'invalid_request')
    with closing(db.connect()) as c:
        row = c.execute('SELECT * FROM '+('listings' if kind == 'listing' else 'messages')+
                        ' WHERE id=?', (target,)).fetchone()
        if not row or (kind == 'message' and user['id'] not in (row['sender_id'], row['receiver_id'])):
            raise HTTPException(404, 'not_found')
        existing = c.execute("SELECT id FROM content_reports WHERE reporter_id=? AND target_type=? "
                             "AND target_id=? AND status='open'", (user['id'], kind, target)).fetchone()
        if existing:
            return {'id': existing['id'], 'status': 'open'}
        cur = c.execute('INSERT INTO content_reports(reporter_id,target_type,target_id,reason,details,created_at) '
                        'VALUES(?,?,?,?,?,?)', (user['id'], kind, target, reason,
                                               text(value, 'details'), now_tokyo()))
        c.commit()
        return {'id': cur.lastrowid, 'status': 'open'}


@router.get('/admin/reports')
def reports(request: Request):
    user = identity(request)
    if not can_operate(user):
        raise HTTPException(403, 'forbidden')
    with closing(db.connect()) as c:
        return {'items': [dict(r) for r in c.execute('SELECT * FROM content_reports ORDER BY id DESC LIMIT 200')]}


@router.post('/admin/reports/{rid}/resolve')
async def resolve_report(request: Request, rid: int):
    user = identity(request)
    if not can_operate(user):
        raise HTTPException(403, 'forbidden')
    value = await body(request)
    decision = value.get('decision')
    if decision not in ('upheld', 'dismissed'):
        raise HTTPException(400, 'invalid_request')
    note = text(value, 'note')
    if not note.strip():
        raise HTTPException(400, 'reason_required')
    with closing(db.connect()) as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT * FROM content_reports WHERE id=?', (rid,)).fetchone()
        if not row:
            raise HTTPException(404, 'not_found')
        if row['status'] != 'open':
            return {'status': row['status']}
        if decision == 'upheld':
            if row['target_type'] == 'listing':
                c.execute("UPDATE listings SET status='moderation_hold',updated_at=? WHERE id=?",
                          (now_tokyo(), row['target_id']))
            else:
                c.execute("UPDATE messages SET body='[Content removed / 内容已移除 / 削除済み]' WHERE id=?",
                          (row['target_id'],))
        c.execute('UPDATE content_reports SET status=?,resolution=?,resolved_by=?,resolved_at=? WHERE id=?',
                  (decision, note, user['id'], now_tokyo(), rid))
        audit_log(c, user['id'], 'content_report_resolved', 'report', rid, decision)
        c.commit()
    return {'status': decision}


@router.post('/account/delete')
async def delete_account(request: Request):
    user = identity(request)
    sensitive_limit(request, user['id'])
    value = await body(request)
    require_password(user, value)
    if value.get('confirmation') != 'DELETE':
        raise HTTPException(400, 'delete_confirmation_required')
    uid = user['id']
    files = set()
    with closing(db.connect()) as c:
        c.execute('BEGIN IMMEDIATE')
        current = c.execute('SELECT * FROM users WHERE id=? AND is_active=1',(uid,)).fetchone()
        if not current or current['pw_hash'] != user['pw_hash']:
            raise HTTPException(401,'session_expired')
        if c.execute("SELECT 1 FROM ai_jobs WHERE user_id=? AND status IN ('queued','running')", (uid,)).fetchone():
            c.rollback()
            raise HTTPException(409, 'analysis_in_progress')
        files.update(r['filename'] for r in c.execute('SELECT i.filename FROM images i JOIN listings l '
                                                      'ON l.id=i.listing_id WHERE l.seller_id=?', (uid,)))
        for row in c.execute('SELECT photo,draft_json FROM oneclick_drafts WHERE user_id=?', (uid,)):
            if row['photo']:
                files.add(row['photo'])
            try:
                files.update(json.loads(row['draft_json'] or '{}').get('photos', []))
            except (ValueError, TypeError):
                pass
        # Only revoke files owned exclusively by this account.
        for row in c.execute('SELECT i.filename FROM images i JOIN listings l ON l.id=i.listing_id '
                             'WHERE l.seller_id IS NULL OR l.seller_id<>?', (uid,)):
            files.discard(row['filename'])
        for row in c.execute('SELECT photo,draft_json FROM oneclick_drafts WHERE user_id<>?', (uid,)):
            files.discard(row['photo'])
            try:
                files.difference_update(json.loads(row['draft_json'] or '{}').get('photos', []))
            except (ValueError, TypeError):
                pass
        for name in files:
            storage.name_only(name)
            c.execute('INSERT OR IGNORE INTO revoked_uploads(name) VALUES(?)', (name,))
            if storage.in_database():
                c.execute('DELETE FROM yuno_upload_chunks WHERE name=?', (name,))
                c.execute('DELETE FROM yuno_uploads WHERE name=?', (name,))
        c.execute('DELETE FROM images WHERE listing_id IN (SELECT id FROM listings WHERE seller_id=?)', (uid,))
        c.execute("UPDATE listings SET status='deleted',title_ja='削除済み',title_zh='已删除',"
                  "desc_ja='',desc_zh='',attrs_json='{}',inspection_record='' WHERE seller_id=?", (uid,))
        for table, field in [('sessions','user_id'),('account_recovery','user_id'),
                             ('oneclick_drafts','user_id'),('ai_jobs','user_id'),('listing_follows','user_id'),
                             ('draft_upload_requests','user_id')]:
            c.execute(f'DELETE FROM {table} WHERE {field}=?', (uid,))
        c.execute('DELETE FROM user_blocks WHERE user_id=? OR blocked_id=?', (uid, uid))
        c.execute("UPDATE messages SET body='[Account deleted / 账号已删除 / 退会済み]' WHERE sender_id=?", (uid,))
        c.execute("UPDATE reviews SET comment='' WHERE reviewer_id=?", (uid,))
        c.execute("UPDATE content_reports SET details='' WHERE reporter_id=?", (uid,))
        salt, pw_hash = hash_password(secrets.token_urlsafe(32))
        c.execute("UPDATE users SET email=?,display_name='Deleted account',phone='',region='',"
                  "salt=?,pw_hash=?,is_active=0 WHERE id=?",
                  (f'deleted-{uid}-{secrets.token_hex(12)}@invalid.example', salt, pw_hash, uid))
        audit_log(c, uid, 'account_deleted', 'user', uid, 'profile anonymized; transaction audit retained')
        c.commit()
    if not storage.in_database():
        for name in files:
            try:
                storage.delete(name)
            except OSError:
                # Revocation was committed atomically and denies public reads.
                pass
    return {'deleted': True, 'sessions_revoked': True, 'transaction_records_retained': True}
