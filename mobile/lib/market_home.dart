import 'package:flutter/material.dart';
import 'design.dart';
import 'labels.dart';
import 'session.dart';

class TrialNotice extends StatelessWidget {
  final Session api;
  const TrialNotice({super.key, required this.api});
  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        margin: const EdgeInsets.only(bottom: 20),
        padding: const EdgeInsets.all(15),
        decoration: BoxDecoration(
            color: Colors.white, border: Border.all(color: YunoColors.line)),
        child: Text(
            api.tr(
                '试用版：可直接浏览市场、行情与商品详情。注册、发布与 AI 功能连接平台；发布前请核对识别、鉴定与估价结果。支付与配送均为模拟，不产生真实扣款。',
                '試用版：市場・相場・商品詳細を閲覧できます。登録・出品・AI機能はサーバーに接続します。結果を確認してから公開してください。決済・配送は模擬で、実際の請求はありません。'),
            style: const TextStyle(fontSize: 12, height: 1.8)),
      );
}

class MarketHome extends StatefulWidget {
  final Session api;
  final VoidCallback onTrends, onBrowse, onPublish;
  final void Function(Json item) onListing;
  final void Function(Json auction) onAuction;
  final Widget Function(Json item) card;
  final Future<void> Function(Json item) onFavorite;
  const MarketHome(
      {super.key,
      required this.api,
      required this.onTrends,
      required this.onBrowse,
      required this.onPublish,
      required this.onListing,
      required this.onAuction,
      required this.card,
      required this.onFavorite});
  @override
  State<MarketHome> createState() => _MarketHomeState();
}

class _MarketHomeState extends State<MarketHome> {
  late Future<List<Json>> data;
  bool rankings = true;
  String category = '', catalogCategory = '', sort = 'newest';
  bool favoritesOnly = false;
  final search = TextEditingController();
  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  Session get api => widget.api;
  @override
  void initState() {
    super.initState();
    data = load();
  }

  Future<List<Json>> load() => Future.wait([
        api.get('/market'),
        api.get('/listings'),
        api.get('/auctions'),
      ]);
  Future<void> reload() async {
    setState(() => data = load());
    await data;
  }

  Text section(String title) => Text(title,
      style: const TextStyle(
          fontSize: 19,
          fontFamily: 'YunoSerif',
          fontFamilyFallback: ['Songti SC', 'serif'],
          fontWeight: FontWeight.w700));
  String catName(dynamic slug) {
    for (final c in api.config['categories'] ?? []) {
      if (c['slug'] == slug) return api.name(Map<String, dynamic>.from(c));
    }
    return '';
  }

  Widget categoryTabs() => SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(children: [
        for (final entry in <(String, String)>[
          ('', api.tr('全部', 'すべて')),
          ('furniture', api.tr('家具家居', '家具')),
          ('appliance', api.tr('家电厨房', '家電')),
          ('watch', api.tr('手表', '時計')),
          ('antique', api.tr('古董艺术', '骨董・美術')),
        ])
          Padding(
              padding: const EdgeInsets.only(right: 8),
              child: TextButton(
                  onPressed: () => setState(() => category = entry.$1),
                  style: TextButton.styleFrom(
                      foregroundColor: category == entry.$1
                          ? Colors.white
                          : YunoColors.muted,
                      backgroundColor: category == entry.$1
                          ? YunoColors.primary
                          : Colors.transparent,
                      padding: const EdgeInsets.symmetric(horizontal: 13),
                      shape: const StadiumBorder()),
                  child: Text(entry.$2, style: const TextStyle(fontSize: 12))))
      ]));
  Widget rankBoard(List<Json> items, bool up) => marketRankBoard(
      api: api, items: items, up: up, onListing: widget.onListing);
  Widget productCard(Json item) {
    final followed =
        (api.me?['following'] as List? ?? []).any((i) => i['id'] == item['id']);
    return Stack(children: [
      widget.card(item),
      Positioned(
          top: 5,
          right: 5,
          child: IconButton(
            tooltip: api.tr('收藏商品', 'お気に入り'),
            style: IconButton.styleFrom(
                backgroundColor: Colors.white.withValues(alpha: 0.9)),
            icon: Icon(followed ? Icons.favorite : Icons.favorite_border,
                color: followed ? const Color(0xffb82e35) : YunoColors.muted,
                size: 18),
            onPressed: () async {
              try {
                await widget.onFavorite(item);
                if (mounted) setState(() {});
              } catch (_) {
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                      content:
                          Text(api.tr('收藏未完成，请重试', '操作できませんでした。再試行してください。'))));
                }
              }
            },
          ))
    ]);
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<List<Json>>(
      future: data,
      builder: (context, snapshot) {
        if (!snapshot.hasData && !snapshot.hasError) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(
              child: TextButton(
                  onPressed: reload,
                  child: Text(api.tr('连接失败，重试', '接続できません。再試行'))));
        }
        final market = snapshot.data![0];
        final summary = Map<String, dynamic>.from(market['overview'] ?? {});
        final moves = Map<String, dynamic>.from(market['moves'] ?? {});
        final items = List<Json>.from(snapshot.data![1]['items'] ?? []);
        final auctions = List<Json>.from(snapshot.data![2]['items'] ?? []);
        final categories = List<Json>.from(market['categories'] ?? []);
        final watch = categories.where((c) => c['slug'] == 'watch').firstOrNull;
        final gainers = List<Json>.from(moves['gainers'] ?? [])
            .where((i) => category.isEmpty || i['cat_slug'] == category)
            .toList();
        final losers = List<Json>.from(moves['losers'] ?? [])
            .where((i) => category.isEmpty || i['cat_slug'] == category)
            .toList();
        final selected = items
            .where((item) =>
                category.isEmpty ||
                (api.config['categories'] as List? ?? []).any((c) =>
                    c['slug'] == category && c['id'] == item['category_id']))
            .toList();
        final owned = items.where((i) => i['is_platform_owned'] == 1).toList();
        final favorites =
            (api.me?['following'] as List? ?? []).map((i) => i['id']).toSet();
        final catalog = items
            .where((item) =>
                (catalogCategory.isEmpty ||
                    (api.config['categories'] as List? ?? []).any((c) =>
                        c['slug'] == catalogCategory &&
                        c['id'] == item['category_id'])) &&
                (!favoritesOnly || favorites.contains(item['id'])) &&
                (search.text.trim().isEmpty ||
                    '${api.title(item)} ${item['title_ja']} ${item['title_zh']}'
                        .toLowerCase()
                        .contains(search.text.trim().toLowerCase())))
            .toList();
        if (sort != 'newest') {
          catalog.sort((a, b) {
            final first =
                num.tryParse('${a['effective_price'] ?? a['price']}') ?? 0;
            final second =
                num.tryParse('${b['effective_price'] ?? b['price']}') ?? 0;
            return sort == 'low'
                ? first.compareTo(second)
                : second.compareTo(first);
          });
        }

        return RefreshIndicator(
            onRefresh: reload,
            child: ListView(
                padding: const EdgeInsets.fromLTRB(15, 16, 15, 24),
                children: [
                  TrialNotice(api: api),
                  Card(
                      child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                    api.tr(
                                        '平台总成交额（模拟支付）· 坂户市', '取引総額（模擬決済）・坂戸市'),
                                    style: const TextStyle(
                                        fontSize: 11, color: YunoColors.muted)),
                                const SizedBox(height: 5),
                                Text(yen(summary['gmv'] ?? 0),
                                    style: const TextStyle(
                                        fontFamily: 'Georgia',
                                        fontSize: 36,
                                        fontWeight: FontWeight.w600,
                                        letterSpacing: -1)),
                                const SizedBox(height: 9),
                                Wrap(
                                    spacing: 8,
                                    runSpacing: 6,
                                    crossAxisAlignment:
                                        WrapCrossAlignment.center,
                                    children: [
                                      Text(
                                          api.tr('近 30 天成交额较前 30 天',
                                              '直近30日・前30日比'),
                                          style: const TextStyle(
                                              fontSize: 12,
                                              color: YunoColors.muted)),
                                      Container(
                                          padding: const EdgeInsets.symmetric(
                                              horizontal: 8, vertical: 6),
                                          decoration: BoxDecoration(
                                              color: YunoColors.sage,
                                              borderRadius:
                                                  BorderRadius.circular(4)),
                                          child: Text(
                                              summary['change_pct'] == null
                                                  ? api.tr('样本不足，暂不计算涨跌',
                                                      'データ不足のため算出しません')
                                                  : '${summary['change_pct']}%',
                                              style: const TextStyle(
                                                  fontSize: 10,
                                                  fontWeight: FontWeight.w700,
                                                  color: YunoColors.muted))),
                                    ]),
                                const SizedBox(height: 12),
                                Wrap(spacing: 20, runSpacing: 7, children: [
                                  Text(
                                      api.tr('${summary['orders'] ?? 0} 笔订单',
                                          '注文 ${summary['orders'] ?? 0} 件'),
                                      style: const TextStyle(fontSize: 12)),
                                  Text(
                                      api.tr('${summary['active_count'] ?? 0} 件在售 · 挂牌总价 ',
                                              '${summary['active_count'] ?? 0} 点出品中・出品総額 ') +
                                          yen(summary['active_asking_total'] ??
                                              0),
                                      style: const TextStyle(fontSize: 12)),
                                ]),
                                const SizedBox(height: 9),
                                Text(
                                    api.tr(
                                        '${summary['paid_orders'] ?? 0} 笔成交（模拟支付，排除 DEMO）',
                                        '取引 ${summary['paid_orders'] ?? 0} 件（模擬決済・DEMO除外）'),
                                    style: const TextStyle(
                                        fontSize: 11, color: YunoColors.muted)),
                                const Divider(height: 26),
                                SizedBox(
                                    height: 84,
                                    width: double.infinity,
                                    child: CustomPaint(
                                        painter: VolumeLine(List<Json>.from(
                                            summary['volume_curve'] ?? [])))),
                                const SizedBox(height: 6),
                                Align(
                                    alignment: Alignment.centerRight,
                                    child: Text(
                                        api.tr('近 12 周成交额走势（排除 DEMO）',
                                            '直近12週の取引総額（DEMO除外）'),
                                        style: const TextStyle(
                                            fontSize: 10,
                                            color: YunoColors.muted))),
                                const Divider(height: 24),
                                Row(children: [
                                  Expanded(
                                      child: Text(
                                          '${api.tr('手表 品类均价 ', '時計 平均価格 ')}${yen(watch?['avg'])} (${watch?['completed'] ?? 0})',
                                          style: const TextStyle(
                                              fontSize: 11,
                                              color: YunoColors.muted))),
                                  InkWell(
                                      onTap: widget.onTrends,
                                      child: Text(api.tr('看完整行情 →', '相場を詳しく →'),
                                          style: const TextStyle(
                                              fontSize: 11,
                                              fontWeight: FontWeight.w700,
                                              decoration:
                                                  TextDecoration.underline))),
                                ]),
                              ]))),
                  const SizedBox(height: 12),
                  Row(children: [
                    Expanded(child: section(api.tr('商品行情', '商品相場'))),
                    Container(
                        padding: const EdgeInsets.all(3),
                        decoration: BoxDecoration(
                            color: YunoColors.sage,
                            borderRadius: BorderRadius.circular(28)),
                        child: Row(children: [
                          for (final entry in [
                            (false, api.tr('现货', '出品中')),
                            (true, api.tr('涨跌榜', '変動率'))
                          ])
                            InkWell(
                                onTap: () =>
                                    setState(() => rankings = entry.$1),
                                child: Container(
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 15, vertical: 8),
                                    decoration: BoxDecoration(
                                        color: rankings == entry.$1
                                            ? Colors.white
                                            : Colors.transparent,
                                        borderRadius: BorderRadius.circular(25),
                                        boxShadow: rankings == entry.$1
                                            ? [
                                                const BoxShadow(
                                                    color: Color(0x14000000),
                                                    blurRadius: 4,
                                                    offset: Offset(0, 2))
                                              ]
                                            : null),
                                    child: Text(entry.$2,
                                        style: TextStyle(
                                            fontSize: 12,
                                            fontWeight: rankings == entry.$1
                                                ? FontWeight.w700
                                                : FontWeight.w400,
                                            color: rankings == entry.$1
                                                ? YunoColors.ink
                                                : YunoColors.muted)))),
                        ])),
                  ]),
                  const SizedBox(height: 8),
                  categoryTabs(),
                  const SizedBox(height: 8),
                  if (rankings) ...[
                    rankBoard(gainers, true),
                    rankBoard(losers, false),
                    Text(
                        api.local(market['basis'] ??
                            {
                              'zh': '平台真实订单；挂牌价不计入涨跌。',
                              'ja': '実取引価格のみ。出品価格は含みません。'
                            }),
                        style: const TextStyle(
                            fontSize: 10, color: YunoColors.muted)),
                    Align(
                        alignment: Alignment.centerRight,
                        child: TextButton(
                            onPressed: widget.onTrends,
                            child: Text(
                                api.tr('查看完整涨跌榜与品类行情 →', 'ランキング・カテゴリ相場 →')))),
                  ] else ...[
                    if (selected.isEmpty)
                      Padding(
                          padding: const EdgeInsets.all(18),
                          child: Text(api.tr('暂无在售商品', '出品中の商品はありません'))),
                    for (final item in selected)
                      Card(
                          child: ListTile(
                              title: Text(api.title(item),
                                  maxLines: 1, overflow: TextOverflow.ellipsis),
                              trailing: Text(yen(
                                  item['effective_price'] ?? item['price'])),
                              onTap: () => widget.onListing(item))),
                  ],
                  const SizedBox(height: 18),
                  section(api.tr('本地配送 · 坂户市', '地域配送・坂戸市')),
                  const SizedBox(height: 10),
                  Text(
                      api.tr(
                          '首期开放坂户市。小件配送 ¥150 起，按距离、重量与尺寸确认；大型家具、冰箱与洗衣机单独报价，不承诺所有商品均可配送。配送为模拟流程。',
                          '坂戸市から開始。小型配送¥150〜、距離・重量・サイズで確認。大型家具・家電は個別見積り。配送は模擬です。'),
                      style: const TextStyle(
                          fontSize: 12, height: 1.8, color: YunoColors.muted)),
                  const SizedBox(height: 10),
                  for (final band in [
                    ('S', api.tr('小件（可手提）', '小型')),
                    ('M', api.tr('中件（单人可搬）', '中型')),
                    ('L', api.tr('大件（家具 / 家电）', '大型'))
                  ])
                    Container(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        decoration: const BoxDecoration(
                            border: Border(
                                bottom: BorderSide(color: YunoColors.line))),
                        child: Row(children: [
                          Expanded(
                              child: Text(band.$2,
                                  style: const TextStyle(fontSize: 12))),
                          Text(
                              api.config['delivery_rules']?['base']?[band.$1] ==
                                      null
                                  ? api.tr('按尺寸确认', 'サイズで確認')
                                  : yen(api.config['delivery_rules']['base']
                                          [band.$1]) +
                                      api.tr(' 起', '〜'),
                              style: const TextStyle(
                                  fontSize: 13, fontWeight: FontWeight.w600))
                        ])),
                  Padding(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      child: Row(children: [
                        Expanded(
                            child: Text(api.tr('特大件（需专车）', '特大型・専用車'),
                                style: const TextStyle(fontSize: 12))),
                        Text(api.tr('单独报价', '個別見積り'),
                            style: const TextStyle(fontSize: 12))
                      ])),
                  const SizedBox(height: 22),
                  section(api.tr('平台自营特价', 'プラットフォーム販売')),
                  const SizedBox(height: 6),
                  Text(
                      api.tr('平台买断入库 · 检测清洁后上架 · 与第三方卖家商品明确区分',
                          '買取在庫・検品後に出品・一般出品と区別'),
                      style: const TextStyle(
                          fontSize: 11, color: YunoColors.muted)),
                  const SizedBox(height: 12),
                  if (owned.isEmpty)
                    Text(api.tr('暂无平台自营商品', 'プラットフォーム商品はありません'),
                        style: const TextStyle(
                            fontSize: 12, color: YunoColors.muted)),
                  for (final item in owned) productCard(item),
                  const SizedBox(height: 22),
                  section(api.tr('拍卖专场', 'オークション')),
                  const SizedBox(height: 6),
                  Text(
                      api.tr(
                          '代理出价 · 防压线延时 · 保留价 · 竞价记录', '自動入札・延長・最低落札価格・入札履歴'),
                      style: const TextStyle(
                          fontSize: 11, color: YunoColors.muted)),
                  const SizedBox(height: 10),
                  if (auctions.isEmpty)
                    Text(api.tr('暂无拍卖商品', 'オークションはありません'),
                        style: const TextStyle(
                            fontSize: 12, color: YunoColors.muted)),
                  for (final item in auctions)
                    Card(
                        child: ListTile(
                            title: Text(api.title(item)),
                            subtitle: Text(api.tr('起拍价 ', '開始価格 ') +
                                yen(item['start_price'])),
                            onTap: () => widget.onAuction(item))),
                  const SizedBox(height: 22),
                  Row(children: [
                    Expanded(child: section(api.tr('在售闲置', '出品中の商品'))),
                    TextButton(
                        onPressed: widget.onPublish,
                        child: Text(api.tr('+ 发布我的闲置', '+ 出品する')))
                  ]),
                  SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Row(children: [
                        for (final c in <Json>[
                          {'slug': '', 'name_zh': '全部', 'name_ja': 'すべて'},
                          ...List<Json>.from(api.config['categories'] ?? [])
                        ])
                          TextButton(
                              onPressed: () =>
                                  setState(() => catalogCategory = c['slug']),
                              style: TextButton.styleFrom(
                                  backgroundColor: catalogCategory == c['slug']
                                      ? YunoColors.primary
                                      : Colors.transparent,
                                  foregroundColor: catalogCategory == c['slug']
                                      ? Colors.white
                                      : YunoColors.muted),
                              child: Text(api.name(c),
                                  style: const TextStyle(fontSize: 11))),
                      ])),
                  Row(children: [
                    Expanded(
                        child: CheckboxListTile(
                            contentPadding: EdgeInsets.zero,
                            dense: true,
                            controlAffinity: ListTileControlAffinity.leading,
                            value: favoritesOnly,
                            onChanged: (v) =>
                                setState(() => favoritesOnly = v ?? false),
                            title: Text(api.tr('我的收藏', 'お気に入り'),
                                style: const TextStyle(fontSize: 11)))),
                    DropdownButton<String>(
                        value: sort,
                        style: const TextStyle(
                            fontSize: 11, color: YunoColors.ink),
                        items: [
                          DropdownMenuItem(
                              value: 'newest',
                              child: Text(api.tr('最新发布', '新着順'))),
                          DropdownMenuItem(
                              value: 'low',
                              child: Text(api.tr('价格从低到高', '価格が安い順'))),
                          DropdownMenuItem(
                              value: 'high',
                              child: Text(api.tr('价格从高到低', '価格が高い順'))),
                        ],
                        onChanged: (v) => setState(() => sort = v ?? 'newest')),
                  ]),
                  TextField(
                      controller: search,
                      onChanged: (_) => setState(() {}),
                      decoration: InputDecoration(
                          hintText: api.tr('搜索商品名称…', '商品名で検索…'),
                          prefixIcon: const Icon(Icons.search, size: 19))),
                  Align(
                      alignment: Alignment.centerRight,
                      child: TextButton(
                          onPressed: widget.onBrowse,
                          child: Text(api.tr('更多筛选 →', '詳しい絞り込み →'),
                              style: const TextStyle(fontSize: 11)))),
                  if (catalog.isEmpty)
                    Padding(
                        padding: const EdgeInsets.symmetric(vertical: 18),
                        child: Text(
                            api.tr(favoritesOnly ? '暂无收藏商品' : '暂无符合条件的商品',
                                favoritesOnly ? 'お気に入りはありません' : '該当する商品はありません'),
                            style: const TextStyle(
                                fontSize: 12, color: YunoColors.muted))),
                  LayoutBuilder(
                      builder: (context, c) =>
                          Wrap(spacing: 10, runSpacing: 10, children: [
                            for (final item in catalog)
                              SizedBox(
                                  width: (c.maxWidth - 10) / 2,
                                  child: productCard(item))
                          ])),
                  const SizedBox(height: 18),
                  Text(
                      api.tr('Yuno Life · 中古交易平台 · 埼玉县坂户市 · 模拟支付',
                          'Yuno Life・リユース・埼玉県坂戸市・模擬決済'),
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                          fontSize: 10, color: YunoColors.muted)),
                ]));
      });
}

class VolumeLine extends CustomPainter {
  final List<Json> weeks;
  VolumeLine(this.weeks);
  @override
  void paint(Canvas canvas, Size size) {
    if (weeks.isEmpty) return;
    final values =
        weeks.map((w) => (w['volume'] as num? ?? 0).toDouble()).toList();
    final max = values.fold<double>(1, (a, b) => a > b ? a : b);
    final path = Path();
    for (var i = 0; i < values.length; i++) {
      final x = values.length == 1 ? 0.0 : i * size.width / (values.length - 1);
      final y = size.height - 5 - values[i] / max * (size.height - 10);
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(
        path,
        Paint()
          ..color = const Color(0xff347957)
          ..strokeWidth = 2
          ..style = PaintingStyle.stroke);
  }

  @override
  bool shouldRepaint(covariant VolumeLine oldDelegate) =>
      oldDelegate.weeks != weeks;
}

Widget marketRankBoard(
        {required Session api,
        required List<Json> items,
        required bool up,
        required ValueChanged<Json> onListing}) =>
    Card(
      clipBehavior: Clip.antiAlias,
      child: Column(children: [
        Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
            child: Row(children: [
              Text(up ? api.tr('涨幅榜', '上昇ランキング') : api.tr('跌幅榜', '下落ランキング'),
                  style: const TextStyle(
                      fontSize: 14, fontWeight: FontWeight.w700)),
              const SizedBox(width: 8),
              Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                  decoration: BoxDecoration(
                      color: up
                          ? const Color(0xffe2f1e8)
                          : const Color(0xfff9e4e2),
                      borderRadius: BorderRadius.circular(3)),
                  child: Text(
                      api.tr('${up ? '上涨' : '下跌'} ${items.length} 件',
                          '${up ? '上昇' : '下落'} ${items.length} 点'),
                      style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: up
                              ? const Color(0xff267955)
                              : const Color(0xffb52f33)))),
              const Spacer(),
              Text(api.tr('${up ? '涨幅' : '跌幅'}从大到小', '変動率順'),
                  style:
                      const TextStyle(fontSize: 10, color: YunoColors.muted)),
            ])),
        const Divider(height: 1),
        if (items.isEmpty)
          Padding(
              padding: const EdgeInsets.all(15),
              child: Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                      up
                          ? api.tr('上涨的商品暂时还没有。真实成交样本不足时不生成排名。',
                              '上昇商品はまだありません。十分な実取引データが必要です。')
                          : api.tr('暂无符合条件的下跌商品。真实成交样本不足时不生成排名。',
                              '下落商品はまだありません。十分な実取引データが必要です。'),
                      style: const TextStyle(
                          fontSize: 12,
                          height: 1.7,
                          color: YunoColors.muted)))),
        for (final indexed in items.indexed) ...[
          InkWell(
              onTap: () =>
                  onListing({'id': indexed.$2['listing_id'], ...indexed.$2}),
              child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(children: [
                    SizedBox(
                        width: 20,
                        child: Text('${indexed.$1 + 1}',
                            style: const TextStyle(
                                fontFamily: 'Georgia', fontSize: 16))),
                    Expanded(
                        child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                          Text(api.title(indexed.$2),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                  fontSize: 13, fontWeight: FontWeight.w600)),
                          const SizedBox(height: 4),
                          Text(
                              api.tr('较首次成交价 ', '初回取引比 ') +
                                  yen(indexed.$2['first']),
                              style: const TextStyle(
                                  fontSize: 10, color: YunoColors.muted)),
                        ])),
                    const SizedBox(width: 8),
                    Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text(yen(indexed.$2['latest']),
                              style: const TextStyle(
                                  fontSize: 14, fontWeight: FontWeight.w700)),
                          Text(
                              api.tr('成交 ${indexed.$2['orders']} 笔',
                                  '取引 ${indexed.$2['orders']} 件'),
                              style: const TextStyle(
                                  fontSize: 10, color: YunoColors.muted)),
                        ]),
                    const SizedBox(width: 8),
                    Text('${up ? '▲ +' : '▼ '}${indexed.$2['pct']}%',
                        style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                            color: up
                                ? const Color(0xff267955)
                                : const Color(0xffb52f33))),
                  ]))),
          if (indexed.$1 < items.length - 1) const Divider(height: 1),
        ],
      ]),
    );
