# N3-W T1 显式 Provisioning Authority Split P1 进度对齐（2026-10-13）

TASK=
`N3W_T1_EXPLICIT_DEVICE_PROVISIONING_COMMAND_AUTHORITY_SPLIT_SOURCE_REPAIR_P1`

## 0. 当前结论

```text
P1_SOURCE_IMPLEMENTED=true
P1_SOURCE_REVIEW=NOT_EXECUTED
P1_CI=PASS
P2=HOLD

T1_ACCESS=false
T1_MUTATION=false
R3_CLEANUP=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
AUTHORIZATION_08_GRANTED=false
```

本文件用于把当前会话已完成的 P1 源码与 CI 结果同步到 GitHub。
它不替代下一门独立源码复核，也不把 CI PASS 等价为 source review PASS。

## 1. Exact authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PR=541
PR_STATE=OPEN_DRAFT
PR_MERGED=false
PR_BASE_BRANCH=main
PR_BASE_HEAD=d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR_HEAD_BRANCH=plan/n3w-t1-full-fresh-install-from-zero-20261010

P1_PRECHANGE_REPOSITORY_HEAD=43809801862541a0b310424b2c8a1685f53ad733
P1_SOURCE_HEAD=e906d3d836fefe2bc2cafc0ff7877232974b5211
PRE_P1_PRODUCT_SOURCE_HEAD=3dbd9723063e1f5f14605b1bcf13bee4c54c84ab
```

`438098...` 到 `e906...` 的 P1 delta 只有 4 个文件：

```text
MOD host/greenhouse-manager/src/greenhouse_manager/bootstrap/device_firstboot.py
ADD host/greenhouse-manager/src/greenhouse_manager/bootstrap/device_provisioning_cli.py
MOD host/greenhouse-manager/tests/bootstrap/test_device_firstboot.py
ADD host/greenhouse-manager/tests/bootstrap/test_device_provisioning_cli.py
```

未修改 systemd、activation topology、R8 authorization ledger、firmware 或 T1 runtime。

## 2. P1 实现内容

P1 将原 `run_device_firstboot()` 混合 authority 拆为：

```text
inspect_device_provisioning()
start_device_provisioning()
resume_device_provisioning()
verify_device_ready()
```

冻结并实现的核心语义：

```text
BOOT_STARTS_NEW_PROVISIONING=false

START_AUTHORITY
!=
RESUME_AUTHORITY
!=
VERIFY_AUTHORITY
```

具体行为：

- `inspect_device_provisioning()` 在 UNPROVISIONED 状态只读，不创建 transaction root 或 transaction；
- `start_device_provisioning()` 是唯一允许创建全新 transaction 的 pure API；
- start 需要 exact confirmation：`START DEVICE PROVISIONING: YES`；
- start 要求 clone preflight 中 `clone_readback_verified=true`；
- start 在当前 boot 直接执行，不要求 reboot；
- `resume_device_provisioning()` 必须已有 transaction，缺失时绝不创建；
- resume 对已经进入 OS_IDENTITY 及以后阶段的 transaction 使用只读 live-host verifier；
- `verify_device_ready()` 在完成态重新读取当前 live host identity，并与持久 host binding 比较；
- copied completed disk 到另一 host 时应 fail-closed；
- legacy `run_device_firstboot()` 在 UNPROVISIONED 状态返回 `explicit_provisioning_start_required`，不能自动开始新 provisioning；
- provisioning completion 继续保持 `production_service_start=false`。

新增 pure CLI contract module：

```text
host/greenhouse-manager/src/greenhouse_manager/bootstrap/device_provisioning_cli.py
```

P1 未安装真实 host console entry point；host wrapper/systemd/activation 属 P2。

## 3. Transaction claim hardening

P1 新 transaction claim 采用：

```text
random claim file
→ O_EXCL/O_NOFOLLOW create
→ file fsync
→ exclusive hard-link to transaction.json
→ parent fsync
→ remove temporary claim file
```

目的：

- 保持“新 transaction 只能创建一次”；
- 避免直接 O_EXCL 创建 final transaction.json 后在断电时留下半写 JSON；
- 并发/已存在 final record 时 fail-closed。

该实现仍需下一门独立源码复核，不在本文件直接宣称 correctness closure。

## 4. Tests added / changed

P1 tests 覆盖：

```text
UNPROVISIONED status is read-only
wrong explicit confirmation causes zero mutation
clone readback evidence required before start
explicit start executes in same boot
duplicate start cannot create second transaction
resume requires existing transaction
resume does not rerun ensure_os_identity after OS_IDENTITY
resume rejects current-host drift
DEVICE_READY verify rechecks current live host
completed disk copied to host B fails closed
legacy wrapper cannot auto-start UNPROVISIONED
release/candidate/system-hash/owner/symlink guards remain
atomic claim temp symlink is rejected
CLI status/start confirmation routing
CLI without host adapter fails closed
```

## 5. CI final state

最终 exact source head：

```text
P1_SOURCE_HEAD=e906d3d836fefe2bc2cafc0ff7877232974b5211
```

关键 CI 全部 terminal SUCCESS：

```text
N3W T1 deployment gate CI
run=38333338398
SUCCESS

N3W T1 fresh install host-only CI
run=38333338482
SUCCESS

Public repository safety CI
run=38333338422
SUCCESS

greenhouse-manager CI
run=38333338438
SUCCESS

H0 H1 initialization and portable restore CI
run=38333338423
SUCCESS

N3W T1 fresh install exact ARM64 CI
run=38333338491
SUCCESS

N3W T1 fresh bootstrap deployable payload CI
run=38333338501
SUCCESS
```

```text
COMPLETED_NON_SUCCESS_COUNT=0
```

此前 head `46e70ffc...` 的 H0/H1 run `38332292492` 因 Ruff `SIM102` 在测试前失败；
该问题只属于 lint/style，已由 `e906d3d...` 等价逻辑改写修复。
最终 exact head 的 H0/H1 已 SUCCESS，不能把旧 lint failure 当成产品故障。

## 6. Current review state

```text
A1_LEGACY_COMMIT_COMPATIBILITY=CLOSED_FROM_PRIOR_REVIEW
A2_DURABLE_RECORD_OWNERSHIP=CLOSED_FROM_PRIOR_REVIEW
A3_ATOMIC_RECORD_WRITE=CLOSED_FROM_PRIOR_REVIEW

A4_COMPLETED_LIVE_HOST_BINDING=IMPLEMENTED_PENDING_INDEPENDENT_REVIEW

P1_AUTHORITY_SPLIT=IMPLEMENTED_PENDING_INDEPENDENT_REVIEW
P1_CI=PASS
P1_SOURCE_REVIEW=NOT_EXECUTED
```

不能在进入下一门前宣称：

```text
P1_SOURCE_REVIEW=PASS
A4=CLOSED
READY_FOR_P2=true
```

## 7. Current live baseline

本轮没有访问真实 T1、R3 或板卡。

```text
T1_RUNTIME_STATE=UNKNOWN_FRESH
MANAGER_STATE=UNKNOWN_FRESH
BROKER_STATE=UNKNOWN_FRESH
HOMEASSISTANT_STATE=UNKNOWN_FRESH

BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false
RF_EXECUTION=false
```

下一门是 source-only review，因此不需要为了复核而访问 T1。

## 8. Authorization state

仍保持：

```text
_03=CONSUMED_NO_REPLAY
_04/_05/_06/_07=SUPERSEDED_UNGRANTED
_08=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_08
AUTHORIZATION_08_GRANTED=false
```

P1 独立源码复核为 read-only gate，不需要新的 live/physical authorization。

## 9. STOP / next gate

本轮在此停止。

```text
NEXT_ONE_GATE=
N3W_T1_EXPLICIT_DEVICE_PROVISIONING_COMMAND_AUTHORITY_SPLIT_SOURCE_REPAIR_P1_INDEPENDENT_SOURCE_REVIEW

SOURCE_MUTATION=false
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
SYSTEMD_MUTATION=false
ACTIVATION_TOPOLOGY_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

下一门只独立复核 P1 exact source `e906d3d...` 的：

1. inspect/start/resume/verify authority 是否真正分离；
2. plain boot 是否仍可能隐式创建新 transaction；
3. transaction claim 的并发/断电/fail-closed 语义；
4. completed live-host binding 是否真正关闭原 A4；
5. pure CLI confirmation 是否不会扩大为 production activation；
6. P1 tests 是否覆盖关键负路径；
7. 是否存在 P1 引入的新 source blocker。

独立复核完成后 STOP；不得自动进入 P2。
