import 'package:flutter/material.dart';

abstract final class YunoColors {
  static const ink = Color(0xff243b32);
  static const muted = Color(0xff778078);
  static const paper = Color(0xfff8f8f4);
  static const sage = Color(0xffeaf0e7);
  static const line = Color(0xffe5e8e1);
}

ThemeData yunoTheme() {
  final border = OutlineInputBorder(
    borderRadius: BorderRadius.circular(14),
    borderSide: const BorderSide(color: YunoColors.line),
  );
  return ThemeData(
    useMaterial3: true,
    colorScheme: ColorScheme.fromSeed(
      seedColor: const Color(0xff345b47),
      primary: YunoColors.ink,
      surface: Colors.white,
      onSurface: YunoColors.ink,
      outline: YunoColors.line,
    ),
    scaffoldBackgroundColor: YunoColors.paper,
    textTheme: const TextTheme(
      bodyLarge: TextStyle(fontSize: 15, height: 1.5),
      bodyMedium: TextStyle(fontSize: 14, height: 1.5),
      titleMedium: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 15),
      border: border,
      enabledBorder: border,
      focusedBorder: border.copyWith(
        borderSide: const BorderSide(color: YunoColors.ink, width: 1.2),
      ),
      labelStyle: const TextStyle(fontSize: 14, color: YunoColors.muted),
    ),
    cardTheme: CardThemeData(
      color: Colors.white,
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(0, 48),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(0, 46),
        side: const BorderSide(color: YunoColors.line),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
    ),
    listTileTheme: const ListTileThemeData(
      contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 5),
      iconColor: YunoColors.muted,
      titleTextStyle: TextStyle(fontSize: 14, color: YunoColors.ink),
      subtitleTextStyle: TextStyle(fontSize: 12, color: YunoColors.muted),
    ),
    navigationBarTheme: NavigationBarThemeData(
      height: 68,
      backgroundColor: Colors.white,
      surfaceTintColor: Colors.transparent,
      indicatorColor: YunoColors.sage,
      labelTextStyle: WidgetStateProperty.resolveWith((states) => TextStyle(
            fontSize: 10,
            color: states.contains(WidgetState.selected)
                ? YunoColors.ink
                : YunoColors.muted,
            fontWeight: states.contains(WidgetState.selected)
                ? FontWeight.w600
                : FontWeight.w400,
          )),
      iconTheme: WidgetStateProperty.all(const IconThemeData(size: 22)),
    ),
    dividerTheme: const DividerThemeData(color: YunoColors.line, thickness: 1),
    bottomSheetTheme: const BottomSheetThemeData(
      showDragHandle: true,
      backgroundColor: YunoColors.paper,
    ),
  );
}
