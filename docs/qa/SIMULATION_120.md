# YUNO LIFE SHOP 120 轮模拟测试记录

2026-11-07（美国东部时间）。业务代码基线为 `f528017b805168fdaf2542df648a8b14a2741b7b`。执行使用专用分支 `codex/simulation-120`，每轮连接独立测试数据库，测试图片和成交历史均由夹具生成，支付与配送均为模拟。

| 验证范围 | 结果 | 执行记录 |
| --- | --- | --- |
| 后端完整回归 | 120/120 轮通过。SQLite 和 libSQL 各 60 轮，累计 14,400 项，零失败、零跳过。 | [GitHub Actions](https://github.com/zhanzonggeng123456-ai/yuno-life-shop/actions/runs/42339272024) |
| Flutter 交易流程 | 120/120 轮通过。每轮 14 组场景，累计 1,680 组。 | [GitHub Actions](https://github.com/zhanzonggeng123456-ai/yuno-life-shop/actions/runs/42339699268) |
| Flutter 组件检查 | 120/120 轮通过。每轮 7 项，累计 840 项。 | [GitHub Actions](https://github.com/zhanzonggeng123456-ai/yuno-life-shop/actions/runs/42339699268) |
| Android 和 iPhone 模拟器 | 两个平台各独立跑完并通过 14 组交易场景。 | [GitHub Actions](https://github.com/zhanzonggeng123456-ai/yuno-life-shop/actions/runs/42339867814) |

后端套件覆盖订单状态、议价、竞拍、买断、配送、服务、退款争议、权限、身份验证、输入校验、AI、行情、持久存储、备份和恢复。客户端 14 组覆盖注册及会话、十图编辑及 AI 草稿、发布、消息和收藏、购买到评价、三项服务、买断、竞拍、退款与争议、议价和取消、后台操作及越权拒绝、并发请求、行情双榜、导航及语言。

并发用例向同一件商品同时提交两笔购买，只有一笔成功。胜出的订单并发重试八次模拟支付，只产生一条支付审计记录。行情用已知成交历史验证涨跌排序、挂牌价排除和单笔成交样本排除。先导测试发现按钮在页面过渡时被脚本过早点击，增加等待按钮可点击的判断后，正式 120 轮通过。

本次验收范围为模拟数据与模拟环境。Android 和 iPhone 使用系统模拟器，120 轮 Flutter 批测使用桌面测试引擎。相机和相册通过生成的图片验证应用流程。测试结果覆盖上述用例，真实收款、物流和实体设备相机属于独立验收场景。

逐轮核对见 [轮次明细](simulation-120.json)。GitHub Actions 中可在 `main` 手动选择后端批测、Flutter 批测或 Android 与 iPhone 模拟器工作流。

本机后端复跑时，先安装 README 中列出的三份依赖，再从仓库根目录运行以下命令。输出路径使用新的目录。

```sh
python scripts/simulation/run_backend.py . --rounds 120 --workers 2 --output ../yuno-backend-qa
```

本机 Flutter 模拟可从 `mobile/` 运行以下命令，默认各执行一轮。交易测试会自行启动及关闭回环验收服务。

```sh
flutter test simulation_test/widgets_test.dart
PYTHONPATH="$(cd ../scripts/simulation/guard && pwd)" flutter test simulation_test/trading_test.dart --dart-define=YUNO_SIM_PYTHON="$(command -v python)"
```
