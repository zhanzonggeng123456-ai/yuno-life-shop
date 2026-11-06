import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:image_picker_platform_interface/image_picker_platform_interface.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:shop/main.dart';
import 'package:shop/labels.dart';
import 'package:shop/api.dart';
import 'package:shop/editor.dart';
import 'package:shop/ui.dart';

void main() {
  testWidgets('An unrecognized category requires confirmation', (tester) async {
    appState.config = {
      'categories': [
        {'slug': 'appliance', 'name_zh': '家电', 'name_ja': '家電', 'attrs': []},
      ],
      'actions': [
        {
          'name': 'listing_create',
          'fields': [
            {
              'name': 'category_slug',
              'type': 'text',
              'required': true,
              'default': null,
            },
          ],
        },
      ],
    };
    await tester.pumpWidget(
      const MaterialApp(home: ActionForm(action: 'listing_create')),
    );
    await tester.pumpAndSettle();
    final field = tester.widget<DropdownButtonFormField<String>>(
      find.byType(DropdownButtonFormField<String>),
    );
    expect(field.initialValue, isNull);
    expect(tester.state<FormState>(find.byType(Form)).validate(), isFalse);
    appState.config = {};
  });
  test('Native draft uses the market interval midpoint and never a heuristic quote', () {
    expect(
      draftReferencePrice({'kind': 'market', 'low': 5000, 'high': 7500}),
      6250,
    );
    expect(
      draftReferencePrice({
        'kind': 'estimate_reference',
        'low': 1000,
        'high': 2000,
      }),
      isNull,
    );
    expect(draftReferencePrice({'kind': 'no_market_price'}), isNull);
  });
  test('Legacy listings fall back to their available title', () {
    appState.choice = 'zh';
    expect(itemName({'title_zh': '', 'title_ja': '中古本'}), '中古本');
    appState.choice = 'ja';
    expect(itemName({'title_zh': '二手书', 'title_ja': ''}), '二手书');
    appState.choice = 'system';
  });
  testWidgets(
    'Camera-first publishing skips Android-only recovery on other hosts',
    (tester) async {
      final previousPicker = ImagePickerPlatform.instance;
      final picker = CameraSpy();
      ImagePickerPlatform.instance = picker;
      addTearDown(() => ImagePickerPlatform.instance = previousPicker);
      appState.config = {
        'actions': [
          {
            'name': 'oneclick_upload',
            'fields': [
              {
                'name': 'name',
                'type': 'text',
                'required': true,
                'default': null,
              },
              {
                'name': 'photos',
                'type': 'photos',
                'multiple': true,
                'required': false,
                'default': null,
              },
            ],
          },
        ],
      };
      await tester.pumpWidget(
        const MaterialApp(home: ActionForm(action: 'oneclick_upload')),
      );
      await tester.pumpAndSettle();
      expect(picker.captures, 1);
      expect(picker.rearCamera, isTrue);
      expect(tester.takeException(), isNull);
      appState.config = {};
    },
  );
  testWidgets('Failed connection keeps the working server and account', (
    tester,
  ) async {
    SharedPreferences.setMockInitialValues({'server': 'http://127.0.0.1:1'});
    FlutterSecureStorage.setMockInitialValues({});
    await appState.initialize();
    appState.user = {'id': 1, 'display_name': 'UI 样本', 'role': 'user'};
    await expectLater(
      appState.connect('http://127.0.0.1:2'),
      throwsA(isA<ApiFailure>()),
    );
    expect(appState.server, 'http://127.0.0.1:1');
    expect(appState.user?['id'], 1);
    expect(appState.preferences.getString('server'), 'http://127.0.0.1:1');
    appState.user = null;
    appState.server = '';
  });
  testWidgets('Profile refreshes immediately when account state changes', (
    tester,
  ) async {
    SharedPreferences.setMockInitialValues({});
    appState.server = '';
    await appState.initialize();
    await appState.languageChoice('zh');
    appState.server = 'http://127.0.0.1:1';
    await tester.pumpWidget(const YunoApp());
    await tester.pumpAndSettle();
    await tester.tap(find.byIcon(Icons.person_outline));
    await tester.pumpAndSettle();
    expect(find.text('欢迎来到 YUNO'), findsOneWidget);
    appState.user = {'id': 1, 'display_name': 'UI 样本', 'role': 'user'};
    appState.changed();
    await tester.pumpAndSettle();
    expect(find.text('UI 样本'), findsOneWidget);
    expect(find.text('欢迎来到 YUNO'), findsNothing);
    appState.user = null;
    appState.server = '';
    appState.changed();
  });
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

class CameraSpy extends ImagePickerPlatform {
  int captures = 0;
  bool rearCamera = false;
  @override
  Future<XFile?> getImageFromSource({
    required ImageSource source,
    ImagePickerOptions options = const ImagePickerOptions(),
  }) async {
    captures++;
    rearCamera =
        source == ImageSource.camera &&
        options.preferredCameraDevice == CameraDevice.rear;
    return null;
  }
}
