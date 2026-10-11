# N3-W T1 Production Stack Staging
# Run #78 exact artifact / three-image payload binding
# 新会话交接文档 V1.0 — 2026-10-11

```text
HANDOFF_STANDARD_VERSION=1.0
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
```

> 本文符合 exact handoff process authority
> `4300890dff0ce63d5a547df21426e287d084d9ee` 下的
> `docs/development/NEW_CHAT_HANDOFF_STANDARD.md` 与
> `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md`。
>
> 如本文与 fresh exact repository / workflow / artifact / runtime evidence
> 冲突，以更高 authority 为准，并先 STOP 完成 rebind。

---

## 0. 会话切换结论

本轮已完成 KF-107 offline-image source repair，并在 exact product-source
head 上得到五门关键 CI PASS。按用户要求，本轮在 **Run #78 artifact 尚未
下载/绑定** 的位置停止；下一会话不重新复盘 staging 历史，只做 Run #78
exact artifact、三镜像 tar、payload 大小与 SHA256 的只读绑定复核。

```text
CURRENT_STAGE=N3W_T1_PRODUCTION_STACK_STAGING_KF107_OFFLINE_IMAGE_SOURCE_CI_CLOSED
CURRENT_STOP_POINT=RUN78_CI_PASS_ARTIFACT_BINDING_NOT_YET_PERFORMED
NEXT_ONE_GATE=N3W_T1_PRODUCTION_STACK_STAGING_RUN78_EXACT_ARTIFACT_THREE_IMAGE_PAYLOAD_BINDING_REVIEW_20261011_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

下一会话从 `NEXT_ONE_GATE` 开始，不自动进入 T1 preflight，不申请或 claim
`..._03` authorization。

---

## 1. 执行模式

### 1.1 高阶模型职责

- 维护 product route、exact source/run/artifact authority；
- 设计 gate、scope、authorization、rollback；
- 区分 source、CI、artifact、runtime、infrastructure 与 physical defect；
- 根据 low-order closure 做 PASS / FAIL / STOP 分类；
- 禁止因换会话而重新发明 executor 或扩大测试框架。

### 1.2 Codex 低阶执行职责

- 机械执行本文 exact DSL；
- 使用 GitHub / Git / hash / tar / bounded Python 等最低必要工具；
- 只读恢复 Run #78 workflow/artifact authority；
- 允许在本地临时工作区下载和解包 artifact 以计算 hash/size；
- 第一处 substantive mismatch 后 fail-closed STOP；
- 不修复、不重跑 CI、不访问 T1、不访问板卡、不进入下一 gate。

### 1.3 DSL execution semantics

```text
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false
```

### 1.4 标准交互循环

```text
高阶模型：rebind / gate / exact artifact authority
        ↓
Codex：只读 DSL compile → artifact inspection → closure
        ↓
高阶模型：复核 closure / 决定是否进入 fresh T1 preflight
```

本 gate 不需要 live mutation authorization。

---

## 2. Product North Star

当前产品路线：

```text
保留 Armbian / Docker / 网络基础设施
→ 温室业务软件可从 clean product state 一次性部署
→ Manager / Broker / Home Assistant 三服务生产配置可重复、可验证
→ staging 与 activation 分离
→ staging one-shot apply 不依赖 T1 外部 registry 网络
```

最终阶段目标：

```text
exact offline staging payload
→ fresh T1 read-only preflight
→ explicit one-shot staging authorization
→ staging PASS while all production services remain stopped
→ separately authorized production activation and acceptance
```

当前不得进入：

```text
T1 live staging apply
Broker/Manager/Home Assistant start
systemd activation enable/start
NetworkManager dispatcher install
reboot
board/USB/serial/Flash/NVS/RF
PR #541 merge
```

---

## 3. Frozen Authorities

### 3.1 Repository / exact-main

```text
REPOSITORY=chrenguo-stack/HomeAssistant
REPOSITORY_MAIN_AT_HANDOFF=d423211b6196c2f2f0f01dff072c4f877fbe58ee

PR=541
PR_STATE=OPEN_DRAFT
PR_MERGED=false
PR_BRANCH=plan/n3w-t1-full-fresh-install-from-zero-20261010

PR541_PRODUCT_SOURCE_HEAD=cb4131e47727d0cf7421133000c3a421c860a99b
PR541_DOC_ALIGNMENT_HEAD_BEFORE_HANDOFF=75907095e58d8174140029556f71794e8d330f83
PRODUCT_SOURCE_TO_DOC_ALIGNMENT_DELTA=DOCS_ONLY
PRODUCT_SOURCE_TO_DOC_ALIGNMENT_NON_DOC_CHANGE=false
```

`cb4131e...` 是 Run #78 的产品/source authority。交接文档提交本身会继续推进
PR 文档 HEAD，因此下一会话必须 fresh rebind PR current HEAD，并证明
`cb4131e... -> current HEAD` 没有新的 non-doc product/source change；若存在，
本 gate STOP。

### 3.2 Run #78 / CI authority

```text
STAGING_PAYLOAD_RUN_ID=38140472427
STAGING_PAYLOAD_RUN_NUMBER=78
STAGING_PAYLOAD_CONCLUSION=success
STAGING_PAYLOAD_EXPECTED_HEAD=cb4131e47727d0cf7421133000c3a421c860a99b

DEPLOYMENT_GATE_RUN_ID=38140472367
DEPLOYMENT_GATE_RUN_NUMBER=361
DEPLOYMENT_GATE_CONCLUSION=success

PRODUCTION_IMAGE_BINDING_RUN_ID=38140472442
PRODUCTION_IMAGE_BINDING_RUN_NUMBER=245
PRODUCTION_IMAGE_BINDING_CONCLUSION=success

MANAGER_STATE_BINDING_RUN_ID=38140472373
MANAGER_STATE_BINDING_RUN_NUMBER=101
MANAGER_STATE_BINDING_CONCLUSION=success

PUBLIC_REPOSITORY_SAFETY_RUN_ID=38140472387
PUBLIC_REPOSITORY_SAFETY_RUN_NUMBER=4083
PUBLIC_REPOSITORY_SAFETY_CONCLUSION=success
```

### 3.3 Candidate / artifact / image

Run #78 artifact metadata deliberately remains unbound at handoff:

```text
RUN78_ARTIFACT_ID=TBD_NEXT_GATE
RUN78_ARTIFACT_NAME=TBD_NEXT_GATE
RUN78_ARTIFACT_ZIP_SHA256=TBD_NEXT_GATE
RUN78_PAYLOAD_ARCHIVE_SIZE_BYTES=TBD_NEXT_GATE
RUN78_PAYLOAD_ARCHIVE_SHA256=TBD_NEXT_GATE
RUN78_PAYLOAD_MANIFEST_SHA256=TBD_NEXT_GATE
RUN78_EXECUTOR_SHA256=TBD_NEXT_GATE
RUN78_HOST_WRAPPER_SHA256=TBD_NEXT_GATE
```

Frozen Manager authority that the payload must preserve:

```text
MANAGER_IMAGE=local/greenhouse-manager:s20-511db028
MANAGER_TAR_SHA256=2ef0421d483334f6ef81c92beb1b6784174f069a4bde179ba615ce0b70435081
MANAGER_CONFIG_DIGEST=sha256:ef0f28c2fd339430a85acb6cb65158c71c61cd8fc3c6330c375da27d0f2440f1
MANAGER_OCI_TARGET_DIGEST=sha256:abd9560c978b69429eea734df216664ea643ed762a77777dcb816f5d537afad6
ARCH=linux/arm64
```

Expected external-image provenance/runtime contract:

```text
HA_UPSTREAM_DIGEST=sha256:0c73235a9140a9b02e4bf618d06d8c496b12ae70656ecddb0e02ad31ad122be4
HA_CONFIG_DIGEST=sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879
HA_LOCAL_RUNTIME_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
HA_PULL_POLICY=never

BROKER_UPSTREAM_DIGEST=sha256:3184566df484a083411a0e70e92c87a264b8f0648df632f10eb23d54d99f4549
BROKER_CONFIG_DIGEST=sha256:4c199d7c9d377d018313a2199f6839978f6fd2219c405ad664d0a830c14b9c7b
BROKER_LOCAL_RUNTIME_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
BROKER_PULL_POLICY=never
```

### 3.4 Successor / deployment material

```text
SUCCESSOR_AUTHORIZATION_ID=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_03
SUCCESSOR_AUTHORIZATION_STATE=NOT_GRANTED
SUCCESSOR_AUTHORIZATION_CLAIMED=false
SUCCESSOR_AUTHORIZATION_CONSUMED=false
```

### 3.5 Target host / runtime authority

Public handoff intentionally omits private T1 locator.

```text
TARGET_HOST_LOCATOR=PRIVATE_EVIDENCE_NOT_PUBLIC_REPO
TARGET_ARCH=aarch64
TARGET_DOCKER_VERSION_LAST_PROVEN=29.7.1
TARGET_COMPOSE_VERSION_LAST_PROVEN=5.4.0
TARGET_HOST_ACCESS_IN_NEXT_GATE=false
```

---

## 4. Current Live Baseline

The most recent live mutation was authorization `..._02`. It failed at the
Home Assistant registry pull timeout and the executor returned:

```text
TRANSACTION_RESULT=FAILED_ROLLBACK_PASS
ROLLBACK_STATUS=PASS
ROLLBACK_ERRORS=[]
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

The rollback contract re-proved the production baseline at transaction exit.
The last independent fresh read-only preflight before that transaction had
proven:

```text
DOCKER_CONTAINER_COUNT=0
DOCKER_VOLUME_COUNT=45
DOCKER_VOLUME_SET_SHA256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b

PROJECT_NETWORK_N3WFC4_PRIVATE_CONTAINERS=0
PROJECT_NETWORK_N3WFC4_SERVICES_CONTAINERS=0

TCP_1883=0
TCP_8883=0
TCP_18883=0
TCP_8123=0
TCP_47112=0
UDP_47111=0

GUARD_ACTIVE=true
GUARD_ENABLED=true
GUARD_EXACT=true

N3W_STATE_ROOT=absent
PRODUCTION_IMAGES=absent
PRODUCTION_SERVICES=stopped

MANAGER_DATABASE_QUICK_CHECK=ok
MANAGER_DATABASE_BUSINESS_ROWS=0
MANAGER_DATABASE_PROVENANCE_ROWS=1
MANAGER_DATABASE_SHA256=6db7069f2134be3b178d3238da2dfc199463d812dd6be318531611eaddc4c971

HISTORICAL_T1_ROOT_AVAILABLE_BYTES=6420955136
```

This runtime evidence is sufficient to classify the completed `..._02`
rollback, but **not** to skip a future fresh T1 preflight.

```text
FRESH_T1_READONLY_REBIND_BEFORE_ANY_T1_ACTION=true

BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
NVS_MUTATION=false
RF_EXECUTION=false
```

Failed-apply local/remote forensic material was intentionally retained by the
host wrapper. The next host-only Run #78 gate must not delete or mutate it.

---

## 5. Proven Current Facts

```text
FACT_PR541_OPEN_DRAFT=true
FACT_PR541_MERGED=false

FACT_KF107_OFFLINE_IMAGE_SOURCE_REPAIR_IMPLEMENTED=true
FACT_KF107_EXACT_PRODUCT_SOURCE_HEAD=cb4131e47727d0cf7421133000c3a421c860a99b

FACT_DEPLOYMENT_GATE_361=PASS
FACT_STAGING_PAYLOAD_78=PASS
FACT_PRODUCTION_IMAGE_BINDING_245=PASS
FACT_MANAGER_STATE_BINDING_101=PASS
FACT_PUBLIC_SAFETY_4083=PASS

FACT_RUN78_ARTIFACT_BINDING_PERFORMED=false
FACT_T1_ACCESSED_AFTER_RUN78=false
FACT_SUCCESSOR_03_GRANTED=false

FACT_AUTH_01_CONSUMED=true
FACT_AUTH_01_ROLLBACK=PASS
FACT_AUTH_02_CONSUMED=true
FACT_AUTH_02_ROLLBACK=PASS
FACT_AUTH_01_02_REPLAY_FORBIDDEN=true

FACT_PRODUCTION_SERVICE_START_FROM_01_02=false
FACT_BOARD_ACCESS_FROM_01_02=false
```

Inference is kept separate:

```text
INFERENCE_RUN78_PAYLOAD_EXPECTED_TO_BE_LARGE=true
INFERENCE_REASON=payload now carries Manager + Home Assistant + Broker image tars
INFERENCE_CURRENT_T1_DISK_CAPACITY_SUFFICIENT=UNPROVEN
```

---

## 6. Current Root Cause / Blockers

### Blocker A — Run #78 exact artifact authority not yet bound

```text
ROOT_CAUSE=NOT_A_PRODUCT_DEFECT;REQUIRED_ARTIFACT_BINDING_GATE_NOT_YET_EXECUTED
PROVEN_BY=USER_REQUESTED_SESSION_STOP_BEFORE_RUN78_ARTIFACT_REVIEW
SOURCE_DEFECT_PROVEN=false
RUNTIME_DEFECT_PROVEN=false
CURRENT_BLOCKER=true
```

Until this gate passes, the project must not claim that the newly green Run #78
payload is eligible for T1 preflight or live staging.

### Blocker B — KF-107 live revalidation still pending

```text
ROOT_CAUSE_PREDECESSOR=ONE_SHOT_APPLY_DEPENDED_ON_EXTERNAL_REGISTRY_PULL
SOURCE_REPAIR_CI=PASS
ARTIFACT_BINDING=PENDING
FRESH_T1_PREFLIGHT=PENDING
LIVE_REVALIDATION=PENDING
SOURCE_DEFECT_PROVEN_AND_REPAIRED=true
CURRENT_RUNTIME_DEFECT_PROVEN=false
```

---

## 7. Closed / Forbidden Routes

除非出现新的 direct counter-evidence，下一会话不得重新进入：

```text
AUTHORIZATION_01_REPLAY=CLOSED_FORBIDDEN:CONSUMED_FAILED_ROLLBACK_PASS
AUTHORIZATION_02_REPLAY=CLOSED_FORBIDDEN:CONSUMED_FAILED_ROLLBACK_PASS

LIVE_T1_REGISTRY_PULL_DURING_STAGING=CLOSED_FORBIDDEN:KF107
OLD_DIGEST_QUALIFIED_RUNTIME_REF_ASSUMPTION=CLOSED:DOCKER_SAVE_LOAD_DID_NOT_RESTORE_ADDRESSABLE_REF
AD_HOC_ZSH_PIPESTATUS_WRAPPER=CLOSED_FORBIDDEN:KF078
PRE_RUN78_PAYLOADS_FOR_NEW_LIVE_APPLY=CLOSED_FORBIDDEN:SUPERSEDED

PRODUCTION_SERVICE_START=FORBIDDEN_IN_CURRENT_STAGE
BOARD_ACCESS=FORBIDDEN_IN_CURRENT_STAGE
PR541_MERGE=FORBIDDEN_WITHOUT_SEPARATE_AUTHORIZATION
```

---

## 8. Authorization Ledger

```text
AUTHORIZATION=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_01
CLAIMED=true
CONSUMED=true
RESULT=FAILED_ROLLBACK_PASS_IMAGE_ID_ORACLE
REPLAY_PERMITTED=false
SUPERSEDED_BY=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_02

AUTHORIZATION=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_02
CLAIMED=true
CONSUMED=true
RESULT=FAILED_ROLLBACK_PASS_HOMEASSISTANT_PULL_TIMEOUT
REPLAY_PERMITTED=false
SUPERSEDED_BY=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_03

PROPOSED_AUTHORIZATION=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_03
GRANTED=false
CLAIMED=false
CONSUMED=false
REPLAY_PERMITTED=NOT_APPLICABLE_NOT_GRANTED
```

Run #78 artifact review is read-only and consumes no live authorization.

---

## 9. Rollback Authority

The next gate is host-only artifact inspection.

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_GATE
LIVE_RUNTIME_MUTATION=false
T1_ACCESS=false
BOARD_ACCESS=false
```

Temporary local artifact files may be created only as bounded evidence and may be
removed after their hashes/sizes are captured. They are not production/runtime
state.

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_PRODUCTION_STACK_STAGING_RUN78_EXACT_ARTIFACT_THREE_IMAGE_PAYLOAD_BINDING_REVIEW_20261011_01
```

### 10.1 Purpose

Bind the immutable artifact published by staging payload Run #78 to exact
repository/workflow authority, verify all published sidecars, prove the payload
contains exactly the expected three image tar artifacts with consistent
size/SHA256 metadata, and quantify payload disk/transport size before any T1
access.

### 10.2 Frozen inputs

```text
REPOSITORY=chrenguo-stack/HomeAssistant
REPOSITORY_MAIN_AT_HANDOFF=d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR=541
PRODUCT_SOURCE_HEAD=cb4131e47727d0cf7421133000c3a421c860a99b

RUN_ID=38140472427
RUN_NUMBER=78
EXPECTED_RUN_CONCLUSION=success

EXPECTED_AUTHORIZATION_ID=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_03
EXPECTED_AUTHORIZATION_CLAIMED=false
EXPECTED_AUTHORIZATION_CONSUMED=false

EXPECTED_IMAGE_TARS=
artifact/greenhouse-manager-arm64.tar
artifact/homeassistant-arm64.tar
artifact/broker-arm64.tar

EXPECTED_MANAGER_TAR_SHA256=2ef0421d483334f6ef81c92beb1b6784174f069a4bde179ba615ce0b70435081

HISTORICAL_T1_ROOT_AVAILABLE_BYTES=6420955136
```

### 10.3 Required proof / operations

```text
1. fresh rebind repository main + PR #541;
2. prove current PR still descends from PRODUCT_SOURCE_HEAD and all later changes are docs-only;
3. rebind Run #78: completed + success + exact head SHA;
4. list Run #78 artifacts and identify exactly one expected staging payload artifact;
5. record artifact ID/name/size/digest/expiry;
6. download the exact artifact to a bounded local temporary workspace;
7. verify GitHub artifact digest when supported;
8. verify payload-archive.sha256, executor.sha256, payload-manifest.sha256,
   host-wrapper.sha256 against actual files;
9. parse payload-manifest.json and require:
   source_head == PRODUCT_SOURCE_HEAD;
   authorization_id == ..._03;
   authorization_claimed == false;
   authorization_consumed == false;
   production_service_start == false;
   board_access == false;
10. inspect payload archive member list and verify all manifest file records
    by exact size + SHA256;
11. prove the three expected image tar members are present exactly once;
12. record each image tar size + SHA256;
13. require Manager tar SHA256 == frozen Manager SHA;
14. require HA/Broker tar SHA256 == payload manifest values;
15. rebind Run #78 job log and require:
    EXTERNAL_IMAGE_TAR_ROUNDTRIP=PASS;
    HOMEASSISTANT_TAR_SHA256 matches actual;
    BROKER_TAR_SHA256 matches actual;
    EXECUTOR_SHA256 matches actual;
    PAYLOAD_MANIFEST_SHA256 matches actual;
    PAYLOAD_ARCHIVE_SHA256 matches actual;
    PAYLOAD_BUILD=PASS;
16. inspect exact payload Compose/image-lock/executor contract:
    HA/Broker runtime refs are deterministic local tags;
    HA/Broker pull_policy == never;
    executor contains local production_image_load path;
    executor staging apply contains no live docker pull path;
17. record:
    artifact ZIP size;
    compressed payload archive size;
    payload archive total uncompressed member bytes;
    three image tar sizes;
    archive + uncompressed-payload extraction peak estimate;
18. compare archive + uncompressed payload bytes to
    HISTORICAL_T1_ROOT_AVAILABLE_BYTES only as a historical risk check.
    This MUST NOT replace a fresh T1 disk preflight;
19. emit closure and STOP.
```

### 10.4 PASS

```text
RUN78_EXACT_ARTIFACT_BINDING=PASS
THREE_IMAGE_TAR_BINDING=PASS
PAYLOAD_SIDECAR_BINDING=PASS
PAYLOAD_SIZE_MEASUREMENT=PASS
HISTORICAL_EXTRACTION_PEAK_LT_LAST_PROVEN_FREE_ROOT=true
READY_FOR_FRESH_T1_READONLY_PREFLIGHT=true
```

If the measured extraction peak is not below the last proven free-root value,
the gate must fail on disk-budget risk rather than relying on a later transfer
attempt.

### 10.5 FAIL

Examples:

```text
RUN78_EXACT_ARTIFACT_BINDING=FAIL_SOURCE_AUTHORITY_DRIFT
or
RUN78_EXACT_ARTIFACT_BINDING=FAIL_ARTIFACT_AMBIGUOUS
or
RUN78_EXACT_ARTIFACT_BINDING=FAIL_HASH_MISMATCH
or
RUN78_EXACT_ARTIFACT_BINDING=FAIL_THREE_IMAGE_TAR_SET
or
RUN78_EXACT_ARTIFACT_BINDING=FAIL_MANIFEST_AUTHORIZATION_BINDING
or
RUN78_EXACT_ARTIFACT_BINDING=FAIL_CI_LOG_BINDING
or
RUN78_EXACT_ARTIFACT_BINDING=FAIL_HISTORICAL_DISK_BUDGET_HARD

READY_FOR_FRESH_T1_READONLY_PREFLIGHT=false
STOP=true
```

Codex不得自动修复、重跑 CI、重新构建 payload 或进入 T1 preflight。

---

## 11. Hard Allowed / Forbidden Scope

Default：

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
LIVE_RUNTIME_MUTATION=false
```

### ALLOWED

```text
- read GitHub repository / PR / commit / workflow / job / log metadata;
- list and download exact Run #78 artifact;
- create a bounded local temporary workspace for artifact evidence;
- compute SHA256 and file sizes;
- list/read/extract artifact and tar members locally;
- use bounded local Python/shell solely for hash/tar/JSON inspection;
- delete only the gate-created local temporary workspace after closure.
```

### FORBIDDEN

```text
- any SSH/T1 access;
- any Docker action on T1;
- any production service start/restart/reload;
- any live staging apply;
- any authorization claim;
- any board/USB/serial/Flash/NVS/RF access;
- any CI rerun;
- any source repair or design change;
- any GitHub repository mutation inside this gate;
- PR #541 merge.
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=LOCAL_TEMPORARY_ARTIFACT_WORKSPACE_ONLY
```

---

## 12. Codex DSL Execution Contract

```text
ROLE:
Low-order executor.

This document is an executable DSL protocol.
A separately supplied Bash/Python executor is NOT required unless
this protocol explicitly says so.

Mechanically compile this DSL into the minimum necessary commands
using already-installed tools, then execute exactly the bounded gate.

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false

Do not repair.
Do not retry CI.
Do not access T1.
Do not enter the next gate.
```

```text
============================================================
0. EXECUTION / AUTHORIZATION STATUS
============================================================

EXECUTION_ID=
N3W_T1_PRODUCTION_STACK_STAGING_RUN78_EXACT_ARTIFACT_THREE_IMAGE_PAYLOAD_BINDING_REVIEW_20261011_01

AUTHORIZATION=NOT_APPLICABLE_READONLY_GATE
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

LIVE_RUNTIME_MUTATION=false
T1_ACCESS=false
BOARD_ACCESS=false

============================================================
1. FROZEN INPUTS
============================================================

REPOSITORY=chrenguo-stack/HomeAssistant
PR=541
PRODUCT_SOURCE_HEAD=cb4131e47727d0cf7421133000c3a421c860a99b
RUN_ID=38140472427
RUN_NUMBER=78
EXPECTED_AUTHORIZATION_ID=
N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_03

============================================================
2. HARD SCOPE
============================================================

ALLOW=GitHub read-only metadata/log/artifact access
ALLOW=bounded local artifact download/hash/tar/json inspection
DENY=repository mutation
DENY=CI rerun
DENY=T1/SSH
DENY=board access
DENY=repair
DENY=next gate

============================================================
3. FRESH REPOSITORY REBIND
============================================================

Read current main and PR #541.
Require PR OPEN_DRAFT and not merged.
Compare PRODUCT_SOURCE_HEAD -> current PR head.

If later delta contains any non-doc file:
  RESULT=FAIL_SOURCE_AUTHORITY_DRIFT
  STOP.

Record current main/head and docs-only delta.

============================================================
4. RUN #78 REBIND
============================================================

Read workflow run 38140472427.
Require:
  run_number=78
  status=completed
  conclusion=success
  head_sha=PRODUCT_SOURCE_HEAD

Otherwise STOP.

============================================================
5. ARTIFACT METADATA BINDING
============================================================

List Run #78 artifacts.
Identify exactly one staging payload artifact for PRODUCT_SOURCE_HEAD.
Require not expired.

Record:
  ARTIFACT_ID
  ARTIFACT_NAME
  ARTIFACT_SIZE_BYTES
  ARTIFACT_DIGEST
  CREATED_AT
  EXPIRES_AT

If zero/multiple/expired: STOP.

============================================================
6. DOWNLOAD + OUTER SIDECARS
============================================================

Download exact artifact to a fresh local temp directory.

Record actual SHA256 for:
  payload-archive.tar.gz
  payload-manifest.json if published outside archive, otherwise archive member
  host-wrapper.py

Read and verify:
  payload-archive.sha256
  executor.sha256
  payload-manifest.sha256
  host-wrapper.sha256

Every sidecar must equal actual content.

============================================================
7. PAYLOAD MANIFEST AUTHORITY
============================================================

Parse payload-manifest.json.

Require:
  source_head=PRODUCT_SOURCE_HEAD
  authorization_id=EXPECTED_AUTHORIZATION_ID
  authorization_claimed=false
  authorization_consumed=false
  production_service_start=false
  board_access=false

Record manager/homeassistant/broker tar SHA fields.

============================================================
8. PAYLOAD FILE-SET + THREE IMAGE TARS
============================================================

Inspect payload-archive.tar.gz without executing its contents.

Verify every manifest file record by exact path/size/SHA256.
Reject duplicate normalized paths.

Require exactly once:
  artifact/greenhouse-manager-arm64.tar
  artifact/homeassistant-arm64.tar
  artifact/broker-arm64.tar

For each, record exact size + SHA256.

Require Manager tar SHA ==
2ef0421d483334f6ef81c92beb1b6784174f069a4bde179ba615ce0b70435081

Require HA/Broker actual SHA == payload manifest values.

============================================================
9. RUN #78 LOG CROSS-BINDING
============================================================

Read Run #78 payload job logs.

Require:
  EXTERNAL_IMAGE_TAR_ROUNDTRIP=PASS
  PAYLOAD_BUILD=PASS

Extract logged:
  HOMEASSISTANT_TAR_SHA256
  BROKER_TAR_SHA256
  EXECUTOR_SHA256
  PAYLOAD_MANIFEST_SHA256
  PAYLOAD_ARCHIVE_SHA256

Require each logged value == downloaded artifact actual value.

============================================================
10. OFFLINE RUNTIME CONTRACT
============================================================

Read exact payload copies of:
  infra/n3w-t1/production/docker-compose.yml
  infra/n3w-t1/production/image-lock.json
  tools/n3w_t1_production_stack_staging.py

Require:
  HA local runtime image exact;
  Broker local runtime image exact;
  HA pull_policy=never;
  Broker pull_policy=never;
  image-lock retains exact upstream digest provenance;
  executor uses production_image_load/local docker load;
  executor staging path contains no live docker pull.

Mismatch => STOP.

============================================================
11. PAYLOAD SIZE REVIEW
============================================================

Record:
  artifact ZIP size
  compressed payload archive size
  total uncompressed payload member bytes
  Manager tar bytes
  HA tar bytes
  Broker tar bytes
  extraction_peak_estimate_bytes =
    compressed payload archive + total uncompressed payload member bytes

Historical comparison only:
  HISTORICAL_T1_ROOT_AVAILABLE_BYTES=6420955136

If extraction_peak_estimate_bytes >= historical value:
  RESULT=FAIL_HISTORICAL_DISK_BUDGET_HARD
  STOP.

Otherwise:
  HISTORICAL_EXTRACTION_PEAK_CHECK=PASS
  FRESH_T1_DISK_PREFLIGHT_STILL_REQUIRED=true

============================================================
12. HARD STOP
============================================================

Emit only the structured closure.
Do not access T1.
Do not mutate GitHub.
Do not repair.
Do not execute fresh T1 preflight.
```

---

## 13. Expected Closure

```text
=== N3W_T1_PRODUCTION_STACK_STAGING_RUN78_EXACT_ARTIFACT_THREE_IMAGE_PAYLOAD_BINDING_REVIEW_20261011_01 CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=NOT_APPLICABLE_READONLY_GATE
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

REPOSITORY_MAIN_CURRENT=
PR541_CURRENT_HEAD=
PRODUCT_SOURCE_HEAD=cb4131e47727d0cf7421133000c3a421c860a99b
PRODUCT_SOURCE_TO_CURRENT_HEAD_DOCS_ONLY=

RUN78_ID=38140472427
RUN78_NUMBER=78
RUN78_STATUS=
RUN78_CONCLUSION=
RUN78_HEAD_SHA=

ARTIFACT_ID=
ARTIFACT_NAME=
ARTIFACT_SIZE_BYTES=
ARTIFACT_DIGEST=
ARTIFACT_EXPIRED=

PAYLOAD_ARCHIVE_SIZE_BYTES=
PAYLOAD_ARCHIVE_SHA256=
PAYLOAD_MANIFEST_SHA256=
EXECUTOR_SHA256=
HOST_WRAPPER_SHA256=

MANIFEST_SOURCE_HEAD=
MANIFEST_AUTHORIZATION_ID=
MANIFEST_AUTHORIZATION_CLAIMED=
MANIFEST_AUTHORIZATION_CONSUMED=
MANIFEST_PRODUCTION_SERVICE_START=
MANIFEST_BOARD_ACCESS=

MANAGER_TAR_SIZE_BYTES=
MANAGER_TAR_SHA256=
HOMEASSISTANT_TAR_SIZE_BYTES=
HOMEASSISTANT_TAR_SHA256=
BROKER_TAR_SIZE_BYTES=
BROKER_TAR_SHA256=

THREE_IMAGE_TAR_SET_EXACT=
MANIFEST_FILE_RECORDS_EXACT=
CI_EXTERNAL_IMAGE_TAR_ROUNDTRIP=
CI_HASH_BINDING_EXACT=
OFFLINE_RUNTIME_CONTRACT_EXACT=

PAYLOAD_UNCOMPRESSED_MEMBER_BYTES=
EXTRACTION_PEAK_ESTIMATE_BYTES=
HISTORICAL_T1_ROOT_AVAILABLE_BYTES=6420955136
HISTORICAL_EXTRACTION_PEAK_CHECK=
FRESH_T1_DISK_PREFLIGHT_STILL_REQUIRED=true

LIVE_RUNTIME_MUTATION=false
T1_ACCESS=false
BOARD_ACCESS=false

RUN78_EXACT_ARTIFACT_BINDING=
READY_FOR_FRESH_T1_READONLY_PREFLIGHT=
NEXT_ROUTE=

STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

### PASS 后

```text
AFTER_PASS_NEXT_STAGE=N3W_T1_PRODUCTION_STACK_STAGING_OFFLINE_PAYLOAD_FRESH_T1_READONLY_PREFLIGHT
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=false
```

说明：fresh T1 **read-only preflight** 本身不需要 live mutation authorization；
只有该 preflight 后的 staging apply 才需要用户对 `..._03` 的明确授权。

### FAIL 后

```text
AUTO_REPAIR=false
AUTO_RETRY=false
RETURN_TO_HIGH_LEVEL_MODEL=true
```

不得自动 rerun CI 或重新构建 artifact。

---

## 15. KNOWN_FAILURES Updates

本轮新增/更新：

```text
KNOWN_FAILURES_UPDATE_REQUIRED=true

KF_ID=KF-107
DOMAIN=INFRASTRUCTURE
SYMPTOM=one-shot live staging depended on external registry; first offline save/load CI then lost digest-qualified addressable ref
ROOT_CAUSE=post-claim registry dependency proven; Docker save/load ref-preservation assumption disproven
FIX_OR_GUARD=exact upstream digest pull+verify -> deterministic local runtime tag -> save/remove/load -> exact local tag/config/platform verify; Compose pull_policy never; T1 staging local docker load only
STATUS=GUARDED_SOURCE_ARTIFACT_AND_LIVE_REVALIDATION_PENDING
```

底层造成 `..._02` GHCR pull 1200 s timeout 的网络原因仍为 `TBD`，不要把
KF-107 的架构修复扩大成未经证明的网络根因。

---

## 16. New Chat Start Prompt

```text
阅读：

docs/development/N3W_T1_PRODUCTION_STACK_STAGING_RUN78_EXACT_ARTIFACT_BINDING_NEW_CHAT_HANDOFF_V1.0_20261011.md

同时读取 exact handoff process authority：
4300890dff0ce63d5a547df21426e287d084d9ee

- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

并 fresh rebind：
- repository main
- PR #541
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_PROGRESS_20261011.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

每次回复先写：
主线任务：N3-W 温室环境监测系统产品化与首次配对验收
支线任务：保留 Armbian，全新部署 T1 温室软件
当前任务：Run #78 exact artifact / 三镜像 tar / payload 大小与 SHA256 绑定复核

本轮继续采用：
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true

当前只进入：
NEXT_ONE_GATE=
N3W_T1_PRODUCTION_STACK_STAGING_RUN78_EXACT_ARTIFACT_THREE_IMAGE_PAYLOAD_BINDING_REVIEW_20261011_01

必须先承认：
- product source authority = cb4131e47727d0cf7421133000c3a421c860a99b；
- staging payload Run #78 / ID 38140472427 已 PASS；
- Run #78 exact artifact ID / payload hashes / three-image tar sizes+SHA 尚未绑定；
- authorization ..._01 与 ..._02 已 consumed，永久禁止 replay；
- proposed authorization N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_03 尚未授予；
- 当前 gate 是 host-only / read-only artifact review；
- 不得访问 T1、不得访问板卡、不得 rerun CI、不得修改 source、不得 merge PR。

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

先 fresh rebind 当前 authority，然后机械执行 handoff 内 DSL；
完成 structured closure 后 STOP，不自动进入 fresh T1 preflight。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=KF107_OFFLINE_IMAGE_SOURCE_CI_PASS
CURRENT_STOP_POINT=RUN78_EXACT_ARTIFACT_BINDING_NOT_YET_PERFORMED

SOURCE_DEFECT_PROVEN=KF107_PREDECESSOR_DEFECT_PROVEN_AND_SOURCE_REPAIR_CI_PASS
CURRENT_BLOCKER=RUN78_ARTIFACT_AUTHORITY_UNBOUND

LIVE_SYSTEM_STATE=PREDECESSOR_02_FAILED_ROLLBACK_PASS_PRODUCTION_SERVICES_NOT_STARTED
FRESH_T1_REBIND_REQUIRED_BEFORE_ANY_T1_ACTION=true

REPOSITORY_MAIN_AT_HANDOFF=d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR541_PRODUCT_SOURCE_HEAD=cb4131e47727d0cf7421133000c3a421c860a99b
RUN78=38140472427
RUN78_CONCLUSION=success

AUTH_01=CONSUMED_NO_REPLAY
AUTH_02=CONSUMED_NO_REPLAY
AUTH_03=NOT_GRANTED

NEXT_ONE_GATE=N3W_T1_PRODUCTION_STACK_STAGING_RUN78_EXACT_ARTIFACT_THREE_IMAGE_PAYLOAD_BINDING_REVIEW_20261011_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

HANDOFF_STANDARD_VERSION=1.0
```

---

## 18. Handoff Compliance Audit

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_STANDARD_VERSION=1.0

EXECUTION_MODEL_EXPLICIT=PASS
HIGH_LEVEL_CODEX_ROLE_BOUNDARY=PASS
DSL_EXECUTION_SEMANTICS_EXPLICIT=PASS

PRODUCT_NORTH_STAR_PRESENT=PASS
FROZEN_AUTHORITIES_COMPLETE=PASS
CURRENT_LIVE_BASELINE_COMPLETE=PASS

PROVEN_FACTS_SEPARATED_FROM_INFERENCE=PASS
CURRENT_BLOCKERS_EXPLICIT=PASS
CLOSED_ROUTES_EXPLICIT=PASS

AUTHORIZATION_LEDGER_COMPLETE=PASS
CONSUMED_AUTH_REPLAY_GUARD=PASS
ROLLBACK_AUTHORITY_EXPLICIT=PASS

NEXT_ONE_GATE_EXPLICIT=PASS
NEXT_GATE_SCOPE_BOUNDED=PASS

ALLOWED_FORBIDDEN_SCOPE_EXPLICIT=PASS
EXPECTED_CLOSURE_PRESENT=PASS
AFTER_PASS_DOES_NOT_AUTO_EXECUTE=PASS

KNOWN_FAILURES_UPDATE_CLASSIFIED=PASS
NEW_CHAT_START_PROMPT_PRESENT=PASS
FINAL_FROZEN_STATE_PRESENT=PASS

HANDOFF_STATE_COMPLETENESS=PASS
HANDOFF_EXECUTION_SEMANTICS_COMPLETENESS=PASS

HANDOFF_READY_FOR_NEW_CHAT=true

=== END ===
```
