"""Read-only public marketplace totals. Demo orders never enter transaction data."""
from datetime import datetime, timedelta
from .market import TOKYO


def marketplace_overview(conn, price_for):
    now = datetime.now(TOKYO)
    rows = conn.execute("SELECT goods_amount,created_at FROM orders WHERE demo=0 AND status IN ('paid','completed')").fetchall()
    total = sum(r['goods_amount'] for r in rows)
    current, previous = [], []
    monday = now.date() - timedelta(days=now.weekday())
    starts = [monday - timedelta(weeks=i) for i in reversed(range(12))]
    buckets = {day: 0 for day in starts}
    for row in rows:
        try:
            created = datetime.fromisoformat(row['created_at'])
            if created.tzinfo is None:
                created = created.replace(tzinfo=TOKYO)
            created = created.astimezone(TOKYO)
        except (ValueError, TypeError):
            continue
        if now - timedelta(days=30) <= created <= now:
            current.append(row['goods_amount'])
        elif now - timedelta(days=60) <= created < now - timedelta(days=30):
            previous.append(row['goods_amount'])
        week = created.date() - timedelta(days=created.weekday())
        if week in buckets and created <= now:
            buckets[week] += row['goods_amount']
    active = conn.execute("SELECT * FROM listings WHERE demo=0 AND status='active'").fetchall()
    enough = len(current) >= 2 and len(previous) >= 2 and sum(previous) > 0
    return {
        'gmv': total,
        'orders': conn.execute('SELECT COUNT(*) FROM orders WHERE demo=0').fetchone()[0],
        'paid_orders': len(rows),
        'active_count': len(active),
        'active_asking_total': sum(price_for(row) for row in active),
        'recent_30_volume': sum(current),
        'previous_30_volume': sum(previous),
        'recent_30_count': len(current),
        'previous_30_count': len(previous),
        'change_pct': round((sum(current) / sum(previous) - 1) * 100, 1) if enough else None,
        'volume_curve': [{'week': day.isoformat(), 'volume': buckets[day]} for day in starts],
        'simulated': True,
    }
