import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import 'package:shared_preferences/shared_preferences.dart';

typedef Json = Map<String, dynamic>;

class ApiFailure implements Exception {
  final String code;
  final int status;
  ApiFailure(this.code, this.status);
  @override
  String toString() => code;
}

class ShopState extends ChangeNotifier with WidgetsBindingObserver {
  final secure = const FlutterSecureStorage();
  final client = http.Client();
  late SharedPreferences preferences;
  String server = const String.fromEnvironment('YUNO_SERVER', defaultValue: '');
  String choice = 'system';
  String? token;
  Json? user;
  Json config = {};
  int revision = 0;
  String get language {
    if (choice != 'system') return choice;
    return WidgetsBinding.instance.platformDispatcher.locale.languageCode ==
            'zh'
        ? 'zh'
        : 'ja';
  }

  Future<void> initialize() async {
    WidgetsBinding.instance.addObserver(this);
    preferences = await SharedPreferences.getInstance();
    server = preferences.getString('server') ?? server;
    choice = preferences.getString('language') ?? 'system';
    if (server.isNotEmpty) token = await secure.read(key: 'session:$server');
    if (token != null) {
      try {
        user = (await get('me'))['user'];
      } on ApiFailure catch (error) {
        if (error.status == 401) await logout(localOnly: true);
      } on Exception catch (_) {
        /* Retry after reconnecting. */
      }
    }
  }

  @override
  void didChangeLocales(List<Locale>? locales) {
    if (choice == 'system') notifyListeners();
  }

  Future<void> languageChoice(String value) async {
    choice = value;
    await preferences.setString('language', value);
    notifyListeners();
  }

  Future<void> connect(String address) async {
    final uri = Uri.tryParse(address.trim());
    if (uri == null ||
        !['http', 'https'].contains(uri.scheme) ||
        uri.host.isEmpty ||
        uri.userInfo.isNotEmpty ||
        uri.hasQuery ||
        uri.hasFragment ||
        (uri.path.isNotEmpty && uri.path != '/')) {
      throw ApiFailure('invalid_server', 400);
    }
    final previousServer = server;
    final previousUser = user;
    final previousToken = token;
    final previousConfig = config;
    try {
      server = address.trim().replaceAll(RegExp(r'/+$'), '');
      user = null;
      token = await secure.read(key: 'session:$server');
      config = await get('config');
      if (token != null) {
        try {
          user = (await get('me'))['user'];
        } on ApiFailure catch (e) {
          if (e.status != 401) rethrow;
        }
      }
      await preferences.setString('server', server);
      changed();
    } catch (_) {
      server = previousServer;
      user = previousUser;
      token = previousToken;
      config = previousConfig;
      rethrow;
    }
  }

  Map<String, String> get headers => {
    'Accept': 'application/json',
    'Accept-Language': language,
    if (token != null) 'Authorization': 'Bearer $token',
  };
  String imageUrl(String path) => '$server$path';
  Future<Json> decode(http.Response response) async {
    Json body;
    try {
      body = jsonDecode(utf8.decode(response.bodyBytes)) as Json;
    } on FormatException {
      throw ApiFailure('invalid_response', response.statusCode);
    } on TypeError {
      throw ApiFailure('invalid_response', response.statusCode);
    }
    if (response.statusCode >= 400) {
      if (response.statusCode == 401) {
        token = null;
        user = null;
        await secure.delete(key: 'session:$server');
        notifyListeners();
      }
      throw ApiFailure(
        body['detail']?.toString() ?? 'request_failed',
        response.statusCode,
      );
    }
    return body;
  }

  Future<Json> get(String path, [Map<String, String>? query]) async {
    if (server.isEmpty) throw ApiFailure('configure_server', 400);
    final uri = Uri.parse('$server/api/v1/$path')
        .replace(queryParameters: query);
    try {
      return await decode(
        await client
            .get(uri, headers: headers)
            // Free hosting may need about a minute to wake after inactivity.
            // This only extends read waiting; mutations are never retried.
            .timeout(const Duration(seconds: 90)),
      );
    } on SocketException {
      throw ApiFailure('connection_failed', 0);
    } on TimeoutException {
      throw ApiFailure('timeout', 0);
    } on http.ClientException {
      throw ApiFailure('connection_failed', 0);
    }
  }

  Future<void> ensureConfig() async {
    if (config.isEmpty) config = await get('config');
  }

  Future<Json> action(
    String name,
    Json fields, {
    List<XFile> photos = const [],
    String photoField = 'photos',
  }) async {
    final uri = Uri.parse('$server/api/v1/actions/$name');
    http.Response response;
    try {
      if (photos.isEmpty) {
        response = await client
            .post(
              uri,
              headers: {...headers, 'Content-Type': 'application/json'},
              body: jsonEncode(fields),
            )
            .timeout(const Duration(seconds: 30));
      } else {
        final request = http.MultipartRequest('POST', uri)
          ..headers.addAll(headers);
        fields.forEach((key, value) {
          if (value != null) request.fields[key] = value.toString();
        });
        for (final photo in photos) {
          request.files.add(
            http.MultipartFile.fromBytes(
              photoField,
              await photo.readAsBytes(),
              filename: photo.name,
            ),
          );
        }
        response = await http.Response.fromStream(
          await client.send(request).timeout(const Duration(seconds: 45)),
        );
      }
    } on TimeoutException {
      throw ApiFailure('timeout', 0);
    } on SocketException {
      throw ApiFailure('connection_failed', 0);
    } on http.ClientException {
      throw ApiFailure('connection_failed', 0);
    }
    final result = await decode(response);
    if (name == 'login' || name == 'register') {
      token = result['token'];
      user = result['user'];
      await secure.write(key: 'session:$server', value: token);
    }
    changed();
    return result;
  }

  Future<Json> poll(int jobId, void Function(String) onStatus) async {
    final deadline = DateTime.now().add(const Duration(seconds: 75));
    while (DateTime.now().isBefore(deadline)) {
      final item = (await get('jobs/$jobId'))['item'] as Json;
      final status = item['status'] as String;
      onStatus(status);
      if (status == 'done') return item;
      if (status == 'failed') throw ApiFailure('ai_failed', 400);
      await Future<void>.delayed(const Duration(milliseconds: 750));
    }
    throw ApiFailure('job_still_running', 408);
  }

  Future<void> logout({bool localOnly = false}) async {
    if (!localOnly && token != null) await action('logout', {});
    await secure.delete(key: 'session:$server');
    token = null;
    user = null;
    changed();
  }

  void changed() {
    revision++;
    notifyListeners();
  }
}
