# 免费托管、独立备份与恢复

当前状态（2026-11-06，America/New_York）：**Render Free + Turso Free 已上线，独立每日备份已配置，首次工作流与恢复验收通过**。正式地址为 **https://yuno-life-shop-free.onrender.com**。iQOO 8 已升级 0.2.2 (4)，切换到新地址并验证冷启动后配置保留。旧 Railway 试用实例已停止，服务与旧数据卷保留，不再接收写入。换网络实测仍按用户要求暂缓。未开通付费、未绑定支付方式、未操作 Nino。

## 本次实际上线与验收

- Render 服务：`srv-dbn7gvm7bikc73aj4e90`，Singapore，Docker **Free**，单进程，健康检查 `/healthz`，自动部署 Off。首次部署 `dep-dbn7h0e7bikc73aj4gv0`，运行源码 `dc71f73dfe58502b8e681c98898e51f412efb38c`。项目 `prj-dbn7gvjrjlhs739nm100`。使用公开仓库 URL 部署，没有给 Render 扩大私有仓库权限。
- Turso：`yuno-life-shop-free`，Free，AWS Singapore，libSQL。最新原库迁入后核对 1 个原验收账号、1 份未发布草稿、2 张原图、0 订单；原账号与草稿 ID 保留。运行读写令牌与备份只读令牌分离，并实际确认只读令牌写入被拒绝。
- 公网 HTTPS 验证健康、配置三项服务、账号与私有草稿鉴权、两张原图 SHA-256、模拟支付标注、管理/文档路由拒绝公开访问。临时验收会话已撤销，旧 token 返回 401。没有发布假商品、价格或订单。
- 手动 Restart service 后再次执行同一组公网数据与鉴权校验，全部通过。手机在现有 Wi-Fi 下切换成功，停止旧 Railway 后强制结束并冷启动仍使用新地址。未关闭 Wi-Fi、未改移动网络/漫游/APN。
- 第一次备份工作流：[42321717105](https://github.com/zhanzonggeng123456-ai/yuno-life-shop/actions/runs/42321717105)，由 workflow_dispatch 主动触发验收，成功。每日 cron 已在 main 生效；首次未来定时触发尚未到时间，不能当作已经观察到定时触发。
- 备份草稿 Release ID `437226449`，tag `yuno-backup-20261107T010211Z-42321717105`，附件 11,640 字节，`draft=true`。匿名访问返回 404。工作流重新下载、解密恢复成功后，本机又独立下载恢复一次，确认会话 0、原账号 1、草稿 1、图片 2。密文 SHA-256：`e567a975dfac5555bf495fb012f9dc8edf4490be0401a65cbf79932bd0307873`。
- 后端验证 [42321522964](https://github.com/zhanzonggeng123456-ai/yuno-life-shop/actions/runs/42321522964)：SQLite 与 libSQL 两轮各 120 项通过，Docker 构建、拒绝临时磁盘、容器重建数据保留检查通过。CI 固定 Python 3.12 与生产镜像一致，并在测试重置前等待 AI 工作线程关闭 SQLite，消除旧测试删除数据库时的句柄竞争。
- Android 0.2.2 (4) 构建、覆盖安装成功，包名 `com.yunolife.shop`，保留用户偏好与安装数据。APK SHA-256：`7d698e729cfc462154816328a4413c47d1db31d396f5c5cd53fd36067fea2229`。Flutter analyze 与 7 项 widget 测试通过。此轮没有构建新的 iOS 包，不把旧 iOS 构建记为 0.2.2 实机验收。
- 旧 Railway 服务 `6b781eab-5770-4237-8e6d-9f777d90cd6f` 已无活动部署，卷 `b9db08f9-7665-484b-a80d-491b85f2d279` 保留。旧地址不可再作为手机入口；不要直接重新启动旧卷对外接单，避免数据分叉。恢复时先冻结写入、使用已验证的最新独立备份。

## 免费档边界

- Render Web Service 明确 `plan: free`；不创建 Render Postgres（免费数据库会到期）、磁盘、cron 或付费实例。15 分钟无流量休眠，再访问约需一分钟启动；每工作区每月 750 小时，另有流量与构建额度。不要用自动请求保活。官方说明免费实例适合试用/个人项目，不提供生产可用性保证：[Render 免费限制](https://render.com/docs/free)。
- Turso **Free**，使用 **libSQL 引擎**，与现有 SQLite SQL 保持兼容；不选择需要另一驱动的 Turso rewrite 引擎。当前公开免费档 5 GB 数据，包含图片；每月 5 亿行读、1000 万行写。平台政策和额度可能变化：[Turso 价格](https://turso.tech/pricing)、[Python 驱动](https://docs.turso.tech/sdk/python/quickstart)。
- 不承诺“永久免费且永不停机”。这里只采用当前无试用倒计时的免费档；额度耗尽时检查/暂停，不自动升级。备份与可迁移数据是退出平台的保障。
- 所有运行、测试、凭据和资源限定 YUNO；不使用 Nino 数据、数据库、目录、实例或付费额度。

## 持久化实现

`YUNO_STORAGE_MODE=remote` 要求有效的 `TURSO_DATABASE_URL`、`TURSO_AUTH_TOKEN` 和 `YUNO_PHOTO_STORAGE=database`。缺一即启动失败，不能悄悄回退到临时磁盘。已有 Railway 挂载卷模式和本地 SQLite 模式保留。

原业务表与 JSON API 保留。新增 `yuno_uploads` 与 `yuno_upload_chunks` 两表保存原图；每块 256 KiB，每张仍上限 5 MiB。文件名、图片顺序、图片原字节不变；照片与现有业务事务共用连接，失败可回滚。读取时校验大小、连续块和 SHA-256。无需第三家图片服务或付费图片 API。

`render.yaml` 仅一个 Free 实例，手动部署、无磁盘、无其它收费资源。先迁移数据再启动，以免初始化占用空目标。数据库令牌只进平台私密环境变量和本地受保护配置，不能写 Git、APK、日志或报告。

## 迁移与切换顺序

1. 本人完成 Render、Turso 登录/注册，选择免费档；如必须绑卡/升级就停止该平台操作。GitHub 权限只选 `yuno-life-shop`。
2. 创建 YUNO 专用空 libSQL 数据库；最小权限数据库令牌，不使用组织管理密钥。用一个单独的临时 QA 数据库验证真实云事务、照片、重启和超时行为。
3. 在短维护窗口重新导出现有 Railway 的最新数据库及图片。工具用 SQLite 写保留锁获取一致快照；缺失/变化的照片立即报错。不可拿旧备份覆盖新用户数据。
4. 解密恢复到新目录后，只导入**没有业务表的目标**：

   ```powershell
   python -m pip install -r requirements.txt -r requirements-cloud.txt -r requirements-backup.txt
   # Turso URL/token 应由受保护环境提供，不在命令文本中写明文密钥。
   python -m deploy.transfer import --database <新恢复目录>/db/yuno.db --uploads <新恢复目录>/uploads
   ```

   工具在独立副本增加原图块，保留所有原 ID、SQLite 自增水位和业务记录，不修改恢复源；目标已有任何业务表即拒绝覆盖。迁移失败检查事务结果，不盲目重试。
5. 在 Render 核对 Free，再部署。验证 HTTPS、鉴权、草稿、全部图片 SHA、交易状态、容器重建和睡眠唤醒；敏感写请求不得自动重试。Android 初次连接等待时间需要覆盖免费服务约一分钟冷启动，切换时验证。
6. 从 Turso 导出独立备份并在本地重新恢复，通过后再改手机地址。保持旧服务可回退，切换后不能让两个独立数据库同时接收写入。确认无回滚需求后再处理旧资源。

## 备份与恢复操作

所有命令默认不导入应用，不初始化/覆盖源数据；不要公开原始 zip、恢复后的数据库或图片。`create` 仅用于 SQLite 文件 + 图片目录，`transfer export` 用于数据库原图模式。

```powershell
# Railway 容器内，输出放 /tmp，不能放公开 uploads：
python -m deploy.backup create --database /data/db/yuno.db --uploads /data/uploads --output /tmp/yuno-snapshot.zip
# 通过已登录的私有 Console / Files 下载，不增加公开备份 API。

# Turso 模式的独立导出（环境已有数据库专用凭据）：
python -m deploy.transfer export --output <私有目录>/yuno-snapshot.zip

# 本地加密，首次自动生成独立随机密钥；现有输出拒绝覆盖：
python -m deploy.backup seal --archive <私有目录>/yuno-snapshot.zip --key-file <独立密钥目录>/cloud.backup-key --output <备份目录>/yuno-snapshot.yuno-backup

# 恢复必须是全新、不存在的目录，不能直接写活跃数据目录：
python -m deploy.backup restore --archive <备份目录>/yuno-snapshot.yuno-backup --key-file <独立密钥目录>/cloud.backup-key --destination <新的隔离目录>
```

加密采用经过认证的 Fernet；没有正确密钥无法恢复，不能只保存备份而丢失密钥。密钥必须与备份分开保管，另存用户自己的安全位置；不上传到公开仓库或同一公开附件。Windows 本次密钥文件已限制当前用户访问。备份只保存在同一台电脑不防电脑损坏，仍应另留一份加密副本与独立密钥副本。

工具检查数据库完整性、外键、清单、每个文件 SHA-256、引用照片和记录数量；拒绝路径穿越、符号链接、重复条目、篡改和覆盖既有目录。验证后原子发布恢复目录。当前工具总展开大小上限 256 MiB，超限报错，不算成功备份；达到前要实现流式加密/导出。手动工具不删除历史备份或业务数据。

自动备份代码在 `.github/workflows/backup.yml` 与 `scripts/automated_backup.py`，所需私密配置已设置，main 上已启用。每天 18:23 UTC（当前美东冬令时 13:23；夏令时 14:23，日本次日 03:23）运行，GitHub 调度可能延迟。只使用当前公共 YUNO 仓库的标准 Linux runner，不使用私有 CI 分钟、Actions artifacts、共享附件存储或收费 runner，不创建 Nino 资源。

整个流程为：只读 Turso 凭据导出一致快照 → Fernet 加密 → 本地解密恢复 → 创建 `draft=true` 的**未发布草稿 Release** → 上传加密附件 → 重新下载并再次解密、恢复、校验。只有新备份真实下载恢复成功，才根据规则清理 YUNO 自己生成的旧草稿备份。完整附件保留最近 7 日和最近 4 个自然周的代表快照（重叠不重复）；不修改普通版本发布、未完成的草稿附件、业务表或 Nino。备份失败会保留旧备份并使 GitHub 工作流失败，以便账户已有的工作流失败通知生效。

即使源码仓库公开，草稿 Release 仍未公开；附件本身另外加密，不能把它手动 Publish。数据库只读令牌和加密密钥分别存入仓库 Actions Secrets，本地保留独立恢复密钥。只读凭据不能用于后端写交易；Render 后端使用另一个仅限 YUNO 数据库的读写令牌。任何密钥都不写源码、APK、日志或报告。

成功备份后只更新 `ops/last-backup.json` 的时间、密文 SHA-256、草稿编号与验证结果，不记录个人资料或数据库内容；实际备份记录也保持这个仓库有维护活动。GitHub 公共仓库的定时工作流存在长期无活动自动停用等政策，不能保证调度永远持续，仍需关注失败通知与记录新鲜度。额度、网络或政策变化不会自动升级付费。每次发布/迁移前仍应额外备份，平台自带的短期恢复窗口不能替代独立备份。

官方依据：[公共仓库标准 runner 免费](https://docs.github.com/en/billing/concepts/product-billing/github-actions)、[Release 附件限制](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)。

## 本次迁移准备的补充核对

已创建 `yuno-life-shop-free` 专用 libSQL 数据库，位于 AWS Singapore，账户为 Free。SQLite 网页文件上传未成功，因此改为空库再通过官方驱动导入；绝不覆盖已有业务表。当前迁移快照 SQL 约 19 KiB，已通过单批事务实际导入。云端始终执行外键约束，导入脚本按依赖顺序先建父表、再插入父记录和图片块。大于 8 MiB SQL 的导入会停止，不能悄悄分批产生半份数据。

官方 libSQL 0.1.11 驱动的连接级 `executescript` 会吞掉 SQL 错误，适配层改用会抛错的 cursor 方法，避免初始化失败却继续运行。相关回归已覆盖。手机读取等待延长至 90 秒，容纳免费后端休眠唤醒；写请求没有新增自动重试。

## 本次已完成的真实云数据恢复

2026-11-06：从现有 Railway 私有 Console 导出，下载到本地、加密，再恢复到独立新目录。快照包括 1 个验收账号、1 份未发布草稿、2 张图片；会话为 0、订单为 0。隔离 API 验证原账号 ID、草稿 ID 和两张图片字节 SHA 均通过。只在恢复副本创建短期验证会话，并在验证结束后清除；未修改云端账号或订单，未公开备份内容。

加密文件 SHA-256：`656ce9d5843eefc7e9abba711aaa59734d94fc4c01b59c0c63de1c8a03e3319e`。密钥路径仅在本地交付记录保存，不在公共仓库保存。
