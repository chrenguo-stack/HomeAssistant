# 温室环境监测系统（ESP32-C6）
# N3-W FC-3 Three-board Physical Execution Preclaim

版本：V1.0  
日期：2026-08-19  
范围：N3-W Final Closure / FC-3 only  
状态：FC-3 authorization-preparation terminal package

---

## 1. 目的与边界

FC-3 只负责冻结最终三板产品 E2E 的授权前执行包、测试对象、artifact、验收 oracle、evidence contract、fail-closed 规则和新的 authorization 候选标识。

FC-3 不执行任何三板物理测试；不访问板卡运行时；不打开串口；不 Flash / erase；不进行 RF 故障注入；不修改生产 Broker、Manager 或 Home Assistant；不进入 N3-L；不把 PR #324 标记 Ready；不合并任何产品 PR。

本阶段遵循 `ONE_BOUNDARY_ONE_VALIDATION`：云端/source/artifact/preclaim contract 与后续 FC-4 物理执行严格分离。

---

## 2. FC-3A — current exact baseline binding

截至本 FC-3 cloud-side preclaim：

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PR324_STATE=OPEN
PR324_DRAFT=true
PR324_MERGED=false
PR324_MERGEABLE=true
PR324_HEAD=147ead29b5963150e17d582492b148854b0250b4
PR324_BASE=ab0adabe7d66c389f0496cf6d8386832c67debfe
FINAL_SOURCE_TREE=9c62b1c87549120e0b8f53b0bd949ce5b00a0569
FINAL_FIRMWARE_TREE=0bc639f301dae9964061bd2b7b72a21ef2a88341
```

FC-2 evidence lineage：

```text
FC1_CLOSURE_COMMIT=1371e4caa21f8a90cca4f2025b5d9eaa7c4176c2
FC2_EVIDENCE_COMMIT=6c7d263c88aba27010e5a4699722ea946efabfd5
FC2_KNOWN_FAILURES_COMMIT=aa37478644092af42aaa2b42a48e51c5e9592e39
FC2_EVIDENCE_FILE=docs/development/N3W_FC2_FINAL_FIRMWARE_ARTIFACT_EVIDENCE_V1.0_20260819.md
```

FC-3 branch 从 `aa37478644092af42aaa2b42a48e51c5e9592e39` 独立建立，不改变 PR #324 产品 HEAD。

---

## 3. FC-3B — unique final firmware artifact contract

三块板在 FC-4 中只能使用同一个 FC-2 frozen generic factory validation image；不得为 A/B/C 生成 role-specific firmware。

```text
TARGET_CONFIG=firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml
TARGET_CONFIG_BLOB=6e40a198c5fcc9f445668da6e78f455a390e991f
TARGET_NAME=gh-n3w-phase4-generic
ESPHOME_VERSION=2026.4.3

FC2_RUN_ID=32214600842
FC2_JOB_ID=95953637621
ARTIFACT_ID=9351968978
ARTIFACT_NAME=N3W-FC2-FINAL-147ead29-20260819
ARTIFACT_SIZE_BYTES=2324996
ARTIFACT_EXPIRED=false
ARTIFACT_ZIP_SHA256=400ef32624ac6af818eb7602140f5468afbecdf842b651aec5d58ad6af08b3a5
PACKAGE_SHA256=f8174bf3bdbed6083aef61a2092ed45fd15056ec7a1a34e586553a31bdf4e2ea

BOOTLOADER_SHA256=a107f538e90357738d011c509e2d80a711e1206ad5ee4338a2400b152654f4f7
PARTITIONS_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
APP_SHA256=fbb6a1b5d2fad984a0f809d422dbe2fcea687eba4eeea7771910bfb530111d81
FACTORY_IMAGE_SHA256=5632712cc9d79fc0633344a7cb58f53c11ff4e0bfa8a6a77391be77171377ab7
```

FC-4 preclaim 必须重新下载/取得 artifact 或其 operator-controlled frozen copy，并重新计算上述 hash；任何一项不一致立即 STOP。

### Generic factory invariants

同一 `factory.bin` 必须保持：

- 不预置 NODE_ID；
- 不预置 SYSTEM_ID；
- 不预置 GATEWAY_ID；
- 不预置 peer MAC / peer identity；
- 不预置 SYSTEM_PEER_KEY / peer key / LMK；
- 不预置用户 Wi-Fi credential；
- 不预置生产或用户 Manager/site binding；
- A/B/C 的角色名称仅为测试标签，不进入 firmware identity；
- late-join C 不允许要求 A/B reflash、repair、手工写入 C 信息。

```text
THREE_BOARDS_SAME_FACTORY_IMAGE_REQUIRED=true
ROLE_SPECIFIC_IMAGE_ALLOWED=false
FACTORY_PREBOUND_NODE_ID=false
FACTORY_PREBOUND_PEER=false
FACTORY_PREBOUND_SITE=false
```

---

## 4. Board object contract

测试对象固定命名：

```text
BOARD_A
BOARD_B
BOARD_C
```

三者必须是相同产品硬件类别：ESP32-C6 / 8MB flash；FC-4 live preclaim 需重新读取/核验实际 silicon/USB identity，且三者必须 distinct。

历史参考绑定只用于帮助 operator 避免拿错旧板，不能冒充 FC-4 live binding：

```text
BOARD_A_PRIOR_USB=/dev/cu.usbmodem14101
BOARD_A_PRIOR_MAC_SHA256=c25b9bc46cf2c4247c607e6cc9ff7536fb22bac5c4e38fe610ca1f176b2f7ca6
BOARD_A_PRIOR_CHIP=ESP32-C6
BOARD_A_PRIOR_REVISION=0.2
BOARD_A_PRIOR_FLASH=8MB

BOARD_B_PRIOR_USB=/dev/cu.usbmodem14201
BOARD_B_PRIOR_MAC_SHA256=de6b31f7d4d166afb8edcce53fe77e8cf3e723676ebac2360a405884dc846108
BOARD_B_PRIOR_CHIP=ESP32-C6
BOARD_B_PRIOR_REVISION=0.2
BOARD_B_PRIOR_FLASH=8MB
```

第三块板 C 尚无历史 frozen identity，因此：

```text
BOARD_C_PRIOR_IDENTITY=NONE
```

FC-3 不访问硬件，所以 live identity 明确保持：

```text
BOARD_A_LIVE_BINDING=NOT_STARTED
BOARD_B_LIVE_BINDING=NOT_STARTED
BOARD_C_LIVE_BINDING=NOT_STARTED
```

FC-4 authorization claim 之前必须完成一次新的 readonly live binding；如果 A/B 历史路径变化，不视为 failure，只以新的 silicon identity/hash 为 authority。

---

## 5. FC-3C — isolated environment contract

FC-4 必须继续运行于独立实验环境，不能访问或修改 production Broker / Manager / Home Assistant。

历史隔离实验环境可作为 operator 识别参考，但必须在 FC-4 preclaim 重新实时绑定：

```text
PRIOR_LAB_MQTT_PORT=18883
PRIOR_LAB_BROKER_IMAGE=eclipse-mosquitto:2.0.22
PRIOR_ANON_CLIENT_ID=lab-board-anon
PRIOR_OBSERVER_USERNAME=gho_lab-observer
```

以上全部是 non-production reference，不得复用为生产 identity。

FC-4 preclaim 必须验证：

1. target LAN/AP 为实验网络；
2. production endpoint 不在有效路由/配置中；
3. Broker / Manager / observer 为 isolated instance；
4. 三板 Wi-Fi 故障与恢复可以由实验 AP/STA 层真实实现；
5. 测试期间不需要重启或修改生产服务；
6. test evidence root 与公开仓库分离，raw private evidence 不上传公开 GitHub。

```text
PRODUCTION_BROKER_MUTATION_ALLOWED=false
PRODUCTION_MANAGER_MUTATION_ALLOWED=false
PRODUCTION_HA_MUTATION_ALLOWED=false
PRODUCTION_ENDPOINT_ACCESS_ALLOWED=false
```

---

## 6. Real Wi-Fi loss / recovery oracle

永久遵守 KF-027：

```text
MQTT_APPLICATION_FAILURE != REAL_STA_WIFI_LOSS
```

### REAL_WIFI_LOSS_PASS 必需条件

某节点只有同时满足以下条件，才能记为真实 Wi-Fi loss：

- STA 实际 disconnected / unassociated；
- Direct IP path 实际不可用；
- 故障不是通过 MQTT client disable、ACL deny、credential rejection、Broker reject、Manager reject 制造；
- firmware 自动从 Direct 路径进入 discovery/relay 流程；
- 不允许 PATH command / manual Relay selection / finite peer grant 作为恢复 authority。

### REAL_WIFI_RECOVERY_PASS 必需条件

- STA association 恢复；
- Direct IP path 恢复；
- firmware 自动返回 Direct；
- NODE_ID 不变化；
- BOOT_ID/boot-session 与 SEQ/canonical high-water 按测试阶段要求连续；
- 不出现 stale relay ownership / canonical rollback。

---

## 7. FC-3D — FC-4 execution package

### 7.1 Proposed fresh authorization

候选 authorization 冻结为：

```text
D1-N3W-FC4-THREE-BOARD-FINAL-PRODUCT-E2E-20260819-01
```

本文件只冻结标识，不构成批准：

```text
FC4_AUTHORIZATION_STATUS=NOT_APPROVED
FC4_AUTHORIZATION_CLAIMED=false
FC4_AUTHORIZATION_CONSUMED=false
```

R5 与旧 S5 授权永久不能用于本执行：

```text
R5_REPLAY=false
R5_AUTHORIZATION_REUSE=false
S5_PRIVATE_PACKAGE_REUSE=false
OLD_PHYSICAL_AUTHORIZATION_REUSE=false
```

### 7.2 Claim boundary

新的 FC-4 authorization 只有在下列 preclaim 全 PASS 后才允许 claim：

- PR #324 exact HEAD still `147ead29...`；
- FC-2 package/artifact hashes 全部一致；
- A/B/C 三板 live identity 已 distinct 绑定；
- 三板 silicon/hardware class 符合；
- isolated network / Broker / Manager 已绑定；
- production route absent；
- operator 确认真实 Wi-Fi loss 方法不会退化为 MQTT/application failure；
- evidence output path 已准备；
- exactly-one fresh authorization 与 execution package self-binding 完整。

任何一项 FAIL / UNKNOWN：

```text
AUTHORIZATION_CLAIMED=false
PHYSICAL_EXECUTION=false
STOP=true
```

一旦 claim 后出现失败，authorization 必须冻结为 `CONSUMED_FAILED`，禁止重放；只能建立新的 successor。

---

## 8. FC-3E — frozen FC-4 state machine

### FC-4A — A/B independent first-use and Direct

- A/B 使用同一个 frozen `factory.bin`；
- 需要 clean first-use state 时，只允许 execution package 明确授权的目标 NVS/flash 操作；
- A、B 独立 setup / registration；
- Manager 自动分配不同 NODE_ID；
- A/B Direct telemetry 均进入 canonical Manager ingress。

PASS 条件：

```text
GENERIC_IDENTICAL_FACTORY_FIRMWARE=PASS
INDEPENDENT_REGISTRATION_A=PASS
INDEPENDENT_REGISTRATION_B=PASS
A_DIRECT_TELEMETRY=PASS
B_DIRECT_TELEMETRY=PASS
```

### FC-4B — B real STA Wi-Fi loss -> Relay

保持 A 正常联网，对 B 实施真实 STA Wi-Fi loss：

- B disconnected/unassociated；
- B Direct IP unavailable；
- B 自动 DISCOVERY；
- B 发现 A 或其他当时合法 Relay；
- 完成长周期 peer authentication / LMK derivation；
- B 进入 RELAY_ACTIVE；
- B telemetry 经 ESP-NOW -> Relay -> canonical Manager ingress；
- 无 PATH / finite grant / manual peer config。

### FC-4C — B real Wi-Fi recovery -> Direct

- 恢复 B STA；
- B 自动重获 Direct IP；
- 自动回 Direct；
- NODE_ID 稳定；
- canonical state 不回退；
- boot/SEQ continuity 满足 frozen oracle。

### FC-4D — late join C

A/B 已是已注册运行节点时加入 C：

- A/B 不 reflash；
- A/B 不 re-pair；
- A/B 不人工录入 C MAC/NODE_ID/key；
- C 使用同一 generic factory image；
- C 独立 first-use / registration；
- Manager 自动分配新且 distinct NODE_ID；
- C Direct telemetry 正常。

### FC-4E — C real Wi-Fi loss -> automatic Relay

- C 真实 STA loss；
- C Direct IP unavailable；
- C 自动 discovery；
- 不人工指定固定 Relay；
- C 自动选择并认证合法 Relay；
- encrypted Relay ingress PASS。

### FC-4F — simultaneous B + C Relay

在至少一个合法 Relay 可联网条件下：

- B/C 同时真实失联；
- B/C 各自 Relay；
- 两个 NODE_ID 不混淆；
- BOOT_ID/SEQ/canonical state 不互相污染；
- Manager canonical high-water 正确。

### FC-4G — multi-Relay failover

必须形成至少两个可被失联节点发现的合法 Relay 候选条件；B 已在 Relay 模式后令当前 Relay 不再可用：

- B 自动退出失效 relay path；
- 重新 discovery；
- 自动认证/切换另一合法 Relay；
- 无 PATH ownership；
- 无 manual Relay selection；
- 无重新配对；
- 无新 finite peer grant。

若现场拓扑无法提供两个真实 Relay 候选，则 FC-4G 不得伪造 PASS，应 fail-closed 退出并重新设计物理拓扑。

### FC-4H — all nodes recover Direct

恢复 A/B/C 正常 Wi-Fi：

- A/B/C 最终全部 Direct；
- NODE_ID 稳定；
- 无 duplicate HA/Manager device identity；
- 无 stale relay ownership；
- 无 canonical rollback。

---

## 9. Required final matrix

FC-4 只有以下全部 PASS 才能形成最终 Three-board PASS：

```text
GENERIC_IDENTICAL_FACTORY_FIRMWARE=PASS
INDEPENDENT_REGISTRATION_A=PASS
INDEPENDENT_REGISTRATION_B=PASS
LATE_REGISTRATION_C=PASS
EXISTING_NODES_NO_REFLASH_ON_C_JOIN=PASS
EXISTING_NODES_NO_REPAIR_ON_C_JOIN=PASS
B_REAL_WIFI_LOSS=PASS
B_DISCONNECTED_DISCOVERY=PASS
B_AUTHENTICATED_RELAY=PASS
B_REAL_WIFI_RECOVERY=PASS
C_REAL_WIFI_LOSS=PASS
C_AUTOMATIC_RELAY_SELECTION=PASS
C_AUTHENTICATED_RELAY=PASS
SIMULTANEOUS_B_C_RELAY=PASS
MULTI_RELAY_FAILOVER=PASS
NO_PATH_AUTHORITY=PASS
NO_FINITE_PEER_GRANT=PASS
NO_MANUAL_PEER_CONFIG=PASS
CANONICAL_STATE_CONTINUITY=PASS
N3W_THREE_BOARD_FINAL_PRODUCT_E2E=PASS
```

任何单项 UNKNOWN / SKIPPED 不得解释为 PASS。

---

## 10. Evidence contract

FC-4 raw evidence 保存在 private evidence root，不上传公开仓库。公开仓库 FC-5 只保存 sanitized terminal summary、exact source/artifact hashes、必要的 non-secret marker count / result 和 regression conclusions。

### 必须采集的证据类型

- A/B/C live physical identity hash + USB binding；
- artifact/package hash re-verification；
- exact flash image binding；
- setup/registration terminal markers；
- Manager assigned NODE_ID mapping（公开材料可 redact）；
- STA association/disassociation/reassociation evidence；
- Direct IP availability/unavailability evidence；
- discovery/authentication/LMK runtime markers；
- ESP-NOW Relay telemetry evidence；
- Manager canonical ingress/high-water evidence；
- path transition Direct -> Relay -> Direct；
- late C registration evidence；
- simultaneous B/C relay evidence；
- relay failover evidence；
- final all-Direct state；
- mutation counters：production=0, old authorization replay=0。

### 禁止 evidence 污染

- source/build/venv 日志不能冒充 runtime evidence；
- MQTT reject 不能冒充 STA loss；
- historical R5 log 不能冒充 FC-4 live proof；
- test harness synthetic status 不能单独覆盖真实 board/Manager evidence。

---

## 11. Execution mutation boundary

FC-4 尚未批准，因此本阶段冻结但不执行以下可能的 physical operations：

- targeted NVS erase / clean first-use preparation；
- exact `factory.bin` Flash / verify；
- controlled reset/boot；
- serial runtime capture；
- isolated Wi-Fi association / disassociation / recovery；
- ESP-NOW RF runtime；
- isolated Broker / Manager test traffic。

生产环境永远不在此 mutation scope。

```text
BOARD_ACCESS=false
USB_RUNTIME_ACCESS=false
SERIAL_OPEN=false
FLASH=false
ERASE=false
RF_EXECUTION=false
PRODUCTION_MUTATION=false
```

---

## 12. FC-4 preclaim expected terminal

真正申请 FC-4 authorization 前，下一次独立 readonly preclaim 必须至少得到：

```text
FC4_PRECLAIM=PASS
PR324_EXACT_HEAD_BINDING=PASS
FC2_ARTIFACT_BINDING=PASS
FACTORY_IMAGE_HASH_BINDING=PASS
BOARD_A_LIVE_BINDING=PASS
BOARD_B_LIVE_BINDING=PASS
BOARD_C_LIVE_BINDING=PASS
A_B_C_DISTINCT=true
HARDWARE_CLASS_BINDING=PASS
ISOLATED_NETWORK_BINDING=PASS
ISOLATED_BROKER_MANAGER_BINDING=PASS
PRODUCTION_ROUTE_ABSENT=PASS
REAL_WIFI_LOSS_ORACLE_FROZEN=true
REAL_WIFI_RECOVERY_ORACLE_FROZEN=true
R5_REPLAY=false
OLD_AUTHORIZATION_REUSE=false
OLD_S5_PRIVATE_PACKAGE_REUSE=false
AUTHORIZATION_CLAIMED=false
PHYSICAL_EXECUTION_STARTED=false
```

FC-3 不伪造上述 live physical PASS；其职责是把这些条件冻结为 FC-4 claim 的前置硬门。

---

## 13. FC-3 terminal result

本阶段完成的边界为：cloud/source/artifact/board-role/environment/oracle/execution/evidence contract 已冻结；live physical binding 与 execution 均未开始。

```text
FC3=PASS
FC3_CLOUD_BASELINE_BINDING=PASS
FC3_ARTIFACT_CONTRACT_FROZEN=PASS
FC3_GENERIC_FACTORY_CONTRACT_FROZEN=PASS
FC3_BOARD_ROLE_CONTRACT_FROZEN=PASS
FC3_ISOLATION_CONTRACT_FROZEN=PASS
FC3_REAL_WIFI_ORACLE_FROZEN=PASS
FC3_EXECUTION_PACKAGE_FROZEN=PASS
FC3_TEST_STATE_MACHINE_FROZEN=PASS
FC3_EVIDENCE_CONTRACT_FROZEN=PASS
FC3_FAIL_CLOSED_CONTRACT_FROZEN=PASS

BOARD_A_LIVE_BINDING=NOT_STARTED
BOARD_B_LIVE_BINDING=NOT_STARTED
BOARD_C_LIVE_BINDING=NOT_STARTED
FC4_PRECLAIM=NOT_STARTED
FC4_AUTHORIZED=false
FC4_AUTHORIZATION_CLAIMED=false
PHYSICAL_EXECUTION_STARTED=false

READY_AUTHORIZED=false
MERGE_AUTHORIZED=false
N3L_STARTED=false
```

下一边界只能是独立的 FC-4 readonly live preclaim；其结果 PASS 后，仍需用户对 `D1-N3W-FC4-THREE-BOARD-FINAL-PRODUCT-E2E-20260819-01` 进行新的明确授权，才能执行任何 physical mutation / three-board E2E。
