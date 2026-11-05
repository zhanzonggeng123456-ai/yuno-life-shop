import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:image_picker_platform_interface/image_picker_platform_interface.dart';
import 'package:yuno_life/main.dart' as app;

// Fixture gateway only: verifies rear-camera intent and native preview/upload.
// This does NOT claim to test iOS/Android hardware capture or permission dialogs.
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
      List.generate(9, (_) => file);
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
      'native register, ten-photo draft, honest AI result, publish, and language tabs',
      (tester) async {
    final dir = await Directory.systemTemp.createTemp('yuno-acceptance-');
    final photo = File('${dir.path}/sample.png');
    await photo.writeAsBytes(base64Decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGM4fvkgAATAAlwVeCj7AAAAAElFTkSuQmCC'));
    final picker = FixturePicker(XFile(photo.path));
    ImagePickerPlatform.instance = picker;
    await app.session.signOut(remote: false);
    await tester.pumpWidget(const app.YunoApp());
    await tester.pumpAndSettle(const Duration(milliseconds: 200));
    await app.session.setLanguage('zh');
    await tester.pumpAndSettle();
    Future<void> tapText(String text) async {
      final f = find.text(text).last;
      await tester.ensureVisible(f);
      await tester.tap(f);
      await tester.pumpAndSettle(const Duration(milliseconds: 200));
    }

    Finder field(String name) => find.byWidgetPredicate(
        (w) => w is TextField && w.decoration?.labelText == name);
    await tester.tap(find.byType(NavigationDestination).at(4));
    await tester.pumpAndSettle();
    await tapText('登录 / 注册');
    await tapText('注册新账号');
    final stamp = DateTime.now().microsecondsSinceEpoch;
    final secret = List.generate(
        24,
        (_) => 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'[
            Random.secure().nextInt(57)]).join();
    await tester.enterText(field('邮箱'), 'phone-$stamp@acceptance.invalid');
    await tester.enterText(field('密码'), secret);
    await tester.enterText(field('昵称'), '验收 DEMO');
    await tapText('注册');
    expect(app.session.signedIn, isTrue);
    await tester.tap(find.byType(NavigationDestination).at(2));
    await tester.pumpAndSettle();
    await tapText('拍照发布');
    expect(picker.rearRequested, isTrue);
    expect(find.text('封面'), findsOneWidget);
    await tapText('相册');
    await tester.enterText(field('商品名称'), 'DEMO Panasonic 電子レンジ');
    await tapText('AI 一键识别 · 鉴定 · 估价');
    // Background jobs are polled every two seconds.
    for (var i = 0; i < 40 && find.text('确认商品信息').evaluate().isEmpty; i++) {
      await tester.pump(const Duration(seconds: 1));
    }
    expect(find.text('确认商品信息'), findsOneWidget);
    expect(find.text('此报价为AI根据现实数据做出的估价，用户可以根据自身另行填写'), findsOneWidget);
    await tester.ensureVisible(field('售价（日元，含税）'));
    await tester.enterText(field('售价（日元，含税）'), '5000');
    await tapText('确认上架');
    await tapText('确认上架');
    expect(find.text('已提交发布'), findsOneWidget);
    expect(tester.takeException(), isNull);
    final own = await app.session.get('/me');
    final listings = own['listings'] as List;
    expect(listings.last['photos'].length, 10);
    await app.session.signOut();
    await dir.delete(recursive: true);
  });
}
