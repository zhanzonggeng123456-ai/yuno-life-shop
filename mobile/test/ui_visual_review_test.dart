import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:yuno_life/main.dart';
import 'package:yuno_life/design.dart';

void main() {
  testWidgets('visual review of zero, large amounts and all primary pages',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.runAsync(() async {
      final loader = FontLoader('YunoSerif')
        ..addFont(rootBundle.load('assets/fonts/NotoSerifSC.ttf'));
      await loader.load();
      final bodyPath = Platform.environment['YUNO_UI_BODY_FONT'];
      if (bodyPath != null) {
        final body = FontLoader('Roboto')
          ..addFont(Future.value(
              ByteData.sublistView(await File(bodyPath).readAsBytes())));
        await body.load();
        await (FontLoader('MaterialIcons')
              ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf')))
            .load();
      }
    });
    var amount = 0;
    session.language = 'zh';
    session.config = {'categories': [], 'regions': [], 'services': {}};
    session.client = MockClient((r) async => http.Response(
        jsonEncode({
          'overview': {
            'gmv': amount,
            'orders': 0,
            'paid_orders': 0,
            'active_count': 0,
            'active_asking_total': 0,
            'volume_curve': []
          },
          'moves': {'gainers': [], 'losers': []},
          'categories': [],
          'items': [],
          'basis': {'zh': '按真实成交记录统计；数据不足时不生成排名。', 'ja': '実取引データに基づきます。'}
        }),
        200,
        headers: {'content-type': 'application/json'}));
    final boundary = GlobalKey();
    Future<void> mount() async {
      await tester.pumpWidget(RepaintBoundary(
          key: boundary,
          child: MaterialApp(
              key: UniqueKey(),
              debugShowCheckedModeBanner: false,
              theme: yunoTheme(),
              home: const HomeShell())));
      await tester.pumpAndSettle();
    }

    Future<void> capture(String name) async {
      expect(tester.takeException(), isNull);
      // Optional local review artifacts; fixtures are never production data.
      if (Platform.environment['YUNO_UI_PREVIEWS'] != '1') return;
      await tester.runAsync(() async {
        final image = await (boundary.currentContext!.findRenderObject()
                as RenderRepaintBoundary)
            .toImage(pixelRatio: 2);
        final data = await image.toByteData(format: ui.ImageByteFormat.png);
        final dir = Directory('../outputs/ui-review')
          ..createSync(recursive: true);
        await File('${dir.path}/$name.png')
            .writeAsBytes(data!.buffer.asUint8List());
        image.dispose();
      });
    }

    await mount();
    final money =
        tester.widget<Text>(find.byKey(const ValueKey('overview-amount')));
    expect(money.data, '¥0');
    expect(tester.getSize(find.byKey(const ValueKey('overview-amount'))).height,
        lessThan(45),
        reason: 'Amount should not inherit loose body leading');
    await capture('market-zero');
    for (final index in [1, 3, 4]) {
      await tester.tap(find.byType(NavigationDestination).at(index));
      await tester.pumpAndSettle();
      await capture('page-$index');
    }
    await tester.tap(find.byType(NavigationDestination).at(2));
    await tester.pumpAndSettle();
    await capture('trade-menu');
    amount = 123456789;
    await mount();
    await capture('market-large');
    expect(find.text('¥123,456,789'), findsOneWidget);
  });
}
