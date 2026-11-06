import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:yuno_life/main.dart';
import 'package:yuno_life/labels.dart';
import 'package:yuno_life/design.dart';
import 'package:yuno_life/market_home.dart';

void main() {
  testWidgets(
      'retry and command reload replace futures without setState assertions',
      (tester) async {
    var calls = 0;
    late VoidCallback reload;
    await tester.pumpWidget(MaterialApp(
        home: LoadView(
      load: () async {
        calls++;
        if (calls == 1) throw Exception('offline');
        return {'count': calls};
      },
      builder: (context, data, callback) {
        reload = callback;
        return TextButton(
            onPressed: callback, child: Text('count ${data['count']}'));
      },
    )));
    await tester.pumpAndSettle();
    await tester.tap(find.text('重试'));
    await tester.pumpAndSettle();
    expect(find.text('count 2'), findsOneWidget);
    await tester.tap(find.text('count 2'));
    await tester.pumpAndSettle();
    expect(find.text('count 3'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    reload();
    expect(calls, 3);
    expect(tester.takeException(), isNull);
  });
  testWidgets('market retry replaces a failed load without setState assertions',
      (tester) async {
    var markets = 0;
    session.client = MockClient((request) async {
      if (request.url.path.endsWith('/market') && ++markets == 1) {
        return http.Response('{"error":"offline"}', 503);
      }
      return http.Response(
          '{"items":[],"moves":{},"categories":[],"basis":{}}', 200,
          headers: {'content-type': 'application/json'});
    });
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: MarketHome(
                api: session,
                onTrends: () {},
                onBrowse: () {},
                onPublish: () {},
                onListing: (_) {},
                onAuction: (_) {},
                card: (_) => const SizedBox(),
                onFavorite: (_) async {}))));
    await tester.pumpAndSettle();
    await tester.tap(find.text('连接失败，重试'));
    await tester.pumpAndSettle();
    expect(markets, 2);
    expect(find.text('平台总成交额（模拟支付）· 坂户市'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
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
  testWidgets('narrow phone with enlarged text keeps primary pages usable',
      (tester) async {
    tester.view.physicalSize = const Size(320, 700);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    for (final language in ['zh', 'ja']) {
      session.language = language;
      await tester.pumpWidget(MaterialApp(
        key: ValueKey(language),
        theme: yunoTheme(),
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context)
              .copyWith(textScaler: TextScaler.linear(1.5)),
          child: child!,
        ),
        home: const HomeShell(),
      ));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      for (final index in [1, 3, 4]) {
        await tester.tap(find.byType(NavigationDestination).at(index));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
      }
      await tester.tap(find.byType(NavigationDestination).at(2));
      await tester.pumpAndSettle();
      expect(find.byType(TradeMenu), findsOneWidget);
      expect(tester.takeException(), isNull);
    }
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
    expect(find.text('商品行情'), findsOneWidget);
    await tester.tap(find.text('成交行情'));
    await tester.pumpAndSettle();
    expect(find.text('涨幅榜'), findsOneWidget);
    expect(find.text('跌幅榜'), findsOneWidget);
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
      'current reference home has overview and working stock/rank switch',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    session.client = MockClient((r) async => http.Response(
        jsonEncode(r.url.path.endsWith('/market')
            ? {
                'overview': {
                  'gmv': 12000,
                  'orders': 2,
                  'paid_orders': 2,
                  'active_count': 1,
                  'active_asking_total': 6000,
                  'change_pct': null,
                  'volume_curve': []
                },
                'moves': {'gainers': [], 'losers': []},
                'categories': [],
              }
            : {
                'items': r.url.path.endsWith('/listings')
                    ? [
                        {
                          'id': 1,
                          'title_zh': '测试在售相机',
                          'price': 6000,
                          'photos': []
                        }
                      ]
                    : []
              }),
        200,
        headers: {'content-type': 'application/json'}));
    await tester
        .pumpWidget(MaterialApp(theme: yunoTheme(), home: const HomeShell()));
    await tester.pumpAndSettle();
    expect(find.byType(MarketHome), findsOneWidget);
    expect(find.text('¥12,000'), findsOneWidget);
    expect(find.text('商品行情'), findsOneWidget);
    await tester.ensureVisible(find.text('现货'));
    await tester.tap(find.text('现货'));
    await tester.pumpAndSettle();
    expect(find.text('测试在售相机'), findsWidgets);
    await tester.scrollUntilVisible(find.text('看完整行情 →'), -180,
        scrollable: find.byType(Scrollable).first);
    await tester.tap(find.text('看完整行情 →'));
    await tester.pumpAndSettle();
    expect(find.byType(TrendsPage), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  testWidgets(
      'two-column market cards fit long bilingual titles on a narrow screen',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    session.client = MockClient((request) async => http.Response(
        jsonEncode({
          'items': List.generate(
              2,
              (i) => {
                    'id': i + 1,
                    'title_zh': '保存良好的家用二手微波炉，附使用说明与配件',
                    'title_ja': '説明書と付属品付きの状態の良い中古電子レンジ',
                    'price': 6000,
                    'condition_grade': 'good',
                    'photos': [],
                    'demo': 1,
                  })
        }),
        200,
        headers: {'content-type': 'application/json'}));
    for (final language in ['zh', 'ja']) {
      session.language = language;
      await tester.pumpWidget(MaterialApp(
          key: ValueKey(language),
          theme: yunoTheme(),
          home: const Scaffold(body: MarketPage())));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(find.byType(ListingCard).first, 180,
          scrollable: find.byType(Scrollable).first);
      await tester.pumpAndSettle();
      expect(find.byType(ListingCard), findsNWidgets(2));
      final cards = find.byType(ListingCard);
      expect(tester.getSize(cards.first).width, lessThan(190));
      expect(
          tester.getTopLeft(cards.first).dy, tester.getTopLeft(cards.last).dy);
      expect(tester.takeException(), isNull);
    }
  });
  testWidgets('reference search and wrapping category chips send real filters',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final requests = <Uri>[];
    session.config['categories'] = [
      {'slug': 'watch', 'name_zh': '手表', 'name_ja': '時計'},
      {'slug': 'camera', 'name_zh': '相机', 'name_ja': 'カメラ'},
    ];
    session.client = MockClient((request) async {
      requests.add(request.url);
      return http.Response('{"items":[]}', 200);
    });
    await tester.pumpWidget(MaterialApp(
        theme: yunoTheme(), home: const Scaffold(body: MarketPage())));
    await tester.pumpAndSettle();
    expect(find.byType(TextField), findsOneWidget);
    await tester.enterText(find.byType(TextField).first, 'Sony');
    await tester.tap(find.text('搜索'));
    await tester.pumpAndSettle();
    expect(requests.last.queryParameters['q'], 'Sony');
    await tester.tap(find.text('相机'));
    await tester.pumpAndSettle();
    expect(requests.last.queryParameters['category'], 'camera');
    expect(requests.last.queryParameters['q'], 'Sony');
    expect(tester.takeException(), isNull);
  });
  testWidgets('raised trade menu preserves market and routes to services',
      (tester) async {
    await tester
        .pumpWidget(MaterialApp(theme: yunoTheme(), home: const HomeShell()));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(NavigationDestination).at(2));
    await tester.pumpAndSettle();
    expect(find.byType(TradeMenu), findsOneWidget);
    expect(find.text('发布闲置'), findsOneWidget);
    expect(find.text('发布拍卖'), findsOneWidget);
    expect(
        tester.widget<NavigationBar>(find.byType(NavigationBar)).selectedIndex,
        0);
    await tester.tap(find.text('增值服务'));
    await tester.pumpAndSettle();
    expect(find.byType(TradePage), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  testWidgets('order filters and personal favorites use account data',
      (tester) async {
    final favorite = {
      'id': 9,
      'title_zh': '收藏的相机',
      'price': 12000,
      'photos': [],
      'condition_grade': 'good'
    };
    session.client = MockClient((r) async {
      final data = switch (r.url.path.split('/').last) {
        'login' => {'access_token': 'widget-test-only-token'},
        'me' => {
            'id': 1,
            'display_name': 'Test',
            'following': [favorite]
          },
        'orders' => {
            'items': [
              {
                'id': 1,
                'status': 'pending_payment',
                'total': 12000,
                'listing': {'title_zh': '待支付相机', 'photos': []}
              },
              {
                'id': 2,
                'status': 'completed',
                'total': 5000,
                'listing': {'title_zh': '已完成手表', 'photos': []}
              },
            ]
          },
        _ => {'items': []},
      };
      return http.Response(jsonEncode(data), 200,
          headers: {'content-type': 'application/json'});
    });
    await session.authenticate(false, {});
    await tester
        .pumpWidget(MaterialApp(theme: yunoTheme(), home: const HomeShell()));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(NavigationDestination).at(3));
    await tester.pumpAndSettle();
    expect(find.text('待支付相机'), findsOneWidget);
    expect(find.text('已完成手表'), findsOneWidget);
    await tester.tap(find.widgetWithText(ChoiceChip, '待模拟支付'));
    await tester.pumpAndSettle();
    expect(find.text('待支付相机'), findsOneWidget);
    expect(find.text('已完成手表'), findsNothing);
    await tester.tap(find.byType(NavigationDestination).at(4));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(ListTile, '我的收藏'));
    await tester.pumpAndSettle();
    expect(find.text('收藏的相机'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  testWidgets('header language changes all five destination labels immediately',
      (tester) async {
    SharedPreferences.setMockInitialValues({'language': 'zh'});
    session.client = MockClient((r) async => http.Response(
        jsonEncode(
            {'categories': [], 'regions': [], 'services': {}, 'items': []}),
        200,
        headers: {'content-type': 'application/json'}));
    await tester.pumpWidget(const YunoApp());
    await tester.pumpAndSettle();
    expect(find.text('市场'), findsOneWidget);
    await tester.tap(find.byType(NavigationDestination).at(4));
    await tester.pumpAndSettle();
    final japanese = find.widgetWithText(ChoiceChip, '日本語');
    await tester.scrollUntilVisible(japanese, 250);
    await tester.ensureVisible(japanese);
    await tester.pumpAndSettle();
    await tester.tap(japanese);
    await tester.pumpAndSettle();
    expect(find.text('市場'), findsOneWidget);
    expect(find.text('市场'), findsNothing);
    expect(find.widgetWithText(NavigationDestination, 'マイページ'), findsOneWidget);
    expect(session.preferences!.getString('language'), 'ja');
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
