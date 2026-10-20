# N3W T1 F5 V2 R1 final closure review / R2 entry decision — 2026-10-20

## 0. Gate

~~~text
TASK=N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R1_FINAL_CLOSURE_REVIEW_R2_ENTRY_DECISION_20261020_01

REVIEW_SOURCE_HEAD=e86f95d71b2293a933e9ad38acc0cd42beb8e4b7
SOURCE_BASE_MAIN=4223f23d2579241f6568a1ba3fbbccf26b3bc3c1
SOURCE_PR=624
SOURCE_BRANCH=feat/n3w-t1-f5-v2-source-implementation-20261019

R1_CI=12_OF_12_WORKFLOWS_SUCCESS
BEHIND_MAIN=0
UNRESOLVED_REVIEW_THREADS=0

REVIEW_RESULT=BLOCKERS_OPEN
R1_CLOSED_PASS=false
R2_ENTRY_ELIGIBLE=false

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
R2_STARTED=false
~~~

本 gate 的任务是做 R1 最终关闭判断和 R2 入口判断，不做 repair，也不进入 R2。

## 1. 已确认关闭的 R1 范围

以下此前 blocker 在 exact review source head 上均已确认修复存在，并由专用 `r1-foundations` CI 覆盖：

~~~text
FINAL_RESULT_ACCEPTED_DEVICE_INVARIANTS=CLOSED
SSH_TRUST_AND_NETWORK_EVIDENCE_STOP_UNAVAILABLE=CLOSED
FRESH_PRODUCT_RESIDUE_COVERAGE=CLOSED
FORENSIC_ORIGINAL_FAILURE_PRESERVATION=CLOSED
FORENSIC_VERIFIED_MANIFEST_BEFORE_REFLASH_HELPER=CLOSED
PRODUCTION_MARKER_AUTHORITY_ROOT_OWNER_MODE=CLOSED
PRODUCTION_AUTHORITY_ROOT_AS_FRESH_RESIDUE=CLOSED
MARKER_READ_HASH_ACCEPT_PARENT_REVALIDATION=CLOSED
FORENSIC_ROOT_DIRECT_SYMLINK_REJECTION=CLOSED
APPROVED_RELEASE_F3_IMAGE_BINDING=CLOSED
FINAL_RESULT_MARKER_STATE_ERROR_CLASS_REPRESENTATION=CLOSED
~~~

SSH transport 仍保持 archived V1 selective reuse 边界，没有恢复 V1 顶层 recovery/authority state machine。

## 2. Remaining blocker A — final result forensic ordering

Frozen V2 failure-finalization order：

~~~text
STARTED + not durable ACCEPTED + FAIL/UNKNOWN
-> FREEZE_EVIDENCE
-> FORENSIC_SNAPSHOT_COMPLETE
-> SESSION_CLOSE
-> TARGET_DISPOSITION=REFLASH_REQUIRED
-> REFLASH_ALLOWED
~~~

Whole-source regression matrix也明确要求：

~~~text
snapshot/manifest completion before REFLASH_REQUIRED
no reflash disposition before session close terminal state
~~~

当前 `validate_result()` 已经要求：

~~~text
marker_state=STARTED
-> status=FAIL
-> reflash_required=true
~~~

但仍允许：

~~~text
marker_state=STARTED
evidence_complete=false
operator_session_closed=false
reflash_required=true
~~~

并且当前 STARTED error-class set 仍包含：

~~~text
PROCESS_CLEANUP_FAIL
~~~

这会使 final result contract 能表达“取证或 session close 尚未完成，但已给出 reflash disposition”的非法终态。

### Required repair

R1 contract 应收敛为：

~~~text
marker_state=STARTED
-> status=FAIL
-> device_acceptance!=PASS
-> T1_PRODUCTION_READY=false
-> evidence_complete=true
-> operator_session_closed=true
-> reflash_required=true
-> error_class in {
     MUTATION_FAIL_REFLASH_REQUIRED,
     POST_REBOOT_ACCEPTANCE_FAIL_REFLASH_REQUIRED
   }
~~~

`PROCESS_CLEANUP_FAIL` 的 final-result 合法路线保留给：

~~~text
marker_state=ACCEPTED
device_acceptance=PASS
T1_PRODUCTION_READY=true
reflash_required=false
~~~

即 durable ACCEPTED 后的 Mac/process cleanup failure。

## 3. Remaining blocker B — qualification read-failure classification

Frozen qualification rule：

~~~text
read/probe/SSH/network evidence unavailable
-> STOP_UNAVAILABLE
-> reflash_required=false
~~~

当前 remote probe 的 `service(name)` 已记录各 systemctl 子命令 return code。

但是：

~~~text
firstboot=service("armbian-firstrun.service")
~~~

之后并没有把不可执行的 systemctl/show probe 加入：

~~~text
unavailable[]
~~~

因此如果 systemctl/read command 本身失败，firstboot fields 可能为空，`evaluate()` 会走：

~~~text
HOST.FIRSTBOOT=FAIL
-> FAIL_REFLASH_REQUIRED
~~~

这把“无法读取”错误提升成“已证明 target nonstandard”。

### Required repair

Remote read-only probe 必须区分：

~~~text
firstboot service state mismatch
-> observed nonstandard
-> FAIL_REFLASH_REQUIRED

firstboot/systemctl probe unavailable
-> unavailable includes firstboot/systemd probe
-> STOP_UNAVAILABLE
-> reflash_required=false
~~~

focused regression 必须覆盖真实 observation classification 和 remote-probe unavailable construction guard。

## 4. R2 entry decision

~~~text
R1_CLOSED_PASS=false
R2_ENTRY_ELIGIBLE=false
R2_STARTED=false
~~~

原因不是 CI failure。当前 exact source CI 全绿；阻塞点来自 final source contract review。

因此不得进入：

~~~text
HOST_BASELINE adaptation
F3 V2 run-context adaptation
production_v2 orchestrator
Provision/F4 interface adaptation
R3 post-reboot acceptance
~~~

## 5. Next one gate

~~~text
NEXT_ONE_GATE=
N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R1_FINAL_CLOSURE_BLOCKER_REPAIR_20261020_01
~~~

只允许修上面两个 R1 blocker，并补 focused tests。

修复后必须：

~~~text
exact-head CI
-> focused closure review
-> R1 CLOSED_PASS decision
-> only then R2 entry decision
~~~

## 6. Hard stop

~~~text
AUTO_EXECUTE_R2=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
STOP=true
~~~
