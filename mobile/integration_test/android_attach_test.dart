// Attach/hot-restart entry for testing the installed Android debug APK.
// Explicitly register the real JNI implementation: this is not mock storage.
import 'package:shared_preferences_android/shared_preferences_android.dart';
import 'native_flow_test.dart' as flow;
import 'role_flow_test.dart' as roles;
import 'closure_flow_test.dart' as closure;
import 'settlement_flow_test.dart' as settlement;

void main() {
  SharedPreferencesAndroid.registerWith();
  switch (const String.fromEnvironment('ACCEPTANCE_SCENARIO')) {
    case 'roles':
      roles.main();
    case 'closure':
      closure.main();
    case 'settlement':
      settlement.main();
    default:
      flow.main();
  }
}
