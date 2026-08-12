# 温室环境监测系统 N3-W / P5 / M08 Relay Successor PATH 恢复与授权发布者凭据确认后开发交接文档

- 版本：V1.0
- 日期：2026-08-12
- 范围：N3-W / P5 / M08
- 仓库：`chrenguo-stack/HomeAssistant`
- 文档性质：公开仓库脱敏交接归档；不包含任何 MQTT 明文用户名、密码、密钥或 private raw evidence

## 1. 交接目的

本文件冻结 M08 Relay successor 修复合并、private materialization、Relay inactive-slot 物理部署、PATH RELAY 恢复调查以及 command publisher credential reconciliation 的当前结论。后续对话必须从本文件和 GitHub exact state 只读复核开始，不得重放已消费授权。

本文件不是 M08 PASS 证据。当前 `M08_PASS=false`、`M08_FAIL=false`，且 M09 仍禁止。

## 2. GitHub exact source anchor

当前 exact-main：

- commit: `ffd9d00c0107e4893166c05939183dc702a30f83`
- tree: `b058be3142b04fe27db0c345469370ce85a48b46`
- merge source: PR #305 `fix(n3w-p5): require fresh reprobe after Relay restart`
- PR #305 exact repair HEAD: `b28daf5e5521e5ac69ab913a8856cae8a4f15f0c`

PR #305 在 Relay 侧增加 boot-local fresh-probe gate，并在 Child PATH RELAY / ReceiptAck retry exhaustion 时使旧 Relay authentication 失效，要求 fresh authenticated Probe/ProbeAck 后才能继续 Relay reassembly。successor-only 运行时 marker 为：

`Fresh authenticated Child probe established for current Relay boot`

## 3. Private materialization 公共绑定

私有材料本身不得上传公开仓库。仅冻结非秘密哈希：

- materialization manifest SHA256: `da136b150254b9e1aaa6419cb1000f5b16fb795f94358e812e5386cb89557053`
- Relay private render SHA256: `061812bf06d7ba8dffee270397c99e9585cfaab162cd402e69d341596b8cb0b3`
- Relay exact firmware SHA256: `9e72074e8a925a107a59e23123eb4efe7dca00822a97b936f4fce5354c77a4cd`
- post-write otadata SHA256: `b7e293bb607d3bddb99b7f38a7a45afd5823c0c61e3216e67858bbc759535282`
- alternative no-reset evidence plan SHA256: `fe7d0377d3fe1c5d9a693faeccca6aee7fe9fa1606685c788e9033ec21361808`
- corrected PATH preexecution plan SHA256: `5e3748e7ec5a9046c0fa782085e98886f3bf0941383b5f577167c7df0003aeb3`
- Relay deployment plan SHA256: `7bfedc8b83838e3cb07add0fd891653953a94fb5a01fb5090a228cf6ffd3d79b`

## 4. Relay successor 物理部署冻结状态

Relay successor 已按一次性 inactive-slot 部署完成：

- target inactive slot: `ota_1`
- app offset: `0x3d0000`
- firmware write exactly once: completed
- firmware readback: exact SHA verified
- otadata copy1 write exactly once: completed
- post-write otadata selection: `ota_1`
- controlled boot count: `1`

必须区分“successor image/boot selection 已部署”和“当前正在运行的 application identity 已证明”。截至本交接：

- `CURRENT_RUNNING_OTA_SLOT_PROVEN=false`
- `RELAY_SUCCESSOR_APPLICATION_LIVENESS_PROVEN=false`
- `RELAY_APPLICATION_BOOT_FAILURE_PROVEN=false`

无串口 marker 不能解释为 application boot failure。

## 5. Child 当前冻结状态

Child successor deployment/liveness 已在此前独立门闭环。当前 M08 调查期间 Child 保持 Direct path。最新 credential reconciliation 门结束时：

- active path: `direct`
- path candidate: none
- Child boot identity hash: `988ca5ee86f094805f1ae79415fb3ae1438a4bb4448906065187fe0640a8ffad`
- canonical seq: `1046 -> 1051`
- path revision: `21420 -> 21425`
- same Child boot session: true
- service baseline unchanged: true
- production `192.168.68.0/24` route present: false

seq 必须在 boot/session 语义下解释，不得跨 boot 直接以数值大小判断 rollback。

## 6. PATH RELAY 恢复调查结论

### 6.1 第一类 host-side 失败：Docker 端口命名空间错误

第一次 successor PATH 尝试使用 Broker 容器内部 `127.0.0.1:18883`。只读恢复分类证明：

- host published port: `18883 -> broker container 1883`
- broker container listener: `1883`
- broker container 不监听 `18883`

根因冻结为：

`HOST_PUBLISHED_PORT_USED_INSIDE_BROKER_CONTAINER_NETWORK_NAMESPACE`

以后 Broker 容器内部发布必须使用 `127.0.0.1:1883`；容器内部使用 host port `18883` 被禁止。

### 6.2 第二类 host-side 失败：发布凭据方向错误

端口修正后，exactly-one PATH RELAY publish 的 `mosquitto_pub` return code 为 0，但 Child 未证明收到/执行 PATH RELAY：

- successor marker: absent
- Relay postcommand RX bytes: 0
- Child boot session unchanged
- canonical continued advancing in same boot
- Manager remained `direct / no candidate`

后继只读分类证明 Broker ACL 的 command-topic 方向为：

- Child runtime credential: READ=ALLOW
- Child runtime credential: WRITE=DENY

因此上一次 command publisher 错误使用了 Child runtime credential。根因冻结为：

`CHILD_RUNTIME_CREDENTIAL_IS_COMMAND_SUBSCRIBER_ONLY_AND_WAS_MISUSED_AS_COMMAND_PUBLISHER`

这解释了 corrected broker endpoint 下的 non-delivery；不得把该次 publish 当作 Child delivery proof。

## 7. 唯一授权 command publisher 与 credential reconciliation

只读 ACL discovery 已证明：

- Broker ACL rule count: 10
- Broker password user count: 5
- command-topic WRITE-authorized publisher candidate count: exactly 1
- authorized publisher username SHA256: `9bba5c53a0545e0c80184b946153c9f58387e3bd1d4ee35740f29ac2e718b019`
- Child runtime credential excluded: true
- ACL file SHA256: `a157d9739cbdbbb6925c6a62338424ca49c745855e592d943efbc14322604af4`
- password file SHA256: `f59394ac8d84d899e5943d37f6c3c76c901911a38d6ca48c206c4a3decb0e6c3`

第一次窄 pairing 规划器未能离线验证 publisher password，并在 claim 前停止。该授权没有被消费。

后继 credential reconciliation 扩大到受控 private/password-like candidate 集合，并取得：

- private text files scanned: 14206
- permission-skipped: 16053
- decode-skipped: 14775
- password candidate variants: 361
- password verification method: SHA512_PBKDF2
- `VERIFIED_PRIVATE_PASSWORD_VARIANT_COUNT=1`
- verified source count: 2
- verified source types: `CONTAINER_ENV_PASSWORD_LIKE_SCALAR`, `PRIVATE_PASSWORD_LIKE_SCALAR`
- secret values printed: false

最终分类：

`EXACT_ONE_CURRENT_PRIVATE_PASSWORD_MATCH`

终端：

`PASS_AUTHORIZED_PUBLISHER_EXACT_CURRENT_PRIVATE_PASSWORD_RECONCILED`

边界：由于有 permission/decode skipped 文件，不能宣称整个 private custody 的全局穷尽唯一性。允许的结论是：当前 Broker-authorized publisher 的有效 password existence 已证明；当前 Broker hash match 已证明；在已检查候选集中恰好一个 password variant 验证成功。

不得公开保存或输出 publisher username/password 明文。

## 8. 授权状态与不可重放边界

以下本轮关键授权已 `CLAIMED=true / CONSUMED=true / DO_NOT_RERUN=true`：

1. `D1-N3W-P5-M08-PRIVATE-FIRMWARE-MATERIALIZATION-SUCCESSOR-PUBLIC-SENTINEL-SCOPE-REPAIR-AND-HOSTONLY-EXECUTION-20260811-01`
2. `D1-N3W-P5-M08-RELAY-SUCCESSOR-EXACT-INACTIVE-SLOT-PHYSICAL-DEPLOYMENT-EXECUTION-20260812-01`
3. `D1-N3W-P5-M08-RELAY-SUCCESSOR-POSTDEPLOYMENT-NO-RESET-READONLY-STATE-AND-LIVENESS-REBASELINE-20260812-01`
4. `D1-N3W-P5-M08-RELAY-SUCCESSOR-ALTERNATIVE-NO-RESET-APPLICATION-LIVENESS-AND-RUNNING-SLOT-EVIDENCE-PLAN-20260812-01`
5. `D1-N3W-P5-M08-RELAY-SUCCESSOR-NEW-PATH-RELAY-REESTABLISHMENT-WITH-PREARMED-SUCCESSOR-MARKER-EVIDENCE-20260812-01`
6. `D1-N3W-P5-M08-RELAY-SUCCESSOR-POSTPATH-READONLY-RECOVERY-CLASSIFICATION-20260812-01`
7. `D1-N3W-P5-M08-RELAY-SUCCESSOR-CORRECTED-PATH-RELAY-PUBLISH-PREEXECUTION-PLAN-20260812-01`
8. `D1-N3W-P5-M08-RELAY-SUCCESSOR-CORRECTED-PATH-RELAY-PUBLISH-WITH-PREARMED-SUCCESSOR-MARKER-EVIDENCE-20260812-01`
9. `D1-N3W-P5-M08-RELAY-SUCCESSOR-POSTPATH-READONLY-RECOVERY-CLASSIFICATION-SUCCESSOR-20260812-01`
10. `D1-N3W-P5-M08-RELAY-SUCCESSOR-AUTHORIZED-COMMAND-PUBLISHER-CREDENTIAL-RECONCILIATION-READONLY-20260812-01`

此外，所有此前交接中已经标记 consumed/non-replayable 的 M08 preliminary gates 继续保持不可重放。

### 未消费但不得原样继续使用的旧规划授权

`D1-N3W-P5-M08-RELAY-SUCCESSOR-AUTHORIZED-COMMAND-PUBLISHER-READONLY-BINDING-AND-RETRY-PLAN-20260812-01`

该门在 claim 前因窄 credential pairing verification 失败停止：

- `AUTHORIZATION_CLAIMED=false`
- `AUTHORIZATION_CONSUMED=false`
- `AUTHORIZATION_REUSABLE_AFTER_REVIEW=true`

但因为后续 credential reconciliation 已改变我们对凭据绑定方式的理解，后续必须使用 successor planning gate，不得原样执行旧规划器。

## 9. 当前 M08 总状态

冻结：

```text
CURRENT_ACTIVE_PATH=direct
CURRENT_PATH_CANDIDATE_NONE=true
PATH_RELAY_REESTABLISHED=false
CURRENT_RUNNING_OTA_SLOT_PROVEN=false
RELAY_SUCCESSOR_APPLICATION_LIVENESS_PROVEN=false
RELAY_APPLICATION_BOOT_FAILURE_PROVEN=false
M08_RELAY_RESTART_ALLOWED_NOW=false
M08_PASS=false
M08_FAIL=false
M09_ALLOWED=false
```

任何后续文档不得把 Relay successor physical deployment 写成 live application PASS，不得把 missing marker 写成 boot failure，不得把当前 M08 写成 PASS/FAIL。

## 10. 下一唯一决策门

下一门尚未授权、尚未 claim、尚未消费：

`D1-N3W-P5-M08-RELAY-SUCCESSOR-AUTHORIZED-COMMAND-PUBLISHER-VERIFIED-CREDENTIAL-BINDING-AND-RETRY-PLAN-SUCCESSOR-20260812-01`

它必须是 host-only / read-only planning gate，至少重新绑定：

- exact main/tree；
- private materialization manifest/firmware hashes；
- current Child same-boot identity；
- current Direct/no-candidate baseline；
- exact command topic hash；
- authorized publisher username hash；
- current ACL/password-file SHA；
- verified credential 的非秘密 source bindings；
- authorized publisher command WRITE=ALLOW；
- Child runtime credential command WRITE=DENY / READ=ALLOW；
- future publish context: Broker container；
- future endpoint: `127.0.0.1:1883`；
- fresh MQTT client ID；
- Relay serial RX-only prearm；
- future exactly-one PATH RELAY publish max=1；
- retry=false；
- second publish=false；
- reset/flash/power/restart/M09=false。

该 planning gate 本身不得 MQTT connect/sub/pub，不得 PATH，不得打开串口，不得碰板卡。

## 11. 后续正确顺序

1. 新对话只读复核本交接 + GitHub exact-main + private/current现场；
2. 若无 drift，再授权上述 verified-credential successor planning gate；
3. planning PASS 后另立新的 exactly-one PATH RELAY physical/runtime execution authorization；
4. execution 必须使用唯一 WRITE-authorized publisher credential、正确 Broker container endpoint、fresh client ID、Relay RX-only prearm；
5. 必须证明 fresh successor marker / Relay path recovery，且 Child boot session 保持稳定；
6. 成功后另立 `ALL_NEW_VERSION_RELAY_BASELINE`；
7. baseline PASS 后才允许创建 fresh exactly-one M08 Relay `RESTART` 授权；
8. M08 完整闭环前禁止 M09。

## 12. Public/private custody 边界

公开 GitHub 只允许保存脱敏结论、代码、测试、CI、非秘密 SHA/状态机结论。以下不得进入公开仓库：

- MQTT username/password 明文；
- application keys、LMK、root keys；
- private raw execution evidence 中的秘密字段；
- private rendered secrets；
- 可直接恢复秘密的 credential value/fingerprint。

本交接仅保存非秘密身份/文件哈希和语义结论。

## 13. 新对话开场要求

新对话首先只读复核：

- `main == ffd9d00c0107e4893166c05939183dc702a30f83`；
- tree == `b058be3142b04fe27db0c345469370ce85a48b46`；
- PR #305 merged exact state；
- private materialization hashes未漂移；
- Broker ACL/password-file hashes未漂移；
- current Child boot/path/candidate state；
- Manager/Broker/HA service baseline；
- production route isolation；
- 上述所有 consumed authorization 不可重放。

只有全部只读复核通过，才进入下一授权。
