# TestFlight 交付记录

2026-11-12（America/New_York）复查：Apple 外部群组页面已显示 **0.4.7（12）“已批准”**，TestFlight 外部 Beta 审核通过。当前外部群组仍为 0 个测试员，未发送邀请或启用公开链接；这不代表正式 App Store 上架审核通过。批准截图与无凭据记录保存在 `outputs/testflight-external-review-approved.png` 和 `outputs/testflight-external-review-approved.json`。

2026-11-11（America/New_York），Yuno Life **0.4.7（12）已成功上传 TestFlight 并提交外部 Beta 审核**。Apple 外部群组页面已显示构建 12“正在等待审核”。尚未发送测试邀请或提交正式 App Store 审核。

- App ID：`6833709556`；Bundle ID：`com.yunolife.shop`。
- [TestFlight 管理页面](https://appstoreconnect.apple.com/teams/aedcac6f-5d95-4898-9a10-0e0ad2d9fb23/apps/6833709556/testflight/ios)。主语言日语，App 支持中日双语。
- 签名 IPA：项目 `outputs/yuno-life-0.4.7-12-app-store.ipa`；未签名归档：`outputs/yuno-life-0.4.7-12-unsigned.xcarchive.zip`。两者均不提交 Git，哈希与结构化证据保存在 `outputs/testflight-delivery-proof.json`。

## 签名和上传

实际使用本机 Xcode 已配置的合法开发者账号和 Apple Distribution 签名，自动注册本项目 Bundle ID、生成本项目 Store 描述文件并完成上传。网页管理员缺少标识符权限并未阻断这条已有授权路径，不需要用户重新登录或付费。没有撤销、替换其他项目证书或修改其他 App 记录。

IPA 深度严格签名校验通过，标识、版本、构建号均读回一致。描述文件为 `iOS Team Store Provisioning Profile: com.yunolife.shop`，含 `beta-reports-active`，无 `ProvisionedDevices` 和 `get-task-allow`。Xcode 日志返回 `Upload succeeded` 和 `EXPORT SUCCEEDED`。

归档源码为 `c9b2135`，与最终验证提交 `32ba3c5` 的整个 `mobile/` 树一致；两者之间只修复了后端测试隔离。图标只移除未使用的全不透明 alpha 通道，RGB 图案不变。

## 代码与云端

- [PR #1](https://github.com/zhanzonggeng123456-ai/yuno-life-shop/pull/1) 已在检查通过后合并，合并提交 `d3deb91`。
- [后端 CI](https://github.com/zhanzonggeng123456-ai/yuno-life-shop/actions/runs/43128245940) 通过 SQLite、libSQL 两套各 133 项回归及容器持久化检查；[iOS CI](https://github.com/zhanzonggeng123456-ai/yuno-life-shop/actions/runs/43128245798) 通过静态检查、25 项 Flutter 测试和归档编译。
- Linux CI 曾出现测试数据库重置竞争，现已为每项测试使用独立数据库；失败日志保留，不计为通过。
- 部署前 [独立加密备份和恢复验证](https://github.com/zhanzonggeng123456-ai/yuno-life-shop/actions/runs/43127540410) 成功。
- 原 Render Free 服务已手动部署 `d3deb91`，部署 ID 为 `dep-dbqgl6brjlhs738851hg`。没有升级付费实例，Turso 持久化及旧 `/api/v1` 保留。
- 公网 `https://yuno-life-shop-free.onrender.com` 的 `/healthz`、根入口、`/api/v1/config`、`/api/v2/config` 返回 200/JSON；两套配置均包含三项服务，未登录 `/api/v2/me` 返回 401。API 使用 `Cache-Control: no-store`。
- 实际核对到 IPA 的 AOT 二进制包含上述公网地址；读取超时延长至 90 秒以容纳免费服务休眠唤醒，写请求没有新增自动重试。

## 范围和保留

本次是 TestFlight 上传，支付与物流仍为模拟，并非正式商店上线。正式日本上架所需的运营资料、账号删除和用户内容治理等另行完成，不记为已通过。

旧 0.4.6 正常包及验收证据保留，不冒称在 0.4.7/TestFlight 全组重跑硬件场景。上传阶段未创建生产测试账号、写入客户数据、操作设备或改动 Nino、经营游戏及正常本地服务。

用于解压和签名的独立 2 GiB RAM 盘已卸载，IPA、归档和本轮日志均保留在本项目 `outputs/`。

## 外部 Beta 审核提交

用户随后明确要求提交 TestFlight 外部测试审核。按 Apple 的前置要求，已创建空的内部群组 `Yuno Life Internal`（未启用自动分发）及外部群组 `Yuno Life External Beta`，并在外部群组送审流程选择构建 12。未邀请测试员或启用公开链接。

已在公网通过正常注册接口创建普通权限的专用 Apple 审核测试账号，独立登录和认证 `/api/v2/me` 均成功；没有使用管理员或客户账号。凭据仅保存在被 Git 忽略、权限为 0600 的 `outputs/testflight-review-account.json`，不写入文档或提交 Git。无凭据的验证结果保存在 `outputs/testflight-review-account-proof.json`。

已在审核表单填写日中双语 Beta 描述及专用登录信息，说明支付与物流为模拟。用户提供审核联系资料后，已补齐姓名、电话（按美国区号 +1 填写）、电子邮箱及同一反馈邮箱，并点击“提交以供审核”。Apple 返回的外部群组页面显示 1 个构建版本，0.4.7（12）状态为“正在等待审核”。这证明已提交，不代表审核通过。

未勾选自动通知测试员，群组仍为 0 个测试员，未启用公开链接。提交截图为 `outputs/testflight-external-review-submitted.png`，无凭据的结构化记录为 `outputs/testflight-external-review-submission.json`。联系人私密资料和审核账号密码不提交 Git。
