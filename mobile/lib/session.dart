import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import 'package:shared_preferences/shared_preferences.dart';

typedef Json = Map<String, dynamic>;

class ApiError implements Exception {
  final int status;
  final String code;
  ApiError(this.status, this.code);
  @override
  String toString() => code;
}

class Session extends ChangeNotifier {
  http.Client client;
  Session({http.Client? client}) : client = client ?? http.Client();
  final storage = const FlutterSecureStorage(
    iOptions: IOSOptions(
      accessibility: KeychainAccessibility.first_unlock_this_device,
    ),
  );
  String baseUrl = const String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );
  String language = 'system';
  String? _token;
  Json? me;
  Json config = {};
  SharedPreferences? preferences;
  bool get signedIn => _token != null;
  bool get operatorRole => ['admin', 'operator'].contains(me?['role']);
  bool get zh =>
      language == 'zh' ||
      (language == 'system' &&
          PlatformDispatcher.instance.locale.languageCode == 'zh');
  String tr(String zhText, String jaText) => zh ? zhText : jaText;
  String local(dynamic value) =>
      value is Map ? '${value[zh ? 'zh' : 'ja'] ?? ''}' : '$value';
  String title(Json value) =>
      '${value[zh ? 'title_zh' : 'title_ja'] ?? value['title_ja'] ?? value['title_zh'] ?? ''}';
  String name(Json value) =>
      '${value[zh ? 'name_zh' : 'name_ja'] ?? value['name_ja'] ?? value['slug'] ?? ''}';
  String photo(String path) => path.startsWith('http') ? path : '$baseUrl$path';

  Future<void> init() async {
    preferences = await SharedPreferences.getInstance();
    language = preferences!.getString('language') ?? 'system';
    baseUrl = preferences!.getString('server') ?? baseUrl;
    _token = await storage.read(key: 'session');
    if (await storage.read(key: 'session_server') != baseUrl) {
      await clearIdentity();
    }
    await bootstrap();
  }

  Future<void> bootstrap() async {
    config = await get('/config');
    if (signedIn) {
      try {
        me = await get('/me');
      } on ApiError catch (error) {
        if (error.status != 401) rethrow;
      }
    }
    notifyListeners();
  }

  Future<void> setLanguage(String value) async {
    language = value;
    await preferences?.setString('language', value);
    notifyListeners();
  }

  Future<void> setServer(String address) async {
    final uri = Uri.tryParse(address.trim());
    if (uri == null ||
        !['http', 'https'].contains(uri.scheme) ||
        !uri.hasAuthority ||
        uri.userInfo.isNotEmpty) {
      throw ApiError(400, 'invalid_server');
    }
    // Never send an existing bearer token to a newly selected server.
    if (baseUrl != address.trim().replaceAll(RegExp(r'/$'), '')) {
      await signOut(remote: false);
      baseUrl = address.trim().replaceAll(RegExp(r'/$'), '');
      await preferences?.setString('server', baseUrl);
    }
    await bootstrap();
  }

  Future<void> authenticate(bool register, Json fields) async {
    final data = await post(register ? '/register' : '/login', fields);
    final token = data['access_token'];
    if (token is! String || token.isEmpty) {
      throw ApiError(401, 'authentication_failed');
    }
    await storage.write(key: 'session', value: token);
    await storage.write(key: 'session_server', value: baseUrl);
    _token = token;
    me = await get('/me');
    notifyListeners();
  }

  Future<void> signOut({bool remote = true}) async {
    try {
      if (remote && signedIn) {
        await post('/logout', {});
      }
    } finally {
      // Network failure must not keep the user signed in on this device.
      await clearIdentity();
    }
  }

  Future<void> clearIdentity() async {
    _token = null;
    me = null;
    await storage.delete(key: 'session');
    await storage.delete(key: 'session_server');
    notifyListeners();
  }

  Future<void> refreshMe() async {
    me = await get('/me');
    notifyListeners();
  }

  Uri uri(String path) => Uri.parse('$baseUrl/api/v1$path');
  Map<String, String> get headers => {
        'Accept': 'application/json',
        'Accept-Language': zh ? 'zh' : 'ja',
        if (_token != null) 'Authorization': 'Bearer $_token',
      };
  Future<Json> decode(http.Response response) async {
    // A gateway may return HTML or an empty body for 401 responses.
    if (response.statusCode == 401 && _token != null) {
      await clearIdentity();
    }
    dynamic data;
    try {
      data = jsonDecode(utf8.decode(response.bodyBytes));
    } catch (_) {
      throw ApiError(response.statusCode, 'invalid_response');
    }
    if (response.statusCode >= 400) {
      throw ApiError(
        response.statusCode,
        data is Map
            ? '${data['error'] ?? 'request_rejected'}'
            : 'request_rejected',
      );
    }
    if (data is! Map<String, dynamic>) {
      throw ApiError(500, 'invalid_response');
    }
    return data;
  }

  Future<Json> get(String path) async => decode(
        await client
            .get(uri(path), headers: headers)
            .timeout(const Duration(seconds: 20)),
      );
  Future<Json> post(String path, Json data) async => decode(
        await client
            .post(
              uri(path),
              headers: {...headers, 'Content-Type': 'application/json'},
              body: jsonEncode(data),
            )
            .timeout(const Duration(seconds: 20)),
      );
  Future<Json> upload(
    String path,
    Json fields,
    List<XFile> files, {
    String field = 'photos',
  }) async {
    if (files.length > 10) {
      throw ApiError(400, 'max_10_photos');
    }
    final request = http.MultipartRequest('POST', uri(path));
    request.headers.addAll(headers);
    fields.forEach((key, value) {
      if (value != null) request.fields[key] = '$value';
    });
    for (final file in files) {
      if (await file.length() > 5 * 1024 * 1024) {
        throw ApiError(400, 'image_too_large');
      }
      request.files.add(await http.MultipartFile.fromPath(field, file.path));
    }
    return decode(
      await http.Response.fromStream(
        await client.send(request).timeout(const Duration(seconds: 45)),
      ),
    );
  }
}
