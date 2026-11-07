# iPhone 硬件验收与复现

2026-11-07（纽约），正常 0.4.5（10）Release 在真实 iPhone 16e / iOS 26.5 完成系统键盘注册、原生后置相机拍摄、原生相册选择 HEIF 照片、转换上传、AI 草稿、手动售价和二次确认上架。0.4.6（11）仅追加价格字段双语标签和版本更新，另行完成正常包签名安装、冷启动、版本读回、中文/日文标签和设置恢复检查。不能把 0.4.5 的完整硬件流程改称在 0.4.6 全部重跑。

## 实际结果

| 检查 | 可核对证据（本地 outputs） |
| --- | --- |
| 自动化授权 | 首次超时不是已确认的兼容性故障。官方截图捕获到“为 XCTest 输入 iPhone 密码 / Enable UI Automation”；用户在设备输入后，探针通过。没有读取手机密码、升级 iOS、登录 iCloud 或改变共享签名 |
| 系统键盘 | XCTest 通过系统键盘输入邮箱、随机测试口令、昵称与售价；实际注册成功，隔离数据库存在对应用户；数字键盘值 1000 与最终商品售价一致。不是 Flutter enterText 注入，也不宣称由人手逐键输入 |
| 后置相机 | 真实系统权限提示获允许；原生控件读回 Back Facing，实际快门、拍后确认和 Use Photo 回传均执行。首张偏暗样本移除，摆位后的实物照片保留 |
| 相册与 HEIF | 只选择本轮系统相机新拍的 IMG_0004。系统信息页显示 Apple iPhone 16e、主相机、HEIF、5712×4284；原生 picker 中按对应拍摄时间选取。未选取其他已有照片 |
| 转换与上传 | App 按现有 imageQuality/maxWidth 配置导入，后端两张 JPEG 均由 ImageIO 实际解码为 2400×1800，并记录文件大小和 SHA-256。证明 HEIF 来源导入转换可用，不声称原始 HEIF 字节被保留上传 |
| 草稿与上架 | draft 1 为 published；listing 1 为 active、售价 1000，images 表存在两张对应图片。全部位于独立硬件验收库，不在正常 8002 数据库 |
| 清理与恢复 | 硬件账号远端退出后 sessions 为 0。0.4.6 恢复中文、访客和正常 8002，读取持久化设置并冷启动实际首页核对；测试 Runner 卸载、8003 停止。系统相册保留本轮新拍样本，没有改删原有照片 |

结构化摘要为 `outputs/hardware-acceptance-proof.json`，上传解码摘要为 `hardware-upload-proof.json`，设置恢复摘要为 `ios-0.4.6-restored-settings.json`。逐步 UI 结果与截图在 `outputs/hardware-control/`。原始 XCTest 输入动作可能包含随机测试凭据，因此已保留脱敏的活动树、诊断日志和通过摘要，移除含该输入的临时原始归档与口令文件；见 `hardware-credential-cleanup.json`。这些仅是可丢弃测试账号，没有使用真实用户口令。

## 官方 XCTest 工具

`mobile/tool/hardware_probe/create.rb` 生成独立 UI 测试工程，不把正常 Runner 设为构建依赖。默认只读探针等待实际 App 按钮出现再保存界面；加 `--control` 使用 `Control.swift` 的 XCTest 操作循环。操作和结果经测试 Runner 自己的 Documents 文件交换，不开网络监听、不修改交付 App、不依赖 iPhone 镜像。已有开发签名即可构建，不使用 `-allowProvisioningUpdates`。

```sh
# 先只读检查目标设备占用；不要终止其他 App 的测试任务。
# YUNO_DEVELOPMENT_TEAM / YUNO_TEST_UDID 使用现有团队与目标设备。
ruby mobile/tool/hardware_probe/create.rb outputs/hardware-repro --control
xcodebuild build-for-testing \
  -project outputs/hardware-repro/YunoHardwareProbe.xcodeproj \
  -scheme YunoHardwareProbe -configuration Debug \
  -destination "id=$YUNO_TEST_UDID" \
  -derivedDataPath outputs/hardware-repro-derived
xcodebuild test-without-building \
  -project outputs/hardware-repro/YunoHardwareProbe.xcodeproj \
  -scheme YunoHardwareProbe -configuration Debug \
  -destination "id=$YUNO_TEST_UDID" \
  -derivedDataPath outputs/hardware-repro-derived \
  -resultBundlePath outputs/hardware-repro.xcresult
```

测试开始后，用另一个终端发送 JSON 文件。每个操作必须使用新 id；命令包含 `op`，可选 `type`、`label`、`contains`、`index`、`value`。支持 dump、activate、tap、press、swipeUp、swipeDown、type、typeFocused、replace、clear、tapPoint、finish。只允许 Yuno、系统相机、照片和 SpringBoard；坐标必须来自已观察到的当前界面。密码字段应按实际 accessibility 类型定位；URL 替换使用系统 Command-A，并核对返回的完整 fieldValue，不能按截断的 debug 文本推算删除长度。

```sh
python3 mobile/tool/hardware_probe/send.py outputs/command.json \
  --device "$YUNO_TEST_UDID" --output-dir outputs/hardware-repro-receipts
```

工具返回 ok 仅表示操作已执行，不能代替结果断言。必须继续核对实际截图、字段值、图片解码和数据库终态；测试结束前退出测试账号，恢复最新正常包、原语言及正常服务器，再发送 finish、卸载测试 Runner 和停止隔离后端。新测试始终使用新的数字运行编号与独立数据库/上传目录。
