import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:integration_test/integration_test.dart';
import 'package:image_picker_platform_interface/image_picker_platform_interface.dart';
import 'package:yuno_life/main.dart' as app;

// Test media gateway: verifies native UI and rear-camera intent, not camera hardware.
class FixturePicker extends ImagePickerPlatform {
  final XFile file;
  bool rearRequested = false;
  FixturePicker(this.file);
  @override
  Future<XFile?> getImageFromSource(
      {required ImageSource source,
      ImagePickerOptions options = const ImagePickerOptions()}) async {
    rearRequested = source == ImageSource.camera &&
        options.preferredCameraDevice == CameraDevice.rear;
    return file;
  }

  @override
  Future<List<XFile>> getMultiImageWithOptions(
          {MultiImagePickerOptions options =
              const MultiImagePickerOptions()}) async =>
      List.generate(min(options.limit ?? 9, 9), (_) => file);
}

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
      'live native registration, photo editing, AI, publishing, logout and languages',
      (tester) async {
    final preferences = await SharedPreferences.getInstance();
    final previousServer = preferences.getString('server');
    final previousLanguage = preferences.getString('language') ?? 'system';
    final dir = await Directory.systemTemp.createTemp('yuno-acceptance-');
    final photo = File('${dir.path}/sample.png');
    await photo.writeAsBytes(base64Decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGM4fvkgAATAAlwVeCj7AAAAAElFTkSuQmCC'));
    final picker = FixturePicker(XFile(photo.path));
    ImagePickerPlatform.instance = picker;
    Future<void> settle() => tester.pumpAndSettle(
        const Duration(milliseconds: 200),
        EnginePhase.sendSemanticsUpdate,
        const Duration(minutes: 2));
    Future<void> reveal(Finder finder, {double delta = 220}) async {
      if (finder.evaluate().isEmpty) {
        await tester.scrollUntilVisible(finder, delta,
            scrollable: find.byType(Scrollable).first, maxScrolls: 40);
      } else {
        await tester.ensureVisible(finder);
      }
      await settle();
    }

    Future<void> tapText(String text, {double delta = 220}) async {
      final finder = find.text(text).last;
      await reveal(finder, delta: delta);
      await tester.tap(finder);
      await settle();
    }

    Finder field(String name) => find.byWidgetPredicate(
        (w) => w is TextField && w.decoration?.labelText == name);
    void stage(String value) {
      debugPrint('ACCEPTANCE: $value');
      binding.reportData = {
        'stage': value,
        'platform': Platform.operatingSystem,
        'camera_hardware': 'not_tested'
      };
    }

    try {
      await preferences.remove('server');
      await app.session.signOut(remote: false);
      await tester.pumpWidget(const app.YunoApp());
      await settle();
      expect(find.byType(NavigationDestination), findsNWidgets(5));
      await app.session.setLanguage('zh');
      await settle();
      stage('boot');
      await tester.tap(find.byType(NavigationDestination).at(4));
      await settle();
      await tapText('登录 / 注册');
      await tapText('注册新账号');
      const alphabet =
          'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789';
      final secret = List.generate(
          24, (_) => alphabet[Random.secure().nextInt(alphabet.length)]).join();
      await tester.enterText(field('邮箱'),
          'phone-${DateTime.now().microsecondsSinceEpoch}@acceptance.invalid');
      await tester.enterText(field('密码'), secret);
      await tester.enterText(field('昵称'), '原生验收 DEMO');
      FocusManager.instance.primaryFocus?.unfocus();
      await settle();
      await tapText('注册');
      for (var i = 0; i < 50 && !app.session.signedIn; i++) {
        await Future<void>.delayed(const Duration(milliseconds: 200));
        await tester.pump();
      }
      expect(app.session.signedIn, isTrue,
          reason: 'Native registration did not establish a secure session');
      stage('registered');
      await tester.tap(find.byType(NavigationDestination).at(2));
      await settle();
      await tapText('发布闲置');
      expect(picker.rearRequested, isTrue);
      expect(find.text('封面'), findsOneWidget);
      await tapText('从相册选');
      await reveal(field('商品名称'));
      await tester.enterText(field('商品名称'), 'DEMO Panasonic 電子レンジ');
      FocusManager.instance.primaryFocus?.unfocus();
      await settle();
      await tapText('AI 一键识别 · 鉴定 · 估价');
      final own = await app.session.get('/me');
      final drafts = own['oneclick_drafts'] as List;
      expect(drafts, isNotEmpty);
      final did = drafts.first['id'];
      var draft = await app.session.get('/oneclick/$did');
      expect(draft['status'], 'recognized');
      expect((draft['photos'] as List).length, 10);
      stage('AI_ten_photos');
      final previousCover = draft['photos'][1]['url'];
      await reveal(find.byType(PopupMenuButton<String>).first, delta: -220);
      await tester.tap(find.byType(PopupMenuButton<String>).at(1));
      await settle();
      await tapText('设为封面');
      draft = await app.session.get('/oneclick/$did');
      expect(draft['photos'][0]['url'], previousCover);
      await tester.tap(find.byType(PopupMenuButton<String>).at(1));
      await settle();
      await tapText('删除');
      draft = await app.session.get('/oneclick/$did');
      expect((draft['photos'] as List).length, 9);
      await tapText('从相册选');
      draft = await app.session.get('/oneclick/$did');
      expect((draft['photos'] as List).length, 10);
      picker.rearRequested = false;
      await reveal(find.byType(PopupMenuButton<String>).first, delta: -220);
      await tester.tap(find.byType(PopupMenuButton<String>).first);
      await settle();
      await tapText('重拍');
      expect(picker.rearRequested, isTrue);
      await tester.tap(find.byType(PopupMenuButton<String>).first);
      await settle();
      await tapText('替换');
      draft = await app.session.get('/oneclick/$did');
      expect((draft['photos'] as List).length, 10);
      stage('cover_delete_add_retake_replace');
      await tapText('AI 一键识别 · 鉴定 · 估价');
      await reveal(find.text('此报价为AI根据现实数据做出的估价，用户可以根据自身另行填写'));
      await reveal(field('日文标题'));
      await tester.enterText(field('日文标题'), 'DEMO 原生验收 電子レンジ');
      await reveal(field('售价（日元，含税）'));
      await tester.enterText(field('售价（日元，含税）'), '5000');
      FocusManager.instance.primaryFocus?.unfocus();
      await settle();
      await tapText('确认上架');
      await tapText('确认上架');
      expect(find.text('已提交发布'), findsOneWidget);
      final account = await app.session.get('/me');
      final listing = (account['listings'] as List).first;
      expect((listing['photos'] as List).length, 10);
      expect(listing['price'], 5000);
      stage('published');
      await tester.tap(find.byTooltip('返回').last);
      await settle();
      await tester.tap(find.byType(NavigationDestination).at(4));
      await settle();
      await tapText('退出登录');
      expect(app.session.signedIn, isFalse);
      expect(await app.session.storage.read(key: 'session'), isNull);
      await tapText('日本語');
      expect(find.widgetWithText(NavigationDestination, '市場'), findsOneWidget);
      await tapText('中文');
      expect(find.widgetWithText(NavigationDestination, '市场'), findsOneWidget);
      expect(tester.takeException(), isNull);
      binding.reportData = {
        'stage': 'passed',
        'platform': Platform.operatingSystem,
        'listing_id': listing['id'],
        'draft_id': did,
        'photo_count': 10,
        'camera_hardware': 'not_tested'
      };
      debugPrint('ACCEPTANCE: passed');
    } finally {
      if (previousServer == null) {
        await preferences.remove('server');
      } else {
        await preferences.setString('server', previousServer);
      }
      await app.session.setLanguage(previousLanguage);
      await dir.delete(recursive: true);
    }
  }, timeout: const Timeout(Duration(minutes: 8)));
}
