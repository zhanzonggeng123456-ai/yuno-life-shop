import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'api.dart';
import 'labels.dart';
import 'main.dart';

Future<T?> openPage<T>(BuildContext context, Widget page) =>
    Navigator.of(context).push<T>(MaterialPageRoute(builder: (_) => page));

String? itemName(Json item) {
  for (final key in [
    'title_${appState.language}',
    'title_ja',
    'title_zh',
    'name',
  ]) {
    final value = item[key];
    if (value is String && value.trim().isNotEmpty) return value;
  }
  return null;
}

int? draftReferencePrice(Json valuation) {
  final low = valuation['low'];
  final high = valuation['high'];
  if (valuation['kind'] != 'market' || low is! num || high is! num) return null;
  return ((low + high) / 2).round();
}

String money(dynamic value) => value == null
    ? '—'
    : '¥${value.toString().replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+(?!\d))'), (m) => '${m[1]},')}';

Widget heading(String title, [String? subtitle]) => Padding(
  padding: const EdgeInsets.symmetric(vertical: 16),
  child: Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        title,
        style: const TextStyle(
          fontSize: 28,
          fontWeight: FontWeight.w800,
          letterSpacing: -.7,
        ),
      ),
      if (subtitle != null)
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Text(
            subtitle,
            style: const TextStyle(color: Color(0xff66716a), height: 1.5),
          ),
        ),
    ],
  ),
);

class PageFrame extends StatelessWidget {
  final Widget child;
  final bool back;
  const PageFrame({super.key, required this.child, this.back = true});
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (back)
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: () => Navigator.of(context).pop(),
                icon: const Icon(Icons.arrow_back),
                label: Text(tx('返回', '戻る')),
              ),
            ),
          Expanded(child: child),
        ],
      ),
    ),
  );
}

class RemoteView extends StatefulWidget {
  final String path;
  final Map<String, String>? query;
  final Widget Function(Json) builder;
  const RemoteView({
    super.key,
    required this.path,
    this.query,
    required this.builder,
  });
  @override
  State<RemoteView> createState() => _RemoteViewState();
}

class _RemoteViewState extends State<RemoteView> {
  late Future<Json> future;
  @override
  void initState() {
    super.initState();
    reload();
  }

  void reload() {
    future = appState.get(widget.path, widget.query);
  }

  @override
  void didUpdateWidget(covariant RemoteView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.path != widget.path ||
        oldWidget.query.toString() != widget.query.toString()) {
      reload();
    }
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<Json>(
    future: future,
    builder: (context, snapshot) {
      if (snapshot.hasError) {
        return ErrorPanel(
          error: snapshot.error!,
          retry: () => setState(reload),
        );
      }
      if (!snapshot.hasData) {
        return Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const CircularProgressIndicator(),
              const SizedBox(height: 16),
              Text(tx('正在加载…', '読み込み中…')),
            ],
          ),
        );
      }
      return RefreshIndicator(
        onRefresh: () async {
          setState(reload);
          await future;
        },
        child: widget.builder(snapshot.data!),
      );
    },
  );
}

class ErrorPanel extends StatelessWidget {
  final Object error;
  final VoidCallback retry;
  const ErrorPanel({super.key, required this.error, required this.retry});
  @override
  Widget build(BuildContext context) => Center(
    child: SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          const Icon(
            Icons.wifi_off_rounded,
            size: 48,
            color: Color(0xff66716a),
          ),
          const SizedBox(height: 16),
          Text(errorText(error), textAlign: TextAlign.center),
          const SizedBox(height: 16),
          FilledButton(onPressed: retry, child: Text(tx('重试', '再試行'))),
        ],
      ),
    ),
  );
}

String errorText(Object error) {
  if (error is PlatformException) {
    if (RegExp('camera|photo|image|picker').hasMatch(error.code)) {
      return tx(
        '相机或相册暂时不可用，请检查系统权限，也可以选择相册入口。',
        'カメラ・アルバムを利用できません。システム権限を確認するか、アルバムから選択してください。',
      );
    }
    return tx('设备功能暂不可用，请检查系统权限后重试。', '端末機能を利用できません。システム権限を確認して再試行してください。');
  }
  if (error is ApiFailure) {
    if (words.containsKey(error.code)) return label(error.code);
    return '${tx('操作未成功，请检查输入与当前状态', '入力と現在の状態を確認してください')} (${error.status})';
  }
  return tx('连接中断，请稍后重试', '接続が中断されました。再試行してください');
}

String displayValue(String key, dynamic value) {
  if (value is bool) return value ? tx('是', 'はい') : tx('否', 'いいえ');
  if (key.contains('confidence') && ['low', 'medium', 'high'].contains(value)) {
    return {
      'low': tx('低', '低'),
      'medium': tx('中', '中'),
      'high': tx('高', '高'),
    }[value]!;
  }
  if (key == 'category_slug') {
    final matches = (appState.config['categories'] as List? ?? []).where(
      (c) => c['slug'] == value,
    );
    if (matches.isNotEmpty) return matches.first['name_${appState.language}'];
  }
  return words.containsKey(value.toString())
      ? label(value.toString())
      : value.toString();
}

Widget emptyState() => Padding(
  padding: const EdgeInsets.all(28),
  child: Column(
    children: [
      const Icon(
        Icons.inventory_2_outlined,
        size: 44,
        color: Color(0xff8a9b8d),
      ),
      const SizedBox(height: 12),
      Text(tx('暂时没有记录', 'まだデータがありません')),
    ],
  ),
);

Widget simulationNote() => Container(
  padding: const EdgeInsets.all(12),
  margin: const EdgeInsets.symmetric(vertical: 10),
  decoration: BoxDecoration(
    color: const Color(0xffffefd2),
    borderRadius: BorderRadius.circular(12),
  ),
  child: Text(
    tx('试用模式 · 支付与配送均为模拟，价格含税', '試用モード · 決済・配送は模擬、価格は税込です'),
    style: const TextStyle(fontSize: 12),
  ),
);

Widget panel(Widget child) => Card(
  child: Padding(padding: const EdgeInsets.all(16), child: child),
);

Widget infoData(dynamic data, {int depth = 0}) {
  if (data == null) return const Text('—');
  if (depth > 5) return const SizedBox.shrink();
  if (data is Map) {
    final entries = data.entries
        .where(
          (entry) =>
              ![
                'photos',
                'filename',
                'photo',
                'attrs_json',
                'payload',
                'poll_url',
              ].contains(entry.key) &&
              (!entry.key.toString().endsWith('_ja') ||
                  appState.language == 'ja') &&
              (!entry.key.toString().endsWith('_zh') ||
                  appState.language == 'zh') &&
              entry.value != null &&
              entry.value.toString().isNotEmpty,
        )
        .toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final entry in entries)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 5),
            child: entry.value is Map || entry.value is List
                ? Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        label(entry.key.toString()),
                        style: const TextStyle(fontWeight: FontWeight.w600),
                      ),
                      Padding(
                        padding: const EdgeInsets.only(left: 8, top: 6),
                        child: infoData(entry.value, depth: depth + 1),
                      ),
                    ],
                  )
                : Wrap(
                    spacing: 12,
                    runSpacing: 3,
                    children: [
                      Text(
                        label(entry.key.toString()),
                        style: const TextStyle(color: Color(0xff66716a)),
                      ),
                      Text(
                        displayValue(entry.key.toString(), entry.value),
                        style: const TextStyle(fontWeight: FontWeight.w500),
                      ),
                    ],
                  ),
          ),
      ],
    );
  }
  if (data is List) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final item in data)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: infoData(item, depth: depth + 1),
          ),
      ],
    );
  }
  return Text(
    words.containsKey(data.toString())
        ? label(data.toString())
        : data.toString(),
  );
}

class ProductPhotos extends StatelessWidget {
  final List<dynamic> photos;
  const ProductPhotos({super.key, required this.photos});
  @override
  Widget build(BuildContext context) {
    if (photos.isEmpty) {
      return Container(
        height: 200,
        alignment: Alignment.center,
        color: const Color(0xffe7ece3),
        child: const Icon(Icons.inventory_2_outlined, size: 56),
      );
    }
    return Column(
      children: [
        SizedBox(
          height: 290,
          child: PageView(
            children: [
              for (final photo in photos)
                GestureDetector(
                  onTap: () => openPage(
                    context,
                    PageFrame(
                      child: InteractiveViewer(
                        child: Image.network(
                          appState.imageUrl(photo['url']),
                          fit: BoxFit.contain,
                          errorBuilder: (_, _, _) =>
                              const Icon(Icons.broken_image_outlined),
                        ),
                      ),
                    ),
                  ),
                  child: Image.network(
                    appState.imageUrl(photo['url']),
                    fit: BoxFit.contain,
                    errorBuilder: (_, _, _) =>
                        const Icon(Icons.broken_image_outlined),
                  ),
                ),
            ],
          ),
        ),
        Text(
          tx('左右滑动查看全部 ${photos.length} 张照片', '左右にスワイプ・全 ${photos.length} 枚'),
        ),
      ],
    );
  }
}
