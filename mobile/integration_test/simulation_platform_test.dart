import 'package:integration_test/integration_test.dart';

import 'device_full_test.dart' as flows;

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  flows.registerNativeTradingTest(
    name: 'Native platform simulator trading flow',
    startServer: () async => const String.fromEnvironment('YUNO_SERVER'),
    hardware: false,
    report: (data) => binding.reportData = data,
  );
}
