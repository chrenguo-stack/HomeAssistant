# N3-W / FC4 Board C First Registration TLS 根因收口暨 Firmware Repair 新会话交接文档

- Version: `V1.1`
- Date: `2026-08-30`
- Repository: `chrenguo-stack/HomeAssistant`
- Predecessor handoff: `N3W_FC4_BoardC_FirstRegistration_TLS_ServerName_RootCause_Closeout_and_FirmwareRepair_Handoff_V1.0_20260830.md`
- Predecessor documentation HEAD: `a4167059db17f86ed3dfa82cc6467468cb6d1a8b`
- Purpose: freeze the completed Board C diagnostic/root-cause state and resume in a fresh conversation at the bounded firmware-repair design boundary.
- Public/private policy: this document intentionally contains no Setup Secret value/hash, raw Board C hardware ID, raw pairing ID, raw NODE_ID, raw Board C IP, or private evidence/workspace path.

---

## 1. North Star / route

```text
NORTH_STAR=FC4_FINAL_PHYSICAL_ACCEPTANCE
CURRENT_ROUTE_NODE=BOARD_C_FIRST_REGISTRATION

ACTIVE_DETOUR=BOARD_C_TLS_SERVER_NAME_FIRMWARE_REPAIR
RETURN_TO_ROUTE=BOARD_C_FIRST_REGISTRATION_RUNTIME_ACCEPTANCE

NEW_BRANCH_ALLOWED=false
```

The TLS repair is a bounded detour required by a proven product blocker. It is not a new product/process branch.

---

## 2. Execution Model / 执行模式

This is a mandatory cross-session execution-governance contract.

```text
EXECUTION_MODEL=
HIGH_LEVEL_REASONING_PLUS_BOUNDED_CODEX_EXECUTION

HIGH_LEVEL_REASONING_ROLE=CHATGPT
BOUNDED_EXECUTION_ROLE=CODEX
```

### 2.1 ChatGPT responsibilities

```text
CHATGPT_RESPONSIBILITIES=
SOURCE_REVIEW
STATE_RECONCILIATION
ROUTE_CONTROL
ROOT_CAUSE_ANALYSIS
GATE_DESIGN
AUTHORIZATION_BOUNDARY_DESIGN
TEST_PLAN_DESIGN
RESULT_CLASSIFICATION
FAILURE_FUSE_ENFORCEMENT
HANDOFF_AND_ARCHIVE_CONTROL
```

ChatGPT is responsible for deciding what evidence is still needed, whether a gate is read-only or mutating, how the authorization boundary is defined, how a result is classified, and whether the route may continue.

### 2.2 Codex responsibilities

```text
CODEX_RESPONSIBILITIES=
EXECUTE_EXACT_BOUNDED_COMMANDS
RETURN_RAW_OR_MACHINE_READABLE_RESULTS
NO_SCOPE_EXPANSION
NO_INDEPENDENT_ROUTE_CHANGE
NO_UNAUTHORIZED_MUTATION
STOP_ON_PRECLAIM_FAILURE
```

Codex is an executor, not the route authority.

### 2.3 Mandatory execution constraints

```text
CODEX_MUST_NOT_INFER_AUTHORIZATION=true
CODEX_MUST_NOT_EXPAND_SCOPE=true
CODEX_MUST_NOT_CREATE_SIBLING_PRODUCT_OR_PROCESS_BRANCH=true
CODEX_MUST_STOP_ON_PRECLAIM_FAILURE=true

CHATGPT_MUST_NOT_TREAT_CODEX_EXECUTOR_FAILURE_AS_PRODUCT_FAILURE=true
CHATGPT_MUST_REVIEW_EACH_GATE_RESULT_BEFORE_NEXT_GATE=true
```

### 2.4 DSL / execution-contract boundary

```text
DSL_OR_EXECUTION_CONTRACT_IS_NOT_SELF_EXECUTING=true
```

A block such as:

```text
AUTHORIZATION=...
READ_ONLY=true
BOARD_ACCESS=false
```

is a contract/constraint description. It is not automatically an executable program.

When Codex execution is required:

```text
CHATGPT_MUST_PROVIDE_AN_ACTUAL_EXECUTABLE_COMMAND_OR_SCRIPT=true
```

unless the current Codex environment explicitly supports the referenced execution contract as an executable interface.

This rule exists to prevent a recurrence of the historical situation where Codex received only a DSL-style contract and correctly reported that no executable SSH/Python/script body had been supplied.

### 2.5 Gate discipline

```text
ONE_GATE_ONE_ROUTE_DECISION=true
UNKNOWN_IS_NOT_FAIL=true
UNOBSERVED_IS_NOT_FALSE=true
```

Executor/oracle/harness defects must never be promoted into product defects without independent product evidence.

Primary failure classes remain:

```text
PRODUCT_BLOCKER
INFRASTRUCTURE_BLOCKER
SECURITY_AUTHORITY_BLOCKER
PHYSICAL_HARNESS_DEFECT
EXECUTOR_OR_ORACLE_DEFECT
EVIDENCE_GAP
TRANSIENT_INFRASTRUCTURE_FAILURE
```

### 2.6 Failure fuse

```text
AFTER_SUCCESSFUL_ROUTE_AUDIT:
TWO_CONSECUTIVE_EXECUTOR_OR_PRECLAIM_NONCLOSURES
=> MANDATORY_ROUTE_AUDIT_BEFORE_THIRD_SUCCESSOR_OR_PRECLAIM

SUCCESSFUL_ROUTE_AUDIT_RESETS_FUSE=true
```

Repeatedly rewriting an oracle is not allowed to bypass the route audit.

---

## 3. Frozen product and guarded source authority

Frozen FC4 product source:

```text
FROZEN_PRODUCT_SOURCE_HEAD=
1f80d54ff5f84056e0559a7d8cc80427c5e0bb14

FROZEN_PRODUCT_SOURCE_TREE=
f3b8095c62e8a4838eb1b614f05c932f54f5226d
```

Board-C P9 guarded source:

```text
GUARDED_HEAD=
867c84d9d90f9c56d2446d9aa1a13c31ac593480

GUARDED_TREE=
de670366fe452637e802fb261929613047805964
```

Exact clean guarded worktree used by the completed diagnostic session:

```text
/Users/chenrenguo/HomeAssistant-p9-exact-867c84d9
```

Do not touch the original dirty worktree:

```text
/Users/chenrenguo/HomeAssistant-local-test
```

The next session must rebind exact source before any source mutation.

---

## 4. Documentation lineage at V1.1 publication

Branch:

```text
docs/n3w-fc4-boardc-recapture-handoff-20260829
```

Predecessor branch HEAD before adding this V1.1 document:

```text
a4167059db17f86ed3dfa82cc6467468cb6d1a8b
```

Documentation lineage from guarded source before V1.1:

```text
867c84d9d90f9c56d2446d9aa1a13c31ac593480
  ↓
d53b504fce8508e527c3dbbc16aa7021ab65b3f3
  ↓
e1d8965e6df403fcbe6908c47952e2fc97026a82
  ↓
feba41dbc04964c8ed4ff7161ddd6298a2b6841a
  ↓
68233e93155b69161da5cdb8ec921c2f769492bf
  ↓
a4167059db17f86ed3dfa82cc6467468cb6d1a8b
```

The next conversation must read the current branch HEAD afresh; this document does not make a self-referential claim that its own commit SHA is immutable forever.

All closeout commits are documentation-only relative to the guarded source. No firmware/Manager/Broker/DynSec/HA product source was changed during this documentation closeout.

---

## 5. Documents to read first in the next conversation

Read and reconcile in this order:

1. `docs/development/N3W_FC4_BoardC_FirstRegistration_TLS_ServerName_RootCause_Closeout_and_FirmwareRepair_Handoff_V1.1_20260830.md`
2. `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`
3. `docs/development/N3W_FC4_BoardC_P9_Executor_Oracle_Incident_Supplement_20260829.md`
4. `docs/development/N3W_FC4_BoardC_SetupSecret_Recapture_Closeout_and_FreshPairingRebind_Handoff_V1.0_20260829.md`

V1.1 supersedes V1.0 for execution-governance and next-session startup semantics. Historical evidence/authorization facts in older documents remain immutable.

---

## 6. Board C first-registration commit is already complete

After the single authorized UDS Setup Secret import, Board C completed normal automatic first registration.

Frozen durable result:

```text
CURRENT_REGISTRATION_STATE=APPROVED
CURRENT_NODE_ID_PRESENT=true
CURRENT_REPAIR_AUTHORIZED=false
CURRENT_HARDWARE_RETIRED=false
CURRENT_APPROVAL_EVENT_COUNT=1

CREDENTIAL_ASSIGNMENT_COUNT=1
CREDENTIAL_STATE=ACTIVE
CREDENTIAL_ACTIVE_GENERATION=1
CREDENTIAL_PENDING_GENERATION_PRESENT=false
CREDENTIAL_PAIRING_MATCH=true
CREDENTIAL_NODE_MATCH=true

APPLICATION_KEY_NODE_ACTIVE=true
APPLICATION_KEY_ACTIVE_EPOCH_COUNT=1
APPLICATION_KEY_STAGED_EPOCH_COUNT=0
APPLICATION_KEY_GRACE_EPOCH_COUNT=0

DYNSEC_EXACT_CLIENT_COUNT=1
DYNSEC_EXACT_ROLE_EXISTS=true
DYNSEC_EXACT_ROLE_BOUND=true

REGISTRATION_COMMIT_PROVEN=true
CREDENTIAL_COMMIT_PROVEN=true
APPLICATION_KEY_COMMIT_PROVEN=true
DYNSEC_IDENTITY_PRESENT=true
FIRST_REGISTRATION_COMMIT_PROVEN=true
```

Therefore the TLS repair must not repeat:

```text
NO_SETUP_SECRET_REIMPORT
NO_PAIRING_REPAIR
NO_NEW_NODE_ID_ALLOCATION
NO_DYNSEC_REPROVISION
NO_CREDENTIAL_GENERATION_BUMP
NO_APPLICATION_KEY_REPROVISION
NO_NVS_ERASE
```

The current blocker is downstream of a successfully committed first registration.

---

## 7. Setup Secret import and physical-recapture boundaries

The physical Setup Secret recapture authorization was consumed and is non-replayable.

The later UDS Setup Secret import authorization was also consumed and is non-replayable.

The UDS import itself did not require manual approval, NODE_ID assignment, DynSec manipulation, or application-key manipulation. Normal Board/Manager protocol progression completed those stages automatically.

No future TLS firmware repair is allowed to reuse Setup Secret import as a workaround.

---

## 8. Runtime route audit already passed

After two consecutive oracle/preclaim nonclosures, the mandatory route audit ran and passed.

Frozen result:

```text
REGISTRATION_COMMIT_PROVEN=true
CREDENTIAL_COMMIT_PROVEN=true
APPLICATION_KEY_COMMIT_PROVEN=true
DYNSEC_IDENTITY_PRESENT=true

BROKER_8883_TLS_CONFIG_COMPLETE=true

BOARD_C_BROKER_TCP_CONNECTION_COUNT>0
BOARD_C_MQTT_CLIENT_CONNECTED_COUNT=0
BOARD_C_PROTOCOL_ERROR_COUNT>0

MQTT_PROTOCOL_BOUNDARY_STILL_PRESENT=true

BOARD_C_MQTT_PROTOCOL_BOUNDARY_ROUTE_AUDIT=PASS
FAIL_CLASS=NONE
PRODUCT_BLOCKER_PROVEN=false

ACTIVE_FAILURE_STREAK_RESET=true
ROUTE_AUDIT_REQUIRED=false
```

This proved there was no route drift back into registration, credential, application-key, DynSec, or listener recovery.

---

## 9. MQTT runtime boundary sequence

Manager subscription authority was already present, but no accepted Board C telemetry or HA discovery publish appeared.

Initial classification:

```text
BOARD_C_MQTT_RUNTIME_INGRESS_STATE=
NO_BOARD_C_MQTT_CONNECT_EVIDENCE
```

Later Board-C source activity proved repeated TCP connections to 8883:

```text
BOARD_C_PAIRING_STUCK=false
BOARD_C_POST_REGISTRATION_RUNTIME_ENTERED=true
BOARD_C_BROKER_TCP_CONNECT_ATTEMPTS>0
BOARD_C_MQTT_CLIENT_CONNECTED_COUNT=0
FAILURE_BOUNDARY=TCP_CONNECTED_BEFORE_MQTT_IDENTITY_ESTABLISHED
```

This disproved the live ACK_PENDING-stuck hypothesis.

---

## 10. Broker protocol-error oracle history

Hundreds of Board-C-source TCP sessions ended in Broker `Protocol error`, but initial log-only classifiers could not distinguish TLS from MQTT protocol semantics.

The correct classification at that stage was:

```text
FAIL_CLASS=EXECUTOR_OR_ORACLE_DEFECT
FAIL_SUBCLASS=BROKER_PROTOCOL_ERROR_DETAIL_UNAVAILABLE
PRODUCT_BLOCKER_PROVEN=false
```

No product blocker was declared until independent Board-side evidence existed.

---

## 11. P9 executor/oracle incident archive — KF-075

The P9 incident supplement is finalized as `KF-075`.

Actual incidents:

1. `ss` UDP listener parsing used the wrong positional field and produced a false zero-listener result.
2. One diagnostic query used Mac-local Docker rather than frozen T1 remote Docker authority.
3. A `docker exec` heredoc omitted `-i`; intended Python never reached container stdin.
4. Docker service discovery treated `.Labels` as an indexable map instead of using the supported `.Label "com.docker.compose.service"` surface.

Classification:

```text
KF-075
DOMAIN=PHYSICAL_HARNESS
STATUS=GUARDED
```

These failures corrected immediately without corresponding product changes and therefore must never be rewritten as Board/Manager/Broker/DynSec product defects.

---

## 12. TLS endpoint and certificate authority facts

Final T1 reconciliation proved:

```text
NODE_BROKER_HOST_KIND=IP
NODE_TLS_SERVER_NAME_KIND=DNS
NODE_BROKER_HOST_EQUALS_TLS_SERVER_NAME=false

BROKER_CERTIFICATE_MATCHES_NODE_BROKER_HOST=false
BROKER_CERTIFICATE_MATCHES_TLS_SERVER_NAME=true

BROKER_CERTIFICATE_CA_VERIFY=true
BROKER_CERTIFICATE_CURRENTLY_TIME_VALID=true
```

This topology is intentional:

```text
TCP_CONNECT_TARGET=broker_host
TLS_EXPECTED_SERVER_NAME=broker_tls_server_name
```

The product must support these values being different.

---

## 13. Frozen firmware source defect

The guarded/frozen `SimpleProductComponent::configure_mqtt_()` configures:

```text
broker address <- broker_state_.broker_host
broker port
username
password
client ID
CA certificate
```

but does not consume the persisted/provisioned:

```text
broker_state_.broker_tls_server_name
```

Frozen source classification:

```text
FIRMWARE_MQTT_SETS_BROKER_ADDRESS=true
FIRMWARE_MQTT_SETS_BROKER_PORT=true
FIRMWARE_MQTT_SETS_CA_CERTIFICATE=true
FIRMWARE_MQTT_SETS_USERNAME=true
FIRMWARE_MQTT_SETS_PASSWORD=true
FIRMWARE_MQTT_SETS_CLIENT_ID=true
FIRMWARE_MQTT_CONSUMES_TLS_SERVER_NAME=false
```

This is the source-side defect that activated in the final T1 topology.

---

## 14. Why Board A/B did not show the defect

The historical Phase 4 clean isolated two-board E2E remains a valid PASS for the topology actually tested.

Board A/B isolated TLS used:

```text
broker_host=host_ip
broker_tls_server_name=host_ip
certificate SAN=IP:host_ip
```

Therefore:

```text
broker_host == broker_tls_server_name == certificate IP SAN
```

The firmware could ignore the separate TLS server-name field and still pass.

The missing matrix dimension was:

```text
broker_host != broker_tls_server_name
```

Board C final-product topology activated it:

```text
broker_host=IP
broker_tls_server_name=DNS
certificate identity=DNS only
```

Thus the earlier A/B physical PASS is not contradicted; the isolated environment masked the latent defect.

---

## 15. Exact-current-node correction

An earlier source-IP/event-correlation oracle produced many apparent identified-client protocol-error counts.

The later exact current NODE_ID reconciliation proved:

```text
BROKER_EXACT_CURRENT_NODE_PROTOCOL_ERROR_COUNT=0
BROKER_EXACT_CURRENT_NODE_CONNECTED_COUNT=0
BROKER_EXACT_CURRENT_NODE_NOT_AUTHORIZED_COUNT=0
MQTT_CURRENT_NODE_ID_VISIBLE_TO_BROKER=false
```

Therefore Broker never established the current Board C MQTT identity.

This correction was required before client-side serial access was authorized.

---

## 16. One-shot Board C read-only serial diagnostic

Consumed authorization:

```text
AUTHORIZATION=
R6-BOARD-C-READ-ONLY-SERIAL-TLS-DIAGNOSTIC-20260830-01

SCOPE=
BOARD_C_SINGLE_OPEN_READ_ONLY_SERIAL_TLS_MQTT_DIAGNOSTIC_ONLY

ONE_SHOT=true
REPLAY_PERMITTED=false
```

Execution facts:

```text
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false

SERIAL_OPEN_ATTEMPT_COUNT=1
SERIAL_OPEN_COUNT=1
SERIAL_CLOSE_COUNT=1
SERIAL_OPEN_EXACTLY_ONCE=true

SERIAL_WRITE_BYTE_COUNT=0
MODEM_CONTROL_IOCTL_EXECUTED=false

RESET_EXECUTED=false
BOOT_BUTTON_EXECUTED=false
FLASH_EXECUTED=false
FLASH_READ_EXECUTED=false
NVS_ERASE_EXECUTED=false
NVS_READ_EXECUTED=false
REPROVISION_EXECUTED=false
PAIRING_MUTATION_EXECUTED=false
MQTT_MUTATION_EXECUTED=false
BROKER_MUTATION_EXECUTED=false
MANAGER_MUTATION_EXECUTED=false
LIVE_PRODUCT_MUTATION=false
```

The raw trace remained in a mode-0600 private evidence boundary.

**This authorization is permanently consumed and must never be replayed.**

---

## 17. Board-side TLS evidence

One-shot serial capture proved:

```text
SERIAL_ESP_TLS_LINE_COUNT=12
SERIAL_MBEDTLS_LINE_COUNT=4
SERIAL_TLS_HANDSHAKE_FAILURE_LINE_COUNT=4
SERIAL_CERTIFICATE_VERIFY_FAILURE_LINE_COUNT=8

SERIAL_LAST_ESP_TLS_ERROR_CODE_COUNT=1
SERIAL_LAST_ESP_TLS_ERROR_CODE_1=0X801A
```

Host-only reuse of the already captured private trace later proved:

```text
SERIAL_MBEDTLS_HANDSHAKE_2700_COUNT=4
SERIAL_MBEDTLS_HANDSHAKE_CODE_VARIANT_COUNT=1
SERIAL_MBEDTLS_HANDSHAKE_CODE_1=0X2700
```

Diagnostic terminal:

```text
BOARD_C_SERIAL_TLS_DIAGNOSTIC_STATE=
TLS_CERTIFICATE_NAME_OR_VERIFY_FAILURE_OBSERVED
```

No second serial access was needed.

---

## 18. Final root-cause closure — KF-076

The evidence chain is complete:

1. Board C first registration committed.
2. Credential generation 1 is ACTIVE.
3. Application key is ACTIVE.
4. DynSec node identity/role exists.
5. Broker 8883 TLS listener is correctly configured.
6. Board C reaches Broker TCP/8883.
7. Current Board C MQTT identity is never established by Broker.
8. Manager correctly carries separate `broker_host` and `broker_tls_server_name`.
9. Broker certificate CA and validity time are correct.
10. Certificate identity matches TLS DNS but does not match the IP connect target.
11. Frozen firmware ignores `broker_tls_server_name`.
12. Board C mbedTLS fails certificate verification during TLS handshake.

Final authoritative terminal:

```text
TLS_SERVER_NAME_BINDING_ROOT_CAUSE=PROVEN

ROOT_CAUSE=
FIRMWARE_IGNORES_PROVISIONED_BROKER_TLS_SERVER_NAME

PRODUCT_BLOCKER_PROVEN=true
FAIL_CLASS=PRODUCT_BLOCKER

BOARD_C_REPAIR_REQUIRED=true
BROKER_REPAIR_REQUIRED=false
MANAGER_REPAIR_REQUIRED=false
DYNSEC_REPAIR_REQUIRED=false
PAIRING_REPAIR_REQUIRED=false
```

Central index:

```text
KF-076
DOMAIN=PRODUCT
STATUS=OPEN
```

KF-076 remains OPEN until source repair, regressions, exact build/CI, firmware materialization, and Board C physical runtime acceptance are all closed.

---

## 19. `connected` / `disconnected` classifier defect — KF-077

The serial classifier once reported:

```text
SERIAL_MQTT_CONNECTED_LINE_COUNT=4
SERIAL_MQTT_DISCONNECTED_LINE_COUNT=4
```

The “connected” count is invalid.

Root cause:

```text
matcher used raw substring "connected"
"disconnected" contains "connected"
```

Therefore that connected count must never be used as success evidence.

Required guard:

```text
connected MUST NOT match disconnected
```

Use structured event IDs, exact mutually-exclusive tokens, or event-specific word-boundary matchers.

Central index:

```text
KF-077
DOMAIN=PHYSICAL_HARNESS
STATUS=OPEN
```

This oracle defect does not change the KF-076 TLS root-cause proof.

---

## 20. Required firmware repair architecture

The repair must preserve:

```text
TCP_CONNECT_TARGET=broker_host
TLS_EXPECTED_SERVER_NAME=broker_tls_server_name
```

Required dataflow:

```text
provisioned/persisted broker_tls_server_name
        ↓
SimpleProductComponent::configure_mqtt_()
        ↓
exact ESPHome MQTT ESP32 backend
        ↓
exact ESP-MQTT / ESP-IDF verification-name field
```

The next session must verify the exact dependency version before assuming API shape.

A candidate underlying field is:

```text
esp_mqtt_client_config_t.broker.verification.common_name
```

but the exact frozen version is the authority. A newer API must not be assumed.

---

## 21. Forbidden TLS workarounds

Prohibited:

```text
DO_NOT_SET_SKIP_CERT_CN_CHECK=true
DO_NOT_DISABLE_SERVER_IDENTITY_VALIDATION

DO_NOT_ADD_CURRENT_SITE_IP_TO_BROKER_CERTIFICATE_AS_WORKAROUND

DO_NOT_FORCE_BROKER_HOST_TO_TLS_DNS_NAME_AS_WORKAROUND

DO_NOT_REPAIR_BROKER_OR_DYNSEC_TO_HIDE_THE_FIRMWARE_DEFECT
```

The product must continue to support a direct IP TCP target with a separate DNS TLS identity.

---

## 22. Mandatory regression matrix

| Case | TCP broker host | TLS expected name | Certificate identity | Expected |
|---|---|---|---|---|
| A | DNS-A | DNS-A | DNS-A | PASS |
| B | IP | DNS-A | DNS-A only | **PASS** |
| C | IP | DNS-B | DNS-A only | FAIL |
| D | IP | DNS-A | correct name, wrong CA | FAIL |
| E | IP | DNS-A | correct name, invalid time | FAIL |

Case B is mandatory. It is the dimension the earlier A/B isolated E2E did not cover.

Also prove the whole state-use chain:

```text
credential/provisioning bundle
→ persisted broker state
→ load_runtime_state_()
→ configure_mqtt_()
→ ESPHome MQTT backend
→ ESP-MQTT / ESP-IDF TLS verification-name field
```

A schema field that exists but is never consumed is not sufficient.

---

## 23. Current failure-fuse state

```text
CURRENT_EXECUTOR_FAILURE_STREAK=0
ROUTE_AUDIT_REQUIRED=false
```

The mandatory route audit reset the earlier streak, and later corrections/serial reconciliation completed without another pair of consecutive executor/preclaim nonclosures.

---

## 24. Current mutation state

At session close:

```text
SOURCE_REPAIR_EXECUTED=false

BOARD_C_FIRMWARE_UPDATE_EXECUTED=false
BOARD_C_SERIAL_REOPENED=false

T1_RUNTIME_MUTATION_EXECUTED=false
BROKER_MUTATION_EXECUTED=false
MANAGER_MUTATION_EXECUTED=false
DYNSEC_MUTATION_EXECUTED=false
PAIRING_MUTATION_EXECUTED=false
```

The final closeout performed documentation mutations only.

---

## 25. Source-repair authorization candidate

Candidate only:

```text
AUTHORIZATION=
R6-BOARD-C-TLS-SERVER-NAME-FIRMWARE-SOURCE-REPAIR-20260830-01

SCOPE=
EXACT_GUARDED_SOURCE_TLS_SERVER_NAME_MINIMAL_REPAIR_TESTS_AND_KF_ONLY

AUTHORIZATION_GRANTED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
```

This handoff does not grant the authorization.

Even if later granted, that authorization is source/test/documentation only and does not authorize:

```text
BOARD_ACCESS
SERIAL_OPEN
FLASH
NVS_MUTATION
T1_RUNTIME_MUTATION
BROKER_MUTATION
MANAGER_MUTATION
DYNSEC_MUTATION
PAIRING_MUTATION
```

Firmware materialization/deployment and Board C physical re-acceptance require separate later authorization.

---

## 26. Next-conversation read-only start sequence

The next conversation must not begin by modifying source.

Required sequence:

1. Read this V1.1 handoff.
2. Read `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`.
3. Read the P9 executor/oracle supplement.
4. Rebind guarded HEAD/tree.
5. Verify current documentation branch remains documentation-only relative to guarded source.
6. Read the exact ESPHome MQTT ESP32 backend used by the frozen build.
7. Read the exact ESP-MQTT / ESP-IDF configuration surface used by that build.
8. Determine the minimal supported independent TLS expected-name setter.
9. Determine the smallest changed-file/hunk allowlist.
10. Design source/unit/integration regression coverage including mandatory Case B.
11. Reconfirm KF-076/KF-077 status.
12. Only then decide whether to grant the candidate source-repair authorization.

Do not repeat any completed Setup Secret, pairing, registration, NODE_ID, DynSec, credential, application-key, or serial diagnostic step.

---

## 27. Next-conversation startup prompt

```text
继续“温室环境监测系统（ESP32-C6）”项目的 N3-W / FC4 Final Physical Acceptance。

本轮首先进行只读恢复与 TLS firmware repair design，不得自动执行任何源码 mutation、Board C 访问、串口操作、Flash/NVS 操作或 T1 runtime mutation。

GitHub 仓库：
chrenguo-stack/HomeAssistant

首先读取并复核分支：
docs/n3w-fc4-boardc-recapture-handoff-20260829

重点读取：
1. docs/development/N3W_FC4_BoardC_FirstRegistration_TLS_ServerName_RootCause_Closeout_and_FirmwareRepair_Handoff_V1.1_20260830.md
2. docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
3. docs/development/N3W_FC4_BoardC_P9_Executor_Oracle_Incident_Supplement_20260829.md
4. docs/development/N3W_FC4_BoardC_SetupSecret_Recapture_Closeout_and_FreshPairingRebind_Handoff_V1.0_20260829.md

必须保持：

NORTH_STAR=FC4_FINAL_PHYSICAL_ACCEPTANCE
CURRENT_ROUTE_NODE=BOARD_C_FIRST_REGISTRATION
ACTIVE_DETOUR=BOARD_C_TLS_SERVER_NAME_FIRMWARE_REPAIR
RETURN_TO_ROUTE=BOARD_C_FIRST_REGISTRATION_RUNTIME_ACCEPTANCE
NEW_BRANCH_ALLOWED=false

EXECUTION_MODEL=
HIGH_LEVEL_REASONING_PLUS_BOUNDED_CODEX_EXECUTION

HIGH_LEVEL_REASONING_ROLE=CHATGPT
BOUNDED_EXECUTION_ROLE=CODEX

CODEX_MUST_NOT_INFER_AUTHORIZATION=true
CODEX_MUST_NOT_EXPAND_SCOPE=true
CODEX_MUST_STOP_ON_PRECLAIM_FAILURE=true
DSL_OR_EXECUTION_CONTRACT_IS_NOT_SELF_EXECUTING=true

当需要 Codex 执行时，ChatGPT 必须提供实际可执行 command/script，除非当前 Codex 环境明确支持该 execution contract 作为可执行接口。

冻结产品源：

FROZEN_PRODUCT_SOURCE_HEAD=
1f80d54ff5f84056e0559a7d8cc80427c5e0bb14

FROZEN_PRODUCT_SOURCE_TREE=
f3b8095c62e8a4838eb1b614f05c932f54f5226d

guarded source：

GUARDED_HEAD=
867c84d9d90f9c56d2446d9aa1a13c31ac593480

GUARDED_TREE=
de670366fe452637e802fb261929613047805964

当前已证明：

FIRST_REGISTRATION_COMMIT_PROVEN=true

TLS_SERVER_NAME_BINDING_ROOT_CAUSE=PROVEN

ROOT_CAUSE=
FIRMWARE_IGNORES_PROVISIONED_BROKER_TLS_SERVER_NAME

PRODUCT_BLOCKER_PROVEN=true
FAIL_CLASS=PRODUCT_BLOCKER

BOARD_C_REPAIR_REQUIRED=true
BROKER_REPAIR_REQUIRED=false
MANAGER_REPAIR_REQUIRED=false
DYNSEC_REPAIR_REQUIRED=false
PAIRING_REPAIR_REQUIRED=false

KF-075=GUARDED
KF-076=OPEN
KF-077=OPEN

最近一次 Board C 串口授权：
R6-BOARD-C-READ-ONLY-SERIAL-TLS-DIAGNOSTIC-20260830-01

该授权：
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
SERIAL_OPEN_COUNT=1

绝对不得重放。

不得重新：
Setup Secret import
pairing
NODE_ID allocation
DynSec provisioning
credential generation
application-key provisioning
NVS erase

下一阶段首先只读确认：
- exact ESPHome MQTT ESP32 backend；
- exact ESP-MQTT / ESP-IDF TLS verification-name API；
- 如何保持 TCP_CONNECT_TARGET=broker_host；
- 如何独立设置 TLS_EXPECTED_SERVER_NAME=broker_tls_server_name；
- 最小 changed-file/hunk allowlist；
- 回归矩阵，尤其 host=IP / tls_name=DNS / DNS-only SAN => PASS；
- KF-076/KF-077 当前状态。

禁止通过：
skip_cert_cn_check
关闭 hostname validation
给当前现场 IP 增加 certificate SAN
强制 broker_host 等于 TLS DNS
来绕过问题。

源码 mutation 候选授权：
R6-BOARD-C-TLS-SERVER-NAME-FIRMWARE-SOURCE-REPAIR-20260830-01

当前：
AUTHORIZATION_GRANTED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

先完成只读 source repair design，再决定是否授权。
```

---

## 28. Handoff terminal

```text
HANDOFF_VERSION=V1.1
HANDOFF_DATE=2026-08-30

DOCUMENTATION_CLOSEOUT=PASS
PRODUCT_SOURCE_MUTATION_IN_CLOSEOUT=false

NORTH_STAR=FC4_FINAL_PHYSICAL_ACCEPTANCE
CURRENT_ROUTE_NODE=BOARD_C_FIRST_REGISTRATION
ACTIVE_DETOUR=BOARD_C_TLS_SERVER_NAME_FIRMWARE_REPAIR
RETURN_TO_ROUTE=BOARD_C_FIRST_REGISTRATION_RUNTIME_ACCEPTANCE
NEW_BRANCH_ALLOWED=false

EXECUTION_MODEL=HIGH_LEVEL_REASONING_PLUS_BOUNDED_CODEX_EXECUTION
HIGH_LEVEL_REASONING_ROLE=CHATGPT
BOUNDED_EXECUTION_ROLE=CODEX
DSL_OR_EXECUTION_CONTRACT_IS_NOT_SELF_EXECUTING=true

FIRST_REGISTRATION_COMMIT_PROVEN=true

TLS_SERVER_NAME_BINDING_ROOT_CAUSE=PROVEN
ROOT_CAUSE=FIRMWARE_IGNORES_PROVISIONED_BROKER_TLS_SERVER_NAME

PRODUCT_BLOCKER_PROVEN=true
FAIL_CLASS=PRODUCT_BLOCKER

BOARD_C_REPAIR_REQUIRED=true
BROKER_REPAIR_REQUIRED=false
MANAGER_REPAIR_REQUIRED=false
DYNSEC_REPAIR_REQUIRED=false
PAIRING_REPAIR_REQUIRED=false

KF_075_STATUS=GUARDED
KF_076_STATUS=OPEN
KF_077_STATUS=OPEN

CURRENT_EXECUTOR_FAILURE_STREAK=0
ROUTE_AUDIT_REQUIRED=false

SOURCE_REPAIR_EXECUTED=false
BOARD_C_FIRMWARE_UPDATE_EXECUTED=false
BOARD_C_SERIAL_REOPENED=false

NEXT_ROUTE_ACTION=
BOARD_C_TLS_SERVER_NAME_FIRMWARE_REPAIR_DESIGN

SOURCE_MUTATION_AUTHORIZED=false
BOARD_ACCESS_AUTHORIZED=false
```

End of handoff.
