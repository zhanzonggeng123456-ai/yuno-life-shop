# YUNO 独立公网后端：免费试用部署记录

用户约束：只用免费方案，不开付费服务，不影响 Nino。
本配置属于独立 yuno-life-shop 仓库，不读取或修改 Nino 配置、域名、数据库、部署或工具链。

## 当前状态（2026-11-06，America/New_York）

已部署，公网 HTTPS 地址：**https://yuno-life-shop-production.up.railway.app**。
手机已保存此公网地址，本地 YUNO 的端口 8000 服务已经停止。
管理控制台仍为私有项目，公网只开放 App API 和商品图片。

| 资源 | 实际配置 |
| --- | --- |
| Railway 计划 | Trial，页面显示 30 days or $5.00 left；未开付费计划 |
| 项目 | yuno-life-shop |
| Project ID | 2ae0f561-fe76-4e27-8df1-92a3feca0339 |
| 服务 | yuno-life-shop |
| Service ID | 6b781eab-5770-4237-8e6d-9f777d90cd6f |
| 环境 | production（独立环境） |
| 区域/实例 | US East / 1 replica / 1 worker |
| 持久卷 | yuno-life-shop-volume，免费档 0.5GB，挂载 /data |
| Volume ID | b9db08f9-7665-484b-a80d-491b85f2d279 |
| 监听与公网目标端口 | PORT=8000 / 8000 |
| 健康检查 | /healthz |
| Serverless | 已开启 |
| 后端源提交 | 872e5e9e8454e9408c9ef2a44e8da306b589be65 |
| 最后一次重建部署 | cf5cf980-ed40-4f54-a0b6-83f9965af128，Active / Deployment successful |

### 已实际验证

- 公网 HTTPS `/healthz` 与 `/api/v1/config` 返回 200；JPY、最多 10 图、三项服务、模拟支付/配送标记正确。
- 云端注册随机临时账号，上传两张生成的测试图片，形成私有草稿；未创建公开假商品、价格或订单。
- 从部署 02cb74ed-7933-4447-876a-984fab2fec32 重建为 cf5cf980-ed40-4f54-a0b6-83f9965af128 后，
  同一账号、草稿和两张图片的 SHA-256 校验均通过。测试会话随后注销，旧 token 已被服务端拒绝。
- 留有一个临时验收账号及未发布草稿；不计入公开市场。随机口令未记录，token 不写入文件或日志。
- iQOO 8 安装 0.2.1 (3) 公网版成功；升级保留公网连接，原生市场读取正常。
- 停止已核实的本地 YUNO 进程后，手机在 Wi-Fi 下冷启动仍正常，证明后端不依赖电脑进程。
- 手机关闭 Wi-Fi 后系统显示没有可用移动互联网连接；已恢复原 Wi-Fi，未改漫游/APN等设置。
  按用户要求，换 Wi-Fi/热点/移动数据实测暂缓，**不记为跨网络实测通过**。
- GitHub Railway App 授权已从所有仓库缩小为仅选 yuno-life-shop，独立页面回读确认。
  未给 Nino 仓库管理或写权限；没有修改 Nino 源码、应用、学习数据、部署或域名。
- CLI 的全工作区/账单/SSH 授权已取消，未生成该 CLI 登录凭据。实际部署通过单仓库连接完成。

### Android 交付

- APK：yuno-life-shop-0.2.1-cloud.apk，内部调试签名，包名 com.yunolife.shop。
- 运行代码提交：0f8ca0e72e5ab0b12f91d780f1bf012c5c5bf82b。
- 构建参数：`--release --target-platform android-arm64 --dart-define=YUNO_SERVER=https://yuno-life-shop-production.up.railway.app`。
- APK SHA-256：1042f1e754cd6d2fc703197449589bb27b544ae03255f360632fb41015746f80。
- Flutter analyze 无问题，7 项单元/组件测试通过；此轮仅更新公网提示、URL 输入属性和版本号。
- iOS 源代码共享此界面更新；此轮未重新构建或安装 iPhone 包，不把此前 0.2.0 模拟器记录当成 0.2.1 真机验收。

### 已有回归证据

容器验证提交：6469f665a2ca157e4b57e815d46da00125382010。
108 项后端回归、Docker 构建、无卷拒绝启动、容器重建后的账号/图片持久读取全部通过：
https://github.com/zhanzonggeng123456-ai/yuno-life-shop/actions/runs/42248240186

原平台本地库核对 users/listings/images/orders/oneclick_drafts 均为 0。
未迁移隔离验收库。本地原数据库、上传目录和既有备份保留；云端从空库初始化。

Railway 当前还发布了部分外部网络屏蔽的故障通告；当前客户端成功不能保证所有运营商可达：
https://status.railway.com/incident/QBCLHG1V

## 免费方案边界（2026-11-06 核对官方文档）

- Railway Free 为 $0/月，含每月 $1 资源额度；Free/Trial 可用 0.5GB 持久卷。
- Trial 最长 30 天、一次性 $5 额度；耗尽或到期后转 Free。账号验证可能限制外网访问。
- 免费额度不是无限资源或可用性承诺；不升级、不添加支付方式、不启用任何付费附加项。
- Serverless 空闲后休眠，首次请求可能较慢甚至返回 502；App 可重试连接，不能保证冷启动无等待。
- 官方另有 Trial 卷在额度过期后删除的数据保留规则；部署前须核对账号实际保留期限。
  免费试用不等于可靠的长期数据托管，须定期离线备份。额度或保留期限不满足要求时暂停，不自动转付费。
- Render 免费服务没有持久磁盘，不适合直接托管本项目的 SQLite 和图片，不作为有数据的部署目标。

官方来源：

- https://docs.railway.com/pricing/plans
- https://docs.railway.com/pricing/free-trial
- https://docs.railway.com/volumes/reference
- https://docs.railway.com/deployments/serverless
- https://render.com/docs/free

## Railway 的独立资源设置

1. 新建独立项目 `yuno-life-shop`，仅连接 `zhanzonggeng123456-ai/yuno-life-shop`。
   核对账号属于 Free/Trial，且未开收费订阅。不得选中 Nino 的项目或共享数据卷。
2. 服务源码使用仓库根目录 Dockerfile，启动命令采用镜像自带 CMD。
3. 只创建一个 YUNO 专属持久卷，挂载 `/data`（Free 上限 0.5GB）。
4. 单实例、单 Uvicorn worker；健康检查 `/healthz`；使用平台注入的 `PORT`。
5. 不创建额外数据库、定时任务、付费域名或静态出口 IP。按账号允许开启 Serverless 后重新部署。
6. 生成平台免费 HTTPS 域名，并实测证书、健康检查和接口。不得把临时隧道连回电脑当作完成部署。

镜像默认设置：

| 设置 | 值 |
| --- | --- |
| YUNO_DATA_DIR | /data |
| YUNO_REQUIRE_PERSISTENT_VOLUME | 1 |
| 数据库（自动设置） | /data/db/yuno.db |
| 图片（自动设置） | /data/uploads |
| 实例/worker | 1 / 1 |

未挂持久卷、存储不可写或数据路径指向卷外时，启动会失败，不会静默写入临时容器。
不要将 `YUNO_REQUIRE_PERSISTENT_VOLUME` 改为 0 来绕过线上检查；0 仅供本地测试。
镜像构建只复制 app/deploy/requirements，排除数据库、上传图片、账号配置和整个 mobile 工程。

Railway 已弃用旧 railway.json/railway.toml，新服务不可使用；本准备没有添加过时配置。
后续如启用 IaC，必须先预览变更，只允许创建独立 YUNO 资源，不允许删改既有资源。

## 公网入口与安全范围

云端只开放 `/api/v1/...`、`/uploads/...`、`/healthz`；根路径返回服务 JSON。
HTML 登录、表单后台和 API 文档入口不对公网开放；原本地 `python run.py` 不受影响。
App API 继续强制 Bearer 鉴权和原有角色权限，不接受 Cookie 代替 token。
API 响应不缓存，图片启用 nosniff，维持模拟支付/模拟配送标识。
代理 IP 不做通配信任；实际部署后须核实平台可信代理地址，防止把用户自带转发头当作真实 IP。
当前未接入图片内容审核，不把此免费试用后端标为已完成面向大众的正式运营审核。

## 后续复验与手机切换

1. 公网 HTTPS 下注册临时验收账号，发布照片草稿并确认可读取。
2. 重建容器后核对账号、草稿和图片仍在，确认写在持久卷。
3. 手机个人中心修改为真实 HTTPS 地址；只有实测成功才保存并更新默认地址的安装包。
4. 手机从电脑 Wi-Fi 切到移动数据（或另一个网络）后重启 App，核对注册/登录、市场、图片和订单。
5. 停止本地 YUNO 后端再测一次，证明公网运行不依赖电脑。本步骤只操作已核实的 YUNO 进程。
6. 记录真实 URL、部署版本、额度/保留期限、重启持久性与跨网实测；在完成前保留原局域网连接。

## 回归命令

```sh
python -m pytest tests -q
docker build -t yuno-backend .
docker volume create yuno-backend-data
docker run --name yuno-backend -p 8000:8000 -v yuno-backend-data:/data yuno-backend
```

GitHub 的 Public backend validation 工作流在独立 CI 容器中验证：
无卷拒绝启动、原生鉴权、上传照片、容器重建后的账号/照片持久性。
CI 不部署正式服务、不访问 Nino、不使用或上传真实用户数据。

## 维护交接

当前服务为手动部署，未把源码更新自动发布到线上。后端代码变化时，
先通过 Public backend validation，再在该 YUNO 服务中检查更新/部署最新提交。
不要在 Nino 的项目或数据卷上执行这些操作。

免费试用不是长期可用性保证。额度耗尽、到期或平台网络故障可能导致不可用；
不会因此自动替用户升级、绑卡、购买额度或迁移到付费产品。
本轮未配置付费备份、真实支付、真实物流、商店上架或账户签名。
