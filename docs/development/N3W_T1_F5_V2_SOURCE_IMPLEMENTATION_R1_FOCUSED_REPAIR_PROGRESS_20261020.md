# N3W T1 F5 V2 R1 focused repair 进展 — 2026-10-20

## 0. Gate

~~~text
TASK=N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R1_FOCUSED_REPAIR_20261020_01
RESULT=SOURCE_REPAIR_IMPLEMENTED_CI_PENDING

SOURCE_BASE_MAIN=4223f23d2579241f6568a1ba3fbbccf26b3bc3c1
SOURCE_BRANCH=feat/n3w-t1-f5-v2-source-implementation-20261019
SOURCE_PR=624

REVIEWED_HEAD_BEFORE_REPAIR=327d8e8e5be2fb5904f6a462c2e301738f054d95

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
R2_STARTED=false
~~~

本 gate 只修复 R1 focused source review 发现的 5 个 blocker，不进入 R2。

## 1. B1 — final result contract fail-closed

`tools/n3w_t1_production_v2_contract.py` 现在强制：

~~~text
DEVICE_ACCEPTANCE=PASS <=> T1_PRODUCTION_READY=true

DEVICE_ACCEPTANCE=PASS
-> REFLASH_REQUIRED=false

OVERALL PASS
-> DEVICE_ACCEPTANCE=PASS
-> T1_PRODUCTION_READY=true
-> OPERATOR_SESSION_CLOSED=true
-> EVIDENCE_COMPLETE=true
-> REFLASH_REQUIRED=false
~~~

同时保留 accepted-device cleanup exception：

~~~text
DEVICE_ACCEPTANCE=PASS
T1_PRODUCTION_READY=true
OVERALL_PROCESS=FAIL
REFLASH_REQUIRED=false
~~~

因此 Mac 侧 cleanup/archive 失败不会把一台 durable ACCEPTED 设备错误标记成需要重装。

新增 focused regression 覆盖 PASS/cleanup-fail/reflash-forbidden 组合。

## 2. B2 — qualification evidence insufficiency cannot authorize reflash

`tools/n3w_t1_fresh_armbian_qualification.py` 已把以下证据不足统一收敛为：

~~~text
STOP_UNAVAILABLE
REFLASH_REQUIRED=false
~~~

包括：

- SSH host-key trust 未证明；
- sudo noninteractive 不可证明；
- SSH service readiness 不可证明；
- NetworkManager readiness 不可证明；
- default route 不可证明；
- DNS readiness 不可证明；
- NTP readiness 不可证明；
- remote read-only probe exception。

已经观察到的 nonstandard host 状态仍保持：

~~~text
wrong OS / Armbian / arch
firstboot contract mismatch
storage contract mismatch
APT source mismatch
Docker residue
product residue

-> FAIL_REFLASH_REQUIRED
~~~

原测试中 `ssh_trust=false -> FAIL_REFLASH_REQUIRED` 已改为 `STOP_UNAVAILABLE`。

## 3. B3 — Standard Fresh residue coverage completed

Fresh qualification 的 explicit product residue set 现在补入：

~~~text
/var/lib/n3w-fresh-bootstrap-authorizations
/var/lib/n3w-t1-provisioning
/var/tmp/n3w-t1-provisioning-candidate
~~~

并继续覆盖现有 product roots、helpers、dispatcher、systemd files、V2 marker。

另外新增 read-only runtime residue probe：

~~~text
PRODUCT_UNITS:
  n3wfc4-broker-ingress-guard.service
  n3wfc4-provision-resume.service
  n3wfc4-broker-activation.service
  n3wfc4-services-activation.service
  n3wfc4-broker-certificate-lifecycle.service
  n3wfc4-broker-certificate-lifecycle.timer

PRODUCT_TARGET_PORTS:
  1883
  8883
  18883
  8123
  47110
  47111
  47112
~~~

systemd/ss read-only probe 如果无法执行，进入 `STOP_UNAVAILABLE`；观察到任一 product unit/listener 则 `FAIL_REFLASH_REQUIRED`。

未恢复 arbitrary-state ownership classifier。

## 4. B4 — forensic freeze + verified manifest before reflash

`freeze_failure()` 不再覆盖失败现场的 `target_mutation`。

如果失败状态已经记录：

~~~text
target_mutation=true
~~~

该事实原样保留。

collector 自己的只读边界独立记录为：

~~~text
forensic_collector_target_mutation=false
~~~

manifest 现在明确记录：

~~~text
FORENSIC_SNAPSHOT_COMPLETE=true
NO_TARGET_MUTATION=true
UNAVAILABLE_IS_EXPLICIT=true
ORIGINAL_FAILURE_NOT_OVERWRITTEN=true
BUNDLE_SHA256_PRESENT=true
~~~

`reflash_disposition()` 不再接受调用方任意传入的 manifest mapping。

现在固定：

~~~text
reflash_disposition(evidence_root, session_close)
-> verify_manifest(evidence_root)
-> verify evidence file size/SHA/bundle binding
-> verify snapshot read-only safety contract
-> verify original failure freeze
-> require session_closed=true
-> only then REFLASH_ALLOWED=true
~~~

因此伪造一个 `FORENSIC_SNAPSHOT_COMPLETE=true` 字典不能绕过 forensic-before-reflash gate。

## 5. B5 — production marker authority directory hardening

`/var/lib/n3w-production` 已存在时，不再只检查“目录且非 symlink”。

现在必须同时满足：

~~~text
kind=directory
owner=current privileged execution uid
mode=0700
not symlink
~~~

不满足 owner/mode 直接 fail-closed。

新创建 authority root 也明确 chmod 0700、fsync grandparent，并重新验证 metadata。

marker file 本身继续保持：

~~~text
mode=0600
owner=current privileged execution uid
atomic create / atomic replace
file fsync
directory fsync
~~~

## 6. Tests added/updated

Focused repair regression 覆盖：

- result PASS 必须 accepted/ready/session-closed/evidence-complete/no-reflash；
- durable accepted device + Mac cleanup failure保留 acceptance/no-reflash；
- accepted device 禁止 reflash_required；
- SSH trust / network readiness gap -> STOP_UNAVAILABLE；
- historical authorization/provisioning residue -> FAIL_REFLASH_REQUIRED；
- product unit/listener residue -> FAIL_REFLASH_REQUIRED；
- failure freeze保留真实 target_mutation；
- reflash disposition必须读取并验证 evidence root manifest；
- forged/tampered manifest不能授权 reflash；
- authority root mode/owner mismatch拒绝 marker start。

## 7. Boundary unchanged

本 gate 没有修改：

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

## 8. Current stop

~~~text
R1_FOCUSED_REPAIR=IMPLEMENTED_CANDIDATE
R1_REPAIR_CI=PENDING

NEXT_ONE_GATE=
N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R1_REPAIR_EXACT_HEAD_CI_COMPLETION_CHECK_20261020_01

AUTO_EXECUTE_R2=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
STOP=true
~~~
