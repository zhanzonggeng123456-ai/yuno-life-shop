"""Shared account and user-content protections for both native contracts."""
import unicodedata

from fastapi import HTTPException


def check_content(*parts):
    text = ''.join(unicodedata.normalize('NFKC', str(p)).casefold() for p in parts)
    text = ''.join(c for c in text if not c.isspace() and unicodedata.category(c) != 'Cf')
    # A small explicit safety filter, supplemented by reports and human review.
    # This is not a claim to classify every prohibited item or image.
    if any(term in text for term in ('毒品交易', '覚醒剤販売', '儿童色情', '児童ポルノ')):
        raise HTTPException(400, 'content_not_allowed')


def blocked(c, first, second):
    if first is None or second is None:
        return False
    return c.execute(
        'SELECT 1 FROM user_blocks WHERE (user_id=? AND blocked_id=?) '
        'OR (user_id=? AND blocked_id=?)', (first, second, second, first)).fetchone() is not None


def ensure_contact_allowed(c, first, second):
    other = c.execute('SELECT is_active FROM users WHERE id=?', (second,)).fetchone()
    if not other or not other['is_active']:
        raise HTTPException(409, 'account_unavailable')
    if blocked(c, first, second):
        raise HTTPException(409, 'user_blocked')
