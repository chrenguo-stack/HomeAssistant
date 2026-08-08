# 温室环境监测系统 N3-W P5 R3 M02 AEAD运行时依赖缺陷与 Successor 修复授权前开发交接文档

- 文档版本：V1.0
- 生成日期：2026-08-09
- 项目：温室环境监测系统（ESP32-C6）
- 阶段：N3-W / P5 / R3
- 当前停点：M02 Direct → Relay 已执行一次并 `CONSUMED_FAILED`
- 下一步：新对话先只读复核本交接文档与 GitHub 精确状态；无漂移后再申请 `D1-N3W-P5-M02-AEAD-RUNTIME-DEPENDENCY-SUCCESSOR-REPAIR-20260809-01`
- 本文档不包含任何私密密钥、MQTT 密码或真实密钥值。

---

## 1. 本轮结束结论

本轮已完成 P5 R3 两块 ESP32-C6 隔离实验环境从工具链、Broker、Manager、两块板烧录、M01 Direct 稳态验证到 M02 Direct→Relay 实板执行。

M02 的物理传输链已经证明：

`Child → ESP-NOW → Relay → isolated Wi-Fi/MQTT → Broker`

实际成立。

M02 未能继续进入 Manager Relay ingress / path lease / canonical 状态切换，根因已通过只读取证闭环定位为：

`MANAGER_RUNTIME_AEAD_DEPENDENCY_MISSING`

即：Manager 生产运行镜像没有安装 Relay AES-GCM 解密路径所需的 Python `cryptography` 包。

这是产品代码/打包缺陷，不是板卡、ESP-NOW、Relay MQTT、Broker subscription 或 path lease 算法故障。

当前必须停止 R3 M02 重放，不得继续 M03；下一阶段应先修复生产运行时依赖，再建立绑定新精确 HEAD 的 successor 物理验证链。

---

## 2. 当前 GitHub 精确冻结基线

仓库：

`chrenguo-stack/HomeAssistant`

### 2.1 main

```text
main = 8a57243fce0d347ebb20108f4ec5a2d5d4267486
```

本轮结束前重新只读确认 main 未漂移。

### 2.2 PR #292

```text
PR = #292
title = feat(n3w): prepare P5 two-board isolated E2E package
state = Open
draft = true
merged = false
mergeable = true
base = main
base_sha = 8a57243fce0d347ebb20108f4ec5a2d5d4267486
head = feature/n3w-p5-two-board-isolated-e2e-prep-20260807-v1
head_sha = 752c4709c6c9b60490dbcaf6da5807538dc03fa7
commits = 15
changed_files = 20
```

PR #292 必须保持 Draft / Unmerged；本轮没有修改其 HEAD。

### 2.3 PR #276

```text
PR = #276
state = Open
merged = false
mergeable = true
head = agent/n3w-single-hop-contract-20260806-v1
head_sha = 239ea594c643d4990d449187f8b0cabae619e3d7
base_sha = 2d444f3e392249c8d7bf1a1aa036e738a418d1cb
```

PR #276 本轮没有修改。

### 2.4 P5 exact source binding

```text
P5 exact HEAD = 752c4709c6c9b60490dbcaf6da5807538dc03fa7
tree = 2da08aac99a3b6cdbf5c093146cfbe77793500c2
exact execution plan blob = ad99f8d22eae647b8690f4981cca98786e953a97
n3w_p5_lab.cpp blob = 116fa324f6959a86557531a89c91d9deae6b77e4
n3w_p5_lab.h blob = c50031157e300eb0f9a8c1da1f7047575b3bf7ea
docker-compose.yml blob = 19109fd7dd8d213f20201dea23b2f9b3a334629f
ACL blob = 146efe3fd6b62567610f24651867c1fee1481843
mqtt_service.py blob = faf6898dfdcb6eb8eee77635f2d058b5c2061f3f
n3w_runtime_wiring.py blob = 0bf2ce6317b6b9f3597d02ba920bc93e068eb3fa
```

---

## 3. R3 治理与不可重放状态

### 3.1 R3 总体物理授权

```text
D1-N3W-P5-TWO-BOARD-ISOLATED-E2E-PHYSICAL-EXECUTION-R3-20260808-01
status = APPROVED_CONSUMED_IN_PROGRESS
```

R1、R2、原始 P5 physical authorization 已退休，禁止重放。

### 3.2 已消费成功的修复门

```text
D1-N3W-P5-R3-MAC-COLIMA-DOCKER-TOOLCHAIN-INSTALL-20260808-01
= APPROVED_CONSUMED_SUCCESS

D1-N3W-P5-R3-BROKER-HEALTHCHECK-QUOTING-OVERLAY-AND-INPLACE-FOUNDATION-RESUME-20260808-01
= APPROVED_CONSUMED_SUCCESS

D1-N3W-P5-R3-MANAGER-STATE-OWNERSHIP-INPLACE-REPAIR-AND-PRESTART-ACCESS-CLOSURE-20260808-01
= APPROVED_CONSUMED_SUCCESS
```

Manager ownership mutation只能执行一次，禁止重放。

### 3.3 M01 successor closure

```text
D1-N3W-P5-R3-M01-ORACLE-FALSE-NEGATIVE-SUCCESSOR-CLOSURE-20260808-01
= APPROVED_CONSUMED_SUCCESS
```

M01 原始尝试保持：

```text
M01_ORIGINAL_ATTEMPT = CONSUMED_FAILED
M01_ORIGINAL_REPLAY_ALLOWED = false
M01_ACTUAL_FAILURE_CLASS = TEST_ORACLE_FALSE_NEGATIVE
M01_PRODUCT_FUNCTION_FAILURE = false
```

Successor 已闭合：

```text
M01_HISTORICAL_DIRECT_STEADY = PASS
M01_LIVE_DIRECT_CANONICAL_OBSERVATION = PASS
M01_HA_SINGLE_DEVICE_CONTINUITY = PASS
M01_SUCCESSOR_CLOSURE = PASS
M01_SUCCESSOR_REPLAY_ALLOWED = false
```

### 3.4 M02 双在线 preflight

```text
D1-N3W-P5-R3-M02-RELAY-POWER-AND-DUAL-ONLINE-PREFLIGHT-20260808-01
= APPROVED_CONSUMED_SUCCESS
```

最终状态：

```text
M02_DUAL_ONLINE_PREFLIGHT = PASS
Child MQTT socket = PASS
Relay MQTT socket = PASS
dual_online = true
Child Direct steady = PASS
premature Relay ingress = false
HA device count = 1
HA entity count = 6
Broker restart = 0
Home Assistant restart = 0
Manager restart = 0
```

### 3.5 M02 Direct → Relay execution

```text
D1-N3W-P5-R3-M02-DIRECT-TO-RELAY-EXECUTION-20260809-01
= APPROVED_CONSUMED_FAILED
```

严格冻结：

```text
M02_ORIGINAL_ATTEMPT = CONSUMED_FAILED
M02_REPLAY_ALLOWED = false
PATH_RELAY_RESEND_ALLOWED = false
```

不得重新发送 `PATH RELAY`。

---

## 4. 当前实板与隔离网络状态

### 4.1 两块板身份

```text
Child base MAC = 98:a3:16:a9:f3:50
Relay base MAC = 98:a3:16:a9:f4:5c

system_id = n3wp5lab
Child node_id = n3wp5_child01
Relay gateway_id = n3wp5_relay01
```

### 4.2 当前物理连接

本轮结束时必须保持：

```text
Child:
  connected to Mac USB data/power = true
  power = Mac USB
  current isolated IP observed = 10.168.1.119

Relay:
  connected to Mac USB data = false
  power = independent 5V
  current isolated IP observed = 10.168.1.180
```

Mac 当前只允许 1 个 ESP32-C6 USB/data 连接，当前为 Child。

### 4.3 隔离网络

```text
Mac isolated IPv4 = 10.168.1.211
isolated subnet = 10.168.1.0/24
router = 10.168.1.1
Wi-Fi channel = 1
Broker host bind = 10.168.1.211:18883
```

本轮所有检查均确认：

```text
PRODUCTION_192_168_68_ROUTE_PRESENT = false
```

严禁对生产 `192.168.68.0/24` 进行 ping、probe 或任何 mutation。

### 4.4 当前软件/路径状态

M02 执行前：

```text
Manager active path = direct
canonical boot session = 077d07249ff2a19f
canonical seq = 1860
```

发送一次 `PATH RELAY` 前，最后 Direct 帧继续推进：

```text
Direct seq = 1861, 1862
```

M02 失败后当前 Manager path lease：

```text
active_transport = direct
active_gateway_id = NONE
candidate_transport = NONE
candidate_gateway_id = NONE
canonical_boot_session_hex = 077d07249ff2a19f
canonical_seq = 1862
revision = 1471
```

Child 固件 desired path 已切换到 Relay；它当前持续把新 telemetry 经 ESP-NOW 发向 Relay。

由于 Manager 缺少 AEAD backend，Relay gateway frame 不能进入验证后的 path candidate，因此 canonical 停在 1862。

---

## 5. M02 实际观测

### 5.1 PATH RELAY

本轮 M02 只发送一次：

```text
PATH_RELAY_COMMAND_COUNT = 1
PATH_RELAY_MQTT_PUBLISH_RC = 0
```

命令时间：

```text
2026-08-09T00:49:25+0800
UTC = 2026-08-08T16:49:25Z
```

不得重发。

### 5.2 Direct → Relay 边界

冻结 MQTT trace：

```text
DIRECT_COUNT = 2
DIRECT_SEQS = 1861,1862

GATEWAY_COUNT = 14
GATEWAY_SEQS = 1863,1864,1865,1866,1867,1868,1869,1870,1871,1872,1873,1874,1875,1876

CANONICAL_COUNT = 3
CANONICAL_SEQS = 1860,1861,1862

CONTROL_COUNT = 1
CONTROL_1 = PATH RELAY

DIRECT_GATEWAY_INTERSECTION_COUNT = 0
GATEWAY_CANONICAL_INTERSECTION_COUNT = 0
```

这证明序列在同一 boot session 中从 Direct 1862 无缝继续到 Relay transport envelope 1863+。

注意：执行脚本的 `GATEWAY_VALID_FRAME_COUNT=14` 只表示外层 `gh.relay/1` envelope 结构/绑定字段通过观察器检查；由于 Manager 缺少 cryptography，这些帧没有完成 AES-GCM authentication/decryption，因此不能称为“已经通过密码学验证的 Relay telemetry”。

### 5.3 Manager 实际结果

Manager 正确订阅：

```text
gh/v1/n3wp5lab/ingress/node/+/telemetry
gh/v1/n3wp5lab/state/+/telemetry
gh/v1/n3wp5lab/ingress/gateway/+/+/frame
```

但从首个 Relay frame 开始，每 5 秒稳定出现：

```text
Rejected N3-W ingress source=relay node=None code=aead_backend_unavailable
```

冻结执行窗口内 14 帧全部走入该失败路径。

因此：

```text
MANAGER_RELAY_ACCEPTED_FRAME_COUNT = 0
MANAGER_ACTIVE_PATH_HEALTHY_REJECT_COUNT = 0
MANAGER_PATH_CANDIDATE_PENDING_COUNT = 0
```

这三个值为 0 并不是 path lease 没收到消息，而是消息在进入 path lease 之前就因 AEAD backend 不可用被 fail-closed。

---

## 6. 根因闭环

精确 HEAD 的 Relay ingress 实现要求：

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
```

ImportError 会转化为：

```text
aead_backend_unavailable
```

精确 HEAD `host/greenhouse-manager/pyproject.toml`：

```text
base dependencies:
  jsonschema>=4.23,<5
  paho-mqtt>=2.1,<3

cryptography>=44,<50:
  only in optional dev
  optional pairing
  optional bootstrap
```

精确 HEAD `host/greenhouse-manager/Dockerfile`：

```text
RUN python -m pip install .
```

因此生产 Manager image 只安装 base dependencies，没有安装 `cryptography`。

根因分类冻结：

```text
M02_FAILURE_CLASS = MANAGER_RUNTIME_AEAD_DEPENDENCY_MISSING

RF_LINK_FAILURE = false
ESP_NOW_FAILURE = false
CHILD_TO_RELAY_FAILURE = false
RELAY_TO_BROKER_FAILURE = false
MQTT_SUBSCRIPTION_FAILURE = false
PATH_LEASE_FAILURE = false

KEY_MATERIAL_FAILURE = UNTESTED
AEAD_AUTHENTICATION_FAILURE = UNTESTED

PRODUCT_CODE_PACKAGING_DEFECT = true
```

必须注意：由于 AES-GCM backend 根本未加载，当前证据不能判断实际 application key 是否正确，也不能判断 cryptographic authentication 是否会成功；这些必须在 runtime dependency 修复后的 successor 中验证。

---

## 7. 为什么不能临时在运行容器内 pip install

禁止使用：

```text
docker exec ... pip install cryptography
```

作为继续 R3 的手工恢复方式。

原因：

1. 会使当前 Manager 容器成为无法从冻结精确源码重建的污染实例；
2. 容器重建后补丁消失；
3. 会破坏后续 M09 Manager restart 的可重复证据语义；
4. 会把产品 packaging 缺陷伪装成现场操作问题；
5. 会破坏当前 R3 immutable evidence 与 successor 的清晰边界。

正确路径是修改代码/包依赖 + Docker image level test + CI，再构造新精确 HEAD 的 successor/R4 物理包。

---

## 8. 本轮关键私密证据索引

所有私密证据根：

```text
$HOME/P5_R3_20260808_PRIVATE
mode = 0700
```

禁止输出任何秘密值。

### 8.1 基础

```text
.env SHA256 =
d00b117dbf0392973df8de1e7f5a23fe91aac03f1f275d1a0f35bc77a7fd093f
```

基础阶段另有 DB-before、ownership、stack preflight、broker repair、corrected preflash 等 immutable evidence。新对话如需精确比较，应从本地 evidence 重新计算 SHA，不得凭缩写或记忆猜测。

### 8.2 Flash

```text
Child flash terminal SHA256 =
b80b2755e63c2bb055caf0c6335b7ab16c7762c44dfb032ec4fbce02230e9ad1

Relay flash terminal SHA256 =
1b97bcf51552b9e85fd133725723d9b29251fe967bfe3f436d1755f82a11a233

Relay runtime activation evidence SHA256 =
5ee6cc27fbb459a1de0d5a186daacac8ac08a70c03342bc07ca2a62dd840e61e
```

两块板均只允许本 R3 已完成的那一次烧录，禁止重新 Flash。

### 8.3 M01 successor

```text
claim SHA256 =
c0f8c8786b7c152ec4df0a1e2ccbdeb796b06c3266bb92b392a5012ae57f1bf7

trace SHA256 =
764c6bfb7714bfa41f74b2bd3664e7f5d0a798a48e83446a225a6b0f5486d6d1

closure SHA256 =
11ff70405486fd5ffca63bee99aecbd81229b0ecabd71aaebfd764b369595b2a
```

全部 immutable，禁止覆盖。

### 8.4 M02 dual-online preflight

```text
claim SHA256 =
37f7ed570b9715080bfcfab6871ac9cf1faf88f8a6efa910aed7b9101d11c945

terminal SHA256 =
f286c7fbd0c6ad88ee623cc868d92f320141d205ed5da45e1f5183dbb2cc647d

terminal mode = 600
status = PASS
replay_allowed = false
```

### 8.5 M02 Direct → Relay execution

```text
claim SHA256 =
f7c68a9cd014ccb48ca99ba1254499eeb8828ceefb7e60d399c045d5ff0e10d4

MQTT trace SHA256 =
5590a022b8677f1d09742c0997903f47cc91cdb727849d7a87d02c24c89c7438

Manager log SHA256 =
7d11486213a110d502e88ce24070b4c1b3d9c1db49caa24f97649b69ef069f0f

terminal evidence SHA256 =
4d454a835b1a76f855ec51115885556e2f876e4ab6896712672263c1c3ca7643

status = CONSUMED_FAILED
replay_allowed = false
```

这些文件必须保持 immutable；尤其不得通过重跑 M02 覆盖。

---

## 9. 当前禁止事项

新对话在 successor repair 获得授权前，全部禁止：

```text
禁止再次发送 PATH RELAY
禁止发送 PATH DIRECT recovery
禁止进入 M03
禁止 Child restart
禁止 Relay restart
禁止 Manager restart
禁止 Broker restart/outage
禁止 Home Assistant restart
禁止重新 Flash
禁止重新生成 PMK/LMK/application keys
禁止 rerender private configs
禁止重跑 lab-init
禁止修改现有 private evidence
禁止访问生产 192.168.68.0/24
禁止修改 PR #292
禁止修改 PR #276
禁止 Ready
禁止 merge
禁止 release/tag/deploy
```

如果因为物理安全必须断电，应视为现场状态发生变化；下一对话必须先记录该变化并重新建立 successor 的物理基线，不能假装仍处于当前连续运行状态。

---

## 10. 下一修复门的严格范围

待新对话只读复核无漂移后，才可由用户明确批准：

```text
D1-N3W-P5-M02-AEAD-RUNTIME-DEPENDENCY-SUCCESSOR-REPAIR-20260809-01
```

建议 scope：

1. 以 P5 exact HEAD `752c4709c6c9b60490dbcaf6da5807538dc03fa7` 为修复事实基线；
2. 不修改原 M02 claim/trace/log/terminal；
3. 修复 `cryptography>=44,<50` 的 production runtime dependency；
4. 优先将 cryptography 纳入 Manager 基础 runtime dependency，除非仓库事实审查证明更合适的显式 runtime extra 能被 Dockerfile 强制安装；
5. 增加生产 Docker image 级测试：
   - `cryptography` 实际可 import；
   - `AESGCM` 实际可实例化；
   - Relay decrypt path 在与生产 image 相同依赖集下可执行；
6. 防止出现“单元测试因安装 `[dev]` 而通过、生产 image 因 `pip install .` 而缺依赖”的再次回归；
7. 运行完整相关 CI；
8. 不操作当前两块板；
9. 不直接 patch 当前运行容器；
10. 不修改 main；
11. 不 Ready/merge/deploy；
12. 修复完成后建立新的 exact HEAD / artifact / private successor package；
13. 原 R3 M02 保持 `CONSUMED_FAILED`，不重写历史；
14. successor 只验证未完成的 M02 cryptographic + path switch 目标，不把原失败伪装成 PASS。

---

## 11. 下一物理 successor 必须重新验证的事项

代码修复后，新物理 successor 至少需要验证：

```text
1. Manager production image includes cryptography
2. AES-GCM backend available
3. existing/current application key binding resolves correctly
4. Relay envelope decrypt/authentication succeeds
5. telemetry inner binding succeeds
6. Direct→Relay path candidate starts only after Direct lease policy permits
7. minimum distinct frames = 2
8. stability window = 5 s
9. active path atomically switches direct → relay
10. canonical identity continuity at the chosen recovery boundary
11. canonical seq advances without duplicate/replay violation
12. at least 3 accepted Relay canonical frames
13. HA remains one n3wp5_child01 device
14. no duplicate entities
15. Broker/HA/Manager restart counts satisfy successor contract
16. production route remains absent
```

是否可以复用当前持续运行的 boot session，需要由新 successor 设计基于“现场是否仍连续供电”和“修复是否必须替换 Manager container”重新决定，不能在本交接文档中预先宣称。

---

## 12. M03 及后续矩阵仍未开始

冻结矩阵：

```text
M01 direct steady
M02 direct → relay
M03 relay → direct
M04 duplicate
M05 reorder
M06 late old frame
M07 child restart
M08 relay restart
M09 manager restart
M10 auth revoke
M11 auth regrant
M12 key rotation
M13 broker outage
M14 identity continuity
```

当前只完成：

```text
M01 functional objective = PASS via successor closure
M02 original R3 = CONSUMED_FAILED due product packaging defect
M03-M14 = NOT STARTED
```

Manager restart 仍只属于 M09；不得为了修 M02 随意消费 M09 语义。代码修复后的 successor 若技术上需要替换 Manager container，必须在 successor 设计中明确区分“修复部署所必需的容器替换”和“M09 restart matrix test”。

---

## 13. 下一对话必须执行的启动顺序

新对话不得直接批准修复。

先只读复核：

```text
1. 阅读本交接文档
2. GitHub main 当前 SHA
3. PR #292 Open/Draft/Unmerged/HEAD
4. PR #276 Open/Unmerged/HEAD
5. exact source dependency facts:
   pyproject.toml
   Dockerfile
   n3w_relay_ingress.py
6. 原 M02 evidence SHA 是否完整
7. 当前实验现场是否仍保持：
   Child Mac USB
   Relay independent 5V
8. production route 是否仍 absent
9. 当前 Broker/HA/Manager 状态仅在 successor scope 允许时读取
10. 确认原 M02 replay=false
```

只有全部无漂移，才报告：

```text
READY_FOR_D1_N3W_P5_M02_AEAD_RUNTIME_DEPENDENCY_SUCCESSOR_REPAIR_AUTHORIZATION=true
```

然后等待用户原样批准：

```text
批准 D1-N3W-P5-M02-AEAD-RUNTIME-DEPENDENCY-SUCCESSOR-REPAIR-20260809-01
```

不得提前 mutation。

---

## 14. 新对话建议启动提示词

```text
阅读《温室环境监测系统_N3W_P5_R3_M02_AEAD运行时依赖缺陷与Successor修复授权前开发交接文档_V1.0_20260809.md》，继续 N3-W P5。

先只读复核 main、PR #292 精确 HEAD、PR #276 精确 HEAD、M02 immutable evidence、Manager production dependency facts，以及当前现场状态。不得重放 R3 M01/M02，不得再次发送 PATH RELAY，不得发送 PATH DIRECT recovery，不得重启板卡/Manager/Broker/HA，不得重新 Flash，不得修改 PR/main。

已知 R3 M02 原始尝试为 CONSUMED_FAILED，失败根因为 Manager production runtime 缺少 cryptography，导致所有 Relay ingress fail-closed 为 aead_backend_unavailable。Child→ESP-NOW→Relay→MQTT 已由 seq 1863–1876 连续 gateway envelope 证明；path lease 尚未切换，canonical 停在 seq 1862。

只读复核通过后，仅报告是否满足下一决策门：
D1-N3W-P5-M02-AEAD-RUNTIME-DEPENDENCY-SUCCESSOR-REPAIR-20260809-01

在我原样批准该门之前，不得修改代码、branch、PR、workflow、Artifact、容器或任何物理现场状态。
```

---

## 15. 结束状态

```text
SESSION_ARCHIVE_READY = true
R3_M01_CLOSED = true
R3_M02_PREFLIGHT_CLOSED_PASS = true
R3_M02_EXECUTION_CLOSED_FAILED = true
R3_M02_REPLAY_ALLOWED = false
ROOT_CAUSE_CLOSED = true
PRODUCT_PACKAGING_FIX_REQUIRED = true
M03_ALLOWED = false
NEXT_GATE_APPROVED = false
NEXT_GATE_PENDING =
D1-N3W-P5-M02-AEAD-RUNTIME-DEPENDENCY-SUCCESSOR-REPAIR-20260809-01
```

本轮到此结束。下一对话从只读复核开始。
