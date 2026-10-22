# N3-W auto 安全回退源码修复执行计划

日期：2026-09-29  
状态：执行中  
修复分支：`fix/n3w-auto-safe-fallback-v1-20260929`

```text
TASK=N3W_AUTO_SAFE_FALLBACK_V1_SOURCE_REPAIR_20260929
BRANCH_BASE=a363962a118e823f97022a6c398383e9e43fc830
ASTRA_DESIGN_BLOB=3e5605f061a88091645e67215e76be6bd2ce0cc1
ASTRA_DESIGN_SOURCE_BASE=60c05ada52c48a58243f666b3e631fd228c53df4
PRODUCT_SOURCE_DRIFT_SINCE_ASTRA_BASE=false
MAIN_DOC_DRIFT_SINCE_ASTRA_BASE=true
BOARD_ACCESS=false
LIVE_T1_MUTATION=false
MERGE=false
```

## 1. 当前重新绑定结论

Astra 设计基线到当前 main 一共前进 122 个提交。对比结果显示，和本修复直接相关的
`firmware/esphome_rc/components/greenhouse_n3w_core/` 产品源码没有变化；主要变化在 current-state、known-failures 等文档和其他工作流。因此本轮可以在当前 main 上重新绑定 Astra 方案，不需要先重做产品架构设计。

当前固定工具链仍为：

- ESPHome 2026.4.3；
- ESP-IDF 5.5.4；
- ESP32-C6；
- 现有 TLS server-name generated-source overlay 继续作为版本绑定入口。

## 2. 不变的安全边界

本修复必须同时满足：

1. 不清空配对；
2. 不改 NODE_ID、SYSTEM_ID、peer trust、MQTT 用户名/密码/client_id；
3. 不修改 CA 和 TLS 校验名称；
4. 不把 discovery response 当认证；
5. 新地址第一版只保存在 RAM；
6. 不新增永久 NVS 写入；
7. 不调用 ordinary pairing / hello / begin 作为地址恢复手段；
8. 健康 Relay 的整轮 Direct 探测仍不得超过 30 秒；
9. 无 Relay 的整轮恢复仍不得超过 120 秒，Wi-Fi 阶段 85 秒、MQTT 阶段 25 秒、确认阶段 5 秒；
10. 换址失败必须回到既有 Relay/退避路径，不能用整板重启掩盖失败。

## 3. 分阶段执行

### Gate A：最小 MQTT 换址能力

先验证 ESPHome 2026.4.3 + ESP-IDF 5.5.4 的实际 MQTT backend。

已重新核对上游源码：

- `set_broker_address()` 只改 ESPHome 上层字段；
- backend 首次 `initialize_()` 后不会因为再次 `set_server()` 自动重建 client；
- `esp_mqtt_client_stop()` 内部等待 `STOPPED_BIT`，使用 `portMAX_DELAY`，不能直接拿它证明“有界取消”；
- `esp_mqtt_set_config()` 可更新活动 client 的配置；
- `esp_mqtt_client_disconnect()` 是异步请求，返回本身不等于连接已结束。

因此 Gate A 不允许把“disable/enable”或“stop 返回前一直等”当成完成。

实现目标：

- 在现有 exact generated-source overlay 中增加最小地址重定向适配；
- 保留原 TLS 名称、CA、账号、client_id、LWT、keepalive、clean-session；
- API 必须有明确的 request / in-progress / connected / failed / timeout 语义；
- 旧轮回调不得提交新轮结果；
- 若无法在既有预算内证明底层退出，则 fail closed，不继续做完整 auto 回退。

停止点：源码合同测试 + ESP32-C6 exact compile 通过后，才进入 Gate B。

### Gate B：发现能力与配对流程解耦

把 discovery query / response 解析中可复用的纯协议逻辑抽到现有公共职责范围内，
但不让已配对节点进入 `SimplePairingClient::run_once()`。

第一版必须：

- 每轮新 request_id + nonce；
- 收集而不是只取第一个 response；
- 最多解析 8 个报文、保留 3 个去重候选、最多尝试 2 个地址；
- 校验 system_id、IPv4 单播、同子网、来源 IP 与 advertised host 一致；
- Broker 端口继续取 durable trusted broker record；
- discovery response 不得覆盖 CA、TLS 名称或凭据。

停止点：纯协议和过滤测试全部通过。

### Gate C：接入 Direct 恢复状态机

只在以下条件进入：

- provisioned state 完整；
- Wi-Fi 有 IPv4；
- 非 pairing / repair / retirement；
- 当前 Direct recovery 调度允许；
- MQTT 持续失败满足门槛；
- 父级 deadline 仍留有安全退出余量。

恢复顺序：

```text
原 broker_host 失败
-> 有界 discovery
-> 候选筛选
-> 请求 MQTT 地址切换
-> 原 CA + 原 TLS 名称验证
-> 原账号登录
-> MQTT connected
-> 既有 Direct confirm
-> commit Direct
```

任何一步失败：

```text
丢弃临时候选
-> 保留 durable broker_host 和全部身份
-> 恢复 Relay 或进入既有退避
```

### Gate D：测试收口

测试按 Astra 48 项矩阵分四层执行：

1. 纯函数 / 协议；
2. MQTT 地址切换适配；
3. Direct/Relay 状态机与截止时间；
4. ESP32-C6 exact compile。

重点阻断项：

- 旧回调污染新 attempt；
- 自动重连偷偷回旧 IP；
- TLS 名称被新 IP 覆盖；
- candidate 失败后写 NVS；
- healthy Relay 30 秒被延长；
- discovery/cleanup 另开独立预算；
- ordinary pairing/KF-099 回归；
- Option-B telemetry ownership 回归。

### Gate E：PR 与独立源码复核

完成源码和仓库 CI 后创建 Draft PR。PR 在物理验证前保持 Draft，不声明 B3 CLOSED。

### Gate F：物理最小验证

该 Gate 需要真实 ESP32-C6 与可控 T1/Broker。

最小验证顺序：

1. 旧地址正常 Direct；
2. T1 地址改变，身份、证书、账号不变；
3. 旧地址连接失败；
4. 节点在同一 boot 中 discovery 到新地址；
5. 新地址通过原 TLS 身份和原账号；
6. Manager-visible telemetry 恢复；
7. healthy Relay 场景整轮 Direct probe 不超过 30 秒；
8. 候选不可达时能按时退出并恢复 Relay；
9. 断电后 RAM 地址消失，下一 boot 可再次 discovery；
10. durable pairing / broker record / credential generation 前后不变。

物理 Gate 未完成前：

```text
SOURCE_REPAIR_COMPLETE可以成立
PHYSICAL_ACCEPTANCE_COMPLETE=false
B3_CLOSED=false
MERGE=false
```
