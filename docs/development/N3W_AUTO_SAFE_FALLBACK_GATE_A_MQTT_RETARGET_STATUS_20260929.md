# N3-W auto 安全回退 Gate A 状态记录

日期：2026-09-29  
分支：`fix/n3w-auto-safe-fallback-v1-20260929`

```text
GATE=N3W_AUTO_SAFE_FALLBACK_V1_MQTT_RUNTIME_RETARGET_CAPABILITY
SOURCE_BASE=a363962a118e823f97022a6c398383e9e43fc830
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
ESP_MQTT_SUBMODULE=6af4446a48ea7fa54948edc4e62277ed70abb6e1
SOURCE_ADAPTER_IMPLEMENTED=true
SOURCE_CONTRACT_TEST_ADDED=true
EXACT_ESP32C6_COMPILE_PENDING=false
EXACT_ESP32C6_COMPILE_PASS=true
PR_HEAD_CI_ALL_PASS=true
PR_HEAD_CI_RUN_COUNT=11
RUNTIME_BOUNDED_CANCEL_PROVEN=false
FULL_AUTO_FALLBACK_IMPLEMENTATION_ALLOWED=false
BOARD_ACCESS=false
LIVE_T1_MUTATION=false
MERGE=false
```

## 1. 本 Gate 只回答一个问题

先确认现有 ESPHome / ESP-IDF MQTT 客户端能否在**不改身份和凭据**的前提下，
在同一次开机运行中把 TCP/TLS 连接目标从旧 IP 换到新 IP，并且失败连接可以在既有
Direct 恢复预算内退出。

本 Gate 通过以前，不进入完整 auto discovery + Direct/Relay 状态机接线。

## 2. exact upstream 复核结果

ESPHome 2026.4.3：

- `MQTTClientComponent::set_broker_address()` 只更新上层 `credentials_.address`；
- ESP32 backend 的 `set_server()` 只更新 `host_` / `port_`；
- backend 第一次 `connect()` 后已有 `esp_mqtt_client`，后续单纯改地址再 `connect()` 不会重建；
- `disconnect()` 只是调用 ESP-IDF 的异步断开入口；
- ESPHome 对底层断开原因仍主要暴露为通用断开，不能把所有失败精确分类。

ESP-IDF 5.5.4 对应 esp-mqtt：

- `esp_mqtt_client_set_uri()` 允许运行期更新 URI，并在内部持锁更新 scheme/host/port；
- `esp_mqtt_client_disconnect()` 只设置断开请求并返回，不代表底层已经退出；
- `esp_mqtt_client_reconnect()` 只有进入 `MQTT_STATE_WAIT_RECONNECT` 后才接受；
- `esp_mqtt_client_stop()` 最终等待 `STOPPED_BIT` 使用 `portMAX_DELAY`，不能作为“有界取消”证明；
- 连接阶段本身可能占用 MQTT 内部锁，因此运行期 `set_uri()` 的最坏阻塞时间必须用真实构建和实板测量。

## 3. 本轮最小源码适配

继续复用已有、已经绑定 ESPHome 2026.4.3 精确源码指纹的
`n3w_tls_server_name_patch.py.script`，没有新建第二套 MQTT 模块。

新增能力只做三件事：

1. `n3w_runtime_retarget_server(address, port)`
   - 同步更新 ESPHome 上层目标地址；
   - backend 已初始化时调用 `esp_mqtt_client_set_uri()`；
   - 只改连接位置。
2. `n3w_runtime_request_disconnect()`
   - 只提交异步断开请求。
3. `n3w_runtime_request_reconnect()`
   - backend 进入可重连状态后才成功，用于上层有界轮询。

明确没有修改：

- TLS server name；
- CA；
- MQTT username/password/client_id；
- NODE_ID / SYSTEM_ID；
- durable NVS broker record；
- pairing state；
- peer trust。

也没有使用 `esp_mqtt_client_stop()` 或 destroy 来伪造“已经安全退出”。

## 4. 当前 STOP 点

源码层最小接口、源码合同测试和 ESP32-C6 编译已经通过，但现在还不能称为 Gate A PASS。

下一步顺序：

```text
source-contract test PASS
-> exact ESP32-C6 compile PASS
-> 实板 timing gate PENDING
```

实板 timing gate 至少要测：

- 已连接状态换址；
- 旧 IP 已失败、backend 位于重连等待时换址；
- 旧 IP 为黑洞、仍处于 TCP/TLS 连接尝试时换址；
- 每种情况下 API 调用耗时、旧连接退出耗时、新地址上线耗时；
- 原 TLS 校验名称和原账号保持；
- 没有新增 NVS 写入；
- healthy Relay 整轮 30 秒上限不被突破。

若黑洞连接期间 `set_uri()` 因内部锁长期阻塞，Gate A 判 FAIL，停止完整 auto 回退实现，
改换更底层的有界连接所有权方案，不通过延长 30 秒预算解决。


## 5. PR #516 CI 对齐

```text
PR=516
PR_HEAD=42d8344a7680fc71b4233af4ccd402b0e3d4ad11
WORKFLOW_RUN_COUNT=11
WORKFLOW_SUCCESS_COUNT=11
WORKFLOW_FAILURE_COUNT=0
GREENHOUSE_MANAGER_RUN=36539288878
PHASE4_SOURCE_CONTRACT=PASS
PHASE4_RUNTIME_HOST_TEST=PASS
ESP32C6_CHILD_COMPILE=PASS
ESP32C6_RELAY_COMPILE=PASS
ESP32C6_PHYSICAL_HARNESS_COMPILE=PASS
```

因此 Gate A 已经从“源码可行性”推进到“实板时序验证”。下一步只验证运行中换址和失败连接退出时延，不提前接入完整 auto discovery。
