import 'dart:io';
import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:yuno_life/session.dart';
import 'package:yuno_life/app_version.dart';

void main() {
  test('visible app version matches package build metadata', () {
    expect(File('pubspec.yaml').readAsStringSync(),
        contains('version: $appVersion+$appBuild'));
  });
  TestWidgetsFlutterBinding.ensureInitialized();
  const storage = FlutterSecureStorage();
  late Session session;
  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    FlutterSecureStorage.setMockInitialValues({});
    session = Session(client: MockClient((request) async {
      if (request.url.path.endsWith('/login')) {
        return http.Response('{"access_token":"fixture-session"}', 200);
      }
      if (request.url.path.endsWith('/me')) {
        return http.Response('{"id":1,"role":"user"}', 200);
      }
      return http.Response('{}', 200);
    }));
    await session.init();
  });
  tearDown(() => session.dispose());
  Future<void> login() => session.authenticate(false, {});

  test('offline logout clears local identity and stored credentials', () async {
    await login();
    session.client =
        MockClient((_) async => throw const SocketException('offline'));
    await expectLater(session.signOut(), throwsA(isA<SocketException>()));
    expect(session.signedIn, isFalse);
    expect(session.me, isNull);
    expect(await storage.read(key: 'session'), isNull);
    expect(await storage.read(key: 'session_server'), isNull);
  });
  test('non-JSON unauthorized response invalidates session before parsing',
      () async {
    await login();
    await expectLater(
        session.decode(http.Response('<html>Unauthorized</html>', 401)),
        throwsA(isA<ApiError>().having((e) => e.status, 'status', 401)));
    expect(session.signedIn, isFalse);
    expect(session.me, isNull);
    expect(await storage.read(key: 'session'), isNull);
    expect(await storage.read(key: 'session_server'), isNull);
  });
  test('array error remains an ApiError instead of a type exception', () async {
    await expectLater(
        session.decode(http.Response('[]', 503)),
        throwsA(
            isA<ApiError>().having((e) => e.code, 'code', 'request_rejected')));
  });
  test('successful response must contain a JSON object', () async {
    await expectLater(
        session.decode(http.Response('[]', 200)),
        throwsA(
            isA<ApiError>().having((e) => e.code, 'code', 'invalid_response')));
  });
  test('changing server never sends old bearer and persists new address',
      () async {
    await login();
    session.client = MockClient((request) async {
      expect(request.headers.containsKey('Authorization'), isFalse);
      expect(request.url.host, 'new.example');
      return http.Response('{}', 200);
    });
    await session.setServer('https://new.example/');
    expect(session.signedIn, isFalse);
    expect(session.preferences!.getString('server'), 'https://new.example');
    expect(await storage.read(key: 'session'), isNull);
  });
  test('restart restores preferences but rejects token for another server',
      () async {
    await session.setLanguage('ja');
    await session.preferences!.setString('server', 'https://new.example');
    await storage.write(key: 'session', value: 'fixture-other-server');
    await storage.write(key: 'session_server', value: 'https://old.example');
    final restarted = Session(client: MockClient((request) async {
      expect(request.headers.containsKey('Authorization'), isFalse);
      return http.Response('{}', 200);
    }));
    addTearDown(restarted.dispose);
    await restarted.init();
    expect(restarted.language, 'ja');
    expect(restarted.baseUrl, 'https://new.example');
    expect(restarted.signedIn, isFalse);
  });
  test('late unauthorized response cannot clear a newer login', () async {
    await login();
    final old = Completer<http.Response>();
    session.client = MockClient((request) async {
      if (request.url.path.endsWith('/old')) return old.future;
      if (request.url.path.endsWith('/login')) {
        return http.Response('{"access_token":"new-session"}', 200);
      }
      return http.Response('{"id":2,"role":"user"}', 200);
    });
    final waiting = session.get('/old');
    final check = expectLater(
        waiting,
        throwsA(
            isA<ApiError>().having((e) => e.code, 'code', 'session_changed')));
    await login();
    old.complete(http.Response('Unauthorized', 401));
    await check;
    expect(session.me!['id'], 2);
    expect(session.signedIn, isTrue);
    expect(await storage.read(key: 'session'), 'new-session');
  });
  test('late profile response cannot resurrect a logged-out identity',
      () async {
    await login();
    final old = Completer<http.Response>();
    session.client = MockClient((_) => old.future);
    final waiting = session.refreshMe();
    final check = expectLater(
        waiting,
        throwsA(
            isA<ApiError>().having((e) => e.code, 'code', 'session_changed')));
    await session.signOut(remote: false);
    old.complete(http.Response('{"id":1,"role":"admin"}', 200));
    await check;
    expect(session.me, isNull);
    expect(session.signedIn, isFalse);
  });
  test('late logout response cannot sign out a newer account', () async {
    await login();
    final old = Completer<http.Response>();
    session.client = MockClient((request) async {
      if (request.url.path.endsWith('/logout')) return old.future;
      if (request.url.path.endsWith('/login')) {
        return http.Response('{"access_token":"new-account"}', 200);
      }
      return http.Response('{"id":2}', 200);
    });
    final waiting = session.signOut();
    final check = expectLater(
        waiting,
        throwsA(
            isA<ApiError>().having((e) => e.code, 'code', 'session_changed')));
    await login();
    old.complete(http.Response('{}', 200));
    await check;
    expect(session.me!['id'], 2);
    expect(session.signedIn, isTrue);
    expect(await storage.read(key: 'session'), 'new-account');
  });
}
