# 温室环境监测系统 N3-W Product Completion S5 固件写入前开发交接文档

> **公共 GitHub 脱敏归档版。** 不包含 private package、本地绝对路径、USB 端口明文、PMK/application key、Wi-Fi/MQTT 凭据或原始 private Manager state。本文中的 SHA256 / Package ID 仅用于不可变绑定与后续只读复核。

**版本：** V1.0  
**日期：** 2026-08-15  
**仓库：** `chrenguo-stack/HomeAssistant`  
**范围：** N3-W Product Completion Successor / S5  
**收口点：** Real Private Package 已 materialize/compile 并完成 preflash readiness；固件尚未写入；后续物理 Flash 与 RF/E2E 放到新会话单独授权。

---

## 1. 最终阶段冻结

```text
PR322=OPEN_DRAFT_UNMERGED
SOURCE_HEAD=d30f4999235619bd545f166ff27d11941aacdd7c

PRIVATE_STATE=PASS
TWO_BOARD_PHYSICAL_IDENTITY=PASS
REAL_PRIVATE_PACKAGE=PASS
PREFLASH_READINESS=PASS

REAL_PMK_GENERATED=true
PAIR_LMK_GENERATED=false

PACKAGE_EXECUTION_AUTHORIZED=false
PHYSICAL_EXECUTION_AUTHORIZATION_PRESENT=false

FLASH_EXECUTED=false
ESP_NOW_RF_EXECUTED=false
WIFI_MQTT_LIVE_E2E_EXECUTED=false

S5_FULL_TWO_BOARD_E2E=PENDING
PRODUCTION_READINESS=NOT_CLAIMED
N3L_STARTED=false

NEXT_PHASE=NEW_CONVERSATION_PREFLASH_READONLY_REBASELINE
```

不得把本轮结果扩展为完整 S5 E2E PASS、生产可用、PR merge 授权或 N3-L 授权。

---

## 2. 产品与安全约束继续冻结

1. 所有 Wi-Fi 监测节点必须保持设备中立、通用出厂固件；出厂时不得写入其他节点 MAC/NODE_ID/GATEWAY_ID、peer relation、peer LMK/key，也不得写入用户 HA/Manager/Wi-Fi 现场信息。
2. 用户可随时增加节点；新增节点不得要求旧节点重刷或人工预写拓扑。
3. 每个节点在首次使用后独立注册并取得自己的 NODE_ID / 成员身份；Board A=Child、Board B=Relay 只是本次隔离测试角色，不是产品永久角色。
4. Relay advertisement 仅是不可信 hint；S4 `PeerAuthorizationService` 仍是唯一 peer authorization authority。
5. Manager 不生成、不分发 pair LMK；端点独立验证授权并派生相同 LMK。
6. Manager epoch 与 endpoint monotonic clock 严格分离；缺少 Manager authority time 时 fail closed。
7. 继续复用既有 `gh.relay/1`、`gh.telemetry/1`、ReceiptAck、replay/path-lease/canonical ingress，不建立第二条授权/遥测管线。

---

## 3. GitHub 与 exact-head 绑定

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PR=322
PR_STATE=OPEN
PR_DRAFT=true
PR_MERGED=false
BASE=main
BASE_SHA=38c3b692d4ebe90d0040c732b6c0313fdfdc1ef6
HEAD_BRANCH=feature/n3w-product-completion-s5-two-board-isolated-20260814-v1
HEAD_SHA=d30f4999235619bd545f166ff27d11941aacdd7c
```

Private package builder 绑定：

```text
tools/n3w_product_s5_build_private_package.py
git_blob_sha1=e76a0d3346b3a6f0e716bd50ffb31f9e2c6e2b73
ESPHOME_VERSION=2026.4.3
```

**注意：本归档使用独立 archive branch，不改变 PR #322 的 exact HEAD `d30f499...`。**

---

## 4. Dedicated private-state 与两板身份闭环

```text
PRIVATE_FILE_COUNT=9
PRIVATE_STATE_CLOSURE_SHA256=e5ff057e43e7a24d8270eab197bf28aa022881c2c1046fceae8f7ea871512abc
MATERIALIZATION_MANIFEST_SHA256=8c90fc3f5830430e757942d19689093d4803d9a4b81762af5f3a6d38d4c85eeb
```

关键 closure：

```text
REGISTRATION_EXACT_TWO_NODE_CLOSURE=PASS
PAIRING_SESSION_EXACT_TWO_NODE_CLOSURE=PASS
CREDENTIAL_LIFECYCLE_EXACT_TWO_NODE_CLOSURE=PASS
APPLICATION_KEY_EXACT_TWO_NODE_CLOSURE=PASS
BOTH_NODES_GENERIC_RELAY_CAPABLE=PASS
CREDENTIAL_GENERATION_INITIAL=1
KEY_EPOCH_INITIAL=1
REPLAY_STATE_ROW_COUNT=0
REPLAY_SEEN_ROW_COUNT=0
RELAY_GATEWAY_RELATION_ROW_COUNT=0
RELAY_OPERATION_ROW_COUNT=0
```

物理 MAC 只读复核：

```text
BOARD_A_PHYSICAL_IDENTITY_BINDING=PASS
BOARD_B_PHYSICAL_IDENTITY_BINDING=PASS
TWO_DISTINCT_PHYSICAL_BOARDS=PASS
FRESH_PHYSICAL_MAC_REVALIDATION_PERFORMED=true

BOARD_A_LOCAL_MAC_SHA256=c25b9bc46cf2c4247c607e6cc9ff7536fb22bac5c4e38fe610ca1f176b2f7ca6
BOARD_B_LOCAL_MAC_SHA256=de6b31f7d4d166afb8edcce53fe77e8cf3e723676ebac2360a405884dc846108
```

USB 端口名没有进入公共归档。后续物理执行不得仅凭端口名确认板卡，必须再次以物理 MAC hash 绑定 Board A/B。

---

## 5. Legacy isolated network 字段路径修复

只读诊断确认旧隔离输入结构为：

```text
wifi.ssid
wifi.password
wifi_channel
mqtt.host
mqtt.port
mqtt.relay_username
mqtt.relay_password
```

最终 R2 使用严格映射：

```text
wifi.ssid             -> wifi_ssid
wifi.password         -> wifi_password
wifi_channel          -> wifi_channel
mqtt.host              -> mqtt_broker
mqtt.port              -> mqtt_port
mqtt.relay_username    -> mqtt_username
mqtt.relay_password    -> mqtt_password
mqtt_tls               -> false
mqtt_client_id         -> fresh random test-only ID
```

明确不复用：

```text
MQTT_CHILD_CREDENTIAL_REUSE=false
MQTT_MANAGER_CREDENTIAL_REUSE=false
MQTT_HA_CREDENTIAL_REUSE=false
LEGACY_NODE_ID_REUSE=false
LEGACY_GATEWAY_ID_REUSE=false
LEGACY_PMK_REUSE=false
LEGACY_LMK_REUSE=false
LEGACY_APPLICATION_KEY_REUSE=false
```

---

## 6. 最终 Real Private Package R2

```text
PACKAGE_ID=S5-E2E-a78a5898-bf24-4bb7-bd49-f221dbffcaf6
PRIVATE_PACKAGE_FILE_COUNT=22
PRIVATE_PACKAGE_CLOSURE_SHA256=aeab2aaa69b7d81ce05a551ab82b4a22907cefa0fc49b45f3c9c39ef2d3bd77f

PACKAGE_MANIFEST_SHA256=c3f5bb6a4e1a408146bae398b14ed9fab37b4823db7b4a2fb740ea2ec9c892ea
PREFLASH_READINESS_SHA256=134835fa079abac9b07da187d1aabb648843df045f08831c1742f2d4cf181c65
FRESH_PMK_SHA256=c8e3b744eee8c41148c9bd52c21b17bdc1d2a0b9931336a81ebfbe1a84d73145

BOARD_A_TEST_ROLE=CHILD
CHILD_FIRMWARE_SHA256=26f40aa68e4b36f7f4de75af5e2a5590828fa653cfab425a1fbade9678e8ca3b

BOARD_B_TEST_ROLE=RELAY
RELAY_FIRMWARE_SHA256=26f8f04c0cf481e5ebf236e709c151f75818c894da870acdf81ef4a17d72834a
```

Host-only build：

```text
PRIVATE_PACKAGE_BUILD=PASS
HOST_ESPHOME_CONFIG_CHILD=PASS
HOST_ESPHOME_COMPILE_CHILD=PASS
HOST_ESPHOME_CONFIG_RELAY=PASS
HOST_ESPHOME_COMPILE_RELAY=PASS
PACKAGE_MANIFEST_VALIDATION=PASS
COPIED_MANAGER_SNAPSHOT_VALIDATION=PASS
SOURCE_PRIVATE_STATE_MUTATED=false
REPO_MUTATED=false
```

Composition / execution boundary：

```text
CHILD_ONLY_OWN_POST_REGISTRATION_MATERIAL=PASS
RELAY_ONLY_OWN_POST_REGISTRATION_MATERIAL=PASS
STATIC_GATEWAY_CHILD_PRESEED_PRESENT=false
PAIR_LMK_SUPPLIED_BY_PACKAGE=false
MANAGER_GENERATES_PAIR_LMK=false
DYNAMIC_INGRESS_AUTHORITY_RAM_ONLY=PASS

PACKAGE_EXECUTION_AUTHORIZED=false
PHYSICAL_EXECUTION_AUTHORIZATION_PRESENT=false
```

private package 本体、PMK/application key、Wi-Fi/MQTT secret、原始 Manager snapshot **未提交 GitHub**。

---

## 7. 失败 R1 / 诊断 / Successor R2 不可重放历史

原 package materialization 授权：

```text
D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-REAL-PRIVATE-PACKAGE-MATERIALIZATION-AND-PREFLASH-READINESS-20260815-01
STATUS=CONSUMED_FAILED
REPLAY_ALLOWED=false
FAIL_REASON=legacy_network_field_missing:wifi_password
REAL_PMK_GENERATED=false
PARTIAL_PRIVATE_PACKAGE_PRESENT=false
```

字段路径诊断：

```text
D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-LEGACY-ISOLATED-NETWORK-FIELD-PATH-READONLY-DIAGNOSTIC-20260815-01
STATUS=PASS_CONSUMED
```

成功 successor：

```text
D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-REAL-PRIVATE-PACKAGE-MATERIALIZATION-AND-PREFLASH-READINESS-SUCCESSOR-R2-20260815-01
STATUS=PASS_CONSUMED
REPLAY_ALLOWED=false
TERMINAL=S5_REAL_PRIVATE_PACKAGE_MATERIALIZATION_AND_PREFLASH_READINESS_SUCCESSOR_R2_PASS
```

此外本轮 private identity materialization、private-state readonly binding review、physical MAC readonly revalidation 等既有授权均保持已消费状态，禁止因为新会话或本归档而重放。

---

## 8. 新会话必须先做的工作

新会话不要直接 Flash。先进行 `PREFLASH READONLY REBASELINE`，至少复核：

```text
1. PR #322 仍 Open / Draft / Unmerged。
2. PR/worktree exact HEAD 仍为 d30f4999235619bd545f166ff27d11941aacdd7c。
3. private-state closure 仍为 e5ff057e...512abc。
4. R2 package ID / package closure / manifest / preflash-readiness / 两个 firmware SHA 全部仍匹配。
5. execution_authorized=false、physical_execution_authorization=None。
6. 失败 R1 和成功 R2 的 consumed/non-replay 状态仍成立。
7. 只读复核阶段禁止 board/serial/USB/JTAG/erase/flash/OTA/ESP-NOW RF/live Wi-Fi/MQTT。
```

建议下一只读门（本归档不构成授权）：

```text
D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-PREFLASH-READONLY-REBASELINE-20260815-01
```

实际 Flash 前还必须独立冻结 exact flash plan / offsets / tool version。当前 builder 明确不生成 device command sheet，因此禁止从 `firmware.bin` 文件名自行猜 write offsets，也禁止直接复用旧实板命令。

后续 physical flash authorization 必须是全新的 exactly-once gate，并重新确认当前 USB 端口与两块物理 MAC 的 Board A/B 绑定。

---

## 9. Flash 后仍未完成的 S5 E2E

即使 Flash PASS，仍需独立验证 Relay 隔离 Wi-Fi/MQTT/Manager、Child disconnected ESP-NOW、真实 advertisement、Manager grants、两端派生相同 LMK、动态 peer、Child→Relay→MQTT→Manager telemetry、canonical seq/replay/path-lease、ReceiptAck/retry-cache、revoke/expiry/stale/replay/credential negatives、restart cleanup/zeroization、HA identity continuity 等。

在这些真实物理 E2E 完成前：

```text
S5_FULL_TWO_BOARD_E2E=PENDING
PRODUCTION_READINESS=NOT_CLAIMED
```

---

## 10. 公共/私有归档边界

本公共归档允许：PR/commit 状态、sanitized PASS/FAIL、非秘密 SHA256、授权状态与产品约束。

严禁提交：private package、本地 private root、PMK/application key 明文、Wi-Fi/MQTT secret、NODE_ID/MAC 明文、private Manager snapshot、原始私有执行证据或可直接重放的 physical execution package。

本文件仅用于开发恢复与状态冻结，**不授权任何新的 board access、Flash/erase/OTA、ESP-NOW RF、Wi-Fi/MQTT live E2E、production 变更、PR merge/release 或 N3-L 操作。**
