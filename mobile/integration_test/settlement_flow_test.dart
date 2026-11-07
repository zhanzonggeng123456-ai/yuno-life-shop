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
  testWidgets('native auction settlement and admin decisions', (tester) async {
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
      Future<int> listing(String suffix, int price) async =>
          id(await post(seller, '/listings/new', {
            'category_slug': 'appliance',
            'title_ja': 'DEMO lifecycle $run $suffix',
            'price': price,
            'region': 'sakado'
          }));
      final lid = await listing('expire-sold', 6000);
      final aid = id(await post(seller, '/listings/$lid/auction', {
        'start_price': 1000,
        'ends_at': DateTime.now()
            .add(const Duration(days: 1))
            .toUtc()
            .toIso8601String()
      }));
      await post(buyer, '/auctions/$aid/bid', {'amount': 4000});
      await login(admin);
      var expired = false;
      for (var n = 0; n < 30; n++) {
        if ('${(await app.session.get('/auctions/$aid'))['ends_at']}'
            .startsWith('2000-')) {
          expired = true;
          break;
        }
        await Future<void>.delayed(const Duration(milliseconds: 200));
      }
      expect(expired, isTrue, reason: 'Start host with --lifecycle-fixtures');
      await command('/auctions/$aid', '/settle');
      expect((await app.session.get('/auctions/$aid'))['status'], 'ended_sold');
      await command('/auctions/$aid', '/settle');
      await login(buyer);
      var orders = (await app.session.get('/orders'))['items'] as List;
      expect(orders.where((o) => o['listing_id'] == lid).length, 1);
      final oid = orders.firstWhere((o) => o['listing_id'] == lid)['id'];
      await command('/orders/$oid', '/pay');
      await command('/orders/$oid', '/complete');
      expect((await app.session.get('/orders/$oid'))['status'], 'completed');
      final unsoldLid = await listing('unsold', 6000);
      final unsoldAid = id(await post(seller, '/listings/$unsoldLid/auction',
          {'start_price': 1000, 'ends_at': '2000-01-01T00:00:00+00:00'}));
      await login(admin);
      await command('/auctions/$unsoldAid', '/settle');
      expect((await app.session.get('/auctions/$unsoldAid'))['status'],
          'ended_unsold');
      stage('auction_sold_idempotent_settlement_paid_completed_and_unsold');
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
            of: find.byWidgetPredicate(
                (w) => w is Text && (w.data ?? '').endsWith(' #$rid')),
            matching: find.byType(Card));
        final button = find.descendant(of: card, matching: find.text(text));
        await reveal(button);
        await tester.tap(button);
        await settle();
        await submit();
      }

      await section('alerts');
      await tap('异常扫描');
      await submit();
      final alerts = (await app.session.get('/admin/alerts'))['items'] as List;
      final alert = alerts
          .firstWhere((a) => a['kind'] == 'bid_jump' && a['target_id'] == aid);
      await rowAction('alerts', alert['id'] as int, '确认处理');
      expect(
          ((await app.session.get('/admin/alerts'))['items'] as List)
              .firstWhere((a) => a['id'] == alert['id'])['status'],
          'acknowledged');
      await listing('low-peer-a', 4000);
      await listing('low-peer-b', 4000);
      final stockA = await listing('stock-approve', 20000);
      final stockB = await listing('stock-reject', 22000);
      var ready = false;
      for (var n = 0; n < 30; n++) {
        final inv =
            (await app.session.get('/admin/inventory'))['items'] as List;
        if (inv.any((i) => i['listing_id'] == stockA) &&
            inv.any((i) => i['listing_id'] == stockB)) {
          ready = true;
          break;
        }
        await Future<void>.delayed(const Duration(milliseconds: 200));
      }
      expect(ready, isTrue);
      await section('suggestions');
      await tap('生成调价建议');
      await submit();
      final suggestions =
          (await app.session.get('/admin/suggestions'))['items'] as List;
      final approve = suggestions.firstWhere((s) => s['listing_id'] == stockA);
      final reject = suggestions.firstWhere((s) => s['listing_id'] == stockB);
      await rowAction('suggestions', approve['id'] as int, '批准调价');
      await rowAction('suggestions', reject['id'] as int, '驳回');
      final finalSuggestions =
          (await app.session.get('/admin/suggestions'))['items'] as List;
      expect(
          finalSuggestions
              .firstWhere((s) => s['id'] == approve['id'])['status'],
          'approved');
      expect(
          finalSuggestions.firstWhere((s) => s['id'] == reject['id'])['status'],
          'rejected');
      expect((await app.session.get('/listings/$stockA'))['price'],
          approve['suggested_price']);
      expect((await app.session.get('/listings/$stockB'))['price'], 22000);
      final audit = (await app.session.get('/admin/audit'))['items'] as List;
      for (final action in [
        'auction_settle',
        'alert_ack',
        'price_change',
        'price_suggestion_reject'
      ]) {
        expect(audit.any((a) => a['action'] == action), isTrue);
      }
      stage('alert_ack_and_price_approve_reject_persisted_and_audited');
      expect(tester.takeException(), isNull);
      await app.session.signOut();
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
