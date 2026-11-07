import 'dart:convert';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:yuno_life/main.dart' as app;
import 'package:yuno_life/labels.dart' as labels;
import 'package:yuno_life/design.dart';

class Actor {
  final String email, password, token;
  Actor(this.email, this.password, this.token);
}

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('native admin writes and auction rejection recovery',
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
        if (item.key == 'decision' ||
            item.key == 'appraisal_status' ||
            item.key == 'role') {
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
      final admin = await actor('admin');
      final lid = id(await post(seller, '/listings/new', {
        'category_slug': 'appliance',
        'title_ja': 'DEMO closure auction',
        'price': 6000,
        'region': 'sakado'
      }));
      final aid = id(await post(seller, '/listings/$lid/auction', {
        'start_price': 1000,
        'deposit_required': '1',
        'deposit_amount': 100,
        'buy_now_price': 6000,
        'ends_at': DateTime.now()
            .add(const Duration(days: 1))
            .toUtc()
            .toIso8601String()
      }));
      await login(buyer);
      await openCommand('/auctions/$aid', '/bid');
      await submit({'amount': '1000'});
      expect(find.text('请先完成模拟保证金，再提交出价。'), findsOneWidget);
      expect(find.byType(app.CommandForm), findsOneWidget);
      expect((await app.session.get('/auctions/$aid'))['bids'], isEmpty);
      await command('/auctions/$aid', '/deposit');
      await openCommand('/auctions/$aid', '/bid');
      await submit({'amount': '500'});
      expect(find.text('出价至少为 ¥1000，请修改后重新提交。'), findsOneWidget);
      await submit({'amount': '1000', 'proxy_max': '500'});
      expect(find.text('代理出价上限不能低于本次出价。'), findsOneWidget);
      await submit({'proxy_max': '2000'});
      expect((await app.session.get('/auctions/$aid'))['bids'].length, 1);
      await command('/auctions/$aid', '/buy-now');
      final orders = (await app.session.get('/orders'))['items'] as List;
      final order = orders.firstWhere((o) => o['listing_id'] == lid);
      expect(order['status'], 'pending_payment');
      await command('/orders/${order['id']}', '/cancel');
      expect((await app.session.get('/orders/${order['id']}'))['status'],
          'cancelled');
      stage('auction_deposit_rejections_correction_buy_now_cancel');
      await login(admin);
      Future<void> section(String name) async {
        await tester.pumpWidget(MaterialApp(
            key: UniqueKey(),
            theme: yunoTheme(),
            home: app.AdminSection(section: name, title: 'DEMO $name')));
        await settle();
      }

      Future<void> rowAction(String name, int rid, String text) async {
        await section(name);
        final card = find.ancestor(
            of: find.byWidgetPredicate((w) => w is Text && (w.data ?? '').endsWith(' #$rid')),
            matching: find.byType(Card));
        final button = find.descendant(of: card, matching: find.text(text));
        await reveal(button);
        await tester.tap(button);
        await settle();
      }

      final users = (await app.session.get('/admin/users'))['items'] as List;
      final uid =
          users.firstWhere((u) => u['email'] == buyer.email)['id'] as int;
      await rowAction('users', uid, '修改角色');
      await submit({'role': 'collector'});
      final updated = (await app.session.get('/admin/users'))['items'] as List;
      expect(updated.firstWhere((u) => u['id'] == uid)['role'], 'collector');
      await rowAction('users', uid, '修改角色');
      await submit({'role': 'user'});
      final toggleId = id(await post(seller, '/listings/new', {
        'category_slug': 'appliance',
        'title_ja': 'DEMO toggle',
        'price': 3000,
        'region': 'sakado'
      }));
      for (final expected in ['removed', 'active']) {
        await rowAction('listings', toggleId, '上下架');
        await submit();
        final listings =
            (await app.session.get('/admin/listings'))['items'] as List;
        expect(listings.firstWhere((l) => l['id'] == toggleId)['status'],
            expected);
      }
      await section('alerts');
      await tap('异常扫描');
      await submit();
      await section('suggestions');
      await tap('生成调价建议');
      await submit();
      final audit = (await app.session.get('/admin/audit'))['items'] as List;
      for (final action in [
        'role_change',
        'listing_toggle',
        'agent_anomaly_scan',
        'agent_pricing_run'
      ]) {
        expect(audit.any((a) => a['action'] == action), isTrue);
      }
      stage('admin_role_toggle_anomaly_pricing_commands_audited');
      expect(tester.takeException(), isNull);
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
