# 温室环境监测系统（ESP32-C6）
# N3-W T1 Broker 8883 Dynamic Ingress Guard
# 新会话交接文档 V1.0 — 2026-09-26

```text
HANDOFF_TEMPLATE_VERSION=1.2
PROJECT_WORKING_CONTEXT_VERSION=1.0
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

> 本文只保存当前阶段增量。长期规则读取 `N3W_PROJECT_WORKING_CONTEXT.md`。  
> fresh repository/runtime/live evidence 与本文冲突时，以 fresh 直接证据为准并先停止执行。  
> 私有 T1 locator、私网地址、凭据和 raw board identity 不写入公开 GitHub。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=T1_BROKER_LAN_IP_INDEPENDENT_RECOVERY
CURRENT_STOP_POINT=READONLY_REBIND_COMPLETE_LIVE_WILDCARD_BLOCKED_BY_MISSING_INGRESS_GUARD
NEXT_ONE_GATE=N3W_T1_BROKER_8883_DYNAMIC_INGRESS_GUARD_SOURCE_DESIGN_20260926_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

当前对话已完成 PR #475 B1 source closure 和 T1 fresh read-only rebind。新会话从 8883 动态 ingress guard 的源码/部署设计开始，不直接进入 live Broker recreate。

---

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.0
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false

STAGE_SPECIFIC_OVERRIDE_COUNT=2
STAGE_OVERRIDES=
1. 新会话中每次回复必须先写“主线任务、支线任务、当前任务”
2. 除非用户明确提出转交 Astra，否则任务由当前 ChatGPT 对话继续执行
```

固定回复开头：

```text
主线任务：N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
支线任务：T1 Broker LAN-IP-independent binding / 8883 dynamic ingress guard
当前任务：N3W_T1_BROKER_8883_DYNAMIC_INGRESS_GUARD_SOURCE_DESIGN_20260926_01
```

---

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=先恢复 T1 Broker/Manager 的客户网络可迁移性，再恢复 PR474 的物理验收
FINAL_ACCEPTANCE_TARGET=客户 LAN/DHCP 变化后 T1 可自动恢复 Broker；Broker 入口受控；Manager 本机 TLS 连续性保持；后续节点与 Relay 物理路线可继续验证
DEFERRED_OR_OUT_OF_SCOPE=B2 stable T1 name/TLS identity；B3 existing-node address migration；PR474 physical validation；board mutation
```

---

## 3. Frozen Authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=b32878682ab4981fd38b8982caefed95ba3e204d
TREE=NOT_APPLICABLE:next gate does not depend on a frozen repository tree hash

PR475=475
PR475_BASE=b32878682ab4981fd38b8982caefed95ba3e204d
PR475_HEAD=c070cc50c72cbbd261e8e8ba6e70d00aa4ef5fd6
PR475_BRANCH=fix/n3w-t1-broker-lan-ip-independent-binding-20260925
PR475_STATE=OPEN_DRAFT
PR475_SOURCE_REVIEW_R3=PASS
PR475_CI=12_OF_12_PASS
PR475_MERGE=false

PR474=474
PR474_HEAD=d3c158b4376ca0577e4a3a45a18a6c5c6e994e75
PR474_STATE=OPEN_DRAFT
PR474_SOURCE_REVIEW=PASS
PR474_PHYSICAL_VALIDATION=PENDING
PR474_MERGE=false

ARTIFACT_ID=NOT_APPLICABLE:T1 deployment design gate
ARTIFACT_SHA256=NOT_APPLICABLE:T1 deployment design gate
DEPLOYED_SOURCE_HEAD=NOT_APPLICABLE:T1 deployment design gate
DEPLOYED_SOURCE_TREE=NOT_APPLICABLE:T1 deployment design gate

OTHER_REQUIRED_AUTHORITY=docs/development/N3W_T1_BROKER_NETWORK_INDEPENDENCE_PROGRESS_ALIGNMENT_20260926.md; docs/development/N3W_T1_BROKER_NETWORK_INDEPENDENCE_ARCHITECTURE_DECISIONS_20260926.md
```

---

## 4. Current Live Baseline

```text
MANAGER_STATE=RESTARTING
MANAGER_RESTART_STATE=REPEATED_RESTARTS_WHILE_BROKER_UNAVAILABLE
BROKER_STATE=EXITED_BIND_FAILURE
HOMEASSISTANT_STATE=UNKNOWN_FRESH

BOARD_A_POWER_STATE=UNKNOWN_FRESH
BOARD_A_LOCATION_ROLE=UNKNOWN_FRESH
BOARD_B_POWER_STATE=UNKNOWN_FRESH
BOARD_B_LOCATION_ROLE=UNKNOWN_FRESH

APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false
T1_RUNTIME_MUTATION=false
```

Fresh live details needed by the next gate:

```text
NETWORK_AUTHORITY=NetworkManager
WIRED_INTERFACE=eth0
WIRED_ADDRESS_MODE=DHCP
DOCKER_FIREWALL_BACKEND=iptables
DOCKER_USER_CHAIN_PRESENT=true
DOCKER_USER_CUSTOM_RULE_COUNT=0
NFTABLES_SERVICE=disabled/inactive
FC4_SYSTEMD_DEPLOYMENT_UNIT=ABSENT
CURRENT_8883_INGRESS_GUARD=ABSENT

MANAGER_INTERNAL_MQTT_HOST=armbian
MANAGER_EXACT_GETADDRINFO_FIRST=AF_INET/127.0.1.1
MANAGER_EXACT_GETADDRINFO_SECOND=AF_INET6/::1
BROKER_CERT_SAN=DNS:armbian
KF035_PREBIND=PASS
POST_RECREATE_TCP_TLS=NOT_YET_PROVEN
```

Private LAN addresses and private T1 filesystem locators are intentionally omitted.

---

## 5. Proven Current Facts

```text
PR475_B1_SOURCE_STAGE=CLOSED_PASS
PR475_CI=12_OF_12_PASS
PR475_MERGE_BLOCKER_COUNT=0

LIVE_PRIVATE_COMPOSE_BOUND=true
LIVE_PRIVATE_COMPOSE_SHA256=d3a2bb681db523d4414e64fd26d49074d76c90ac5265493f18ec760494472f

BROKER_FAILURE_CAUSE=stale concrete customer-LAN Docker host publication
BROKER_MOSQUITTO_LISTENER_ALREADY_WILDCARD=true
BROKER_ALLOW_ANONYMOUS=false
BROKER_DYNSEC_ENABLED=true

BROKER_RENDERED_NETWORK_KEYS=n3wfc4-private,n3wfc4-services
BROKER_EFFECTIVE_NETWORK_MAPPING=PASS
MANAGER_HOST_NETWORK=PASS
MANAGER_PORTS_ABSENT=PASS

CURRENT_8883_INGRESS_RESTRICTION=NONE
NETWORKMANAGER_MANAGES_ETH0=true
CURRENT_CUSTOMER_SUBNET_IS_DYNAMIC=true
```

```text
INFERENCE_DESIGN_DIRECTION=Use a dedicated DOCKER-USER ingress guard that derives the current eth0 connected IPv4 subnet at runtime and fails closed when it cannot derive a unique trusted subnet.
```

This design direction has not yet been implemented or live-tested.

---

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=1
CURRENT_BLOCKER=A6 wildcard activation has no durable trusted-LAN ingress guard
ROOT_CAUSE=Current Docker/host firewall state permits published-port traffic without a project-specific 8883 source restriction
PROVEN_BY=Fresh iptables/DOCKER-USER/NetworkManager read-only evidence
SOURCE_DEFECT_PROVEN=true
RUNTIME_DEFECT_PROVEN=true
```

The original B1 source defect is repaired in PR #475. The remaining blocker is a live-deployment safety prerequisite, not a reopening of B1 source review.

---

## 7. Closed / Forbidden Routes

```text
HARDCODE_CURRENT_T1_IPV4=CLOSED:recreates the original customer-LAN portability defect
HARDCODE_CURRENT_CUSTOMER_SUBNET=CLOSED:same portability defect at firewall layer
DIRECT_WILDCARD_RECREATE_WITHOUT_INGRESS_GUARD=CLOSED:expands IPv4 exposure
SWITCH_DOCKER_FIREWALL_BACKEND_TO_NFTABLES=CLOSED:not required for this repair
MANUAL_ONE_OFF_IPTABLES_ONLY=CLOSED:not durable across reboot/network change
REOPEN_PR474_SOURCE=CLOSED:source review already PASS
REOPEN_KF094_KF095_KF096=CLOSED:not part of this infrastructure route
B2_B3_IN_THIS_GATE=CLOSED:separate follow-up work
```

---

## 8. Authorization Ledger

```text
AUTHORIZATION=GitHub progress alignment and new-chat handoff requested by user
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=NONE

SOURCE_DESIGN_CONTINUATION=AUTHORIZED_BY_NEW_CHAT_CONTINUATION_REQUEST
LIVE_T1_MUTATION_AUTHORIZED=false
BROKER_RECREATE_AUTHORIZED=false
MANAGER_MUTATION_AUTHORIZED=false
BOARD_ACCESS_AUTHORIZED=false
PR474_MERGE_AUTHORIZED=false
PR475_MERGE_AUTHORIZED=false
```

---

## 9. Rollback Authority

The next gate is design-only.

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:SOURCE_DESIGN_ONLY
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=true
EXISTING_PRIVATE_COMPOSE_ROLLBACK_MATERIAL_PRESENT=true
BROKER_DATA_AUTHORITY_BOUND=true
TLS_AUTHORITY_BOUND=true
```

Any later live mutation gate must take fresh prechange hashes/snapshots and must not rely only on historical backups.

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_BROKER_8883_DYNAMIC_INGRESS_GUARD_SOURCE_DESIGN_20260926_01
```

### Purpose

Design the smallest durable guard that allows Broker TCP/8883 only from the T1's current trusted wired LAN while keeping Docker's publication independent of a concrete customer IP.

The design must cover:

- `DOCKER-USER` ownership and original-destination TCP/8883 matching;
- runtime derivation of the current `eth0` connected IPv4 subnet;
- NetworkManager-triggered refresh after DHCP/network changes;
- boot/restart ordering with Docker and NetworkManager;
- idempotence and atomic rule replacement;
- fail-closed behavior when trusted subnet authority is absent or ambiguous;
- preservation of unrelated Docker/firewall rules;
- rollback and observability;
- source/host regression strategy.

It cannot prove live ingress behavior, Broker restart success, Manager TLS reconnection, node hostname resolution, or board telemetry.

### Inputs

```text
INPUT_1=PR475 exact head c070cc50c72cbbd261e8e8ba6e70d00aa4ef5fd6
INPUT_2=Fresh T1 read-only network/firewall evidence in progress-alignment document
INPUT_3=NetworkManager manages eth0 with DHCP
INPUT_4=Docker firewall backend is iptables and DOCKER-USER exists
INPUT_5=No existing FC4 systemd deployment unit and no existing 8883 ingress guard
```

### Operations

```text
1. Fresh-rebind repository main and PR475 exact head.
2. Inspect existing deployment/tooling conventions before introducing a new helper or service.
3. Freeze exact packet-filter semantics, including Docker DNAT/original-destination behavior.
4. Define one authority for deriving trusted wired-LAN subnet.
5. Define systemd + NetworkManager refresh ownership and fail-closed startup behavior.
6. Define idempotent rule lifecycle, rollback, and non-target invariants.
7. Define focused source/host tests and a later live acceptance oracle.
8. Record the design in GitHub; do not implement or deploy unless a later gate authorizes it.
```

### PASS / FAIL / STOP

```text
PASS_IF=Design has one durable authority, no customer-specific IP/subnet constants, fail-closed semantics, bounded ownership, regression tests, and a reversible deployment path.
FAIL_IF=Design depends on current LAN constants, flushes Docker/global firewall state, weakens TLS/DynSec, lacks DHCP-change refresh, or cannot fail closed.
STOP_BOUNDARY=Source/design closure only; no T1 mutation or Broker recreate.

AUTO_EXECUTE_NEXT_GATE=false
```

---

## 11. Hard Allowed / Forbidden Scope

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

```text
- GitHub fresh read-only inspection
- public source/design analysis
- creation/update of a bounded public design document on a purpose-specific branch
- source/host test design
- comparison against PR475/KF034/KF035/KF097 contracts
```

### FORBIDDEN

```text
- T1 firewall mutation
- T1 Compose mutation
- Broker recreate/start
- Manager restart or configuration mutation
- Docker daemon/firewall-backend changes
- board access, firmware, NVS, serial
- B2/B3 implementation
- PR474/PR475 merge
- re-opening closed radio/physical routes
```

---

## 12. Execution Contract

```text
EXECUTOR=ChatGPT current conversation
EXECUTION_METHOD=GitHub connector + bounded source/design review
DIRECT_CODE_SUPPLIED=false
DSL_COMPILATION_USED=false

ASTRA_DEFAULT=false
ASTRA_ONLY_IF_USER_EXPLICITLY_REQUESTS=true
```

Use short phased GitHub calls. Do not auto-repair or auto-cross into implementation/live recovery.

---

## 13. Expected Closure

```text
=== N3W_T1_BROKER_8883_DYNAMIC_INGRESS_GUARD_SOURCE_DESIGN_20260926_01 CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=SOURCE_DESIGN_CONTINUATION
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true

DESIGN_AUTHORITY=
DOCKER_FILTER_HOOK=
TRUSTED_SUBNET_AUTHORITY=
NETWORK_CHANGE_REFRESH_AUTHORITY=
BOOT_ORDERING=
FAIL_CLOSED_BEHAVIOR=
RULE_IDEMPOTENCE=
ROLLBACK_MODEL=
SOURCE_TEST_PLAN=
LIVE_ACCEPTANCE_PLAN=

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

SOURCE_DESIGN_RESULT=
NEXT_ROUTE=
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=N3W_T1_BROKER_8883_DYNAMIC_INGRESS_GUARD_SOURCE_REPAIR_20260926_01
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=false_for_repository_source_repair_but_live_mutation_still_requires_separate_gate

AUTO_REPAIR_AFTER_FAIL=false
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=true_if_design_creates_new durable guard
EXISTING_KF_GUARD_USED=KF034,KF035,KF097
NEW_KF_REQUIRED=false_by_default
```

PR #475 carries the current KF-097 source change; main does not yet contain it because PR #475 is unmerged.

---

## 16. New Chat Start Prompt Contract

The exact copyable prompt is intentionally delivered separately to the user. The new chat must read:

```text
1. this handoff
2. docs/development/N3W_PROJECT_WORKING_CONTEXT.md
3. docs/development/N3W_CURRENT_STATE.md
4. docs/development/N3W_CURRENT_STATE_INDEX.md
5. docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
6. docs/development/N3W_T1_BROKER_NETWORK_INDEPENDENCE_PROGRESS_ALIGNMENT_20260926.md
7. docs/development/N3W_T1_BROKER_NETWORK_INDEPENDENCE_ARCHITECTURE_DECISIONS_20260926.md
8. PR #475 exact head and current state
9. PR #474 only for frozen source/physical-defer context
```

It must then fresh-rebind the minimum repository state and enter only the specified next gate.

---

## 17. Final Frozen State

```text
CURRENT_STAGE=T1_BROKER_LAN_IP_INDEPENDENT_RECOVERY
CURRENT_STOP_POINT=READONLY_REBIND_COMPLETE_LIVE_WILDCARD_BLOCKED_BY_MISSING_INGRESS_GUARD
CURRENT_BLOCKER=A6_NO_DURABLE_8883_INGRESS_GUARD
LIVE_SYSTEM_STATE=BROKER_EXITED_MANAGER_RESTARTING_NO_T1_MUTATION_PERFORMED
NEXT_ONE_GATE=N3W_T1_BROKER_8883_DYNAMIC_INGRESS_GUARD_SOURCE_DESIGN_20260926_01

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

PROJECT_WORKING_CONTEXT_VERSION=1.0
HANDOFF_TEMPLATE_VERSION=1.2

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

---

## 18. Handoff Compliance Audit

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_TEMPLATE_VERSION=1.2
PROJECT_WORKING_CONTEXT_VERSION=1.0

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
