"""支付服务商接入层(第二阶段:接口层,非真实收款)。
MockProvider:本地模拟,明确标注模拟,只写payment_intents表,绝不宣称为真实收款。
LicensedProvider:持牌服务商占位,未配置商户信息时一律拒绝,防止把模拟当真实。
切换方式:YUNO_PAYMENT_PROVIDER=licensed + YUNO_PAYMENT_API_KEY,且必须先完成商户签约,
否则保持模拟。用户在外部唯一必须办理的事项:与日本持牌支付服务商签约开户,取得商户号
与API密钥,配置回调地址并完成分账/退款报备。本软件不代注册、不代签约、不收钱。
"""
import os
import secrets

from .security import now_tokyo


class PaymentError(Exception):
    pass


def payout_split(goods_amount, commission, delivery_fee):
    return {
        "seller_receivable": max(0, goods_amount - commission),
        "commission_amount": commission,
        "delivery_amount": delivery_fee or 0,
        "total_collected": goods_amount + (delivery_fee or 0),
    }


class MockProvider:
    name = "mock"

    def create_intent(self, conn, order, idempotency_key):
        split = payout_split(order["goods_amount"], order["commission"],
                             order["delivery_fee"])
        ref = "MOCK-" + secrets.token_hex(8)
        conn.execute(
            "INSERT OR IGNORE INTO payment_intents(order_id,provider,intent_ref,"
            "seller_receivable,commission_amount,delivery_amount,status,"
            "idempotency_key,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (order["id"], "mock", ref, split["seller_receivable"],
             split["commission_amount"], split["delivery_amount"], "simulated",
             idempotency_key, now_tokyo()))
        return {"provider": "mock", "intent_ref": ref, "simulated": True,
                "split": split}

    def refund(self, conn, order, amount):
        return {"provider": "mock", "simulated": True, "refunded": amount,
                "note": "模拟退款,非真实资金退回"}


class LicensedProvider:
    name = "licensed"

    def _check(self):
        if os.environ.get("YUNO_PAYMENT_PROVIDER") != "licensed":
            raise PaymentError("licensed provider not enabled")
        if not os.environ.get("YUNO_PAYMENT_API_KEY"):
            raise PaymentError("licensed provider API key not configured; "
                               "complete merchant onboarding first (docs/PENDING.md)")
        raise PaymentError("licensed provider adapter not implemented for a "
                           "specific PSP; implement the PSP adapter before "
                           "enabling live payments")

    def create_intent(self, conn, order, idempotency_key):
        self._check()

    def refund(self, conn, order, amount):
        self._check()


def get_provider():
    if os.environ.get("YUNO_PAYMENT_PROVIDER") == "licensed":
        return LicensedProvider()
    return MockProvider()
