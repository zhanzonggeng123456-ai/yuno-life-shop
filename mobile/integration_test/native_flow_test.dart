import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:integration_test/integration_test.dart';
import 'package:image_picker_platform_interface/image_picker_platform_interface.dart';
import 'package:yuno_life/main.dart' as app;
import 'package:yuno_life/labels.dart' as copy;

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
    // IntegrationTest uses the real keyboard by default. enterText needs the
    // test input channel registered; otherwise Profile can silently send no text.
    // This validates form submission, not the physical iOS keyboard.
    binding.testTextInput.register();
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
      for (var i = 0; i < 40 && finder.evaluate().isEmpty; i++) {
        await tester.drag(find.byType(Scrollable).first, Offset(0, -delta));
        await settle();
      }
      expect(finder.evaluate().isNotEmpty, isTrue,
          reason: 'Requested control was not built after scrolling');
      await tester.ensureVisible(finder.first);
      await settle();
    }

    Future<void> tapText(String text, {double delta = 220}) async {
      final finder = find.text(text);
      await reveal(finder, delta: delta);
      await tester.tap(finder.last);
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
      expect(tester.widget<TextField>(field('邮箱')).controller!.text.isNotEmpty,
          isTrue,
          reason: 'Test email input was not delivered');
      expect(tester.widget<TextField>(field('密码')).controller!.text == secret,
          isTrue,
          reason: 'Test password input was not delivered');
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
      await reveal(find.byType(PopupMenuButton<String>), delta: -220);
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
      await reveal(find.byType(PopupMenuButton<String>), delta: -220);
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
      stage('publish_logout_languages_passed');

      // Fixtures use public JSON commands; all actions below use native forms.
      final stamp = DateTime.now().microsecondsSinceEpoch;
      final sellerResponse = await app.session.client.post(
        app.session.uri('/register'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'email': 'seller-$stamp@acceptance.invalid',
          'password': secret,
          'display_name': 'DEMO 验收卖家'
        }),
      );
      expect(sellerResponse.statusCode, 200);
      final sellerToken = jsonDecode(sellerResponse.body)['access_token'];
      Future<Map<String, dynamic>> sellerPost(String path, Map data) async {
        final response = await app.session.client.post(app.session.uri(path),
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer $sellerToken'
            },
            body: jsonEncode(data));
        expect(response.statusCode, 200,
            reason: 'Seller fixture command failed');
        return Map<String, dynamic>.from(jsonDecode(response.body));
      }

      Future<int> sellerListing(String title) async {
        final result = await sellerPost('/listings/new', {
          'category_slug': 'appliance',
          'title_ja': title,
          'title_zh': title,
          'price': 6000,
          'region': 'sakado'
        });
        return int.parse('${result['next']}'.split('/').last);
      }

      final fixedId = await sellerListing('DEMO native fixed');
      final offerId = await sellerListing('DEMO native offer');
      final auctionListingId = await sellerListing('DEMO native auction');
      final auctionResult =
          await sellerPost('/listings/$auctionListingId/auction', {
        'start_price': 1000,
        'buy_now_price': 6000,
        'ends_at': DateTime.now()
            .toUtc()
            .add(const Duration(hours: 1))
            .toIso8601String()
      });
      final auctionId = int.parse('${auctionResult['next']}'.split('/').last);
      await app.session.authenticate(true, {
        'email': 'buyer-$stamp@acceptance.invalid',
        'password': secret,
        'display_name': 'DEMO 验收买家'
      });
      Future<void> showDetail(String path) async {
        await tester.pumpWidget(MaterialApp(
            key: UniqueKey(), home: app.DetailPage(path: path, title: '验收详情')));
        await settle();
      }

      Future<void> command(String path, String ending,
          [Map<String, String> inputs = const {}]) async {
        final detail = await app.session.get(path);
        final action = (detail['actions'] as List)
            .firstWhere((a) => '${a['path']}'.endsWith(ending));
        await showDetail(path);
        await tapText(app.session.local(action['label']));
        for (final input in inputs.entries) {
          final control = field(copy.label(app.session, input.key));
          await reveal(control);
          await tester.enterText(control, input.value);
        }
        FocusManager.instance.primaryFocus?.unfocus();
        await settle();
        await tapText('确认提交');
      }

      await command('/listings/$fixedId', '/follow');
      expect(((await app.session.get('/me'))['following'] as List).length, 1);
      await showDetail('/listings/$fixedId');
      await tapText('联系卖家');
      await tester.enterText(
          field(copy.label(app.session, 'body')), 'DEMO 站内消息验收');
      FocusManager.instance.primaryFocus?.unfocus();
      await settle();
      await tapText('发送');
      final buyerId = app.session.me!['id'];
      expect(
          ((await app.session.get('/messages/$fixedId/$buyerId'))['items']
                  as List)
              .length,
          1);
      await command('/listings/$fixedId', '/buy');
      final orderId = (await app.session.get('/me'))['orders'][0]['id'];
      await command('/orders/$orderId', '/pay');
      expect((await app.session.get('/orders/$orderId'))['status'], 'paid');
      await command('/orders/$orderId', '/delivery-request');
      expect(((await app.session.get('/me'))['deliveries'] as List).length, 1);
      await command('/orders/$orderId', '/complete');
      expect(
          (await app.session.get('/orders/$orderId'))['status'], 'completed');
      await command('/orders/$orderId', '/review', {'comment': 'DEMO 原生评价'});
      stage('native_fixed_pay_delivery_complete_review_chat_follow');
      await command('/listings/$offerId', '/offer', {'amount': '5000'});
      final offer = (await app.session.get('/me'))['offers'][0]['id'];
      await sellerPost('/offers/$offer/counter', {'counter_amount': 5500});
      await command('/offers/$offer', '/accept-counter');
      expect((await app.session.get('/me'))['orders'][0]['goods_amount'], 5500);
      await command('/auctions/$auctionId', '/bid');
      expect(
          ((await app.session.get('/auctions/$auctionId'))['bids'] as List)
              .length,
          1);
      final ownResult = await app.session.post('/listings/new', {
        'category_slug': 'appliance',
        'title_ja': 'DEMO native buyback',
        'price': 5000,
        'region': 'sakado'
      });
      await command('${ownResult['next']}', '/buyback/new');
      expect(((await app.session.get('/me'))['buybacks'] as List).length, 1);
      for (final service in (app.session.config['services'] as Map).entries) {
        await tester.pumpWidget(MaterialApp(
            key: UniqueKey(), home: const Scaffold(body: app.TradePage())));
        await settle();
        final name = app.session.name(Map<String, dynamic>.from(service.value));
        await reveal(find.text(name));
        final tile =
            find.ancestor(of: find.text(name), matching: find.byType(ListTile));
        await tester.tap(
            find.descendant(of: tile, matching: find.byType(FilledButton)));
        await settle();
        await tapText('确认提交');
      }
      expect(
          ((await app.session.get('/me'))['service_orders'] as List).length, 3);
      expect(tester.takeException(), isNull);
      await app.session.signOut();
      stage('native_offer_auction_buyback_three_services');
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
      binding.testTextInput.unregister();
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
