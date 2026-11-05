# Yuno Life 架构与数据库设计(第一阶段 MVP)

技术栈:Python 3.12 + FastAPI + SQLite + 后端直出响应式网页。
模块化单体,无前端构建步骤,手机浏览器可用。
货币 JPY,时区 Asia/Tokyo(时间戳以东京时间存储)。

## 表结构

- users:邮箱唯一、密码哈希 + 盐、昵称、角色
  (user/collector/operator/appraiser/courier/admin)、电话、地区。
  同一普通用户可同时买卖,无需两个账户。
- sessions:随机 token、用户、30 天过期。
- categories:slug、日/中/英名、attrs_json(属性定义,JSON 可扩展)。
- settings:键值参数。commission_rate(默认 0.10,限 0.07~0.10)、
  regions(地区列表与开放状态)、buyback_params(买断建议参数)、
  delivery_rules(配送分档)。
- listings:卖家(自营为 NULL)、分类、日/中标题与介绍、价格、
  成色、属性 JSON、状态、是否自营、今日特价、折扣价与截止、
  精选、检测记录、地区、尺寸档、重量、DEMO 标记。
- images:商品图片本地文件名。
- offers:商品、买家、金额、状态(pending/accepted/rejected/countered)、
  还价金额。
- messages:商品、买家、发送/接收方、正文。线程键=(商品,买家)。
- orders:买家、卖家(自营为 NULL)、商品、商品金额、佣金、
  运费(可为空 = 需单独报价)、合计、状态、支付凭证、
  幂等键(唯一)、是否自营销售、DEMO 标记。
- order_audit:订单金额变动审计(创建/模拟支付/完成/取消)。
- buybacks:商品、卖家、状态、AI 参考区间下限/上限/可信度/依据、
  平台报价、预约取货时间、验货记录、实际收购成本。
- inventory:自营商品、买断申请、收购成本、附加费用、
  状态(in_stock/sold)。
- expenses:后台登记的经营费用(用于利润统计)。

## 核心状态机

订单:pending_payment → paid → completed;pending_payment/paid → cancelled。
下单时商品 reserved;模拟支付后商品 sold;取消后商品恢复 active。
自营商品售出完成时,对应库存同步 sold。

买断:submitted → estimated → reviewing → quoted → accepted →
pickup_scheduled → inspected → paid → completed;
submitted/estimated/reviewing/quoted → rejected。
收购付款一步同时完成:原商品 sold、新平台自营商品上架、
库存记录(成本 = 报价)、买断 completed。

议价:pending → accepted(生成订单)/rejected/countered;
countered → accepted(按还价生成订单)。

## 关键业务规则实现位置

- 佣金:business.commission_rate() 读 settings,钳制 0.07~0.10;
  自营售出佣金 0;买家合计 = 商品价 + 运费,佣金由卖家侧承担。
- 配送:business.delivery_fee()。S=150 / M=200 / L=250 日元;
  重量 >20kg 升一档;>30kg 或 XL(大型家具/冰箱/洗衣机等)单独报价,
  不生成标准运费订单;未开放地区不承诺配送;地区距离附加费来自配置。
- 买断报价:绝非固定比例。后台 buyback_params 只是建议区间的输入
  (品类因子 - 库存惩罚),最终报价由运营人工输入;平台可拒绝。
- AI 辅助:business.local_ai_assist() + price_reference()。
  >=3 笔同类真实成交才给成交中位数 ±20% 区间;否则用在售挂牌价范围
  并标注“挂牌价、不是成交价”;两者皆无则不给价格、明说暂无样本。
- 经营统计:business.stats()。GMV = 已支付/已完成订单商品金额合计;
  自营销售额与 C2C 交易额分列;佣金收入仅 C2C;自营毛利 = 自营销售额
  - 已售库存成本;经营利润 = 佣金收入 + 自营毛利 - 费用;
  净利润本阶段 = 经营利润(税金未计,另列)。

## 第二、三阶段新增表结构

- auctions:商品(唯一)、起拍价、保留价、最小加价、一口价、
开始/结束时间、保证金要求与金额、状态(active/ended_sold/ended_unsold)。
- bids:拍卖、出价人、出价金额、代理上限(proxy_max)。
- deposits:拍卖、出价人、保证金金额、状态(held,模拟托管)。
- reviews:订单、评价人/被评价人、评分 1~5、内容;每订单每方向限 1 条。
- listing_follows:用户、商品(唯一约束),用于行情关注数与热门榜。
- deliveries:订单、类型(buyer_delivery/seller_pickup)、配送员、
预约时间、状态(requested/assigned/picked_up/delivered/confirmed)、
取货/交付照片文件名。
- service_orders:用户、关联商品/买断申请、服务类型、小时数/件数、
单价、应收金额、状态(requested/confirmed/in_progress/completed/cancelled)。
服务目录与单价以代码常量 FINAL_SERVICE_PRICES 为准(仅三项:家居清洁 1500 日元/小时、小件搬运 500 日元/趟、本地配送预约 150 日元/趟起),settings 旧值不影响展示与计价。
- refunds:订单、申请人、原因、证据、状态(requested/decided)、
裁决、裁决人、裁决说明;批准后订单状态变为 refunded 并记账。
- disputes:订单、举报人、原因、状态(open/decided)、裁决、裁决人、说明。
- hv_reviews:商品(唯一)、身份验证标记、鉴定状态(pending/approved/rejected)、
鉴定说明、审核人。手表/钱币/古董且 >=100000 日元发布时自动建档。
- payment_intents:订单、服务商(mock/licensed)、凭证号、分账明细
(卖家应收/佣金/运费)、状态、幂等键(唯一)。
- audit_log:高风险操作审计(退款裁决、争议裁决、高价值审核、
调价批准、预警确认)。
- alerts:异常预警(类型/对象/详情/级别/状态)。
- price_suggestions:自营调价建议(商品/建议价/原因/状态/决策人),
运营确认后才改价。

## 第二、三阶段核心状态机与规则

拍卖:出价 >= 当前价 + 最小加价(首拍 >= 起拍价);代理出价当前价 =
第二高代理上限 + 最小加价(上限为最高代理上限,平局先出价者领先);
结束前 300 秒内出价,结束时间延长 300 秒;保证金(模拟)未交者出价被拒;
结算时最高价 >= 保留价 -> 复用 create_order 生成待付款订单,
否则流拍(商品恢复在售);一口价直接按一口价生成订单。
买断状态机修正:无样本提交状态 submitted 此前只能先到 estimated 但无
对应入口(死状态),现允许 submitted 直接进入 reviewing,与界面一致。
配送:requested → assigned → picked_up → delivered → confirmed;
取货/交付可附照片(本地存储)。
服务:requested → confirmed → in_progress → completed;与买断同笔结算时
页面分项列示应收、买断应付与抵扣净额。
行情:只统计 demo=0 且 status 为 paid/completed 的真实订单;挂牌价
(在售商品)与成交价分开展示;样本 <10 笔标注样本较少,0 笔标注暂无样本。
利润:营业额 = GMV + 服务收入;经营利润 = 佣金收入 + 自营毛利 +
服务收入 - 已批准退款 - 费用;净利润本阶段 = 经营利润(税金未计,另列)。
Agent:全部本地启发式,输出均为建议;调价建议须运营确认才生效,
争议/退款裁决须运营人工确认,均写入 audit_log。

## AI 一键链路(拍照/上传 -> 一键识别 -> 一键上架)

- oneclick_drafts:用户、照片、商品名、补充描述、成色、期望价、
识别 JSON、草稿 JSON、鉴定 JSON、估价 JSON、状态
(uploaded/recognized/published)、关联商品。草稿只归属本人,
无关用户读/识别/发布一律 403(测试覆盖)。
- 识别(app/oneclick.py recognize):关键词品牌/材质/成色模式 +
品类关键词 + 本地历史数据;每项建议含字段/值/可信度/依据/
is_guess=True,界面原样标注"推测·可修改"。
- 鉴定(appraise):成色等级 + 真伪风险等级(low/medium/high)与风险因素
(手表无附件、钱币无评级机构/真伪未知、古董无来源、高价值品牌未确认);
风险只是"需人工多看一眼"的程度,不是真伪判定(is_determination=False)。
高价值(手表/钱币/古董且 >=100000 日元)自动进 hv_reviews 复核队列,
通过前购买/出价/拍卖均被拦截;结论与复核记录写入 audit_log。
- 估价(valuation_for):复用 price_reference,只用本地真实订单与挂牌数据;
>=3 笔真实成交取中位数 ±20%,否则用在售挂牌价范围(标注非成交),
皆无则 low/high 为 None 且明确提示缺少可靠成交样本,绝不编价。
- 上架:草稿全部可改,点"一键上架"即用户确认;发布后复用正常商品、
订单、库存流程,照片转为商品图片;高价值商品同步写入 appraisal_queued
审计。真实视觉模型仅 real_vision_assist() 占位,默认关闭。

## 权限矩阵(服务端强制校验)

- 普通用户:自己的商品/订单/议价/买断/消息;无关用户操作一律 403。
- 运营(operator):商品上下架、买断审核与报价、订单查看、库存查看。
- 鉴定审核(appraiser):买断验货。
- 管理员(admin):以上全部 + 用户角色变更 + 参数设置 + 费用登记。
- 配送人员(courier):配送任务接单、取货、交付(照片留存)。
- 新功能同样服务端强制校验:拍卖结算/调价批准/退款争议裁决/
高价值审核/预警确认仅运营或鉴定角色;配送状态推进仅运营或配送员;
服务订单详情仅本人或运营可见;无关用户一律 403(测试覆盖)。
