import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:yuno_life/main.dart';

http.Response fixtureResponse(String body, int status) =>
    http.Response(body, status,
        headers: {'content-type': 'application/json; charset=utf-8'});

void main() {
  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    FlutterSecureStorage.setMockInitialValues({});
    await session.signOut(remote: false);
    session.language = 'zh';
  });
  testWidgets(
      'connection form recovers from invalid address without stale error',
      (tester) async {
    session.client = MockClient((_) async => fixtureResponse('{}', 200));
    var saved = false;
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: ConnectionForm(onSaved: () => saved = true))));
    await tester.enterText(find.byType(TextField), 'invalid');
    await tester.tap(find.text('连接'));
    await tester.pumpAndSettle();
    expect(find.textContaining('信息不符合要求'), findsOneWidget);
    await tester.enterText(find.byType(TextField), 'https://fixture.example');
    await tester.tap(find.text('连接'));
    await tester.pumpAndSettle();
    expect(saved, isTrue);
    expect(find.textContaining('信息不符合要求'), findsNothing);
    expect(tester.takeException(), isNull);
  });
  testWidgets('all four rules load in both languages', (tester) async {
    session.client = MockClient((_) async => fixtureResponse(
        jsonEncode({
          'items': [
            for (var i = 0; i < 4; i++) {'zh': '规则$i', 'ja': '規約$i'}
          ]
        }),
        200));
    for (final language in ['zh', 'ja']) {
      session.language = language;
      await tester.pumpWidget(
          MaterialApp(key: ValueKey(language), home: const RulesPage()));
      await tester.pumpAndSettle();
      for (var i = 0; i < 4; i++) {
        expect(
            find.text('${language == 'zh' ? '规则' : '規約'}$i'), findsOneWidget);
      }
      expect(tester.takeException(), isNull);
    }
  });
  testWidgets('support retains question on failure and accepts corrected retry',
      (tester) async {
    var calls = 0;
    session.client = MockClient((request) async {
      if (request.url.path.endsWith('/login')) {
        return fixtureResponse('{"access_token":"fixture"}', 200);
      }
      if (request.url.path.endsWith('/me')) {
        return fixtureResponse('{"id":1}', 200);
      }
      if (request.url.path.endsWith('/support')) {
        expect(jsonDecode(request.body)['question'], '模拟付款如何处理');
        calls++;
        return fixtureResponse(
            calls == 1 ? '[]' : '{"answer_zh":"付款为模拟，不产生扣款"}',
            calls == 1 ? 503 : 200);
      }
      return fixtureResponse('{}', 200);
    });
    await session.authenticate(false, {});
    await tester.pumpWidget(const MaterialApp(home: SupportPage()));
    await tester.enterText(find.byType(TextField), '模拟付款如何处理');
    await tester.tap(find.text('发送'));
    await tester.pumpAndSettle();
    expect(find.text('模拟付款如何处理'), findsOneWidget);
    await tester.tap(find.text('发送'));
    await tester.pumpAndSettle();
    expect(calls, 2);
    expect(find.text('付款为模拟，不产生扣款'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
