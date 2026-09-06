# N3-W R1R4 归档与产品路线调整

日期：2026-09-06
状态：ACTIVE_PRODUCT_ROUTE_DECISION / R1R4_PAUSED_ARCHIVED
执行模式：HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION

## 1. 用户确认的路线决策

用户明确同意：暂停 R1R4 保持 Wi-Fi 关联时的跨信道完成事件诊断，归档至 GitHub，回到普通官方 ESP-NOW 能力上的 Direct / Discovery / Relay 产品工作。无需为继续 R1R4 新增独立测试 AP。

本决策替代 [原产品方向文档](N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md) 中第 5、7、8 节将 controlled off-channel lifecycle 完整验证作为产品修复前置条件的路线。官方能力优先、单跳、Direct-first、bounded discovery、安全身份和不默认实现完整 radio-ownership 状态机等原则继续有效。

暂停不等于实验 PASS，也不等于官方 API 被证明不可用。既有诊断源码、提交、CI 与原始证据保持不变，不删除失败记录，不拼接跨 boot session 的 PASS。

## 2. 两种场景的区别

- 保持关联的跨信道操作：节点仍与信道 1 的 AP 保有 Wi-Fi 关联，临时到信道 6 收发，然后希望返回 1 后原连接仍可继续。关联是逻辑连接状态，不代表离开期间还能同时在两个信道收发。
- 失联后的跨信道发现：节点已不能使用原 Wi-Fi 连接，先尝试最近信道；找不到可信 Relay 时，有界尝试其他允许信道。找到 Relay 后停留在其信道工作；找不到时退避并按策略重试 Direct/Discovery。

第二种是当前产品优先场景。信道 1/6 是诊断参数，不是产品必须写死的信道。无结果后可以先回最近信道重试，但不能假定 AP 永远未换信道。

Wi-Fi 仍有关联但 MQTT/主机不可达是另一种 Direct 不可用情形：不能仅因 MQTT 失败就按“Wi-Fi 已断开”直接切信道，必须明确其策略与驱动操作条件。

## 3. R1R4 evidence 索引与边界

仓库：chrenguo-stack/HomeAssistant
诊断分支：diag/n3w-r1r4-usb-console-evidence-20260905

固定参考 authority：
- Espressif ESP-IDF：735507283d5b2f9fb363a1901172dbd9e847945d
- pioarduino：8de41af2dbb81bc443a8d7986ebd152f82e10bba

最终诊断源码：
[e24d4407ad57e876239747a68b00532235af868f](https://github.com/chrenguo-stack/HomeAssistant/commit/e24d4407ad57e876239747a68b00532235af868f)

最终诊断构建：
[run 34022554815](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/34022554815)
- artifact ID：9986074470
- ZIP SHA256：97ad221dd1e2ed17d2a0b45af08f37f370e1cce1e5677fccf06c67cb09deeab0
- CONTROL binary SHA256：47d340e63b87c3b614fe70611be9f4ea6c80a8346b73a2ef925a53b4f2ca9793
- DUT binary SHA256：a102599a2f4c13c65cff4f95d964cfda3386805df38f5b86bda60a871e4d7de8
- 归档前已独立检查上传 ZIP、全部 13 项内部 SHA256SUMS、角色/USB console 配置。Actions artifact 有保留期；元数据索引不等于永久保存二进制。

Host 等待修正：
[66d234f9b15dbbcb328fe93072ea8755afc6e0d6](https://github.com/chrenguo-stack/HomeAssistant/commit/66d234f9b15dbbcb328fe93072ea8755afc6e0d6)
- 用户/执行器报告：focused 9 passed、host suite 38 passed，Ruff/compileall/diff check PASS，已推送。
- 核心行为：reader 持续落盘；首次观察到 lifecycle 建立唯一窗口；人工确认不延长窗口；summary/fatal/timeout 结束；预存确认文件忽略。
- 前一版完整 diff 的 8 项测试曾由高阶审阅环境直接调用通过。最终 9/38 结果属于执行器报告，不冒充高阶环境重跑。
- Host 提交与最终诊断 binary source 是不同 authority，不能混称已重建。

### 物理结果

01：采集因人工确认窗口耗尽而不完整；没有得到完整 off-channel lifecycle。产品恢复完成。

02：初始关联重试后 baseline PASS，DUT 收到 target probe；CONTROL 最终仍在信道 6，home ACK 未通过。其时 request/cancel driver ID 未正确保存配对。两板 preboot exact restore；CONTROL 产品运行证据完整，DUT 当轮证据部分完整。

03：使用最终诊断固件的一次 RF 运行（此前备份传输失败未进入 RF）。
- DUT request driver ID=1；cancel 使用同一 ID；匹配 ROC_DONE op_id=1/status=WIFI_ROC_FAIL；最终信道 1。
- CONTROL switch request input ID=55、driver ID=1；API 与 ESP-NOW send callback 成功；未观察到匹配 ACTION_TX 完成事件，1200 ms 等待超时；实际信道 6。
- CONTROL raw 出现 HOME_ACK_RX channel=6 seq=66。接收分支未核对/输出 source MAC，不能声明完成帧级来源绑定。
- DUT HOME_ACK API 成功、发送回调 FAIL。不能把此组合简化为“完全没有收到帧”。
- 两板首次 summary 均在后续断开/重启前出现；DUT 与 CONTROL 均有后续新 boot。整份 capture 仍 INCOMPLETE，不改原 manifest。
- 两板恢复日志/元数据记录完整回读与本次备份逐字节一致。产品 raw 分别含原节点身份、持久化状态加载、runtime active、Wi-Fi/MQTT Connected 和连续遥测。
- 后续复位来源 UNKNOWN；不是已证明的无线根因。

03 普通审阅包 SHA256：
b6f62288ec143cce7fe2f07c4f474fa961930bd2693b698e696024a334301a21

首次会话派生索引（执行器报告）：
- CONTROL 原 raw：2641f1e5b806dea6e79552c1fe5e1728e7cc2dbefa3abfcfa42ed6129bc19391；范围 [0,11545)；派生 SHA256 80013df0597a06fb598c86de2ea88393c0de02eb01e349614644814667c4127f
- DUT 原 raw：8de753b17036c45637f04ce24e075fb43cddcfd9045c54e51c39c1f24a24505e；范围 [0,15179)；派生 SHA256 ee635759d9345b4ba0786d3ee97e5c9510013085369dc49ec4930e347e571124

本 GitHub 归档保存决策、证据索引与准确结论；未上传私有完整 flash、凭据或完整 raw 包。不得声称原始二进制证据已全部永久归档到仓库。

## 4. 产品实现方向

1. 已配对节点从 durable state 加载身份与安全状态，通信 runtime 不以“已有 Wi-Fi 关联”作为启动前提。
2. Direct 优先，连接/恢复尝试有界。
3. Relay 节点保持其正常 AP 信道，使用官方普通 ESP-NOW 收发，将原节点数据单跳转发给主机。
4. 失联节点优先搜索最近信道，再有界搜索允许信道，找到可信且具备可用上行的 Relay 后停止扫描。
5. 无候选则退避，重新尝试 Direct/Discovery；不持续无界扫频。
6. 保留身份认证、应用确认、去重、原节点归属及单跳限制。
7. 协调 ESPHome Wi-Fi 正在扫描/连接的阶段与发现窗口，满足固定驱动 API 条件。不要仅删除 wifi_connected guard 或另建完整无线状态机。
8. peer channel=0 只意味着使用本机当前信道，不会自动发现邻居信道或解决信道一致性。
9. 不以 ACTION_TX 事件存在来推定 ESP-NOW wrapper 必然发布该事件；关联状态下的特殊 off-channel 机制不再是本轮产品修复的必经路径。

## 5. 已开始的产品源码检查

检查基线：
dd2b54778f95d5a0b8bd6612bcd1f1db8663facd

文件：
[SimpleProductComponent](https://github.com/chrenguo-stack/HomeAssistant/blob/dd2b54778f95d5a0b8bd6612bcd1f1db8663facd/firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.cpp)

直接观察：
- start_runtime_if_ready_() 在 !wifi_connected() 时返回 false；
- loop() 在 !runtime_ready_ 时调用启动后返回，尚不能进入 runtime_.tick()；
- 启动要求读取有效的 connected channel，再调用 runtime_.start(..., channel)；
- set_radio_channel() 在 Wi-Fi 已连接时只接受当前信道；未连接时才调用 radio_.set_channel()。

结论：已配对节点在 Wi-Fi 覆盖外冷启动的 runtime/discovery 入口问题仍存在。上述源码检查不是新的物理验证。

下一步仅定向检查 runtime_.start 初始路径语义、发现计时与信道 hint、普通 esp_now_send 驱动路径，以及 Wi-Fi 重连协作。产出最小产品补丁设计和必要回归条件，再实施工程验证。

## 6. 下一阶段验收

- 已配对节点无 Wi-Fi 冷启动后可以进入有界发现；
- Direct 失效后找到可信 Relay，原节点遥测到达主机；
- Relay 稳定工作且不会为替别人找信道频繁离开自身 AP；
- 搜索无果时有界退出与退避；
- Direct 恢复后稳定切回，保留身份、去重与单跳约束。

不重开 FC4；本次归档不修改产品固件，不访问板卡、T1、Manager 或 Broker。
