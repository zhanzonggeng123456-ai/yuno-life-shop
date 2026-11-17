import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';

/// Draft metadata is encrypted; photos live in this app's persistent sandbox.
/// Keys bind drafts to both the server and the signed-in account.
class DraftStore {
  final FlutterSecureStorage storage;
  final Future<Directory> Function() directory;
  Future<void> _writes = Future.value();
  DraftStore(
      {FlutterSecureStorage? storage, Future<Directory> Function()? directory})
      : storage = storage ??
            const FlutterSecureStorage(
                iOptions: IOSOptions(
                    accessibility:
                        KeychainAccessibility.first_unlock_this_device)),
        directory = directory ?? getApplicationSupportDirectory;

  String owner(String server, int uid) =>
      sha256.convert(utf8.encode('$server|$uid')).toString();
  String key(String owner, int? did) => 'yuno_draft_$owner:${did ?? "new"}';

  Future<XFile> keepPhoto(String owner, XFile photo) async {
    final root = Directory('${(await directory()).path}/yuno-drafts/$owner');
    await root.create(recursive: true);
    final name =
        '${DateTime.now().microsecondsSinceEpoch}-${Random.secure().nextInt(1 << 32)}';
    final extension = photo.path.toLowerCase().endsWith('.png') ? 'png' : 'jpg';
    final saved = await File(photo.path).copy('${root.path}/$name.$extension');
    return XFile(saved.path);
  }

  Future<void> save(String key, Map<String, dynamic> snapshot) {
    final encoded = jsonEncode(snapshot);
    final next = _writes
        .catchError((Object _) {})
        .then((_) => storage.write(key: key, value: encoded));
    _writes = next;
    return next;
  }

  Future<Map<String, dynamic>?> load(String key) async {
    await _writes.catchError((Object _) {});
    final raw = await storage.read(key: key);
    if (raw == null) return null;
    final value = jsonDecode(raw);
    return value is Map<String, dynamic> ? value : null;
  }

  Future<void> clear(String owner, String key) async {
    await _writes.catchError((Object _) {});
    final snapshot = await load(key);
    final root = '${(await directory()).path}/yuno-drafts/$owner/';
    for (final path
        in (snapshot?['owned_photos'] as List? ?? []).whereType<String>()) {
      if (path.startsWith(root) && !path.substring(root.length).contains('/')) {
        try {
          await File(path).delete();
        } on FileSystemException {/* Already gone. */}
      }
    }
    await storage.delete(key: key);
  }

  Future<void> clearAccount(String server, int uid) async {
    final account = owner(server, uid);
    await _writes.catchError((Object _) {});
    for (final key in (await storage.readAll())
        .keys
        .where((k) => k.startsWith('yuno_draft_$account:'))
        .toList()) {
      await clear(account, key);
    }
    final folder =
        Directory('${(await directory()).path}/yuno-drafts/$account');
    if (await folder.exists()) await folder.delete(recursive: true);
  }
}
