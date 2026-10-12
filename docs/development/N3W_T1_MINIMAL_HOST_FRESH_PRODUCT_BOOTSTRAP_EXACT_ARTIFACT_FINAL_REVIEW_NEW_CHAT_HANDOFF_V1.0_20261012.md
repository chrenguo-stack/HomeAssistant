# 温室环境监测系统（ESP32-C6） / N3-W
# T1 minimal-host fresh product bootstrap exact HEAD / artifact 最终复核
# 新会话交接文档 V1.0 — 2026-10-12

```text
HANDOFF_TEMPLATE_VERSION=1.2
PROJECT_WORKING_CONTEXT_VERSION=1.0
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

> 本文只保存当前阶段增量。长期规则引用 `N3W_PROJECT_WORKING_CONTEXT.md`。  
> 本 handoff 不指定 historical exact handoff-standard authority；不要恢复已废弃的旧 DSL/Codex 执行模式。  
> fresh repository/runtime/live evidence 与本文冲突时，以 fresh 直接证据为准并先停止执行。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=FRESH_BOOTSTRAP_DEPLOYABLE_PATH_SOURCE_CI_CLOSED_PASS
CURRENT_STOP_POINT=EXACT_PRODUCT_SOURCE_AND_DEPLOYABLE_ARTIFACT_BOUND_BEFORE_FINAL_INDEPENDENT_REVIEW
NEXT_ONE_GATE=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_EXACT_HEAD_ARTIFACT_FINAL_SOURCE_AND_EXECUTION_PATH_REVIEW_20261012_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

本轮已经完成 minimal-host fresh bootstrap deployable path 的源码、CI、exact artifact 构建与绑定。对话上下文已较长，因此把**最终源码与执行路径复核**放到新会话；新会话不是重新开发，也不是进入 live apply，而是只复核下面冻结的 exact source + exact artifact。

---

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.0
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false

STAGE_SPECIFIC_OVERRIDE_COUNT=0
STAGE_OVERRIDES=NONE
```

---

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=ARMBIAN_DOCKER_NETWORK_MINIMAL_HOST_TO_FRESH_GREENHOUSE_PRODUCT_BOOTSTRAP
FINAL_ACCEPTANCE_TARGET=FROM_MINIMAL_HOST_CREATE_FRESH_IDENTITY_STATE_SECRETS_CA_TLS_DYNSEC_MANAGER_HA_RUNTIME_WITH_ZERO_NODE_CREDENTIALS_AND_LEAVE_PRODUCTION_SERVICES_STOPPED
DEFERRED_OR_OUT_OF_SCOPE=LIVE_T1_BOOTSTRAP_APPLY,PRODUCTION_ACTIVATION,FIRST_PAIR,BOARD_NVS_RF,PR541_MERGE
```

---

## 3. Frozen Authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
TREE=ee977996a4c962097684519841dce2e3bcba23f2

CANDIDATE_REF=plan/n3w-t1-full-fresh-install-from-zero-20261010@d5a1be83aa5ab039696297ebdfa4ce787fe168ba
CANDIDATE_HEAD=d5a1be83aa5ab039696297ebdfa4ce787fe168ba
CANDIDATE_TREE=73d720ccf88348d4dcc60e21f48c9a81048f3f30

ARTIFACT_ID=11723440338
ARTIFACT_SHA256=sha256:588e1d793c6a03193e6ecbb46fd809f44bfed45659cf00566a16cf1faf779f06

DEPLOYED_SOURCE_HEAD=NOT_APPLICABLE:FRESH_PRODUCT_BOOTSTRAP_NOT_DEPLOYED
DEPLOYED_SOURCE_TREE=NOT_APPLICABLE:FRESH_PRODUCT_BOOTSTRAP_NOT_DEPLOYED

OTHER_REQUIRED_AUTHORITY=RUN_38194585872;PAYLOAD_ARCHIVE_SHA256_5f79c883ba16d06e0bc5f89a36e829c43e3083ffd57e222d429baf1a8801d873;PAYLOAD_MANIFEST_SHA256_067c7d5af5d816cd8800de374cc6532126c2a3f6f7dfe37db915c784dc9459b4
```

Additional exact artifact identity:

```text
ARTIFACT_NAME=n3w-t1-fresh-bootstrap-deployable-d5a1be83aa5ab039696297ebdfa4ce787fe168ba
ARTIFACT_SIZE_BYTES=814749903
EXACT_HEAD_WORKFLOW_COUNT=25
EXACT_HEAD_WORKFLOW_PASS_COUNT=25
ALL_EXACT_HEAD_CI=PASS
```

PR #541 may become docs-only-ahead of `CANDIDATE_HEAD` after this handoff is archived. The next review must keep `d5a1be83...` as the **product-source authority bound to artifact #11723440338**, and must not silently substitute a later documentation-only PR HEAD.

---

## 4. Current Live Baseline

The last direct live T1 proof is the completed minimal-baseline normalization. There has been no project-authorized T1 access in the deployable-path source/CI gate, but the next chat must not claim a present live state without a fresh read.

```text
LAST_PROVEN_T1_BASELINE=ARMBIAN + DOCKER + NETWORK ONLY
LAST_PROVEN_CONTAINERS=0
LAST_PROVEN_IMAGES=0
LAST_PROVEN_VOLUMES=0
LAST_PROVEN_DOCKER_NETWORKS=bridge,host,none
LAST_PROVEN_PRODUCT_PATHS_ABSENT=true
LAST_PROVEN_PRODUCT_UNIT_ABSENT=true
LAST_PROVEN_PRODUCT_FIREWALL_ABSENT=true
LAST_PROVEN_PRODUCTION_LISTENERS=0

MANAGER_STATE=UNKNOWN_FRESH:last_proven_absent
MANAGER_RESTART_STATE=UNKNOWN_FRESH
BROKER_STATE=UNKNOWN_FRESH:last_proven_absent
HOMEASSISTANT_STATE=UNKNOWN_FRESH:last_proven_absent

BOARD_A_POWER_STATE=UNKNOWN_FRESH
BOARD_A_LOCATION_ROLE=UNKNOWN_FRESH
BOARD_B_POWER_STATE=UNKNOWN_FRESH
BOARD_B_LOCATION_ROLE=UNKNOWN_FRESH

APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false
T1_RUNTIME_MUTATION=false
```

The next gate is source/artifact-only, so it does not need T1 access. A fresh T1 read-only recheck is required only before any later live bootstrap authorization.

---

## 5. Proven Current Facts

```text
MINIMAL_BASELINE_NORMALIZATION=CLOSED_PASS
NORMALIZATION_SOURCE_AUTHORITY=43207da98bc0e116af2845b690b3f0ee230637ab

PRODUCT_SOURCE_HEAD=d5a1be83aa5ab039696297ebdfa4ce787fe168ba
PRODUCT_SOURCE_TREE=73d720ccf88348d4dcc60e21f48c9a81048f3f30
ALL_EXACT_HEAD_CI=PASS:25_OF_25

FRESH_BOOTSTRAP_DEPLOYABLE_RUN=38194585872
FRESH_BOOTSTRAP_DEPLOYABLE_CI=PASS
ARTIFACT_ID=11723440338
ARTIFACT_DIGEST=sha256:588e1d793c6a03193e6ecbb46fd809f44bfed45659cf00566a16cf1faf779f06
PAYLOAD_ARCHIVE_SHA256=5f79c883ba16d06e0bc5f89a36e829c43e3083ffd57e222d429baf1a8801d873
PAYLOAD_MANIFEST_SHA256=067c7d5af5d816cd8800de374cc6532126c2a3f6f7dfe37db915c784dc9459b4

FRESH_DEPLOYMENT_GATE=PASS
FRESH_LIVE_ADAPTER_PRECOMMIT_REHEARSAL=PASS
FRESH_BOOTSTRAP_INNER_BINDING=PASS
FRESH_BOOTSTRAP_DEPLOYABLE_POST_UPLOAD_BINDING=PASS

CI_T1_ACCESS=false
CI_LIVE_MUTATION=false
CI_PRODUCTION_SERVICE_START=false
CI_BOARD_ACCESS=false
```

No conclusion here says the live T1 bootstrap path is already approved or physically/live accepted. That is intentionally deferred.

---

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=0
CURRENT_BLOCKER=NONE_PROVEN
ROOT_CAUSE=NOT_APPLICABLE
PROVEN_BY=EXACT_HEAD_25_OF_25_CI_PASS_AND_DEPLOYABLE_ARTIFACT_BINDING_PASS
SOURCE_DEFECT_PROVEN=false
RUNTIME_DEFECT_PROVEN=false
```

The pending independent final review is a release/readiness decision gate, not a proven defect.

---

## 7. Closed / Forbidden Routes

```text
OLD_STAGING_AUTH_03=CLOSED:SUPERSEDED_BY_MINIMAL_HOST_FRESH_BOOTSTRAP_ROUTE
OLD_STAGING_PAYLOAD_ARTIFACT_11721250984=CLOSED:LEGACY_S20_MANAGER_AND_SUPERSEDED_EXECUTOR
OLD_IMAGE_ONLY_ARTIFACT_11721600979=CLOSED_AS_DEPLOYMENT_INPUT:VALID_IMAGE_EVIDENCE_ONLY_NOT_DEPLOYABLE_APPLY_PACKAGE
NORMALIZATION_AUTHORIZATION_REPLAY=CLOSED:CONSUMED_PASS_NO_REPLAY
DIRECT_FRESH_BOOTSTRAP_LIVE_APPLY_NOW=CLOSED:NO_LIVE_AUTHORIZATION_AND_FINAL_REVIEW_NOT_DONE
PR541_MERGE_NOW=CLOSED:NOT_AUTHORIZED
BOARD_NVS_RF_ROUTE=CLOSED_FOR_THIS_GATE:OUT_OF_SCOPE
```

---

## 8. Authorization Ledger

```text
AUTHORIZATION=N3W_T1_MINIMAL_BASELINE_NORMALIZATION_LIVE_APPLY_20261012_01
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=NOT_APPLICABLE:CLOSED_PASS
```

Future fresh bootstrap authorization exists in source but has **not** been granted:

```text
PROPOSED_AUTHORIZATION=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_01
GRANTED=false
CLAIMED=false
CONSUMED=false
```

This handoff and the next review do not grant it.

---

## 9. Rollback Authority

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_SOURCE_AND_ARTIFACT_REVIEW_GATE
```

No live mutation, service restart, product filesystem write, Docker mutation, or board operation is allowed in the next gate.

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_EXACT_HEAD_ARTIFACT_FINAL_SOURCE_AND_EXECUTION_PATH_REVIEW_20261012_01
```

### Purpose

Independently review the exact product source head and exact deployable artifact before any T1 live preexecution. The review must decide whether the repository-owned path is internally complete, fail-closed, exact-bound, and safe to advance to a **separate future read-only live preexecution**. It cannot prove live T1 behavior and cannot grant/consume the future live authorization.

### Inputs

```text
SOURCE_HEAD=d5a1be83aa5ab039696297ebdfa4ce787fe168ba
SOURCE_TREE=73d720ccf88348d4dcc60e21f48c9a81048f3f30
RUN_ID=38194585872
ARTIFACT_ID=11723440338
ARTIFACT_DIGEST=sha256:588e1d793c6a03193e6ecbb46fd809f44bfed45659cf00566a16cf1faf779f06
PAYLOAD_ARCHIVE_SHA256=5f79c883ba16d06e0bc5f89a36e829c43e3083ffd57e222d429baf1a8801d873
PAYLOAD_MANIFEST_SHA256=067c7d5af5d816cd8800de374cc6532126c2a3f6f7dfe37db915c784dc9459b4
```

Primary review files:

```text
tools/n3w_t1_fresh_product_bootstrap.py
tools/n3w_t1_fresh_product_staging_host.py
host/greenhouse-manager/src/greenhouse_manager/bootstrap/fresh_installer.py
tools/n3w_t1_clean_product_deployment_gate.py
infra/n3w-t1/production/docker-compose.fresh.yml
.github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml
```

### Operations

```text
1. Fresh read-only rebind main, PR #541, exact source HEAD/tree and exact-head CI.
2. Rebind run 38194585872 and artifact 11723440338, including artifact digest and inner payload/manifest sidecars.
3. Review payload extraction and member safety: path traversal, symlink/hardlink, device/FIFO/special members, manifest exactness.
4. Review offline ARM64 image load/binding and post-load tar release; prove no post-claim registry dependency.
5. Review minimal-host preflight and prove no product mutation before authorization claim.
6. Review durable claim marker / host-wrapper claim observation / unknown-outcome handling / no-replay semantics.
7. Review fresh identity, Manager/N3-W state, Broker TLS/CA/secrets and DynSec creation; node credential count must remain 0.
8. Review runtime staging ownership, permissions, exact source completeness and product-state target paths.
9. Review commit_candidate atomicity/boundaries and transaction-owned cleanup on failures before/after commit.
10. Review stopped_postcheck: 0 running containers/listeners, exact image/network expectations, product paths/unit/firewall state, deployment gate, state/DynSec/credential audit.
11. Prove production service start/activation, board/NVS/RF and PR merge are outside this path.
12. Return PASS/FAIL/STOP and stop; do not repair source or enter live T1 preexecution automatically.
```

### PASS / FAIL / STOP

```text
PASS_IF=EXACT_SOURCE_ARTIFACT_BINDING_PASS_AND_ALL_REVIEW_AXES_CLOSED_WITH_NO_BLOCKER
FAIL_IF=ANY_SOURCE_ARTIFACT_CLAIM_CLEANUP_COMMIT_POSTCHECK_OR_SCOPE_DEFECT_IS_PROVEN
STOP_BOUNDARY=FIRST_SUBSTANTIVE_MISMATCH_OR_FINAL_REVIEW_CLASSIFICATION

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
- GitHub read-only PR/commit/tree/source/CI inspection.
- Download/read exact workflow artifact #11723440338.
- Local/connector-side read-only archive/hash/manifest inspection.
- Static reasoning about execution path and failure semantics.
- After classification only, a bounded public-safe GitHub documentation closure may be committed.
```

### FORBIDDEN

```text
- T1 SSH/live access or any T1 filesystem/Docker/systemd/firewall mutation.
- Running the artifact against T1.
- Claiming or consuming N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_01.
- Starting Broker, Manager or Home Assistant.
- Installing/enabling activation units or dispatcher.
- Board/USB/serial/Flash/NVS/RF access.
- Source/test/workflow repair inside this review gate.
- Automatic retry after any substantive mismatch.
- PR #541 merge.
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=PUBLIC_SAFE_REVIEW_CLOSURE_DOCS_ONLY_AFTER_CLASSIFICATION
```

---

## 12. Execution Contract

```text
EXECUTOR=HIGH_LEVEL_MODEL_USING_GITHUB_READONLY_TOOLS_AND_ARTIFACT_INSPECTION
EXECUTION_METHOD=chat-tool
DIRECT_CODE_SUPPLIED=false
DSL_COMPILATION_USED=false
```

Use phased short GitHub calls. Do not auto-fix. The first substantive mismatch stops the review and returns the evidence to the high-level model.

---

## 13. Expected Closure

```text
=== N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_EXACT_HEAD_ARTIFACT_FINAL_SOURCE_AND_EXECUTION_PATH_REVIEW_20261012_01 CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=NONE_READONLY_REVIEW
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

MAIN_REBIND=
SOURCE_HEAD_REBIND=
SOURCE_TREE_REBIND=
EXACT_HEAD_CI=
RUN_REBIND=
ARTIFACT_ID_REBIND=
ARTIFACT_DIGEST_REBIND=
PAYLOAD_ARCHIVE_SHA256_REBIND=
PAYLOAD_MANIFEST_SHA256_REBIND=

A1_PAYLOAD_EXTRACTION_AND_BINDING=
A2_OFFLINE_IMAGE_LOAD_AND_PLATFORM_BINDING=
A3_PRECLAIM_MINIMAL_HOST_PREFLIGHT=
A4_DURABLE_CLAIM_AND_NO_REPLAY=
A5_FRESH_IDENTITY_STATE_BROKER_DYNSEC=
A6_RUNTIME_STAGING_OWNERSHIP_AND_PERMISSIONS=
A7_COMMIT_BOUNDARY_AND_TRANSACTION_CLEANUP=
A8_STOPPED_POSTCHECK=
A9_NO_PRODUCTION_ACTIVATION=
A10_NO_BOARD_OR_MERGE_SCOPE_EXPANSION=

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

FINAL_SOURCE_EXECUTION_PATH_REVIEW=
NEXT_ROUTE=
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_PREEXECUTION_READONLY
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=YES_BEFORE_ANY_FRESH_BOOTSTRAP_LIVE_APPLY

AUTO_REPAIR_AFTER_FAIL=false
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

PASS does not authorize T1 access or live apply. A later live preexecution must freshly re-prove the T1 minimal baseline before any explicit apply authorization can be considered.

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=false
EXISTING_KF_GUARD_USED=KF-107_OFFLINE_IMAGE_POSTCLAIM_DEPENDENCY_GUARD
NEW_KF_REQUIRED=false
```

The directory-creation CI fixture failure repaired before run #11 is not currently classified as a new product KF.

---

## 16. New Chat Start Prompt

```text
阅读《docs/development/N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_EXACT_ARTIFACT_FINAL_REVIEW_NEW_CHAT_HANDOFF_V1.0_20261012.md》。

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_DEPLOYABLE_PATH_SOURCE_REPAIR_20261012.md
- docs/development/N3W_T1_MINIMAL_BASELINE_NORMALIZATION_LIVE_CLOSURE_20261012.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

先 fresh read-only rebind：
- repository main
- PR #541
- exact product-source HEAD d5a1be83aa5ab039696297ebdfa4ce787fe168ba
- exact tree 73d720ccf88348d4dcc60e21f48c9a81048f3f30
- workflow run 38194585872
- artifact 11723440338
- artifact digest sha256:588e1d793c6a03193e6ecbb46fd809f44bfed45659cf00566a16cf1faf779f06
- payload archive SHA256 5f79c883ba16d06e0bc5f89a36e829c43e3083ffd57e222d429baf1a8801d873
- payload manifest SHA256 067c7d5af5d816cd8800de374cc6532126c2a3f6f7dfe37db915c784dc9459b4

然后只进入：

NEXT_ONE_GATE=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_EXACT_HEAD_ARTIFACT_FINAL_SOURCE_AND_EXECUTION_PATH_REVIEW_20261012_01

这是最终源码与执行路径只读复核。
不得访问或修改真实 T1，不得启动 Broker/Manager/Home Assistant，不得申请或使用 live bootstrap authorization，不得访问板卡，不得 merge PR #541。
发现 substantive mismatch 立即 STOP，不自动修复、不自动重试。

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=FRESH_BOOTSTRAP_DEPLOYABLE_PATH_SOURCE_CI_CLOSED_PASS
CURRENT_STOP_POINT=EXACT_PRODUCT_SOURCE_AND_DEPLOYABLE_ARTIFACT_BOUND_BEFORE_FINAL_INDEPENDENT_REVIEW
CURRENT_BLOCKER=NONE_PROVEN
LIVE_SYSTEM_STATE=UNKNOWN_FRESH;LAST_PROVEN_T1_BASELINE_ARMBIAN_DOCKER_NETWORK_ONLY
NEXT_ONE_GATE=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_EXACT_HEAD_ARTIFACT_FINAL_SOURCE_AND_EXECUTION_PATH_REVIEW_20261012_01

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
