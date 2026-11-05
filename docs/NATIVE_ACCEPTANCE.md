# 原生 App 验收记录

基线：`1ab6b8f`，按 `CODEX_APP_BRIEF.md` 实现。日期：2026-11-05（纽约）。

当前结论：**尚未达到完整交付验收标准**。不得用“安装成功”替代“可正常使用”。

| 项目 | 结果与证据 |
| --- | --- |
| 后端兼容 | 原有 97 项测试保持通过；原业务模块及数据库结构不改 |
| JSON API 集成 | 新增 7 项多流程集成测试；共 104 项后端测试通过 |
| 覆盖流程 | token 注册/登录/过期/退出、权限隔离、直购/支付幂等/完成/评价/退款、议价/消息、10 图/封面/替换/草稿/任务/确认发布、拍卖、买断、自营、配送、三项服务、各后台读取 |
| Flutter 静态检查 | 最终复验 `No issues found` |
| Flutter 组件测试 | 4 项通过：390px 五入口/双榜/空态/登录态；原生密码表单；语言持久化；安全存储及切换服务器清除 token |
| iOS 编译 | 清理空间后 Profile 与当前正常 Release 均完整构建成功；Release 19.4 MB |
| iOS 安装 | Release 中间产物经本机签名深度验证，可直接安装到连接的 iPhone 16e |
| iOS 启动 | 规范 Flutter 运行库访问权限、重新安装后，系统已允许启动；进程查询及设备截图确认原生市场主页、商品数据与五个底部入口可见。不能仅凭这些操作断定原始签名错误的唯一根因 |
| iPhone 原生流程测试 | 已进入真实设备流程断言，但首轮注册未通过；后续发现 iOS 本地网络系统弹窗阻断流程，尚未完成。测试脚本增加启动等待、隔离服务器及注册完成等待；不计为通过 |
| Android 构建 | 清理空间后构建成功；统一 NDK 28.2 后再次构建成功；arm64 Debug APK 约 87 MB，`apksigner verify` 通过 |
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
并确认原生市场主页已显示。当前正常 Release 已恢复安装，手机等待用户允许本地网络访问。
本轮未撤销、替换开发证书，未删除 Nino 数据；已关闭本项目两个陈旧的服务进程，
保留当前 8002 试用服务与独立 8003 测试服务，避免旧代码进程继续响应请求。

补充证据：`ios-release-after-fix.log`、`iphone-normalized-install.log`、
`iphone-release-current-install.log`、`iphone-release-current-launch.log`、
`iphone-restarted.png`（市场主页）、`iphone-release-current.png`（系统网络权限弹窗）、
`iphone-integration-after-fix.log`、`iphone-integration-retry.log`、`iphone-integration-waited.log`。

需要完成的后续验收：允许手机本地网络访问后，重跑设备流程测试及真实相机操作；在 Android 上安装运行；
最后重新安装正常试用包并核对对应源码版本。测试数据与日常本地数据必须隔离。
