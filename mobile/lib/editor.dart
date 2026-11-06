import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import 'api.dart';
import 'labels.dart';
import 'main.dart';
import 'ui.dart';

class ActionForm extends StatefulWidget {
  final String action;
  final Json values;
  final Json initialValues;
  const ActionForm({
    super.key,
    required this.action,
    this.values = const {},
    this.initialValues = const {},
  });
  @override
  State<ActionForm> createState() => _ActionFormState();
}

class _ActionFormState extends State<ActionForm> {
  final formKey = GlobalKey<FormState>();
  final controllers = <String, TextEditingController>{};
  final picker = ImagePicker();
  final photos = <XFile>[];
  Json? schema;
  Object? error;
  bool busy = false;
  String stage = '';
  bool get cameraFirst => widget.action == 'oneclick_upload';
  List<dynamic> get fields => schema?['fields'] ?? [];
  List<dynamic> get uploadFields =>
      fields.where((f) => f['type'] == 'photos').toList();
  int get photoLimit => uploadFields.any((f) => f['multiple'] == true) ? 10 : 1;
  String get photoField {
    final multiple = uploadFields.where((f) => f['multiple'] == true);
    return (multiple.isNotEmpty ? multiple.first : uploadFields.first)['name'];
  }

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      await appState.ensureConfig();
      final action = (appState.config['actions'] as List)
          .cast<Json>()
          .firstWhere((a) => a['name'] == widget.action);
      Json currentSettings = {};
      if (widget.action == 'admin_settings_post') {
        currentSettings = (await appState.get('admin/settings'))['item'];
      }
      for (final field in action['fields']) {
        final name = field['name'] as String;
        final value =
            widget.values[name] ??
            currentSettings[name] ??
            widget.initialValues[name] ??
            field['default'];
        controllers[name] = TextEditingController(
          text: value?.toString() ?? '',
        );
      }
      if (!mounted) return;
      setState(() => schema = action);
      if (cameraFirst) {
        final lost = await picker.retrieveLostData();
        if (lost.files != null && mounted) {
          setState(() => photos.addAll(lost.files!.take(10)));
        } else if (mounted) {
          await pick(ImageSource.camera);
        }
      }
    } catch (e) {
      if (mounted) setState(() => error = e);
    }
  }

  Future<void> pick(ImageSource source, {int? replace}) async {
    try {
      if (replace == null && photos.length >= photoLimit) {
        throw ApiFailure('max_photos', 400);
      }
      final List<XFile> selected;
      if (source == ImageSource.camera ||
          replace != null ||
          uploadFields.every((f) => f['multiple'] != true)) {
        final file = await picker.pickImage(
          source: source,
          preferredCameraDevice: CameraDevice.rear,
          imageQuality: 88,
          maxWidth: 2200,
        );
        selected = file == null ? [] : [file];
      } else {
        selected = await picker.pickMultiImage(
          imageQuality: 88,
          maxWidth: 2200,
        );
      }
      if (!mounted) return;
      if (selected.length + photos.length > photoLimit && replace == null) {
        throw ApiFailure('max_photos', 400);
      }
      for (final file in selected) {
        if (await file.length() > 5 * 1024 * 1024) {
          throw ApiFailure('photo_too_large', 400);
        }
      }
      if (!mounted) return;
      setState(() {
        if (replace != null && selected.isNotEmpty) {
          photos[replace] = selected.first;
        } else {
          photos.addAll(selected);
        }
      });
    } catch (e) {
      if (mounted) setState(() => error = e);
    }
  }

  Map<String, String>? options(String name) {
    if (name == 'category_slug') {
      return {
        for (final cat in appState.config['categories'])
          cat['slug']: cat['name_${appState.language}'],
      };
    }
    if (name == 'region') {
      return {
        for (final region in appState.config['regions'])
          region['code']:
              region['name_${appState.language}'] ?? region['name_ja'],
      };
    }
    if (['condition', 'condition_grade'].contains(name)) {
      return {
        for (final v in ['excellent', 'good', 'fair', 'poor']) v: label(v),
      };
    }
    if (name == 'size_class') {
      return {
        for (final v in ['S', 'M', 'L', 'XL']) v: v,
      };
    }
    if (name == 'role') {
      return {
        for (final v in [
          'user',
          'collector',
          'operator',
          'appraiser',
          'courier',
          'admin',
        ])
          v: label(v),
      };
    }
    if (['identity_verified', 'deposit_required'].contains(name)) {
      return {'': tx('否', 'いいえ'), '1': tx('是', 'はい')};
    }
    if (name == 'rating') {
      return {
        for (final v in ['5', '4', '3', '2', '1']) v: '$v ★',
      };
    }
    if (name == 'appraisal_status') {
      return {'approved': label('approved'), 'rejected': label('rejected')};
    }
    if (name == 'decision' && widget.action == 'refund_decide') {
      return {'approved': label('approved'), 'rejected': label('rejected')};
    }
    if (name == 'kind' && widget.action == 'service_create') {
      return {
        for (final key in (appState.config['services'] as Map).keys)
          key: label(key),
      };
    }
    if (name == 'kind' && widget.action == 'delivery_request') {
      return {
        for (final v in ['buyer_delivery', 'seller_pickup']) v: label(v),
      };
    }
    return null;
  }

  Future<void> submit() async {
    if (!formKey.currentState!.validate()) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final values = <String, dynamic>{
        ...widget.values,
        for (final entry in controllers.entries)
          if (!uploadFields.any((f) => f['name'] == entry.key))
            entry.key: entry.value.text,
      };
      if (widget.action == 'order_pay' &&
          !values.containsKey('idempotency_key')) {
        values['idempotency_key'] =
            'native-order-${values['oid']}-${appState.user?['id']}';
      }
      var result = await appState.action(
        widget.action,
        values,
        photos: photos,
        photoField: uploadFields.isEmpty ? 'photos' : photoField,
      );
      if (cameraFirst) {
        final draftId = result['id'];
        final job = await appState.action('ai_job_create', {
          'kind': 'oneclick_recognize',
          'draft_id': '$draftId',
        });
        await appState.poll(job['job_id'], (value) {
          if (mounted) setState(() => stage = label(value));
        });
      } else if (widget.action == 'ai_job_create') {
        await appState.poll(result['job_id'], (value) {
          if (mounted) setState(() => stage = label(value));
        });
      } else if ([
        'oneclick_photo_add',
        'oneclick_photo_delete',
        'draft_photo_replace',
      ].contains(widget.action)) {
        await appState.action('oneclick_recognize', {'did': values['did']});
      }
      if (mounted) Navigator.of(context).pop(result);
    } catch (e) {
      if (mounted) {
        setState(() {
          error = e;
          busy = false;
        });
      }
    }
  }

  @override
  void dispose() {
    for (final c in controllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PageFrame(
    child: schema == null
        ? (error == null
              ? const Center(child: CircularProgressIndicator())
              : ErrorPanel(error: error!, retry: load))
        : Form(
            key: formKey,
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                heading(label(widget.action)),
                if (cameraFirst)
                  Text(
                    tx(
                      '拍照后立即预览，识别与鉴定均为推测。确认型号后可查询现实市场参考价。',
                      '撮影後すぐに確認できます。認識・鑑定は推測です。型番確認後、市場の参考価格を検索できます。',
                    ),
                  ),
                if (uploadFields.isNotEmpty) ...[
                  Wrap(
                    spacing: 8,
                    children: [
                      FilledButton.icon(
                        onPressed: busy ? null : () => pick(ImageSource.camera),
                        icon: const Icon(Icons.camera_alt_outlined),
                        label: Text(tx('拍照', '撮影')),
                      ),
                      OutlinedButton.icon(
                        onPressed: busy
                            ? null
                            : () => pick(ImageSource.gallery),
                        icon: const Icon(Icons.photo_library_outlined),
                        label: Text(tx('相册', 'アルバム')),
                      ),
                      Text('${photos.length}/$photoLimit'),
                    ],
                  ),
                  for (var i = 0; i < photos.length; i++)
                    panel(
                      Column(
                        children: [
                          GestureDetector(
                            onTap: () => openPage(
                              context,
                              PageFrame(
                                child: InteractiveViewer(
                                  child: Image.file(
                                    File(photos[i].path),
                                    fit: BoxFit.contain,
                                  ),
                                ),
                              ),
                            ),
                            child: Image.file(
                              File(photos[i].path),
                              height: 160,
                              fit: BoxFit.contain,
                            ),
                          ),
                          Wrap(
                            spacing: 4,
                            children: [
                              TextButton(
                                onPressed: busy
                                    ? null
                                    : () => setState(() {
                                        final photo = photos.removeAt(i);
                                        photos.insert(0, photo);
                                      }),
                                child: Text(
                                  i == 0
                                      ? tx('封面 ✓', '表紙 ✓')
                                      : tx('设为封面', '表紙に設定'),
                                ),
                              ),
                              TextButton(
                                onPressed: busy
                                    ? null
                                    : () =>
                                          pick(ImageSource.camera, replace: i),
                                child: Text(tx('重拍', '再撮影')),
                              ),
                              TextButton(
                                onPressed: busy
                                    ? null
                                    : () =>
                                          pick(ImageSource.gallery, replace: i),
                                child: Text(tx('替换', '差し替え')),
                              ),
                              TextButton(
                                onPressed: busy
                                    ? null
                                    : () => setState(() => photos.removeAt(i)),
                                child: Text(tx('删除', '削除')),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                ],
                for (final field in fields)
                  if (field['type'] != 'photos' &&
                      !widget.values.containsKey(field['name']))
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      child: input(field),
                    ),
                ...attributeInputs(),
                simulationNote(),
                if (error != null)
                  Padding(
                    padding: const EdgeInsets.all(12),
                    child: Text(
                      errorText(error!),
                      style: const TextStyle(color: Colors.red),
                    ),
                  ),
                if (busy) ...[const LinearProgressIndicator(), Text(stage)],
                const SizedBox(height: 12),
                FilledButton(
                  onPressed: busy || (cameraFirst && photos.isEmpty)
                      ? null
                      : submit,
                  child: Padding(
                    padding: const EdgeInsets.all(10),
                    child: Text(
                      cameraFirst
                          ? tx('AI 一键识别与估价', 'AI 認識・査定')
                          : label(widget.action),
                    ),
                  ),
                ),
              ],
            ),
          ),
  );

  Widget input(Json field) {
    final name = field['name'] as String;
    final controller = controllers[name]!;
    final choices = options(name);
    if (choices != null) {
      if (!choices.containsKey(controller.text)) {
        controller.text = choices.keys.first;
      }
      return DropdownButtonFormField<String>(
        key: ValueKey('${appState.language}:$name'),
        initialValue: controller.text,
        isExpanded: true,
        decoration: InputDecoration(labelText: label(name)),
        items: [
          for (final e in choices.entries)
            DropdownMenuItem(
              value: e.key,
              child: Text(e.value, overflow: TextOverflow.ellipsis),
            ),
        ],
        onChanged: busy
            ? null
            : (value) {
                controller.text = value!;
                if (name == 'category_slug') setState(() {});
              },
      );
    }
    final numeric = ['integer', 'number'].contains(field['type']);
    return TextFormField(
      controller: controller,
      enabled: !busy,
      readOnly: ['ends_at', 'pickup_at', 'scheduled_at'].contains(name),
      onTap: ['ends_at', 'pickup_at', 'scheduled_at'].contains(name)
          ? () => chooseTokyoTime(controller)
          : null,
      obscureText: name == 'password',
      maxLines: name.contains('desc') || name == 'text' ? 3 : 1,
      keyboardType: numeric
          ? const TextInputType.numberWithOptions(decimal: true)
          : name == 'email'
          ? TextInputType.emailAddress
          : TextInputType.text,
      decoration: InputDecoration(
        labelText: label(name),
        helperText: ['ends_at', 'pickup_at', 'scheduled_at'].contains(name)
            ? tx('日本时间', '日本時間')
            : name == 'password' && widget.action == 'register'
            ? tx('至少 8 个字符', '8文字以上')
            : null,
      ),
      validator: (text) {
        if (field['required'] == true &&
            (text == null || text.trim().isEmpty)) {
          return tx('请填写此项', '入力してください');
        }
        if (numeric &&
            text != null &&
            text.isNotEmpty &&
            num.tryParse(text) == null) {
          return tx('请输入数字', '数値を入力してください');
        }
        return null;
      },
    );
  }

  Future<void> chooseTokyoTime(TextEditingController controller) async {
    final now = DateTime.now().toUtc().add(const Duration(hours: 9));
    final date = await showDatePicker(
      context: context,
      initialDate: now,
      firstDate: now,
      lastDate: now.add(const Duration(days: 3650)),
    );
    if (date == null || !mounted) return;
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay(hour: now.hour, minute: now.minute),
    );
    if (time == null || !mounted) return;
    controller.text = DateTime.utc(
      date.year,
      date.month,
      date.day,
      time.hour,
      time.minute,
    ).toIso8601String().replaceFirst('Z', '+09:00');
  }

  List<Widget> attributeInputs() {
    if (!controllers.containsKey('category_slug')) return [];
    final slug = controllers['category_slug']!.text;
    final categories = appState.config['categories'] as List;
    final category = categories.where((c) => c['slug'] == slug).firstOrNull;
    if (category == null) return [];
    return [
      for (final attr in category['attrs'] ?? [])
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: TextFormField(
            controller: controllers.putIfAbsent(
              'attr_${attr['key']}',
              () => TextEditingController(
                text:
                    widget.initialValues['attrs']?[attr['key']]?.toString() ??
                    '',
              ),
            ),
            enabled: !busy,
            decoration: InputDecoration(
              labelText:
                  attr['label_${appState.language}'] ?? label(attr['key']),
            ),
          ),
        ),
    ];
  }
}
