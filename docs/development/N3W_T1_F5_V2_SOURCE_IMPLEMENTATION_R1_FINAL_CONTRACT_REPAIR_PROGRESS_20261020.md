# N3W T1 F5 V2 R1 final contract repair 进展 — 2026-10-20

## 0. Gate

~~~text
TASK=N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R1_FINAL_CONTRACT_REPAIR_20261020_01
RESULT=SOURCE_REPAIR_IMPLEMENTED_CI_PENDING

SOURCE_BASE_MAIN=4223f23d2579241f6568a1ba3fbbccf26b3bc3c1
SOURCE_BRANCH=feat/n3w-t1-f5-v2-source-implementation-20261019
SOURCE_PR=624

REVIEWED_HEAD_BEFORE_REPAIR=21c83603de7ad7185ad43ffd30bf390d73c77b3f
SOURCE_TEST_HEAD_BEFORE_PROGRESS_ALIGNMENT=8eec6c156b8dfa74b883e811fe384e99827af7e1

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
R2_STARTED=false
~~~

本 gate 只修复 R1 final closure review 发现的 2 个 contract blocker，不进入 R2。

## 1. F1 — approved release now binds exact F3 image identity

冻结工作包要求 approved release 至少冻结：

~~~text
F3 payload hash
F3 image hash
F3 transport hash
~~~

原 R1 release contract 已要求：

~~~text
f3_payload
transport_contract
~~~

但缺少独立的 image artifact binding。

现在 `REQUIRED_RELEASE_ARTIFACTS` 增加：

~~~text
f3_image
~~~

因此一个 release 如果没有独立的 F3 image SHA-256 / size binding，将直接：

~~~text
release_artifacts_missing
~~~

对应 focused regression 已加入。

## 2. F2 — final result can now represent and enforce target disposition

`gh.n3w-t1-production-v2-result/1` 在当前未合并 R1 candidate 内补齐两个稳定字段：

~~~text
marker_state:
  ABSENT
  STARTED
  ACCEPTED

error_class:
  NONE
  PRE_MUTATION_FAIL
  MUTATION_FAIL_REFLASH_REQUIRED
  POST_REBOOT_ACCEPTANCE_FAIL_REFLASH_REQUIRED
  PROCESS_CLEANUP_FAIL
~~~

不增加 recovery/resume 状态机；这些字段只描述最终事实和 disposition。

### 2.1 PASS

生产 PASS 现在必须同时满足：

~~~text
status=PASS
marker_state=ACCEPTED
error_class=NONE
device_acceptance=PASS
T1_PRODUCTION_READY=true
operator_session_closed=true
evidence_complete=true
reflash_required=false
~~~

### 2.2 STARTED but not ACCEPTED

任何 final result 只要：

~~~text
marker_state=STARTED
~~~

就必须：

~~~text
status=FAIL
device_acceptance!=PASS
T1_PRODUCTION_READY=false
reflash_required=true
~~~

允许的 error class 只限：

~~~text
MUTATION_FAIL_REFLASH_REQUIRED
POST_REBOOT_ACCEPTANCE_FAIL_REFLASH_REQUIRED
PROCESS_CLEANUP_FAIL
~~~

因此以下组合不再可被 schema 接受：

~~~text
status=FAIL
marker_state=STARTED
device_acceptance=NOT_REACHED
reflash_required=false
~~~

这直接关闭“STARTED / mutation 已进入，但 final result 没有要求重装”的合同缺口。

### 2.3 ABSENT

marker 尚未创建时：

~~~text
marker_state=ABSENT
status=FAIL
error_class=PRE_MUTATION_FAIL
device_acceptance=NOT_REACHED
T1_PRODUCTION_READY=false
~~~

`reflash_required` 允许 true 或 false：

- qualification 已证明 target nonstandard 时可为 true；
- SSH/网络/证据不足等 pre-mutation stop/fail 时可为 false。

这样不会把“marker 尚未 STARTED”错误等同于“永远不需要 reflash”。

### 2.4 durable ACCEPTED + later Mac/process failure

如果：

~~~text
marker_state=ACCEPTED
device_acceptance=PASS
T1_PRODUCTION_READY=true
~~~

则始终：

~~~text
reflash_required=false
~~~

overall status 可以是：

~~~text
PASS + error_class=NONE
~~~

也可以是：

~~~text
FAIL + error_class=PROCESS_CLEANUP_FAIL
~~~

因此继续保留冻结规则：

~~~text
durable ACCEPTED
+ later Mac cleanup/public-result/archive failure
-> device acceptance remains PASS
-> T1_PRODUCTION_READY=true
-> overall process FAIL
-> REFLASH_REQUIRED=false
~~~

## 3. Regression coverage added

新增/更新 focused tests：

~~~text
release without f3_image -> reject

PASS requires ACCEPTED + NONE + accepted/ready/closed/evidence/no-reflash

STARTED failure + reflash_required=true -> accept
STARTED failure + reflash_required=false -> reject

STARTED + PRE_MUTATION_FAIL -> reject

post-reboot acceptance failure
-> STARTED
-> device_acceptance=FAIL
-> reflash_required=true

ABSENT + PRE_MUTATION_FAIL
-> reflash_required=false allowed
-> reflash_required=true allowed

ABSENT + mutation failure class -> reject
ABSENT + device acceptance claim -> reject

ACCEPTED + later PROCESS_CLEANUP_FAIL
-> accepted/ready retained
-> no reflash

ACCEPTED + reflash_required=true -> reject
~~~

## 4. R1 boundary unchanged

本 gate 没有修改 R2 business primitives：

~~~text
tools/n3w_t1_fresh_host_baseline.py
tools/n3w_t1_fresh_product_bootstrap.py
tools/n3w_t1_fresh_product_staging_host.py
tools/n3w_t1_device_provisioning_host.py
tools/n3w_t1_f4_activation_host.py
tools/n3w_t1_f4_reboot_authority.py
tools/n3w_t1_f4_reboot_verify.py
~~~

因此：

~~~text
R2_STARTED=false
HOST_BASELINE_ADAPTATION_STARTED=false
F3_V2_CONTEXT_ADAPTATION_STARTED=false
PROVISION_SOURCE_MUTATION=false
F4_SOURCE_MUTATION=false
V2_ORCHESTRATOR_IMPLEMENTATION_STARTED=false
POST_REBOOT_ACCEPTANCE_IMPLEMENTATION_STARTED=false
~~~

## 5. Current stop

~~~text
R1_FINAL_CONTRACT_REPAIR=IMPLEMENTED_CANDIDATE
R1_FINAL_CONTRACT_REPAIR_CI=PENDING

NEXT_ONE_GATE=
N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R1_FINAL_CONTRACT_REPAIR_EXACT_HEAD_CI_COMPLETION_CHECK_20261020_01

AUTO_EXECUTE_R2=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
STOP=true
~~~
