import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker_platform_interface/image_picker_platform_interface.dart';
import 'package:yuno_life/main.dart';

class CapacityPicker extends ImagePickerPlatform {
  final XFile photo;
  final sources = <ImageSource>[];
  int? requestedLimit;
  CapacityPicker(this.photo);
  @override
  Future<XFile?> getImageFromSource(
      {required ImageSource source,
      ImagePickerOptions options = const ImagePickerOptions()}) async {
    sources.add(source);
    return photo;
  }

  @override
  Future<List<XFile>> getMultiImageWithOptions(
      {MultiImagePickerOptions options =
          const MultiImagePickerOptions()}) async {
    requestedLimit = options.limit;
    return List.generate(8, (_) => photo);
  }
}

void main() {
  testWidgets(
      'gallery respects remaining slots including one slot and full capacity',
      (tester) async {
    final original = ImagePickerPlatform.instance;
    final dir = await tester
        .runAsync(() => Directory.systemTemp.createTemp('yuno-photo-test-'));
    final file = File('${dir!.path}/photo.png');
    await tester.runAsync(() => file.writeAsBytes(base64Decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGM4fvkgAATAAlwVeCj7AAAAAElFTkSuQmCC')));
    final picker = CapacityPicker(XFile(file.path));
    ImagePickerPlatform.instance = picker;
    addTearDown(() async {
      ImagePickerPlatform.instance = original;
      await dir.delete(recursive: true);
    });
    session.language = 'zh';
    session.config = {'categories': [], 'regions': []};
    await tester.pumpWidget(const MaterialApp(home: PublishPage()));
    await tester.pumpAndSettle();
    expect(picker.sources, [ImageSource.camera]);
    await tester.ensureVisible(find.text('从相册选'));
    await tester.tap(find.text('从相册选'));
    await tester.pumpAndSettle();
    expect(picker.requestedLimit, 9);
    // One camera photo + eight selected photos leaves one slot.
    await tester.tap(find.text('从相册选'));
    await tester.pumpAndSettle();
    expect(picker.sources, [ImageSource.camera, ImageSource.gallery]);
    await tester.tap(find.text('从相册选'));
    await tester.pumpAndSettle();
    expect(picker.sources.length, 2);
    expect(find.text('每件商品最多 10 张照片。'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
  });
}
