import 'dart:convert';
import 'dart:io';

import 'package:integration_test/integration_test_driver.dart';

Future<void> main() => integrationDriver(
  responseDataCallback: (data) async {
    final destination = Platform.environment['YUNO_DEVICE_REPORT'];
    if (destination != null) {
      await File(destination)
          .writeAsString(const JsonEncoder.withIndent('  ').convert(data));
    }
  },
);
