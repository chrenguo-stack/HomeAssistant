# N3-W T1 逐台 fresh Armbian 自动产品部署 F1B focused closure review 修补进度
# 2026-10-14

## 0. 当前结论

TASK=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F1B_FOCUSED_CLOSURE_REVIEW_20261014_01
REVIEW_BASE=fb2a0d0ef55980c83919b608633b060f656e8dcc
ORIGINAL_F1B_HEAD=f011bf389a0909383b9e485d089b89f9120e9173
REPAIRED_SOURCE_HEAD=f1306067667c1a58b172b543c452c1a388ec119e
PR=541
PR_STATE=OPEN_DRAFT_UNMERGED
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
F1B_FOCUSED_CLOSURE=OPEN_PENDING_EXACT_HEAD_CI_AND_ARTIFACT
AUTO_ENTER_F2=false

本轮按 handoff 要求独立复核 A1-A10。原 exact F1B head 的 27/27 CI 与 artifact binding 已重新核实，
但 focused review 没有直接沿用“CI 绿=源码闭环”的结论。

## 1. Fresh rebind

MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR_HEAD_BEFORE_REVIEW=5eb049ff8f1fe45f8af1a41a94d08627950c42a7
ORIGINAL_F1B_SOURCE_HEAD=f011bf389a0909383b9e485d089b89f9120e9173
DOCS_ONLY_ADVANCE_FROM_F011_TO_5EB=PASS

原 F1B source authority 的 27 个 workflow 均 SUCCESS。deployable artifact 重新绑定：
ORIGINAL_ARTIFACT_RUN=38523814780
ORIGINAL_ARTIFACT_ID=11875663387
ORIGINAL_ARTIFACT_DIGEST=sha256:ed43762adfa6f9a0e034d6974dc79b87a7a7bb357f60659413d5b368ca8f250f

## 2. A1-A10 独立复核

A1=CLOSED_SOURCE
- transport schema /2；
- runtime payload 不内嵌三个 image tar；
- T1 按 image_requested 每次只接收一个 tar；
- remote staged image count max=1。

A2=CLOSED_SOURCE
- capacity schema /1；
- 5 GiB reserve 保持；
- 每镜像 required free 由 tar size + loaded size + 5 GiB 组成；
- Docker 尚未安装时，root free capacity admission 发生在 authorization claim 之前。

A3 原始实现发现 focused blocker：
A3_ORIGINAL=BLOCKED
ROOT_CAUSE=REMOTE_CLAIM_MAY_ALREADY_BE_DURABLE_WHILE_SSH_RESULT_OR_CLAIM_EVENT_IS_LOST
OLD_FALSE_REPORT_PATH=STOP_PRECLAIM+authorization_consumed=false
FAILURE_CLASS=KF-108_RECURRENCE

修补后：
- durable authorization record present -> STOP_PARTIAL、consumed、no-replay；
- durable record absent -> STOP_PRECLAIM、unconsumed；
- record state unknown -> STOP_UNKNOWN、consumed、no-replay。
A3_REPAIR=CLOSED_SOURCE_PENDING_CI

A4=CLOSED_SOURCE
顺序保持 remote SHA verify -> docker load -> runtime binding -> tar delete -> postload free-space recheck。
runtime binding 继续使用 arm64/linux、RootFS fingerprint 和 config-contract fingerprint。

A5=CLOSED_SOURCE
Golden Master、Seal、clone helper 不进入 active per-device fresh runtime payload/call path；
sealed-image/clone-readback 不再是 per-device fresh provisioning 前置条件。

A6=CLOSED_SOURCE
真实安装命令为 n3w-t1-provision，surface 为 status/start/resume-if-needed/verify；
start 必须显式确认 START DEVICE PROVISIONING: YES。

A7=CLOSED_SOURCE
UNPROVISIONED=NOOP
INITIALIZING=RESUME_EXISTING
DEVICE_READY=VERIFY_ONLY
AUTO_START_NEW_PROVISIONING_ON_BOOT=false

A8=CLOSED_SOURCE
F3 只提交 public runtime，instance material 仍 absent；
F3 只 enable guard + provision-resume；
F4 activation/services/certificate timer 在 F3 明确不得 enabled/start。

A9=CLOSED_SOURCE
repository-owned fresh host baseline 只处理 Ubuntu/Armbian 上 Docker Engine + Compose；
不执行 product compose up，不启动 Broker/Manager/Home Assistant。

A10 focused review 发现另一个 host-wrapper cleanup 缺口：
A10_ORIGINAL=PARTIAL
ROOT_CAUSE=HOST_SIDE_IMAGE_TRANSFER_OR_EVENT_ERROR_COULD_ESCAPE_WITH_REMOTE_SSH_APPLY_PROCESS_NOT_EXPLICITLY_REAPED

修补增加 bounded remote apply process cleanup：
- host event/transfer 异常先 terminate；
- bounded wait；
- 不收敛则 kill + bounded wait；
- fresh installer 既有 transaction-owned product cleanup、consumed/no-replay 与 stopped postcheck 保持不变。
A10_REPAIR=CLOSED_SOURCE_PENDING_CI

## 3. Same-gate source/test 修补

SOURCE_COMMITS:
1c65e3c934dc497b30bed81cda88be5546c61716
3bc6b8cb42b04f3e4d6c817afd916788bd12cd20
c71aa255a975eed04bbd3675e5466190440163f1
aee10ac9949db7c9cfffbbed61178295d93aca00
f1306067667c1a58b172b543c452c1a388ec119e

FILES_CHANGED_FROM_HANDOFF_DOCS_HEAD:
- tools/n3w_t1_fresh_product_staging_host.py
- tests/tools/test_n3w_t1_fresh_product_staging_host.py

新增 regression 覆盖：
- claim error + durable record present；
- claim error + durable record absent；
- claim error + durable record state unknown；
- host-side remote apply process terminate/wait；
- terminate 不收敛时 kill/wait。

## 4. CI checkpoint

REPAIRED_SOURCE_HEAD=f1306067667c1a58b172b543c452c1a388ec119e
EXACT_HEAD_CI=RUNNING
POLL_COUNT=2
CI_FAILURE_COUNT=0_AT_CHECKPOINT
DEPLOYABLE_ARTIFACT=WAIT_EXACT_HEAD_RUN

原 f011 artifact 不再作为 repaired source closure artifact。只有 f130 exact-head CI 与新 deployable artifact
完成后，才允许写 F1B CLOSED_SOURCE。

## 5. Stop boundary

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
F2_ENTERED=false

NEXT_ACTION=WAIT_EXACT_REPAIRED_HEAD_CI_WITHIN_3_POLL_LIMIT_THEN_FINISH_F1B_CLOSURE_OR_STOP_WITH_LINKS

本文件是 same-gate progress，不构成 F2 授权，也不构成 F1B 最终 closure。
