"""Loopback-only physical-device fixture server; never deploy this script.

Uses a NEW isolated database, current business/API code, libSQL driver and
database-backed photos. Fixture operations are reachable only through the
operator's own localhost/ADB tunnel, not the public production gateway.
"""
import argparse
from contextlib import closing
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--port', type=int, default=18765)
    args = parser.parse_args()
    root = args.data_dir.resolve()
    if (not (root / '.yuno-device-qa').is_file() or (root / 'device.db').exists()
            or os.environ.get('TURSO_DATABASE_URL') or os.environ.get('TURSO_AUTH_TOKEN')
            or args.port not in range(18765, 18770)):
        raise SystemExit('Refuse nonempty/unmarked storage, cloud credentials or unrelated port')
    os.environ.update(YUNO_DB_PATH=str(root / 'device.db'),
                      YUNO_UPLOAD_DIR=str(root / 'uploads'),
                      YUNO_PHOTO_STORAGE='database', YUNO_DB_DRIVER='libsql')
    from fastapi import FastAPI, HTTPException
    from app import db
    from deploy.gateway import app as native
    fixture = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @fixture.post('/__device_qa/promote/{uid}')
    def promote(uid: int):
        with closing(db.connect()) as conn:
            user = conn.execute('SELECT email FROM users WHERE id=?', (uid,)).fetchone()
            if not user or not user[0].endswith('@example.jp'):
                raise HTTPException(403)
            conn.execute("UPDATE users SET role='admin' WHERE id=?", (uid,))
            conn.commit()
        return {'fixture': True}

    @fixture.post('/__device_qa/expire-auction/{aid}')
    def expire(aid: int):
        past = (datetime.now(timezone(timedelta(hours=9))) - timedelta(minutes=1)).isoformat(timespec='seconds')
        with closing(db.connect()) as conn:
            conn.execute('UPDATE auctions SET ends_at=? WHERE id=?', (past, aid))
            conn.commit()
        return {'fixture': True}

    if args.port != 18765:
        @fixture.post('/__device_qa/market-history/{seller_id}/{buyer_id}')
        def market_history(seller_id: int, buyer_id: int):
            """Insert synthetic history so both market boards can be checked."""
            samples = {
                'QA 涨幅第一': (10000, 15000),
                'QA 涨幅第二': (10000, 12000),
                'QA 跌幅第一': (10000, 5000),
                'QA 跌幅第二': (20000, 15000),
                'QA 单一成交': (9000,),
            }
            with closing(db.connect()) as conn:
                category = conn.execute(
                    "SELECT id FROM categories WHERE slug='appliance'"
                ).fetchone()[0]
                for title, amounts in samples.items():
                    lid = conn.execute(
                        'INSERT INTO listings(seller_id,category_id,title_ja,title_zh,price,'
                        'created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
                        (seller_id, category, title, title, 77777,
                         '2026-10-01T00:00:00+09:00', '2026-10-01T00:00:00+09:00'),
                    ).lastrowid
                    for day, amount in enumerate(amounts, start=1):
                        when = f'2026-10-{day:02}T00:00:00+09:00'
                        conn.execute(
                            'INSERT INTO orders(buyer_id,seller_id,listing_id,goods_amount,'
                            'commission,total,status,created_at,updated_at) '
                            'VALUES(?,?,?,?,?,?,?,?,?)',
                            (buyer_id, seller_id, lid, amount, 0, amount,
                             'completed', when, when),
                        )
                conn.commit()
            return {'fixture': True}

    fixture.mount('/', native)
    import uvicorn
    uvicorn.run(fixture, host='127.0.0.1', port=args.port, workers=1, access_log=False)


if __name__ == '__main__':
    main()
