
# N3-W T1 软件环境清洁重装：S0 R1 取证失败后交接 V1.0 — 2026-10-10

HANDOFF_STANDARD_VERSION=1.0
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true
NEXT_ONE_GATE_ONLY=true

交接标准：4300890dff0ce63d5a547df21426e287d084d9ee 所固定的 docs/development/NEW_CHAT_HANDOFF_STANDARD.md 和 docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md。若历史交接、推断与 fresh live T1/GitHub exact evidence 冲突，以更高权限事实为准并 STOP。

## 0. 会话切换结论

用户要求核对上传文件、形成准确到容器/数据目录/服务的清理清单，GitHub 进度对齐，按标准模板交接后新对话继续。

CURRENT_STAGE=T1_SOFTWARE_CLEAN_REDEPLOY_S0_R1_PARTIAL
CURRENT_STOP_POINT=ALL_SIX_CONTAINER_INSPECT_FAILED_EXACT_DELETE_PATHS_UNPROVEN
NEXT_ONE_GATE=N3W_T1_SOFTWARE_OWNERSHIP_S0_R2_EXACT_CONTAINER_AND_DATA_BINDING_READONLY
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true

S0 R1 已证明容器列表、网络关联、unit 名、46 个 Docker 卷名；但六次 Docker inspect metadata 均失败，无一条可靠的 Name→full container ID→宿主 Mount Source/卷归属链。当前不存在可安全执行的精确目录或卷删除清单，不能伪造。这不妨碍形成明确状态的候选分类并完成正式交接。下一会话只补足缺失证据。

## 1. 执行模式

EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
HIGH_LEVEL_MODEL=PRODUCT_ROUTE_AUTHORITY_GATES_AUTHORIZE_AND_CLASSIFY
CODEX=LOW_ORDER_EXACT_DSL_COMPILATION_AND_EVIDENCE_COLLECTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true
DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false

高阶模型维护架构、权限、停止点和证明分类；Codex 机械运行 exact Git/Docker/SSH/只读 JSON 提取，输出 closure，不得修复、不重试、不跨门。若没有 T1 SSH 连接能力，由用户使用 Mac Terminal 运行已版本化命令并上传报告。不要仅因新对话再开发通用执行器。

## 2. Product North Star

CURRENT_PRODUCT_ROUTE=KEEP_ARMBIAN_FRESH_REDEPLOY_N3W_SOFTWARE
PRESERVE=ARMbian_BOOT_DISK_KERNEL_ETH0_NETWORKMANAGER_SSH_DOCKER_UNRELATED_APPLICATIONS
FRESH_INSTALL=N3W_BROKER_DYNSEC_TLS_CA_MANAGER_ZERO_REGISTRATION_CREDENTIAL_REPLAY_RELAY_KEYS
HOME_ASSISTANT=REDEPLOY_ONLY_AFTER_EXCLUSIVE_N3W_OWNER_PROVEN
N3W_BOARD_PAIRING=AFTER_NEW_T1_RUNTIME_ACCEPTANCE
ROLLBACK_EXECUTOR_DEVELOPMENT=STOPPED
OS_REINSTALL=false
WHOLE_DISK_ERASE=false

## 3. Frozen Authorities

Repository: chrenguo-stack/HomeAssistant
MAIN_AT_HANDOFF_PREPARATION=d423211b6196c2f2f0f01dff072c4f877fbe58ee
MAIN_TREE=NOT_NEEDED_FOR_READONLY_GATE_FRESH_REBIND_IF_REQUIRED
SOURCE_BRANCH=plan/n3w-t1-full-fresh-install-from-zero-20261010
HANDOFF_PARENT_BRANCH_COMMIT=0ef361ea287136f8383d3f822672c55ed918d530
PR_541=OPEN_DRAFT
PR_540=CLOSED_UNMERGED_SUPERSEDED
STANDARD_EXACT_COMMIT=4300890dff0ce63d5a547df21426e287d084d9ee

Candidate/artifact: NOT_APPLICABLE because next gate is read-only ownership; no candidate image or deployment artifact yet selected.

Current route authority:
docs/development/N3W_T1_SOFTWARE_CLEAN_REDEPLOY_PRESERVE_ARMBIAN_AUTHORITY_20261010.md

S0 R1 classified evidence:
docs/development/N3W_T1_SOFTWARE_OWNERSHIP_S0_R1_EVIDENCE_CLASSIFICATION_AND_CLEAN_MANIFEST_20261010.md

S0 R2 corrected private-readonly command:
docs/development/N3W_T1_SOFTWARE_OWNERSHIP_S0_R2_EXACT_DOCKER_JSON_AND_MOUNT_READONLY_RUNBOOK_20261010.md

Also authoritative: docs/development/N3W_CURRENT_STATE.md, N3W_CURRENT_STATE_INDEX.md, KNOWN_FAILURES_AND_REGRESSION_GUARDS.md.

Target T1: Armbian arm64 with root partition /dev/mmcblk2p2 and /boot on /dev/mmcblk2p1. Private host IP/MAC/machine ID/serial must not be published. No whole-host wipe.

Uploaded real evidence (private, not posted to GitHub):
N3W_T1_SOFTWARE_OWNERSHIP_20261010_080909.txt
SHA256=74127af80fec997a51717cf08c72879813e7885b6a9ff99a76c999783121132f
COLLECTED_LOCAL=2026-10-10T08:09:13+08:00

The parent branch commit above predates the status updates and this handoff; next session MUST fresh rebind PR #541 HEAD and main, not reuse the parent as current HEAD.

## 4. Current Live Baseline

Last observed at 08:09+08, not independently refreshed after the report:
- greenhouse-manager: Up 13 hours; Docker host network; full ID/image digest/host paths unknown.
- greenhouse-manager-p4-shadow: Created; full ID/mount unknown.
- n3wfc4-broker-1: Up 3 days; n3wfc4-private and n3wfc4-services networks.
- fc4-homeassistant: Up 3 days; n3wfc4-private; business data ownership unknown.
- homeassistant: Up 3 days; host network; likely separate service but ownership not proven; preserve.
- recipes-broker-1: Exited(0) 13 days ago; preserve.
- TCP 8883, TCP 47112, UDP 47111, TCP 8123 IPv4/IPv6 listening; process and exact container port owner unverified.
- Anonymous Docker volumes listed: 46; volume-to-container mount map unknown.
- n3wfc4-private has Broker + fc4-homeassistant; n3wfc4-services has Broker; host has Manager + homeassistant.
- Related systemd six unit names known, actual FragmentPath unknown.
- No T1 mutation, board access, USB, serial, flash, NVS or RF activity in this conversation.

CURRENT_RUNTIME_REQUIRES_FRESH_READONLY_REBIND=true

## 5. Proven Current Facts

S0_R1_CONTAINER_COUNT=6
S0_R1_INSPECT_SUCCEEDED=0
S0_R1_INSPECT_FAILED=6
S0_R1_DOCKER_VOLUME_NAME_COUNT=46
S0_R1_VOLUME_OWNER_PROVEN=false
S0_R1_HOST_RW_SOURCE_PROVEN=false
S0_R1_NETWORK_MEMBERSHIP=PASS
S0_R1_SYSTEMD_UNIT_NAMES=PASS
S0_R1_LIVE_MUTATION=false
S0_R1_DATA_DELETE=false

Exact systemd names:
- n3w-p4-fresh-manager-deploy.service (static)
- n3w-p4-fresh-manager-r3-deploy.service (static)
- n3wfc4-broker-activation.service (enabled)
- n3wfc4-broker-ingress-guard.service (enabled)
- n3wfc4-broker-certificate-lifecycle.service (static)
- n3wfc4-broker-certificate-lifecycle.timer (enabled)

Classification from real names only, pending exact ID/mount confirmation:
- N3W rebuild candidates: greenhouse-manager, greenhouse-manager-p4-shadow, n3wfc4-broker-1.
- Shared or ambiguous: fc4-homeassistant; do not delete.
- Preserve by default: homeassistant and recipes-broker-1.
- Networks n3wfc4-private and n3wfc4-services are active and must not be deleted during inventory.
- All 46 anonymous Docker volumes: DELETE_NOT_APPROVED.
- Host data directories: DELETE_NOT_APPROVED because exact Source paths have not been observed.
INFERENCE_FC4_HA_EXCLUSIVE_N3W=UNPROVEN
INFERENCE_RECIPES_BROKER_UNRELATED=UNPROVEN

## 6. Current Root Cause / Blockers

Blocker A: all six formatted Docker inspect probes failed, detailed stderr not in captured log. Root cause TBD; classification PHYSICAL_HARNESS KF-101 OPEN. No product, Docker daemon or TLS runtime defect proven. R2 reads raw Docker JSON locally on remote T1, selects only safe metadata fields with installed Python, records exact errors and container name/full-ID mapping.

Blocker B: 46 anonymous volumes, real Manager/Broker/HA bind sources, Compose config_files and working_dir, systemd FragmentPaths and potentially shared HA data remain unknown. No destructive action is allowed until exact ownership and isolation are established.

## 7. Closed / Forbidden Routes

- PR #540 R4/B1I1 rollback engineering = stopped, closed, not merged; never resume in this route.
- Full Armbian OS reinstallation and /dev/mmcblk2 wiping = superseded by user.
- docker system prune, compose down -v, --remove-orphans, remove all anonymous volumes, remove both HA containers by name, remove recipes-broker by name = forbidden.
- Board reset/flash/NVS, Setup Secret import, RF tests = forbidden in S0 R2.

## 8. Authorization Ledger

AUTHORIZATION=S0_R1_READONLY
CLAIMED=false
CONSUMED=false
RESULT=PARTIAL_EVIDENCE_6_INSPECT_FAILURES
REPLAY_PERMITTED=false
SUPERSEDED_BY=S0_R2_JSON_READONLY

AUTHORIZATION=OLD_R4_B1I1_LIVE_MUTATION
CLAIMED=false
CONSUMED=false
RESULT=SUPERSEDED_PR540_CLOSED
REPLAY_PERMITTED=false
SUPERSEDED_BY=PR541_SOFTWARE_CLEAN_DEPLOY

AUTHORIZATION=SOFTWARE_ONLY_ROUTE_DECISION
CLAIMED=false
CONSUMED=false
RESULT=USER_APPROVED_PRESERVE_ARMBIAN
REPLAY_PERMITTED=false
SUPERSEDED_BY=NEXT_EXACT_CLEAN_TARGET_AUTHORIZATION_ONLY_AFTER_PROOF

PROPOSED_AUTHORIZATION=S0_R2_READONLY_JSON_CAPTURE
GRANTED=READONLY_ONLY
PROPOSED_AUTHORIZATION=EXACT_CONTAINER_VOLUME_HOST_PATH_DELETE
GRANTED=false

## 9. Rollback Authority

ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_GATE
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=false
LIVE_RUNTIME_MUTATION=false
ROLLBACK_ENGINEERING=ABANDONED_BY_USER

Future scoped clean install must be separately scoped; do not re-open old Manager rollback engineering.

## 10. Next ONE Gate

NEXT_ONE_GATE=N3W_T1_SOFTWARE_OWNERSHIP_S0_R2_EXACT_CONTAINER_AND_DATA_BINDING_READONLY

Purpose: from current Docker JSON, prove every current full container ID/name/image/project/service/config/workdir, every Mount Type/Source/Destination/RW/Name, current Docker volumes and exact referencing containers, plus known unit FragmentPaths. Use corrected versioned Mac Terminal command. No terminal Docker inspect template.

Frozen inputs: PR #541 latest HEAD, current main, user's preserve-Armbian direction, S0 R1 file hash, exact S0 R2 runbook.

PASS:
S0_R2_RESULT=PASS
CURRENT_CONTAINER_LIST_COMPLETE=true
EACH_CURRENT_INSPECT_AND_ID_NAME=PASS
EACH_MOUNT_SOURCE_DESTINATION_RW=PASS
VOLUME_OWNER_REFERENCE_MAP=PASS
RELATED_SYSTEMD_FRAGMENT_PATH=PASS_OR_EXPLICIT_MISSING
T1_MUTATION=false
READY_FOR_NEXT_S1_CLASSIFICATION=true

FAIL: any Docker JSON inspect failure, ID mismatch, unparseable mount, resource ownership unknown where needed, permission/tool missing, or host drift -> S0_R2_RESULT=FAIL_EVIDENCE_INCOMPLETE, STOP. No destructive cleanup.

## 11. Hard Allowed / Forbidden Scope

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=MAC_LOCAL_N3W_T1_SOFTWARE_OWNERSHIP_R2_LOG_ONLY

Allowed: GitHub readonly rebind, selected Docker JSON metadata via installed Python and Docker, Docker volume owner mapping, exact six systemd units status/FragmentPath, local private Mac report.

Forbidden: Config.Env, private keys, Setup Secret, business DB content; copying raw inspect JSON or real host paths to public GitHub; stopping/removing/restarting anything; updating the OS/Docker/CA/ACL; systemd changes; board activity; merge.

## 12. Codex DSL Execution Contract

ROLE=LOW_ORDER_EXECUTOR
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false

0. PRECLAIM: S0_R2 is read-only; no mutation authorization; fresh rebind GitHub PR541/current main.
1. INPUT: same exact source paths in section 3; real T1 target only, no invented IP or paths.
2. EXECUTION: user runs versioned S0 R2 Mac Terminal SSH command if no direct SSH connector is connected. Parse docker ps exact ID list; docker inspect --type container ID JSON per container. Use remote Python for whitelist metadata only. Capture exact name, full ID, six mounts if present, compose labels, network names. List volumes and inspect each, match Mount.Name to container. Read unit states and FragmentPath; no ExecStart with secrets.
3. VALIDATE: every live inspect succeeds and name/ID binds; do not bind based on list order. Print missing metadata as UNKNOWN. Do not treat unreferenced volume as proven orphan.
4. PRIVATE EVIDENCE: local Mac report only; public GitHub gets sanitized conclusions.
5. HARD STOP: fail immediately after missing/ambiguous required evidence. On PASS only return closure; do not enter S1 automatically.

## 13. Expected Closure

=== N3W_T1_SOFTWARE_OWNERSHIP_S0_R2 CLOSURE ===
EXECUTION_ID=
AUTHORIZATION=READONLY_S0_R2
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
MAIN_SHA=
PR541_HEAD=
T1_LOCAL_OBSERVATION_TIME=
CONTAINER_COUNT=
INSPECT_SUCCESS_COUNT=
INSPECT_FAILED_COUNT=
EXACT_CONTAINER_NAME_FULL_ID=PASS|FAIL
COMPOSE_LABELS=PASS|FAIL
EXACT_MOUNT_SOURCE_RW_BINDING=PASS|FAIL
VOLUME_COUNT=
VOLUME_REFERENCES=PASS|FAIL
HA_DATA_SOURCE_OVERLAP=PROVEN_YES|PROVEN_NO|UNKNOWN
RECIPES_BROKER_OWNERSHIP=PROVEN|UNKNOWN
UNIT_FRAGMENT_PATHS=PASS|FAIL
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
S0_R2_RESULT=PASS|FAIL_EVIDENCE_INCOMPLETE
NEXT_ROUTE=S1_CLEAN_MANIFEST_DESIGN_OR_S0_R2_READONLY_DIAGNOSIS
STOP=true
=== END ===

## 14. After PASS / FAIL

AFTER_PASS_NEXT_STAGE=N3W_T1_SOFTWARE_OWNERSHIP_S1_EXACT_CLEAN_MANIFEST_DESIGN
AUTO_EXECUTE_AFTER_PASS=false
NEW_DESTRUCTIVE_AUTHORIZATION_REQUIRED=true

AFTER_FAIL_NEXT_STAGE=S0_R2_EVIDENCE_DIAGNOSTIC_ONLY
AUTO_REPAIR=false
AUTO_RETRY=false
RETURN_TO_HIGH_LEVEL_MODEL=true

## 15. KNOWN_FAILURES Updates

KNOWN_FAILURES_UPDATE_REQUIRED=true
KF_ID=KF-101
DOMAIN=PHYSICAL_HARNESS
SYMPTOM=S0_R1_ALL_6_DOCKER_INSPECT_FORMATTED_METADATA_FAIL
ROOT_CAUSE=TBD_STDERR_NOT_CAPTURED
FIX_OR_GUARD=JSON_INSPECT_WITH_SAFE_WHITELIST_AND_FULL_ID_MOUNT_SOURCE_BINDING
STATUS=OPEN
PRODUCT_DEFECT_PROVEN=false

Recorded in docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md.

## 16. New Chat Start Prompt

阅读：
docs/development/N3W_T1_SOFTWARE_OWNERSHIP_S0_R1_FAILED_INSPECT_NEW_CHAT_HANDOFF_V1.0_20261010.md

同时阅读 exact handoff process authority 4300890dff0ce63d5a547df21426e287d084d9ee：
- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

fresh rebind：
- repository main
- PR #541
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_T1_SOFTWARE_CLEAN_REDEPLOY_PRESERVE_ARMBIAN_AUTHORITY_20261010.md
- docs/development/N3W_T1_SOFTWARE_OWNERSHIP_S0_R1_EVIDENCE_CLASSIFICATION_AND_CLEAN_MANIFEST_20261010.md
- docs/development/N3W_T1_SOFTWARE_OWNERSHIP_S0_R2_EXACT_DOCKER_JSON_AND_MOUNT_READONLY_RUNBOOK_20261010.md

继续 N3-W 温室环境监测系统项目。
每次回复先写：
主线任务：N3-W 温室环境监测系统产品化与首次配对验收
支线任务：保留 Armbian，温室软件环境全新部署
当前任务：N3W_T1_SOFTWARE_OWNERSHIP_S0_R2_EXACT_CONTAINER_AND_DATA_BINDING_READONLY

本轮执行模型：高阶模型负责产品和 Gate，Codex 低阶执行 exact DSL；PREWRITTEN_EXECUTOR_REQUIRED=false。
S0 R1 实测六个容器及四十六个 Docker 卷，但六次 inspect 全失败，因此完整 ID、宿主 Mount Source、卷归属尚未证明，不能删除。
只执行：
NEXT_ONE_GATE=N3W_T1_SOFTWARE_OWNERSHIP_S0_R2_EXACT_CONTAINER_AND_DATA_BINDING_READONLY
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
OS_REINSTALL=false
DATA_DELETE=false
使用版本化 S0 R2 JSON 只读命令在 Mac Terminal 收集私有报告，得到容器 full-ID、Compose labels、Mount Type/Source/Destination/RW/Name、卷归属和 systemd FragmentPath，并 STOP。不要继续旧 R4/B1I1 回退、整盘擦除或擅自清理任何 HA/Broker/卷。后续清理清单要按私有精确证据制作，只向公共 GitHub 提交脱敏摘要。

## 17. Final Frozen State

CURRENT_STAGE=T1_PRESERVE_ARMBIAN_S0_R1_CLASSIFIED_PARTIAL
CURRENT_STOP_POINT=S0_R1_INSPECT_6_OF_6_FAILED_NO_EXACT_HOST_DATA_PATHS
SOURCE_DEFECT_PROVEN=false
PRODUCT_DEFECT_PROVEN=false
CURRENT_BLOCKER=KF101_OPEN_CONTAINER_METADATA_PROOF_GAP
LIVE_SYSTEM_STATE=LAST_OBSERVED_2026_10_10_0809_NOT_FRESH_AT_NEW_CHAT
NEXT_ONE_GATE=N3W_T1_SOFTWARE_OWNERSHIP_S0_R2_EXACT_CONTAINER_AND_DATA_BINDING_READONLY
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_STANDARD_VERSION=1.0

## 18. Handoff Compliance Audit

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
