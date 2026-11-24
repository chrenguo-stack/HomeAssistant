# N3-W R8V13-07 fresh U5 continuation pending mini handoff

`MINI_HANDOFF_TEMPLATE_VERSION=1.2`

## 1. 当前任务与停点

- 当前任务：`R8V13-07` — 事务 A fresh physical reacceptance，把备用 T1 从 healthy exact HA 2026.10.4 安全准备为 healthy exact HA 2026.10.0。
- 已完成到：KF-152 repaired recovery control plane 已部署；fresh PREPARE reacceptance 已完成 U1→U4；预安装 Manager→Broker→HA active self-test PASS；一次正式 INSTALL intent 已接受并把 fresh transaction 推进到 U5。
- 当前状态：**等待用户执行已归档的 U5 bounded continuation，并在新对话反馈最终输出**。
- 当前停点：fresh install authority 尚未签发。上一次 authority issue 因私有 executor 使用不符合产品正则的 authorization ID 而 fail-closed；没有进入 destructive boundary。

当前 durable transaction：

```text
TRANSACTION_ID_SHA256=afbfeeb85c3ab579b62d86d347f76b7f6ee7f203b068eac028be1d18761950c3
STATUS=ACTIVE
PHASE=U5_INSTALL_REQUESTED_REVALIDATING
RECOVERY_REQUIRED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
AUTHORIZATION_ID_SHA256=null
PREDECESSOR_START_PRESENT=false
PREDECESSOR_RELEASE_OBSERVED=false
TARGET_LOADED_IMAGE_ID=null
TARGET_ACTIVATION=null
TARGET_ACCEPTANCE_PRESENT=false
DESTRUCTIVE_BOUNDARY_CROSSED=false
```

fresh PREPARE / U4 evidence：

```text
FRESH_PREPARE_RESULT=PASS
FRESH_U4_LEDGER=PASS
FRESH_U4_TRANSACTION_SHA256=fa7d9777772d32b95ab761bbfe34e4b1d29a33a384bdc34f16191543bd8530cd

TARGET_IMAGE_REF=local/n3w-homeassistant:2026.10.0-0c73235a
TARGET_ARCHIVE_SHA256=e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663
TARGET_ARCHIVE_SIZE=2448553472

PREDECESSOR_IMAGE_REF=local/n3w-homeassistant:2026.10.4-5881590f
PREDECESSOR_ARCHIVE_SHA256=6502b8cdbf706d746e32311fdaa39ffc5ca703d76f766806bbb21d3c71278d1f
PREDECESSOR_ARCHIVE_SIZE=2447090176

USB_FILESYSTEM_UUID=b72ac2fc-79a0-4fb8-888e-f35b0114f959
ROOT_AVAILABLE_AFTER_PREPARE=4686393344
USB_AVAILABLE_AFTER_PREPARE=13443194880
```

INSTALL 前业务证据：

```text
PREINSTALL_SELF_TEST_VERDICT=PASS
PREINSTALL_SELF_TEST_SHA256=cc2a9e3c867db76cc1630e460eaf036797c0daedb5c4da99460151780fba1c9e
INSTALL_INTENT_EXECUTED=true
INSTALL_REQUEST_BINDING_SHA256=f012b3ed4fe47090e5dc23b23c48b558099ce6247dad716b4d6252ae8ef5cd83
```

上一次 STOP 根因：

```text
FAILED_PRIVATE_EXECUTOR=N3W_T1_R8V13_07_PREINSTALL_AND_FRESH_INSTALL_20261124_02.sh
INVALID_AUTHORIZATION_ID=N3W_T1_R8V13_07_INSTALL_CUTOVER_20261124_02
PRODUCT_REQUIRED_REGEX=^N3W_T1_CORE_UPDATER_[A-Za-z0-9_-]{1,160}$
ROOT_CAUSE=PRIVATE_EXECUTOR_AUTHORIZATION_ID_MISSING_CORE_UPDATER_PREFIX
PRODUCT_FAILURE=false
BINDING_DRIFT=false
AUTHORITY_PUBLICATION_OCCURRED=false
INSTALL_INTENT_REPLAY_ALLOWED=false
```

## 2. GitHub 续接入口

- 仓库：`chrenguo-stack/HomeAssistant`
- PR：`#824` — OPEN / DRAFT / mergeable at handoff preparation
- 分支：`review/t1-ota-r8-existing-tx-predecessor-prep-20261123`
- PR head at handoff preparation：`f50e48f91857bf5262e959d948928593ac5925c0`
- Master Task Document：`docs/development/templates/STAGE_EXECUTION_PLAN_TEMPLATE.md`
- Master Task Document SHA：`b6bf93b3fbc7fba770ae4cac2c60ef9d79eeb105`
- Current Stage / Task：`N3W_T1_CORE_STACK_OTA_V1_3_R8_PHYSICAL_ACCEPTANCE / R8V13-07`
- Next Task Chain：`R8V13-07 → R8V13-08 → R8V13-09 → R8V13-10 → R8V13-11 → R8V13-12 → R8V13-13 → R8V13-14`
- Current State：`docs/development/N3W_CURRENT_STATE.md`
- State Index：`docs/development/N3W_CURRENT_STATE_INDEX.md`
- KF closure：`docs/development/N3W_T1_OTA_V1_3_KF152_SOURCE_CI_DOCKER_PACKAGE_CLOSURE_20261124.md`
- Architecture：`docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md`
- Regression authority：`docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`

Exact source / package authority：

```text
EXACT_SOURCE_HEAD=9339ab22fc29ddd14d2e147d13e616ccebed945b
RECOVERY_ARTIFACT_RUN=45317562079
RECOVERY_ARTIFACT_ID=14885876408
RECOVERY_ARTIFACT_DIGEST_SHA256=23289a67fd60051ac60d4392f690917134c3076d3d8aeb9226eae9a37d52407c
RECOVERY_INSTALL_MANIFEST_SHA256=6792c681b61404d7a6a31e1bd78f25e6332d89a147d2639f2c4b6a1b705bdd89
RECOVERY_PYZ_SHA256=d3e844a05571e94ef384aa62fd4763f2d53c253f281cb94f30dd37ca19743b30
ACTIVE_COMPOSE_SHA256=6cd522b55136beceb8661820896351238d2218c23c3b3e71e98a7521ac67f0f4
APPROVED_MANIFEST_SHA256=5fbae3dedc6af008fec90efc24e75349ce82fc3a538e935806bef6ab3cbc4a36
```

Exact continuation executor：

```text
PATH=tools/execution_packages/n3w/t1_ota_r8v13_07/N3W_T1_R8V13_07_U5_AUTHORITY_CONTINUE_AND_INSTALL_20261124_03.sh
SHA256=8a026b108954c524964a0373c516f3904c08d42424fd497605f27caa60ada9b3
GIT_BLOB_SHA=bfe577199eaf362d5558f4098f39859effd9f7b6
AUTHORIZATION_ID=N3W_T1_CORE_UPDATER_R8V13_07_INSTALL_CUTOVER_20261124_03
```

关键 PR evidence comments：

```text
7124599609 = fresh PREPARE V03 physical PASS / fresh U4 durable
7125179778 = invalid authorization-ID STOP root cause
7125215220 = bounded U5 continuation executor prepared
```

新会话不得仅凭本 handoff 假定 GitHub head 或 live state 未变化；执行后结果以用户反馈的完整输出和 fresh rebind 为准。

## 3. 下一步

- 下一动作：用户在本对话结束后执行已提供的 continuation script；新对话首先接收用户贴回的**完整最终输出**，据此分类 `U13A_COMMITTED`、`U13B_ROLLED_BACK` 或 nonterminal STOP，再做必要的 fresh rebind。
- 允许范围：沿既有 R8V13-07 授权，只从 durable U5 签发新的合法 install authority，启动 exact product worker，允许状态机完成 U5→U13A 或失败自动恢复；如脚本检测到已经承担恢复责任，仅允许一次产品 `--resume-pending` continuation。
- 暂停边界：不得重放 PREPARE；不得重放 INSTALL intent；不得手工释放/加载镜像；不得跨入 R8V13-08；不得 Broker OTA、host reboot、USB format/history delete、merge、release、production publish。
- 需要用户操作：执行已经下载的 `N3W_T1_R8V13_07_U5_AUTHORITY_CONTINUE_AND_INSTALL_20261124_03.sh`，并在新对话粘贴完整输出。执行期间不得拔 U 盘。

成功/失败分支：

```text
SUCCESS:
STATUS=COMMITTED
PHASE=U13A_COMMITTED
POST_COMMIT_RUNTIME=PASS
R8V13_07_RESULT=PASS
=> STOP before R8V13-08; first archive/rebind result

ROLLBACK:
STATUS=ROLLED_BACK
PHASE=U13B_ROLLED_BACK
ROLLBACK_RUNTIME_HEALTH=PASS
R8V13_07_RESULT=NOT_PASS
=> R8V13-08 remains blocked; do not rerun

NONTERMINAL:
FRESH_INSTALL_CONTINUATION_RESULT=STOPPED_NONTERMINAL or STOP
=> do not rerun; preserve durable phase and diagnose from exact state
```

## 3A. 条件补充信息

```text
TARGET=local/n3w-homeassistant:2026.10.0-0c73235a
MUTATION_OR_RECOVERY_ACTION=from existing U5 issue fresh valid install authority, run exact product U5-to-terminal worker, and only if recovery responsibility exists allow one product resume-pending continuation
PRE_ACTION_BASELINE=ACTIVE/U5_INSTALL_REQUESTED_REVALIDATING; exact HA 10.4 + Manager fresh-1cae18039eee + Broker 2.1.2-3184566d healthy before failed authority issue; no authority claim/consume; no predecessor_start/release; target absent

AUTHORIZATION_SOURCE=user-approved execution contract N3W_T1_R8V13_07_FRESH_PHYSICAL_REACCEPTANCE_20261124_01
AUTHORIZATION_SCOPE=R8V13-07 only: corrected install-authority issuance + product U5-U13 + automatic safe recovery; excludes R8V13-08 auto advance, Broker OTA, reboot, USB format/history deletion, merge/release/publish
AUTHORIZATION_STATE=UNCLAIMED
AUTHORIZATION_REPLAY_ALLOWED=false

EXACT_SOURCE_HEAD=9339ab22fc29ddd14d2e147d13e616ccebed945b
EXACT_ARTIFACT=run 45317562079 / artifact 14885876408 / digest 23289a67fd60051ac60d4392f690917134c3076d3d8aeb9226eae9a37d52407c / pyz d3e844a05571e94ef384aa62fd4763f2d53c253f281cb94f30dd37ca19743b30
EXACT_TRANSACTION=afbfeeb85c3ab579b62d86d347f76b7f6ee7f203b068eac028be1d18761950c3 / ACTIVE / U5_INSTALL_REQUESTED_REVALIDATING
EXACT_RUNTIME_AUTHORITY=compose 6cd522b55136beceb8661820896351238d2218c23c3b3e71e98a7521ac67f0f4; HA 10.4 image ID sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365; Manager image ID sha256:c4bcb441de0554ebb20e3feb2b98a65cc435750539a2c951eb7be710ff191221; Broker image ID sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563

LAST_SUCCESSFUL_STEP=preinstall active business self-test PASS, then formal INSTALL intent accepted and durable transaction advanced to U5
ACTUAL_CHANGES_ALREADY_MADE=KF-152 pyz deployed; fresh candidate materialized; fresh transaction created; fresh PREPARE U1-U4 completed with new USB target/predecessor archives; INSTALL intent submitted once; no fresh install authority published; no service stop/image release/target load

ROLLBACK_OR_RECOVERY_ENTRY=product state machine recovery only; continuation script invokes --resume-pending once only when durable state proves recovery responsibility/predecessor_start/U9-U12
FRESH_REBIND_REQUIRED=true
STOP_CONDITION=after user result: stop on U13A before R8V13-08; stop on U13B/nonterminal and do not rerun; any source/runtime/authorization/evidence drift stops affected operation
```

## 4. 新会话启动语

```text
继续 N3-W 当前任务。

用户会先贴回 R8V13-07 U5 bounded continuation 的最终执行输出。先完整读取该输出，不要要求用户重复运行。

先读取：
- docs/development/templates/STAGE_EXECUTION_PLAN_TEMPLATE.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/N3W_T1_OTA_V1_3_R8V13_07_U5_CONTINUATION_PENDING_MINI_HANDOFF_20261124.md
- docs/development/N3W_T1_OTA_V1_3_KF152_SOURCE_CI_DOCKER_PACKAGE_CLOSURE_20261124.md
- docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

fresh rebind：
- repository main
- PR #824 / branch review/t1-ota-r8-existing-tx-predecessor-prep-20261123 / current head
- master task R8V13-07 -> R8V13-08
- exact continuation executor path + SHA256 8a026b108954c524964a0373c516f3904c08d42424fd497605f27caa60ada9b3
- if output is nonterminal or rollback, fresh-read transaction/runtime/authority before any further mutation

当前停点：
fresh transaction afbfeeb85c3ab579b62d86d347f76b7f6ee7f203b068eac028be1d18761950c3 is ACTIVE / U5_INSTALL_REQUESTED_REVALIDATING before continuation execution. PREPARE and INSTALL intent must not be replayed. The previous authority issue failed only because a private executor authorization ID missed the required N3W_T1_CORE_UPDATER_ prefix; no destructive boundary was crossed.

当前任务：
R8V13-07

下一任务链：
R8V13-07 -> R8V13-08 -> R8V13-09 -> R8V13-10 -> R8V13-11 -> R8V13-12 -> R8V13-13 -> R8V13-14

按用户反馈结果分类：
- U13A + healthy exact 10.0 => archive R8V13-07 PASS, then stop before R8V13-08
- U13B => archive failure/rollback evidence, R8V13-08 blocked
- nonterminal STOP => do not rerun; diagnose durable phase and fulfill any existing recovery responsibility first

按现有授权边界继续；如发现 source、runtime、authorization 或 evidence drift，停止受影响操作并重新判定。
```

## 5. mini handoff 完整性检查

```text
MINI_HANDOFF_TEMPLATE_VERSION=1.2
MINI_HANDOFF_COMPLETE=PASS

TEAM_SHARED_WORKSPACE=GITHUB
GITHUB_STATE_ALIGNED=true
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
UNARCHIVED_CRITICAL_RESULT_COUNT=0

LIVE_OR_PHYSICAL_MUTATION_PENDING=true
PRODUCTION_RECOVERY_IN_PROGRESS=false
UNCONSUMED_ONE_SHOT_AUTHORIZATION=true
ROLLBACK_STATE_AMBIGUOUS=false
CURRENT_STATE_AMBIGUOUS=false

SUPPLEMENT_REQUIRED=true
SUPPLEMENT_COMPLETE=true
FORMAL_HANDOFF_RECOMMENDED=false

FRESH_REBIND_REQUIRED=true
MASTER_TASK_DOCUMENT_BOUND=true
TASK_ALIGNMENT=PASS
NEXT_ACTION_EXPLICIT=true
NEXT_TASK_CHAIN_EXPLICIT=true
STOP_BOUNDARY_EXPLICIT=true
```

本 handoff 不新增权限；它只记录已经存在的 R8V13-07 execution contract、当前 durable U5 状态和 exact continuation entry。
