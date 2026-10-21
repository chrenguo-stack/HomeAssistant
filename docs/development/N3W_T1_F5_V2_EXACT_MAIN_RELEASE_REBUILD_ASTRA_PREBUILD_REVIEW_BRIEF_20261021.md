# N3-W T1 F5 V2 exact-main release rebuild — Astra prebuild independent review brief（2026-10-21）

## 1. Review mission

请在任何新的 production-authoritative artifact 构建之前，对当前 N3-W T1 F5 V2 exact-main release rebuild 链做一次独立、完整、只读复核。

本轮最核心的问题不是“现有 CI 是否绿”，而是：

> 当前 exact main 是否已经具备足够严密的 source / workflow / artifact provenance、内容完整性和 fail-closed 边界，可以安全地开始 F3 + F4/reboot artifact 重建，并继续进入 release-inputs 与 final production release 构建？

请不要默认接受现有设计，也不要因为 PR #628 已合并就默认认为 release 构建链一定正确。必须直接检查当前源码、workflow、builder、测试和历史 authority。

本轮只读：

~~~text
TASK=N3W_T1_F5_V2_EXACT_MAIN_RELEASE_REBUILD_ASTRA_PREBUILD_REVIEW_20261021_01

READ_ONLY_REVIEW=true
REPOSITORY_MUTATION=false
WORKFLOW_DISPATCH=false
GITHUB_ARTIFACT_PRODUCTION=false

T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
REAL_T1_PRODUCTION_AUTHORIZATION=false
~~~

本轮禁止：
- 启动 F3/F4/release-inputs/final-release workflow；
- 修改 repository；
- 访问 T1；
- 运行 production executor；
- 创建、接受或写入 STARTED/ACCEPTED marker；
- 合并任何 PR；
- 重开无关旧问题。

## 2. Exact authority — 必须先 fresh rebind

Repository：

~~~text
REPOSITORY=chrenguo-stack/HomeAssistant
~~~

当前 exact-main：

~~~text
REVIEW_MAIN=e9ca449bc95b45235b7f95ca5478b5a7102daeb7
REVIEW_MAIN_TREE=b25ce47f2dd20e569eb7b674317991a11ee1c4e0
REVIEW_BRANCH=main
~~~

首先 fresh rebind：
1. repository current main；
2. main tree；
3. PR #628 / #629 / #630；
4. current state / current state index；
5. exact workflow/source files。

如果 main 已不等于 `e9ca449b...`，立即停止并报告：

~~~text
MAIN_DRIFT=true
RESULT=BLOCK
REASON=EXACT_MAIN_AUTHORITY_DRIFT
~~~

不要在漂移后的 main 上继续使用本 brief 中的旧 SHA 结论。

## 3. Merge / review chain that must be preserved

### PR #628 — real T1 executor + non-disruptive acceptance + evidence classification

~~~text
PR628_HEAD=291ab6b27f50457314472049768663bc7e744e79
PR628_MERGE_COMMIT=3252a204f1cb6ecd09818bca9bd50d1a6ced586c
PR628_PREMERGE_CI=17/17_PASS
PR628_SOURCE_BLOCKER=CLOSED
~~~

PR #628 introduced / repaired:
- concrete real-T1 production executor；
- exact-release F3 local materialization；
- F4/reboot internal authorization boundaries；
- post-reboot target-local runtime auth evidence；
- external negative MQTT auth probe；
- 90-second non-disruptive observation；
- sticky mid-window failure semantics；
- evidence-insufficient vs explicit product-failure classification；
- release-input packaging of the production executor.

### PR #629 — PR628 post-merge alignment

~~~text
PR629_HEAD=bbcae9ce0431807b54c05158cf7d44b3d3bef72b
PR629_MERGE_COMMIT=90775b804807b4ff69ca7cea71a220a2e3a5a416
PR629_PREMERGE_CI=11/11_PASS
PR629_SCOPE=DOCS_ONLY
~~~

### PR #630 — exact-main release rebuild preparation

~~~text
PR630_HEAD=95d209d2a692ce76d1761d98741e3530f1baab88
PR630_MERGE_COMMIT=e9ca449bc95b45235b7f95ca5478b5a7102daeb7
PR630_PREMERGE_CI=11/11_PASS
PR630_SCOPE=DOCS_ONLY
~~~

Fresh compare 已知应满足：

~~~text
291ab6b27f50457314472049768663bc7e744e79
  -> e9ca449bc95b45235b7f95ca5478b5a7102daeb7

AHEAD_BY=9
BEHIND_BY=0

EXPECTED_CONTENT_DELTA_AFTER_PR628=
docs/development/N3W_CURRENT_STATE.md
docs/development/N3W_CURRENT_STATE_INDEX.md
docs/development/N3W_T1_F5_V2_PR628_POSTMERGE_STATE_ALIGNMENT_20261021.md
docs/development/N3W_T1_F5_V2_EXACT_MAIN_RELEASE_REBUILD_PREPARATION_20261021.md
~~~

Astra 必须独立确认：
- PR #629/#630 之后没有 product source / workflow / test drift；
- 当前 production code/workflow 内容仍然是已复核的 PR #628 内容；
- docs-only merge 不被误当作旧 release 可以继续复用的理由。

## 4. Current build state

当前尚未启动新的 exact-main artifact chain。

已知 current-main Actions：

~~~text
EXACT_MAIN=e9ca449bc95b45235b7f95ca5478b5a7102daeb7
F3_EXACT_MAIN_WORKFLOW_RUN=NONE
F4_EXACT_MAIN_WORKFLOW_RUN=NONE
RELEASE_INPUTS_EXACT_MAIN_WORKFLOW_RUN=NONE
FINAL_RELEASE_EXACT_MAIN_WORKFLOW_RUN=NONE
~~~

当前 main merge push 仅因 path filter 触发 Public repository safety CI；这不等价于 F3/F4 production artifact 已生成。

旧 artifact / 旧 release：
- 可以作为历史证据；
- 不能作为当前 exact-main 的 production authority；
- 不能与新 main 的 artifacts 混用。

## 5. Required primary files

Astra 必须直接读取并复核以下 workflow：

~~~text
.github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml
.github/workflows/n3w-t1-f4-exact-control-package.yml
.github/workflows/n3w-t1-f5-v2-release-inputs-ci.yml
.github/workflows/n3w-t1-f5-v2-exact-production-release-ci.yml
.github/workflows/n3w-t1-f5-v2-source-ci.yml
~~~

核心 builder / contract：

~~~text
tools/n3w_t1_f5_v2_release_inputs_builder.py
tools/n3w_t1_f5_v2_release_builder.py
tools/n3w_t1_production_v2_contract.py
~~~

F3 / F4 / executor / acceptance：

~~~text
tools/n3w_t1_fresh_product_bootstrap.py
tools/n3w_t1_fresh_product_staging_host.py
tools/n3w_t1_fresh_host_baseline.py
tools/n3w_t1_device_provisioning_host.py

tools/n3w_t1_f4_activation_host.py
tools/n3w_t1_f4_certificate_runtime_guard.py
tools/n3w_t1_f4_reboot_authority.py
tools/n3w_t1_f4_reboot_verify.py

tools/n3w_t1_production_v2.py
tools/n3w_t1_production_v2_executor.py
tools/n3w_t1_post_reboot_acceptance.py
tools/n3w_t1_production_marker.py
tools/n3w_t1_fresh_armbian_qualification.py
tools/n3w_t1_ssh_transport.py
~~~

关键 tests：

~~~text
tests/tools/test_n3w_t1_f5_v2_release_inputs_builder.py
tests/tools/test_n3w_t1_f5_v2_release_builder.py
tests/tools/test_n3w_t1_production_v2.py
tests/tools/test_n3w_t1_production_v2_contract.py
tests/tools/test_n3w_t1_production_v2_executor.py
tests/tools/test_n3w_t1_post_reboot_acceptance.py
tests/tools/test_n3w_t1_f4_reboot_verify.py
tests/tools/test_n3w_t1_fresh_product_staging_host.py
tests/tools/test_n3w_t1_mqtt_nondisruptive_integration.py
~~~

## 6. Required project authority documents

请至少读取：

~~~text
docs/development/N3W_CURRENT_STATE.md
docs/development/N3W_CURRENT_STATE_INDEX.md
docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

docs/development/N3W_T1_F5_V2_PR628_POSTMERGE_STATE_ALIGNMENT_20261021.md
docs/development/N3W_T1_F5_V2_EXACT_MAIN_RELEASE_REBUILD_PREPARATION_20261021.md

docs/development/N3W_T1_F5_V2_REAL_T1_PRODUCTION_EXECUTOR_SOURCE_REPAIR_20261020.md
docs/development/N3W_T1_F5_V2_NONDISRUPTIVE_POST_REBOOT_ACCEPTANCE_SOURCE_REPAIR_20261020.md
docs/development/N3W_T1_F5_V2_EXACT_RELEASE_INPUTS_PRODUCER_SOURCE_REPAIR_20261020.md

docs/development/N3W_T1_F5_PRODUCTION_PROCESS_V2_SIMPLIFIED_ARCHITECTURE_CONTRACT_20261019.md
docs/development/N3W_T1_F5_PRODUCTION_PROCESS_V2_SOURCE_DESIGN_20261019.md
docs/development/N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R3_POST_REBOOT_ACCEPTANCE_AND_RELEASE_INTEGRATION_CLOSURE_20261020.md
~~~

历史文档中的旧 SHA / old PASS 只能按其历史语境解释，不得覆盖 current exact-main。

## 7. Frozen intended rebuild chain

当前设计的唯一 rebuild chain：

~~~text
A. exact-main F3 deployable payload
B. exact-main F4 control + reboot-control
   A / B may run in parallel

C. exact-main V2 release inputs
   requires successful exact A + B run IDs

D. exact-main V2 production release
   requires successful exact C run + exact artifact name

E. local exact-release validation

F. Standard Fresh Armbian read-only qualification

G. separate real-T1 production authorization decision
~~~

本次 Astra review 只决定能否进入 A/B。

不得直接进入 G。

## 8. Expected artifacts

For exact main `e9ca449b...`：

### F3

~~~text
n3w-t1-fresh-bootstrap-deployable-e9ca449bc95b45235b7f95ca5478b5a7102daeb7
~~~

Expected exact outer file set：

~~~text
runtime-payload.tar.gz
runtime-payload.sha256
payload-manifest.sha256
capacity-contract.json
capacity-contract.sha256
homeassistant-arm64.tar
greenhouse-manager-arm64.tar
broker-arm64.tar
executor.sha256
host-wrapper.py
host-wrapper.sha256
host-baseline.py
host-baseline.sha256
~~~

### F4 / reboot

~~~text
n3w-t1-f4-control-package-e9ca449bc95b45235b7f95ca5478b5a7102daeb7

n3w-t1-f4-reboot-successor-control-e9ca449bc95b45235b7f95ca5478b5a7102daeb7
~~~

### Release inputs

~~~text
n3w-t1-f5-v2-release-inputs-e9ca449bc95b45235b7f95ca5478b5a7102daeb7
~~~

Required logical artifact classes：

~~~text
f3_payload
f3_image
f4_control
reboot_control
v2_mac_tools
transport_contract
~~~

### Final production release

~~~text
n3w-t1-f5-v2-exact-production-release-e9ca449bc95b45235b7f95ca5478b5a7102daeb7
~~~

Outer files：

~~~text
n3w-t1-f5-v2-release.tar.gz
n3w-t1-f5-v2-release.tar.gz.sha256
~~~

## 9. A1 — exact-main source authority and post-PR628 drift

Independently verify:

1. current main and tree equal the brief authority；
2. PR #628 merged source is actually reachable from current main；
3. PR #629/#630 only changed docs；
4. no source/workflow/test changed after the reviewed PR #628 head；
5. exact-main production authority should be current merged main, not PR628 head or an older release SHA；
6. docs-only advancement does not allow reuse of an old release whose `source_head` differs.

Required classification：

~~~text
A1=PASS | BLOCK
~~~

Any unexpected non-doc delta is a BLOCK until understood.

## 10. A2 — F3 exact-main producer

Review:

~~~text
.github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml
~~~

Verify at minimum:

- manual dispatch can target `main`；
- `SOURCE_HEAD` resolves to the dispatched exact-main SHA；
- checkout is exact；
- current ARM64 Manager image is built from that source；
- HA / Broker inputs are digest-qualified and their expected image/config identity is checked；
- F3 output carries exact `source_head`；
- outer file set is exact and no extra files can enter；
- runtime payload, capacity contract, image tars, host wrapper/baseline and executor sidecars are reverified after upload；
- no secret values are packaged；
- no production service is started；
- no board/T1 access occurs；
- image transport/capacity metadata is internally bound；
- stale historical authorization labels embedded in build metadata, if any, cannot grant real production authority.

Pay special attention to whether a workflow_dispatch occurring around a moving `main` can produce an artifact whose name/source metadata does not match the checkout actually built.

Required classification：

~~~text
A2=PASS | BLOCK
~~~

## 11. A3 — F4 + reboot-control producer

Review:

~~~text
.github/workflows/n3w-t1-f4-exact-control-package.yml
tools/n3w_t1_f4_package_builder.py
tools/n3w_t1_f4_reboot_successor_package_builder.py
~~~

Verify:

- both jobs bind the same exact `SOURCE_HEAD`；
- both checkout the requested exact source；
- F4 and reboot manifests/reports bind exact source；
- output sets are exact；
- package-building itself performs no live mutation；
- reboot package build does not reboot；
- no secret or target-specific runtime identity is embedded；
- the two required artifacts from one F4 run are sufficient and unambiguous for downstream C；
- downstream does not accidentally accept F4 from one source and reboot-control from another.

Required classification：

~~~text
A3=PASS | BLOCK
~~~

## 12. A4 — release-input producer provenance closure

Review:

~~~text
.github/workflows/n3w-t1-f5-v2-release-inputs-ci.yml
tools/n3w_t1_f5_v2_release_inputs_builder.py
~~~

Verify that C cannot consume a wrong/stale/mixed upstream combination.

Specifically review:

- checkout `ref: main` plus `GITHUB_SHA` / `origin/main` equality；
- F3/F4 workflow path checks；
- `head_sha == GITHUB_SHA`；
- `head_branch == main`；
- completed/success requirement；
- accepted event set；
- exact artifact-name construction；
- unexpired + exactly-one artifact requirement；
- same F4 run required for F4 + reboot-control；
- exact outer file-set checks after download；
- source-head checks inside payload/report/manifest；
- source-tree binding；
- builder `--production-authority`；
- post-upload re-download verification；
- six-artifact logical set exactness；
- no path traversal/symlink bypass；
- no accidental acceptance of same-name artifacts from another run.

Also inspect race behavior:
if `main` advances after dispatch but before checkout/fetch, does the workflow fail closed rather than silently bind mixed state?

Required classification：

~~~text
A4=PASS | BLOCK
~~~

## 13. A5 — final exact production release provenance closure

Review:

~~~text
.github/workflows/n3w-t1-f5-v2-exact-production-release-ci.yml
tools/n3w_t1_f5_v2_release_builder.py
~~~

Verify:

- final workflow can consume only the dedicated release-input producer；
- exact `inputs_run_id` + exact artifact name are both required；
- input run is current-main, completed/success, workflow_dispatch；
- artifact exists exactly once and is unexpired；
- current checkout is exact merged main；
- `--production-authority` requires `origin/main == source_head`；
- release-input source head/tree must equal final build source head/tree；
- release contains exact required artifact set；
- every artifact size + SHA is bound；
- extra artifacts are rejected；
- path escape / symlink input cannot bypass；
- final release manifest/release ID is deterministic from exact material；
- final tar sidecar correctly binds the tar generated for upload.

Important independent question:

> The final-release workflow verifies the release before upload but does not perform the same explicit post-upload re-download verification that release-inputs does. Is the separate mandatory local exact-release validation gate sufficient to close this transport boundary, or is a source/workflow repair required before build?

Do not assume either answer.

Required classification：

~~~text
A5=PASS | BLOCK
~~~

If PASS depends on E (local validation), say so explicitly.

## 14. A6 — v2_mac_tools completeness and runtime dependency closure

This is a critical review item.

Current `MAC_TOOL_FILES` must include the actual repaired production execution stack, including at least:

~~~text
tools/n3w_t1_device_provisioning_host.py
tools/n3w_t1_f4_activation_host.py
tools/n3w_t1_f4_certificate_runtime_guard.py
tools/n3w_t1_f4_reboot_authority.py
tools/n3w_t1_f4_reboot_verify.py
tools/n3w_t1_failure_forensics.py
tools/n3w_t1_fresh_armbian_qualification.py
tools/n3w_t1_fresh_host_baseline.py
tools/n3w_t1_fresh_product_bootstrap.py
tools/n3w_t1_fresh_product_staging_host.py
tools/n3w_t1_post_reboot_acceptance.py
tools/n3w_t1_production_marker.py
tools/n3w_t1_production_v2.py
tools/n3w_t1_production_v2_contract.py
tools/n3w_t1_production_v2_executor.py
tools/n3w_t1_f5_v2_release_builder.py
tools/n3w_t1_ssh_transport.py
~~~

Independently inspect imports/runtime calls and answer:

1. are all Python/runtime files needed by the concrete Mac production executor included；
2. are any imports accidentally satisfied only by the repository checkout, making the release non-self-contained；
3. is the PR #628 evidence-classification code actually packaged；
4. are exact bytes/size/SHA recorded so an older executor cannot be substituted；
5. are there files included that silently introduce a second authority path；
6. does release-local F3 reconstruct the exact expected outer set without depending on historical Actions metadata.

Required classification：

~~~text
A6=PASS | BLOCK
~~~

This item must not be answered only from the file list; trace actual imports/calls.

## 15. A7 — release contract / integrity / fail-closed behavior

Review:

~~~text
tools/n3w_t1_production_v2_contract.py
tools/n3w_t1_f5_v2_release_inputs_builder.py
tools/n3w_t1_f5_v2_release_builder.py
~~~

Verify:

- `REQUIRED_RELEASE_ARTIFACTS` is complete and exact for the intended V2 route；
- release schema rejects missing/extra unsafe structure as intended；
- source_head and source_tree use exact SHA formats；
- release ID/hash covers all material necessary to establish authority；
- artifacts are regular files, not symlinks；
- path traversal / absolute path / parent escape are rejected；
- F3 image and transport contracts bind exact sizes/SHA；
- F4/reboot reports + manifest source binding are both checked；
- secret boundary remains false；
- board access remains false；
- failure while building cleans partial destination and does not leave a misleading valid release.

Required classification：

~~~text
A7=PASS | BLOCK
~~~

## 16. A8 — main drift, race, duplicate run, retention and operator-mix risks

The intended operator rule is:

~~~text
if main changes before A/B/C/D chain completes:
    STOP
    prior chain becomes historical/non-authoritative
    fresh rebind
    rebuild from new exact main
~~~

Review whether source + workflow enforce this strongly enough even under:

- A and B launched in parallel；
- main changes after A but before B；
- main changes after A/B but before C；
- main changes after C but before D；
- duplicate successful F3 or F4 runs for the same source；
- same artifact name existing in different runs；
- F4 14-day retention expiring before C；
- run retry / rerun attempts；
- one upstream run cancelled then rerun；
- operator supplies wrong run ID but correct-looking artifact name.

Required classification：

~~~text
A8=PASS | BLOCK | PASS_WITH_OPERATOR_GUARD
~~~

If an operator guard is required, specify an exact mechanical check, not a vague instruction.

## 17. A9 — local exact-release validation sufficiency

The separate local validation gate after D is intended to prove the downloaded official artifact is exactly the production release built by D.

Minimum intended checks:

~~~text
workflow path/run/head/event/status binding
artifact ID/name/digest/unexpired binding
downloaded official Actions artifact identity
outer artifact set exact
release tar SHA sidecar exact
safe extraction
release directory verify PASS
release.source_head=current exact main
release.source_tree=current exact main tree
required logical artifact set exact
each artifact size/SHA exact
v2_mac_tools manifest exact
repaired executor/verifier bytes present
secret_values_included=false
board_access=false
local cache binding recorded
~~~

Astra must answer:

1. Is this enough to compensate for no final-workflow post-upload re-download step?
2. What exact extra local checks are required, if any?
3. Must the Actions artifact digest itself be recorded and compared?
4. Must local validation verify the release tar contains no unexpected members / unsafe paths before extraction?
5. Must the local cache retain both GitHub artifact identity and release internal identity?

Required classification：

~~~text
A9=PASS | BLOCK | PASS_WITH_REQUIRED_LOCAL_CHECKS
~~~

## 18. A10 — whole-chain prebuild decision

Perform a whole-chain review, not just local checks.

Search for any new blocker in:
- source provenance；
- artifact provenance；
- release completeness；
- packaging/runtime dependency completeness；
- security boundaries；
- credential leakage；
- mutable external dependency assumptions；
- source/main race；
- evidence truthfulness；
- old authority accidentally retained；
- local validation gap；
- Standard Fresh Armbian qualification boundary；
- accidental real-T1 mutation path from build workflows.

Also confirm that this review does **not** reopen unrelated historical areas unless current main directly regressed them:

~~~text
PR474=false
KF094=false
KF095=false
KF096=false
RADIO_STATE_MACHINE=false
MULTI_RELAY_SELECTION=false
B2_ADDRESS_MIGRATION=false
OLD_F5_V1_ROUTE=false
~~~

Required final classification：

~~~text
A10=PASS | BLOCK
~~~

## 19. Standard Fresh Armbian / real-T1 boundary

Even if A1–A10 all pass:

~~~text
REAL_T1_PRODUCTION_EXECUTION=false
REAL_T1_NONDISRUPTIVE_ACCEPTANCE=false
KF_122=OPEN
~~~

The allowed next progression is only:

~~~text
F3/F4 artifact rebuild
-> release-inputs
-> final release
-> local exact-release validation
-> Standard Fresh Armbian read-only qualification
-> separate real-T1 production authorization decision
~~~

A PASS here is not permission to run the production executor.

## 20. Required evidence standard

For every BLOCK:
- cite exact file + function/section；
- explain the concrete false-PASS / false-authority / unsafe execution path；
- identify whether it is source, workflow, artifact, local-validation, or operator-contract blocker；
- give the minimum repair scope；
- do not propose broad redesign unless required.

For every PASS:
- state what exact enforcement proves it；
- distinguish source guarantee from operator procedure；
- do not convert “not observed” into “proved absent.”

Do not rely only on documentation assertions when source is available.

## 21. Required final output

Return the following exact fields first:

~~~text
TASK=N3W_T1_F5_V2_EXACT_MAIN_RELEASE_REBUILD_ASTRA_PREBUILD_REVIEW_20261021_01

REVIEW_MAIN=
REVIEW_MAIN_TREE=
MAIN_DRIFT=

PR628_REACHABLE_FROM_MAIN=
POST_PR628_NON_DOC_DRIFT=
PR629_DOCS_ONLY=
PR630_DOCS_ONLY=

A1_EXACT_MAIN_AUTHORITY=
A2_F3_PRODUCER=
A3_F4_REBOOT_PRODUCER=
A4_RELEASE_INPUT_PROVENANCE=
A5_FINAL_RELEASE_PROVENANCE=
A6_MAC_TOOLS_RUNTIME_COMPLETENESS=
A7_RELEASE_CONTRACT_INTEGRITY=
A8_DRIFT_RACE_RETENTION=
A9_LOCAL_VALIDATION=
A10_WHOLE_CHAIN=

BLOCKER_COUNT=
NONBLOCKING_NOTE_COUNT=
SOURCE_REPAIR_REQUIRED=
WORKFLOW_REPAIR_REQUIRED=
LOCAL_VALIDATION_ADDITIONS_REQUIRED=

F3_F4_REBUILD_READY=
REAL_T1_AUTHORIZED=false

RESULT=PASS | PASS_WITH_NONBLOCKING_NOTES | BLOCK

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
WORKFLOW_DISPATCH=false
GITHUB_ARTIFACT_PRODUCTION=false
MERGE=false

STOP_POINT=
NEXT_ONE_GATE=
~~~

If PASS / PASS_WITH_NONBLOCKING_NOTES:

~~~text
NEXT_ONE_GATE=
N3W_T1_F5_V2_EXACT_MAIN_F3_F4_ARTIFACT_REBUILD_EXECUTION_20261021_01
~~~

If BLOCK:
- define exactly one bounded source/workflow/local-validation repair gate；
- do not dispatch builds；
- do not access T1.

## 22. Review brief status

~~~text
BRIEF_SOURCE_MAIN=e9ca449bc95b45235b7f95ca5478b5a7102daeb7
BRIEF_SOURCE_TREE=b25ce47f2dd20e569eb7b674317991a11ee1c4e0

BRIEF_ONLY=true
PRODUCT_SOURCE_MUTATION=false
WORKFLOW_MUTATION=false
BUILD_DISPATCH=false
T1_ACCESS=false
MERGE=false
~~~
