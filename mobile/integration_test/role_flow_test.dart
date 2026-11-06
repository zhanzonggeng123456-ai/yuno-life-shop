import 'dart:convert';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:yuno_life/main.dart' as app;
import 'package:yuno_life/labels.dart' as labels;
import 'package:yuno_life/session.dart' as api;
import 'package:yuno_life/design.dart';

class Actor {
  final String email, password, token;
  Actor(this.email, this.password, this.token);
}

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
      'native role transitions, invalid login, required fields and access control',
      (tester) async {
    const run = String.fromEnvironment('ACCEPTANCE_RUN_ID');
    expect(RegExp(r'^\d+$').hasMatch(run), isTrue,
        reason: 'Start isolated host role fixture with the same run id');
    final preferences = await SharedPreferences.getInstance();
    final oldServer = preferences.getString('server');
    final oldLanguage = preferences.getString('language') ?? 'system';
    binding.testTextInput.register();
    Future<void> settle() => tester.pumpAndSettle(
        const Duration(milliseconds: 150),
        EnginePhase.sendSemanticsUpdate,
        const Duration(minutes: 2));
    Future<void> reveal(Finder finder) async {
      for (var i = 0; i < 45 && finder.evaluate().isEmpty; i++) {
        await tester.drag(find.byType(Scrollable).first, const Offset(0, -200));
        await settle();
      }
      expect(finder.evaluate().isNotEmpty, isTrue,
          reason: 'Required native control not found');
      await tester.ensureVisible(finder.first);
      await settle();
    }

    Future<void> tap(String text) async {
      final finder = find.text(text);
      await reveal(finder);
      await tester.tap(finder.last);
      await settle();
    }

    Finder field(String key) => find.byWidgetPredicate((w) =>
        w is TextField &&
        w.decoration?.labelText == labels.label(app.session, key));
    Future<void> input(String key, String value) async {
      await reveal(field(key));
      await tester.enterText(field(key), value);
    }

    void stage(String name) {
      debugPrint('ROLE_ACCEPTANCE: $name');
      binding.reportData = {
        'stage': name,
        'hardware': 'not_tested',
        'keyboard': 'test_channel'
      };
    }

    Future<Actor> actor(String role) async {
      final email = 'role-acceptance-$run-$role@acceptance.invalid';
      const alphabet =
          'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789';
      final secret = List.generate(
          24, (_) => alphabet[Random.secure().nextInt(alphabet.length)]).join();
      final response = await app.session.client.post(
          app.session.uri('/register'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'email': email,
            'password': secret,
            'display_name': 'DEMO role $role'
          }));
      expect(response.statusCode, 200,
          reason: 'Fixture account registration failed');
      final value = jsonDecode(response.body);
      final result = Actor(email, secret, value['access_token']);
      if (['admin', 'courier', 'appraiser'].contains(role)) {
        var ready = false;
        for (var i = 0; i < 30; i++) {
          final response = await app.session.client.get(app.session.uri('/me'),
              headers: {'Authorization': 'Bearer ${result.token}'});
          if (jsonDecode(response.body)['role'] == role) {
            ready = true;
            break;
          }
          await Future<void>.delayed(const Duration(milliseconds: 200));
        }
        expect(ready, isTrue,
            reason:
                'Isolated host role fixture has not assigned the required role');
      }
      return result;
    }

    Future<Map<String, dynamic>> post(Actor actor, String path,
        [Map data = const {}]) async {
      final response = await app.session.client.post(app.session.uri(path),
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ${actor.token}'
          },
          body: jsonEncode(data));
      expect(response.statusCode, 200, reason: 'Fixture command rejected');
      return Map<String, dynamic>.from(jsonDecode(response.body));
    }

    int id(Map data) => int.parse('${data['next']}'.split('/').last);
    Future<void> login(Actor actor) => app.session.authenticate(
        false, {'email': actor.email, 'password': actor.password});
    Future<void> detail(String path) async {
      await tester.pumpWidget(MaterialApp(
          key: UniqueKey(),
          theme: yunoTheme(),
          home: app.DetailPage(path: path, title: '角色验收')));
      await settle();
    }

    Future<void> openCommand(String path, String ending) async {
      final data = await app.session.get(path);
      final action = (data['actions'] as List)
          .firstWhere((a) => '${a['path']}'.endsWith(ending));
      await detail(path);
      await tap(app.session.local(action['label']));
    }

    Future<void> submit([Map<String, String> values = const {}]) async {
      for (final item in values.entries) {
        if (item.key == 'decision' || item.key == 'appraisal_status') {
          await tester.tap(find.byType(DropdownButtonFormField<String>).first);
          await settle();
          await tap(labels.status(app.session, item.value));
        } else if (item.key == 'pickup_at') {
          await reveal(field(item.key));
          await tester.tap(field(item.key));
          await settle();
          expect(find.byType(DatePickerDialog), findsOneWidget);
          await tap('OK');
          expect(find.byType(TimePickerDialog), findsOneWidget);
          await tap('OK');
          expect(
              tester
                  .widget<TextField>(field(item.key))
                  .controller!
                  .text
                  .isNotEmpty,
              isTrue);
        } else {
          await input(item.key, item.value);
        }
      }
      FocusManager.instance.primaryFocus?.unfocus();
      await settle();
      await tap('确认提交');
    }

    Future<void> command(String path, String ending,
        [Map<String, String> values = const {}]) async {
      await openCommand(path, ending);
      await submit(values);
    }

    try {
      await preferences.remove('server');
      await app.session.signOut(remote: false);
      await app.session.init();
      await app.session.setLanguage('zh');
      final seller = await actor('seller'), buyer = await actor('buyer');
      final admin = await actor('admin'),
          courier = await actor('courier'),
          appraiser = await actor('appraiser');
      await tester.pumpWidget(const app.YunoApp());
      await settle();
      await tester.tap(find.byType(NavigationDestination).at(4));
      await settle();
      await tap('登录 / 注册');
      await input('email', buyer.email);
      await input('password', '${buyer.password}wrong');
      FocusManager.instance.primaryFocus?.unfocus();
      await settle();
      await tap('登录');
      expect(app.session.signedIn, isFalse);
      expect(
          find.byWidgetPredicate(
              (w) => w is Text && w.style?.color == Colors.red),
          findsOneWidget);
      await input('password', buyer.password);
      FocusManager.instance.primaryFocus?.unfocus();
      await settle();
      await tap('登录');
      expect(app.session.signedIn, isTrue);
      await expectLater(app.session.get('/admin/users'),
          throwsA(isA<api.ApiError>().having((e) => e.status, 'status', 403)));
      stage('native_login_rejection_recovery_and_forbidden');
      Future<int> listing(String title) async =>
          id(await post(seller, '/listings/new', {
            'category_slug': 'appliance',
            'title_ja': title,
            'price': 6000,
            'region': 'sakado'
          }));
      Future<int> paidOrder() async {
        final lid = await listing('DEMO role lifecycle');
        final oid = id(await post(buyer, '/listings/$lid/buy'));
        await post(
            buyer, '/orders/$oid/pay', {'idempotency_key': 'role-$run-$oid'});
        return oid;
      }

      final oid = await paidOrder();
      final deliveryId = id(await post(
          buyer, '/orders/$oid/delivery-request', {'kind': 'buyer_delivery'}));
      await login(courier);
      for (final operation in ['assign', 'pickup', 'deliver']) {
        await command('/deliveries/$deliveryId', '/$operation');
      }
      expect((await app.session.get('/deliveries/$deliveryId'))['status'],
          'delivered');
      await login(buyer);
      await command('/deliveries/$deliveryId', '/confirm');
      expect((await app.session.get('/deliveries/$deliveryId'))['status'],
          'confirmed');
      await openCommand('/orders/$oid', '/refund');
      await submit();
      expect(find.text('必填'), findsWidgets);
      expect((await app.session.get('/orders/$oid'))['status'], 'paid');
      await submit({'reason': 'DEMO refund', 'evidence': 'DEMO fixture'});
      final refund =
          (await app.session.get('/orders/$oid'))['refunds'][0]['id'];
      await login(admin);
      await command('/refunds/$refund', '/decide',
          {'decision': 'approved', 'decision_note': 'DEMO approved'});
      expect((await app.session.get('/orders/$oid'))['status'], 'refunded');
      final terminal = await app.session.get('/orders/$oid');
      expect(
          (terminal['actions'] as List).any((a) =>
              '${a['path']}'.endsWith('/pay') ||
              '${a['path']}'.endsWith('/complete')),
          isFalse);
      final disputeOrder = await paidOrder();
      await login(buyer);
      await command(
          '/orders/$disputeOrder', '/dispute', {'reason': 'DEMO dispute'});
      final dispute =
          (await app.session.get('/orders/$disputeOrder'))['disputes'][0]['id'];
      await login(admin);
      await command('/disputes/$dispute', '/decide',
          {'decision': 'rejected', 'note': 'DEMO adjudication'});
      expect(
          (await app.session.get('/disputes/$dispute'))['status'], 'decided');
      stage(
          'courier_fulfilment_required_validation_refund_dispute_terminality');
      final buybackId = id(await post(seller, '/buyback/new',
          {'listing_id': await listing('DEMO buyback lifecycle')}));
      await command('/buyback/$buybackId', '/review');
      await command('/buyback/$buybackId', '/quote', {'quote': '1000'});
      await login(seller);
      await command('/buyback/$buybackId', '/accept');
      await command(
          '/buyback/$buybackId', '/pickup', {'pickup_at': 'native_picker'});
      await login(appraiser);
      await command('/buyback/$buybackId', '/inspect',
          {'inspection_note': 'DEMO inspected'});
      await login(admin);
      await command('/buyback/$buybackId', '/pay', {'resale_price': '3500'});
      expect((await app.session.get('/buyback/$buybackId'))['status'],
          'completed');
      expect(
          ((await app.session.get('/admin/inventory'))['items'] as List)
              .any((i) => i['buyback_id'] == buybackId),
          isTrue);
      final serviceId = id(await post(
          buyer, '/services/new', {'kind': 'cleaning_home', 'hours': 2}));
      for (final operation in ['confirm', 'start', 'complete']) {
        await command('/services/$serviceId', '/$operation');
      }
      expect((await app.session.get('/services/$serviceId'))['status'],
          'completed');
      final cancelled =
          id(await post(buyer, '/services/new', {'kind': 'local_delivery'}));
      await login(buyer);
      await command('/services/$cancelled', '/cancel');
      expect((await app.session.get('/services/$cancelled'))['status'],
          'cancelled');
      await login(admin);
      for (final section in [
        'users',
        'listings',
        'buybacks',
        'orders',
        'inventory',
        'auctions',
        'deliveries',
        'services',
        'refunds',
        'disputes',
        'high-value',
        'profit',
        'alerts',
        'suggestions',
        'expenses',
        'audit',
        'settings'
      ]) {
        await tester.pumpWidget(MaterialApp(
            key: UniqueKey(),
            theme: yunoTheme(),
            home: app.AdminSection(section: section, title: 'DEMO $section')));
        await settle();
        expect(tester.takeException(), isNull);
      }
      final highListing = id(await post(seller, '/listings/new', {
        'category_slug': 'watch',
        'title_ja': 'DEMO high value review',
        'price': 100000,
        'region': 'sakado'
      }));
      final pendingBuy = await app.session.client.post(
          app.session.uri('/listings/$highListing/buy'),
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ${buyer.token}'
          },
          body: '{}');
      expect(pendingBuy.statusCode, 409);
      final queue = await app.session.get('/admin/high-value');
      final review = (queue['items'] as List)
          .firstWhere((r) => r['listing_id'] == highListing);
      await tester.pumpWidget(MaterialApp(
          key: UniqueKey(),
          theme: yunoTheme(),
          home: const app.AdminSection(
              section: 'high-value', title: 'DEMO review')));
      await settle();
      final card = find.ancestor(
          of: find.text(' #${review['id']}'), matching: find.byType(Card));
      final reviewButton =
          find.descendant(of: card, matching: find.text('人工审核'));
      await reveal(reviewButton);
      await tester.tap(reviewButton);
      await settle();
      await submit({
        'appraisal_status': 'approved',
        'identity_verified': '1',
        'appraisal_note': 'DEMO human fixture review'
      });
      final reviewed =
          (await app.session.get('/listings/$highListing'))['review'];
      expect(reviewed['appraisal_status'], 'approved');
      expect(reviewed['identity_verified'], 1);
      await tester.pumpWidget(MaterialApp(
          key: UniqueKey(),
          theme: yunoTheme(),
          home: const app.AdminSection(
              section: 'expenses', title: 'DEMO expenses')));
      await settle();
      await tap('登记费用');
      await submit(
          {'kind': 'DEMO test', 'amount': '1200', 'note': 'DEMO expense $run'});
      expect(
          ((await app.session.get('/admin/expenses'))['items'] as List).any(
              (e) => e['note'] == 'DEMO expense $run' && e['amount'] == 1200),
          isTrue);
      final settings =
          (await app.session.get('/admin/settings'))['items'] as List;
      final original = {
        for (final row in settings) row['key'] as String: '${row['value']}'
      };
      await tester.pumpWidget(MaterialApp(
          key: UniqueKey(),
          theme: yunoTheme(),
          home: const app.AdminSection(
              section: 'settings', title: 'DEMO settings')));
      await settle();
      await tap('保存参数');
      await submit({
        'commission_rate': '0.50',
        'regions': original['regions']!,
        'buyback_params': original['buyback_params']!
      });
      expect(find.text('佣金比例须在 7%–10% 之间，请修改后重新提交。'), findsOneWidget);
      expect((await app.session.get('/config'))['commission_rate'],
          double.parse(original['commission_rate']!));
      await submit({'commission_rate': '0.08'});
      expect((await app.session.get('/config'))['commission_rate'], 0.08);
      await post(admin, '/admin/settings', {
        for (final key in ['commission_rate', 'regions', 'buyback_params'])
          key: original[key]
      });
      stage('high_value_expenses_settings_rejection_and_save');
      await app.session.signOut();
      expect(await app.session.storage.read(key: 'session'), isNull);
      stage('passed');
    } finally {
      await app.session.signOut(remote: false);
      binding.testTextInput.unregister();
      if (oldServer == null) {
        await preferences.remove('server');
      } else {
        await preferences.setString('server', oldServer);
      }
      await app.session.setLanguage(oldLanguage);
    }
  }, timeout: const Timeout(Duration(minutes: 10)));
}
