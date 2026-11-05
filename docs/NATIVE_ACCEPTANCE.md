# 原生 App 验收记录

基线：`1ab6b8f`，按 `CODEX_APP_BRIEF.md` 实现。日期：2026-11-05（纽约）。

当前结论：**尚未达到完整交付验收标准**。不得用“安装成功”替代“可正常使用”。

| 项目 | 结果与证据 |
| --- | --- |
| 后端兼容 | 原有 97 项测试保持通过；原业务模块及数据库结构不改 |
| JSON API 集成 | 新增 9 项多流程集成测试；共 106 项后端测试通过（包含概览统计验证） |
| 覆盖流程 | token 注册/登录/过期/退出、权限隔离、直购/支付幂等/完成/评价/退款、议价/消息、10 图/封面/替换/草稿/任务/确认发布、拍卖、买断、自营、配送、三项服务、各后台读取 |
| Flutter 静态检查 | 最终复验 `No issues found` |
| Flutter 组件测试 | 12 项通过：原有 10 项，加上 320 宽/1.5 倍字体中日文布局、相册剩余数量及满额限制；静态检查无问题 |
| iOS 编译 | 清理空间后 Profile 与当前正常 Release 均完整构建成功；当前 0.4.0 Release 44.7 MB（含离线衬线字体） |
| iOS 安装 | Release 中间产物经本机签名深度验证，可直接安装到连接的 iPhone 16e |
| iOS 启动 | 解锁及恢复联网后的复验，系统接受 0.4.0（5）启动；Profile 测试包也已启动并连接 VM 服务。之前签名/信任拒绝记录保留在下方，不能代表后续每次安装均可靠启动 |
| iPhone 原生流程测试 | 已连接真实设备并执行到 ACCEPTANCE: boot；发现同一 iPhone 上另有 Nino 的 xcodebuild 自动测试争用前台。已主动停止 Yuno 测试、恢复正常 Release，未终止 Nino。注册及后续流程仍未通过，待设备可独占时重跑 |
| Android 构建 | 仅保留历史 0.1.0（2）arm64 Debug APK 约 87 MB，`apksigner verify` 通过；0.4.0 未构建。当前不足 1 GiB 空间，且本项目固定的 NDK 28.2 已在之前清理，需要重新安装 |
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

## 0.4.0（5）以更新后的 Muse 链接与用户照片为准

0.3.0 采用旧参考，与用户给定照片不符。重新加载链接后确认新版概览结构，完成 0.4.0 原生调整。
后端 106 项、Flutter 10 项通过，静态检查无问题；Release 44.7 MB 编译、安装与启动通过。
证据：`backend-tests-0.4.log`、`flutter-tests-0.4.log`、`flutter-analyze-0.4.log`、`ios-build-0.4.log`、
`iphone-install-0.4.log`、`iphone-launch-0.4.log`、`iphone-version-0.4.log`，日志均在本机忽略目录 `outputs/`。
实际设备截图及组件预览明确区分，见 [0.4.0 界面说明](NATIVE_UI_0_4.md)。
已清理本项目 `.dart_tool/flutter_build` 内 20 个旧哈希缓存目录，保留当前构建缓存与安装产物；Nino 文件未动。
GitHub 已知写入权限不足，本轮代码保留在本地分支，不声称已推送远端。

## 本次全面验收复核（0.4.0 build 5）

结论仍为 **未通过完整验收**。后端测试不等于原生客户端端到端测试。

- 后端：106 项全部通过（12.51 秒）；日志 `outputs/acceptance-backend-0.4.log`。
- Flutter：12 项全部通过；日志 `outputs/acceptance-flutter-final.log`。静态检查无问题，见 `outputs/acceptance-flutter-analyze-final.log`。
- 发现并修复相册选择未按剩余名额限制的问题：发布草稿及已上架商品管理均传入剩余数量；满 10 张时不再打开草稿相册，保留服务端与提交前校验。新增测试覆盖 9 个剩余名额、只剩 1 个名额和满额拒绝。
- 新增 320 宽、字体 1.5 倍、中日文四个主页面及交易菜单测试，发现日文行情榜标题右侧溢出 2.8 像素。表头改为可换行布局，复测通过。原始失败日志 `outputs/acceptance-accessibility.log` 保留。
- 真机脚本改用当前“交易 → 发布闲置”与“从相册选”入口，覆盖注册、10 图、封面、删除补图、重拍替换、AI、确认上架、退出及语言。随机凭据只在测试内生成，不输出。测试 picker 只验证调用意图，明确不算相机硬件验收。
- 使用独立 8003 服务和独立数据库，未向日常 8002 数据库写入验收交易。本次设备测试未能启动，未进入注册断言；不能把脚本存在计为流程通过。
- 最终正常 `main.dart` Release 包编译成功（44.7 MB），本机 `codesign --verify --deep --strict` 通过，已重新安装，使用日常 8002 服务。日志 `outputs/acceptance-release-build-final.log`、`acceptance-release-install-final.log`。
- 最终启动命令被 iOS 拒绝：CoreDevice 10002 / FBS Security，可能为签名、权限或描述文件未被显式信任。未擅自判定具体原因或撤销共享证书。见 `outputs/acceptance-release-launch-final.log`。
- 真机测试与恢复后的截图分别保留在 `outputs/acceptance-running-iphone.png`、`acceptance-release-final.png`。本次失败不以历史成功启动截图替代。
- 未执行新版 Android 构建及运行、真实相机/相册权限、全部交易客户端流程。空间与设备阻断解除后仍需继续；Nino 源码、归档、设备数据及共享签名配置均未修改。

本次改动保存在本地 `codex/flutter-native-app`。GitHub 写权限此前已拒绝，未声称推送成功。

### 用户解锁并恢复联网后的续验

- `outputs/acceptance-unlocked-launch.log` 记录系统接受正常包启动。截图 `acceptance-unlocked.png` 为应用切换过渡画面，可见 Yuno 新市场页面，不能作为完整页面视觉验收截图。
- `outputs/acceptance-unlocked-flow.log` 记录 Profile 包构建安装、VM Service 连接成功，以及真实设备的 `ACCEPTANCE: boot`；8003 日志也记录来自手机的配置、行情、商品请求。
- 后续截图反复显示 Nino。只读进程检查确认另一项 `xcodebuild test-without-building` 正在同一 UDID 上运行 `NinoSmoke/Smoke/testNormalAppRemoteUI40331`，因此不能同时可靠执行两项前台测试。
- 主动中断本项目 Flutter drive，日志中的 Service has disappeared 是停止测试后连接消失，不据此判定业务崩溃；注册、照片、AI、上架等后续阶段均不计通过。未终止或修改 Nino 测试。
- 已从最终正常构建的 `mobile/build/ios/Release-iphoneos/Runner.app` 恢复安装 0.4.0（5），签名深度校验及安装成功；没有留下 integration_test 测试包。恢复安装日志 `outputs/acceptance-unlocked-restored.log`。为避免争抢设备，恢复后未再次强制拉起应用。
- 已请求用户在 Nino 测试结束或由对应任务暂停后告知，再继续 Yuno 真机验收。完整验收结论仍为未通过。
