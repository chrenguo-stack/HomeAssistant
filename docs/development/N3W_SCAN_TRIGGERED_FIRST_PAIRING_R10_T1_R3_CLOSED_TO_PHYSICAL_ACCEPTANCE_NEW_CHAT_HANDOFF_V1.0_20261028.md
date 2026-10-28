# 温室环境监测系统（ESP32-C6）/ N3-W
# R10 T1 candidate R3 CLOSED_PASS → 首次配对 / 板端真实验收
# 新会话交接文档 V1.0 — 2026-10-28

```text
HANDOFF_TEMPLATE_VERSION=1.3
SOLE_VALID_HANDOFF_TEMPLATE_VERSION=1.3
OLDER_HANDOFF_TEMPLATE_VERSIONS=INVALID_FOR_NEW_HANDOFF_GENERATION
HISTORICAL_TEMPLATE_COPIES=HISTORICAL_EVIDENCE_ONLY
HISTORICAL_HANDOFF_STANDARD_DOES_NOT_AUTHORIZE_OLD_TEMPLATE=true
PROJECT_WORKING_CONTEXT_VERSION=1.1
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
HANDOFF_STANDARD_AUTHORITY=4300890dff0ce63d5a547df21426e287d084d9ee
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

> 本文只保存当前阶段增量。长期工作规则统一引用
> `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`。
> historical handoff standard authority 只提供 process/standard 规则；formal handoff 使用 current main V1.3 template。
> fresh repository/runtime/live/physical evidence 与本文冲突时，以 fresh 直接证据为准并先停止执行。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=R10_T1_CANDIDATE_R3_CLOSED_PASS_TO_PHYSICAL_FIRST_PAIR_ACCEPTANCE
CURRENT_STOP_POINT=R3_T1_UPGRADE_AND_POST_LIVE_FORENSIC_CLOSED_PASS_BEFORE_ANY_BOARD_ACCESS
NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_PHYSICAL_ACCEPTANCE_EXECUTION_20261028_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

本轮对话已把 T1 从 predecessor production runtime 安全升级到支持 scan-triggered first-registration 的 R9/R10 产品能力，并完成独立 post-live forensic。新会话不重跑 T1 upgrade，直接回到已经冻结的 R10 首次配对 / 板端真实验收路线。

---

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.1
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false

STAGE_SPECIFIC_OVERRIDE_COUNT=3
STAGE_OVERRIDES=
1) repository main 与已部署产品 source 分开记录：main 仍为 2fbd0e9c...；当前 T1/Board R9-R10 产品 source authority 为 e299c937...。
2) PR #720 / #721 均保持 OPEN/DRAFT；其 exact head 是本轮 source/recovery authority，不得因 docs-only handoff 提交改写已部署 product authority。
3) 下一 gate 的 physical design 已冻结；默认仍不访问 board。只有用户在新会话明确批准 exact physical authorization 后，才允许进入 board/USB/serial/readback/write。
```

---

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=节点WiFi已连接且未注册→LCD显示联机注册QR→手机系统相机打开节点本地页面→用户显式搜索T1→用户显式选择T1→节点对所选T1做TLS指纹校验→first-registration durable transaction→47112身份/来源绑定临时暴露→Setup Secret/HMAC/HKDF/credential delivery→Manager durable COMMIT→节点durable provisioned→LCD注册成功→正常MQTT/HA运行

FINAL_ACCEPTANCE_TARGET=在真实ESP32-C6与当前已升级T1上完成一次受控首次注册，并同时证明固件exact写入、flash readback、NVS不被写入步骤改变、无idle自动注册、显式T1选择、真实TLS/bootstrap、durable Manager COMMIT、47112成功后关闭、节点正常遥测以及Broker/Manager/HomeAssistant连续性

DEFERRED_OR_OUT_OF_SCOPE=第二次物理尝试;自动NVS清空;整机factory reset;T1重新部署;Manager强制recreate;动态漫游;节点退役新功能;PR合并
```

---

## 3. Frozen Authorities

### 3.1 Repository / product-source split

```text
REPOSITORY=chrenguo-stack/HomeAssistant

MAIN=2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e
MAIN_TREE=3064ab74ac96bbce44a0bf880ab53c7afc5bc134
MAIN_ROLE=CURRENT_REPOSITORY_MAIN_BEFORE_DOCS_ONLY_ALIGNMENT

R9_R10_PRODUCT_SOURCE=e299c937a7b89bb8a7b9a7432186ba46a416cd44
R9_R10_PRODUCT_SOURCE_TREE=e6e8290bdea3d9b09a70c598b4c3a9f5551540a7

PR720=https://github.com/chrenguo-stack/HomeAssistant/pull/720
PR720_STATE=OPEN_DRAFT
PR720_HEAD=4fd8212fc010b084d886f81ca09bb92696f0bbaf
PR720_ROLE=R3_T1_UPGRADE_EXACT_PACKAGE_SOURCE_AUTHORITY

PR721=https://github.com/chrenguo-stack/HomeAssistant/pull/721
PR721_STATE=OPEN_DRAFT
PR721_HEAD=47a334feac5fde699b004d0a0853a1af786fd271
PR721_ROLE=R2_FAILED_RESIDUE_RECONCILIATION_AUTHORITY
```

Docs-only handoff branch does not redefine any of the above product-source authorities. New session must fresh rebind main, PR #720 and PR #721 before execution.

### 3.2 Current T1 R3 artifact / deployment authority

```text
R3_ARTIFACT_ID=12802190308
R3_ARTIFACT_NAME=n3w-r10-t1-upgrade-4fd8212fc010
R3_ARTIFACT_DIGEST=sha256:cd49b7a2df1df3b9740faa51d1f59dff98e7375a49e0f922a5dc49905ac030af

R3_MANIFEST_SHA256=68eb56dfc0a60ace97c6647d745322ba08121c33627b7d07b7929c13d55573aa
R3_MANAGER_TAR_SHA256=5d580f1536c8817dfe97cdba4c3a3e5474dfc3a007a4880344da06a04d4b56fd
R3_EXECUTOR_SHA256=0fffa320e9c1bbe98e2e037d7ca8149a5fa1be989989e3d19d30088e5c42fbeb
R3_DISPATCHER_SHA256=c49267193b4a530caf7330f4c4a51a100d02bf487681f5de1dfef42d27c4ddfc

DEPLOYED_T1_MANAGER_IMAGE=local/greenhouse-manager:fresh-e299c937a7b8
DEPLOYED_T1_MANAGER_RUNTIME_ID=sha256:9675821a1445b6711549cbee424299dea7f0b35795018954d3cb3b61da7af7f4
R10_TRANSACTION_SHA256=a6f667da61060d8abb7b8b38a5d90950b9bf7027d5f4e9f3c971071f7f4f5f05
```

### 3.3 R9 board firmware authority

```text
R9_WORKFLOW_RUN_ID=40612774339
R9_ARTIFACT_ID=12783234959
R9_ARTIFACT_NAME=n3w-scan-first-pair-r9-e299c937-exact-source
R9_ARTIFACT_DIGEST=sha256:6b31001da3a4dff44f8c8cf605b885bcafcfd084d35969351938aa4904cc9995
R9_ARTIFACT_EXPIRES_AT=2026-11-27T01:09:52Z

R9_RELEASE_BUNDLE_SHA256=b30bede249c90d4a50c9d3d779219bf9bf84a91960ec2a67332ef895e6a07dc1
R9_MANIFEST_SHA256=8db79ea5c7ac3b3c4b97a7852bf39447ff2f14d45880d4c5a0d8e4d5805cdf05
R9_FIRMWARE_BIN_SHA256=fe11f5a81ce83e97fc0834114486a9cace26624977f9c4e0104c71687f4cc7be
R9_FIRMWARE_FACTORY_BIN_SHA256=b734c343b3caf725c3991e6dc408b471a607f0c10cfe641346a78228b65c3bbf
R9_FACTORY_IMAGE_SIZE_BYTES=1525680

R9_FACTORY_IMAGE_START=0x000000
R9_FACTORY_IMAGE_END_EXCLUSIVE=0x1747b0
R9_NVS_OFFSET=0x790000
R9_NVS_SIZE=0x070000
R9_FACTORY_OVERLAPS_NVS=false
```

Only the exact reviewed `firmware.factory.bin` is eligible for the first physical run. Same-source rebuilds and flat release ZIP `flash_args` are not interchangeable authority.

### 3.4 Other required authority

```text
OTHER_REQUIRED_AUTHORITY=
docs/adr/0011-n3w-scan-triggered-first-registration.md;
docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_PHYSICAL_ACCEPTANCE_DESIGN_AND_READONLY_PREFLIGHT_20261028.md;
docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_T1_CANDIDATE_UPGRADE_DESIGN_AND_READONLY_PREFLIGHT_20261028.md;
docs/development/N3W_CURRENT_STATE.md;
docs/development/N3W_CURRENT_STATE_INDEX.md;
docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
```

The physical-acceptance design document is currently carried on the R10 stacked source/docs line and must be read from an exact ref that contains it if it is not yet on main.

---

## 4. Current Live Baseline

Latest direct post-R3 evidence:

```text
MANAGER_STATE=RUNNING_TARGET_R9_R10_CAPABLE
MANAGER_IMAGE=local/greenhouse-manager:fresh-e299c937a7b8
MANAGER_RUNTIME_ID=sha256:9675821a1445b6711549cbee424299dea7f0b35795018954d3cb3b61da7af7f4
MANAGER_RESTART_STATE=REQUIRES_FRESH_READONLY_RECHECK_BEFORE_PHYSICAL_RUN

BROKER_STATE=RUNNING_CONTINUITY_PASS
BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
BROKER_RESTART_STATE=REQUIRES_FRESH_READONLY_RECHECK_BEFORE_PHYSICAL_RUN

HOMEASSISTANT_STATE=RUNNING
HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
HOMEASSISTANT_RESTART_STATE=REQUIRES_FRESH_READONLY_RECHECK_BEFORE_PHYSICAL_RUN

REGISTRATION_GUARD_STATE=active/enabled/loaded
PAIRING_WINDOW=CLOSED
TCP_47110_LISTENERS=1
UDP_47111_LISTENERS=1
TCP_47112_LISTENERS=0

DATABASE_INTEGRITY=ok
FIRST_REGISTRATION_TABLE_PRESENT=true
CURRENT_REGISTRATION_COUNT=1
UNRESOLVED_FIRST_REGISTRATION=0

REGISTRATION_TLS_PRESENT=true
TRUSTED_LAN_STATE_PRESENT=true
R2_HISTORY_PRESENT=true

BOARD_TARGET_STATE=UNKNOWN_FRESH
BOARD_POWER_STATE=UNKNOWN_FRESH
BOARD_WIFI_STATE=UNKNOWN_FRESH
BOARD_PRODUCT_REGISTRATION_STATE=UNKNOWN_FRESH
BOARD_PENDING_ACK_STATE=UNKNOWN_FRESH

APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false
BOARD_ACCESS=false
```

The next gate must freshly recheck T1 continuity and target-board starting state. Historical “board is clean/unregistered” assumptions are not accepted.

---

## 5. Proven Current Facts

```text
FACT_1=R3_T1_CANDIDATE_UPGRADE_EXECUTOR_RETURNED_PASS_COMMITTED
FACT_2=R3_LIVE_AUTHORIZATION_IS_CONSUMED_AND_NON_REPLAYABLE
FACT_3=INDEPENDENT_POST_LIVE_FORENSIC_CONFIRMED_TARGET_MANAGER_RUNNING
FACT_4=BROKER_CONTINUITY_PASS_AND_HOMEASSISTANT_IMAGE_UNCHANGED
FACT_5=REGISTRATION_GUARD_ACTIVE_ENABLED_LOADED
FACT_6=47110_TCP_AND_47111_UDP_LISTEN_AND_47112_TCP_IS_IDLE_CLOSED
FACT_7=PAIRING_WINDOW_IS_CLOSED
FACT_8=DATABASE_INTEGRITY_OK_FIRST_REGISTRATION_TABLE_PRESENT_CURRENT_REGISTRATION_COUNT_1_UNRESOLVED_0
FACT_9=F4_R10_SUCCESSOR_BINDING_PASS
FACT_10=ALL_SIX_SUCCESSOR_LIVE_FILES_EXACTLY_MATCH_R3_MANIFEST
FACT_11=F4_INSTALLED_FILES_BINDINGS_FOR_COMPOSE_SERVICES_DISPATCHER_PASS
FACT_12=R2_FAILED_UPGRADE_REMAINS_HISTORICAL_FAIL_EVIDENCE
FACT_13=R2_FAILED_RESIDUE_RECONCILIATION_CLOSED_PASS_AND_HISTORY_PRESERVED
FACT_14=NO_BOARD_USB_SERIAL_FLASH_OR_NVS_ACTION_OCCURRED_DURING_R3_T1_ROUTE
FACT_15=R9_FACTORY_IMAGE_DOES_NOT_OVERLAP_NVS
FACT_16=R10_PHYSICAL_ACCEPTANCE_DESIGN_IS_ALREADY_FROZEN
FACT_17=KF129_REMAINS_OPEN_UNTIL_REAL_FIRST_PAIR_PHYSICAL_ACCEPTANCE
FACT_18=KF133_RECONCILIATION_BACKUP_MODE_FALSE_STOP_IS_GUARDED
```

Inference that must not be promoted before fresh physical evidence:

```text
INFERENCE_TARGET_BOARD_IS_WIFI_READY_UNREGISTERED=UNKNOWN
INFERENCE_TARGET_BOARD_HAS_NO_PENDING_ACK=UNKNOWN
INFERENCE_CURRENT_T1_RESTART_COUNTS_UNCHANGED_SINCE_POSTLIVE=UNKNOWN_FRESH
INFERENCE_R9_ARTIFACT_IS_STILL_DOWNLOADABLE_AT_EXECUTION_TIME=REQUIRES_FRESH_CHECK
```

---

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=1
CURRENT_BLOCKER=REAL_PHONE_SCAN_PLUS_REAL_ESP32C6_FIRST_REGISTRATION_PHYSICAL_ACCEPTANCE_NOT_YET_PROVEN
ROOT_CAUSE=NOT_APPLICABLE:REMAINING_ACCEPTANCE_STAGE
PROVEN_BY=R3_T1_UPGRADE_CLOSED_PASS_PLUS_R10_PHYSICAL_DESIGN
SOURCE_DEFECT_PROVEN=false
RUNTIME_DEFECT_PROVEN=false
```

KF-129 is still OPEN only because the replacement Manager-owned product path has not yet completed real end-to-end physical acceptance. R3 T1 deployment alone does not close KF-129.

---

## 7. Closed / Forbidden Routes

```text
R1_ARTIFACT_12792592683=CLOSED_SUPERSEDED_DO_NOT_EXECUTE
R2_ARTIFACT_12795906971=CLOSED_FAILED_HISTORICAL_DO_NOT_EXECUTE
BAD_R3_ARTIFACT_12801331456=CLOSED_SUPERSEDED_DO_NOT_EXECUTE
R2_LIVE_AUTHORIZATION_REPLAY=CLOSED_CONSUMED
R2_RECONCILIATION_AUTHORIZATION_REPLAY=CLOSED_CONSUMED
R3_LIVE_AUTHORIZATION_REPLAY=CLOSED_CONSUMED
R3_T1_UPGRADE_RERUN=CLOSED_ALREADY_COMMITTED
MANAGER_FORCE_RECREATE_PAIRING=CLOSED_KF129
OUT_OF_BAND_COMPOSE_PAIRING_OVERRIDE=CLOSED_KF129
MANUAL_ENGINEERING_47112_OPEN_AS_PRODUCT_ACCEPTANCE=CLOSED
ERASE_FLASH_OR_NVS_TO_MANUFACTURE_CLEAN_BOARD=CLOSED
FLAT_RELEASE_ZIP_FLASH_ARGS=CLOSED_NOT_EXECUTABLE_AUTHORITY
MANUAL_SETUP_SECRET_COPY_TO_PHONE_OR_T1=CLOSED_PRODUCT_PATH_FORBIDS
MULTI_T1_AUTO_SELECTION=CLOSED_USER_SELECTION_REQUIRED
AUTOMATIC_SECOND_PHYSICAL_ATTEMPT_AFTER_TERMINAL_FAILURE=CLOSED
```

---

## 8. Authorization Ledger

Historical/relevant authorizations:

```text
AUTHORIZATION=N3W_R10_T1_CANDIDATE_UPGRADE_R2_20261028_01
CLAIMED=true
CONSUMED=true
RESULT=FAIL_ROLLBACK_FAILED_HISTORICAL
REPLAY_PERMITTED=false
SUPERSEDED_BY=R3_ROUTE

AUTHORIZATION=N3W_R10_FAILED_RESIDUE_RECONCILE_R2_20261028_01
CLAIMED=true
CONSUMED=true
RESULT=PASS_ARCHIVED_FAILED_RESIDUE
REPLAY_PERMITTED=false
SUPERSEDED_BY=NONE

AUTHORIZATION=N3W_R10_T1_CANDIDATE_UPGRADE_R3_STAGING_20261028_01
CLAIMED=true
CONSUMED=true
RESULT=PASS_EXACT_ARTIFACT_STAGED
REPLAY_PERMITTED=false
SUPERSEDED_BY=R3_LIVE

AUTHORIZATION=N3W_R10_T1_CANDIDATE_UPGRADE_R3_20261028_01
CLAIMED=true
CONSUMED=true
RESULT=PASS_COMMITTED
REPLAY_PERMITTED=false
SUPERSEDED_BY=NONE
```

Next physical execution:

```text
PROPOSED_AUTHORIZATION=NEW_R10_PHYSICAL_ACCEPTANCE_ONE_SHOT_AUTHORIZATION_TO_BE_BOUND_IN_NEW_CHAT
GRANTED=false
AUTHORIZATION_SCOPE=ONE_EXACT_R9_FACTORY_ARTIFACT_PLUS_ONE_EXACT_OPERATOR_CONFIRMED_ESP32C6_TARGET_PLUS_ONE_FIRST_REGISTRATION_ACCEPTANCE_RUN
AUTHORIZATION_CONSUMPTION_BOUNDARY=FIRST_BOARD_WRITE_BEGINS
```

Do not infer that any older board-write authorization remains valid merely because it was historically unconsumed. New chat must bind a fresh exact authorization to current artifact + current target.

---

## 9. Rollback Authority

The next gate includes a board write only after fresh prechecks and explicit authorization.

```text
ROLLBACK_BASELINE=FRESH_PRIVATE_PREWRITE_FACTORY_RANGE_BACKUP_PLUS_FRESH_PRIVATE_FULL_NVS_BACKUP
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=true
ROLLBACK_AUTHORITY_PATH_OR_ID=PRIVATE_OPERATOR_EVIDENCE_NOT_PUBLIC_GITHUB
RESTART_SCOPE_ALLOWED=NO_T1_SERVICE_RESTART_FOR_NORMAL_PATH
SECOND_ATTEMPT_ALLOWED=false
ROLLBACK_FAILURE_CLASS=ROLLBACK_INCOMPLETE
```

Rollback semantics:

```text
prechecks fail
→ no board write
→ STOP

board write / immediate preboot readback fails
→ restore only exact overwritten factory-image range from private prewrite backup
→ verify restored bytes
→ leave NVS untouched
→ STOP

R9 image boots but first-registration later fails
→ do not automatically restore firmware
→ do not clear NVS
→ do not clear Manager transaction state
→ freeze evidence
→ STOP for root-cause review
```

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_PHYSICAL_ACCEPTANCE_EXECUTION_20261028_01
```

### Purpose

Use the already-frozen R10 physical procedure to run exactly one real-board first-registration acceptance after fresh authority/precondition checks. This gate must prove the exact board image/write/NVS boundary and the real phone-scan → explicit T1 selection → real ESP32-C6 TLS/bootstrap → durable Manager COMMIT → normal runtime path.

It does not authorize a second attempt, NVS reset, T1 repair/redeploy, source repair or PR merge.

### Inputs

```text
INPUT_1=FRESH_REPOSITORY_MAIN_PR720_PR721_REBIND
INPUT_2=R10_PHYSICAL_ACCEPTANCE_DESIGN_DOC_EXACT_SOURCE
INPUT_3=R9_ARTIFACT_ID_12783234959
INPUT_4=R9_FACTORY_IMAGE_SHA256_b734c343b3caf725c3991e6dc408b471a607f0c10cfe641346a78228b65c3bbf
INPUT_5=CURRENT_T1_R3_COMMITTED_RUNTIME
INPUT_6=OPERATOR_CONFIRMED_EXACT_ESP32C6_TARGET
INPUT_7=INSTALLED_ESPTOOL_V5_COMMAND_AUTHORITY
```

### Operations

```text
1. fresh rebind repository main, PR #720, PR #721, R9 artifact availability and exact physical-design document.
2. fresh T1 readonly preflight:
   - Manager/Broker/HomeAssistant healthy;
   - target Manager exact;
   - registration guard/trusted-LAN healthy;
   - pairing idle CLOSED;
   - 47112 closed;
   - no unresolved current first-registration intent blocking the target;
   - capture container identity/restart baselines;
   - no force-recreate/Compose override path.
3. before board access, present the exact physical authorization scope and obtain explicit user approval if not already granted in the new chat.
4. bind one operator-confirmed ESP32-C6 target; USB port is locator only, not identity.
5. read-only board/security precheck:
   - ESP32-C6;
   - 8 MB flash;
   - Secure Boot disabled;
   - Flash Encryption disabled;
   - exactly one selected target;
   - determine board Wi-Fi/product-registration/pending-ACK starting state without destructive reset.
6. require Wi-Fi-connected + genuinely unregistered + no higher-priority pending final-ACK recovery. Any mismatch STOP; do not erase NVS.
7. fresh download/reverify exact R9 artifact; only exact firmware.factory.bin may be written.
8. immediately before first write, capture private exact overwritten-range backup and full NVS backup with byte count + SHA-256.
9. write exact merged factory image at offset 0 without erase-flash/NVS erase and without application boot before readback.
10. preboot read back exact factory-covered range and require exact factory SHA-256.
11. preboot read NVS again and require byte-identical SHA-256 to prewrite NVS.
12. only after both proofs PASS, allow application boot.
13. prove first-boot baseline:
    - normal boot/LCD;
    - Wi-Fi reconnect;
    - unregistered;
    - registration QR visible;
    - no idle auto T1 registration;
    - T1 still no new transaction and 47112 closed.
14. user scans LCD registration QR with phone system camera; do not expose/publish raw QR payload.
15. explicit search; observe product-safe T1 candidate label(s); require explicit candidate click; no auto-selection.
16. observe accepted 47110 durable first-registration attempt before 47112 exposure.
17. real ESP32-C6 performs TLS leaf-fingerprint verification and Setup-Secret bootstrap.
18. require pairing/credential delivery/final ACK and Manager durable COMMIT.
19. require 47112 to close after COMMIT.
20. require node durable provisioned state, commit-bound LCD registration success, then normal 已联网 behavior.
21. require post-pair MQTT/Manager data advance and Broker/Manager/HomeAssistant continuity against pre-run baselines.
22. capture public-safe PASS/FAIL evidence; keep raw board identity, raw pairing IDs, scan token, Setup Secret, credentials, NVS/backups private.
23. STOP. Do not auto-enter any retry/repair/merge gate.
```

### PASS / FAIL / STOP

```text
PASS_IF=EXACT_R9_FACTORY_WRITE_AND_READBACK_PASS_AND_NVS_UNCHANGED_DURING_FLASH_AND_WIFI_CONNECTED_UNREGISTERED_PRESTATE_PASS_AND_IDLE_NO_AUTO_REGISTRATION_PASS_AND_REAL_QR_PHONE_PAGE_PASS_AND_EXPLICIT_T1_SELECTION_PASS_AND_REAL_ESP32C6_TLS_BOOTSTRAP_PASS_AND_DURABLE_ATTEMPT_PRECEDES_47112_AND_MANAGER_COMMIT_PASS_AND_NODE_DURABLE_PROVISIONED_AND_LCD_SUCCESS_COMMIT_BOUND_AND_47112_CLOSES_AND_MQTT_ADVANCES_AND_T1_STACK_CONTINUITY_PASS

FAIL_IF=ANY_EXACT_ARTIFACT_OR_TARGET_OR_SECURITY_OR_PRESTATE_MISMATCH_OR_FLASH_READBACK_MISMATCH_OR_NVS_CHANGED_DURING_FLASH_OR_WIFI_PRECONDITION_MISMATCH_OR_ALREADY_PROVISIONED_OR_QR_MISSING_OR_USER_SELECTION_BYPASSED_OR_TLS_BOOTSTRAP_FAIL_OR_47112_OPENS_BEFORE_DURABLE_ATTEMPT_OR_WRONG_IDENTITY_SOURCE_MUTATES_STATE_OR_MANAGER_COMMIT_UNPROVEN_OR_LCD_SUCCESS_PREMATURE_OR_47112_REMAINS_OPEN_OR_T1_STACK_CONTINUITY_BREAKS

STOP_BOUNDARY=FIRST_TERMINAL_PASS_OR_FIRST_SUBSTANTIVE_FAILURE

AUTO_EXECUTE_NEXT_GATE=false
```

---

## 11. Hard Allowed / Forbidden Scope

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

Before explicit physical authorization:

```text
- fresh GitHub main/PR/artifact/design authority rebind
- T1 read-only runtime/database/listener/container inspection
- exact physical authorization preparation
```

After explicit physical authorization, only inside the same gate:

```text
- exact one-board identity/security read-only precheck
- private factory-range + NVS prewrite backups
- one exact R9 firmware.factory.bin write to offset 0
- preboot factory-range and NVS readbacks
- controlled first application boot
- one real phone-scan / explicit T1-selection / first-registration run
- public-safe evidence capture
- bounded overwritten-range restore only if write/preboot readback fails
```

### FORBIDDEN

```text
- replaying any consumed R2/R3 authorization
- rerunning T1 candidate upgrade
- deleting R2 history or R3 transaction/workspace
- Manager force-recreate or out-of-band Compose override
- T1 service repair/redeploy during physical gate
- erase-flash
- erase-region on NVS
- whole-NVS reset
- flat ZIP flash_args
- same-source unreviewed firmware rebuild substitution
- automatic second board attempt
- manually opening engineering 47112 as product acceptance
- manual Setup Secret transfer
- fake second T1 deployed only to force multi-T1 branch
- source repair
- PR merge
```

```text
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=PRIVATE_OPERATOR_BOARD_BACKUPS_AND_PUBLIC_SAFE_ACCEPTANCE_SUMMARY_ONLY
```

---

## 12. Execution Contract

```text
EXECUTOR=HIGH_LEVEL_MODEL_PLUS_MAC_TERMINAL_AND_MANUAL_PHYSICAL_STEPS
EXECUTION_METHOD=mac-terminal+manual-physical
DIRECT_CODE_SUPPLIED=false
DSL_COMPILATION_USED=true

CI_POLL_MAX=3
CI_PENDING_DIRECT_LINKS_REQUIRED=true
CI_ALL_GREEN_CONTINUE_REQUIRED_REVIEW=true
SAME_GATE_LOW_RISK_REPAIR_CONTINUE=false
```

Execution discipline:

- first perform fresh read-only GitHub/T1 checks;
- physical authorization must be explicit and exact before board access/write;
- Mac Terminal commands must contain no comments;
- use the installed esptool v5 help/current CLI as command-spelling authority;
- USB port is only a locator; confirm target silicon identity before mutation;
- use no-reset/no-boot sequence until the post-write readback and NVS-unchanged checks complete;
- first substantive mismatch STOPs the gate;
- no automatic repair/retry;
- do not infer failure from missing logs when socket/database/durable state provides stronger evidence.

---

## 13. Expected Closure

```text
=== N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_PHYSICAL_ACCEPTANCE_EXECUTION_20261028_01 CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=
AUTHORIZATION_CLAIMED=
AUTHORIZATION_CONSUMED=

FRESH_MAIN=
PR720_HEAD=
PR721_HEAD=

R9_ARTIFACT_ID=
R9_FACTORY_IMAGE_SHA256=
R9_ARTIFACT_REVERIFY=

T1_MANAGER_IMAGE=
T1_REGISTRATION_GUARD_READY=
T1_TRUSTED_LAN_READY=
T1_IDLE_47112_CLOSED=
T1_PREEXISTING_ACTIVE_TRANSACTION=

BOARD_TARGET_BOUND=
BOARD_CHIP=
BOARD_FLASH_SIZE=
BOARD_SECURE_BOOT_DISABLED=
BOARD_FLASH_ENCRYPTION_DISABLED=
BOARD_WIFI_PRESTATE=
BOARD_PRODUCT_REGISTRATION_PRESTATE=
BOARD_PENDING_ACK_PRESTATE=

PREWRITE_FACTORY_RANGE_BACKUP=
PREWRITE_NVS_BACKUP=
FACTORY_WRITE=
FACTORY_PREBOOT_READBACK=
NVS_UNCHANGED_PREBOOT=

FIRST_BOOT=
REGISTRATION_QR=
IDLE_AUTO_REGISTRATION_ABSENT=
EXPLICIT_T1_SELECTION=
DURABLE_ATTEMPT_BEFORE_47112=
REAL_TLS_BOOTSTRAP=
MANAGER_COMMIT=
NODE_DURABLE_PROVISIONED=
LCD_COMMIT_BOUND_SUCCESS=
POST_SUCCESS_47112_CLOSED=
POST_PAIR_MQTT_ADVANCE=
T1_STACK_CONTINUITY=

LIVE_RUNTIME_MUTATION=
BOARD_ACCESS=
FLASH_MUTATION=
NVS_MUTATION=

R10_PHYSICAL_ACCEPTANCE=
KF129=
NEXT_ROUTE=
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=R10_PHYSICAL_ACCEPTANCE_CLOSURE_AND_GITHUB_ALIGNMENT
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=ANY_FURTHER_MUTATION_OR_MERGE

AUTO_REPAIR_AFTER_FAIL=false
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

A PASS may make KF-129 eligible for closure review, but the executor must not silently edit KNOWN_FAILURES or merge PRs inside the physical gate.

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=true
EXISTING_KF_GUARD_USED=KF-129,KF-131,KF-132,KF-133
NEW_KF_REQUIRED=true
```

New current-session guard already added on the docs alignment branch:

```text
KF_ID=KF-133
SYMPTOM=R2 failed-residue reconciliation preclaim false-STOP on current_static_not_predecessor_exact although live bytes were exact
ROOT_CAUSE=archived backup copies are intentionally root:root 0600 but old oracle compared their full metadata against original live 0644/0755 bindings
FIX_OR_GUARD=backup copy requires root:root 0600 plus original SHA/size; current live file separately requires full original SHA/size/mode/uid/gid; regression tests plus real reconciliation rerun PASS
STATUS=GUARDED
```

KF-129 remains OPEN at handoff. No new physical-test failure has yet occurred.

---

## 16. New Chat Start Prompt

默认读取集：

```text
1. 本 handoff
2. docs/development/N3W_PROJECT_WORKING_CONTEXT.md
3. docs/development/N3W_CURRENT_STATE.md
4. docs/development/N3W_CURRENT_STATE_INDEX.md
5. docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
6. exact handoff standard authority 4300890dff0ce63d5a547df21426e287d084d9ee（只读取 standard/process）
7. current V1.3 template from main
```

建议新会话直接粘贴：

```text
阅读《N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_T1_R3_CLOSED_TO_PHYSICAL_ACCEPTANCE_NEW_CHAT_HANDOFF_V1.0_20261028.md》。

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/adr/0011-n3w-scan-triggered-first-registration.md
- docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_PHYSICAL_ACCEPTANCE_DESIGN_AND_READONLY_PREFLIGHT_20261028.md
- docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_T1_CANDIDATE_UPGRADE_DESIGN_AND_READONLY_PREFLIGHT_20261028.md

同时读取 exact handoff process authority：
4300890dff0ce63d5a547df21426e287d084d9ee
只读取其中 NEW_CHAT_HANDOFF_STANDARD.md 的 process/standard 规则；
formal handoff template 使用 current main V1.3，不回退旧模板。

并 fresh rebind：
- repository main
- PR #720
- PR #721
- R9 artifact ID 12783234959 availability / exact hashes
- R3 T1 committed runtime
- current R10 transaction/F4 successor state

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

每次回复先写：
主线任务：N3-W 扫描触发首次配对 R10
当前任务：首次配对 / 板端真实验收

必须先承认：
- R3 T1 candidate upgrade 已 CLOSED_PASS；
- R3 live authorization 已 consumed，禁止重放；
- 当前 T1 Manager 已是 fresh-e299c937a7b8；
- 47110/TCP 与 47111/UDP 已 ready，47112 idle closed；
- F4 R10 successor binding 与六个 successor live files 已独立验证 PASS；
- R2 failed upgrade 仅保留为历史 FAIL，residue reconciliation 已 CLOSED_PASS；
- PR #720/#721 仍 OPEN/DRAFT，不能自动 merge；
- R9 board artifact ID=12783234959；
- exact firmware.factory.bin SHA256=b734c343b3caf725c3991e6dc408b471a607f0c10cfe641346a78228b65c3bbf；
- factory image 不覆盖 NVS；
- 当前没有任何 board/USB/serial/flash/NVS action；
- KF-129 仍 OPEN，只差真实 first-pair physical acceptance；
- 不允许 Manager force-recreate、NVS erase、flat flash_args、manual Setup Secret、自动第二次物理尝试。

当前只进入：
NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_PHYSICAL_ACCEPTANCE_EXECUTION_20261028_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

先做 GitHub + T1 fresh readonly rebind。
在任何 board access/write 之前，先向我展示 exact artifact/target/scope，并请求新的 one-shot physical authorization。
不要自动跨越失败、重试、修复、merge。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=R10_T1_R3_CLOSED_TO_BOARD_PHYSICAL_ACCEPTANCE
CURRENT_STOP_POINT=R3_T1_UPGRADE_CLOSED_PASS_NO_BOARD_ACCESS_YET
CURRENT_BLOCKER=REAL_FIRST_PAIR_PHYSICAL_ACCEPTANCE_PENDING

LIVE_SYSTEM_STATE=TARGET_MANAGER_E299_RUNNING_REGISTRATION_RUNTIME_READY_PAIRING_IDLE_CLOSED

NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_PHYSICAL_ACCEPTANCE_EXECUTION_20261028_01

R3_T1_CANDIDATE_UPGRADE=CLOSED_PASS
R3_AUTHORIZATION_CONSUMED=true
R3_AUTHORIZATION_REPLAY_PERMITTED=false

R2_FAILED_RESIDUE_RECONCILIATION=CLOSED_PASS
KF129=OPEN_PENDING_REAL_PHYSICAL_ACCEPTANCE
KF133=GUARDED

BOARD_ACCESS=false
APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

PROJECT_WORKING_CONTEXT_VERSION=1.1
HANDOFF_TEMPLATE_VERSION=1.3

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

This docs-only handoff/current-state alignment is the durable replacement for chat-only project state. A fresh session must still rebind current repository/live evidence before executing the physical gate.

---

## 18. Handoff Compliance Audit

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.1

PROJECT_WORKING_CONTEXT_REFERENCED=PASS
LONG_TERM_RULE_DUPLICATION_MINIMIZED=PASS
STAGE_SPECIFIC_OVERRIDES_EXPLICIT=PASS
PRIVATE_CONTEXT_EXCLUDED_FROM_PUBLIC_HANDOFF=PASS

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
EXECUTION_CONTRACT_SELF_CONTAINED=PASS
CI_CONTINUATION_HARD_RULES_PRESENT=PASS
EXPECTED_CLOSURE_PRESENT=PASS
AFTER_PASS_DOES_NOT_AUTO_EXECUTE=PASS

KNOWN_FAILURES_UPDATE_CLASSIFIED=PASS
NEW_CHAT_START_PROMPT_PRESENT=PASS
TEAM_WORKSPACE_STATUS_PRESENT=PASS
FINAL_FROZEN_STATE_PRESENT=PASS

HANDOFF_STATE_COMPLETENESS=PASS
HANDOFF_READY_FOR_NEW_CHAT=true

=== END ===
```
