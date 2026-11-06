# 原生 App 验收记录

基线：`1ab6b8f`，按 `CODEX_APP_BRIEF.md` 实现。日期：2026-11-05（纽约）。

当前结论：**尚未达到完整交付验收标准**。不得用“安装成功”替代“可正常使用”。

| 项目 | 结果与证据 |
| --- | --- |
| 后端兼容 | 原有 97 项测试保持通过；原业务模块及数据库结构不改 |
| JSON API 集成 | 新增 11 项多流程集成测试；共 108 项后端测试通过（包含概览统计验证） |
| 覆盖流程 | token 注册/登录/过期/退出、权限隔离、直购/支付幂等/完成/评价/退款、议价/消息、10 图/封面/替换/草稿/任务/确认发布、拍卖、买断、自营、配送、三项服务、各后台读取 |
| Flutter 静态检查 | 最终复验 `No issues found` |
| Flutter 组件测试 | 13 项通过：实际字体的零/大金额与主页面检查，加上原有 10 项，加上 320 宽/1.5 倍字体中日文布局、相册剩余数量及满额限制；静态检查无问题 |
| iOS 编译 | 清理空间后 Profile 与当前正常 Release 均完整构建成功；当前 0.4.3 Release 44.7 MB（含离线衬线字体） |
| iOS 安装 | Release 中间产物经本机签名深度验证，可直接安装到连接的 iPhone 16e |
| iOS 启动 | 当前 0.4.3（8）正常 Release 安装、启动及真实首页截图通过；历史 0.4.0 Profile 交易测试也已通过。历史签名/信任拒绝记录保留在下方 |
| iPhone 原生流程测试 | 0.4.0 主要业务场景 68 秒通过；0.4.1 追加角色场景 67 秒通过，0.4.2 扩展为 84 秒通过，包含配送履约、退款/争议、买断入库、服务处理、原生登录/必填异常及 17 后台读取分区。媒体与文字输入为测试入口；硬件、系统权限及未执行的后台写操作不计通过，详见本记录最新小节 |
| Android 构建 | 当前 0.4.3（8）调试包已构建、签名与 16 KB 对齐验证通过，见最新小节。历史：仅保留历史 0.1.0（2）APK；当前 0.4.0 构建尝试补齐 NDK 28.2 后磁盘只剩约 197 MiB，已主动停止本项目 Gradle 并清除新增 NDK 28，保留原有 NDK 27。新版未构建成功，未计通过 |
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

### 排队释放后的设备验收（2026-11-05，纽约）

只读检查确认不再有其他真机测试占用该 UDID 后续验；未终止任何 Nino 进程。
设备仍连接，独立 8003 与正常 8002 服务已恢复，分别使用验收与日常数据目录。

1. 修正测试输入：IntegrationTest 默认使用真实文字输入通道，Profile 中原脚本 `enterText` 未将内容写入，造成空表单注册被后端 400 拒绝。显式注册测试文字输入通道并增加不输出凭据的布尔断言，重跑注册通过。不是通过放宽后端验证使测试通过。
2. 修正测试定位：`Finder.first` 在懒加载列表尚未构建目标时会直接报 No element；改为先滚动至控件存在再定位。原生产品代码未因测试而改变。
3. 发布场景完整通过：真实 Keychain、注册、默认后置相机调用意图、10 图实际上传、AI、封面、删除后补图、重拍/替换、手动售价、用户确认上架、退出清理 token、中日文即时切换。媒体是合法 PNG fixture，不能证明相机权限、硬件、HEIC 或真实相册；文字输入同样是测试通道，不能证明系统键盘。
4. 扩展交易场景通过：在独立库用公共 JSON 命令准备卖家、商品、拍卖和买家会话，再使用真机原生详情页、消息页及表单执行收藏、消息、直购、模拟支付、配送预约、确认收货、评价、议价及接受卖家还价、拍卖出价、买断申请和三项服务预约。用 API 核对收藏、消息、订单状态/金额、配送记录、出价、买断与服务记录。部分页面由测试直接定位，运营角色审核/收购付款、配送员履约、退款争议全链路等没有在本次客户端测试中执行；原后端测试覆盖不替代这些原生验收。
5. 最终扩展场景日志 `outputs/acceptance-queue-business.log` 显示所有阶段以及 All tests passed，耗时 68 秒（1 个完整场景，框架 teardown 不另计业务用例）；较早输入/滚动失败日志分别保留在 `acceptance-queue-resume.log`、`acceptance-queue-input-fixed.log`。最终静态检查 `acceptance-queue-analyze.log` 无问题。
6. 结束后已恢复签名验证通过的正常 Release `mobile/build/ios/Release-iphoneos/Runner.app`，重新安装并启动成功。截图见 [恢复后的实际 iPhone 主页](previews/iphone-acceptance-restored-0.4.0.png)，不是组件预览；正常服务统计仍为零，没有把验收交易写入日常库。安装/启动日志 `acceptance-queue-restored.log`、`acceptance-queue-normal-launch.log`。已请求用户补验真实拍照及相册添加，尚未收到结果。
7. Android 已实际尝试当前 0.4.0 构建。设置本机 JDK 17 后开始 Gradle，成功下载/解压要求的 NDK 28.2，但可用空间从约 4 GiB 降到 197 MiB；为避免磁盘写满，主动停止本项目 Flutter/Gradle 构建。移除本次新增 NDK 28 后恢复约 3 GiB，保留原有 NDK 27、Gradle 下载缓存和 Nino 内容。新版 APK 没有生成，Android 安装、运行均未计通过。需准备更多空间后续验（建议构建前至少 8 GiB）。日志 `acceptance-queue-android-build.log`。
8. 仅清理本项目 iOS Profile 与重复的 iphoneos 产物、Release 内除正常 Runner.app 外的中间文件；正常安装包保留。Nino、共享证书及描述文件未动。

当前结论：iOS 主要业务场景已有真实设备自动化通过证据，但 **完整验收仍未通过**。
剩余重点为真实硬件/权限、Android 当前版本及未执行的角色与异常流程，不以已通过场景代替。

### 0.4.1（6）用户照片反馈后的排版修正

用户指出 ¥0 字形和整体排版不协调。统一金额字形和行高、压缩概览留白、修正榜单左对齐，统一表单/按钮/交易菜单圆角，导航标签略放大，个人中心登录按钮改为藏蓝。
13 项 Flutter 检查通过（包含新增实际字体零金额/大金额及主页面检查）；静态检查无问题。
正常 Release 44.7 MB 构建、签名深度校验、安装及启动通过；设备清单明确为 0.4.1 build 6。
实际设备截图及修改说明见 [0.4.1 排版说明](NATIVE_UI_0_4_1.md)。
之前 0.4.0 的 68 秒交易场景记录保留，本次未重跑该全链路；不扩大本次视觉验收的结论。
Android、真实相机/相册权限和未执行角色/异常流程仍待验收，不因本次视觉修正记为通过。
正常试用包现位于 `mobile/build/ios/Release-iphoneos/Runner.app`（0.4.1 build 6），后续测试结束应恢复此包，不能恢复旧的 0.4.0 备份。

### 2026-11-06 继续验收：角色链路与异常表单

当前 0.4.1（6）下新增 `mobile/integration_test/role_flow_test.dart`，真实 iPhone 场景 **67 秒通过**；静态检查无问题。不是重放之前的发布场景，也不把 teardown 计为额外业务用例。

- **原生登录与异常**：错误口令显示错误且未建立会话，随后正确口令登录成功；普通买家请求后台用户读取被后端 403 拒绝。403 验证是设备发出的请求断言，不声称后台错误页交互已逐项人工测试。
- **配送履约**：配送员原生表单接单、取货完成、交付完成，买家原生确认，读取状态为 confirmed。照片附件未使用，不算配送拍照/硬件通过。
- **退款与争议**：空退款原因在原生表单被必填校验拦截，订单仍 paid；填写后提交，运营通过下拉选择和裁决依据批准退款，订单为 refunded，终态动作中没有支付和确认收货。另一个订单由买家发起争议、运营裁决，争议为 decided。模拟支付订单由 API fixture 准备，没有真实收款。
- **买断与入库**：运营审核/报价、卖家接受报价、卖家使用原生日期和时间选择器预约取货、鉴定员填验货说明、运营模拟收购付款并输入自营售价，买断为 completed，自营库存包含对应 buyback_id。订单和商品由隔离 API fixture 准备，角色切换由脚本登录完成。
- **服务处理**：运营确认/开始/完成清洁服务，状态 completed；买家取消另一个配送预约服务，状态 cancelled。
- **后台读取**：17 个原生后台分区载入未出现 Flutter 异常，服务日志记录全部 200：用户、商品、买断、订单、库存、拍卖、配送、服务、退款、争议、鉴定、利润、预警、调价、费用、审计、设置。只计读取页面，未把每个后台写操作都算通过。
- **安全存储**：最终退出，Keychain session 已清理；恢复语言与服务器偏好。

角色准备工具 `mobile/tool/acceptance_roles.py` 仅接受本仓库 `data/acceptance-*/yuno.db`，
只修改本轮数字编号对应的三个精确邮箱角色，无新 HTTP 路由、无鉴权旁路。
实际调用日常 `data/native-runtime/yuno.db` 的防误操作校验返回退出码 2，角色分配未执行。
不读取或打印账号口令/token。此次权限准备不计为 App 的角色分配操作已通过。

证据：本机忽略目录 `outputs/role-device-flow.log`（各阶段与 All tests passed）、
`role-analyze.log`、`role-fixture-guard.log`、`role-restored-install.log`、
`role-restored-launch.log`、`role-restored-version.json`、`role-restored-phone.png`。
正常 Release 已重新安装、启动并取得实际首页截图；设备清单确认为 **0.4.1 build 6**，
没有留下测试入口。临时角色工具及独立 8003 服务均已停止；正常 8002 服务仍可用，日常成交数据仍为零。

当前仍不能记为完整交付通过：Android 当前版本缺构建/安装/运行证据；真实相机、相册、系统键盘等硬件/权限未补验。高价值人工鉴定、后台参数修改等未执行的写操作不在本次通过范围。
磁盘约 2.3 GiB，本次没有重试会耗尽空间的 Android 构建；Nino 与共享签名配置未改动。

### 0.4.2（7）后台写操作扩展与失败状态修复

继续检查后台参数修改时，新增回归测试复现：原业务拒绝越界佣金并重定向带
`rate_out_of_range`，但 JSON 边界未识别该拒绝消息，错误返回 200 和模拟成功结果。
这会使原生表单关闭并误报已提交。修复仅在 `app/api_v1.py` 将已有越界消息映射为 409，
原业务验证不改；App 给出明确的中日文范围提示，失败时保留表单供修正。

- 修复前 `outputs/settings-range-before.log` 明确记录期望 409、实际 200 的失败。
- 新增回归验证：返回错误码、原佣金设置未改变。全后端 **107 项通过**（12.64 秒），包含原有 97 项及 10 项手机 API 测试。
- Flutter 13 项检查通过，静态检查无问题。
- 扩展后的真实 iPhone 角色场景 **84 秒通过**：保留前一轮配送、买断、退款争议、服务、错误登录与校验流程，再补充高价值商品待审核时购买被拒绝、原生审核表单批准并记录身份 fixture、原生费用登记、参数越界不关闭表单/显示范围错误/后端值不变、合法 0.08 保存成功。最后通过 API 恢复验收库原参数。
- 高价值“身份验证/审核”是隔离测试资料中的状态操作，不代表真的鉴定了物品或核验真实身份；费用与交易也都是验收 fixture。部分后台页面由测试直接定位，角色由短时 Host 工具准备。
- 原生审核通过后读取 appraisal_status=approved、identity_verified=1；费用列表含本轮 1200 日元测试记录。参数更新测试均在独立 8003 库，未改日常经营参数。
- 临时权限工具和 8003 测试服务已停止；正常 8002 服务已用最新 JSON 边界重启，数据目录不变。

证据：`role-device-final.log`、`role-backend-final.log`、`role-widget-final.log`、
`role-analyze-final.log`、`role-release-0.4.2-build.log`，均在本机忽略目录 `outputs/`。
本次正常 Release 44.7 MB 构建成功，版本更新为 **0.4.2 build 7**；手机安装/启动复核通过，设备清单确认版本 0.4.2（7）。
Android 当前包、真实相机/相册/系统键盘仍无通过证据；未执行的后台写操作不扩大计入本轮通过范围。

最终恢复证据：`role-0.4.2-install.log`、`role-0.4.2-launch.log`、`role-0.4.2-version.json`。
[实际 iPhone 首页截图](previews/iphone-market-0.4.2.png) 已核对，正常成交数据仍为零。
已清理本项目 Profile、重复 iphoneos、单元测试缓存及 Release 非 App 中间文件；
保留 `mobile/build/ios/Release-iphoneos/Runner.app` 正常 **0.4.2（7）**，可用空间恢复约 2.7 GiB。
没有修改 Nino、原有 NDK 27、共享证书或描述文件。


### 0.4.3（8）全线补验：拍卖拒绝恢复与后台写操作

用户要求全线闭环，继续补查此前未覆盖的拒绝状态与后台操作。
新增回归测试复现：保证金未交时拍卖拒绝出价，但 JSON 接口错误返回 200。
仅修正 JSON 边界对 `deposit_required`、`bid_too_low:*`、`proxy_below_bid`、
`auction_ended`、`no_buy_now` 的拒绝映射为 409；原拍卖业务模块未改。
原生界面显示中日文具体提示，保留出价表单，允许修改后继续。

- 后端 **108 项通过**，13 项 Flutter 检查通过，静态检查无问题。
- 新增 `mobile/integration_test/closure_flow_test.dart`，隔离 8003 库与新数字运行编号；真实 iPhone **33 秒通过**。
- 原生拍卖：未交模拟保证金被拦截且无出价记录；交模拟保证金；出价不足及代理上限不足均保留表单和明确提示；修正后产生一条出价；一口价生成待支付订单；取消后为 cancelled。
- 原生后台：修改本轮买家角色为 collector 后读回验证，再恢复 user；新商品 removed/active 往返；触发异常扫描、调价扫描并核对审计记录。没有把“扫描调用成功”算成“产生了建议、批准/驳回建议、处理异常记录”均通过。
- 首轮脚本只按 ` #编号` 查找用户卡片，未包含姓名，因此后台定位未完成；改成完整标题编号后缀，换新运行编号后全场景通过。首轮日志保留，不作全通过证据。
- 测试文字仍走测试通道，角色由短时 Host fixture 分配；不能据此证明真实系统键盘或真实身份验证。
- 停止本轮 Host 工具与 8003，正常 8002 已重新加载最新接口代码，仍使用 `data/native-runtime/`。
- 正常 0.4.3（8）Release 44.7 MB 构建、签名深度校验、安装、启动及设备版本核对通过；[实际 iPhone 首页截图](previews/iphone-market-0.4.3.png) 已核对。后续测试必须恢复本包，不能用旧版本备份。

证据位于忽略的 `outputs/`：`closure-auction-before.log`、`closure-backend.log`、
`closure-flutter.log`、`closure-analyze-final.log`、`closure-device-final.log`、
`closure-release.log`、`closure-normal-install.log`、`closure-normal-launch.log`、
`closure-normal-version.json`、`closure-normal-phone.png`。

**全线验收仍未闭环**：Android 当前版本缺构建安装运行证据，安全清理本项目中间文件后磁盘仍低于 8 GiB；不重复下载 NDK 使磁盘写满。
实际尝试 Device Hub 的 View Screen 后一直停留 Connecting display，未能取得可操作手机屏幕；真实相机/相册/系统键盘仍无通过证据。
其余未执行的后台写操作、拍卖到期结算等不扩大计入通过范围。此前硬件问题用户仅回复“允许”，不是拍照和相册成功的结果。
未改动 Nino、共享证书/描述文件；本地提交不代表已推送 GitHub。


### 2026-11-06 续验：拍卖到期与后台决策

`mobile/integration_test/settlement_flow_test.dart` 在实际 iPhone **25 秒通过**，日志 `outputs/settlement-device-final.log`。

- 拍卖成交结算后为 ended_sold；再次原生结算，买家对应商品仍只有一笔订单；原生模拟支付及确认收货后 completed。另一个无出价过期拍卖原生结算后 ended_unsold。
- 原生异常扫描产生本轮大幅跳价预警，点击“确认处理”并核对 acknowledged。
- 原生生成调价建议后，对两个不同库存分别“批准调价”和“驳回”；读取 approved/rejected，批准商品价格等于建议价格、驳回商品价格保持 22000；审计包含结算、预警确认、价格修改与驳回。
- 首轮测试样本中位数等于其中一个库存原价，因此业务正确地没有生成该商品的调价建议，脚本 firstWhere 失败；补足低价同行 fixture 后，换新数字编号重跑通过。原业务规则没有为测试改动。
- 使用独立 data/acceptance-settlement-* 库。`acceptance_roles.py --lifecycle-fixtures` 仅处理本轮精确卖家邮箱与命名商品：准备老库存与拍卖时间，用以避免等待几十天或真实拍卖结束；不能将此记为真实时间流逝验证。调用日常库时仍被路径保护拒绝（退出码 2，`settlement-fixture-guard.log`）。
- 媒体/系统键盘没有在本次测试中操作。Device Hub 现明确提示 Screen Sharing Unavailable，iPhone 须 iOS 27.0 或以上；当前为 iOS 26.5。不会擅自升级手机。
- 测试后正常 **0.4.3（8）** Release 已签名验证、恢复安装、启动并核对实际首页截图（outputs/settlement-normal-phone.png）。没有留下测试入口。


### 当前 Android 包构建突破与剩余运行阻断

在本机显式选择已安装 NDK 27.1 和 CMake 3.22.1，项目内通过 Gradle finalizeDsl 配置插件工具链，开启 flexible page sizes；没有修改共享 SDK 或 pub 插件源码，默认构建仍选 NDK 28.2。
这是新的低占用构建路径，不是再次下载之前耗尽空间的 NDK 28。

- **0.4.3（8）Android APK 当前版构建成功**，102 MB：`outputs/yuno-life-0.4.3-arm64-debug.apk`。
- `aapt dump badging` 确认 applicationId=com.yunolife.shop.dev、versionName=0.4.3、versionCode=8、minSdk=24。
- APK 签名验证通过，ZIP 16 KB 对齐检查通过；包内各 `.so` 的 LOAD 对齐为 0x4000 或 0x10000，没有低于 16 KB。日志：`android-ndk27-signature.log`、`android-ndk27-zipalign.log`、`android-ndk27-elf.log`。
- 构建证据 `android-ndk27-variant.log`（94.9 秒，Built app-debug.apk）。较早 Gradle 回调时机配置失败日志保留，不作成功证据；最终使用 finalizeDsl 修正。
- 本机只启动独立 YunoNativeAcceptance，未使用 Nino AVD。实际启动发现系统镜像创建 userdata 时仍要求 7372.80 MB；缩小本项目配置和官方 qcow2 选项不能解除该要求，均返回明确空间错误。没有跳过空间检查或强制写满磁盘。
- Android **安装与运行仍未通过**，不能把 APK 构建或 ELF 对齐代替实际 16 KB 系统运行。日志：`android-yuno-boot-final.log`、`android-yuno-qcow2.log`。
- 已保留 APK 与 iOS 正常 Release，清除本项目 Android/iOS 重复构建中间文件，以及本轮 Flutter 引擎版本唯一的解压转换缓存（可从已缓存原始依赖再生成），空间恢复约 2.7 GiB；未改 Nino、NDK 27、共享证书/描述文件。
- 本轮 8003 与角色/时间 fixture 已停止，正常 8002 持续运行。iPhone 仍为正常 0.4.3（8）包。全线验收仍缺真实相机、相册、系统键盘和 Android 安装运行证据。
