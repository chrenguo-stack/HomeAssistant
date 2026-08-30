# N3-W / FC4 Board C TLS Root-Cause Closeout and Firmware Repair Handoff

## 1. Document Identity / Schema

```text
HANDOFF_SCHEMA_VERSION=1.0
HANDOFF_TEMPLATE_ID=N3W_FC4_DEVELOPMENT_HANDOFF_TEMPLATE
HANDOFF_TEMPLATE_VERSION=1.0
HANDOFF_TEMPLATE_BLOB_SHA=e26ff3329e52e6e56b16b865c19649feabbb09b7

HANDOFF_DOCUMENT_VERSION=V1.2
HANDOFF_DATE=2026-08-30

HANDOFF_LINT_REQUIRED=true
HANDOFF_LINT_RESULT=PASS
PUBLIC_REPOSITORY_SAFETY_REQUIRED=true
PUBLIC_REPOSITORY_SAFETY_RESULT=PASS
```

V1.2 is the first handoff in this lineage governed by the canonical handoff contract. It supersedes V1.1 for next-session recovery semantics while preserving all historical evidence and consumed-authorization facts.

## 2. North Star / Route

```text
NORTH_STAR=FC4_FINAL_PHYSICAL_ACCEPTANCE
CURRENT_ROUTE_NODE=BOARD_C_FIRST_REGISTRATION
ACTIVE_DETOUR=BOARD_C_TLS_SERVER_NAME_FIRMWARE_REPAIR
RETURN_TO_ROUTE=BOARD_C_FIRST_REGISTRATION_RUNTIME_ACCEPTANCE
NEW_BRANCH_ALLOWED=false
```

The TLS repair is a bounded detour caused by a proven product blocker. It is not a new product/process route.

## 3. Execution Model

```text
EXECUTION_MODEL=HIGH_LEVEL_REASONING_PLUS_BOUNDED_CODEX_EXECUTION
HIGH_LEVEL_REASONING_ROLE=CHATGPT
BOUNDED_EXECUTION_ROLE=CODEX

ONE_GATE_ONE_ROUTE_DECISION=true
UNKNOWN_IS_NOT_FAIL=true
UNOBSERVED_IS_NOT_FALSE=true
DSL_OR_EXECUTION_CONTRACT_IS_NOT_SELF_EXECUTING=true

CODEX_MUST_NOT_INFER_AUTHORIZATION=true
CODEX_MUST_NOT_EXPAND_SCOPE=true
CODEX_MUST_STOP_ON_PRECLAIM_FAILURE=true
CHATGPT_MUST_REVIEW_EACH_GATE_RESULT_BEFORE_NEXT_GATE=true
```

ChatGPT owns source review, state reconciliation, route control, root-cause analysis, gate/authorization design, test-plan design, result classification, failure-fuse enforcement, and handoff/archive control. Codex executes exact bounded commands/scripts and returns raw or machine-readable output. A DSL contract alone is not executable unless the active Codex environment explicitly supports that contract as an execution interface.

## 4. Repository / Branch Authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
HANDOFF_BRANCH=docs/n3w-fc4-boardc-recapture-handoff-20260829
HANDOFF_PREDECESSOR_HEAD=6f69b87a7ec1007fbd1f1c0475751e382d099e54
HANDOFF_BRANCH_HEAD_POLICY=READ_CURRENT_BRANCH_HEAD_ON_RECOVERY
```

The next session must read the live branch HEAD and compare it with the frozen product/guarded source. Do not treat a documentation branch tip as product-source authority.

## 5. Frozen Product Source

```text
FROZEN_PRODUCT_SOURCE_HEAD=1f80d54ff5f84056e0559a7d8cc80427c5e0bb14
FROZEN_PRODUCT_SOURCE_TREE=f3b8095c62e8a4838eb1b614f05c932f54f5226d

GUARDED_HEAD=867c84d9d90f9c56d2446d9aa1a13c31ac593480
GUARDED_TREE=de670366fe452637e802fb261929613047805964
```

No TLS product-source repair has been authorized or executed.

## 6. Worktree / Workspace Guard

```text
PRIVATE_WORKTREE_PATH_EXPOSED=false
DIRTY_WORKTREE_MUTATION_ALLOWED=false
```

Exact/private local worktree locators remain private and must be recovered from trusted private context when needed. Public handoffs must use `<PRIVATE_EXACT_WORKTREE_PATH>` rather than developer absolute paths. The original dirty worktree must not be reset, stashed, discarded, or repurposed as the exact repair authority.

## 7. Runtime Authority

```text
RUNTIME_AUTHORITY_STATE=PASS
SECTION_STATE=APPLICABLE
```

Frozen runtime authority facts:

```text
MANAGER_COUNT=1
BROKER_COUNT=1
MANAGER_REVISION_MATCH=true

REGISTRATION_COMMIT_PROVEN=true
CREDENTIAL_COMMIT_PROVEN=true
APPLICATION_KEY_COMMIT_PROVEN=true
DYNSEC_IDENTITY_PRESENT=true

BROKER_8883_TLS_CONFIG_COMPLETE=true
BOARD_C_POST_REGISTRATION_RUNTIME_ENTERED=true
BOARD_C_MQTT_CLIENT_CONNECTED_COUNT=0
```

A mandatory route audit passed after the earlier executor/oracle failure fuse and reset the streak.

## 8. Product State / Proven Facts

```text
PRODUCT_STATE=FIRST_REGISTRATION_COMMITTED_TLS_RUNTIME_BLOCKED
SECTION_STATE=APPLICABLE
```

Board C first registration is already committed:

```text
CURRENT_REGISTRATION_STATE=APPROVED
CURRENT_NODE_ID_PRESENT=true
CURRENT_REPAIR_AUTHORIZED=false
CURRENT_HARDWARE_RETIRED=false

CREDENTIAL_ASSIGNMENT_COUNT=1
CREDENTIAL_STATE=ACTIVE
CREDENTIAL_ACTIVE_GENERATION=1
CREDENTIAL_PENDING_GENERATION_PRESENT=false

APPLICATION_KEY_NODE_ACTIVE=true
APPLICATION_KEY_ACTIVE_EPOCH_COUNT=1
APPLICATION_KEY_STAGED_EPOCH_COUNT=0
APPLICATION_KEY_GRACE_EPOCH_COUNT=0

DYNSEC_EXACT_CLIENT_COUNT=1
DYNSEC_EXACT_ROLE_EXISTS=true
DYNSEC_EXACT_ROLE_BOUND=true
FIRST_REGISTRATION_COMMIT_PROVEN=true
```

Therefore TLS repair must not redo Setup Secret import, pairing, NODE_ID allocation, DynSec provisioning, credential generation, application-key provisioning, or NVS erase.

## 9. Active Blocker / Root Cause

```text
PRODUCT_BLOCKER_PROVEN=true
ROOT_CAUSE=FIRMWARE_IGNORES_PROVISIONED_BROKER_TLS_SERVER_NAME
SECTION_STATE=APPLICABLE
```

Final evidence chain:

```text
NODE_BROKER_HOST_KIND=IP
NODE_TLS_SERVER_NAME_KIND=DNS
NODE_BROKER_HOST_EQUALS_TLS_SERVER_NAME=false

BROKER_CERTIFICATE_MATCHES_NODE_BROKER_HOST=false
BROKER_CERTIFICATE_MATCHES_TLS_SERVER_NAME=true
BROKER_CERTIFICATE_CA_VERIFY=true
BROKER_CERTIFICATE_CURRENTLY_TIME_VALID=true

FIRMWARE_MQTT_CONSUMES_TLS_SERVER_NAME=false

SERIAL_MBEDTLS_HANDSHAKE_2700_COUNT=4
SERIAL_MBEDTLS_HANDSHAKE_CODE_1=0X2700
```

The Manager delivers distinct connection address and TLS identity correctly; the certificate is valid for the DNS TLS identity; frozen firmware fails to consume that identity and Board C reports TLS certificate-verification handshake failure.

Historical Board A/B isolated E2E did not expose this because that harness used:

```text
broker_host == broker_tls_server_name == certificate IP SAN
```

The missing regression dimension was `broker_host != broker_tls_server_name`.

## 10. Failure Classification / Fuse

```text
FAIL_CLASS=PRODUCT_BLOCKER
CURRENT_EXECUTOR_FAILURE_STREAK=0
ROUTE_AUDIT_REQUIRED=false
```

The product blocker is proven independently of executor/oracle failures. `UNKNOWN != FAIL` remains mandatory. Executor/oracle/harness defects must not be promoted into product defects without independent product evidence.

Failure-fuse rule:

```text
AFTER_SUCCESSFUL_ROUTE_AUDIT:
TWO_CONSECUTIVE_EXECUTOR_OR_PRECLAIM_NONCLOSURES
=> MANDATORY_ROUTE_AUDIT_BEFORE_THIRD_SUCCESSOR_OR_PRECLAIM
```

## 11. Authorization Ledger

```text
CONSUMED_AUTHORIZATION_COUNT=3
REPLAY_OF_CONSUMED_AUTHORIZATION_ALLOWED=false
```

```text
AUTHORIZATION_LEDGER_BEGIN
AUTHORIZATION_ID=R6-BOARD-C-SETUP-SECRET-PHYSICAL-RECAPTURE-20260829-01
AUTHORIZATION_STATE=CONSUMED
REPLAY_PERMITTED=false
AUTHORIZATION_SCOPE=BOARD_C_SETUP_SECRET_PHYSICAL_RECAPTURE
AUTHORIZATION_LEDGER_END
```

```text
AUTHORIZATION_LEDGER_BEGIN
AUTHORIZATION_ID=R6-BOARD-C-UDS-SETUP-SECRET-IMPORT-20260830-01
AUTHORIZATION_STATE=CONSUMED
REPLAY_PERMITTED=false
AUTHORIZATION_SCOPE=BOARD_C_SINGLE_UDS_SETUP_SECRET_IMPORT
AUTHORIZATION_LEDGER_END
```

```text
AUTHORIZATION_LEDGER_BEGIN
AUTHORIZATION_ID=R6-BOARD-C-READ-ONLY-SERIAL-TLS-DIAGNOSTIC-20260830-01
AUTHORIZATION_STATE=CONSUMED
REPLAY_PERMITTED=false
AUTHORIZATION_SCOPE=BOARD_C_SINGLE_OPEN_READ_ONLY_SERIAL_TLS_MQTT_DIAGNOSTIC_ONLY
AUTHORIZATION_LEDGER_END
```

Candidate only, not granted:

```text
AUTHORIZATION_LEDGER_BEGIN
AUTHORIZATION_ID=R6-BOARD-C-TLS-SERVER-NAME-FIRMWARE-SOURCE-REPAIR-20260830-01
AUTHORIZATION_STATE=CANDIDATE
REPLAY_PERMITTED=false
AUTHORIZATION_SCOPE=EXACT_GUARDED_SOURCE_TLS_SERVER_NAME_MINIMAL_REPAIR_TESTS_AND_KF_ONLY
AUTHORIZATION_LEDGER_END
```

The candidate source-repair authorization does not authorize Board access, serial open, firmware flash, NVS mutation, T1 mutation, Broker/Manager/DynSec mutation, or pairing mutation.

## 12. Mutation State

```text
SOURCE_MUTATION_EXECUTED=false
PHYSICAL_MUTATION_EXECUTED=false
RUNTIME_MUTATION_EXECUTED=false

REPOSITORY_GOVERNANCE_MUTATION_EXECUTED=true
```

The completed diagnostic used one authorized read-only serial open, but did not mutate Board state. The current closeout only changes repository documentation/governance tooling. No product source or live runtime has been mutated.

## 13. Known Failures / Regression Guards

```text
KNOWN_FAILURES_UPDATED=true
KNOWN_FAILURES_STATE=KF-075_GUARDED_KF-076_OPEN_KF-077_OPEN
```

Relevant central entries:

```text
KF-075=GUARDED
DOMAIN=PHYSICAL_HARNESS
TOPIC=Board-C P9 executor target/transport/oracle authority

KF-076=OPEN
DOMAIN=PRODUCT
TOPIC=MQTT TCP endpoint and TLS expected-server-name separation

KF-077=OPEN
DOMAIN=PHYSICAL_HARNESS
TOPIC=connected substring falsely matching disconnected
```

KF-076 remains OPEN until source repair, regression tests, exact build/CI, firmware materialization, and Board C runtime/HA acceptance close. KF-077 remains OPEN until its matcher regression is materialized.

This handoff template contract itself is governed by:

```text
NEW_SESSION_HANDOFF_REQUIRES_TEMPLATE=true
HANDOFF_LINT_REQUIRED=true
HANDOFF_LINT_PASS_REQUIRED_BEFORE_CLOSEOUT=true
```

## 14. Forbidden Actions / Non-goals

```text
FORBIDDEN_ACTIONS_STATE=DECLARED
```

Without new explicit authority, do not:

```text
REIMPORT_SETUP_SECRET
REPAIR_OR_RESTART_PAIRING
ALLOCATE_NEW_NODE_ID
REPROVISION_DYNSEC
BUMP_CREDENTIAL_GENERATION
REPROVISION_APPLICATION_KEY
ERASE_NVS

OPEN_BOARD_C_SERIAL
RESET_BOARD_C
FLASH_BOARD_C

MUTATE_T1_RUNTIME
MUTATE_BROKER
MUTATE_MANAGER
MUTATE_DYNSEC

SET_SKIP_CERT_CN_CHECK
DISABLE_TLS_SERVER_IDENTITY_VALIDATION
ADD_SITE_IP_TO_CERTIFICATE_AS_WORKAROUND
FORCE_BROKER_HOST_TO_TLS_DNS_AS_WORKAROUND
```

Do not use a Broker/DynSec workaround to hide the firmware defect.

## 15. Next Route Action

```text
NEXT_ROUTE_ACTION=BOARD_C_TLS_SERVER_NAME_FIRMWARE_REPAIR_DESIGN
```

Only one immediate route action is allowed: read-only source repair design against exact frozen dependency interfaces.

## 16. Physical State

```text
PHYSICAL_STATE=BOARD_C_REGISTERED_SERIAL_AUTH_CONSUMED_NO_REOPEN
SECTION_STATE=APPLICABLE
```

The last Board C serial authorization was consumed exactly once:

```text
SERIAL_OPEN_ATTEMPT_COUNT=1
SERIAL_OPEN_COUNT=1
SERIAL_CLOSE_COUNT=1
SERIAL_WRITE_BYTE_COUNT=0
RESET_EXECUTED=false
FLASH_EXECUTED=false
NVS_ERASE_EXECUTED=false
```

Do not reopen serial under that authorization.

## 17. Source Repair / Changed-file Allowlist

```text
SOURCE_REPAIR_STATE=DESIGN_PENDING_AUTHORIZATION_NOT_GRANTED
SECTION_STATE=APPLICABLE
```

Before mutation, the next session must read the exact ESPHome MQTT ESP32 backend and exact ESP-MQTT/ESP-IDF structures used by the frozen build.

Required architecture:

```text
TCP_CONNECT_TARGET=broker_host
TLS_EXPECTED_SERVER_NAME=broker_tls_server_name
```

Candidate underlying mechanism such as `broker.verification.common_name` must be verified against the exact frozen dependency version; do not assume a newer API.

The mutation allowlist must be designed before authorization and must exclude unrelated firmware, pairing, credential, Broker, Manager, DynSec, and HA changes.

## 18. Tests / CI / Artifact Authority

```text
TEST_PLAN_STATE=DEFINED
SECTION_STATE=APPLICABLE
```

Mandatory TLS matrix:

| Case | TCP host | TLS expected name | Certificate identity | Expected |
|---|---|---|---|---|
| A | DNS-A | DNS-A | DNS-A | PASS |
| B | IP | DNS-A | DNS-A only | PASS |
| C | IP | DNS-B | DNS-A only | FAIL |
| D | IP | DNS-A | correct name, wrong CA | FAIL |
| E | IP | DNS-A | correct name, invalid time | FAIL |

Case B is mandatory.

Also prove:

```text
credential/provisioning bundle
→ persisted broker state
→ load_runtime_state_()
→ configure_mqtt_()
→ ESPHome MQTT backend
→ ESP-MQTT/ESP-IDF verification-name field
```

KF-077 regression must prove `connected` cannot match `disconnected`.

Template/governance validation for this document:

```text
python3 tools/check_development_handoff.py --self-test
python3 tools/check_development_handoff.py --file docs/development/N3W_FC4_BoardC_FirstRegistration_TLS_ServerName_RootCause_Closeout_and_FirmwareRepair_Handoff_V1.2_20260830.md
python3 tools/check_public_repository_safety.py --repository .
```

## 19. Next-Session Read-Only Recovery

```text
NEXT_SESSION_RECOVERY_STATE=DEFINED
```

Next conversation sequence:

1. Read this V1.2 handoff.
2. Read `docs/development/HANDOFF_DOCUMENT_CONTRACT.md`.
3. Read `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`.
4. Read the P9 executor/oracle supplement and Setup Secret recapture closeout.
5. Read the live documentation branch HEAD; do not rely only on the predecessor SHA recorded here.
6. Rebind frozen product HEAD/tree and guarded HEAD/tree.
7. Reconfirm no source repair authorization has been granted.
8. Read exact ESPHome MQTT ESP32 backend and exact ESP-MQTT/ESP-IDF TLS verification-name API.
9. Produce the minimum repair design, changed-file/hunk allowlist, and focused regression plan.
10. Only after review decide whether to grant the candidate source-repair authorization.

## 20. New Conversation Startup Prompt

```text
STARTUP_PROMPT_PRESENT=true
```

Copy-paste prompt:

```text
继续“温室环境监测系统（ESP32-C6）”项目的 N3-W / FC4 Final Physical Acceptance。

首先只读恢复，不得自动执行源码 mutation、Board C 访问、串口、Flash/NVS 或 T1 runtime mutation。

GitHub：
chrenguo-stack/HomeAssistant

分支：
docs/n3w-fc4-boardc-recapture-handoff-20260829

首先读取：
1. docs/development/N3W_FC4_BoardC_FirstRegistration_TLS_ServerName_RootCause_Closeout_and_FirmwareRepair_Handoff_V1.2_20260830.md
2. docs/development/HANDOFF_DOCUMENT_CONTRACT.md
3. docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
4. docs/development/N3W_FC4_BoardC_P9_Executor_Oracle_Incident_Supplement_20260829.md
5. docs/development/N3W_FC4_BoardC_SetupSecret_Recapture_Closeout_and_FreshPairingRebind_Handoff_V1.0_20260829.md

NORTH_STAR=FC4_FINAL_PHYSICAL_ACCEPTANCE
CURRENT_ROUTE_NODE=BOARD_C_FIRST_REGISTRATION
ACTIVE_DETOUR=BOARD_C_TLS_SERVER_NAME_FIRMWARE_REPAIR
RETURN_TO_ROUTE=BOARD_C_FIRST_REGISTRATION_RUNTIME_ACCEPTANCE
NEW_BRANCH_ALLOWED=false

EXECUTION_MODEL=HIGH_LEVEL_REASONING_PLUS_BOUNDED_CODEX_EXECUTION
HIGH_LEVEL_REASONING_ROLE=CHATGPT
BOUNDED_EXECUTION_ROLE=CODEX
DSL_OR_EXECUTION_CONTRACT_IS_NOT_SELF_EXECUTING=true

FROZEN_PRODUCT_SOURCE_HEAD=1f80d54ff5f84056e0559a7d8cc80427c5e0bb14
FROZEN_PRODUCT_SOURCE_TREE=f3b8095c62e8a4838eb1b614f05c932f54f5226d
GUARDED_HEAD=867c84d9d90f9c56d2446d9aa1a13c31ac593480
GUARDED_TREE=de670366fe452637e802fb261929613047805964

TLS_SERVER_NAME_BINDING_ROOT_CAUSE=PROVEN
ROOT_CAUSE=FIRMWARE_IGNORES_PROVISIONED_BROKER_TLS_SERVER_NAME
PRODUCT_BLOCKER_PROVEN=true
FAIL_CLASS=PRODUCT_BLOCKER

KF-075=GUARDED
KF-076=OPEN
KF-077=OPEN

R6-BOARD-C-SETUP-SECRET-PHYSICAL-RECAPTURE-20260829-01 已消费，不得重放。
R6-BOARD-C-UDS-SETUP-SECRET-IMPORT-20260830-01 已消费，不得重放。
R6-BOARD-C-READ-ONLY-SERIAL-TLS-DIAGNOSTIC-20260830-01 已消费，不得重放。

源码修复候选：
R6-BOARD-C-TLS-SERVER-NAME-FIRMWARE-SOURCE-REPAIR-20260830-01
当前仅 CANDIDATE，未授权。

NEXT_ROUTE_ACTION=BOARD_C_TLS_SERVER_NAME_FIRMWARE_REPAIR_DESIGN

先只读确认 exact ESPHome/ESP-MQTT/ESP-IDF TLS expected-name API、最小 changed-file/hunk allowlist 和回归矩阵，再决定是否授权源码修改。
```

## 21. Handoff Terminal

```text
HANDOFF_SCHEMA_VERSION=1.0
HANDOFF_TEMPLATE_ID=N3W_FC4_DEVELOPMENT_HANDOFF_TEMPLATE
HANDOFF_TEMPLATE_VERSION=1.0

NORTH_STAR=FC4_FINAL_PHYSICAL_ACCEPTANCE
CURRENT_ROUTE_NODE=BOARD_C_FIRST_REGISTRATION
ACTIVE_DETOUR=BOARD_C_TLS_SERVER_NAME_FIRMWARE_REPAIR
RETURN_TO_ROUTE=BOARD_C_FIRST_REGISTRATION_RUNTIME_ACCEPTANCE
NEW_BRANCH_ALLOWED=false

EXECUTION_MODEL=HIGH_LEVEL_REASONING_PLUS_BOUNDED_CODEX_EXECUTION

PRODUCT_BLOCKER_PROVEN=true
FAIL_CLASS=PRODUCT_BLOCKER

CURRENT_EXECUTOR_FAILURE_STREAK=0
ROUTE_AUDIT_REQUIRED=false

NEXT_ROUTE_ACTION=BOARD_C_TLS_SERVER_NAME_FIRMWARE_REPAIR_DESIGN

HANDOFF_LINT_REQUIRED=true
HANDOFF_LINT_RESULT=PASS
PUBLIC_REPOSITORY_SAFETY_REQUIRED=true
PUBLIC_REPOSITORY_SAFETY_RESULT=PASS
```
