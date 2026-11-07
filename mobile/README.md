# YUNO LIFE SHOP 手机客户端

Flutter 3.47.9，单代码库提供 Android 和 iOS 原生界面。应用通过
`/api/v1` JSON 接口连接 FastAPI，不使用 WebView。

## 已部署公网试用

后端地址：`https://yuno-life-shop-free.onrender.com`。
0.2.2 (4) Android 内测包已预设此地址，不依赖电脑服务或同一个 Wi-Fi；
手机需要能访问该地址的互联网连接。已有安装可在个人中心修改服务器地址。
非试用型免费部署、每日备份和恢复实测见 [部署与恢复记录](../docs/FREE_HOSTING_RECOVERY.md)。空闲后首次读取可等待约一分钟，客户端读取等待上限 90 秒；写请求不自动重试。旧 Railway 试用入口已停用。

公网版构建：

```sh
flutter build apk --release --target-platform android-arm64 --dart-define=YUNO_SERVER=https://yuno-life-shop-free.onrender.com
```

## 本地运行

先在仓库根目录启动后端。局域网试用时设置 `YUNO_HOST=0.0.0.0`，
手机和电脑连接同一 Wi-Fi。然后在此目录运行：

```sh
flutter pub get
flutter run --dart-define=YUNO_SERVER=http://电脑局域网IP:8000
```

未传入服务器地址时，应用首次启动显示连接设置。个人中心可修改地址。
设置和手动语言选择会持久化。登录 token 按服务器隔离保存在
Android Keystore / iOS Keychain 支持的安全存储中。

本地 HTTP 连接用于局域网试用，服务必须保持运行。公开服务应配置 HTTPS。
生产支付和物流仍为模拟，应用内持续标注。

## Android 内部试用包

```sh
flutter build apk --release --target-platform android-arm64 --dart-define=YUNO_SERVER=http://电脑局域网IP:8000
```

当前工程使用调试签名生成内部试用包。版本为 `0.2.2+4`，
包名为 `com.yunolife.shop`。商店签名、上架和真实支付不在本次范围。

Android 依赖固定了兼容版本，以复用现有 NDK 27 工具链。
Flutter 对插件建议使用 NDK 28 的提示与构建结果分别记录在验收说明中。

## iOS

在 macOS 上安装 Xcode、CocoaPods 和 Flutter 后：

```sh
flutter build ios --simulator --debug --dart-define=YUNO_SERVER=http://127.0.0.1:8000
```

真机调试需要在 Xcode 中选择自己的开发团队并完成签名。
相机、相册、本地网络用途说明已配置。模拟器的相机可用性由宿主环境决定。

## 验证

最新验收见 [120 轮模拟测试记录](../docs/qa/SIMULATION_120.md) 和 [iQOO 8 真机与换网记录](../docs/qa/ANDROID_DEVICE.md)。独立 Android 验收包的完整操作见 [实体 Android 验收](../docs/DEVICE_QA.md)。

```sh
flutter analyze
flutter test test
flutter drive --driver=test_driver/integration_test.dart --target=integration_test/app_test.dart -d 设备ID --dart-define=YUNO_SERVER=http://验收服务器IP:8765
```

端到端测试需要专用的空白验收数据库与上传目录。测试随机生成账号口令，
覆盖安全存储、登录注册、多图草稿、AI 任务、发布、消息、直购、模拟支付幂等、
配送申请、评价、三项服务、拍卖、买断申请、议价及语言切换。
图片文件在测试中生成，相机硬件流程需另行真机验证。

Android 自动化测试时通过环境变量
`YUNO_QA=true` 使用独立包名 `com.yunolife.shop.qa`。
这让测试登录信息与普通试用包分开存放。Flutter 驱动结束会卸载测试应用。
在已装试用包的实体手机上，务必先构建验收 APK，再从该二进制启动，
避免 Flutter 复用旧 APK 元数据时按旧包名清理：

```sh
YUNO_QA=true flutter build apk --profile --target=integration_test/app_test.dart --target-platform android-arm64 --dart-define=YUNO_SERVER=http://验收服务器IP:8765
flutter drive --profile --use-application-binary=build/app/outputs/flutter-apk/app-profile.apk --driver=test_driver/integration_test.dart --target=integration_test/app_test.dart -d 设备ID
```

上面的环境变量语法适用于 sh；PowerShell 使用 `$env:YUNO_QA="true"`。
测试只能连接隔离数据库，不能连接正式用户数据。

磁盘紧张时可在真机上使用 profile 驱动方式：

```sh
flutter drive --profile --driver=test_driver/integration_test.dart --target=integration_test/app_test.dart -d 设备ID --dart-define=YUNO_SERVER=http://验收服务器IP:8765
```

仓库的 Native mobile validation 工作流在 macOS 运行后端测试、
Flutter 检查、iPhone 模拟器端到端测试，并保存模拟器安装包与截图。
