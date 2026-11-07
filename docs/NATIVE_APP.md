# Flutter 原生 App

基线为 `1ab6b8f` 的 `CODEX_APP_BRIEF.md`。`mobile/` 是 iOS / Android 单代码库，
使用 Flutter Material 组件，不含 WebView 或 HTML 页面渲染。

## 接口与兼容性

`app/main.py` 仅增加路由注册。业务模块、HTML 路由与数据库结构保持不变。
`app/api_v1.py` 新增 JSON 读取模型；命令通过进程内 ASGI 调用既有写路由，
共享原有校验、权限、限流、审计和状态机。App 不接收或解析 HTML；
命令响应转换为资源路径，App 再读取权威 JSON 状态。

API 前缀 `/api/v1`：

- 公共：`/config`、`/listings`、`/listings/{id}`、`/auctions`、
  `/auctions/{id}`、`/market`、`/rules`、`/users/{id}`。
- 账号：`POST /register`、`/login`、`/logout`；`GET /me`。
- AI：草稿上传、照片增删换封面、型号确认、识别、确认发布；
  `/ai-jobs` 派发与 `/ai-jobs/{id}` 轮询。
- 业务：商品发布、直购、议价、拍卖、买断、服务、配送、订单、
  退款争议、评价、消息及后台命令，路径与原有 POST 路由对应。
- 管理：`GET /admin/{section}` 及原有管理命令；服务器再次校验角色。

普通命令接受 JSON，照片接受 multipart。详情返回本地化操作标题及表单字段，
客户端用 Flutter 表单展示。失败返回 JSON 错误，不能把重定向当作成交成功。

App 采用不透明 Bearer 会话 token，复用既有会话表。API 不以 Cookie 鉴权。
token 存 Keychain / Keystore，不存 SharedPreferences，不记录口令或 token；
token 与服务器地址绑定，更换服务器会清除旧会话。语言偏好单独持久化。

## 功能

五项底部入口：市场、成交行情、交易、订单、个人中心。
相机优先、即时预览、最多 10 图、首图封面、替换/删除/重拍、全图上传分析。
敏感品类展示成色与真伪两轴，普通品类只显示成色；推测、置信度、人工复核、
真实市场样本及无报价原因分别展示，用户明确确认后才发布。
估价模型与多源搜索沿用原后端，不调用付费 API，不编造报价。

服务目录只读取最终三项：家居清洁 1500 日元/小时、小件搬运 500 日元/趟
（10kg 内）、本地配送 150 日元/趟起。交易界面保留含税、模拟支付与模拟物流说明。
行情为原后端单商品涨跌双榜，保留样本量与无样本状态。
规则、客服、账户与角色受限的管理操作均有原生入口。

## 运行与构建

需要 Python 3.10+（推荐 3.12）、Flutter stable、Xcode / CocoaPods、
Android SDK 36、JDK 17、NDK `28.2.13676358`。首次双平台构建建议预留 8 GB 以上。

仓库根目录启动后端，手机与 Mac 必须在可互访的局域网：

```sh
YUNO_HOST=Mac的局域网IP YUNO_PORT=8002 .venv/bin/python run.py
```

在 `mobile/`：

```sh
flutter pub get
flutter analyze
flutter test
flutter build ios --release --dart-define=API_BASE_URL=http://Mac的局域网IP:8002
flutter build apk --debug --target-platform android-arm64 \
  --dart-define=API_BASE_URL=http://Mac的局域网IP:8002
```

iOS bundle ID 为 `com.yunolife.shop.dev`。真机需有效开发签名和设备信任。
日常试用使用 Release 构建；Debug 仅用于 Flutter/Xcode 调试。
直接安装本地 `.app` 前，可在 `mobile/` 执行：

```sh
python3 tool/prepare_ios_app.py build/ios/iphoneos/Runner.app
```

此工具只规范目录和文件访问权限，并执行签名深度校验，不改签名内容、
不撤销证书、不删除手机数据，也不能修复过期或被撤销的证书。
Android Debug 允许局域网 HTTP；正式发布配置不开放全局明文 HTTP。
试用包签名不代表商店上架签名。

个人中心和启动错误页可修改后端地址，不需要在源码中写 IP。
本机试用后端使用 `data/native-runtime/`，复制旧本地数据后独立运行，
不会覆盖旧工作目录的数据库。

## 测试

```sh
# 根目录
.venv/bin/python -m pytest tests/ -q
# mobile/
flutter test
flutter drive --profile --keep-app-running --no-uninstall-first \
  --driver test_driver/native_driver.dart \
  --target integration_test/native_flow_test.dart -d 设备UDID \
  --dart-define=API_BASE_URL=http://Mac的局域网IP:8003
```

设备测试应使用独立的 `YUNO_DB_PATH`、`YUNO_UPLOAD_DIR`。
流程测试中的 picker 是测试专用图片入口，用于验证后置相机意图、10 图预览、
实际上传和发布；它不能证明相机硬件、权限弹窗或 HEIC 已验收。
脚本显式注册测试文字输入通道，因此验证的是表单内容和提交，不是系统键盘。
交易场景通过 JSON 命令准备卖家、商品及拍卖，再在真实设备的原生详情页、
消息页和交易表单操作并核对 API 状态；买家准备登录与部分页面定位由测试驱动，
不能据此声称这些导航和每个角色后台都已逐项人工验收。
测试前先在同一 bundle ID 的 App 中允许本地网络访问；Flutter 组件测试不能点击 iOS 系统权限弹窗。
保留 `--keep-app-running --no-uninstall-first`，避免测试结束卸载 App，或在重装时重置权限。
测试后重新安装以 `lib/main.dart` 为入口的正常 Release 包。

### 角色与异常流程

`integration_test/role_flow_test.dart` 补验配送、买断、服务、退款争议、原生登录及后台读取。
先启动独立 8003 服务并确认数据库已创建；使用新的数字运行编号，两个命令保持一致：

```bash
# 仓库根目录；仅允许 data/acceptance-*/yuno.db，不接受日常数据库
python3 mobile/tool/acceptance_roles.py \
  --db data/acceptance-本轮编号/yuno.db --run-id "$YUNO_ACCEPTANCE_RUN_ID"
# 另一终端，mobile/ 下
flutter drive --profile --keep-app-running --no-uninstall-first \
  --driver test_driver/native_driver.dart --target integration_test/role_flow_test.dart \
  -d 设备UDID --dart-define=API_BASE_URL=http://Mac的局域网IP:8003 \
  --dart-define=ACCEPTANCE_RUN_ID="$YUNO_ACCEPTANCE_RUN_ID"
```

编号每轮换新。Host 工具只给本轮三个精确测试邮箱分配 admin/courier/appraiser，
最多存活 20 分钟；无 HTTP 管理入口，不读取、生成或打印口令/token。
账号由设备测试通过注册接口创建，随机口令仅保留在测试内存中。
角色准备是测试 fixture，不计为管理员角色分配界面已验收；切换角色会话由脚本完成。
完成后停止 Host 工具与独立 8003 服务，恢复正常 Release 和 8002 服务。

最终结果见 [NATIVE_ACCEPTANCE.md](NATIVE_ACCEPTANCE.md)。真实收款、真实物流、
付费模型与商店上架均不在范围内。原后端 CSRF、图片审核等遗留边界仍见根 README。


## 当前界面版本

当前正常试用包为 0.4.6（11），补齐详情页当前交易价的中日文标签；保留 0.4.5 会话/错误处理与 0.4.4 异步刷新修复。本轮内部试用验收已闭环，版本与证据范围见 [验收记录](NATIVE_ACCEPTANCE.md) 和 [真实 iPhone 硬件实测](NATIVE_HARDWARE_ACCEPTANCE.md)。
界面沿用按用户给定 Muse 参考及手机照片调整的 0.4.1 排版，排版说明见
[NATIVE_UI_0_4_1.md](NATIVE_UI_0_4_1.md)。`GET /me` 额外返回当前用户的 `following` 商品列表；
订单读取中的 `listing` 字段包含商品标题与照片，便于原生订单卡片展示。以上均为读取扩展。

`integration_test/closure_flow_test.dart` 使用同一隔离角色工具与新运行编号，补验拍卖保证金/出价拒绝恢复、一口价取消、后台角色修改、商品上下架和扫描审计。不是相机或系统键盘测试。


### 低占用 Android 验收构建

本机可显式复用 NDK 27.1.12297006 与 CMake 3.22.1：

```sh
# mobile/；JAVA_HOME 指向本机 JDK 17
YUNO_ANDROID_NDK_VERSION=27.1.12297006 flutter build apk --debug --no-pub \
  --target-platform android-arm64 \
  --dart-define=API_BASE_URL=http://Mac的局域网IP:8002
```

此选项仅用于已验证的本地验收工具链，Gradle 统一配置本项目和 Android 插件，开启 NDK 27 的 flexible page sizes。
默认仍为 NDK 28.2；不改共享 SDK 或依赖源码。16 KB 支持依据见 [Android 官方说明](https://developer.android.com/guide/practices/page-sizes)。
当前 APK `outputs/yuno-life-0.4.6-arm64-debug.apk` 的运行库、Dart assets、ZIP 对齐与签名已检查，最终包内所有原生库直接解析 ELF32/ELF64，LOAD 均不低于 16 KB。
此前自动创建分区路径要求约 7.2 GB；现已在独立 2 GiB 稀疏盘的 API 36 模拟器完成安装、启动及四组集成测试，实测系统页大小 16384。

在项目根运行 `python3 mobile/tool/prepare_android_acceptance.py --run-id 新数字编号`，使用已有 SDK 镜像创建项目专属测试盘，再执行打印的启动命令。
磁盘需至少 2 GiB 余量；运行期间持续检查余量，空间不足时只停止本轮专属模拟器。不得使用 Nino AVD。
先安装已有正常 APK，再于 `mobile/` 执行官方 `flutter attach -d 设备序列号 --debug -t integration_test/android_attach_test.dart`，
同时传入 `--dart-define=API_BASE_URL=http://10.0.2.2:8003`、新数字 `ACCEPTANCE_RUN_ID` 和 `ACCEPTANCE_SCENARIO`（默认主业务，或 roles/closure/settlement）。
隔离 8003 和受限角色 Host 需按前述流程先启动。attach 后用 R 热重启，再用其 DDS URL 执行
`flutter drive --no-pub --driver=test_driver/native_driver.dart --use-existing-app=DDS地址 -d 设备序列号`。
入口注册真实 Android JNI 存储插件；媒体和文字仍为测试 fixture，不证明硬件相机或系统键盘。
结束后 detach、恢复正常 APK、停止隔离服务及本轮模拟器，保留证据后可删除本轮测试盘。

`integration_test/settlement_flow_test.dart` 补验到期结算、重复结算、流拍、预警确认与调价批准/驳回。
启动相同的隔离角色工具时加 `--lifecycle-fixtures`；仅本轮精确卖家邮箱和指定测试商品会被准备为老库存/过期拍卖。
该时间与库存准备属于 fixture，不是真实时间流逝，也不是生产管理接口。

整 App 的需求与证据层级对照见 [NATIVE_COVERAGE.md](NATIVE_COVERAGE.md)。

Android arm64 Debug 包交付前运行 `python3 mobile/tool/verify_android_app.py outputs/yuno-life-0.4.6-arm64-debug.apk`（根目录，JAVA_HOME 为已安装 JDK）。
它同时拒绝缺 Flutter 运行库/Dart kernel 的残缺包，并检查签名和 ELF/ZIP 16 KB 对齐。若清理中间文件或本轮引擎转换缓存后增量包缺库，应使用项目 Gradle `--no-daemon --rerun-tasks :app:assembleDebug`（保持 target、target-platform、dart-defines 等本轮构建参数），随后重新检查与安装启动；不要停止其他任务的共享 daemon。

安装/启动 smoke 可给 `prepare_android_acceptance.py` 传 `--data-size-mib 1024`；完整业务验收仍默认 2048。`--avd-home` 可指向本项目内已有测试卷的子目录，余量检查针对该测试卷，模拟器自身兼容性检查保留。本轮主盘空间不足时，在确认内存余量后使用专属 4 GiB RAM 卷、1 GiB 数据盘完成最终 0.4.6 安装冷启动，随后释放 RAM 卷；未使用 Nino AVD、未禁用空间检查。原始配置与操作脚本保留在 `outputs/smoke-0.4.6-ram.py`，结果见最新验收小节。
