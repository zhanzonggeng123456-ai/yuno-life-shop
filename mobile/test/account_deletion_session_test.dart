import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:yuno_life/draft_store.dart';
import 'package:yuno_life/session.dart';

class UnavailableDraftStore extends DraftStore {
  bool attempted = false;
  @override
  Future<void> clearAccount(String server, int uid) async {
    attempted = true;
    throw const FileSystemException('storage unavailable');
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    FlutterSecureStorage.setMockInitialValues({});
  });
  test(
      'successful server deletion clears identity and reports local cleanup separately',
      () async {
    final drafts = UnavailableDraftStore();
    final api = Session(
        drafts: drafts,
        client: MockClient((request) async {
          if (request.url.path.endsWith('/login')) {
            return http.Response('{"access_token":"test"}', 200);
          }
          if (request.url.path.endsWith('/me')) {
            return http.Response('{"id":7}', 200);
          }
          return http.Response('{"deleted":true}', 200);
        }));
    await api.init();
    await api.authenticate(false, {});
    expect(await api.deleteAccount('test-password'), isFalse);
    expect(drafts.attempted, isTrue);
    expect(api.signedIn, isFalse);
    expect(api.me, isNull);
    expect(await api.storage.read(key: 'session'), isNull);
    api.dispose();
  });
  test(
      'rejected server deletion retains identity and never erases local drafts',
      () async {
    final drafts = UnavailableDraftStore();
    final api = Session(
        drafts: drafts,
        client: MockClient((request) async {
          if (request.url.path.endsWith('/login')) {
            return http.Response('{"access_token":"test"}', 200);
          }
          if (request.url.path.endsWith('/me')) {
            return http.Response('{"id":7}', 200);
          }
          if (request.url.path.endsWith('/account/delete')) {
            return http.Response('{"error":"current_password_required"}', 403);
          }
          return http.Response('{}', 200);
        }));
    await api.init();
    await api.authenticate(false, {});
    await expectLater(api.deleteAccount('wrong'), throwsA(isA<ApiError>()));
    expect(drafts.attempted, isFalse);
    expect(api.signedIn, isTrue);
    api.dispose();
  });
}
