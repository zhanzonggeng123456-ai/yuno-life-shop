import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:shop/main.dart';
import 'package:shop/labels.dart';

void main() {
  testWidgets(
    'Five destinations and setup fit a narrow phone in both languages',
    (tester) async {
      SharedPreferences.setMockInitialValues({});
      await appState.initialize();
      tester.view.physicalSize = const Size(360, 800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(const YunoApp());
      await tester.pumpAndSettle();
      expect(find.byType(NavigationDestination), findsNWidgets(5));
      expect(find.text('YUNO LIFE SHOP'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await appState.languageChoice('zh');
      await tester.pumpAndSettle();
      expect(find.text('成交行情'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await appState.languageChoice('ja');
      await tester.pumpAndSettle();
      expect(find.text('取引相場'), findsOneWidget);
      expect(tester.takeException(), isNull);
      expect(label('order_pay'), contains('模擬'));
    },
  );
}
