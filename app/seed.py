"""演示数据种子脚本。明确标注 DEMO,可一键重置。
用法:先设置三个演示账号的口令环境变量,再运行:
  YUNO_SEED_ADMIN_PASSWORD=... YUNO_SEED_SELLER_PASSWORD=... \
  YUNO_SEED_BUYER_PASSWORD=... python -m app.seed [--reset]
演示口令不写进代码:未设置环境变量时直接报错退出,绝不用默认口令。
演示成交绝不伪装成真实行情:演示商品 demo=1,演示订单 demo=1,
且不在首页行情位置出现(本阶段根本不展示行情)。
"""
import argparse
import os
import sys

from . import db as d
from .security import hash_password, now_tokyo


def create_user(conn, email, name, role, password):
    salt, h = hash_password(password)
    cur = conn.execute(
        "INSERT OR IGNORE INTO users(email,pw_hash,salt,display_name,role,created_at)"
        " VALUES(?,?,?,?,?,?)", (email, h, salt, name, role, now_tokyo()))
    conn.commit()
    row = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    return row["id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true",
                    help="清空演示数据(demo=1 的商品/订单)并重建")
    args = ap.parse_args()
    admin_pw = os.environ.get("YUNO_SEED_ADMIN_PASSWORD")
    seller_pw = os.environ.get("YUNO_SEED_SELLER_PASSWORD")
    buyer_pw = os.environ.get("YUNO_SEED_BUYER_PASSWORD")
    missing = [k for k, v in (
        ("YUNO_SEED_ADMIN_PASSWORD", admin_pw),
        ("YUNO_SEED_SELLER_PASSWORD", seller_pw),
        ("YUNO_SEED_BUYER_PASSWORD", buyer_pw)) if not v]
    if missing:
        print("seed 拒绝运行:未设置 " + ", ".join(missing)
              + "。演示口令必须用环境变量传入,不设默认口令。")
        return 2
    d.init_db()
    conn = d.connect()
    try:
        if args.reset:
            conn.execute("DELETE FROM listings WHERE demo=1")
            conn.execute("DELETE FROM orders WHERE demo=1")
            conn.commit()
        admin_id = create_user(conn, "admin@yuno.local", "管理员", "admin", admin_pw)
        seller_id = create_user(conn, "seller@example.jp", "坂户卖家", "user", seller_pw)
        buyer_id = create_user(conn, "buyer@example.jp", "坂户买家", "user", buyer_pw)
        cat = d.category_by_slug(conn, "appliance")
        conn.execute(
            "INSERT INTO listings(seller_id,category_id,title_ja,title_zh,desc_ja,"
            "desc_zh,price,condition_grade,attrs_json,region,size_class,weight_kg,"
            "demo,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (seller_id, cat["id"], "中古 電子レンジ(良好)", "二手微波炉(良好)",
             "動作確認済みの中古電子レンジです。", "已确认可正常工作的二手微波炉。",
             6000, "good", '{"brand": "Panasonic"}', "sakado", "M", 12, 1,
             now_tokyo(), now_tokyo()))
        conn.commit()
        print(f"seed ok: admin_id={admin_id} seller_id={seller_id} buyer_id={buyer_id}")
        print("演示账号: admin@yuno.local / seller@example.jp / buyer@example.jp"
              "(口令来自环境变量,部署后请立即修改)")
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
