# 实体 Android 验收

`mobile/integration_test/device_full_test.dart` 在实体手机运行同一套原生页面、表单、网络请求和业务代码。它使用独立包名 `com.yunolife.shop.qa`，不覆盖普通试用包；后端必须使用新的本地隔离库。不要连接正式云库运行交易用例。

## 隔离服务

在仓库根目录用已安装项目依赖（含 `requirements-cloud.txt`）的 Python 运行：

```powershell
$qaDir = '../device-acceptance-unique'
New-Item -ItemType Directory -Path $qaDir
New-Item -ItemType File -Path "$qaDir/.yuno-device-qa"
python -m scripts.device_qa_server --data-dir $qaDir
```

脚本只绑定回环地址，实体机验收默认使用 `127.0.0.1:18765`，模拟测试专用端口为 `18766–18769`。它拒绝已有数据库、没有标记的目录、范围外端口以及带 Turso 云凭据的进程。它使用 libSQL 驱动和数据库图片存储。实体机验收使用的夹具仅提升随机测试账号的运营权限、让指定测试拍卖到期。模拟测试另可注入行情样本。该脚本仅供隔离验收使用，Docker 构建上下文排除了 `scripts/`。

## 手机运行

```powershell
adb -s DEVICE_ID reverse tcp:18765 tcp:18765
cd mobile
$env:YUNO_QA = 'true'
flutter build apk --profile --target=integration_test/device_full_test.dart --target-platform android-arm64 --dart-define=YUNO_SERVER=http://127.0.0.1:18765
# 先核验 APK 的包名确为 com.yunolife.shop.qa，再启动驱动。
$env:YUNO_DEVICE_REPORT = 'C:/absolute/path/device-report.json'
flutter drive --profile --use-application-binary=build/app/outputs/flutter-apk/app-profile.apk --driver=test_driver/device_full_driver.dart --target=integration_test/device_full_test.dart -d DEVICE_ID
```

出现手机安装确认时按系统正常流程完成，不绕过身份验证。不切换手机网络。

用例前半段用程序生成的 PNG 和选图夹具验证十图编辑、限制、AI 草稿、发布与交易。业务动作提交真实原生表单；多数表单由测试直接导航进入，因此不代表每个功能入口都逐一手点覆盖。为避开 Vivo 输入法延迟，批量表单通过原生字段控制器填值。

末尾恢复真实选图插件，按驱动提示操作手机：

- `CAMERA_READY`：在系统相机实际拍摄并确认。
- `ALBUM_READY`：选择专用测试图片，不选择个人图片。
- `KEYBOARD_READY`：通过真实输入法输入 `YunoDeviceQA`。

硬件阶段的照片只预览，不提交、不上传。报告只记录通过的用例组，不保存随机口令或会话令牌。

结束后停止本次隔离服务，仅移除自己添加的 ADB 映射：

```powershell
adb -s DEVICE_ID reverse --remove tcp:18765
```

普通安装包的公网读取另见 [换网验收记录](qa/ANDROID_DEVICE.md)。当前 iOS 验证使用 [系统模拟器](qa/SIMULATION_120.md)，签名及 iPhone 真机属于独立验收。
