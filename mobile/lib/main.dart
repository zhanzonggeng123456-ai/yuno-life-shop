import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:image_picker/image_picker.dart';

import 'session.dart';
import 'labels.dart';
import 'design.dart';
import 'market_home.dart';

final session = Session();
void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const YunoApp());
}

class YunoApp extends StatefulWidget {
  const YunoApp({super.key});
  @override
  State<YunoApp> createState() => _YunoAppState();
}

class _YunoAppState extends State<YunoApp> {
  late Future<void> ready;
  @override
  void initState() {
    super.initState();
    ready = session.init();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
        animation: session,
        builder: (context, _) => MaterialApp(
          debugShowCheckedModeBanner: false,
          title: 'Yuno Life',
          locale: Locale(session.zh ? 'zh' : 'ja'),
          supportedLocales: const [Locale('zh'), Locale('ja')],
          localizationsDelegates: GlobalMaterialLocalizations.delegates,
          theme: yunoTheme(),
          home: FutureBuilder(
            future: ready,
            builder: (context, snapshot) {
              if (snapshot.connectionState != ConnectionState.done) {
                return const Scaffold(
                  body: Center(child: CircularProgressIndicator()),
                );
              }
              if (snapshot.hasError) {
                return Scaffold(
                  body: SafeArea(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Text(
                            'Yuno Life',
                            style: TextStyle(
                              fontSize: 32,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 24),
                          Text(
                            session.tr(
                              '暂时无法连接平台。请确认 Mac 后端正在运行，手机与 Mac 位于同一网络。',
                              '接続できません。Mac のサーバーと同一ネットワークを確認してください。',
                            ),
                          ),
                          const SizedBox(height: 16),
                          ConnectionForm(
                            onSaved: () {
                              setState(() {
                                ready = session.bootstrap();
                              });
                            },
                          ),
                          TextButton(
                            onPressed: () {
                              setState(() {
                                ready = session.bootstrap();
                              });
                            },
                            child: Text(session.tr('重试', '再試行')),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              }
              return const HomeShell();
            },
          ),
        ),
      );
}

void notify(BuildContext context, String text) {
  if (context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }
}

String failure(Object? error) {
  if (error is ApiError) {
    if (error.status == 401) return session.tr('登录已过期，请重新登录。', 'ログインが必要です。');
    if (error.status == 403) return session.tr('你没有此操作权限。', 'この操作の権限がありません。');
    if (error.status == 429) {
      return session.tr('操作频繁，请稍后重试。', '操作回数が多すぎます。時間をおいて再試行してください。');
    }
    if (error.status == 422 || error.status == 400) {
      return session.tr('信息不符合要求，请检查必填项、金额和图片格式。', '入力内容・金額・画像形式を確認してください。');
    }
    if (error.status == 404) return session.tr('此内容已不存在。', '内容が見つかりません。');
    return session.tr('操作未完成，请刷新状态后重试。', '操作できませんでした。状態を確認して再試行してください。');
  }
  return session.tr('网络连接失败，请重试。', '接続に失敗しました。再試行してください。');
}

Future<void> open(BuildContext context, Widget page) async {
  await Navigator.of(context).push(MaterialPageRoute(builder: (_) => page));
}

Future<bool> ensureLogin(BuildContext context) async {
  if (session.signedIn) return true;
  await open(context, const AuthPage());
  return session.signedIn;
}

Widget heading(String title, {String? subtitle}) => Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
                fontSize: 19,
                height: 1.3,
                fontFamily: 'YunoSerif',
                fontFamilyFallback: ['Songti SC', 'serif'],
                fontWeight: FontWeight.w700),
          ),
          if (subtitle != null)
            Text(subtitle, style: TextStyle(color: Colors.grey.shade700)),
        ],
      ),
    );
Widget simulation() => Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.science_outlined, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              session.tr(
                '价格含税 · 支付与物流均为模拟，不会产生真实扣款。',
                '税込価格・決済と配送は模擬です。実際の請求は発生しません。',
              ),
              style: const TextStyle(fontSize: 12),
            ),
          ),
        ],
      ),
    );
Widget empty() => Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        children: [
          const Icon(Icons.inventory_2_outlined, size: 42),
          const SizedBox(height: 12),
          Text(session.tr('暂无记录', '記録はありません')),
        ],
      ),
    );
Widget imageView(
  String url, {
  double? width,
  double height = 180,
  BoxFit fit = BoxFit.cover,
}) =>
    Image.network(
      session.photo(url),
      width: width,
      height: height,
      fit: fit,
      errorBuilder: (_, e, st) => SizedBox(
        height: height,
        width: width,
        child: const Icon(Icons.image_not_supported_outlined),
      ),
    );

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});
  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int tab = 0;
  @override
  Widget build(BuildContext context) => AnimatedBuilder(
      animation: session,
      builder: (context, _) => Scaffold(
            body: SafeArea(
              child: KeyedSubtree(
                key: ValueKey('$tab-${session.language}-${session.signedIn}'),
                child: [
                  MarketHome(
                    api: session,
                    onTrends: () => setState(() => tab = 1),
                    onBrowse: () => open(
                        context,
                        PageFrame(
                            title: session.tr('在售闲置', '出品中の商品'),
                            child: const MarketPage())),
                    onPublish: () => launchPublish(context),
                    onListing: (item) => open(
                        context,
                        DetailPage(
                            path: '/listings/${item['id']}',
                            title: session.title(item))),
                    onAuction: (item) => open(
                        context,
                        DetailPage(
                            path: '/auctions/${item['id']}',
                            title: session.title(item))),
                    card: (item) => ListingCard(item: item),
                    onFavorite: (item) async {
                      if (!await ensureLogin(context)) return;
                      final followed = (session.me?['following'] as List? ?? [])
                          .any((i) => i['id'] == item['id']);
                      await session.post(
                          '/listings/${item['id']}/${followed ? 'unfollow' : 'follow'}',
                          {});
                      await session.refreshMe();
                    },
                  ),
                  const TrendsPage(),
                  const TradePage(),
                  const OrdersPage(),
                  const ProfilePage(),
                ][tab],
              ),
            ),
            bottomNavigationBar: DecoratedBox(
              decoration: const BoxDecoration(
                  border: Border(top: BorderSide(color: YunoColors.line))),
              child: NavigationBar(
                selectedIndex: tab,
                onDestinationSelected: (i) {
                  if (i == 2) {
                    showModalBottomSheet(
                        context: context,
                        isScrollControlled: true,
                        backgroundColor: Colors.white,
                        showDragHandle: false,
                        shape: const RoundedRectangleBorder(
                            borderRadius: BorderRadius.vertical(
                                top: Radius.circular(20))),
                        builder: (_) => TradeMenu(hostContext: context));
                  } else {
                    setState(() => tab = i);
                  }
                },
                destinations: [
                  NavigationDestination(
                    icon: const Icon(Icons.home_outlined),
                    label: session.tr('市场', '市場'),
                  ),
                  NavigationDestination(
                    icon: const Icon(Icons.bar_chart_outlined),
                    label: session.tr('成交行情', '相場'),
                  ),
                  NavigationDestination(
                    icon: SizedBox(
                        width: 50,
                        height: 24,
                        child: OverflowBox(
                            minHeight: 50,
                            maxHeight: 50,
                            minWidth: 50,
                            maxWidth: 50,
                            child: Transform.translate(
                                offset: const Offset(0, -12),
                                child: Container(
                                    width: 50,
                                    height: 50,
                                    decoration: BoxDecoration(
                                        color: YunoColors.primary,
                                        shape: BoxShape.circle,
                                        border: Border.all(
                                            color: Colors.white, width: 3),
                                        boxShadow: const [
                                          BoxShadow(
                                              color: Color(0x33000000),
                                              blurRadius: 12,
                                              offset: Offset(0, 3))
                                        ]),
                                    child: const Icon(Icons.swap_horiz,
                                        color: Colors.white, size: 25))))),
                    label: session.tr('交易', '取引'),
                  ),
                  NavigationDestination(
                    icon: Badge.count(
                        count: (session.me?['orders'] as List? ?? []).length,
                        isLabelVisible:
                            (session.me?['orders'] as List? ?? []).isNotEmpty,
                        child: const Icon(Icons.receipt_long_outlined)),
                    label: session.tr('订单', '注文'),
                  ),
                  NavigationDestination(
                    icon: const Icon(Icons.person_outline),
                    label: session.tr('个人中心', 'マイページ'),
                  ),
                ],
              ),
            ),
          ));
}

Widget badge(String text, {bool warning = false}) => Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
          color: warning ? const Color(0xfffff2db) : const Color(0xffedf1ef),
          borderRadius: BorderRadius.circular(20)),
      child: Text(text,
          style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: warning ? const Color(0xffa86c22) : YunoColors.muted)),
    );

String regionLabel(dynamic code) {
  for (final r in session.config['regions'] ?? []) {
    if (r['code'] == code) return session.name(Map<String, dynamic>.from(r));
  }
  return '$code';
}

String categoryLabel(Json category) {
  const short = {
    'furniture': ['家具家居', '家具'],
    'appliance': ['家电', '家電'],
    'digital': ['手机数码', 'スマホ・デジタル'],
    'watch': ['手表', '時計'],
    'coin': ['钱币收藏', 'コイン'],
    'figure': ['模型玩具', '模型・玩具'],
    'camera': ['相机', 'カメラ'],
    'antique': ['古董艺术', '骨董・美術'],
    'instrument': ['乐器音响', '楽器・音響'],
    'book': ['书籍媒体', '本・メディア'],
    'fashion': ['服饰箱包', '服・バッグ'],
    'tool': ['工具运动户外', '工具・アウトドア'],
    'other': ['其他', 'その他'],
  };
  final pair = short[category['slug']];
  return pair == null ? session.name(category) : session.tr(pair[0], pair[1]);
}

Widget filterChip(String label, bool selected, VoidCallback onTap) =>
    ChoiceChip(
      label: Text(label),
      selected: selected,
      showCheckmark: false,
      labelStyle: TextStyle(
          fontSize: 12, color: selected ? Colors.white : YunoColors.ink),
      selectedColor: YunoColors.primary,
      backgroundColor: Colors.white,
      side: BorderSide(color: selected ? YunoColors.primary : YunoColors.line),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      onSelected: (_) => onTap(),
    );

class PageFrame extends StatelessWidget {
  final String title;
  final Widget child;
  const PageFrame({super.key, required this.title, required this.child});
  @override
  Widget build(BuildContext context) => Scaffold(
        body: SafeArea(
          child: Column(
            children: [
              Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                child: Row(
                  children: [
                    IconButton(
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.arrow_back),
                      tooltip: session.tr('返回', '戻る'),
                    ),
                    Expanded(
                      child: Text(
                        title,
                        style: const TextStyle(
                          fontSize: 20,
                          height: 1.3,
                          fontFamily: 'YunoSerif',
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              Expanded(child: child),
            ],
          ),
        ),
      );
}

class LoadView extends StatefulWidget {
  final Future<Json> Function() load;
  final Widget Function(BuildContext, Json, VoidCallback) builder;
  const LoadView({super.key, required this.load, required this.builder});
  @override
  State<LoadView> createState() => _LoadViewState();
}

class _LoadViewState extends State<LoadView> {
  late Future<Json> value;
  @override
  void initState() {
    super.initState();
    value = widget.load();
  }

  void reload() {
    setState(() => value = widget.load());
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<Json>(
        future: value,
        builder: (context, s) {
          if (s.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (s.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(failure(s.error)),
                    TextButton(
                      onPressed: reload,
                      child: Text(session.tr('重试', '再試行')),
                    ),
                  ],
                ),
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: () async {
              reload();
              await value;
            },
            child: widget.builder(context, s.data!, reload),
          );
        },
      );
}

class MarketPage extends StatefulWidget {
  const MarketPage({super.key});
  @override
  State<MarketPage> createState() => _MarketPageState();
}

class _MarketPageState extends State<MarketPage> {
  final query = TextEditingController(),
      min = TextEditingController(),
      max = TextEditingController();
  String category = '', region = '';
  bool platform = false;
  int version = 0;
  @override
  void dispose() {
    query.dispose();
    min.dispose();
    max.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => LoadView(
        key: ValueKey(version),
        load: () => session.get(
          '/listings?${Uri(queryParameters: {
                'q': query.text,
                'category': category,
                'region': region,
                'price_min': min.text.isEmpty ? '0' : min.text,
                'price_max': max.text.isEmpty ? '1000000000' : max.text,
                'only_platform': '$platform'
              }).query}',
        ),
        builder: (context, data, reload) {
          final items = List<Json>.from(data['items']);
          return ListView(
            padding: const EdgeInsets.all(14),
            children: [
              Row(children: [
                Expanded(
                    child: TextField(
                  controller: query,
                  onSubmitted: (_) => setState(() => version++),
                  decoration: InputDecoration(
                    prefixIcon: const Icon(Icons.search),
                    hintText: session.tr('搜手表、冰箱、相机…', '時計・冷蔵庫・カメラを検索…'),
                    hintStyle:
                        const TextStyle(fontSize: 14, color: YunoColors.muted),
                    suffixIcon: IconButton(
                      icon: const Icon(Icons.tune),
                      onPressed: () async {
                        await showModalBottomSheet(
                          context: context,
                          isScrollControlled: true,
                          builder: (context) => StatefulBuilder(
                            builder: (context, setModal) => Padding(
                              padding: EdgeInsets.fromLTRB(
                                20,
                                24,
                                20,
                                MediaQuery.viewInsetsOf(context).bottom + 24,
                              ),
                              child: SingleChildScrollView(
                                child: Column(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    DropdownButtonFormField<String>(
                                      initialValue: category,
                                      items: [
                                        DropdownMenuItem(
                                          value: '',
                                          child: Text(
                                              session.tr('全部分类', 'すべてのカテゴリ')),
                                        ),
                                        for (final c
                                            in session.config['categories'] ??
                                                [])
                                          DropdownMenuItem(
                                            value: '${c['slug']}',
                                            child: Text(
                                              session.name(c),
                                              overflow: TextOverflow.ellipsis,
                                            ),
                                          ),
                                      ],
                                      isExpanded: true,
                                      onChanged: (v) =>
                                          setModal(() => category = v ?? ''),
                                    ),
                                    DropdownButtonFormField<String>(
                                      initialValue: region,
                                      items: [
                                        DropdownMenuItem(
                                          value: '',
                                          child: Text(
                                              session.tr('全部地区', 'すべての地域')),
                                        ),
                                        for (final r
                                            in (session.config['regions'] ?? [])
                                                .where(
                                          (dynamic r) =>
                                              r['active'] == true ||
                                              r['active'] == 1,
                                        ))
                                          DropdownMenuItem(
                                            value: '${r['code']}',
                                            child: Text(session.name(r)),
                                          ),
                                      ],
                                      onChanged: (v) =>
                                          setModal(() => region = v ?? ''),
                                    ),
                                    const SizedBox(height: 12),
                                    Row(
                                      children: [
                                        Expanded(
                                          child: TextField(
                                            controller: min,
                                            keyboardType: TextInputType.number,
                                            decoration: InputDecoration(
                                              labelText:
                                                  session.tr('最低价', '最低価格'),
                                            ),
                                          ),
                                        ),
                                        const SizedBox(width: 12),
                                        Expanded(
                                          child: TextField(
                                            controller: max,
                                            keyboardType: TextInputType.number,
                                            decoration: InputDecoration(
                                              labelText:
                                                  session.tr('最高价', '最高価格'),
                                            ),
                                          ),
                                        ),
                                      ],
                                    ),
                                    SwitchListTile(
                                      title:
                                          Text(session.tr('仅平台自营', '自社商品のみ')),
                                      value: platform,
                                      onChanged: (v) =>
                                          setModal(() => platform = v),
                                    ),
                                    FilledButton(
                                      onPressed: () => Navigator.pop(context),
                                      child: Text(session.tr('应用筛选', '適用')),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        );
                        if (mounted) setState(() => version++);
                      },
                    ),
                  ),
                )),
                const SizedBox(width: 8),
                FilledButton(
                    onPressed: () => setState(() => version++),
                    style: FilledButton.styleFrom(
                        shape: const StadiumBorder(),
                        minimumSize: const Size(64, 48),
                        padding: const EdgeInsets.symmetric(horizontal: 16)),
                    child: Text(session.tr('搜索', '検索'))),
              ]),
              const SizedBox(height: 10),
              Wrap(spacing: 7, runSpacing: 0, children: [
                for (final c in <Json>[
                  {'slug': '', 'name_zh': '全部', 'name_ja': 'すべて'},
                  ...List<Json>.from(session.config['categories'] ?? [])
                ])
                  filterChip(
                      categoryLabel(c),
                      category == c['slug'],
                      () => setState(() {
                            category = c['slug'];
                            version++;
                          })),
              ]),
              const SizedBox(height: 10),
              if (items.isEmpty) empty(),
              LayoutBuilder(builder: (context, constraints) {
                final columns = constraints.maxWidth < 300 ? 1 : 2;
                final cardWidth =
                    (constraints.maxWidth - (columns - 1) * 12) / columns;
                return GridView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: items.length,
                  gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: columns,
                    crossAxisSpacing: 12,
                    mainAxisSpacing: 12,
                    mainAxisExtent: cardWidth / 1.05 +
                        150 * MediaQuery.textScalerOf(context).scale(14) / 14,
                  ),
                  itemBuilder: (_, i) =>
                      ListingCard(item: items[i], onReturn: reload),
                );
              }),
              simulation(),
            ],
          );
        },
      );
}

class ListingCard extends StatelessWidget {
  final Json item;
  final VoidCallback? onReturn;
  const ListingCard({super.key, required this.item, this.onReturn});
  @override
  Widget build(BuildContext context) {
    final photos = List<Json>.from(item['photos'] ?? []);
    return Card(
      margin: EdgeInsets.zero,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () async {
          await open(
              context,
              DetailPage(
                  path: '/listings/${item['id']}', title: session.title(item)));
          onReturn?.call();
        },
        child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize: MainAxisSize.min,
            children: [
              AspectRatio(
                  aspectRatio: 1.05,
                  child: Stack(fit: StackFit.expand, children: [
                    if (photos.isNotEmpty)
                      imageView(photos.first['url'])
                    else
                      Container(
                          color: const Color(0xffeef0e9),
                          child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                const Icon(Icons.photo_camera_outlined,
                                    size: 28, color: Color(0xffa2ae9f)),
                                const SizedBox(height: 7),
                                Text(session.tr('暂无实拍', '写真は未登録'),
                                    style: const TextStyle(
                                        fontSize: 10, color: YunoColors.muted)),
                              ])),
                    if (item['demo'] == 1 || item['is_platform_owned'] == 1)
                      Positioned(
                          top: 10,
                          left: 10,
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 7, vertical: 3),
                            decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.93),
                                borderRadius: BorderRadius.circular(6)),
                            child: Text(
                                item['demo'] == 1
                                    ? 'DEMO'
                                    : session.tr('平台自营', '自社販売'),
                                style: const TextStyle(
                                    fontSize: 9, fontWeight: FontWeight.w600)),
                          )),
                    if (photos.length > 1)
                      Positioned(
                          bottom: 8,
                          right: 8,
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                                color: Colors.black45,
                                borderRadius: BorderRadius.circular(6)),
                            child: Text('${photos.length}',
                                style: const TextStyle(
                                    color: Colors.white, fontSize: 10)),
                          )),
                  ])),
              Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(session.title(item),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                                fontSize: 14,
                                height: 1.4,
                                fontWeight: FontWeight.w700)),
                        const SizedBox(height: 8),
                        Text(yen(item['effective_price'] ?? item['price']),
                            style: const TextStyle(
                                fontSize: 18,
                                color: YunoColors.ink,
                                letterSpacing: -0.3,
                                fontWeight: FontWeight.w600)),
                        const SizedBox(height: 3),
                        Wrap(spacing: 5, runSpacing: 4, children: [
                          badge(status(session, item['condition_grade'])),
                          if (item['category_id'] != null)
                            for (final c in session.config['categories'] ?? [])
                              if (c['id'] == item['category_id'])
                                badge(categoryLabel(
                                    Map<String, dynamic>.from(c))),
                        ]),
                        const SizedBox(height: 5),
                        Text(regionLabel(item['region']),
                            style: const TextStyle(
                                fontSize: 11, color: YunoColors.muted)),
                      ])),
            ]),
      ),
    );
  }
}

class AuthPage extends StatefulWidget {
  const AuthPage({super.key});
  @override
  State<AuthPage> createState() => _AuthPageState();
}

class _AuthPageState extends State<AuthPage> {
  final email = TextEditingController(),
      password = TextEditingController(),
      name = TextEditingController();
  bool register = false, busy = false;
  String? error;
  @override
  void dispose() {
    email.dispose();
    password.dispose();
    name.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PageFrame(
        title: session.tr('账号', 'アカウント'),
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            heading(
              register
                  ? session.tr('创建账号', '新規登録')
                  : session.tr('欢迎回来', 'おかえりなさい'),
            ),
            TextField(
              controller: email,
              keyboardType: TextInputType.emailAddress,
              autocorrect: false,
              decoration: InputDecoration(labelText: label(session, 'email')),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: password,
              obscureText: true,
              autocorrect: false,
              enableSuggestions: false,
              decoration: InputDecoration(
                labelText: label(session, 'password'),
                helperText: session.tr('至少 8 位', '8文字以上'),
              ),
            ),
            if (register) ...[
              const SizedBox(height: 16),
              TextField(
                controller: name,
                decoration: InputDecoration(
                  labelText: label(session, 'display_name'),
                ),
              ),
            ],
            if (error != null)
              Text(error!, style: const TextStyle(color: Colors.red)),
            const SizedBox(height: 20),
            FilledButton(
              onPressed: busy
                  ? null
                  : () async {
                      setState(() => busy = true);
                      try {
                        await session.authenticate(register, {
                          'email': email.text.trim(),
                          'password': password.text,
                          'display_name': name.text.trim(),
                        });
                        if (context.mounted) Navigator.pop(context);
                      } catch (e) {
                        if (mounted) setState(() => error = failure(e));
                      } finally {
                        if (mounted) setState(() => busy = false);
                      }
                    },
              child: busy
                  ? const CircularProgressIndicator()
                  : Text(
                      register
                          ? session.tr('注册', '登録')
                          : session.tr('登录', 'ログイン'),
                    ),
            ),
            TextButton(
              onPressed:
                  busy ? null : () => setState(() => register = !register),
              child: Text(
                register
                    ? session.tr('已有账号，去登录', 'ログインへ')
                    : session.tr('注册新账号', '新規登録へ'),
              ),
            ),
            simulation(),
          ],
        ),
      );
}

class CommandForm extends StatefulWidget {
  final Json action;
  final VoidCallback? done;
  const CommandForm({super.key, required this.action, this.done});
  @override
  State<CommandForm> createState() => _CommandFormState();
}

class _CommandFormState extends State<CommandForm> {
  final form = GlobalKey<FormState>();
  final values = <String, TextEditingController>{};
  final attachments = <XFile>[];
  bool busy = false;
  String? error;
  @override
  void initState() {
    super.initState();
    for (final entry in (widget.action['fields'] as Map? ?? {}).entries) {
      values['${entry.key}'] = TextEditingController(
        text: '${entry.value['default'] ?? ''}',
      );
    }
    if (values.containsKey('idempotency_key')) {
      values['idempotency_key']!.text =
          'mobile-${DateTime.now().microsecondsSinceEpoch}';
    }
  }

  @override
  void dispose() {
    for (final c in values.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> date(String key) async {
    final now = DateTime.now();
    final day = await showDatePicker(
      context: context,
      firstDate: now,
      lastDate: now.add(const Duration(days: 365)),
      initialDate: now,
    );
    if (day == null || !mounted) return;
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.now(),
    );
    if (time == null) return;
    values[key]!.text = DateTime(
      day.year,
      day.month,
      day.day,
      time.hour,
      time.minute,
    ).toUtc().toIso8601String();
  }

  @override
  Widget build(BuildContext context) {
    final fields = Map<String, dynamic>.from(widget.action['fields'] ?? {});
    final path = '${widget.action['path']}';
    return PageFrame(
      title: session.local(widget.action['label']),
      child: Form(
        key: form,
        child: ListView(
          padding: const EdgeInsets.all(14),
          children: [
            simulation(),
            for (final e in fields.entries)
              if (!['idempotency_key', 'receiver_id'].contains(e.key))
                Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: field(e.key, e.value),
                ),
            if (path.startsWith('/deliveries/') &&
                (path.contains('/pickup') || path.contains('/deliver'))) ...[
              Text(session.tr('可添加取货或交付照片', '集荷・配達写真を追加できます')),
              TextButton.icon(
                onPressed: busy
                    ? null
                    : () async {
                        try {
                          final p = await ImagePicker().pickImage(
                            source: ImageSource.camera,
                            preferredCameraDevice: CameraDevice.rear,
                            imageQuality: 85,
                          );
                          if (p != null && mounted) {
                            setState(
                              () => attachments
                                ..clear()
                                ..add(p),
                            );
                          }
                        } catch (e) {
                          if (context.mounted) notify(context, failure(e));
                        }
                      },
                icon: const Icon(Icons.camera_alt_outlined),
                label: Text(session.tr('拍照', '撮影')),
              ),
              for (final p in attachments)
                Image.file(File(p.path), height: 160),
            ],
            if (error != null)
              Text(error!, style: const TextStyle(color: Colors.red)),
            FilledButton(
              onPressed: busy
                  ? null
                  : () async {
                      if (!form.currentState!.validate()) return;
                      setState(() => busy = true);
                      try {
                        final data = <String, dynamic>{
                          for (final e in values.entries) e.key: e.value.text,
                        };
                        final result = attachments.isEmpty
                            ? await session.post(path, data)
                            : await session.upload(
                                path,
                                data,
                                attachments,
                                field: 'photo',
                              );
                        if (context.mounted) {
                          widget.done?.call();
                          Navigator.pop(context, result);
                        }
                      } catch (e) {
                        if (mounted) setState(() => error = failure(e));
                      } finally {
                        if (mounted) setState(() => busy = false);
                      }
                    },
              child: busy
                  ? const CircularProgressIndicator()
                  : Text(session.tr('确认提交', '確認して送信')),
            ),
          ],
        ),
      ),
    );
  }

  Widget field(String key, Json meta) {
    final control = values[key]!;
    final isDate = ['ends_at', 'scheduled_at', 'pickup_at'].contains(key);
    List<String>? options;
    if (key == 'rating') options = ['1', '2', '3', '4', '5'];
    if (key == 'role') {
      options = [
        'user',
        'collector',
        'operator',
        'appraiser',
        'courier',
        'admin',
      ];
    }
    if (key == 'decision') options = ['approved', 'rejected'];
    if (key == 'kind' &&
        '${widget.action['path']}'.contains('delivery-request')) {
      options = ['buyer_delivery', 'seller_pickup'];
    }
    if (key == 'appraisal_status') {
      options = ['approved', 'rejected', 'pending'];
    }
    if (options != null) {
      return DropdownButtonFormField<String>(
        initialValue: options.contains(control.text) ? control.text : null,
        decoration: InputDecoration(labelText: label(session, key)),
        items: [
          for (final option in options)
            DropdownMenuItem(
              value: option,
              child: Text(status(session, option)),
            ),
        ],
        onChanged: (v) => control.text = v ?? '',
        validator: (v) => meta['required'] == true && (v == null || v.isEmpty)
            ? session.tr('必填', '必須')
            : null,
      );
    }
    return TextFormField(
      controller: control,
      readOnly: isDate,
      onTap: isDate ? () => date(key) : null,
      keyboardType: meta['type'] == 'number'
          ? const TextInputType.numberWithOptions(decimal: true)
          : TextInputType.text,
      maxLines: [
        'note',
        'reason',
        'evidence',
        'body',
        'comment',
        'inspection_note',
        'decision_note',
      ].contains(key)
          ? 3
          : 1,
      decoration: InputDecoration(
        labelText: label(session, key),
        suffixIcon: isDate ? const Icon(Icons.calendar_today) : null,
      ),
      validator: (v) {
        if (meta['required'] == true && (v ?? '').trim().isEmpty) {
          return session.tr('必填', '必須');
        }
        if (meta['type'] == 'number' &&
            v != null &&
            v.isNotEmpty &&
            num.tryParse(v) == null) {
          return session.tr('请输入数字', '数値を入力');
        }
        return null;
      },
    );
  }
}

Future<Json?> runCommand(BuildContext context, Json action,
    {bool openResult = false}) async {
  if (!await ensureLogin(context) || !context.mounted) return null;
  final result = await Navigator.push<Json>(
    context,
    MaterialPageRoute(builder: (_) => CommandForm(action: action)),
  );
  if (result != null && context.mounted) {
    notify(context, session.tr('已提交，请核对最新状态。', '送信しました。最新状態を確認してください。'));
    final next = '${result['next'] ?? ''}';
    if (openResult &&
        RegExp(r'^/(orders|buyback|services|deliveries|refunds|disputes|auctions)/\d+$')
            .hasMatch(next)) {
      await open(
          context, DetailPage(path: next, title: session.tr('详情', '詳細')));
    }
  }
  return result;
}

class DetailPage extends StatelessWidget {
  final String path, title;
  const DetailPage({super.key, required this.path, required this.title});
  @override
  Widget build(BuildContext context) => PageFrame(
        title: title.isEmpty ? session.tr('详情', '詳細') : title,
        child: LoadView(
          load: () => session.get(path),
          builder: (context, data, reload) {
            final item =
                path.startsWith('/listings/') ? data : data['listing'] as Json?;
            final photos = List<Json>.from(item?['photos'] ?? []);
            final money = [
              'price',
              'effective_price',
              'goods_amount',
              'commission',
              'delivery_fee',
              'total',
              'current_price',
              'minimum_bid',
              'quote',
              'acquisition_cost',
              'amount',
              'unit_price',
            ];
            return ListView(
              padding: const EdgeInsets.all(14),
              children: [
                if (photos.isNotEmpty)
                  SizedBox(
                    height: 260,
                    child: PageView(
                      children: [
                        for (final photo in photos)
                          GestureDetector(
                            onTap: () => open(
                              context,
                              PageFrame(
                                title: session.tr('照片预览', '写真プレビュー'),
                                child: InteractiveViewer(
                                  child: imageView(
                                    photo['url'],
                                    height: 600,
                                    fit: BoxFit.contain,
                                  ),
                                ),
                              ),
                            ),
                            child: imageView(
                              photo['url'],
                              height: 260,
                              fit: BoxFit.contain,
                            ),
                          ),
                      ],
                    ),
                  ),
                if (photos.length > 1)
                  Text(
                    session.tr(
                      '左右滑动查看全部 ${photos.length} 张照片',
                      'スワイプして ${photos.length} 枚の写真を表示',
                    ),
                  ),
                if (item != null) heading(session.title(item)),
                if (item != null && item['demo'] == 1)
                  const Chip(label: Text('DEMO')),
                if (item != null)
                  Text(
                    '${item[session.zh ? 'desc_zh' : 'desc_ja'] ?? item['desc_ja'] ?? ''}',
                  ),
                simulation(),
                for (final key in [
                  'status',
                  'condition_grade',
                  ...money,
                  'starts_at',
                  'ends_at',
                  'scheduled_at',
                  'pickup_at',
                  'inspection_note',
                  'decision',
                  'decision_note',
                  'reason',
                  'evidence',
                  'comment',
                  'rating',
                  'hours',
                  'qty',
                  'note',
                  'created_at',
                ])
                  if (data[key] != null && '${data[key]}'.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(child: Text(label(session, key))),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              money.contains(key)
                                  ? yen(data[key])
                                  : status(session, data[key]),
                              textAlign: TextAlign.end,
                            ),
                          ),
                        ],
                      ),
                    ),
                if (item?['attrs'] is Map)
                  for (final e in (item!['attrs'] as Map).entries)
                    Text('${label(session, '${e.key}')}: ${e.value}'),
                if (data['review'] != null)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Text(
                        session.tr(
                          '高价值商品需人工审核，审核通过前不可交易。',
                          '高額商品は手動審査が必要です。承認まで取引できません。',
                        ),
                      ),
                    ),
                  ),
                if (data['bids'] is List) ...[
                  heading(session.tr('竞拍记录', '入札履歴')),
                  for (final bid in data['bids'])
                    ListTile(
                      title: Text(yen(bid['amount'])),
                      subtitle: Text('${bid['created_at']}'),
                    ),
                ],
                if (item != null && session.me?['id'] == item['seller_id'])
                  OutlinedButton.icon(
                    onPressed: () async {
                      await open(context, PhotoManager(lid: item['id']));
                      reload();
                    },
                    icon: const Icon(Icons.photo_library_outlined),
                    label: Text(session.tr('管理商品照片', '商品写真の管理')),
                  ),
                if (item != null && data['thread_buyer_id'] != null)
                  OutlinedButton.icon(
                    onPressed: () async {
                      if (await ensureLogin(context) && context.mounted) {
                        await open(
                          context,
                          ChatPage(
                              lid: item['id'], bid: data['thread_buyer_id']),
                        );
                      }
                    },
                    icon: const Icon(Icons.chat_bubble_outline),
                    label: Text(session.tr('联系卖家', '出品者に連絡')),
                  ),
                for (final a in data['actions'] ?? [])
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 5),
                    child: FilledButton.tonal(
                      onPressed: () async {
                        final result = await runCommand(
                          context,
                          Map<String, dynamic>.from(a),
                        );
                        if (result != null && context.mounted) {
                          final next = '${result['next'] ?? ''}';
                          if (RegExp(
                                r'^/(orders|buyback|services|deliveries|refunds|disputes|auctions)/\d+$',
                              ).hasMatch(next) &&
                              next != path) {
                            await open(
                              context,
                              DetailPage(
                                  path: next, title: session.tr('详情', '詳細')),
                            );
                          }
                          reload();
                        }
                      },
                      child: Text(session.local(a['label'])),
                    ),
                  ),
                for (final resource in ['refunds', 'disputes'])
                  if (data[resource] is List)
                    for (final value in data[resource])
                      ListTile(
                        title: Text(
                          '${session.tr(resource == 'refunds' ? '退款' : '争议', resource == 'refunds' ? '返金' : '紛争')} #${value['id']}',
                        ),
                        subtitle: Text(status(session, value['status'])),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => open(
                          context,
                          DetailPage(
                            path: '/$resource/${value['id']}',
                            title: session.tr('处理详情', '処理詳細'),
                          ),
                        ),
                      ),
                if (data['audit'] is List) ...[
                  heading(session.tr('交易记录', '取引記録')),
                  for (final a in data['audit'])
                    ListTile(
                      title: Text(status(session, a['event'])),
                      subtitle: Text('${a['created_at']}'),
                      trailing: Text(yen(a['amount_delta'])),
                    ),
                ],
              ],
            );
          },
        ),
      );
}

class AccountListPage extends StatelessWidget {
  final String kind;
  const AccountListPage({super.key, required this.kind});
  String get title =>
      {
        'orders': session.tr('我的订单', '注文'),
        'offers': session.tr('议价', '価格交渉'),
        'buybacks': session.tr('买断申请', '買取申込'),
        'service_orders': session.tr('服务预约', 'サービス予約'),
        'deliveries': session.tr('配送预约', '配達予約'),
        'listings': session.tr('我的商品', '出品商品'),
        'oneclick_drafts': session.tr('发布草稿', '下書き'),
        'threads': session.tr('站内消息', 'メッセージ'),
        'following': session.tr('我的收藏', 'お気に入り'),
      }[kind] ??
      '';
  @override
  Widget build(BuildContext context) {
    if (!session.signedIn) {
      return ListView(padding: const EdgeInsets.all(14), children: [
        if (kind == 'orders') TrialNotice(api: session),
        heading(title),
        const SizedBox(height: 64),
        Center(
            child: Container(
                width: 88,
                height: 88,
                decoration: BoxDecoration(
                    color: YunoColors.sage,
                    borderRadius: BorderRadius.circular(30)),
                child: Icon(resourceIcon(kind),
                    size: 34, color: const Color(0xff7b9276)))),
        const SizedBox(height: 24),
        Center(
            child: Text(session.tr('每一次好物交接，都在这里', 'ものがつなぐ、取引の記録'),
                style: const TextStyle(
                    fontSize: 17, fontWeight: FontWeight.w500))),
        const SizedBox(height: 8),
        Center(
            child: Text(session.tr('登录后查看你的记录', 'ログインして履歴を確認'),
                style: const TextStyle(fontSize: 13, color: YunoColors.muted))),
        const SizedBox(height: 24),
        Center(
            child: FilledButton(
                onPressed: () => open(context, const AuthPage()),
                child: Text(session.tr('登录查看', 'ログインして表示')))),
      ]);
    }
    return LoadView(
      load: () => session.get('/me'),
      builder: (context, data, reload) {
        final items = List<Json>.from(data[kind] ?? []);
        return ListView(
          padding: const EdgeInsets.all(14),
          children: [
            heading(title),
            if (kind == 'buybacks') ...[
              Text(
                  session.tr('从自己已发布的商品中选择，进入商品详情申请平台买断。报价需平台评估，可婉拒。',
                      '出品済みの商品を選び、商品詳細から買取申込へ。査定によりお断りする場合があります。'),
                  style:
                      const TextStyle(fontSize: 12, color: YunoColors.muted)),
              const SizedBox(height: 8),
              FilledButton(
                  onPressed: () => openAccount(context, 'listings'),
                  child: Text(session.tr('选择商品申请回收', '商品を選んで買取申込'))),
              const SizedBox(height: 16),
            ],
            if (items.isEmpty) empty(),
            for (final item in items)
              if (kind == 'listings' || kind == 'following')
                ListingCard(item: item, onReturn: reload)
              else
                Card(
                  child: ListTile(
                    title: Text(
                      kind == 'threads'
                          ? session.title(item)
                          : '$title #${item['id']}',
                    ),
                    subtitle: Text(status(session, item['status'] ?? '')),
                    trailing: Text(
                      item['total'] != null ? yen(item['total']) : '›',
                    ),
                    onTap: () async {
                      if (kind == 'threads') {
                        await open(
                          context,
                          ChatPage(
                            lid: item['listing_id'],
                            bid: item['buyer_id'],
                          ),
                        );
                      } else if (kind == 'oneclick_drafts') {
                        await open(context, PublishPage(draftId: item['id']));
                      } else {
                        final resource = {
                              'buybacks': 'buyback',
                              'service_orders': 'services',
                            }[kind] ??
                            kind;
                        await open(
                          context,
                          DetailPage(
                            path: '/$resource/${item['id']}',
                            title: title,
                          ),
                        );
                      }
                      reload();
                    },
                  ),
                ),
          ],
        );
      },
    );
  }
}

IconData resourceIcon(String key) => switch (key) {
      'listings' => Icons.inventory_2_outlined,
      'orders' => Icons.receipt_long_outlined,
      'offers' => Icons.chat_bubble_outline,
      'buybacks' => Icons.sell_outlined,
      'service_orders' => Icons.home_outlined,
      'deliveries' => Icons.local_shipping_outlined,
      'oneclick_drafts' => Icons.edit_note_outlined,
      'threads' => Icons.forum_outlined,
      'auctions' => Icons.gavel_outlined,
      _ => Icons.cleaning_services_outlined,
    };

Future<void> launchPublish(BuildContext context, {bool auction = false}) async {
  if (await ensureLogin(context) && context.mounted) {
    await open(context, PublishPage(auctionAfterPublish: auction));
  }
}

class TradeMenu extends StatelessWidget {
  final BuildContext hostContext;
  const TradeMenu({super.key, required this.hostContext});
  @override
  Widget build(BuildContext context) => SafeArea(
      top: false,
      child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  Expanded(child: heading(session.tr('交易', '取引'))),
                  TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: Text(session.tr('关闭', '閉じる')))
                ]),
                LayoutBuilder(
                    builder: (context, c) =>
                        Wrap(spacing: 8, runSpacing: 8, children: [
                          for (final entry in <(String, String, VoidCallback)>[
                            (
                              session.tr('发布闲置', '出品する'),
                              session.tr('拍照后一口价发布，可议价', '撮影して即決出品・価格交渉も可能'),
                              () {
                                Navigator.pop(context);
                                launchPublish(hostContext);
                              }
                            ),
                            (
                              session.tr('发布拍卖', 'オークション出品'),
                              session.tr('先拍照，再确认起拍价与拍卖参数', '撮影後に開始価格・入札条件を確認'),
                              () {
                                Navigator.pop(context);
                                launchPublish(hostContext, auction: true);
                              }
                            ),
                            (
                              session.tr('卖给平台', '買取申込'),
                              session.tr('平台评估后报价，可婉拒，不承诺固定比例',
                                  '個別査定・買取をお断りする場合があります'),
                              () {
                                Navigator.pop(context);
                                openAccount(hostContext, 'buybacks');
                              }
                            ),
                            (
                              session.tr('增值服务', '暮らしのサービス'),
                              session.tr('家居清洁、小件搬运、本地配送预约', '清掃・小型運搬・地域配送予約'),
                              () {
                                Navigator.pop(context);
                                open(
                                    hostContext,
                                    PageFrame(
                                        title: session.tr('增值服务', 'サービス'),
                                        child: const TradePage()));
                              }
                            ),
                          ])
                            SizedBox(
                                width: (c.maxWidth - 8) / 2,
                                child: Material(
                                    color: YunoColors.paper,
                                    shape: RoundedRectangleBorder(
                                        borderRadius: BorderRadius.circular(12),
                                        side: const BorderSide(
                                            color: YunoColors.line)),
                                    child: InkWell(
                                        borderRadius: BorderRadius.circular(12),
                                        onTap: entry.$3,
                                        child: Container(
                                            constraints: const BoxConstraints(
                                                minHeight: 94),
                                            padding: const EdgeInsets.all(14),
                                            child: Column(
                                                crossAxisAlignment:
                                                    CrossAxisAlignment.start,
                                                children: [
                                                  Text(entry.$1,
                                                      style: const TextStyle(
                                                          fontSize: 14,
                                                          fontWeight:
                                                              FontWeight.w700)),
                                                  const SizedBox(height: 6),
                                                  Text(entry.$2,
                                                      style: const TextStyle(
                                                          fontSize: 11,
                                                          height: 1.6,
                                                          color: YunoColors
                                                              .muted)),
                                                ]))))),
                        ])),
              ])));
}

Future<void> openAccount(BuildContext context, String kind) async {
  if (await ensureLogin(context) && context.mounted) {
    await open(
        context,
        PageFrame(
            title: AccountListPage(kind: kind).title,
            child: AccountListPage(kind: kind)));
  }
}

class TradePage extends StatelessWidget {
  final VoidCallback? onMarket, onOrders;
  const TradePage({super.key, this.onMarket, this.onOrders});
  @override
  Widget build(BuildContext context) => ListView(
        padding: const EdgeInsets.all(14),
        children: [
          heading(session.tr('交易', '取引')),
          Card(
            color: YunoColors.primary,
            clipBehavior: Clip.antiAlias,
            child: InkWell(
                onTap: () async {
                  if (await ensureLogin(context) && context.mounted) {
                    await open(context, const PublishPage());
                  }
                },
                child: Padding(
                    padding: const EdgeInsets.all(18),
                    child: Row(children: [
                      Container(
                          width: 50,
                          height: 50,
                          decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.15),
                              shape: BoxShape.circle),
                          child: const Icon(Icons.photo_camera_outlined,
                              color: Colors.white, size: 24)),
                      const SizedBox(width: 14),
                      Expanded(
                          child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                            Text(session.tr('拍照发布 · AI 一键估价', '撮影して出品・AI一括査定'),
                                style: const TextStyle(
                                    fontSize: 18,
                                    fontWeight: FontWeight.w800,
                                    color: Colors.white)),
                            const SizedBox(height: 5),
                            Text(
                                session.tr('先拍照，AI 一次给出识别、鉴定与估价，最多 10 张，第一张为封面',
                                    '写真から認識・鑑定・査定へ。最大10枚、先頭がカバーです。'),
                                style: const TextStyle(
                                    fontSize: 12,
                                    height: 1.6,
                                    color: Colors.white)),
                          ])),
                    ]))),
          ),
          LayoutBuilder(builder: (context, constraints) {
            final actions = <(String, String, VoidCallback)>[
              (
                session.tr('我要买', '買いたい'),
                session.tr('浏览在售商品，一口价买断或参与拍卖', '出品中の商品を探す。即決購入やオークションへ'),
                onMarket ??
                    () => open(
                        context,
                        const PageFrame(
                            title: 'Yuno Life', child: MarketPage()))
              ),
              (
                session.tr('平台回收', '買取サービス'),
                session.tr(
                    '按品类与库存评估报价，平台可婉拒，不承诺固定比例', '品目と在庫から個別査定。買取をお断りする場合があります'),
                () => openAccount(context, 'buybacks')
              ),
              (
                session.tr('我的订单', '注文履歴'),
                session.tr('查看付款、配送与完成状态', '決済・配送・完了状況を確認'),
                onOrders ?? () => openAccount(context, 'orders')
              ),
              (
                session.tr('我的发布', '出品管理'),
                session.tr('管理在售与已售商品', '出品中・売却済みの商品を管理'),
                () => openAccount(context, 'listings')
              ),
            ];
            final width = (constraints.maxWidth - 10) / 2;
            return Wrap(spacing: 10, children: [
              for (final a in actions)
                SizedBox(
                    width: width,
                    child: Card(
                        clipBehavior: Clip.antiAlias,
                        child: InkWell(
                            onTap: a.$3,
                            child: Padding(
                              padding: const EdgeInsets.all(13),
                              child: ConstrainedBox(
                                  constraints:
                                      const BoxConstraints(minHeight: 66),
                                  child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(a.$1,
                                            style: const TextStyle(
                                                fontWeight: FontWeight.w700,
                                                fontSize: 15)),
                                        const SizedBox(height: 4),
                                        Text(a.$2,
                                            style: const TextStyle(
                                                fontSize: 12, height: 1.5)),
                                      ])),
                            ))))
            ]);
          }),
          const SizedBox(height: 8),
          heading(session.tr('增值服务', '暮らしのサービス')),
          Card(
              child: Column(children: [
            for (final e in (session.config['services'] as Map? ?? {}).entries)
              ListTile(
                title: Text(session.name(Map<String, dynamic>.from(e.value)),
                    style: const TextStyle(fontWeight: FontWeight.w700)),
                subtitle: Text(
                    '${yen(e.value['price'])}${e.value['unit'] == 'hour' ? session.tr(' / 小时，按实际时长结算', ' / 時間') : e.key == 'transport_small' ? session.tr(' / 趟，10kg 以内', ' / 回、10kg以内') : session.tr(' / 趟起，按距离与尺寸确认', ' / 回〜、距離・サイズにより確認')}',
                    style: const TextStyle(fontSize: 11)),
                trailing: FilledButton(
                    onPressed: () async {
                      if (!await ensureLogin(context) || !context.mounted) {
                        return;
                      }
                      await runCommand(
                          context,
                          {
                            'path': '/services/new',
                            'label': {'zh': '服务预约（模拟）', 'ja': 'サービス予約（模擬）'},
                            'fields': {
                              'kind': {'default': e.key, 'required': true},
                              'hours': {
                                'default': 1,
                                'type': 'number',
                                'required': true
                              },
                              'qty': {
                                'default': 1,
                                'type': 'number',
                                'required': true
                              },
                              'note': {'default': ''},
                            },
                          },
                          openResult: true);
                    },
                    child: Text(session.tr('预约', '予約'))),
              ),
          ])),
          Card(
              child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(session.tr('配送说明', '配送について'),
                            style:
                                const TextStyle(fontWeight: FontWeight.w700)),
                        const SizedBox(height: 5),
                        Text(
                            session.tr(
                                '小件配送 ¥150 起，按距离、重量与尺寸计价；大件单独报价，不承诺所有商品均可配送。',
                                '小型配送は¥150〜。距離・重量・サイズで確認。大型品は個別見積りで、配送できない場合もあります。'),
                            style: const TextStyle(
                                fontSize: 12, color: YunoColors.muted)),
                        simulation(),
                      ]))),
          for (final pair in [
            ['auctions', session.tr('拍卖市场', 'オークション')],
            ['offers', session.tr('议价管理', '価格交渉')],
            ['oneclick_drafts', session.tr('继续编辑草稿', '下書きを編集')],
            ['deliveries', session.tr('配送预约（模拟）', '配達予約（模擬）')],
          ])
            ListTile(
                leading: Icon(resourceIcon(pair[0]), size: 20),
                title: Text(pair[1]),
                trailing: const Icon(Icons.chevron_right, size: 18),
                onTap: () => pair[0] == 'auctions'
                    ? open(context, const AuctionListPage())
                    : openAccount(context, pair[0])),
        ],
      );
}

class AuctionListPage extends StatelessWidget {
  const AuctionListPage({super.key});
  @override
  Widget build(BuildContext context) => PageFrame(
        title: session.tr('拍卖', 'オークション'),
        child: LoadView(
          load: () => session.get('/auctions'),
          builder: (context, data, reload) => ListView(
            padding: const EdgeInsets.all(14),
            children: [
              simulation(),
              if ((data['items'] as List).isEmpty) empty(),
              for (final item in data['items'])
                Card(
                  child: ListTile(
                    title: Text(session.title(item)),
                    subtitle: Text(
                      '${status(session, item['status'])} · ${yen(item['start_price'])}',
                    ),
                    onTap: () async {
                      await open(
                        context,
                        DetailPage(
                          path: '/auctions/${item['id']}',
                          title: session.title(item),
                        ),
                      );
                      reload();
                    },
                  ),
                ),
            ],
          ),
        ),
      );
}

class TrendsPage extends StatelessWidget {
  const TrendsPage({super.key});
  @override
  Widget build(BuildContext context) => LoadView(
      load: () => session.get('/market'),
      builder: (context, data, reload) {
        final moves = Map<String, dynamic>.from(data['moves'] ?? {});
        void showItem(Json item) => open(
            context,
            DetailPage(
                path: '/listings/${item['id']}', title: session.title(item)));
        return ListView(padding: const EdgeInsets.all(15), children: [
          TrialNotice(api: session),
          heading(session.tr('成交行情', '取引相場')),
          const Divider(height: 12, color: YunoColors.ink),
          marketRankBoard(
              api: session,
              items: List<Json>.from(moves['gainers'] ?? []),
              up: true,
              onListing: showItem),
          marketRankBoard(
              api: session,
              items: List<Json>.from(moves['losers'] ?? []),
              up: false,
              onListing: showItem),
          Text(session.local(data['basis'] ?? ''),
              style: const TextStyle(
                  fontSize: 12, height: 1.8, color: YunoColors.muted)),
          const SizedBox(height: 10),
          Text(
              session.tr(
                  '数据不足 ${moves['insufficient'] ?? 0} 件，持平 ${moves['flat_count'] ?? 0} 件；不编造涨跌。',
                  'データ不足 ${moves['insufficient'] ?? 0} 点・横ばい ${moves['flat_count'] ?? 0} 点。'),
              style: const TextStyle(fontSize: 11, color: YunoColors.muted)),
          const SizedBox(height: 24),
          heading(session.tr('品类均价', 'カテゴリ平均価格')),
          for (final cat in data['categories'] ?? [])
            Card(
                child: ListTile(
              title: Text(categoryLabel(Map<String, dynamic>.from(cat))),
              subtitle: Text(
                  session.tr(
                      '${cat['completed']} 笔成交', '取引 ${cat['completed']} 件'),
                  style:
                      const TextStyle(fontSize: 11, color: YunoColors.muted)),
              trailing: Text(yen(cat['avg'])),
            )),
        ]);
      });
}

class ProfilePage extends StatelessWidget {
  const ProfilePage({super.key});
  @override
  Widget build(BuildContext context) => ListView(
        padding: const EdgeInsets.all(14),
        children: [
          TrialNotice(api: session),
          heading(session.tr('个人中心', 'マイページ')),
          const Divider(height: 12, color: YunoColors.ink),
          Card(
              child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(children: [
                    const CircleAvatar(
                        radius: 26,
                        backgroundColor: YunoColors.sage,
                        child: Text('Y',
                            style: TextStyle(
                                color: YunoColors.primary,
                                fontSize: 22,
                                fontWeight: FontWeight.w800))),
                    const SizedBox(width: 14),
                    Expanded(
                        child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                          Text(
                              session.me?['display_name'] ??
                                  session.tr('访客', 'ゲスト'),
                              style: const TextStyle(
                                  fontSize: 18, fontWeight: FontWeight.w700)),
                          const SizedBox(height: 4),
                          Text(session.tr('管理你的商品、订单与本地服务', '出品・注文・地域サービスを管理'),
                              style: const TextStyle(fontSize: 12)),
                        ])),
                  ]))),
          if (!session.signedIn)
            Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: FilledButton(
                    onPressed: () => open(context, const AuthPage()),
                    child: Text(session.tr('登录 / 注册', 'ログイン・登録')))),
          Wrap(spacing: 6, runSpacing: 6, children: [
            for (final pair in [
              ['listings', session.tr('我发布的', '出品商品')],
              ['orders', session.tr('交易记录', '取引履歴')],
              ['following', session.tr('我的收藏', 'お気に入り')],
              ['service_orders', session.tr('服务订单', 'サービス予約')],
              ['deliveries', session.tr('配送预约', '配達予約')],
              ['offers', session.tr('议价', '価格交渉')],
              ['buybacks', session.tr('买断申请', '買取申込')]
            ])
              OutlinedButton(
                  onPressed: () => openAccount(context, pair[0]),
                  child: Text(pair[1], style: const TextStyle(fontSize: 11))),
          ]),
          const SizedBox(height: 14),
          Card(
              clipBehavior: Clip.antiAlias,
              child: Column(children: [
                for (final kind in [
                  'listings',
                  'following',
                  'service_orders',
                  'deliveries'
                ]) ...[
                  ListTile(
                      title: Text(AccountListPage(kind: kind).title),
                      trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                        if (session.me?[kind] is List)
                          Text('${(session.me![kind] as List).length}',
                              style: const TextStyle(
                                  fontSize: 12, color: YunoColors.muted)),
                        const SizedBox(width: 16),
                        const Icon(Icons.chevron_right, size: 16),
                      ]),
                      onTap: () => openAccount(context, kind)),
                  if (kind != 'deliveries') const Divider(height: 1),
                ],
                const Divider(height: 1),
                ExpansionTile(
                    title: Text(session.tr('更多交易管理', '取引管理')),
                    children: [
                      for (final kind in [
                        'orders',
                        'offers',
                        'buybacks',
                        'oneclick_drafts',
                        'threads'
                      ])
                        ListTile(
                            title: Text(AccountListPage(kind: kind).title),
                            trailing: const Icon(Icons.chevron_right, size: 16),
                            onTap: () => openAccount(context, kind))
                    ]),
                if (session.operatorRole) ...[
                  const Divider(height: 1),
                  ListTile(
                      title: Text(session.tr('员工入口', 'スタッフ入口')),
                      trailing: const Icon(Icons.chevron_right, size: 16),
                      onTap: () => open(context, const AdminPage())),
                ],
              ])),
          const SizedBox(height: 12),
          heading(session.tr('语言 / 言語', '言語 / 语言')),
          Wrap(spacing: 8, children: [
            for (final pair in [
              ['zh', '中文'],
              ['ja', '日本語'],
              ['system', session.tr('跟随系统', 'システム設定')]
            ])
              filterChip(pair[1], session.language == pair[0],
                  () => session.setLanguage(pair[0]))
          ]),
          const SizedBox(height: 18),
          heading(session.tr('规则与说明', 'ルールとご案内')),
          const RulesAccordion(),
          Card(
              child: Column(children: [
            ListTile(
                title: Text(session.tr('全部条款与隐私政策', '利用規約・プライバシー')),
                trailing: const Icon(Icons.chevron_right, size: 16),
                onTap: () => open(context, const RulesPage())),
            const Divider(height: 1),
            ListTile(
                title: Text(session.tr('本地客服助手', 'ローカルサポート')),
                trailing: const Icon(Icons.chevron_right, size: 16),
                onTap: () => open(context, const SupportPage())),
          ])),
          Card(
              child: ExpansionTile(
                  title: Text(session.tr('连接平台', 'サーバー接続')),
                  children: [
                Padding(
                    padding: const EdgeInsets.all(12),
                    child: ConnectionForm(onSaved: () {}))
              ])),
          if (session.signedIn)
            OutlinedButton(
                onPressed: () async {
                  try {
                    await session.signOut();
                  } catch (e) {
                    if (context.mounted) notify(context, failure(e));
                  }
                },
                child: Text(session.tr('退出登录', 'ログアウト'))),
          simulation(),
          const Center(
              child: Text('Yuno Life · 0.4.0 (5)',
                  style: TextStyle(fontSize: 11, color: YunoColors.muted))),
          const SizedBox(height: 16),
        ],
      );
}

class RulesAccordion extends StatelessWidget {
  const RulesAccordion({super.key});
  @override
  Widget build(BuildContext context) => FutureBuilder<Json>(
        future: session.get('/rules'),
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return TextButton(
                onPressed: () => open(context, const RulesPage()),
                child: Text(session.tr('查看规则与说明', 'ルールを確認')));
          }
          return Column(children: [
            for (final entry in <(String, String)>[
              (
                session.tr('佣金与费用', '手数料・費用'),
                session.tr('默认佣金 10%，后台可调 7–10%。商品价格含税。',
                    '手数料は初期設定10%、7–10%で調整可能。表示価格は税込です。')
              ),
              for (final item in List<Json>.from(snapshot.data?['items'] ?? []))
                (
                  switch (item['key']) {
                    'terms' => session.tr('利用规约', '利用規約'),
                    'privacy' => session.tr('隐私政策', 'プライバシー'),
                    'returns' => session.tr('退货与纠纷', '返品・紛争'),
                    'prohibited' => session.tr('禁售品', '出品禁止物'),
                    _ => session.tr('平台规则', 'ルール'),
                  },
                  session.local(item)
                ),
              (
                session.tr('AI 估价说明', 'AI査定について'),
                session.tr(
                    'AI 结果为参考，可手动修改；无同型号市场样本时如实说明，不编造价格。此报价为AI根据现实数据做出的估价，用户可以根据自身另行填写',
                    'AI結果は参考情報で編集できます。同一型番の相場データがない場合は明示し、価格を捏造しません。査定は取引価格や買取の保証ではありません。')
              ),
            ])
              Card(
                  child: ExpansionTile(
                      title: Text(entry.$1,
                          style: const TextStyle(
                              fontSize: 14, fontWeight: FontWeight.w700)),
                      children: [
                    Padding(
                        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                        child: Align(
                            alignment: Alignment.centerLeft,
                            child: Text(entry.$2,
                                style: const TextStyle(
                                    fontSize: 12, height: 1.7))))
                  ])),
          ]);
        },
      );
}

class OrdersPage extends StatefulWidget {
  const OrdersPage({super.key});
  @override
  State<OrdersPage> createState() => _OrdersPageState();
}

class _OrdersPageState extends State<OrdersPage> {
  String selected = '';
  @override
  Widget build(BuildContext context) {
    if (!session.signedIn) return const AccountListPage(kind: 'orders');
    return LoadView(
        load: () => session.get('/orders'),
        builder: (context, data, reload) {
          final items = List<Json>.from(data['items'] ?? [])
              .where((item) => selected.isEmpty || item['status'] == selected)
              .toList();
          return ListView(padding: const EdgeInsets.all(14), children: [
            TrialNotice(api: session),
            heading(session.tr('订单', '注文')),
            Wrap(spacing: 7, children: [
              for (final entry in ['', 'pending_payment', 'paid', 'completed'])
                filterChip(
                    entry.isEmpty
                        ? session.tr('全部', 'すべて')
                        : status(session, entry),
                    selected == entry,
                    () => setState(() => selected = entry)),
            ]),
            const SizedBox(height: 10),
            if (items.isEmpty) empty(),
            for (final item in items)
              Card(
                  shape: const RoundedRectangleBorder(
                      side: BorderSide(color: YunoColors.line)),
                  clipBehavior: Clip.antiAlias,
                  child: InkWell(
                    onTap: () async {
                      await open(
                          context,
                          DetailPage(
                              path: '/orders/${item['id']}',
                              title: session.tr('订单详情', '注文詳細')));
                      reload();
                    },
                    child: Padding(
                        padding: const EdgeInsets.all(13),
                        child: Column(children: [
                          Row(children: [
                            ClipRRect(
                                borderRadius: BorderRadius.circular(8),
                                child: SizedBox(
                                    width: 56,
                                    height: 56,
                                    child: (item['listing']?['photos']
                                                    as List? ??
                                                [])
                                            .isEmpty
                                        ? Container(
                                            color: YunoColors.paper,
                                            child: const Icon(
                                                Icons.image_outlined,
                                                color: YunoColors.muted))
                                        : imageView(
                                            item['listing']['photos'][0]['url'],
                                            width: 56,
                                            height: 56))),
                            const SizedBox(width: 11),
                            Expanded(
                                child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                  Text(
                                      item['listing'] is Map
                                          ? session.title(
                                              Map<String, dynamic>.from(
                                                  item['listing']))
                                          : '#${item['listing_id']}',
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                          fontSize: 14,
                                          fontWeight: FontWeight.w700)),
                                  const SizedBox(height: 4),
                                  Text(
                                      '#${item['id']} · ${status(session, item['status'])}',
                                      style: const TextStyle(
                                          fontSize: 11,
                                          color: YunoColors.muted)),
                                ])),
                          ]),
                          const Divider(height: 22),
                          Row(children: [
                            badge(session.tr('模拟支付', '模擬決済'), warning: true),
                            const Spacer(),
                            Text(yen(item['total']),
                                style: const TextStyle(
                                    fontWeight: FontWeight.w800, fontSize: 16))
                          ]),
                        ])),
                  )),
            simulation(),
          ]);
        });
  }
}

class ConnectionForm extends StatefulWidget {
  final VoidCallback onSaved;
  const ConnectionForm({super.key, required this.onSaved});
  @override
  State<ConnectionForm> createState() => _ConnectionFormState();
}

class _ConnectionFormState extends State<ConnectionForm> {
  late final control = TextEditingController(text: session.baseUrl);
  bool busy = false;
  String? error;
  @override
  void dispose() {
    control.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Column(
        children: [
          TextField(
            controller: control,
            keyboardType: TextInputType.url,
            autocorrect: false,
            decoration: InputDecoration(
              labelText: session.tr('平台地址', 'サーバーURL'),
              helperText: session.tr('更换平台会退出当前账号', 'サーバー変更時はログアウトします'),
            ),
          ),
          if (error != null) Text(error!),
          FilledButton(
            onPressed: busy
                ? null
                : () async {
                    setState(() => busy = true);
                    try {
                      await session.setServer(control.text);
                      widget.onSaved();
                    } catch (e) {
                      if (mounted) setState(() => error = failure(e));
                    } finally {
                      if (mounted) setState(() => busy = false);
                    }
                  },
            child: Text(session.tr('连接', '接続')),
          ),
        ],
      );
}

class RulesPage extends StatelessWidget {
  const RulesPage({super.key});
  @override
  Widget build(BuildContext context) => PageFrame(
        title: session.tr('规则与说明', '規約と説明'),
        child: LoadView(
          load: () => session.get('/rules'),
          builder: (context, data, reload) => ListView(
            padding: const EdgeInsets.all(14),
            children: [
              simulation(),
              for (final item in data['items'])
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Text(
                      session.local(item),
                      style: const TextStyle(fontSize: 17, height: 1.6),
                    ),
                  ),
                ),
            ],
          ),
        ),
      );
}

class SupportPage extends StatefulWidget {
  const SupportPage({super.key});
  @override
  State<SupportPage> createState() => _SupportPageState();
}

class _SupportPageState extends State<SupportPage> {
  final question = TextEditingController();
  String answer = '';
  bool busy = false;
  @override
  void dispose() {
    question.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PageFrame(
        title: session.tr('本地客服助手', 'ローカルサポート'),
        child: ListView(
          padding: const EdgeInsets.all(14),
          children: [
            Text(
              session.tr(
                '本地规则问答，不调用付费 API，不代替人工裁决。',
                'ローカルのルール回答です。有料APIは使用せず、手動判断の代わりにはなりません。',
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: question,
              maxLines: 3,
              decoration:
                  InputDecoration(labelText: label(session, 'question')),
            ),
            FilledButton(
              onPressed: busy
                  ? null
                  : () async {
                      if (!await ensureLogin(context) || !mounted) return;
                      setState(() => busy = true);
                      try {
                        final data = await session.post('/support', {
                          'question': question.text,
                        });
                        if (mounted) {
                          setState(
                            () => answer =
                                '${data[session.zh ? 'answer_zh' : 'answer_ja'] ?? data['answer'] ?? ''}',
                          );
                        }
                      } catch (e) {
                        if (mounted) setState(() => answer = failure(e));
                      } finally {
                        if (mounted) setState(() => busy = false);
                      }
                    },
              child: Text(session.tr('发送', '送信')),
            ),
            if (busy) const LinearProgressIndicator(),
            if (answer.isNotEmpty)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Text(answer),
                ),
              ),
          ],
        ),
      );
}

class ChatPage extends StatefulWidget {
  final int lid, bid;
  const ChatPage({super.key, required this.lid, required this.bid});
  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final text = TextEditingController();
  bool busy = false;
  @override
  void dispose() {
    text.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PageFrame(
        title: session.tr('站内消息', 'メッセージ'),
        child: LoadView(
          load: () => session.get('/messages/${widget.lid}/${widget.bid}'),
          builder: (context, data, reload) => ListView(
            padding: const EdgeInsets.all(14),
            children: [
              for (final m in data['items'])
                Align(
                  alignment: m['sender_id'] == session.me?['id']
                      ? Alignment.centerRight
                      : Alignment.centerLeft,
                  child: Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${m['display_name']}',
                            style: const TextStyle(fontWeight: FontWeight.bold),
                          ),
                          Text('${m['body']}'),
                          Text(
                            '${m['created_at']}',
                            style: const TextStyle(fontSize: 11),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              if ((data['items'] as List).isEmpty) empty(),
              TextField(
                controller: text,
                maxLines: 3,
                decoration: InputDecoration(labelText: label(session, 'body')),
              ),
              FilledButton(
                onPressed: busy
                    ? null
                    : () async {
                        if (text.text.trim().isEmpty) return;
                        setState(() => busy = true);
                        try {
                          await session.post(
                            '/messages/${widget.lid}/${widget.bid}',
                            {
                              'body': text.text.trim(),
                              'receiver_id': data['receiver_id'],
                            },
                          );
                          text.clear();
                          reload();
                        } catch (e) {
                          if (context.mounted) notify(context, failure(e));
                        } finally {
                          if (mounted) setState(() => busy = false);
                        }
                      },
                child: Text(session.tr('发送', '送信')),
              ),
            ],
          ),
        ),
      );
}

class AdminPage extends StatelessWidget {
  const AdminPage({super.key});
  @override
  Widget build(BuildContext context) {
    final entries = {
      'users': session.tr('用户', 'ユーザー'),
      'listings': session.tr('商品', '商品'),
      'buybacks': session.tr('买断', '買取'),
      'orders': session.tr('订单', '注文'),
      'inventory': session.tr('自营库存', '自社在庫'),
      'auctions': session.tr('拍卖', 'オークション'),
      'deliveries': session.tr('配送（模拟）', '配送（模擬）'),
      'services': session.tr('服务', 'サービス'),
      'refunds': session.tr('退款（模拟）', '返金（模擬）'),
      'disputes': session.tr('争议', '紛争'),
      'high-value': session.tr('鉴定审核', '鑑定審査'),
      'profit': session.tr('经营利润', '損益'),
      'alerts': session.tr('异常预警', '異常通知'),
      'suggestions': session.tr('调价建议', '価格提案'),
      'expenses': session.tr('费用', '経費'),
      'audit': session.tr('审计记录', '監査ログ'),
      'settings': session.tr('参数设置', '設定'),
    };
    return PageFrame(
      title: session.tr('管理后台', '運営管理'),
      child: ListView(
        padding: const EdgeInsets.all(14),
        children: [
          for (final e in entries.entries)
            ListTile(
              title: Text(e.value),
              trailing: const Icon(Icons.chevron_right),
              onTap: () =>
                  open(context, AdminSection(section: e.key, title: e.value)),
            ),
        ],
      ),
    );
  }
}

class AdminSection extends StatelessWidget {
  final String section, title;
  const AdminSection({super.key, required this.section, required this.title});
  @override
  Widget build(BuildContext context) => PageFrame(
        title: title,
        child: LoadView(
          load: () => session.get('/admin/$section'),
          builder: (context, data, reload) => ListView(
            padding: const EdgeInsets.all(14),
            children: [
              simulation(),
              if (section == 'profit')
                for (final e in data.entries)
                  if (fieldLabels.containsKey(e.key))
                    ListTile(
                      title: Text(label(session, e.key)),
                      trailing: Text(yen(e.value)),
                    ),
              for (final a in data['actions'] ?? [])
                FilledButton(
                  onPressed: () async {
                    await runCommand(context, a);
                    reload();
                  },
                  child: Text(session.local(a['label'])),
                ),
              if (data['items'] is List) ...[
                if ((data['items'] as List).isEmpty) empty(),
                for (final item in data['items'])
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text(
                            '${item['display_name'] ?? session.title(item)} #${item['id'] ?? ''}',
                            style: const TextStyle(fontWeight: FontWeight.bold),
                          ),
                          for (final key in [
                            'email',
                            'role',
                            'status',
                            'price',
                            'cost',
                            'amount',
                            'note',
                            'details',
                            'appraisal_status',
                            'appraisal_note',
                            'created_at',
                          ])
                            if (item[key] != null)
                              Text(
                                '${label(session, key)}: ${status(session, item[key])}',
                              ),
                          if (item['key'] != null)
                            Text('${item['key']}: ${item['value']}'),
                          if ([
                            'buybacks',
                            'orders',
                            'auctions',
                            'deliveries',
                            'services',
                            'refunds',
                            'disputes',
                          ].contains(section))
                            TextButton(
                              onPressed: () async {
                                await open(
                                  context,
                                  DetailPage(
                                    path:
                                        '/${section == 'buybacks' ? 'buyback' : section}/${item['id']}',
                                    title: title,
                                  ),
                                );
                                reload();
                              },
                              child: Text(session.tr('处理详情', '詳細・処理')),
                            ),
                          for (final a in item['actions'] ?? [])
                            TextButton(
                              onPressed: () async {
                                await runCommand(context, a);
                                reload();
                              },
                              child: Text(session.local(a['label'])),
                            ),
                        ],
                      ),
                    ),
                  ),
              ],
            ],
          ),
        ),
      );
}

class PublishPage extends StatefulWidget {
  final int? draftId;
  final bool auctionAfterPublish;
  const PublishPage(
      {super.key, this.draftId, this.auctionAfterPublish = false});
  @override
  State<PublishPage> createState() => _PublishPageState();
}

class _PublishPageState extends State<PublishPage> {
  final picker = ImagePicker();
  final localPhotos = <XFile>[];
  final name = TextEditingController(),
      text = TextEditingController(),
      brand = TextEditingController(),
      model = TextEditingController(),
      price = TextEditingController(),
      jaTitle = TextEditingController(),
      zhTitle = TextEditingController(),
      jaDesc = TextEditingController(),
      zhDesc = TextEditingController(),
      weight = TextEditingController(text: '0');
  final attrs = <String, TextEditingController>{};
  List<Json> remotePhotos = [];
  Json? analysis;
  int? did;
  bool busy = false, loading = false, photosDirty = false;
  String? error;
  String progress = '';
  String category = 'other', condition = 'good', size = 'M', region = 'sakado';
  @override
  void initState() {
    super.initState();
    did = widget.draftId;
    if (did != null) {
      loading = true;
      refreshDraft().catchError((Object e) {
        if (mounted) setState(() => error = failure(e));
      }).whenComplete(() {
        if (mounted) setState(() => loading = false);
      });
    } else {
      WidgetsBinding.instance.addPostFrameCallback(
        (_) => pick(ImageSource.camera),
      );
    }
  }

  @override
  void dispose() {
    for (final c in [
      name,
      text,
      brand,
      model,
      price,
      jaTitle,
      zhTitle,
      jaDesc,
      zhDesc,
      weight,
      ...attrs.values,
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> pick(ImageSource source, {int? replace}) async {
    try {
      if (localPhotos.length + remotePhotos.length >= 10 && replace == null) {
        notify(context, session.tr('每件商品最多 10 张照片。', '写真は10枚までです。'));
        return;
      }
      final photo = await picker.pickImage(
        source: source,
        preferredCameraDevice: CameraDevice.rear,
        imageQuality: 85,
        maxWidth: 2400,
      );
      if (photo != null && mounted) {
        if (did != null) {
          await session.upload('/oneclick/$did/photos/add', {}, [photo]);
          photosDirty = true;
          await refreshDraft();
        } else {
          setState(() {
            if (replace != null) {
              localPhotos[replace] = photo;
            } else {
              localPhotos.add(photo);
            }
            analysis = null;
          });
        }
      }
    } catch (e) {
      if (mounted) {
        notify(
          context,
          session.tr('无法打开相机或相册，请检查权限。', 'カメラ・写真へのアクセス権限を確認してください。'),
        );
      }
    }
  }

  Future<void> gallery() async {
    try {
      final remaining = 10 - localPhotos.length - remotePhotos.length;
      if (remaining <= 0) {
        notify(context, session.tr('每件商品最多 10 张照片。', '写真は10枚までです。'));
        return;
      }
      final selected = await picker.pickMultiImage(
        imageQuality: 85,
        maxWidth: 2400,
        limit: remaining,
      );
      if (selected.length + localPhotos.length + remotePhotos.length > 10) {
        if (mounted) {
          notify(context, session.tr('每件商品最多 10 张照片。', '写真は10枚までです。'));
        }
        return;
      }
      if (did != null) {
        if (selected.isNotEmpty) {
          await session.upload('/oneclick/$did/photos/add', {}, selected);
          photosDirty = true;
        }
        await refreshDraft();
      } else if (mounted) {
        setState(() => localPhotos.addAll(selected));
      }
    } catch (e) {
      if (mounted) notify(context, failure(e));
    }
  }

  Future<void> refreshDraft() async {
    final value = await session.get('/oneclick/$did');
    if (!mounted) return;
    final dr = Map<String, dynamic>.from(value['draft'] ?? {});
    setState(() {
      analysis = value;
      remotePhotos = List<Json>.from(value['photos'] ?? []);
      name.text = '${value['name'] ?? name.text}';
      text.text = '${value['text'] ?? text.text}';
      if (jaTitle.text.isEmpty) jaTitle.text = '${dr['title_ja'] ?? ''}';
      if (zhTitle.text.isEmpty) zhTitle.text = '${dr['title_zh'] ?? ''}';
      if (jaDesc.text.isEmpty) jaDesc.text = '${dr['desc_ja'] ?? ''}';
      if (zhDesc.text.isEmpty) zhDesc.text = '${dr['desc_zh'] ?? ''}';
      category = '${dr['category_slug'] ?? category}';
      condition = '${dr['condition_grade'] ?? condition}';
      if (brand.text.isEmpty) brand.text = '${dr['brand'] ?? ''}';
      if (model.text.isEmpty) model.text = '${dr['model'] ?? ''}';
      if (price.text.isEmpty && dr['suggested_price'] != null) {
        price.text = '${dr['suggested_price']}';
      }
      for (final e in (dr['attrs'] as Map? ?? {}).entries) {
        attrs.putIfAbsent(
          '${e.key}',
          () => TextEditingController(text: '${e.value}'),
        );
      }
    });
  }

  Future<void> poll(int id) async {
    for (var i = 0; i < 45; i++) {
      if (!mounted) return;
      final job = await session.get('/ai-jobs/$id');
      if (job['status'] == 'done') return;
      if (job['status'] == 'failed') throw ApiError(500, 'job_failed');
      await Future<void>.delayed(const Duration(seconds: 2));
    }
    throw ApiError(408, 'job_timeout');
  }

  Future<void> analyze() async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
      progress = session.tr('上传全部照片…', 'すべての写真をアップロード…');
    });
    try {
      if (did == null) {
        final response = await session.upload(
            '/oneclick/upload',
            {
              'name': name.text.trim().isEmpty
                  ? session.tr('照片中的商品', '写真の商品')
                  : name.text.trim(),
              'text': text.text,
              'condition': condition,
            },
            localPhotos);
        did = int.parse('${response['next']}'.split('/').last);
        localPhotos.clear();
        await refreshDraft();
      }
      setState(
        () => progress = session.tr('本地识别与两轴鉴定（全部为推测）…', 'ローカル認識と鑑定（すべて推測）…'),
      );
      final job = await session.post('/ai-jobs', {
        'kind': 'oneclick_recognize',
        'draft_id': did,
      });
      await poll(job['job_id']);
      photosDirty = false;
      await refreshDraft();
      if (model.text.trim().isNotEmpty) {
        await compare();
      } else {
        if (mounted) {
          setState(
            () => progress = session.tr(
              '请确认精确型号；未确认型号时不编造报价。',
              '正確な型番を確認してください。未確認の場合は価格を作りません。',
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) setState(() => error = failure(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> compare() async {
    if (did == null || model.text.trim().isEmpty) return;
    await session.post('/oneclick/$did/model', {
      'brand': brand.text.trim(),
      'model': model.text.trim(),
    });
    if (mounted) {
      setState(
        () => progress = session.tr(
          '并行查询同型号市场样本，最多 60 秒…',
          '同型番の市場サンプルを検索中、最大60秒…',
        ),
      );
    }
    final task = await session.post('/ai-jobs', {
      'kind': 'oneclick_valuation',
      'draft_id': did,
    });
    await poll(task['job_id']);
    await refreshDraft();
    if (mounted) {
      setState(
        () => progress = session.tr('分析完成；请编辑并确认发布。', '分析完了。編集して出品を確認してください。'),
      );
    }
  }

  Future<void> manageRemote(int index, String operation) async {
    try {
      if (operation == 'delete') {
        await session.post('/oneclick/$did/photos/$index/delete', {});
      } else if (operation == 'cover') {
        final order = List<int>.generate(remotePhotos.length, (i) => i);
        order.insert(0, order.removeAt(index));
        await session.post('/oneclick/$did/photos/reorder', {'order': order});
      } else {
        final photo = await picker.pickImage(
          source:
              operation == 'retake' ? ImageSource.camera : ImageSource.gallery,
          preferredCameraDevice: CameraDevice.rear,
          imageQuality: 85,
          maxWidth: 2400,
        );
        if (photo == null) return;
        await session.upload(
            '/oneclick/$did/photos/$index/replace',
            {},
            [
              photo,
            ],
            field: 'photo');
      }
      photosDirty = true;
      await refreshDraft();
    } catch (e) {
      if (mounted) notify(context, failure(e));
    }
  }

  Widget photoTile(int index, bool remote) {
    final body = remote
        ? imageView(remotePhotos[index]['url'], height: 150, width: 150)
        : Image.file(
            File(localPhotos[index].path),
            height: 150,
            width: 150,
            fit: BoxFit.cover,
          );
    return SizedBox(
      width: 160,
      child: Column(
        children: [
          GestureDetector(
            onTap: () => open(
              context,
              PageFrame(
                title: session.tr('照片预览', '写真プレビュー'),
                child: InteractiveViewer(
                  child: remote
                      ? imageView(
                          remotePhotos[index]['url'],
                          height: 600,
                          fit: BoxFit.contain,
                        )
                      : Image.file(
                          File(localPhotos[index].path),
                          fit: BoxFit.contain,
                        ),
                ),
              ),
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: body,
            ),
          ),
          Row(
            children: [
              Expanded(
                child: Text(
                  index == 0 ? session.tr('封面', 'カバー') : '#${index + 1}',
                ),
              ),
              PopupMenuButton<String>(
                onSelected: (op) async {
                  if (remote) {
                    await manageRemote(index, op);
                  } else if (op == 'delete') {
                    setState(() => localPhotos.removeAt(index));
                  } else if (op == 'cover') {
                    setState(
                      () => localPhotos.insert(0, localPhotos.removeAt(index)),
                    );
                  } else {
                    await pick(
                      op == 'retake' ? ImageSource.camera : ImageSource.gallery,
                      replace: index,
                    );
                  }
                },
                itemBuilder: (_) => [
                  for (final pair in [
                    ['cover', session.tr('设为封面', 'カバーに設定')],
                    ['replace', session.tr('替换', '差し替え')],
                    ['retake', session.tr('重拍', '撮り直し')],
                    ['delete', session.tr('删除', '削除')],
                  ])
                    PopupMenuItem(value: pair[0], child: Text(pair[1])),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget edit(TextEditingController c, String key, {int lines = 1}) => Padding(
        padding: const EdgeInsets.only(bottom: 14),
        child: TextField(
          controller: c,
          maxLines: lines,
          keyboardType: ['price', 'weight_kg'].contains(key)
              ? const TextInputType.numberWithOptions(decimal: true)
              : TextInputType.text,
          decoration: InputDecoration(labelText: label(session, key)),
        ),
      );
  @override
  Widget build(BuildContext context) {
    final categories = List<Json>.from(session.config['categories'] ?? []);
    final categoryRow =
        categories.where((c) => c['slug'] == category).firstOrNull;
    final specification = List<dynamic>.from(categoryRow?['attrs'] ?? []);
    final ap = Map<String, dynamic>.from(analysis?['appraisal'] ?? {});
    final val = Map<String, dynamic>.from(analysis?['valuation'] ?? {});
    final rec = Map<String, dynamic>.from(analysis?['recognition'] ?? {});
    final count = localPhotos.length + remotePhotos.length;
    return PageFrame(
      title: session.tr('拍照发布', '撮影して出品'),
      child: loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(14),
              children: [
                heading(session.tr(
                    widget.auctionAfterPublish ? '发布拍卖 · 先拍照确认商品' : '发布商品',
                    widget.auctionAfterPublish ? 'オークション・商品確認' : '商品を出品')),
                Text(
                  session.tr(
                    '最多 10 张，第一张为封面。识别均为本地推测；不能仅凭照片确认型号或真伪。',
                    '写真10枚まで、1枚目はカバー。認識はローカルの推測で、写真のみで型番・真贋を断定しません。',
                  ),
                ),
                const SizedBox(height: 16),
                if (count > 0)
                  SizedBox(
                    height: 205,
                    child: ListView.separated(
                      scrollDirection: Axis.horizontal,
                      itemCount: count,
                      separatorBuilder: (_, i) => const SizedBox(width: 10),
                      itemBuilder: (_, i) => photoTile(i, did != null),
                    ),
                  ),
                Row(
                  children: [
                    Expanded(
                      child: FilledButton.icon(
                        onPressed: busy ? null : () => pick(ImageSource.camera),
                        style: FilledButton.styleFrom(
                            minimumSize: const Size(0, 80)),
                        icon: const Icon(Icons.camera_alt_outlined),
                        label: Text(session.tr('拍照', '撮影')),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: busy ? null : gallery,
                        style: OutlinedButton.styleFrom(
                            minimumSize: const Size(0, 80)),
                        icon: const Icon(Icons.photo_library_outlined),
                        label: Text(session.tr('从相册选', '写真から選択')),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                edit(name, 'name'),
                edit(text, 'text', lines: 3),
                FilledButton(
                  onPressed: count == 0 || busy ? null : analyze,
                  child: Text(session.tr('AI 一键识别 · 鉴定 · 估价', 'AI認識・鑑定・査定')),
                ),
                if (busy) const LinearProgressIndicator(),
                if (progress.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    child: Text(progress),
                  ),
                if (error != null)
                  Text(error!, style: const TextStyle(color: Colors.red)),
                if (analysis != null &&
                    analysis!['status'] == 'recognized') ...[
                  const SizedBox(height: 16),
                  heading(session.tr('识别结果 · 全部可修改', '認識結果・すべて編集可能')),
                  for (final suggestion in rec['suggestions'] ?? [])
                    Text(
                      '${label(session, suggestion['field'])}: ${status(session, suggestion['value'])} · ${session.tr('推测', '推測')} · ${label(session, 'confidence')} ${status(session, suggestion['confidence'])}',
                    ),
                  const SizedBox(height: 16),
                  edit(brand, 'brand'),
                  edit(model, 'model'),
                  OutlinedButton(
                    onPressed: busy
                        ? null
                        : () async {
                            setState(() => busy = true);
                            try {
                              await compare();
                            } catch (e) {
                              if (mounted) setState(() => error = failure(e));
                            } finally {
                              if (mounted) setState(() => busy = false);
                            }
                          },
                    child: Text(session.tr('确认型号并查询真实市场样本', '型番を確認して市場を検索')),
                  ),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            session.tr('鉴定 · AI 推测', '鑑定・AI推測'),
                            style: const TextStyle(fontWeight: FontWeight.bold),
                          ),
                          Text(
                            '${label(session, 'condition_grade')}: ${status(session, ap['condition_grade'])}',
                          ),
                          if (ap['authenticity'] != null) ...[
                            Text(
                              session.tr(
                                '真伪轴：${ap['authenticity']['verdict_zh']}',
                                '真贋：${ap['authenticity']['verdict'] == 'suspect' ? '疑義あり' : '正規品の傾向（推測）'}',
                              ),
                            ),
                            Text(
                              '${label(session, 'confidence')}: ${status(session, ap['authenticity']['confidence'])}',
                            ),
                          ],
                          if (ap['requires_manual_review'] == true)
                            Text(
                              session.tr(
                                '需人工复核，通过前不可交易。',
                                '手動審査が必要です。承認まで取引できません。',
                              ),
                              style: const TextStyle(color: Colors.red),
                            ),
                          if ((ap['detail_checklist'] as List? ?? [])
                              .isNotEmpty)
                            Text(
                              session.tr(
                                '建议补拍细节：${(ap['detail_checklist'] as List).join('、')}',
                                '細部写真の追加を推奨：文字刻印、型番、全体、付属品など。',
                              ),
                            ),
                        ],
                      ),
                    ),
                  ),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            session.tr(
                              'AI 参考价 · 非成交价 · 非收购承诺',
                              'AI参考価格・成約価格でも買取約束でもありません',
                            ),
                            style: const TextStyle(fontWeight: FontWeight.bold),
                          ),
                          if (val['low'] != null)
                            Text(
                              '${yen(val['low'])} – ${yen(val['high'])}',
                              style: const TextStyle(
                                fontSize: 28,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          Text(
                            '${val[session.zh ? 'basis_zh' : 'basis_ja'] ?? ''}',
                          ),
                          Text(
                            '${label(session, 'sample_count')}: ${val['sample_count'] ?? 0} · ${label(session, 'confidence')}: ${status(session, val['confidence'] ?? 'none')}',
                          ),
                          const SizedBox(height: 8),
                          const Text('此报价为AI根据现实数据做出的估价，用户可以根据自身另行填写'),
                          if (!session.zh)
                            Text('${val['disclaimer_ja'] ?? ''}'),
                          for (final source
                              in (val['source_statuses'] as Map? ?? {}).entries)
                            Text(
                              '${source.key}: ${status(session, source.value)}',
                            ),
                          for (final sample in val['market_comps'] ?? [])
                            Text(
                              '${sample['source'] ?? ''} · ${yen(sample['price'])} · ${sample['url'] ?? ''}',
                            ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  heading(session.tr('确认商品信息', '商品情報の確認')),
                  DropdownButtonFormField<String>(
                    initialValue: categories.any((c) => c['slug'] == category)
                        ? category
                        : null,
                    isExpanded: true,
                    decoration: InputDecoration(
                      labelText: label(session, 'category_slug'),
                    ),
                    items: [
                      for (final c in categories)
                        DropdownMenuItem(
                          value: '${c['slug']}',
                          child: Text(
                            session.name(c),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                    ],
                    onChanged: (v) => setState(() => category = v ?? 'other'),
                  ),
                  const SizedBox(height: 14),
                  DropdownButtonFormField<String>(
                    initialValue: condition,
                    decoration: InputDecoration(
                      labelText: label(session, 'condition_grade'),
                    ),
                    items: [
                      for (final c in ['excellent', 'good', 'fair', 'poor'])
                        DropdownMenuItem(
                          value: c,
                          child: Text(status(session, c)),
                        ),
                    ],
                    onChanged: (v) => setState(() => condition = v ?? 'good'),
                  ),
                  const SizedBox(height: 14),
                  edit(jaTitle, 'title_ja'),
                  edit(zhTitle, 'title_zh'),
                  edit(jaDesc, 'desc_ja', lines: 3),
                  edit(zhDesc, 'desc_zh', lines: 3),
                  edit(price, 'price'),
                  edit(weight, 'weight_kg'),
                  DropdownButtonFormField<String>(
                    initialValue: size,
                    decoration: InputDecoration(
                      labelText: label(session, 'size_class'),
                    ),
                    items: [
                      for (final v in ['S', 'M', 'L', 'XL'])
                        DropdownMenuItem(value: v, child: Text(v)),
                    ],
                    onChanged: (v) => size = v ?? 'M',
                  ),
                  const SizedBox(height: 14),
                  for (final spec in specification)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 14),
                      child: TextField(
                        controller: attrs.putIfAbsent(
                          '${spec['key']}',
                          () => TextEditingController(),
                        ),
                        decoration: InputDecoration(
                          labelText:
                              '${spec[session.zh ? 'label_zh' : 'label_ja'] ?? spec['key']}',
                        ),
                      ),
                    ),
                  FilledButton(
                    onPressed: busy
                        ? null
                        : () async {
                            if (photosDirty || count == 0) {
                              notify(
                                  context,
                                  session.tr('照片已变化，请重新运行 AI 分析。',
                                      '写真が変更されました。AI分析を再実行してください。'));
                              return;
                            }
                            if ((int.tryParse(price.text) ?? 0) < 1 ||
                                jaTitle.text.trim().isEmpty) {
                              notify(
                                context,
                                session.tr(
                                  '请填写日文标题与大于 0 的售价。',
                                  '日本語タイトルと正の価格を入力してください。',
                                ),
                              );
                              return;
                            }
                            final yes = await showDialog<bool>(
                              context: context,
                              builder: (context) => AlertDialog(
                                title: Text(session.tr('确认上架？', '出品を確認')),
                                content: Text(
                                  session.tr(
                                    '你确认商品信息与售价。AI 内容均为推测，发布后进入正常交易或人工复核流程。',
                                    '商品情報と価格を確認してください。AIの内容は推測です。公開後は通常取引または手動審査に進みます。',
                                  ),
                                ),
                                actions: [
                                  TextButton(
                                    onPressed: () =>
                                        Navigator.pop(context, false),
                                    child: Text(session.tr('继续编辑', '編集を続ける')),
                                  ),
                                  FilledButton(
                                    onPressed: () =>
                                        Navigator.pop(context, true),
                                    child: Text(session.tr('确认上架', '確認して出品')),
                                  ),
                                ],
                              ),
                            );
                            if (yes != true || !mounted) return;
                            setState(() => busy = true);
                            try {
                              final result = await session.post(
                                '/oneclick/$did/publish',
                                {
                                  'category_slug': category,
                                  'title_ja': jaTitle.text,
                                  'title_zh': zhTitle.text,
                                  'desc_ja': jaDesc.text,
                                  'desc_zh': zhDesc.text,
                                  'price': price.text,
                                  'condition_grade': condition,
                                  'region': region,
                                  'size_class': size,
                                  'weight_kg': weight.text,
                                  for (final e in attrs.entries)
                                    'attr_${e.key}': e.value.text,
                                },
                              );
                              if (widget.auctionAfterPublish &&
                                  context.mounted) {
                                final listing =
                                    await session.get('${result['next']}');
                                final actions =
                                    List<Json>.from(listing['actions'] ?? []);
                                final auction = actions
                                    .where((a) =>
                                        '${a['path']}'.endsWith('/auction'))
                                    .firstOrNull;
                                if (auction != null && context.mounted) {
                                  await runCommand(context, auction,
                                      openResult: true);
                                }
                              }
                              if (context.mounted) {
                                await Navigator.pushReplacement(
                                  context,
                                  MaterialPageRoute(
                                    builder: (_) => DetailPage(
                                      path: '${result['next']}',
                                      title: session.tr('已提交发布', '出品を送信しました'),
                                    ),
                                  ),
                                );
                              }
                            } catch (e) {
                              if (mounted) setState(() => error = failure(e));
                            } finally {
                              if (mounted) setState(() => busy = false);
                            }
                          },
                    child: Text(session.tr('确认上架', '確認して出品')),
                  ),
                ],
                simulation(),
              ],
            ),
    );
  }
}

class PhotoManager extends StatelessWidget {
  final int lid;
  const PhotoManager({super.key, required this.lid});
  @override
  Widget build(BuildContext context) => PageFrame(
        title: session.tr('管理商品照片', '商品写真の管理'),
        child: LoadView(
          load: () => session.get('/listings/$lid'),
          builder: (context, data, reload) {
            final photos = List<Json>.from(data['photos']);
            return ListView(
              padding: const EdgeInsets.all(14),
              children: [
                Text(session.tr('最多 10 张。第一张为封面。', '10枚まで。1枚目がカバーです。')),
                for (final indexed in photos.indexed)
                  Card(
                    child: Column(
                      children: [
                        imageView(
                          indexed.$2['url'],
                          height: 220,
                          fit: BoxFit.contain,
                        ),
                        Wrap(
                          children: [
                            TextButton(
                              onPressed: () async {
                                try {
                                  await session.post(
                                    '/listings/$lid/photos/${indexed.$2['id']}/cover',
                                    {},
                                  );
                                  reload();
                                } catch (e) {
                                  if (context.mounted) {
                                    notify(context, failure(e));
                                  }
                                }
                              },
                              child: Text(
                                indexed.$1 == 0
                                    ? session.tr('当前封面', 'カバー')
                                    : session.tr('设为封面', 'カバーに設定'),
                              ),
                            ),
                            for (final pair in [
                              [ImageSource.camera, session.tr('重拍', '撮り直し')],
                              [ImageSource.gallery, session.tr('替换', '差し替え')],
                            ])
                              TextButton(
                                onPressed: () async {
                                  try {
                                    final file = await ImagePicker().pickImage(
                                      source: pair[0] as ImageSource,
                                      preferredCameraDevice: CameraDevice.rear,
                                      imageQuality: 85,
                                    );
                                    if (file != null) {
                                      await session.upload(
                                        '/listings/$lid/photos/${indexed.$2['id']}/replace',
                                        {},
                                        [file],
                                        field: 'photo',
                                      );
                                      reload();
                                    }
                                  } catch (e) {
                                    if (context.mounted) {
                                      notify(context, failure(e));
                                    }
                                  }
                                },
                                child: Text(pair[1] as String),
                              ),
                            TextButton(
                              onPressed: () async {
                                try {
                                  await session.post(
                                    '/listings/$lid/photos/${indexed.$2['id']}/delete',
                                    {},
                                  );
                                  reload();
                                } catch (e) {
                                  if (context.mounted) {
                                    notify(context, failure(e));
                                  }
                                }
                              },
                              child: Text(session.tr('删除', '削除')),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                if (photos.length < 10)
                  FilledButton.icon(
                    onPressed: () async {
                      try {
                        final files = await ImagePicker().pickMultiImage(
                          imageQuality: 85,
                          limit: 10 - photos.length,
                        );
                        if (files.length + photos.length > 10) {
                          if (context.mounted) {
                            notify(context, session.tr('最多 10 张照片', '10枚までです'));
                          }
                          return;
                        }
                        if (files.isNotEmpty) {
                          await session.upload(
                            '/listings/$lid/photos/add',
                            {},
                            files,
                          );
                          reload();
                        }
                      } catch (e) {
                        if (context.mounted) notify(context, failure(e));
                      }
                    },
                    icon: const Icon(Icons.add_photo_alternate_outlined),
                    label: Text(session.tr('添加照片', '写真を追加')),
                  ),
              ],
            );
          },
        ),
      );
}
