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
Android SDK 36、JDK 17、NDK `27.1.12297006`。首次双平台构建建议预留 8 GB 以上。

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
flutter drive --profile --driver test_driver/native_driver.dart \
  --target integration_test/native_flow_test.dart -d 设备UDID \
  --dart-define=API_BASE_URL=http://Mac的局域网IP:8003
```

设备测试应使用独立的 `YUNO_DB_PATH`、`YUNO_UPLOAD_DIR`。
流程测试中的 picker 是测试专用图片入口，用于验证后置相机意图、10 图预览、
实际上传和发布；它不能证明相机硬件、权限弹窗或 HEIC 已验收。
测试后重新安装以 `lib/main.dart` 为入口的正常 Release 包。

最终结果见 [NATIVE_ACCEPTANCE.md](NATIVE_ACCEPTANCE.md)。真实收款、真实物流、
付费模型与商店上架均不在范围内。原后端 CSRF、图片审核等遗留边界仍见根 README。
