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
READONLY_T1_BOARD_PREFLIGHT=PASS
BOARD_B_PRODUCT_PROVISIONING_ASSUMED=false
GATE_A_MQTT_PROFILE=EPHEMERAL_ISOLATED_TLS_LAB
ISOLATED_FIXTURE_SOURCE_REPAIR=IMPLEMENTED
ISOLATED_FIXTURE_CI_PENDING=false
ISOLATED_FIXTURE_CI=PASS
PRIVATE_BUILD_EXECUTOR_CI=PASS
PRIVATE_BUILD_LOCAL_FAILURE_1_ROOT_CAUSE=INTEL_MACOS_CBOR2_6_NO_PREBUILT_X86_64_WHEEL_AND_NO_RUST
PRIVATE_BUILD_LOCAL_FAILURE_1_SOURCE_DEFECT=false
PRIVATE_BUILD_LOCAL_FAILURE_1_REPAIR=REUSE_EXISTING_EXACT_ESPHOME_FIRST
PRIVATE_BUILD_LOCAL=PASS
PRIVATE_BUILD_APPLICATION_SHA256=77b0fd6a98c3e837d3543eebdd30b86354790847d0c78cdab7e96f0d7d66a8ad
PRIVATE_BUILD_OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
PRIVATE_BUILD_CA_CERT_SHA256=66ca928aaab07eaef6aebf0a7dec9b8a0e0fac9a9d719f4e1354ea575eed0a66
PRIVATE_BUILD_SERVER_CERT_SHA256=c33bdac940da24cff4de772ff0478f0f069a3ab956dc03b1557738c4f640af4e
PRIVATE_BUILD_SERVER_KEY_SHA256=29ee45ca617fb5e4e854081e77a9ae4c468c3b07fb1d206cb0d61d86d8cbee61
PRIVATE_BUILD_ESPHOME_SOURCE=existing_exact_cli
T1_ISOLATED_LAB_EXECUTOR=IMPLEMENTED
T1_ISOLATED_LAB_EXECUTOR_CI_PENDING=false
T1_ISOLATED_LAB_EXECUTOR_CI=PASS
T1_ISOLATED_LAB_PREFLIGHT=PASS
T1_ISOLATED_LAB_PORT_18883_FREE=true
T1_ISOLATED_LAB_LIVE_ALIAS_UNASSIGNED=true
T1_ISOLATED_LAB_BLACKHOLE_UNASSIGNED=true
T1_ISOLATED_LAB_BROKER_RESTART_COUNT=0
T1_ISOLATED_LAB_MANAGER_RESTART_COUNT=0
T1_ISOLATED_LAB_MUTATION=false
BOARD_B_GATE_A_WRITE_EXECUTOR=IMPLEMENTED
BOARD_B_GATE_A_WRITE_EXECUTOR_CI_PENDING=true
KF099_ROLLBACK_EXECUTOR=IMPLEMENTED
KF099_ROLLBACK_EXECUTOR_CI_PENDING=true
KF099_HISTORICAL_WRITE_AUTH_REPLAY=false
KF099_ROLLBACK_ARTIFACT_AVAILABLE=true
KF099_ROLLBACK_ARTIFACT_ID=10959875986
KF099_ROLLBACK_ARTIFACT_EXPIRES_AT=2026-10-05T08:48:09Z
RUNTIME_BOUNDED_CANCEL_PROVEN=false
FULL_AUTO_FALLBACK_IMPLEMENTATION_ALLOWED=false
BOARD_ACCESS=true
BOARD_FLASH=false
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

## 3.1 实板前提修正

只读预检已经通过，但 KF-099 的既有实板证据表明 Board B 当前处于 pairing WAIT / repair-intent-required 路径，不能假设它持有完整、可直接启动 Direct MQTT 的产品 Broker NVS。

因此 Gate A 已去掉 `runtime_ready()` 前提，并把 MQTT 连接资料改为**测试专用、临时、非持久** profile：

- 产品 pairing/runtime 保持关闭；
- 测试固件只在 RAM 中配置 ESPHome MQTT client；
- TLS server name、CA、用户名、密码、client ID 由私有本地构建输入提供；
- 不读取或覆盖 Board B 的产品 Broker NVS；
- 不使用生产 Broker 节点凭据；
- 不修改生产 Manager / DynSec；
- 实板时使用独立临时 TLS MQTT lab broker。

这样 Gate A 只测当前真正要回答的问题：ESPHome/ESP-IDF MQTT client 在连接中和重连等待中，能否在既有 25 秒预算内完成 runtime retarget。

## 3.2 2026-09-29 本地私有构建失败与修补

首次 Mac 私有构建在安装 ESPHome 依赖时停止，未进入固件编译。Python 3.11 本身正常；失败点是 `cbor2 6.1.4` 在 Intel macOS / CPython 3.11 上没有匹配的预编译 wheel，pip 因而退回源码构建，而该版本从 6.0 起使用 Rust，当前 Mac 没有 Rust toolchain。

这不是 Gate A firmware/source failure，也没有 Board/T1 mutation。

执行器现改为：

1. 优先复用本机已经安装且版本**精确等于 2026.4.3** 的 ESPHome CLI；
2. 其次检查当前 Python module 是否正好是 2026.4.3；
3. 只有没有 exact local ESPHome 时才建立私有 venv；
4. 对 Intel macOS 且没有 Rust 的情况 fail closed，不自动安装持久 Rust toolchain；
5. 私有 venv 路径仍先升级 pip/setuptools/wheel，再安装 exact ESPHome。

## 3.3 私有 exact build 已通过

Mac 本地 exact build 已完成，使用本机现有的 ESPHome 2026.4.3，没有安装 Rust，也没有访问 Board 或修改 T1。

公开记录只保存 source / firmware / TLS 文件哈希，不保存 LAN 地址、MQTT 用户名/密码/client ID、TLS 私钥内容或私有 bundle 路径。

Gate A 现已冻结到本次私有构建的 application / otadata / CA / server cert / server key 哈希。随后新增 T1 isolated lab transaction package：

- `preflight`：只读检查 T1 当前网络、生产 Broker/Manager 连续性、TCP/18883 空闲、live alias / blackhole 仍未占用；
- `activate`：只有得到单次明确授权后，才创建临时 `/run` 私有目录、临时 TLS Mosquitto 18883 和 live alias；
- `cleanup`：只清理带 exact label 的临时容器、exact live alias 和 exact `/run` 目录；
- 生产 Broker、Manager、DynSec、HA、Compose authority、Board B 均不属于该 T1 lab transaction 的修改范围。

## 3.4 Board B exact write gate 已准备

Board B Gate A writer 已加入仓库，但尚未执行。它冻结到本次私有 application / otadata 哈希和 Board B / partition-table identity。

写入范围只允许：

- `0x9000` otadata；
- `0x10000` application。

bootloader、partition table、product NVS 和 full erase 均明确禁止。写入前必须重新做不超过 15 分钟的 read-only Board preflight，并消费一次性授权。

KF-099 rollback artifact 已 fresh 检查，当前仍未过期且 GitHub digest 与冻结 SHA256 一致。历史 KF-099 写入授权不可复用；回退仍需要新的独立授权。

## 3.5 Fresh KF-099 rollback gate 已准备

为了避免复用已经消费的历史 KF-099 写入授权，Gate A 分支新增独立 rollback package。它接受同一个冻结 rollback artifact，但使用新的 preflight schema 和新的单次授权 token。

回退写入范围同样只允许 `0x9000` 与 `0x10000`。回退后的正确基线定义为已知的 KF-099 pairing WAIT / `repair_intent_required`，不把“正常 Direct MQTT”误当作回退成功条件。

## 3.6 T1 isolated-lab fresh read-only preflight 已通过

2026-09-30 fresh preflight 证明：

- TCP/18883 当前空闲；
- live alias 当前未分配；
- blackhole 地址当前未分配；
- production Broker restart_count=0；
- Manager restart_count=0；
- 本轮没有 T1 mutation；
- 没有 production Broker mutation；
- 没有 Board access。

公共记录不保存具体 LAN 地址。

因此仓库和只读运行时前提均已满足。下一步首次进入 live T1 mutation：启动临时 TLS Mosquitto 18883 并添加绑定的临时 live alias。该动作必须使用一次性明确授权。

## 4. 当前 STOP 点

源码层最小接口、源码合同测试和 ESP32-C6 编译已经通过，但现在还不能称为 Gate A PASS。

下一步顺序：

```text
source-contract test PASS
-> exact ESP32-C6 compile PASS
-> private exact build PASS
-> T1 isolated-lab package CI PENDING
-> fresh T1 read-only lab preflight PASS
-> explicit T1 mutation authorization PENDING
-> Board B exact write package CI PENDING
-> Board B read-only preflight PENDING
-> Board B write authorization PENDING
-> 实板 timing gate PENDING
-> fresh KF099 rollback preflight PENDING
-> fresh KF099 rollback write authorization PENDING
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
PR_HEAD=292cae83e5f064dc6106ae5b7f3a8e51163fa50b
WORKFLOW_RUN_COUNT=11
WORKFLOW_SUCCESS_COUNT=11
WORKFLOW_FAILURE_COUNT=0
GREENHOUSE_MANAGER_RUN=36569554113
GATE_A_EXECUTION_PACKAGE_CONTRACTS=PASS
PHASE4_SOURCE_CONTRACT=PASS
PHASE4_RUNTIME_HOST_TEST=PASS
ESP32C6_CHILD_COMPILE=PASS
ESP32C6_RELAY_COMPILE=PASS
ESP32C6_PHYSICAL_HARNESS_COMPILE=PASS
GATE_A_FIXTURE_COMPILE=PASS
PRIVATE_BUILD_EXECUTOR_SOURCE_HEAD=8210cf7b53e9ec934d145f1c15e9619579c923be
PRIVATE_BUILD_EXECUTOR_SOURCE_TREE=5d3e6ad7151938ffa7ac23b2b6af6663bcd10c7c
PRIVATE_BUILD_EXECUTOR_BLOB=819943d636d0ae095782cdc373448783ad143008
```

因此 Gate A 已经从“源码可行性”推进到“私有 exact build -> 实板时序验证”。下一步先在 Mac 本地生成不进入公共仓库的 exact Gate A firmware + 临时 TLS/MQTT lab bundle；该构建步骤不访问 Board、不修改 T1。构建成功后，再根据生成的私有 manifest 准备 T1 临时 lab 激活与 Board B 单次写入 gate。
