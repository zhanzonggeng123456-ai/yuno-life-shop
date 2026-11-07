import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker_platform_interface/image_picker_platform_interface.dart';
import 'package:integration_test/integration_test.dart';
import 'package:shop/main.dart' as shop;
import 'package:shop/api.dart';
import 'package:shop/editor.dart';
import 'package:shop/screens.dart';
import 'package:shop/labels.dart';

class FixturePicker extends ImagePickerPlatform {
  final List<XFile> files;
  int singles = 0;
  bool rear = false;
  List<XFile> selection = [];
  FixturePicker(this.files);
  @override
  Future<LostDataResponse> getLostData() async => LostDataResponse();
  @override
  Future<XFile?> getImageFromSource({
    required ImageSource source,
    ImagePickerOptions options = const ImagePickerOptions(),
  }) async {
    rear =
        source == ImageSource.camera &&
        options.preferredCameraDevice == CameraDevice.rear;
    return files[(singles++) % files.length];
  }

  @override
  Future<List<XFile>> getMultiImageWithOptions({
    MultiImagePickerOptions options = const MultiImagePickerOptions(),
  }) async => selection;
}

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  registerNativeTradingTest(
    name: 'Physical Android native forms and full trading lifecycles',
    startServer: () async => const String.fromEnvironment('YUNO_SERVER'),
    hardware: true,
    report: (data) => binding.reportData = data,
  );
}

void registerNativeTradingTest({
  required String name,
  required Future<String> Function() startServer,
  required bool hardware,
  required void Function(Json) report,
}) {
  final app = shop.appState;
  final passed = <String>[];
  final random = Random.secure();
  String randomText() =>
      List.generate(24, (_) => random.nextInt(36).toRadixString(36)).join();
  void record(String name) {
    passed.add(name);
    debugPrint('YUNO DEVICE PASS: $name');
  }

  testWidgets(name, (tester) async {
    final address = Uri.parse(await startServer());
    expect(address.scheme, 'http');
    expect(address.host, '127.0.0.1');
    expect(address.port, inInclusiveRange(18765, 18769));
    await app.initialize();
    await app.connect(address.toString());
    await app.languageChoice('zh');
    await tester.pumpWidget(const shop.YunoApp());
    Future<void> settle() async {
      if (hardware) {
        for (var i = 0; i < 12; i++) {
          await tester.pump(const Duration(milliseconds: 100));
        }
      } else {
        await tester.pumpAndSettle(
          const Duration(milliseconds: 18),
          EnginePhase.sendSemanticsUpdate,
          const Duration(seconds: 15),
        );
      }
      expect(tester.takeException(), isNull);
    }

    await settle();
    final nav = tester.state<NavigatorState>(find.byType(Navigator).first);
    Future<void> root() async {
      nav.popUntil((route) => route.isFirst);
      await settle();
    }

    Future<void> reveal(Finder finder) async {
      final scroll = find.byType(Scrollable).first;
      tester.state<ScrollableState>(scroll).position.jumpTo(0);
      await tester.pump();
      await tester.scrollUntilVisible(
        finder,
        320,
        scrollable: scroll,
        maxScrolls: 100,
        duration: const Duration(milliseconds: 100),
      );
      await tester.ensureVisible(finder);
      await tester.pump();
    }

    Future<void> enter(String key, String value) async {
      final dropdown = find.byKey(ValueKey('${app.language}:$key'));
      await reveal(
        find.byWidgetPredicate(
          (widget) =>
              widget.key == ValueKey('${app.language}:$key') ||
              (widget is TextField &&
                  widget.decoration?.labelText == label(key)),
        ),
      );
      if (dropdown.evaluate().isNotEmpty) {
        await reveal(dropdown);
        await tester.tap(dropdown);
        await settle();
        String text = label(value);
        if (key == 'rating') text = '$value ★';
        if (key == 'category_slug') {
          text = (app.config['categories'] as List).firstWhere(
            (c) => c['slug'] == value,
          )['name_${app.language}'];
        }
        await tester.tap(find.text(text).last);
        await settle();
        return;
      }
      final field = find.byWidgetPredicate(
        (widget) =>
            widget is TextField && widget.decoration?.labelText == label(key),
      );
      await reveal(field);
      final input = tester.widget<TextField>(field);
      if (input.readOnly &&
          ['ends_at', 'pickup_at', 'scheduled_at'].contains(key)) {
        await tester.tap(field);
        await settle();
        expect(find.byType(DatePickerDialog), findsOneWidget);
        final next = find.descendant(
          of: find.byType(DatePickerDialog),
          matching: find.byIcon(Icons.chevron_right),
        );
        await tester.tap(next);
        await settle();
        await tester.tap(find.text('15').last);
        await tester.tap(find.byType(TextButton).last);
        await settle();
        expect(find.byType(TimePickerDialog), findsOneWidget);
        await tester.tap(find.byType(TextButton).last);
        await settle();
        return;
      }
      // Vivo IME sends late updates under instrumentation; native keyboard is
      // independently exercised in the real hardware phase below.
      input.controller!.value = TextEditingValue(
        text: value,
        selection: TextSelection.collapsed(offset: value.length),
      );
      await tester.pump();
    }

    Future<Json> form(String action, Json context, Json fields) async {
      await root();
      Json? result;
      nav
          .push<Json>(
            MaterialPageRoute(
              builder: (_) => ActionForm(action: action, values: context),
            ),
          )
          .then((value) => result = value);
      await settle();
      for (final entry in fields.entries) {
        await enter(entry.key, entry.value.toString());
      }
      final button = find.widgetWithText(FilledButton, label(action));
      await reveal(button);
      if (!hardware) {
        final clickable = button.hitTestable();
        for (var i = 0; i < 30 && clickable.evaluate().isEmpty; i++) {
          await tester.pump(const Duration(milliseconds: 30));
        }
        expect(clickable, findsOneWidget, reason: 'Submit button for $action');
      }
      await tester.tap(button);
      for (var i = 0; i < 300 && result == null; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      if (result == null) {
        final errors = tester
            .widgetList<Text>(find.byType(Text))
            .map((t) => t.data ?? '')
            .where(
              (text) =>
                  text.contains('失败') ||
                  text.contains('错误') ||
                  text.contains('请') ||
                  text.contains('不可'),
            )
            .toList();
        fail('Native form did not complete: $action; visible errors=$errors');
      }
      await settle();
      return result!;
    }

    Future<Json> item(String resource, int id) async =>
        (await app.get('$resource/$id'))['item'] as Json;
    Future<void> screen(String resource, int id, String? action) async {
      await root();
      nav.push(
        MaterialPageRoute(
          builder: (_) => DetailPage(resource: resource, id: id),
        ),
      );
      await settle();
      if (action != null) {
        final button = find.widgetWithText(FilledButton, label(action));
        await reveal(button);
        expect(button, findsWidgets);
      }
    }

    Future<void> signIn(String email, String password) async {
      await form('login', {}, {'email': email, 'password': password});
      expect(app.user?['email'], email);
    }

    Future<int> listing(String title) async =>
        (await form('listing_create', {}, {
              'category_slug': 'appliance',
              'title_ja': title,
              'title_zh': title,
              'price': '4000',
            }))['id']
            as int;
    Future<void> fixture(String path) async {
      final response = await http.post(
        Uri.parse('${app.server}/__device_qa/$path'),
      );
      expect(response.statusCode, 200);
    }

    final seller = '${randomText()}@example.jp', sellerPassword = randomText();
    final buyer = '${randomText()}@example.jp', buyerPassword = randomText();
    final operator = '${randomText()}@example.jp',
        operatorPassword = randomText();
    await form('register', {}, {
      'email': seller,
      'display_name': 'QA 卖家',
      'password': sellerPassword,
    });
    final sellerId = app.user!['id'];
    final secureToken = await app.secure.read(key: 'session:${app.server}');
    expect(secureToken != null && secureToken == app.token, isTrue);
    await app.initialize();
    expect(app.token == secureToken, isTrue);
    record('native registration + secure storage reread');
    await form('register', {}, {
      'email': buyer,
      'display_name': 'QA 买家',
      'password': buyerPassword,
    });
    await form('register', {}, {
      'email': operator,
      'display_name': 'QA 运营',
      'password': operatorPassword,
    });
    await fixture('promote/${app.user!['id']}');
    await signIn(operator, operatorPassword);
    expect(app.user!['role'], 'admin');
    await signIn(seller, sellerPassword);

    final temp = await Directory.systemTemp.createTemp('yuno-device-fixtures-');
    final bytes = base64Decode(
      'iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAKklEQVR4nO3NQQkAAAgEsItiZCMY1RQ+hMH+S/WcikAgEAgEAoFAIPgSLOl9QEyeTzaIAAAAAElFTkSuQmCC',
    );
    final files = <XFile>[];
    for (var i = 0; i < 10; i++) {
      final file = File('${temp.path}/yuno-qa-$i.png');
      await file.writeAsBytes(bytes);
      files.add(XFile(file.path));
    }
    final realPicker = ImagePickerPlatform.instance;
    addTearDown(() => ImagePickerPlatform.instance = realPicker);
    final picker = FixturePicker(files);
    ImagePickerPlatform.instance = picker;
    await root();
    await tester.tap(find.byIcon(Icons.add_circle_outline));
    await settle();
    await tester.tap(find.text('拍照发布'));
    await settle();
    expect(picker.rear, isTrue);
    expect(find.text('1/10'), findsOneWidget);
    picker.selection = files.skip(1).toList();
    await tester.tap(find.text('相册'));
    await settle();
    expect(find.text('10/10'), findsOneWidget);
    await tester.tap(find.text('拍照').first);
    await settle();
    await reveal(find.text('每件商品最多 10 张照片'));
    expect(find.text('每件商品最多 10 张照片'), findsOneWidget);
    await reveal(find.text('设为封面').first);
    await tester.tap(find.text('设为封面').first);
    await settle();
    await reveal(find.text('重拍').first);
    await tester.tap(find.text('重拍').first);
    await settle();
    await reveal(find.text('替换').first);
    await tester.tap(find.text('替换').first);
    await settle();
    await reveal(find.text('删除').first);
    await tester.tap(find.text('删除').first);
    await settle();
    await reveal(find.text('9/10'));
    expect(find.text('9/10'), findsOneWidget);
    picker.selection = [files.first];
    await tester.tap(find.text('相册'));
    await settle();
    await enter('name', 'QA 微波炉');
    final ai = find.widgetWithText(FilledButton, 'AI 一键识别与估价');
    await reveal(ai);
    await tester.tap(ai);
    for (
      var i = 0;
      i < 400 && find.byType(ActionForm).evaluate().isNotEmpty;
      i++
    ) {
      await tester.pump(const Duration(milliseconds: 100));
    }
    expect(find.byType(ActionForm), findsNothing);
    await settle();
    final drafts = (await app.get('drafts'))['items'] as List;
    final draftId = drafts.first['id'] as int;
    final draft = await item('drafts', draftId);
    expect(draft['photos'].length, 10);
    expect(draft['valuation']['suggested_price'], isNull);
    expect(draft['appraisal'], isA<Map>());
    record('native ten-photo controls + limit + AI no invented market price');
    await screen('drafts', draftId, 'oneclick_publish');
    final published = await form(
      'oneclick_publish',
      {'did': draftId},
      {
        'category_slug': 'appliance',
        'title_ja': 'QA 十图微波炉',
        'title_zh': 'QA 十图微波炉',
        'price': '4000',
      },
    );
    final lid = published['id'] as int;
    expect((await item('listings', lid))['photos'].length, 10);
    await screen('listings', lid, 'auction_create');
    await reveal(find.byType(PageView));
    expect(find.byType(PageView), findsOneWidget);
    record('native publish confirmation + ten-photo product detail');

    await signIn(buyer, buyerPassword);
    final buyerId = app.user!['id'];
    await screen('listings', lid, 'buy');
    await form('follow', {'lid': lid}, {});
    await form('unfollow', {'lid': lid}, {});
    await root();
    nav.push(
      MaterialPageRoute(
        builder: (_) => ThreadPage(lid: lid, buyerId: buyerId),
      ),
    );
    await settle();
    final message = tester.widget<TextField>(find.byType(TextField).last);
    message.controller!.text = 'QA 实机站内消息';
    await tester.tap(find.byIcon(Icons.send_outlined));
    await settle();
    expect((await app.get('threads/$lid/$buyerId'))['items'].length, 1);
    record('native messaging + follow/unfollow');
    final oid = (await form('buy', {'lid': lid}, {}))['id'] as int;
    await screen('orders', oid, 'order_pay');
    final payment = {'oid': oid, 'idempotency_key': 'qa-device-$oid'};
    await form('order_pay', payment, {});
    await form('order_pay', payment, {});
    expect((await item('orders', oid))['status'], 'paid');
    final delivery =
        (await form(
              'delivery_request',
              {'oid': oid},
              {'kind': 'buyer_delivery'},
            ))['id']
            as int;
    await signIn(operator, operatorPassword);
    await screen('deliveries', delivery, 'delivery_assign');
    await form('delivery_assign', {'did': delivery}, {});
    await form('delivery_pickup', {'did': delivery}, {});
    await form('delivery_deliver', {'did': delivery}, {});
    expect((await item('deliveries', delivery))['status'], 'delivered');
    await signIn(buyer, buyerPassword);
    await form('delivery_confirm', {'did': delivery}, {});
    await form('order_complete', {'oid': oid}, {});
    await form(
      'order_review',
      {'oid': oid},
      {'rating': '5', 'comment': 'QA 模拟交易评价'},
    );
    expect((await item('orders', oid))['status'], 'completed');
    record(
      'native buy + simulated payment idempotency + delivery lifecycle + review',
    );

    final serviceIds = <int>[];
    for (final kind in ['cleaning_home', 'transport_small', 'local_delivery']) {
      serviceIds.add(
        (await form('service_create', {}, {'kind': kind}))['id'] as int,
      );
    }
    await signIn(operator, operatorPassword);
    for (final sid in serviceIds) {
      await form('service_confirm', {'sid': sid}, {});
      await form('service_start', {'sid': sid}, {});
      await form('service_complete', {'sid': sid}, {});
      expect((await item('services', sid))['status'], 'completed');
    }
    record('all three native service reservation/confirm/start/complete flows');

    await signIn(seller, sellerPassword);
    final buybackLid = await listing('QA 平台买断');
    final bid =
        (await form('buyback_new', {'listing_id': buybackLid}, {}))['id']
            as int;
    await signIn(operator, operatorPassword);
    await form('buyback_review', {'bid': bid}, {});
    await form('buyback_quote', {'bid': bid}, {'quote': '1800'});
    await signIn(seller, sellerPassword);
    await form('buyback_accept', {'bid': bid}, {});
    await form('buyback_pickup', {'bid': bid}, {'pickup_at': 'date-picker'});
    await signIn(operator, operatorPassword);
    await form(
      'buyback_inspect',
      {'bid': bid},
      {'inspection_note': 'QA 隔离验货记录'},
    );
    await form('buyback_pay', {'bid': bid}, {'resale_price': '3000'});
    expect((await item('buybacks', bid))['status'], 'completed');
    record('native platform buyback full lifecycle + native date/time picker');

    await signIn(seller, sellerPassword);
    final auctionLid = await listing('QA 代理竞拍');
    final aid =
        (await form(
              'auction_create',
              {'lid': auctionLid},
              {
                'start_price': '1000',
                'min_increment': '100',
                'ends_at': 'date-picker',
              },
            ))['id']
            as int;
    await signIn(buyer, buyerPassword);
    await form(
      'auction_bid',
      {'aid': aid},
      {'amount': '1000', 'proxy_max': '1800'},
    );
    await signIn(operator, operatorPassword);
    await form(
      'auction_bid',
      {'aid': aid},
      {'amount': '1500', 'proxy_max': '2200'},
    );
    expect((await item('auctions', aid))['current_price'], 1900);
    await fixture('expire-auction/$aid');
    await form('auction_settle', {'aid': aid}, {});
    expect((await item('auctions', aid))['status'], 'ended_sold');
    record('native auction creation + competing proxy bids + settlement');

    await signIn(seller, sellerPassword);
    final refundLid = await listing('QA 退款与争议');
    await signIn(buyer, buyerPassword);
    final refundOid = (await form('buy', {'lid': refundLid}, {}))['id'] as int;
    await form('order_pay', {
      'oid': refundOid,
      'idempotency_key': 'qa-refund-$refundOid',
    }, {});
    final dispute =
        (await form(
              'dispute_create',
              {'oid': refundOid},
              {'reason': 'QA 隔离争议'},
            ))['id']
            as int;
    final refund =
        (await form(
              'refund_request',
              {'oid': refundOid},
              {'reason': 'QA 隔离退款', 'evidence': 'QA 测试说明'},
            ))['id']
            as int;
    await signIn(operator, operatorPassword);
    await form(
      'dispute_decide',
      {'did': dispute},
      {'decision': 'QA 调解完成', 'note': 'QA 仅测试状态流转'},
    );
    await form(
      'refund_decide',
      {'rid': refund},
      {'decision': 'approved', 'decision_note': 'QA 模拟退款通过'},
    );
    expect((await item('refunds', refund))['status'], 'decided');
    expect((await item('refunds', refund))['decision'], 'approved');
    expect((await item('orders', refundOid))['status'], 'refunded');
    record('native dispute decision + simulated refund lifecycle');

    if (!hardware) {
      await signIn(seller, sellerPassword);
      final negotiated = await listing('QA 议价商品');
      final contested = await listing('QA 并发购买');
      await signIn(buyer, buyerPassword);
      final buyerToken = app.token!;
      await form('offer', {'lid': negotiated}, {'amount': '2800'});
      final offers = (await app.get('offers'))['items'] as List;
      final offer = offers.singleWhere(
        (row) => row['listing_id'] == negotiated,
      );
      final offerId = offer['id'] as int;
      await signIn(seller, sellerPassword);
      await form('offer_counter', {'oid': offerId}, {'counter_amount': '3200'});
      expect((await item('offers', offerId))['status'], 'countered');
      await signIn(buyer, buyerPassword);
      await form('offer_accept_counter', {'oid': offerId}, {});
      expect((await item('offers', offerId))['status'], 'accepted');
      final orders = (await app.get('orders'))['items'] as List;
      final order = orders.singleWhere(
        (row) => row['listing_id'] == negotiated,
      );
      expect(order['goods_amount'], 3200);
      await form('order_cancel', {'oid': order['id']}, {});
      expect((await item('orders', order['id']))['status'], 'cancelled');
      record('native offer, counteroffer, acceptance and cancellation');

      await form('register', {}, {
        'email': '${randomText()}@example.jp',
        'display_name': 'QA 无关用户',
        'password': randomText(),
      });
      final outsider = app.user!['id'];
      final outsiderToken = app.token!;
      await expectLater(
        app.get('orders/$oid'),
        throwsA(
          isA<ApiFailure>().having((failure) => failure.status, 'status', 404),
        ),
      );
      await expectLater(
        app.get('admin/users'),
        throwsA(
          isA<ApiFailure>().having((failure) => failure.status, 'status', 403),
        ),
      );
      await expectLater(
        app.action('admin_listing_toggle', {'lid': negotiated}),
        throwsA(
          isA<ApiFailure>().having((failure) => failure.status, 'status', 403),
        ),
      );
      await signIn(operator, operatorPassword);
      await form('admin_user_role', {'uid': outsider}, {'role': 'courier'});
      final users = (await app.get('admin/users'))['items'] as List;
      expect(
        users.singleWhere((row) => row['id'] == outsider)['role'],
        'courier',
      );
      await form('admin_listing_toggle', {'lid': negotiated}, {});
      expect((await item('listings', negotiated))['status'], 'removed');
      await form('admin_listing_toggle', {'lid': negotiated}, {});
      expect((await item('listings', negotiated))['status'], 'active');
      await form('admin_expenses_post', {}, {'kind': 'QA 耗材', 'amount': '100'});
      await form('admin_run_anomalies', {}, {});
      await form('admin_run_pricing', {}, {});
      final audit = (await app.get('admin/audit'))['items'] as List;
      expect(
        audit.map((row) => row['action']),
        containsAll([
          'role_change',
          'listing_toggle',
          'expense_add',
          'agent_anomaly_scan',
          'agent_pricing_run',
        ]),
      );
      record(
        'native admin controls and audit + forbidden cross-account access',
      );

      Future<http.Response> sendAs(String token, String action, Json payload) =>
          http
              .post(
                Uri.parse('${app.server}/api/v1/actions/$action'),
                headers: {
                  'Authorization': 'Bearer $token',
                  'Content-Type': 'application/json',
                },
                body: jsonEncode(payload),
              )
              .timeout(const Duration(seconds: 15));
      final tokens = [buyerToken, outsiderToken];
      final buys = await Future.wait([
        for (final token in tokens) sendAs(token, 'buy', {'lid': contested}),
      ]);
      expect(
        buys.map((response) => response.statusCode),
        unorderedEquals([200, 409]),
      );
      final winner = buys.indexWhere((response) => response.statusCode == 200);
      final contestedOrder =
          (jsonDecode(buys[winner].body) as Json)['id'] as int;
      final payments = await Future.wait(
        List.generate(
          8,
          (_) => sendAs(tokens[winner], 'order_pay', {
            'oid': contestedOrder,
            'idempotency_key': 'qa-race-$contestedOrder',
          }),
        ),
      );
      expect(
        payments.map((response) => response.statusCode),
        everyElement(200),
      );
      final checked = await app.get('orders/$contestedOrder');
      expect(checked['item']['status'], 'paid');
      final contestedAudit = (checked['related']['audits'] as List);
      expect(
        contestedAudit.where((row) => row['event'] == 'mock_payment'),
        hasLength(1),
      );
      record(
        'competing buyer requests and eight concurrent simulated payment retries',
      );

      await fixture('market-history/$sellerId/$buyerId');
      final moves = (await app.get('market'))['moves'] as Json;
      expect((moves['gainers'] as List).map((row) => row['pct']), [50.0, 20.0]);
      expect((moves['losers'] as List).map((row) => row['pct']), [
        -50.0,
        -25.0,
      ]);
      await root();
      await tester.tap(find.byIcon(Icons.show_chart_rounded));
      await settle();
      expect(find.text('▲ 上涨榜'), findsOneWidget);
      expect(find.text('▼ 下跌榜'), findsOneWidget);
      expect(
        tester.getTopLeft(find.text('QA 涨幅第一')).dy,
        lessThan(tester.getTopLeft(find.text('QA 涨幅第二')).dy),
      );
      expect(
        tester.getTopLeft(find.text('QA 跌幅第一')).dy,
        lessThan(tester.getTopLeft(find.text('QA 跌幅第二')).dy),
      );
      expect(find.text('QA 单一成交'), findsNothing);
      record(
        'populated native market rankings and insufficient sample exclusion',
      );
    }

    await root();
    for (final icon in [
      Icons.storefront_outlined,
      Icons.show_chart_rounded,
      Icons.add_circle_outline,
      Icons.receipt_long_outlined,
      Icons.person_outline,
    ]) {
      await tester.tap(find.byIcon(icon));
      await settle();
    }
    await app.languageChoice('ja');
    await settle();
    expect(find.text('取引相場'), findsOneWidget);
    await app.languageChoice('zh');
    await settle();
    expect(find.text('成交行情'), findsOneWidget);
    await app.languageChoice('system');
    await settle();
    expect(app.choice, 'system');
    await app.languageChoice('zh');
    record('five native destinations + Chinese/Japanese/system languages');

    // Actual external camera/album/IME: operated through the device UI. Those
    // images remain local and are NOT submitted or uploaded to any server.
    if (hardware) {
      await signIn(seller, sellerPassword);
      await root();
      ImagePickerPlatform.instance = realPicker;
      debugPrint('YUNO DEVICE MANUAL: CAMERA_READY');
      nav.push(
        MaterialPageRoute(
          builder: (_) => const ActionForm(action: 'oneclick_upload'),
        ),
      );
      await settle();
      for (var i = 0; i < 1200 && find.text('1/10').evaluate().isEmpty; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(find.text('1/10'), findsOneWidget);
      debugPrint('YUNO DEVICE MANUAL: CAMERA_CAPTURED');
      await tester.tap(find.text('相册'));
      await settle();
      debugPrint('YUNO DEVICE MANUAL: ALBUM_READY');
      for (var i = 0; i < 1200 && find.text('2/10').evaluate().isEmpty; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(find.text('2/10'), findsOneWidget);
      final nameField = find.byWidgetPredicate(
        (widget) =>
            widget is TextField &&
            widget.decoration?.labelText == label('name'),
      );
      await reveal(nameField);
      await tester.tap(nameField);
      await settle();
      debugPrint('YUNO DEVICE MANUAL: KEYBOARD_READY');
      for (
        var i = 0;
        i < 1200 &&
            tester.widget<TextField>(nameField).controller!.text !=
                'YunoDeviceQA';
        i++
      ) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(
        tester.widget<TextField>(nameField).controller!.text,
        'YunoDeviceQA',
      );
      FocusManager.instance.primaryFocus?.unfocus();
      await root();
      record(
        'actual rear camera capture + OS album selection + Vivo IME text entry (not uploaded)',
      );
    }
    await app.logout();
    expect(await app.secure.read(key: 'session:${app.server}'), isNull);
    report({
      'passed': passed,
      'fixture_server': 'isolated-loopback',
      'production_data_mutations': false,
      'cross_network_tested': false,
    });
    debugPrint('YUNO DEVICE COMPLETE: ${passed.length} groups');
    expect(sellerId, isNotNull);
  }, timeout: const Timeout(Duration(minutes: 25)));
}
