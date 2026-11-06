import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';
import 'package:integration_test/integration_test.dart';
import 'package:shop/main.dart' as shop;
import 'package:shop/screens.dart';
import 'package:shop/editor.dart';
import 'package:shop/api.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  final app = shop.appState;
  final random = Random.secure();
  String randomText() =>
      List.generate(20, (_) => random.nextInt(36).toRadixString(36)).join();

  Future<void> settle(WidgetTester tester) async {
    for (var i = 0; i < 20; i++) {
      await tester.pump(const Duration(milliseconds: 150));
    }
    expect(tester.takeException(), isNull);
  }

  testWidgets(
    'Native login, photos, AI draft, trading, services, messages and language',
    (tester) async {
      await app.initialize();
      await app.connect(const String.fromEnvironment('YUNO_SERVER'));
      await app.languageChoice('zh');
      await tester.pumpWidget(const shop.YunoApp());
      await settle(tester);
      expect(find.byType(NavigationDestination), findsNWidgets(5));

      // Register through the native form, using a fresh, ephemeral password.
      await tester.tap(find.byIcon(Icons.person_outline));
      await settle(tester);
      await tester.tap(find.text('注册'));
      await settle(tester);
      final sellerEmail = '${randomText()}@example.jp';
      final sellerPassword = randomText();
      await tester.enterText(find.byType(TextFormField).at(0), sellerEmail);
      await tester.enterText(find.byType(TextFormField).at(1), 'QA 出品者');
      await tester.enterText(find.byType(TextFormField).at(2), sellerPassword);
      final submit = find.widgetWithText(FilledButton, '注册');
      await tester.ensureVisible(submit);
      await tester.tap(submit);
      await settle(tester);
      expect(find.byType(ActionForm), findsNothing);
      expect(app.user?['email'], sellerEmail);
      final sellerId = app.user!['id'];
      expect(await app.secure.read(key: 'session:${app.server}'), app.token);

      // Valid small PNGs, isolated to the QA database and device temp directory.
      final bytes = base64Decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=',
      );
      final temp = await Directory.systemTemp.createTemp('yuno-native-test-');
      final files = <XFile>[];
      for (var i = 0; i < 2; i++) {
        final file = File('${temp.path}/photo$i.png');
        await file.writeAsBytes(bytes);
        files.add(XFile(file.path));
      }
      final upload = await app.action('oneclick_upload', {
        'name': '微波炉',
        'condition': 'good',
      }, photos: files);
      final did = upload['id'];
      final job = await app.action('ai_job_create', {
        'kind': 'oneclick_recognize',
        'draft_id': '$did',
      });
      await app.poll(job['job_id'], (_) {});
      var draft = (await app.get('drafts/$did'))['item'] as Json;
      expect(draft['photos'].length, 2);
      expect(draft['valuation']['suggested_price'], isNull);
      await app.action('draft_photo_cover', {'did': did, 'idx': 1});
      await app.action(
        'draft_photo_replace',
        {'did': did, 'idx': 1},
        photos: [files.first],
        photoField: 'photo',
      );
      await app.action('oneclick_recognize', {'did': did});
      final published = await app.action('oneclick_publish', {
        'did': did,
        'category_slug': 'appliance',
        'title_ja': 'QA 電子レンジ',
        'title_zh': 'QA 微波炉',
        'price': '4000',
      });
      final lid = published['id'];
      final listing = (await app.get('listings/$lid'))['item'];
      expect(listing['photos'].length, 2);

      // View the actual native product screen, including both photos.
      final nav = tester.state<NavigatorState>(find.byType(Navigator).first);
      nav.push(
        MaterialPageRoute<void>(
          builder: (_) => DetailPage(resource: 'listings', id: lid),
        ),
      );
      await settle(tester);
      expect(find.text('QA 微波炉'), findsWidgets);
      expect(find.byType(PageView), findsOneWidget);
      nav.pop();
      await settle(tester);

      await app.logout();
      final buyerEmail = '${randomText()}@example.jp';
      final buyerPassword = randomText();
      await app.action('register', {
        'email': buyerEmail,
        'display_name': 'QA 購入者',
        'password': buyerPassword,
      });
      final buyerId = app.user!['id'];
      await app.action('thread_post', {
        'lid': lid,
        'buyer_id': buyerId,
        'body': 'QA 商品の状態を確認します',
      });
      expect((await app.get('threads/$lid/$buyerId'))['items'].length, 1);
      final order = (await app.action('buy', {'lid': lid}))['id'];
      final pay = {'oid': order, 'idempotency_key': randomText()};
      await app.action('order_pay', pay);
      await app.action('order_pay', pay);
      expect((await app.get('orders/$order'))['item']['status'], 'paid');
      final delivery = await app.action('delivery_request', {
        'oid': order,
        'kind': 'buyer_delivery',
      });
      expect(
        (await app.get('deliveries/${delivery['id']}'))['item']['status'],
        'requested',
      );
      await app.action('order_complete', {'oid': order});
      await app.action('order_review', {
        'oid': order,
        'rating': 5,
        'comment': 'QA',
      });

      for (final kind in [
        'cleaning_home',
        'transport_small',
        'local_delivery',
      ]) {
        final service = await app.action('service_create', {'kind': kind});
        expect(
          (await app.get('services/${service['id']}'))['item']['kind'],
          kind,
        );
        await app.action('service_cancel', {'sid': service['id']});
      }

      await app.logout();
      await app.action('login', {
        'email': sellerEmail,
        'password': sellerPassword,
      });
      expect(app.user!['id'], sellerId);
      final auctionListing = (await app.action('listing_create', {
        'category_slug': 'book',
        'title_ja': 'QA 本',
        'price': 1000,
      }))['id'];
      final auction = (await app.action('auction_create', {
        'lid': auctionListing,
        'start_price': 1000,
        'min_increment': 100,
        'ends_at': DateTime.now()
            .add(const Duration(hours: 1))
            .toUtc()
            .toIso8601String(),
      }))['id'];
      final buybackListing = (await app.action('listing_create', {
        'category_slug': 'appliance',
        'title_ja': 'QA 買取',
        'price': 3000,
      }))['id'];
      final buyback = await app.action('buyback_new', {
        'listing_id': buybackListing,
      });
      expect(
        (await app.get('buybacks/${buyback['id']}'))['item']['seller_id'],
        sellerId,
      );

      await app.action('login', {
        'email': buyerEmail,
        'password': buyerPassword,
      });
      await app.action('auction_bid', {
        'aid': auction,
        'amount': 1000,
        'proxy_max': 1800,
      });
      expect(
        (await app.get('auctions/$auction'))['item']['current_price'],
        1000,
      );
      await app.action('offer', {'lid': buybackListing, 'amount': 2500});
      final offers = (await app.get('offers'))['items'] as List;
      final offer = offers.firstWhere((o) => o['listing_id'] == buybackListing);
      await app.action('login', {
        'email': sellerEmail,
        'password': sellerPassword,
      });
      await app.action('offer_accept', {'oid': offer['id']});

      // Switch all five root screens and check the native rendering.
      for (final icon in [
        Icons.storefront_outlined,
        Icons.show_chart_rounded,
        Icons.add_circle_outline,
        Icons.receipt_long_outlined,
        Icons.person_outline,
      ]) {
        await tester.tap(find.byIcon(icon));
        await settle(tester);
      }
      await app.languageChoice('ja');
      await settle(tester);
      expect(find.text('取引相場'), findsOneWidget);
      await app.languageChoice('zh');
      await settle(tester);
      expect(find.text('成交行情'), findsOneWidget);
      expect((await app.get('market'))['moves'], isA<Map>());
      await app.logout();
      expect(await app.secure.read(key: 'session:${app.server}'), isNull);
      await temp.delete(recursive: true);
    },
    timeout: const Timeout(Duration(minutes: 5)),
  );
}
