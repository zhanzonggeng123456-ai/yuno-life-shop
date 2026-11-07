import 'package:flutter_test/flutter_test.dart';

import '../test/widget_test.dart' as widgets;

void main() {
  const rounds = int.fromEnvironment('YUNO_SIM_ROUNDS', defaultValue: 1);
  const first = int.fromEnvironment('YUNO_SIM_FIRST', defaultValue: 1);
  for (var round = first; round < first + rounds; round++) {
    group('YUNO widget simulation round $round', widgets.main);
  }
}
