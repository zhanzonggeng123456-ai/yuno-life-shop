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
| iOS 编译 | Debug 与 Release 均曾编译成功；后续构建的 Xcode 阶段完成，但 Flutter 复制产物阶段因磁盘不足失败 |
| iOS 安装 | Release 中间产物经本机签名深度验证，可直接安装到连接的 iPhone 16e |
| iOS 启动 | 系统拒绝启动，返回签名、entitlements 或未信任 profile 错误；重新签名和安装后仍未解除。不能判为通过 |
| iPhone 原生流程测试 | Debug 打包、Profile 复制阶段均遇到 `No space left on device`，没有执行到流程断言；不是通过 |
| Android 构建 | Gradle 报 `No space left on device`；没有已验收的 APK 或安装运行证据 |
| 相机/相册硬件 | 未验收，测试 picker 不能替代硬件测试 |
| 商店/真实支付/真实物流 | 明确不做，界面均作模拟说明 |

本地原始日志位于忽略的 `outputs/`：

- `backend-tests.log` / `backend-tests.xml`
- `api-tests.log`
- `flutter-analyze.log` / `flutter-tests.log`
- `ios-build.log` / `ios-release-build.log` / `ios-final-build.log`
- `iphone-integration.log` / `iphone-profile-integration.log`
- `android-build.log` / `android-retry-build.log` / `android-final-build.log`

需要完成的后续验收：释放至少 8 GB 构建空间；定位手机实际的签名/信任提示；
恢复 iOS 正常启动后运行设备流程测试及真实相机操作；构建并在 Android 上安装运行；
最后重新安装正常试用包并核对对应源码版本。测试数据与日常本地数据必须隔离。
