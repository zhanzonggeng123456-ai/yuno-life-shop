import 'package:flutter/material.dart';
import 'session.dart';
import 'labels.dart';

class TradeProgress extends StatelessWidget {
  final Session api;
  final String resource;
  final Json data;
  const TradeProgress(
      {super.key,
      required this.api,
      required this.resource,
      required this.data});
  @override
  Widget build(BuildContext context) {
    final state = '${data['status'] ?? ''}';
    final description = switch ((resource, state)) {
      ('orders', 'pending_payment') =>
        api.tr('订单已创建。买家可继续模拟支付，也可取消订单。', '注文を作成しました。購入者は模擬決済または取消を選べます。'),
      ('orders', 'paid') => api.tr('模拟支付已记录。接下来安排交付，买家收货后确认完成。',
          '模擬決済を記録しました。受け渡しを調整し、購入者が受取後に完了を確認します。'),
      ('orders', 'completed') => api.tr('本次交易流程已完成，可以评价；如有问题请从订单发起退款或争议。',
          '取引手続が完了しました。評価、または問題があれば注文から返金・紛争を申請できます。'),
      ('orders', 'cancelled') => api.tr(
          '订单已取消，无需继续支付。商品状态以商品详情为准。', '注文は取消済みです。決済は不要です。商品状況は詳細で確認してください。'),
      ('orders', 'refunded') =>
        api.tr('模拟退款已处理。退款与裁决记录可在下方查看。', '模擬返金は処理済みです。返金と判断の記録は下で確認できます。'),
      ('offers', 'pending') =>
        api.tr('议价已发送，等待卖家接受、拒绝或还价。', '価格交渉を送信しました。出品者の返答をお待ちください。'),
      ('offers', 'countered') =>
        api.tr('卖家已还价，由买家确认是否接受。', '出品者から再提案があります。購入者は内容を確認して承諾できます。'),
      ('offers', 'accepted') =>
        api.tr('议价已接受，请在交易记录中确认订单。', '交渉が成立しました。取引履歴で注文を確認してください。'),
      ('deliveries', 'requested') => api.tr(
          '配送预约已提交，等待工作人员接单。配送仍为模拟。', '配送予約を受け付けました。担当者の受注を待っています。配送は模擬です。'),
      ('deliveries', 'assigned') =>
        api.tr('已有配送员接单，下一步为模拟取货。', '配送担当が決まりました。次は模擬集荷です。'),
      ('deliveries', 'picked_up') =>
        api.tr('模拟取货已完成，等待交付。', '模擬集荷が完了しました。受け渡しを待っています。'),
      ('deliveries', 'delivered') =>
        api.tr('模拟交付已记录，请买家确认是否收到。', '模擬配達を記録しました。購入者は受取を確認してください。'),
      ('refunds', 'requested') || ('disputes', 'open') => api.tr(
          '申请已提交，等待运营人工处理。请保留相关记录。', '申請済みです。運営の手動確認をお待ちください。関連記録を保管してください。'),
      ('refunds', 'decided') ||
      ('disputes', 'decided') =>
        api.tr('运营已作出处理，请查看裁决结果和依据。', '運営が判断しました。結果と判断理由を確認してください。'),
      _ => api.tr(
          '当前状态如下；可用操作会根据你的身份和最新状态显示。', '現在の状況を表示しています。権限と最新状態に応じた操作が表示されます。'),
    };
    return Card(
        child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(status(api, state),
                    style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                Text(description),
                const SizedBox(height: 8),
                Text(api.tr('内测：不产生真实扣款或配送。', 'ベータ版：実際の請求・配送は発生しません。'),
                    style: const TextStyle(fontSize: 12)),
              ],
            )));
  }
}
