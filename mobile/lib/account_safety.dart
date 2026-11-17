import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'main.dart'
    show
        session,
        PageFrame,
        DetailPage,
        LoadView,
        open,
        ensureLogin,
        notify,
        failure,
        empty;

Future<void> reportContent(BuildContext context, String type, int id) async {
  if (!await ensureLogin(context) || !context.mounted) return;
  await open(context, ReportPage(type: type, id: id));
}

Future<void> blockPerson(BuildContext context, int uid) async {
  if (!await ensureLogin(context) || !context.mounted) return;
  final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
            title: Text(session.tr('屏蔽此用户？', 'このユーザーをブロックしますか？')),
            content: Text(session.tr(
                '屏蔽后隐藏对方商品，并阻止双方继续发消息或发起新交易。已有订单和争议记录仍保留。可在账号安全中解除。',
                '相手の商品を非表示にし、双方のメッセージと新規取引を停止します。既存の注文・紛争記録は保持されます。アカウント設定で解除できます。')),
            actions: [
              TextButton(
                  onPressed: () => Navigator.pop(context, false),
                  child: Text(session.tr('取消', '取消'))),
              FilledButton(
                  onPressed: () => Navigator.pop(context, true),
                  child: Text(session.tr('屏蔽', 'ブロック')))
            ],
          ));
  if (confirmed != true) return;
  try {
    await session.post('/account/blocked/$uid', {'blocked': true});
    if (context.mounted) {
      notify(context, session.tr('已屏蔽，可从账号安全管理。', 'ブロックしました。アカウント設定で管理できます。'));
      Navigator.maybePop(context);
    }
  } catch (e) {
    if (context.mounted) notify(context, failure(e));
  }
}

class ReportPage extends StatefulWidget {
  final String type;
  final int id;
  const ReportPage({super.key, required this.type, required this.id});
  @override
  State<ReportPage> createState() => _ReportPageState();
}

class _ReportPageState extends State<ReportPage> {
  final details = TextEditingController();
  String reason = 'other';
  bool busy = false;
  String? error;
  @override
  void dispose() {
    details.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PageFrame(
      title: session.tr('举报内容', 'コンテンツを報告'),
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text(session.tr('举报会进入人工处理队列；提交不代表举报已被认定成立。紧急危险请联系当地紧急服务。',
              '報告は運営の確認待ちになります。送信のみで違反認定されるものではありません。緊急時は地域の緊急窓口へ連絡してください。')),
          const SizedBox(height: 16),
          DropdownButtonFormField<String>(
              initialValue: reason,
              isExpanded: true,
              decoration:
                  InputDecoration(labelText: session.tr('举报原因', '報告理由')),
              items: [
                for (final pair in [
                  ['illegal', session.tr('违法或禁售物品', '違法・出品禁止物')],
                  ['counterfeit', session.tr('疑似假冒', '偽造品の疑い')],
                  ['harassment', session.tr('骚扰或不当内容', '嫌がらせ・不適切な内容')],
                  ['privacy', session.tr('泄露个人信息', '個人情報の公開')],
                  ['other', session.tr('其他', 'その他')],
                ])
                  DropdownMenuItem(value: pair[0], child: Text(pair[1]))
              ],
              onChanged: busy ? null : (v) => reason = v ?? 'other'),
          const SizedBox(height: 16),
          TextField(
              controller: details,
              maxLines: 4,
              maxLength: 1000,
              decoration: InputDecoration(
                  labelText:
                      session.tr('情况说明（不要填写密码）', '詳細（パスワードは入力しないでください）'))),
          if (error != null)
            Text(error!, style: const TextStyle(color: Colors.red)),
          FilledButton(
              onPressed: busy
                  ? null
                  : () async {
                      setState(() {
                        busy = true;
                        error = null;
                      });
                      try {
                        await session.post('/reports', {
                          'target_type': widget.type,
                          'target_id': widget.id,
                          'reason': reason,
                          'details': details.text.trim()
                        });
                        if (context.mounted) {
                          notify(
                              context,
                              session.tr(
                                  '举报已提交，等待人工处理。', '報告を送信しました。運営の確認をお待ちください。'));
                          Navigator.pop(context);
                        }
                      } catch (e) {
                        if (mounted) setState(() => error = failure(e));
                      } finally {
                        if (mounted) setState(() => busy = false);
                      }
                    },
              child: Text(session.tr('提交举报', '報告を送信'))),
        ],
      ));
}

class AccountSafetyPage extends StatefulWidget {
  const AccountSafetyPage({super.key});
  @override
  State<AccountSafetyPage> createState() => _AccountSafetyPageState();
}

class _AccountSafetyPageState extends State<AccountSafetyPage> {
  final password = TextEditingController();
  String? code, error;
  bool busy = false;
  @override
  void dispose() {
    password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PageFrame(
      title: session.tr('账号安全与屏蔽', 'アカウント・ブロック'),
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text(session.tr(
              '恢复码用于忘记密码后的重设，不通过邮件发送。每次生成会替换旧码；使用后作废，并退出所有设备。请保存在你自己的安全位置。',
              'リカバリーコードはパスワード再設定に使います。メール送信はしません。再発行で旧コードは無効になり、使用すると全端末がログアウトします。安全な場所に保管してください。')),
          const SizedBox(height: 16),
          TextField(
              controller: password,
              obscureText: true,
              enableSuggestions: false,
              autocorrect: false,
              decoration:
                  InputDecoration(labelText: session.tr('当前密码', '現在のパスワード'))),
          if (error != null)
            Text(error!, style: const TextStyle(color: Colors.red)),
          FilledButton(
              onPressed: busy
                  ? null
                  : () async {
                      setState(() {
                        busy = true;
                        error = null;
                      });
                      try {
                        final data = await session.post(
                            '/account/recovery-code',
                            {'password': password.text});
                        if (mounted) {
                          setState(() {
                            code = '${data['recovery_code']}';
                            password.clear();
                          });
                        }
                      } catch (e) {
                        if (mounted) setState(() => error = failure(e));
                      } finally {
                        if (mounted) setState(() => busy = false);
                      }
                    },
              child: Text(session.tr('生成 / 更换一次性恢复码', 'リカバリーコードを発行・再発行'))),
          if (code != null)
            Card(
                child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(children: [
                      Text(session.tr(
                          '仅本次显示，离开后无法再次查看。', 'この画面でのみ表示します。離れると再表示できません。')),
                      const SizedBox(height: 12),
                      SelectableText(code!,
                          style: const TextStyle(fontSize: 18)),
                      TextButton(
                          onPressed: () async {
                            await Clipboard.setData(ClipboardData(text: code!));
                            if (context.mounted) {
                              notify(
                                  context,
                                  session.tr(
                                      '已复制，请妥善保管。', 'コピーしました。安全に保管してください。'));
                            }
                          },
                          child: Text(session.tr('复制恢复码', 'コードをコピー'))),
                    ]))),
          const Divider(height: 32),
          ListTile(
              title: Text(session.tr('管理已屏蔽用户', 'ブロックしたユーザー')),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => open(context, const BlockedUsersPage())),
          const Divider(),
          ListTile(
              title: Text(session.tr('删除账号', 'アカウント削除'),
                  style: const TextStyle(color: Colors.red)),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => open(context, const DeleteAccountPage())),
        ],
      ));
}

class ResetPasswordPage extends StatefulWidget {
  const ResetPasswordPage({super.key});
  @override
  State<ResetPasswordPage> createState() => _ResetPasswordPageState();
}

class _ResetPasswordPageState extends State<ResetPasswordPage> {
  final email = TextEditingController(),
      code = TextEditingController(),
      password = TextEditingController(),
      confirmation = TextEditingController();
  bool busy = false;
  String? error;
  final form = GlobalKey<FormState>();
  @override
  void dispose() {
    for (final c in [email, code, password, confirmation]) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PageFrame(
      title: session.tr('找回密码', 'パスワード再設定'),
      child: Form(
          key: form,
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              Text(session.tr(
                  '使用你事先保存的一次性恢复码。没有恢复码时无法自动找回；请通过客服渠道申请人工协助，不要提供密码。',
                  '事前に保存したリカバリーコードを使ってください。コードがない場合は自動再設定できません。パスワードを伝えずにサポートへ相談してください。')),
              const SizedBox(height: 16),
              TextFormField(
                  controller: email,
                  keyboardType: TextInputType.emailAddress,
                  autocorrect: false,
                  decoration: InputDecoration(
                      labelText: session.tr('注册邮箱', '登録メールアドレス')),
                  validator: (v) => (v ?? '').contains('@')
                      ? null
                      : session.tr('请输入邮箱', 'メールアドレスを入力してください')),
              const SizedBox(height: 16),
              TextFormField(
                  controller: code,
                  obscureText: true,
                  enableSuggestions: false,
                  autocorrect: false,
                  decoration: InputDecoration(
                      labelText: session.tr('一次性恢复码', 'リカバリーコード')),
                  validator: (v) => (v ?? '').trim().isEmpty
                      ? session.tr('请输入恢复码', 'コードを入力してください')
                      : null),
              const SizedBox(height: 16),
              TextFormField(
                  controller: password,
                  obscureText: true,
                  enableSuggestions: false,
                  autocorrect: false,
                  decoration: InputDecoration(
                      labelText: session.tr('新密码（至少 8 位）', '新しいパスワード（8文字以上）')),
                  validator: (v) => (v ?? '').length < 8
                      ? session.tr('至少 8 位', '8文字以上必要です')
                      : null),
              const SizedBox(height: 16),
              TextFormField(
                  controller: confirmation,
                  obscureText: true,
                  enableSuggestions: false,
                  autocorrect: false,
                  decoration: InputDecoration(
                      labelText: session.tr('再次输入新密码', '新しいパスワード（確認）')),
                  validator: (v) => v == password.text
                      ? null
                      : session.tr('两次密码不一致', 'パスワードが一致しません')),
              if (error != null)
                Text(error!, style: const TextStyle(color: Colors.red)),
              FilledButton(
                  onPressed: busy
                      ? null
                      : () async {
                          if (!form.currentState!.validate()) return;
                          setState(() {
                            busy = true;
                            error = null;
                          });
                          try {
                            await session.post('/account/reset-password', {
                              'email': email.text.trim(),
                              'recovery_code': code.text.trim(),
                              'new_password': password.text
                            });
                            await session.clearIdentity();
                            if (context.mounted) {
                              notify(
                                  context,
                                  session.tr('密码已重设，所有旧会话已退出。请重新登录并生成新恢复码。',
                                      '再設定しました。全端末でログアウトしました。再ログインし、新しいコードを発行してください。'));
                              Navigator.pop(context);
                            }
                          } catch (e) {
                            if (mounted) setState(() => error = failure(e));
                          } finally {
                            if (mounted) setState(() => busy = false);
                          }
                        },
                  child: Text(session.tr('重设密码', 'パスワードを再設定'))),
            ],
          )));
}

class DeleteAccountPage extends StatefulWidget {
  const DeleteAccountPage({super.key});
  @override
  State<DeleteAccountPage> createState() => _DeleteAccountPageState();
}

class _DeleteAccountPageState extends State<DeleteAccountPage> {
  final password = TextEditingController(),
      confirmation = TextEditingController();
  bool busy = false;
  String? error;
  @override
  void dispose() {
    password.dispose();
    confirmation.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PageFrame(
      title: session.tr('删除账号', 'アカウント削除'),
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text(session.tr(
              '删除后立即退出所有设备，匿名化账号资料，移除公开商品照片、草稿及本人发送的消息正文。订单、争议与必要审计记录会保留，备份不会即时全部清除。此操作无法撤销。请先保存你需要的交易记录，并处理未完成事项。',
              '削除すると全端末からログアウトし、プロフィールを匿名化して公開写真・下書き・送信メッセージ本文を削除します。注文・紛争・必要な監査記録は保持され、バックアップの即時全消去は行いません。取り消せません。必要な記録を保存し、未完了の取引を確認してください。')),
          const SizedBox(height: 16),
          TextField(
              controller: password,
              obscureText: true,
              enableSuggestions: false,
              autocorrect: false,
              decoration:
                  InputDecoration(labelText: session.tr('当前密码', '現在のパスワード'))),
          const SizedBox(height: 16),
          TextField(
              controller: confirmation,
              autocorrect: false,
              decoration: InputDecoration(
                  labelText: session.tr('输入 DELETE 确认删除', 'DELETE と入力して確認'))),
          if (error != null)
            Text(error!, style: const TextStyle(color: Colors.red)),
          FilledButton(
              onPressed: busy
                  ? null
                  : () async {
                      if (password.text.isEmpty ||
                          confirmation.text != 'DELETE') {
                        setState(() => error = session.tr(
                            '请输入当前密码与 DELETE。', '現在のパスワードと DELETE を入力してください。'));
                        return;
                      }
                      final yes = await showDialog<bool>(
                          context: context,
                          builder: (context) => AlertDialog(
                                title: Text(
                                    session.tr('永久删除此账号？', 'アカウントを削除しますか？')),
                                content: Text(session.tr('账号资料无法恢复，所有设备会退出登录。',
                                    'プロフィールは復元できません。すべての端末でログアウトします。')),
                                actions: [
                                  TextButton(
                                      onPressed: () =>
                                          Navigator.pop(context, false),
                                      child: Text(session.tr('保留账号', '削除しない'))),
                                  FilledButton(
                                      onPressed: () =>
                                          Navigator.pop(context, true),
                                      child: Text(session.tr('确认删除', '削除を確定')))
                                ],
                              ));
                      if (yes != true || !mounted) return;
                      setState(() {
                        busy = true;
                        error = null;
                      });
                      try {
                        final cleaned =
                            await session.deleteAccount(password.text);
                        if (context.mounted) {
                          Navigator.of(context)
                              .popUntil((route) => route.isFirst);
                          notify(
                              context,
                              cleaned
                                  ? session.tr('账号已删除。', 'アカウントを削除しました。')
                                  : session.tr(
                                      '服务器账号已删除并退出登录；本机草稿清理未完成，请在系统设置中清除 App 数据。',
                                      'サーバーのアカウントは削除・ログアウト済みです。端末の下書き削除が未完了のため、端末設定からアプリのデータを削除してください。'));
                        }
                      } catch (e) {
                        if (mounted) setState(() => error = failure(e));
                      } finally {
                        if (mounted) setState(() => busy = false);
                      }
                    },
              child: Text(session.tr('删除账号', 'アカウント削除'))),
        ],
      ));
}

class BlockedUsersPage extends StatelessWidget {
  const BlockedUsersPage({super.key});
  @override
  Widget build(BuildContext context) => PageFrame(
      title: session.tr('已屏蔽用户', 'ブロックしたユーザー'),
      child: LoadView(
        load: () => session.get('/account/blocked'),
        builder: (context, data, reload) => ListView(children: [
          if ((data['items'] as List).isEmpty)
            Padding(
                padding: const EdgeInsets.all(24),
                child: Text(session.tr('没有已屏蔽用户。', 'ブロックしたユーザーはいません。'))),
          for (final person in data['items'])
            ListTile(
                title: Text('${person['display_name']}'),
                trailing: TextButton(
                    onPressed: () async {
                      try {
                        await session.post('/account/blocked/${person['id']}',
                            {'blocked': false});
                        reload();
                      } catch (e) {
                        if (context.mounted) notify(context, failure(e));
                      }
                    },
                    child: Text(session.tr('解除屏蔽', 'ブロック解除')))),
        ]),
      ));
}

class ModerationPage extends StatelessWidget {
  const ModerationPage({super.key});
  Future<void> resolve(BuildContext context, int id, String decision,
      VoidCallback reload) async {
    var note = '';
    final reason = await showDialog<String>(
        context: context,
        builder: (context) => AlertDialog(
              title: Text(session.tr('填写处理依据', '判断理由')),
              content: TextField(
                  onChanged: (value) => note = value,
                  maxLines: 3,
                  maxLength: 1000),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: Text(session.tr('取消', '取消'))),
                FilledButton(
                    onPressed: () {
                      if (note.trim().isNotEmpty) {
                        Navigator.pop(context, note.trim());
                      }
                    },
                    child: Text(session.tr('确认处理', '判断を確定')))
              ],
            ));
    if (reason == null) return;
    try {
      await session.post(
          '/admin/reports/$id/resolve', {'decision': decision, 'note': reason});
      reload();
    } catch (e) {
      if (context.mounted) notify(context, failure(e));
    }
  }

  @override
  Widget build(BuildContext context) => PageFrame(
      title: session.tr('内容举报处理', 'コンテンツ報告'),
      child: LoadView(
        load: () => session.get('/admin/reports'),
        builder: (context, data, reload) =>
            ListView(padding: const EdgeInsets.all(16), children: [
          Text(session.tr('人工判断成立后，商品停止展示或消息正文被移除；交易与审计记录保留。',
              '報告を認定すると商品を非公開、またはメッセージ本文を削除します。取引・監査記録は保持します。')),
          if ((data['items'] as List).isEmpty) empty(),
          for (final item in data['items'])
            Card(
                child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                              '#${item['id']} · ${item['target_type']} #${item['target_id']}'),
                          Text({
                                'illegal': session.tr('违法或禁售物品', '違法・出品禁止物'),
                                'counterfeit': session.tr('疑似假冒', '偽造品の疑い'),
                                'harassment':
                                    session.tr('骚扰或不当内容', '嫌がらせ・不適切な内容'),
                                'privacy': session.tr('泄露个人信息', '個人情報の公開'),
                                'other': session.tr('其他', 'その他'),
                              }[item['reason']] ??
                              '${item['reason']}'),
                          if (item['target_type'] == 'listing') ...[
                            Text(
                                '${item[session.zh ? 'reported_title_zh' : 'reported_title_ja'] ?? item['reported_title_ja'] ?? ''}'),
                            TextButton(
                                onPressed: () => open(
                                    context,
                                    DetailPage(
                                        path: '/listings/${item['target_id']}',
                                        title: session.tr('被举报商品', '報告対象の商品'))),
                                child:
                                    Text(session.tr('查看被举报商品', '報告対象の商品を見る'))),
                          ],
                          if (item['target_type'] == 'message') ...[
                            Text(session.tr('被举报消息正文', '報告対象のメッセージ')),
                            SelectableText(
                                '${item['reported_body'] ?? session.tr('内容已不存在', 'コンテンツがありません')}'),
                          ],
                          Text('${item['details']}'),
                          Text({
                                'open': session.tr('待处理', '確認待ち'),
                                'upheld': session.tr('举报成立', '報告を認定'),
                                'dismissed': session.tr('举报不成立', '非該当')
                              }[item['status']] ??
                              '${item['status']}'),
                          if (item['status'] == 'open')
                            Wrap(spacing: 8, children: [
                              OutlinedButton(
                                  onPressed: () => resolve(
                                      context, item['id'], 'dismissed', reload),
                                  child: Text(session.tr('不成立', '非該当'))),
                              FilledButton(
                                  onPressed: () => resolve(
                                      context, item['id'], 'upheld', reload),
                                  child:
                                      Text(session.tr('成立并移除内容', '認定して非表示'))),
                            ])
                          else
                            Text('${item['resolution']}'),
                        ]))),
        ]),
      ));
}
