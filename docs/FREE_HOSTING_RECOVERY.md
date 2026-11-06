# 免费托管、独立备份与恢复

当前状态：现有 Railway Trial 继续服务；Render Free + Turso Free 的代码适配和配置已准备，**尚未迁移上线**。不能把本地 libSQL 驱动测试当作真实 Turso 云端验收。换网络手机实测由用户另行安排。未开通付费、未绑定支付方式、不操作 Nino。

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

工具检查数据库完整性、外键、清单、每个文件 SHA-256、引用照片和记录数量；拒绝路径穿越、符号链接、重复条目、篡改和覆盖既有目录。验证后原子发布恢复目录。当前工具总展开大小上限 256 MiB，超限报错，不算成功备份；达到前要实现流式加密/导出。不会自动删除历史备份或业务数据。

计划在最终托管凭据具备后启用每日备份，保留最近 7 日和最近 4 周；每次发布/迁移前额外备份，定期隔离恢复验证。**当前只有已验收的一次性备份，自动备份尚未启用**。不能把平台自带短期恢复窗口代替独立备份，也不能把此操作说明当作正在运行的定时任务。

## 本次已完成的真实云数据恢复

2026-11-06：从现有 Railway 私有 Console 导出，下载到本地、加密，再恢复到独立新目录。快照包括 1 个验收账号、1 份未发布草稿、2 张图片；会话为 0、订单为 0。隔离 API 验证原账号 ID、草稿 ID 和两张图片字节 SHA 均通过。只在恢复副本创建短期验证会话，并在验证结束后清除；未修改云端账号或订单，未公开备份内容。

加密文件 SHA-256：`656ce9d5843eefc7e9abba711aaa59734d94fc4c01b59c0c63de1c8a03e3319e`。密钥路径仅在本地交付记录保存，不在公共仓库保存。
