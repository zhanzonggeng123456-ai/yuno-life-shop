import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:yuno_life/main.dart';
import 'package:yuno_life/labels.dart';

void main() {
  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    FlutterSecureStorage.setMockInitialValues({});
    session.preferences = await SharedPreferences.getInstance();
    await session.signOut(remote: false);
    session.language = 'zh';
    session.config = {'categories': [], 'regions': [], 'services': {}};
    session.client = MockClient((request) async => http.Response(
        jsonEncode({
          'items': [],
          'moves': {
            'up_count': 0,
            'down_count': 0,
            'flat_count': 0,
            'insufficient': 0,
            'gainers': [],
            'losers': []
          },
          'categories': [],
          'basis': {'zh': '真实订单', 'ja': '実取引'}
        }),
        200,
        headers: {'content-type': 'application/json'}));
  });
  testWidgets('five native destinations render at phone width without overflow',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(const MaterialApp(home: HomeShell()));
    await tester.pumpAndSettle();
    expect(find.byType(NavigationDestination), findsNWidgets(5));
    expect(find.byType(AppBar), findsNothing);
    expect(find.text('暂无记录'), findsOneWidget);
    await tester.tap(find.text('成交行情'));
    await tester.pumpAndSettle();
    expect(find.text('上涨 ▲'), findsOneWidget);
    expect(find.text('下跌 ▼'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.tap(find.text('订单'));
    await tester.pumpAndSettle();
    expect(find.text('登录查看'), findsOneWidget);
    await tester.tap(find.text('个人中心'));
    await tester.pumpAndSettle();
    expect(find.text('登录 / 注册'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  testWidgets(
      'login is a native password form and empty accounts are not prefilled',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(home: AuthPage()));
    final fields =
        tester.widgetList<TextField>(find.byType(TextField)).toList();
    expect(fields.length, 2);
    expect(fields[1].obscureText, isTrue);
    expect(fields.every((field) => field.controller!.text.isEmpty), isTrue);
    expect(find.byType(AppBar), findsNothing);
  });
  test('language changes persist and payment labels remain simulated',
      () async {
    await session.setLanguage('ja');
    expect(session.preferences!.getString('language'), 'ja');
    expect(status(session, 'paid'), '模擬決済済');
    await session.setLanguage('zh');
    expect(status(session, 'paid'), '已模拟支付');
  });
  test(
      'bearer session is only stored in secure storage, expires, and is never forwarded to a new host',
      () async {
    final requests = <http.Request>[];
    session.client = MockClient((request) async {
      requests.add(request);
      if (request.url.path.endsWith('/login')) {
        return http.Response(
            '{"access_token":"test-only-token","token_type":"bearer"}', 200);
      }
      if (request.url.path.endsWith('/me')) {
        return http.Response(
            '{"id":1,"display_name":"Test","role":"user"}', 200);
      }
      return http.Response('{"categories":[],"regions":[],"services":{}}', 200);
    });
    await session.authenticate(
        false, {'email': 'test@example.jp', 'password': 'test-only-password'});
    expect(await session.storage.read(key: 'session'), 'test-only-token');
    expect(session.preferences!.getKeys().contains('session'), isFalse);
    expect(requests.last.headers['Authorization'], 'Bearer test-only-token');
    await session.setServer('http://new-local-server:8000');
    expect(session.signedIn, isFalse);
    expect(await session.storage.read(key: 'session'), isNull);
    expect(requests.last.headers.containsKey('Authorization'), isFalse);
  });
}
