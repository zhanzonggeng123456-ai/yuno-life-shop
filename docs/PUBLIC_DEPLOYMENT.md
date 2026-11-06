# YUNO 独立公网后端：免费试用准备

用户约束：只用免费方案，不开付费服务，不影响 Nino。
本配置属于独立 yuno-life-shop 仓库，不读取或修改 Nino 配置、域名、数据库、部署或工具链。

## 当前状态

已准备并验证独立 Docker 后端、持久存储启动检查、App 专用公网入口及容器重建持久性测试。

验证提交：6469f665a2ca157e4b57e815d46da00125382010。
GitHub CI 全部通过：108 项后端回归、Docker 构建、无卷拒绝启动、
创建临时账号/照片草稿，以及容器重建后账号、草稿和图片持久读取。
运行记录：https://github.com/zhanzonggeng123456-ai/yuno-life-shop/actions/runs/42248240186

尚未创建实际托管服务、绑定公网地址或修改手机连接，不能据此声称已离开电脑可用。
需要先在 Railway 登录，并核实账号当前的免费额度、验证状态和资源限制。

本地原平台核对：users/listings/images/orders/oneclick_drafts 均为 0。
隔离验收数据不迁移；本地数据库和上传目录继续保留。云端可初始化空库，无需传输本地私人数据库。

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

## 上线后的验收与手机切换

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
