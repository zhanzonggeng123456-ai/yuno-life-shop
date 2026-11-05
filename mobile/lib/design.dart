import 'package:flutter/material.dart';

abstract final class YunoColors {
  static const primary = Color(0xff24304b);
  static const ink = Color(0xff25314a);
  static const muted = Color(0xff858894);
  static const paper = Color(0xfffaf7f1);
  static const sage = Color(0xfff0ece1);
  static const line = Color(0xffd8d2c5);
}

ThemeData yunoTheme() {
  final border = OutlineInputBorder(
    borderRadius: BorderRadius.zero,
    borderSide: const BorderSide(color: YunoColors.line),
  );
  return ThemeData(
    useMaterial3: true,
    colorScheme: ColorScheme.fromSeed(
      seedColor: YunoColors.primary,
      primary: YunoColors.primary,
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
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: const BorderSide(color: YunoColors.line)),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(0, 48),
        shape: const RoundedRectangleBorder(),
        textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(0, 46),
        side: const BorderSide(color: YunoColors.line),
        shape: const RoundedRectangleBorder(),
      ),
    ),
    listTileTheme: const ListTileThemeData(
      contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 5),
      iconColor: YunoColors.muted,
      titleTextStyle: TextStyle(fontSize: 14, color: YunoColors.ink),
      subtitleTextStyle: TextStyle(fontSize: 12, color: YunoColors.muted),
    ),
    navigationBarTheme: NavigationBarThemeData(
      height: 64,
      backgroundColor: Colors.white,
      surfaceTintColor: Colors.transparent,
      indicatorColor: Colors.transparent,
      labelTextStyle: WidgetStateProperty.resolveWith((states) => TextStyle(
            fontSize: 10,
            color: states.contains(WidgetState.selected)
                ? YunoColors.primary
                : YunoColors.muted,
            fontWeight: states.contains(WidgetState.selected)
                ? FontWeight.w600
                : FontWeight.w400,
          )),
      iconTheme: WidgetStateProperty.resolveWith((states) => IconThemeData(
          size: 21,
          color: states.contains(WidgetState.selected)
              ? YunoColors.primary
              : YunoColors.muted)),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: Colors.white,
      selectedColor: YunoColors.primary,
      showCheckmark: false,
      side: const BorderSide(color: YunoColors.line),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      labelStyle: const TextStyle(fontSize: 12),
      padding: const EdgeInsets.symmetric(horizontal: 3, vertical: 2),
    ),
    dividerTheme: const DividerThemeData(color: YunoColors.line, thickness: 1),
    bottomSheetTheme: const BottomSheetThemeData(
      showDragHandle: true,
      backgroundColor: YunoColors.paper,
    ),
  );
}
