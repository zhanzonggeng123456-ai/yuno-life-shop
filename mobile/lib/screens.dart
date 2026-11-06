import 'package:flutter/material.dart';

import 'api.dart';
import 'editor.dart';
import 'labels.dart';
import 'main.dart';
import 'ui.dart';

Future<Json?> perform(
  BuildContext context,
  String action, [
  Json values = const {},
]) async {
  if (appState.token == null && !['login', 'register'].contains(action)) {
    await openPage<Json>(context, const ActionForm(action: 'login'));
    if (appState.token == null || !context.mounted) return null;
  }
  final result = await openPage<Json>(
    context,
    ActionForm(action: action, values: values),
  );
  if (result != null && context.mounted) {
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(tx('操作已保存', '保存しました'))));
  }
  return result;
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});
  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int index = 0;
  @override
  void initState() {
    super.initState();
    appState.addListener(refresh);
  }

  void refresh() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    appState.removeListener(refresh);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final labels = ['market', 'prices', 'trade', 'orders', 'me'];
    final pages = [
      const Marketplace(),
      const MarketPrices(),
      const TradeHub(),
      const CollectionPage(resource: 'orders', embedded: true),
      const ProfilePage(),
    ];
    return Scaffold(
      body: SafeArea(
        child: appState.server.isEmpty
            ? const ConnectionPage(embedded: true)
            : pages[index],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (value) => setState(() => index = value),
        destinations: [
          for (var i = 0; i < labels.length; i++)
            NavigationDestination(
              icon: Icon(
                [
                  Icons.storefront_outlined,
                  Icons.show_chart_rounded,
                  Icons.add_circle_outline,
                  Icons.receipt_long_outlined,
                  Icons.person_outline,
                ][i],
              ),
              label: label(labels[i]),
            ),
        ],
      ),
    );
  }
}

class ConnectionPage extends StatefulWidget {
  final bool embedded;
  const ConnectionPage({super.key, this.embedded = false});
  @override
  State<ConnectionPage> createState() => _ConnectionPageState();
}

class _ConnectionPageState extends State<ConnectionPage> {
  late final input = TextEditingController(text: appState.server);
  bool busy = false;
  Object? error;
  @override
  void dispose() {
    input.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final content = ListView(
      padding: const EdgeInsets.all(24),
      children: [
        const SizedBox(height: 32),
        const Icon(
          Icons.storefront_rounded,
          size: 72,
          color: Color(0xff225947),
        ),
        heading('YUNO LIFE SHOP', tx('连接你的中古交易平台', '中古品取引プラットフォームに接続')),
        Text(
          tx(
            '输入电脑上运行的平台地址，手机与电脑需要连接同一 Wi-Fi。',
            'パソコンのサーバーアドレスを入力してください。同じ Wi-Fi に接続してください。',
          ),
        ),
        const SizedBox(height: 20),
        TextField(
          controller: input,
          keyboardType: TextInputType.url,
          decoration: InputDecoration(
            labelText: tx('服务器地址', 'サーバーアドレス'),
            hintText: 'http://192.168.68.63:8000',
          ),
        ),
        const SizedBox(height: 16),
        FilledButton(
          onPressed: busy
              ? null
              : () async {
                  setState(() {
                    busy = true;
                    error = null;
                  });
                  try {
                    await appState.connect(input.text);
                    if (context.mounted && !widget.embedded) {
                      Navigator.pop(context);
                    }
                  } catch (e) {
                    if (mounted) setState(() => error = e);
                  } finally {
                    if (mounted) setState(() => busy = false);
                  }
                },
          child: Text(tx('连接平台', '接続する')),
        ),
        if (busy) const LinearProgressIndicator(),
        if (error != null) Text(errorText(error!)),
        simulationNote(),
      ],
    );
    return widget.embedded ? content : PageFrame(child: content);
  }
}

class Marketplace extends StatefulWidget {
  const Marketplace({super.key});
  @override
  State<Marketplace> createState() => _MarketplaceState();
}

class _MarketplaceState extends State<Marketplace> {
  final query = <String, String>{};
  @override
  Widget build(BuildContext context) => Column(
    children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 6),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'YUNO LIFE SHOP',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w800,
                color: Theme.of(context).colorScheme.primary,
                letterSpacing: 2,
              ),
            ),
            heading(
              tx('好物，在附近。', 'いいもの、すぐそば。'),
              tx('坂户先行 · 本地中古交易', '坂戸から始まる、中古品マーケット'),
            ),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    textInputAction: TextInputAction.search,
                    decoration: InputDecoration(
                      hintText: tx('寻找商品、品牌、型号', '商品・ブランド・型番を検索'),
                      prefixIcon: const Icon(Icons.search),
                    ),
                    onSubmitted: (value) => setState(() => query['q'] = value),
                  ),
                ),
                IconButton(
                  onPressed: filters,
                  icon: const Icon(Icons.tune_rounded),
                  tooltip: tx('筛选', '絞り込み'),
                ),
              ],
            ),
          ],
        ),
      ),
      Expanded(
        child: RemoteView(
          key: ValueKey('market:${appState.revision}:$query'),
          path: 'listings',
          query: query,
          builder: (data) {
            final items = data['items'] as List;
            return ListView(
              padding: const EdgeInsets.all(20),
              children: [
                Text(
                  tx(
                    '发现 ${data['total']} 件商品 · 价格含税',
                    '${data['total']} 件の商品 · 税込価格',
                  ),
                ),
                if (items.isEmpty) emptyState(),
                LayoutBuilder(
                  builder: (context, box) => Wrap(
                    spacing: 12,
                    runSpacing: 12,
                    children: [
                      for (final item in items)
                        SizedBox(
                          width: (box.maxWidth - 12) / 2,
                          child: ProductCard(item: item),
                        ),
                    ],
                  ),
                ),
                if (items.length < data['total'])
                  TextButton(
                    onPressed: () => openPage(
                      context,
                      const CollectionPage(resource: 'listings'),
                    ),
                    child: Text(tx('查看全部商品', 'すべての商品を見る')),
                  ),
                simulationNote(),
              ],
            );
          },
        ),
      ),
    ],
  );

  Future<void> filters() async {
    try {
      await appState.ensureConfig();
      if (!mounted) return;
      final selected = Map<String, String>.from(query);
      final low = TextEditingController(text: query['price_min']);
      final high = TextEditingController(text: query['price_max']);
      final saved = await showModalBottomSheet<bool>(
        context: context,
        isScrollControlled: true,
        builder: (context) => StatefulBuilder(
          builder: (context, update) => SafeArea(
            child: SingleChildScrollView(
              padding: EdgeInsets.fromLTRB(
                20,
                20,
                20,
                MediaQuery.of(context).viewInsets.bottom + 20,
              ),
              child: Column(
                children: [
                  heading(tx('筛选商品', '商品を絞り込む')),
                  DropdownButtonFormField<String>(
                    initialValue: selected['category'] ?? '',
                    isExpanded: true,
                    decoration: InputDecoration(
                      labelText: label('category_slug'),
                    ),
                    items: [
                      DropdownMenuItem(
                        value: '',
                        child: Text(tx('全部类别', '全カテゴリー')),
                      ),
                      for (final cat in appState.config['categories'])
                        DropdownMenuItem(
                          value: cat['slug'],
                          child: Text(cat['name_${appState.language}']),
                        ),
                    ],
                    onChanged: (v) => update(() => selected['category'] = v!),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: selected['region'] ?? '',
                    isExpanded: true,
                    decoration: InputDecoration(labelText: label('region')),
                    items: [
                      DropdownMenuItem(
                        value: '',
                        child: Text(tx('全部地区', 'すべての地域')),
                      ),
                      for (final r in appState.config['regions'])
                        DropdownMenuItem(
                          value: r['code'],
                          child: Text(
                            r['name_${appState.language}'] ?? r['name_ja'],
                          ),
                        ),
                    ],
                    onChanged: (v) => update(() => selected['region'] = v!),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: low,
                    keyboardType: TextInputType.number,
                    decoration: InputDecoration(labelText: tx('最低价格', '最低価格')),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: high,
                    keyboardType: TextInputType.number,
                    decoration: InputDecoration(labelText: tx('最高价格', '最高価格')),
                  ),
                  SwitchListTile(
                    title: Text(tx('仅平台自营', '直営商品のみ')),
                    value: selected['owned'] == 'true',
                    onChanged: (v) => update(() => selected['owned'] = '$v'),
                  ),
                  FilledButton(
                    onPressed: () => Navigator.pop(context, true),
                    child: Text(tx('应用筛选', '絞り込む')),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
      if (saved == true && mounted) {
        if (int.tryParse(low.text) != null) {
          selected['price_min'] = low.text;
        } else {
          selected.remove('price_min');
        }
        if (int.tryParse(high.text) != null) {
          selected['price_max'] = high.text;
        } else {
          selected.remove('price_max');
        }
        setState(() {
          query.clear();
          query.addAll(selected);
        });
      }
      low.dispose();
      high.dispose();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(errorText(e))));
      }
    }
  }
}

class ProductCard extends StatelessWidget {
  final Json item;
  const ProductCard({super.key, required this.item});
  @override
  Widget build(BuildContext context) {
    final photos = item['photos'] as List;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () =>
            openPage(context, DetailPage(resource: 'listings', id: item['id'])),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            AspectRatio(
              aspectRatio: 1,
              child: photos.isEmpty
                  ? Container(
                      color: const Color(0xffe7ece3),
                      child: const Icon(Icons.inventory_2_outlined, size: 40),
                    )
                  : Image.network(
                      appState.imageUrl(photos.first['url']),
                      fit: BoxFit.cover,
                      errorBuilder: (_, _, _) =>
                          const Icon(Icons.broken_image_outlined),
                    ),
            ),
            Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item['title_${appState.language}']?.toString().isNotEmpty ==
                            true
                        ? item['title_${appState.language}']
                        : item['title_ja'],
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    money(item['price']),
                    style: const TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  Text(
                    label(item['condition_grade']),
                    style: const TextStyle(fontSize: 11),
                  ),
                  if (item['is_platform_owned'] == 1)
                    Text(
                      tx('平台自营', '直営商品'),
                      style: const TextStyle(
                        color: Color(0xff225947),
                        fontSize: 11,
                      ),
                    ),
                  if (item['demo'] == 1)
                    const Text('DEMO', style: TextStyle(fontSize: 11)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class TradeHub extends StatelessWidget {
  const TradeHub({super.key});
  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(20),
    children: [
      heading(
        tx('让闲置，继续生活。', '手放すものに、次の暮らしを。'),
        tx('拍照、确认、上架。每一步都由你决定。', '撮影、確認、出品。最後に決めるのはあなたです。'),
      ),
      panel(
        Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Icon(
              Icons.camera_alt_outlined,
              size: 58,
              color: Color(0xff225947),
            ),
            const SizedBox(height: 16),
            Text(
              tx('拍照开启 AI 一键发布', '写真から AI 出品'),
              style: const TextStyle(fontSize: 23, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 10),
            Text(
              tx('最多 10 张照片 · 双轴鉴定 · 同型号市场参考价', '写真10枚まで · 状態と真贋 · 同型番の市場参考価格'),
            ),
            const SizedBox(height: 18),
            FilledButton.icon(
              onPressed: () async {
                final result = await perform(context, 'oneclick_upload');
                if (result != null && context.mounted) {
                  await openPage(
                    context,
                    DetailPage(resource: 'drafts', id: result['id']),
                  );
                }
              },
              icon: const Icon(Icons.camera_alt),
              label: Text(tx('拍照发布', '撮影して出品')),
            ),
            TextButton(
              onPressed: () async {
                final result = await perform(context, 'listing_create');
                if (result != null && context.mounted) {
                  await openPage(
                    context,
                    DetailPage(resource: 'listings', id: result['id']),
                  );
                }
              },
              child: Text(tx('手动填写商品', '商品を手動入力')),
            ),
          ],
        ),
      ),
      for (final resource in ['auctions', 'buybacks', 'services', 'drafts'])
        panel(
          ListTile(
            leading: Icon(
              {
                'auctions': Icons.gavel,
                'buybacks': Icons.handshake_outlined,
                'services': Icons.cleaning_services_outlined,
                'drafts': Icons.edit_note,
              }[resource],
            ),
            title: Text(label(resource)),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => openPage(context, CollectionPage(resource: resource)),
          ),
        ),
      simulationNote(),
    ],
  );
}

class MarketPrices extends StatelessWidget {
  const MarketPrices({super.key});
  @override
  Widget build(BuildContext context) => RemoteView(
    key: ValueKey('prices:${appState.revision}'),
    path: 'market',
    builder: (data) {
      final moves = data['moves'] as Json;
      return ListView(
        padding: const EdgeInsets.all(20),
        children: [
          heading(
            label('prices'),
            tx('涨跌双榜 · 单个商品真实订单统计', '騰落ランキング · 商品ごとの実取引統計'),
          ),
          Text(
            tx(
              '上涨 ${moves['up_count']} · 下跌 ${moves['down_count']} · 样本不足 ${moves['insufficient']} 件已排除',
              '上昇 ${moves['up_count']} · 下落 ${moves['down_count']} · サンプル不足 ${moves['insufficient']} 件を除外',
            ),
          ),
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: board(context, moves['gainers'], true)),
              const SizedBox(width: 10),
              Expanded(child: board(context, moves['losers'], false)),
            ],
          ),
          Text(
            tx(
              '依据为最近与首次真实成交价格的变化。挂牌价与成交价分开展示。',
              '直近と初回の実取引価格の変化。出品価格と成約価格は別表示です。',
            ),
          ),
          heading(tx('品类行情', 'カテゴリー相場')),
          for (final cat in data['categories'])
            panel(
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    cat['name_${appState.language}'],
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                  Text(
                    tx(
                      '在售 ${cat['active']} · 成交 ${cat['completed']} · 样本 ${cat['completed']}',
                      '販売中 ${cat['active']} · 成約 ${cat['completed']} · サンプル ${cat['completed']}',
                    ),
                  ),
                  Text(
                    '${tx('真实成交区间 ', '実成約価格帯 ')}${money(cat['low'])} – ${money(cat['high'])}',
                  ),
                  if (cat['completed'] < 10)
                    Text(tx('样本较少，仅供参考', 'サンプルが少ないため参考情報です')),
                ],
              ),
            ),
          heading(tx('12 周成交走势', '12週間の成約推移')),
          for (final week in data['curve'])
            ListTile(
              title: Text(week['week']),
              subtitle: Text(
                tx('成交 ${week['count']} 笔', '成約 ${week['count']} 件'),
              ),
              trailing: Text(money(week['avg'])),
            ),
        ],
      );
    },
  );
  Widget board(BuildContext context, List items, bool up) => panel(
    Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          up ? tx('▲ 上涨榜', '▲ 上昇') : tx('▼ 下跌榜', '▼ 下落'),
          style: TextStyle(
            color: up ? Colors.green.shade800 : Colors.red.shade800,
            fontWeight: FontWeight.w800,
          ),
        ),
        if (items.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Text(tx('暂无足够样本', 'サンプル不足')),
          ),
        for (var i = 0; i < items.length; i++)
          InkWell(
            onTap: () => openPage(
              context,
              DetailPage(resource: 'listings', id: items[i]['listing_id']),
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (i == 0)
                    Text(up ? tx('最高涨幅', '最大上昇') : tx('最高跌幅', '最大下落')),
                  Text(
                    items[i]['title_${appState.language}'] ??
                        items[i]['title_ja'],
                    maxLines: 2,
                  ),
                  Text(
                    '${items[i]['pct'].toStringAsFixed(1)}%',
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.w800,
                      color: up ? Colors.green.shade800 : Colors.red.shade800,
                    ),
                  ),
                  Text(
                    tx(
                      '样本 ${items[i]['orders']} 笔',
                      'サンプル ${items[i]['orders']} 件',
                    ),
                  ),
                  Text(
                    '${money(items[i]['first'])} → ${money(items[i]['latest'])}',
                    style: const TextStyle(fontSize: 11),
                  ),
                ],
              ),
            ),
          ),
      ],
    ),
  );
}

class ProfilePage extends StatelessWidget {
  const ProfilePage({super.key});
  @override
  Widget build(BuildContext context) {
    final user = appState.user;
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        heading(
          user?['display_name'] ?? tx('欢迎来到 YUNO', 'YUNO へようこそ'),
          user == null
              ? tx('一个账号，买卖好物。', 'ひとつのアカウントで、売る・買う。')
              : label(user['role']),
        ),
        if (appState.token == null)
          Wrap(
            spacing: 12,
            children: [
              FilledButton(
                onPressed: () => perform(context, 'login'),
                child: Text(label('login')),
              ),
              OutlinedButton(
                onPressed: () => perform(context, 'register'),
                child: Text(label('register')),
              ),
            ],
          ),
        if (appState.token != null) ...[
          for (final resource in [
            'listings',
            'offers',
            'threads',
            'buybacks',
            'services',
            'deliveries',
            'refunds',
            'disputes',
            'jobs',
          ])
            ListTile(
              title: Text(
                resource == 'listings' ? tx('我的商品', '出品した商品') : label(resource),
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => openPage(
                context,
                CollectionPage(
                  resource: resource,
                  query: resource == 'listings' ? {'mine': 'true'} : null,
                ),
              ),
            ),
          if (['admin', 'operator', 'appraiser'].contains(user?['role']))
            ListTile(
              title: Text(tx('运营后台', '運営管理')),
              leading: const Icon(Icons.admin_panel_settings_outlined),
              onTap: () => openPage(context, const AdminHub()),
            ),
        ],
        heading(tx('偏好设置', '設定')),
        Text(tx('界面语言', '表示言語')),
        const SizedBox(height: 8),
        SegmentedButton<String>(
          showSelectedIcon: false,
          segments: const [
            ButtonSegment(value: 'zh', label: Text('中文')),
            ButtonSegment(value: 'ja', label: Text('日本語')),
            ButtonSegment(value: 'system', label: Icon(Icons.phone_android)),
          ],
          selected: {appState.choice},
          onSelectionChanged: (value) => appState.languageChoice(value.first),
        ),
        Text(tx('手机图标代表跟随系统', '端末アイコンはシステム設定に従います')),
        ListTile(
          title: Text(tx('服务器连接', 'サーバー接続')),
          subtitle: Text(appState.server),
          onTap: () => openPage(context, const ConnectionPage()),
        ),
        for (final key in ['terms', 'privacy', 'returns', 'prohibited'])
          ListTile(
            title: Text(label(key)),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => openPage(
              context,
              PageFrame(
                child: RemoteView(
                  path: 'rules/$key',
                  builder: (data) => ListView(
                    padding: const EdgeInsets.all(20),
                    children: [
                      heading(label(key)),
                      SelectableText(
                        data['text'],
                        style: const TextStyle(height: 1.7),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        if (appState.token != null)
          TextButton(
            onPressed: () async {
              try {
                await appState.logout();
              } catch (e) {
                if (context.mounted) {
                  ScaffoldMessenger.of(context)
                      .showSnackBar(SnackBar(content: Text(errorText(e))));
                }
              }
            },
            child: Text(label('logout')),
          ),
        simulationNote(),
      ],
    );
  }
}

class CollectionPage extends StatefulWidget {
  final String resource;
  final Map<String, String>? query;
  final bool embedded;
  const CollectionPage({
    super.key,
    required this.resource,
    this.query,
    this.embedded = false,
  });
  @override
  State<CollectionPage> createState() => _CollectionPageState();
}

class _CollectionPageState extends State<CollectionPage> {
  int offset = 0;
  @override
  Widget build(BuildContext context) {
    final needsLogin =
        !['listings', 'auctions'].contains(widget.resource) &&
        !widget.resource.startsWith('admin/');
    if (appState.token == null && needsLogin) {
      final login = Center(
        child: FilledButton(
          onPressed: () async {
            await perform(context, 'login');
            if (mounted) setState(() {});
          },
          child: Text(label('login')),
        ),
      );
      return widget.embedded ? login : PageFrame(child: login);
    }
    final content = RemoteView(
      key: ValueKey('${widget.resource}:${appState.revision}:$offset'),
      path: widget.resource,
      query: {...?widget.query, 'offset': '$offset'},
      builder: (data) {
        final items = data['items'] as List? ?? [];
        return ListView(
          padding: const EdgeInsets.all(20),
          children: [
            heading(label(widget.resource.replaceFirst('admin/', ''))),
            if (widget.resource == 'services') ...[
              for (final kind in [
                'cleaning_home',
                'transport_small',
                'local_delivery',
              ])
                Card(
                  child: ListTile(
                    title: Text(label(kind)),
                    trailing: const Icon(Icons.add_circle_outline),
                    onTap: () async {
                      final result = await perform(context, 'service_create', {
                        'kind': kind,
                      });
                      if (result != null && context.mounted) {
                        await openPage(
                          context,
                          DetailPage(resource: 'services', id: result['id']),
                        );
                      }
                    },
                  ),
                ),
            ],
            if (data['item'] != null) panel(infoData(data['item'])),
            if (items.isEmpty && data['item'] == null) emptyState(),
            for (final item in items)
              widget.resource == 'listings'
                  ? ProductCard(item: item)
                  : panel(
                      ListTile(
                        title: Text(
                          item['title_${appState.language}'] ??
                              item['title_ja'] ??
                              (item['kind'] == null
                                  ? '#${item['id']}'
                                  : label(item['kind'])),
                        ),
                        subtitle: Text(
                          label(item['status'] ?? '') +
                              (item['body'] == null ? '' : '\n${item['body']}'),
                        ),
                        trailing: Text(
                          money(
                            item['total'] ??
                                item['amount'] ??
                                item['start_price'] ??
                                item['quote'],
                          ),
                        ),
                        onTap: () async {
                          if (widget.resource == 'threads') {
                            await openPage(
                              context,
                              ThreadPage(
                                lid: item['listing_id'],
                                buyerId: item['buyer_id'],
                              ),
                            );
                          } else if (widget.resource.startsWith('admin/')) {
                            await openPage(
                              context,
                              AdminRecord(
                                resource: widget.resource.substring(6),
                                item: item,
                              ),
                            );
                          } else {
                            await openPage(
                              context,
                              DetailPage(
                                resource: widget.resource,
                                id: item['id'],
                              ),
                            );
                          }
                          if (mounted) setState(() {});
                        },
                      ),
                    ),
            if (data['total'] != null && data['total'] > 50)
              Row(
                children: [
                  TextButton(
                    onPressed: offset == 0
                        ? null
                        : () => setState(() => offset -= 50),
                    child: Text(tx('上一页', '前へ')),
                  ),
                  TextButton(
                    onPressed: offset + 50 >= data['total']
                        ? null
                        : () => setState(() => offset += 50),
                    child: Text(tx('下一页', '次へ')),
                  ),
                ],
              ),
            simulationNote(),
          ],
        );
      },
    );
    return widget.embedded ? content : PageFrame(child: content);
  }
}

class DetailPage extends StatefulWidget {
  final String resource;
  final int id;
  const DetailPage({super.key, required this.resource, required this.id});
  @override
  State<DetailPage> createState() => _DetailPageState();
}

class _DetailPageState extends State<DetailPage> {
  int revision = 0;
  @override
  Widget build(BuildContext context) => PageFrame(
    child: RemoteView(
      key: ValueKey('${widget.resource}:${widget.id}:$revision'),
      path: '${widget.resource}/${widget.id}',
      builder: (data) {
        final item = data['item'] as Json;
        final related = data['related'] as Json? ?? {};
        final actions = availableActions(item, related);
        final title =
            item['title_${appState.language}'] ??
            item['title_ja'] ??
            item['name'] ??
            '${label(widget.resource)} #${widget.id}';
        final body = Map<String, dynamic>.from(item);
        for (final key in [
          'draft',
          'recognition',
          'appraisal',
          'valuation',
          'detail_checklist',
        ]) {
          body.remove(key);
        }
        return ListView(
          padding: const EdgeInsets.all(20),
          children: [
            heading(title),
            if (item['photos'] != null) ProductPhotos(photos: item['photos']),
            if (widget.resource == 'listings') ...[
              heading(money(item['price']), tx('价格含税', '税込価格')),
              if (item['demo'] == 1) const Text('DEMO'),
            ],
            if (related['listing'] != null)
              ListTile(
                leading: const Icon(Icons.inventory_2_outlined),
                title: Text(
                  related['listing']['title_${appState.language}'] ??
                      related['listing']['title_ja'],
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => openPage(
                  context,
                  DetailPage(
                    resource: 'listings',
                    id: related['listing']['id'],
                  ),
                ),
              ),
            if (widget.resource == 'drafts') ...[
              for (final field in ['recognition', 'appraisal', 'valuation'])
                if (item[field] != null && (item[field] as Map).isNotEmpty)
                  panel(
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          label(field),
                          style: const TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 10),
                        infoData(item[field]),
                        if (field == 'valuation') ...[
                          const SizedBox(height: 12),
                          const Text('此报价为AI根据现实数据做出的估价，用户可以根据自身另行填写'),
                          if (appState.language == 'ja')
                            const Text('AI による現実のデータに基づく査定です。価格はご自身で変更できます。'),
                        ],
                      ],
                    ),
                  ),
              if ((item['detail_checklist'] as List?)?.isNotEmpty == true)
                panel(
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(tx('建议补充的细节照片', '追加するとよい詳細写真')),
                      infoData(item['detail_checklist']),
                    ],
                  ),
                ),
            ],
            panel(infoData(body)),
            if (widget.resource == 'listings' && item['seller_id'] != null)
              OutlinedButton.icon(
                icon: const Icon(Icons.person_outline),
                label: Text(tx('卖家资料与评价', '出品者とレビュー')),
                onPressed: () =>
                    openPage(context, PublicProfilePage(id: item['seller_id'])),
              ),
            if (widget.resource == 'jobs') panel(infoData(item['result'])),
            if (related['bids'] != null)
              panel(
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(tx('出价记录', '入札履歴')),
                    infoData(related['bids']),
                  ],
                ),
              ),
            simulationNote(),
            for (final action in actions)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 5),
                child: FilledButton.tonal(
                  onPressed: () => runAction(action),
                  child: Padding(
                    padding: const EdgeInsets.all(6),
                    child: Text(
                      label(action.$1) +
                          (action.$2.containsKey('idx')
                              ? ' · ${tx('照片', '写真')} ${action.$2['idx'] + 1}'
                              : action.$2.containsKey('pid')
                              ? ' · #${action.$2['pid']}'
                              : ''),
                    ),
                  ),
                ),
              ),
            if (widget.resource == 'listings' &&
                appState.user != null &&
                item['seller_id'] != null)
              OutlinedButton.icon(
                icon: const Icon(Icons.chat_bubble_outline),
                onPressed: item['seller_id'] == appState.user!['id']
                    ? () => openPage(
                        context,
                        const CollectionPage(resource: 'threads'),
                      )
                    : () => openPage(
                        context,
                        ThreadPage(
                          lid: widget.id,
                          buyerId: appState.user!['id'],
                        ),
                      ),
                label: Text(label('threads')),
              ),
          ],
        );
      },
    ),
  );

  Future<void> runAction((String, Json, Json) action) async {
    if (appState.token == null) {
      await perform(context, 'login');
      if (appState.token == null || !mounted) return;
    }
    final result = await openPage<Json>(
      context,
      ActionForm(
        action: action.$1,
        values: action.$2,
        initialValues: action.$3,
      ),
    );
    if (!mounted || result == null) return;
    if (result['resource'] != null &&
        result['id'] != null &&
        (result['resource'] != widget.resource || result['id'] != widget.id) &&
        result['resource'] != 'users') {
      await openPage(
        context,
        DetailPage(resource: result['resource'], id: result['id']),
      );
    }
    if (mounted) setState(() => revision++);
  }

  List<(String, Json, Json)> availableActions(Json item, Json related) {
    final result = <(String, Json, Json)>[];
    void add(String name, Json values, [Json initial = const {}]) {
      result.add((name, values, initial));
    }

    final uid = appState.user?['id'];
    final role = appState.user?['role'];
    final operator = ['admin', 'operator'].contains(role);
    final state = item['status'];
    final id = widget.id;
    switch (widget.resource) {
      case 'listings':
        if (uid == item['seller_id']) {
          add('listing_photo_add', {'lid': id});
          for (final photo in item['photos']) {
            add('listing_photo_cover', {'lid': id, 'pid': photo['id']});
            add('listing_photo_replace', {'lid': id, 'pid': photo['id']});
            add('listing_photo_delete', {'lid': id, 'pid': photo['id']});
          }
          if (state == 'active') {
            add('auction_create', {'lid': id});
            add('buyback_new', {'listing_id': id});
          }
        } else {
          if (state == 'active') {
            add('buy', {'lid': id});
            add('offer', {'lid': id});
          }
          add('follow', {'lid': id});
          add('unfollow', {'lid': id});
        }
      case 'drafts':
        if (state == 'published') break;
        add('oneclick_photo_add', {'did': id});
        for (var i = 0; i < (item['photos'] as List).length; i++) {
          add('draft_photo_cover', {'did': id, 'idx': i});
          add('draft_photo_replace', {'did': id, 'idx': i});
          add('oneclick_photo_delete', {'did': id, 'idx': i});
        }
        add('oneclick_recognize', {'did': id});
        if (state == 'recognized') {
          final draft = Map<String, dynamic>.from(item['draft'] ?? {});
          add('oneclick_model_confirm', {'did': id}, draft);
          add('ai_job_create', {
            'kind': 'oneclick_valuation',
            'draft_id': '$id',
          });
          final suggested = item['valuation']?['suggested_price'];
          if (suggested != null) draft['price'] = suggested;
          add('oneclick_publish', {'did': id}, draft);
        }
      case 'orders':
        if (state == 'pending_payment') {
          if (uid == item['buyer_id']) {
            add('order_pay', {
              'oid': id,
              'idempotency_key': 'native-order-$id-$uid',
            });
          }
          add('order_cancel', {'oid': id});
        }
        if (state == 'paid') add('order_complete', {'oid': id});
        if (['paid', 'completed'].contains(state)) {
          add('delivery_request', {'oid': id});
          add('refund_request', {'oid': id});
          add('dispute_create', {'oid': id});
        }
        if (state == 'completed') add('order_review', {'oid': id});
      case 'offers':
        final own = related['listing']?['seller_id'] == uid;
        if (state == 'pending' && own) {
          add('offer_accept', {'oid': id});
          add('offer_reject', {'oid': id});
          add('offer_counter', {'oid': id});
        }
        if (state == 'countered' && uid == item['buyer_id']) {
          add('offer_accept_counter', {'oid': id});
        }
      case 'auctions':
        if (state == 'active') {
          if (related['listing']?['seller_id'] != uid) {
            if (item['deposit_required'] == 1) {
              add('auction_deposit', {'aid': id});
            }
            add('auction_bid', {'aid': id});
            if (item['buy_now_price'] != null) {
              add('auction_buy_now', {'aid': id});
            }
          }
          add('auction_settle', {'aid': id});
        }
      case 'buybacks':
        if (operator) {
          if (['submitted', 'estimated'].contains(state)) {
            add('buyback_review', {'bid': id});
          }
          if (state == 'reviewing') add('buyback_quote', {'bid': id});
          if ([
            'submitted',
            'estimated',
            'reviewing',
            'quoted',
          ].contains(state)) {
            add('buyback_reject', {'bid': id});
          }
          if (state == 'pickup_scheduled') add('buyback_inspect', {'bid': id});
          if (state == 'inspected') add('buyback_pay', {'bid': id});
        }
        if (uid == item['seller_id']) {
          if (state == 'quoted') add('buyback_accept', {'bid': id});
          if (state == 'accepted') add('buyback_pickup', {'bid': id});
        }
      case 'services':
        if (operator) {
          if (state == 'requested') add('service_confirm', {'sid': id});
          if (state == 'confirmed') add('service_start', {'sid': id});
          if (state == 'in_progress') add('service_complete', {'sid': id});
        }
        if (['requested', 'confirmed'].contains(state)) {
          add('service_cancel', {'sid': id});
        }
      case 'deliveries':
        if (operator || role == 'courier') {
          if (state == 'requested') add('delivery_assign', {'did': id});
          if (state == 'assigned') add('delivery_pickup', {'did': id});
          if (state == 'picked_up') add('delivery_deliver', {'did': id});
        }
        if (state == 'delivered') add('delivery_confirm', {'did': id});
      case 'refunds':
        if (operator && state == 'requested') add('refund_decide', {'rid': id});
      case 'disputes':
        if (operator && state == 'open') add('dispute_decide', {'did': id});
    }
    return result;
  }
}

class PublicProfilePage extends StatelessWidget {
  final int id;
  const PublicProfilePage({super.key, required this.id});
  @override
  Widget build(BuildContext context) => PageFrame(
    child: RemoteView(
      path: 'profiles/$id',
      builder: (data) => ListView(
        padding: const EdgeInsets.all(20),
        children: [
          heading(data['item']['display_name']),
          Text(label(data['item']['role'])),
          heading(tx('交易评价', '取引レビュー')),
          Text(
            data['item']['average'] == null
                ? tx('暂无评价', 'まだ評価がありません')
                : '${(data['item']['average'] as num).toStringAsFixed(1)} ★ · ${data['item']['count']}',
          ),
          for (final review in data['reviews']) panel(infoData(review)),
        ],
      ),
    ),
  );
}

class ThreadPage extends StatefulWidget {
  final int lid;
  final int buyerId;
  const ThreadPage({super.key, required this.lid, required this.buyerId});
  @override
  State<ThreadPage> createState() => _ThreadPageState();
}

class _ThreadPageState extends State<ThreadPage> {
  final input = TextEditingController();
  int revision = 0;
  bool busy = false;
  Object? error;
  @override
  void dispose() {
    input.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PageFrame(
    child: Column(
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: heading(label('threads')),
        ),
        Expanded(
          child: RemoteView(
            key: ValueKey(revision),
            path: 'threads/${widget.lid}/${widget.buyerId}',
            builder: (data) => ListView(
              padding: const EdgeInsets.all(20),
              children: [
                if ((data['items'] as List).isEmpty) emptyState(),
                for (final message in data['items'])
                  Align(
                    alignment: message['sender_id'] == appState.user?['id']
                        ? Alignment.centerRight
                        : Alignment.centerLeft,
                    child: panel(
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(message['body']),
                          Text(
                            message['created_at'],
                            style: const TextStyle(fontSize: 10),
                          ),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
        if (error != null) Text(errorText(error!)),
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: input,
                  decoration: InputDecoration(labelText: label('body')),
                ),
              ),
              IconButton(
                onPressed: busy
                    ? null
                    : () async {
                        if (input.text.trim().isEmpty) return;
                        setState(() {
                          busy = true;
                          error = null;
                        });
                        try {
                          await appState.action('thread_post', {
                            'lid': widget.lid,
                            'buyer_id': widget.buyerId,
                            'body': input.text,
                          });
                          input.clear();
                          if (mounted) setState(() => revision++);
                        } catch (e) {
                          if (mounted) setState(() => error = e);
                        } finally {
                          if (mounted) setState(() => busy = false);
                        }
                      },
                icon: const Icon(Icons.send_outlined),
                tooltip: label('thread_post'),
              ),
            ],
          ),
        ),
      ],
    ),
  );
}

class AdminHub extends StatelessWidget {
  const AdminHub({super.key});
  @override
  Widget build(BuildContext context) {
    final role = appState.user?['role'];
    final operator = ['operator', 'admin'].contains(role);
    return PageFrame(
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          heading(tx('运营后台', '運営管理')),
          if (operator) ...[
            for (final resource in [
              'orders',
              'buybacks',
              'deliveries',
              'services',
              'refunds',
              'disputes',
            ])
              ListTile(
                title: Text(label(resource)),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => openPage(
                  context,
                  CollectionPage(
                    resource: resource,
                    query: const {'admin': 'true'},
                  ),
                ),
              ),
            for (final resource in [
              'inventory',
              'profit',
              'alerts',
              'suggestions',
              'expenses',
              'audit',
            ])
              ListTile(
                title: Text(label(resource)),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => openPage(
                  context,
                  CollectionPage(resource: 'admin/$resource'),
                ),
              ),
            for (final action in [
              'admin_run_anomalies',
              'admin_run_pricing',
              'admin_expenses_post',
            ])
              OutlinedButton(
                onPressed: () => perform(context, action),
                child: Text(label(action)),
              ),
          ],
          ListTile(
            title: Text(label('high-value')),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => openPage(
              context,
              const CollectionPage(resource: 'admin/high-value'),
            ),
          ),
          if (role == 'admin') ...[
            ListTile(
              title: Text(label('users')),
              onTap: () => openPage(
                context,
                const CollectionPage(resource: 'admin/users'),
              ),
            ),
            ListTile(
              title: Text(label('settings')),
              onTap: () => openPage(
                context,
                const CollectionPage(resource: 'admin/settings'),
              ),
            ),
            OutlinedButton(
              onPressed: () => perform(context, 'admin_settings_post'),
              child: Text(label('admin_settings_post')),
            ),
          ],
        ],
      ),
    );
  }
}

class AdminRecord extends StatelessWidget {
  final String resource;
  final Json item;
  const AdminRecord({super.key, required this.resource, required this.item});
  @override
  Widget build(BuildContext context) {
    final options = <(String, Json)>[
      if (resource == 'users') ('admin_user_role', {'uid': item['id']}),
      if (resource == 'high-value')
        ('admin_high_value_review', {'hid': item['id']}),
      if (resource == 'alerts') ('admin_alert_ack', {'aid': item['id']}),
      if (resource == 'suggestions') ...[
        ('admin_suggestion_approve', {'sid': item['id']}),
        ('admin_suggestion_reject', {'sid': item['id']}),
      ],
    ];
    return PageFrame(
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          heading(label(resource)),
          panel(infoData(item)),
          for (final option in options)
            FilledButton.tonal(
              onPressed: () => perform(context, option.$1, option.$2),
              child: Text(label(option.$1)),
            ),
        ],
      ),
    );
  }
}
