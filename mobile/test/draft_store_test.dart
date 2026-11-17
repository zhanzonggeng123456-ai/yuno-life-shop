import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:image_picker/image_picker.dart';
import 'package:yuno_life/draft_store.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Directory temp;
  late DraftStore store;
  setUp(() async {
    FlutterSecureStorage.setMockInitialValues({});
    temp = await Directory.systemTemp.createTemp('yuno-draft-test-');
    store = DraftStore(directory: () async => temp);
  });
  tearDown(() async {
    await temp.delete(recursive: true);
  });

  test(
      'photos survive picker temp cleanup and draft metadata survives reopening',
      () async {
    final owner = store.owner('https://one.example', 7);
    final source = File('${temp.path}/picker.png');
    await source.writeAsBytes([1, 2, 3]);
    final kept = await store.keepPhoto(owner, XFile(source.path));
    final key = store.key(owner, null);
    final values = ['before'];
    final saving = store.save(key, {
      'values': values,
      'photos': [kept.path],
      'owned_photos': [kept.path]
    });
    values[0] = 'after';
    await saving;
    await source.delete();
    final reopened = DraftStore(directory: () async => temp);
    final restored = await reopened.load(key);
    expect(restored!['values'], ['before']);
    expect(await File((restored['photos'] as List).single).readAsBytes(),
        [1, 2, 3]);
    await reopened.clear(owner, key);
    expect(await File(kept.path).exists(), isFalse);
    expect(await reopened.load(key), isNull);
  });

  test(
      'ordered writes keep newest snapshot and account cleanup is scoped to host and user',
      () async {
    final owners = [
      store.owner('https://one.example', 1),
      store.owner('https://one.example', 2),
      store.owner('https://two.example', 1)
    ];
    final source = File('${temp.path}/source.png');
    await source.writeAsBytes([9]);
    final paths = <String>[];
    for (final owner in owners) {
      final photo = await store.keepPhoto(owner, XFile(source.path));
      paths.add(photo.path);
      await store.save(store.key(owner, null), {
        'owned_photos': [photo.path]
      });
    }
    final key = store.key(owners[0], 12);
    final one = store.save(key, {'revision': 1});
    final two = store.save(key, {'revision': 2});
    await Future.wait([one, two]);
    expect((await store.load(key))!['revision'], 2);
    await store.clearAccount('https://one.example', 1);
    expect(await store.load(key), isNull);
    expect(await File(paths[0]).exists(), isFalse);
    for (var i = 1; i < owners.length; i++) {
      expect(await store.load(store.key(owners[i], null)), isNotNull);
      expect(await File(paths[i]).exists(), isTrue);
    }
  });

  test('cleanup never deletes a referenced file outside the account sandbox',
      () async {
    final other = File('${temp.path}/outside.png');
    await other.writeAsBytes([8]);
    final owner = store.owner('https://one.example', 1),
        key = store.key(store.owner('https://one.example', 1), null);
    await store.save(key, {
      'owned_photos': [other.path]
    });
    await store.clear(owner, key);
    expect(await other.exists(), isTrue);
  });
}
