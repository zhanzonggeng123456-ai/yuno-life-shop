import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'api.dart';
import 'screens.dart';

final appState = ShopState();

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await appState.initialize();
  runApp(const YunoApp());
}

class YunoApp extends StatelessWidget {
  const YunoApp({super.key});
  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: appState,
    builder: (context, _) => MaterialApp(
      title: 'YUNO LIFE SHOP',
      debugShowCheckedModeBanner: false,
      locale: Locale(appState.language),
      supportedLocales: const [Locale('zh'), Locale('ja')],
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff225947)),
        scaffoldBackgroundColor: const Color(0xfff5f5ef),
        cardTheme: const CardThemeData(
          color: Colors.white,
          elevation: 0,
          margin: EdgeInsets.symmetric(vertical: 6),
        ),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(),
          filled: true,
          fillColor: Colors.white,
        ),
      ),
      home: const HomeShell(),
    ),
  );
}
