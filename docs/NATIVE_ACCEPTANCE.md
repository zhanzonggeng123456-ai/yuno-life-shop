# 原生 App 验收记录

基线：`1ab6b8f`，按 `CODEX_APP_BRIEF.md` 实现。日期：2026-11-05（纽约）。

当前结论：**尚未达到完整交付验收标准**。不得用“安装成功”替代“可正常使用”。

| 项目 | 结果与证据 |
| --- | --- |
| 后端兼容 | 原有 97 项测试保持通过；原业务模块及数据库结构不改 |
| JSON API 集成 | 新增 7 项多流程集成测试；共 104 项后端测试通过 |
| 覆盖流程 | token 注册/登录/过期/退出、权限隔离、直购/支付幂等/完成/评价/退款、议价/消息、10 图/封面/替换/草稿/任务/确认发布、拍卖、买断、自营、配送、三项服务、各后台读取 |
| Flutter 静态检查 | 最终复验 `No issues found` |
| Flutter 组件测试 | 9 项通过：五页布局、中日文双列长标题、搜索与分类请求、交易跳转、订单状态筛选及收藏数据、登录表单、语言即时刷新及持久化、token 隔离；静态检查无问题 |
| iOS 编译 | 清理空间后 Profile 与当前正常 Release 均完整构建成功；Release 19.4 MB |
| iOS 安装 | Release 中间产物经本机签名深度验证，可直接安装到连接的 iPhone 16e |
| iOS 启动 | 0.3.0（4）已安装并成功启动，真机截图显示新版市场及接口商品；详情见 NATIVE_UI_0_3.md。旧版 0.2.0 的验证错误保留在下方历史记录中 |
| iPhone 原生流程测试 | 已进入真实设备流程断言，但首轮注册未通过；后续发现 iOS 本地网络系统弹窗阻断流程，尚未完成。测试脚本增加启动等待、隔离服务器及注册完成等待；不计为通过 |
| Android 构建 | 0.1.0（2）arm64 Debug APK 约 87 MB，`apksigner verify` 通过；本轮 0.3.0 因空间不足未重新构建 Android 包 |
| Android 运行 | 已创建独立 YunoNativeAcceptance 测试设备，不使用 Nino AVD；模拟器要求约 7.2 GiB 可用空间，当前不足，尚未启动及执行流程测试 |
| 相机/相册硬件 | 未验收，测试 picker 不能替代硬件测试 |
| 商店/真实支付/真实物流 | 明确不做，界面均作模拟说明 |

本地原始日志位于忽略的 `outputs/`：

- `backend-tests.log` / `backend-tests.xml`
- `api-tests.log`
- `flutter-analyze.log` / `flutter-tests.log`
- `ios-build.log` / `ios-release-build.log` / `ios-final-build.log`
- `iphone-integration.log` / `iphone-profile-integration.log`
- `android-build.log` / `android-retry-build.log` / `android-final-build.log` / `android-space-retry.log` / `android-current-build.log` / `android-emulator.log`

2026-11-05 补充：已清理重复下载的 GitHub Desktop，以及无用户 App、已关机的
iOS 27.1 默认模拟器所用系统镜像，清理后磁盘可用约 8.5 GiB。Nino 源码、
三份归档、Nino iPhone 17 Pro 设备数据及其 iOS 26.5 系统镜像均保留。
Android 构建补齐 NDK 28.2 与插件所需平台版本后，清掉 Yuno 构建中间文件，
保留 `outputs/yuno-life-android-arm64-debug.apk`（安装包不纳入 Git）。
此时可用空间约 3.7 GiB；构建工具不是 Nino 文件，Nino 数据保持不动。
用户确认联网后仍有“无法验证 App”或“完整性”提示。后续重新安装后系统接受启动，
并确认原生市场主页已显示。0.1.0（2）恢复后用户已确认允许本地网络并进入市场。随后按用户反馈进行视觉更新；
0.2.0（3）已完整构建及安装，但新包的设备验证再次受阻，不能沿用旧版的启动通过结论。
本轮未撤销、替换开发证书，未删除 Nino 数据；已关闭本项目两个陈旧的服务进程，
保留当前 8002 试用服务与独立 8003 测试服务，避免旧代码进程继续响应请求。

补充证据：`ios-release-after-fix.log`、`iphone-normalized-install.log`、
`iphone-release-current-install.log`、`iphone-release-current-launch.log`、
`iphone-restarted.png`（市场主页）、`iphone-release-current.png`（系统网络权限弹窗）、
`iphone-integration-after-fix.log`、`iphone-integration-retry.log`、`iphone-integration-waited.log`。

需要完成的后续验收：允许手机本地网络访问后，重跑设备流程测试及真实相机操作；在 Android 上安装运行；
最后重新安装正常试用包并核对对应源码版本。测试数据与日常本地数据必须隔离。

## 0.2.0（3）视觉更新

仓库主分支复核仍为 `1ab6b8f`；本地原生开发分支为 `codex/flutter-native-app`。
设计及明确标注的渲染预览见 [NATIVE_UI_0_2.md](NATIVE_UI_0_2.md)。
新日志：`flutter-tests-polish.log`、`flutter-analyze-polish.log`、`ios-polish-build.log`、
`iphone-polish-launch.log`、`iphone-polish-signed-launch.log`、`iphone-polish-flutter-run.log`。

本轮继续清理可再生成的 Gradle 缓存，并移除本任务新增的 NDK 28.2（重做 Android 构建时需重新安装）；
原有 NDK 27.1、Nino 项目、归档及设备数据均保留。

Mac 解锁后的复核：`outputs/iphone-ui-0.2-unlocked.png` 仅证明系统验证弹窗仍遮挡屏幕，不能作为新版 UI 通过证据。设备安装清单确认版本 0.2.0（3）；8002 公共配置接口可达。未删除 Nino 内容，未改动共享开发证书或描述文件。

## 0.3.0（4）按 Muse 静态界面对齐

用户确认 GitHub main 仍为 `1ab6b8fe`，静态 artifact 的后续改动不在 GitHub。
本轮直接按用户给定的 Muse 参考实现原生 UI，不声称移植了 artifact 中未提供的门禁或“100 次跑满”结果。

新增 `/me` 收藏列表与订单内商品展示字段，只扩展 JSON 读取；原业务逻辑与数据库结构不改。
104 项后端测试及 9 项 Flutter 测试通过，静态检查无问题；编译、安装与启动证据见
`outputs/backend-tests-muse.log`、`flutter-tests-muse.log`、`flutter-analyze-muse.log`、
`ios-muse-final-build.log` 及 `docs/previews/iphone-market-0.3.0.png`。
真机主页通过不等于全部交易流程通过；相机硬件、完整真机流程与 Android 新版运行仍待验收。
