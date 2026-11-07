// Opt-in test entry outside test/: its plugin state is always mocked.
// ignore_for_file: invalid_use_of_visible_for_testing_member

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:shop/main.dart' as shop;

import '../integration_test/device_full_test.dart' as flows;

class SimulationBinding extends LiveTestWidgetsFlutterBinding {
  @override
  bool get overrideHttpClient => false;
}

void main() {
  SimulationBinding();
  const rounds = int.fromEnvironment('YUNO_SIM_ROUNDS', defaultValue: 1);
  const firstRound = int.fromEnvironment('YUNO_SIM_FIRST', defaultValue: 1);
  const port = int.fromEnvironment('YUNO_SIM_PORT', defaultValue: 18766);
  const python = String.fromEnvironment('YUNO_SIM_PYTHON');
  final base = 'http://127.0.0.1:$port';
  if (python.isEmpty || port < 18766 || port > 18769) {
    throw StateError(
      'Provide a Python executable and a dedicated simulation port',
    );
  }

  setUp(() {
    final app = shop.appState;
    WidgetsBinding.instance.removeObserver(app);
    WidgetsBinding.instance.removeObserver(app);
    app.server = '';
    app.user = null;
    app.token = null;
    app.config = {};
    SharedPreferences.setMockInitialValues({});
    FlutterSecureStorage.setMockInitialValues({});
  });
  for (var i = firstRound; i < firstRound + rounds; i++) {
    final round = i;
    flows.registerNativeTradingTest(
      name: 'Isolated Flutter trading simulation round $round',
      hardware: false,
      startServer: () async {
        final data = await Directory.systemTemp.createTemp('yuno-sim-$round-');
        await File('${data.path}/.yuno-device-qa').writeAsString('simulation');
        final env = Map<String, String>.of(Platform.environment)
          ..removeWhere(
            (key, _) => RegExp(
              r'^(YUNO_|TURSO_)|^(HTTP_PROXY|HTTPS_PROXY|ALL_PROXY)$',
              caseSensitive: false,
            ).hasMatch(key),
          );
        final server = await Process.start(
          python,
          [
            '-m',
            'scripts.device_qa_server',
            '--data-dir',
            data.path,
            '--port',
            '$port',
          ],
          workingDirectory: Directory.current.parent.path,
          environment: env,
          includeParentEnvironment: false,
        );
        final logs = StringBuffer();
        server.stdout.transform(utf8.decoder).listen(logs.write);
        server.stderr.transform(utf8.decoder).listen(logs.write);
        var exited = false;
        server.exitCode.then((_) => exited = true);
        addTearDown(() async {
          server.kill();
          await server.exitCode.timeout(const Duration(seconds: 5));
        });
        final deadline = DateTime.now().add(const Duration(seconds: 15));
        while (!exited && DateTime.now().isBefore(deadline)) {
          try {
            final response = await http
                .get(Uri.parse('$base/healthz'))
                .timeout(const Duration(milliseconds: 600));
            if (response.statusCode == 200 &&
                logs.toString().contains('Uvicorn running on $base')) {
              return base;
            }
          } on Exception {
            // The fresh process has not bound its socket yet.
          }
          await Future<void>.delayed(const Duration(milliseconds: 100));
        }
        throw StateError('Isolated simulation server did not start: $logs');
      },
      report: (result) => stdout.writeln(
        'YUNO_SIM_RESULT ${jsonEncode({'round': round, ...result})}',
      ),
    );
  }
}
