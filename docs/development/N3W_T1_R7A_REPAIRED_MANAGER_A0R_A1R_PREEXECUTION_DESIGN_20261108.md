# 温室环境监测系统（ESP32-C6）
# N3-W T1 R7A repaired Manager A0R / A1R preexecution design — 2026-11-08

```text
GATE=N3W_T1_R7A_REPAIRED_MANAGER_EXACT_ARTIFACT_AND_FRESH_A1_REACTIVATION_PREEXECUTION_20261108_01
STATUS=SOURCE_PREEXECUTION_IN_PROGRESS
REPOSITORY=chrenguo-stack/HomeAssistant
PR=800
PACKAGE_CONTROL_HEAD=4c883c02fbf3a64d944548a1dda8c7431d59ae61

REPAIRED_MANAGER_SOURCE_HEAD=7807271e4c48161f2fad96a7886fa4c24b038321
PACKAGE_RUN_ID=42480154921
PACKAGE_ARTIFACT_ID=13616844356
PACKAGE_ARTIFACT_DIGEST_SHA256=3c07406cd51258c8ef95f02e1e6cc80d09eb7235c218e7ead74a02a5521442fd
UPDATER_PYZ_SHA256=c0461a5097d8af0f8a6e7f3a175b7dadc82b55a436c6c229092262cd35521b44
MANAGER_TAR_SHA256=9746222b145df33d98056f1349456780377875534b28f633b736360c528a0c67
MANAGER_BUILD_IMAGE_ID=sha256:b1875c6ed969df108d2df768d61369a0c93956d146f284276b392c686c13a4f9
PACKAGE_BINDING=PASS
PRE_U1_V2_SIMULATION=PASS

LIVE_T1_MUTATION=false
SERVICE_RESTART=false
A1_REACTIVATION=false
PREPARE=false
USB_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

## 1. 结论

旧 A0/A1 execution package 已经属于历史一次性证据，不允许通过修改原目录来“复活”。本轮新增两个独立 successor：

1. **A0R**：只允许 Manager 从 `fresh-bf38e388497b` 升级到 repaired `fresh-7807271e4c48`。
2. **A1R**：只有在 A0R 产生 COMMITTED 的 V2 Manager transaction、fresh read-only 检查继续满足后，才允许重新安装/启用 OTA wiring。

两个 successor 均以 `live_execution_authorized=false` 提交；本轮不授权真实执行。

## 2. exact package authority

Manager package workflow run `42480154921` 三个 job 均 SUCCESS：

- source = SUCCESS
- exact-manager-slice = SUCCESS
- pre-u1-v2-simulation = SUCCESS

package artifact 是该 run 中唯一的 `n3w-t1-core-updater-manager-v2-7807271e4c48`，ID `13616844356`，digest 为 `sha256:3c07406c...`。package 内 updater、Manager tar、Manager build image ID 均由 workflow post-upload binding 冻结。

上游 repaired exact three-image artifact 仍固定为 run `42452239964` / artifact `13615963302`；历史 failed duplicate-name artifact 不具有 authority。A0R 对 package 使用 artifact ID metadata 验证，并继续验证 package 内 upstream artifact ID，避免同名 artifact 漂移。

## 3. A0R contract

```text
PREDECESSOR_MANAGER=local/greenhouse-manager:fresh-bf38e388497b
TARGET_MANAGER=local/greenhouse-manager:fresh-7807271e4c48
MUTATION_PROFILE=IMAGE_ONLY_V1
HOMEASSISTANT_MUTATION=false
BROKER_MUTATION=false
HOST_DAEMON_ACTIVATION=false
USB_MUTATION=false
ONE_APPLY_MAXIMUM=true
AUTOMATIC_RETRY=false
EXECUTOR_EXPLICIT_ROLLBACK=false
GENERIC_V2_INTERNAL_FAILURE_ROLLBACK=true
```

predecessor baseline 文件是基于已接受 bf38 IMAGE_ONLY 升级链推导的 preexecution candidate，不冒充 fresh live capture。真实 A0R 前必须重新只读检查：

- live Manager 必须仍为 bf38；
- Home Assistant / Broker 必须保持冻结 peer；
- OTA env/mount 与 A1 residue 必须不存在；
- USB-like disk 必须为 0；
- Generic V2 transaction 必须 terminal / recovery clear；
- live baseline 与 package baseline 必须 exact/fail-closed。

用户新提供的“重启后 Home Assistant 网页后台可登录”作为当前现场健康的新增操作员证据，但不等价于 repaired Manager 已部署，也不替代上述 fresh read-only gate。

## 4. A1R contract

A1R 的入口 Manager 被提升为 `fresh-7807271e4c48`，并强制读取 V2 Manager transaction：

```text
component=manager
status=COMMITTED
phase=COMMITTED
authorization_consumed=true
target.target_image_ref=local/greenhouse-manager:fresh-7807271e4c48
target_runtime_image_id=sha256:...
```

A1R 保留已有安全结构：

- single SSH epoch；
- source blob exact binding；
- preflight 不等待来掩盖既有 drift；
- activation/rollback restart 后使用 bounded container convergence；
- post activation 15 秒 same-container stability hold；
- Manager UID/GID 999:999；
- Manager 无 Docker socket、无 block device；
- runtime mount 只读；
- Broker continuity；
- USB=0；
- HA USB transaction / PREPARE state 不得出现；
- A1R 失败只回滚 wiring，不回滚 Manager image。

## 5. Authorization split

```text
A0R_PROPOSED_AUTH=N3W_T1_CORE_UPDATER_R7A_REPAIRED_MANAGER_A0R_LIVE_APPLY_20261108_01
A1R_PROPOSED_AUTH=N3W_T1_R7A_REPAIRED_MANAGER_A1R_LIVE_REACTIVATION_20261108_01

A0R_AUTH != A1R_AUTH
OLD_A0_AUTH_REPLAY=false
OLD_A1_AUTH_REPLAY=false
OLD_BOUNDARY_B_AUTH_REPLAY=false
```

真实顺序冻结为：

```text
fresh read-only A0R eligibility
→ explicit A0R authorization
→ bf38 → 780727
→ fresh read-only transaction/runtime validation
→ separate explicit A1R authorization
→ OTA wiring reactivation
→ 15 s same-container stability validation
→ later, separately authorized Boundary B PREPARE
```

## 6. Hard stop

本 gate 只允许 source/preexecution、测试和 GitHub 归档。不得执行 Manager deploy、service restart、A1 activation、PREPARE、USB 写入/格式化、board 操作或 merge。
