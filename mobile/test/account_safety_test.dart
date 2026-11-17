import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:yuno_life/account_safety.dart';
import 'package:yuno_life/main.dart' show session, StartupPanel;
import 'package:yuno_life/trade_status.dart';
import 'package:yuno_life/session.dart' show Session;

void main() {
  setUp(() {
    session.language = 'zh';
  });
  testWidgets('password recovery validates input before sending a write',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(home: ResetPasswordPage()));
    await tester.ensureVisible(find.text('重设密码'));
    await tester.tap(find.text('重设密码'));
    await tester.pumpAndSettle();
    expect(find.text('至少 8 位'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  testWidgets(
      'account deletion requires password, typed confirmation, and final dialog',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(home: DeleteAccountPage()));
    await tester.tap(find.widgetWithText(FilledButton, '删除账号'));
    await tester.pumpAndSettle();
    expect(find.text('请输入当前密码与 DELETE。'), findsOneWidget);
    expect(find.byType(AlertDialog), findsNothing);
    final fields = find.byType(TextField);
    await tester.enterText(fields.at(0), 'example-only');
    await tester.enterText(fields.at(1), 'DELETE');
    await tester.tap(find.widgetWithText(FilledButton, '删除账号'));
    await tester.pumpAndSettle();
    expect(find.text('永久删除此账号？'), findsOneWidget);
    await tester.tap(find.text('保留账号'));
    await tester.pumpAndSettle();
    expect(find.byType(AlertDialog), findsNothing);
    expect(tester.takeException(), isNull);
  });
  testWidgets(
      'cold start explains waiting after a delay and disposes its timer',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(home: StartupPanel()));
    await tester.pump(const Duration(seconds: 9));
    expect(find.textContaining('首次'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    expect(tester.takeException(), isNull);
  });
  testWidgets('trade instructions retain simulation language in both languages',
      (tester) async {
    final api = Session()..language = 'zh';
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: TradeProgress(
                api: api,
                resource: 'orders',
                data: const {'status': 'pending_payment'}))));
    expect(find.textContaining('买家可继续模拟支付'), findsOneWidget);
    api.language = 'ja';
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: TradeProgress(
                api: api,
                resource: 'orders',
                data: const {'status': 'paid'}))));
    expect(find.textContaining('模擬決済を記録'), findsOneWidget);
    expect(find.textContaining('実際の請求・配送は発生しません'), findsOneWidget);
    api.dispose();
  });
  testWidgets(
      'moderation shows the reported content and requires a decision reason',
      (tester) async {
    final original = session.client;
    final writes = <String>[];
    session.client = MockClient((request) async {
      if (request.method == 'POST') {
        writes.add(request.body);
        return http.Response('{"status":"upheld"}', 200);
      }
      return http.Response(
          jsonEncode({
            'items': [
              {
                'id': 1,
                'target_type': 'message',
                'target_id': 7,
                'reason': 'harassment',
                'details': 'Review this',
                'status': 'open',
                'reported_body': 'Reported content only'
              },
              {
                'id': 2,
                'target_type': 'listing',
                'target_id': 9,
                'reason': 'counterfeit',
                'details': '',
                'status': 'open',
                'reported_title_zh': '被举报商品示例'
              },
            ]
          }),
          200,
          headers: {'content-type': 'application/json; charset=utf-8'});
    });
    addTearDown(() => session.client = original);
    await tester.pumpWidget(const MaterialApp(home: ModerationPage()));
    await tester.pumpAndSettle();
    expect(
        find.byWidgetPredicate(
            (w) => w is SelectableText && w.data == 'Reported content only'),
        findsOneWidget);
    await tester.ensureVisible(find.text('成立并移除内容').first);
    await tester.tap(find.text('成立并移除内容').first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('确认处理'));
    await tester.pumpAndSettle();
    expect(writes, isEmpty);
    await tester.enterText(
        find.byType(TextField), 'Reviewed the reported content');
    await tester.tap(find.text('确认处理'));
    await tester.pumpAndSettle();
    expect(jsonDecode(writes.single),
        {'decision': 'upheld', 'note': 'Reviewed the reported content'});
    await tester.scrollUntilVisible(find.text('查看被举报商品'), 200,
        scrollable: find.byType(Scrollable).first);
    expect(find.text('查看被举报商品'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
