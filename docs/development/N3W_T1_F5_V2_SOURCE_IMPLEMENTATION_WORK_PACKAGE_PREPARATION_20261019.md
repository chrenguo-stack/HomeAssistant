# N3W T1 F5 V2 源码实现工作包准备 — 2026-10-19

## 0. Gate

~~~text
TASK=N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_WORK_PACKAGE_PREPARATION_20261019_01
RESULT=WORK_PACKAGE_FROZEN

SOURCE_MAIN=4223f23d2579241f6568a1ba3fbbccf26b3bc3c1
SOURCE_BRANCH=feat/n3w-t1-f5-v2-source-implementation-20261019

F5_V2_ARCHITECTURE_AUTHORITY=
docs/development/N3W_T1_F5_PRODUCTION_PROCESS_V2_SIMPLIFIED_ARCHITECTURE_CONTRACT_20261019.md

F5_V2_SOURCE_DESIGN_AUTHORITY=
docs/development/N3W_T1_F5_PRODUCTION_PROCESS_V2_SOURCE_DESIGN_20261019.md

F5_V2_SOURCE_REVIEW_AUTHORITY=
docs/development/N3W_T1_F5_PRODUCTION_PROCESS_V2_SOURCE_DESIGN_REVIEW_20261019.md

F5_V2_REPOSITORY_ALIGNMENT_FINAL=true

PRODUCT_SOURCE_IMPLEMENTATION=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~

本 gate 只冻结实现工作包、文件边界、复用边界和分阶段顺序，不写产品源码。

目标是避免重新形成 F5 V1 的长 stacked PR 链。V2 源码实现使用一个干净分支、一个 Draft PR、分阶段提交和 CI 检查。

## 1. Implementation strategy

~~~text
ONE_SOURCE_BRANCH=true
ONE_SOURCE_PR=true
STACKED_IMPLEMENTATION_PRS=false

R1=FOUNDATIONS
R2=BUSINESS_PRIMITIVE_ADAPTATION_AND_ORCHESTRATION
R3=POST_REBOOT_ACCEPTANCE_INTEGRATION_AND_WHOLE_SOURCE_CLOSURE
~~~

每个阶段在同一 source branch 上形成独立可复核 commit 集合。

任何阶段出现 blocker，只修当前 branch；不新开平行 repair stack，除非必须隔离已经合并后的回归。

## 2. Selective reuse from archived V1

F5 V1 PR #612-#621 保持 ARCHIVED / CLOSED / UNMERGED。

V2 不恢复 V1 顶层状态机，但允许把已经验证过、且与 V2 架构一致的独立基础能力作为参考源码重新审查后选择性移植。

允许优先参考：

~~~text
PR612 / 9048dd7c6b48c0620471919c0cf96c96bdab71f1
  tools/n3w_t1_ssh_transport.py
  tests/tools/test_n3w_t1_ssh_transport.py

PR613 / b2622cb7588d0224e1345abe84bd7aec307a2aae
  tools/n3w_t1_f5_release_builder.py
  tests/tools/test_n3w_t1_f5_release_builder.py
  .github/workflows/n3w-t1-f5-exact-production-release-ci.yml
~~~

这些只能作为 implementation reference，不得 whole-branch merge/cherry-pick。

明确禁止直接恢复：

~~~text
n3w_t1_production_authority.py
n3w_t1_production_runtime.py
V1 per-phase parent claim/recovery
failed-run terminalizer
UNKNOWN-run adjudication
repair/reopen/resume state machine
~~~

V2 只保留 STARTED -> ACCEPTED 顶层 run marker，并复用现有 F3/F4 内部 one-shot safety guards。

## 3. R1 — Foundations

R1 只建立新 V2 安全基础面，不修改现有 F3/F4 产品行为。

### 3.1 ADD

~~~text
tools/n3w_t1_production_v2_contract.py
tools/n3w_t1_ssh_transport.py
tools/n3w_t1_fresh_armbian_qualification.py
tools/n3w_t1_production_marker.py
tools/n3w_t1_failure_forensics.py

tests/tools/test_n3w_t1_production_v2_contract.py
tests/tools/test_n3w_t1_ssh_transport.py
tests/tools/test_n3w_t1_fresh_armbian_qualification.py
tests/tools/test_n3w_t1_production_marker.py
tests/tools/test_n3w_t1_failure_forensics.py
~~~

### 3.2 Contract responsibilities

`n3w_t1_production_v2_contract.py` 只负责稳定 schema / canonical hash / release-plan-result validation，不做 SSH、target mutation 或 phase dispatch。

至少定义：

~~~text
RELEASE_SCHEMA=gh.n3w-t1-production-v2-release/1
PLAN_SCHEMA=gh.n3w-t1-production-v2-plan/1
RESULT_SCHEMA=gh.n3w-t1-production-v2-result/1
RUN_MARKER_SCHEMA=gh.n3w-t1-production-v2-run/1
RUN_CONTEXT_SCHEMA=gh.n3w-t1-production-v2-run-context/1
FORENSIC_SCHEMA=gh.n3w-t1-production-v2-forensics/1
~~~

approved release 至少冻结：

- source head/tree；
- OS / Armbian / architecture contract；
- docker.io exact Ubuntu package version；
- docker-compose-v2 exact Ubuntu package version；
- apt source policy；
- F3 payload/image/transport hashes；
- F4/reboot control package hashes；
- V2 Mac tool file set/hash；
- capacity minimums；
- public evidence policy。

### 3.3 SSH transport

优先选择性移植 archived V1 的 SSH transport，因为它已经实现：

- known_hosts exact host-key binding；
- one password prompt per SSH epoch；
- ControlMaster reuse；
- child commands BatchMode-only；
- local private socket/work-root；
- explicit close and post-reboot new epoch；
- no password persistence；
- no management key installation。

V2 只允许做必要的命名/结果字段收敛，不重写已经验证过的基础 SSH 生命周期。

### 3.4 Fresh qualification

只读取、固定小检查集：

~~~text
HOST.OS_ARCH
HOST.ARMBIAN_IDENTITY
HOST.FIRSTBOOT
HOST.SSH_TRUST
HOST.PRIVILEGE
HOST.NETWORK_TIME
HOST.STORAGE
HOST.APT_SOURCE
HOST.DOCKER_ABSENT
HOST.PRODUCT_ABSENT
~~~

必须输出：

~~~text
PASS
FAIL_REFLASH_REQUIRED
STOP_UNAVAILABLE
~~~

R1 不允许调用旧 arbitrary inventory ownership classifier。

### 3.5 Production marker

target helper 通过 SSH stdin/临时受控执行即可，不要求先永久安装工具。

durable state：

~~~text
/var/lib/n3w-production/run.json
~~~

命令首版只有：

~~~text
inspect
start
accept
~~~

没有：

~~~text
resume
repair
clear
reset
force
reopen
~~~

start 必须 atomic-create + file fsync + directory fsync。
accept 必须验证 exact STARTED binding 后 atomic-replace + fsync。

### 3.6 Failure forensics

Mac 侧只读取证。

固定产生：

~~~text
failure-summary.json
forensic-snapshot.json
evidence-manifest.json
~~~

必须证明：

~~~text
NO_TARGET_MUTATION=true
UNAVAILABLE_IS_EXPLICIT=true
ORIGINAL_FAILURE_NOT_OVERWRITTEN=true
BUNDLE_SHA256_PRESENT=true
~~~

## 4. R2 — Existing business primitive adaptation + orchestrator

R2 才允许修改既有部署 primitive。

### 4.1 Required ADD

~~~text
tools/n3w_t1_production_v2.py
tests/tools/test_n3w_t1_production_v2.py
~~~

### 4.2 Required ADAPT — HOST_BASELINE

~~~text
tools/n3w_t1_fresh_host_baseline.py
tests/tools/test_n3w_t1_fresh_host_baseline.py
~~~

冻结规则：

~~~text
LATEST_APT_CANDIDATE_IS_NOT_AUTHORITY=true
RELEASE_BOUND_PACKAGE_VERSION_REQUIRED=true
APT_CANDIDATE_MUST_EQUAL_RELEASE_VERSION=true
INSTALL_EXACT_PACKAGE_VERSION=true
VERSION_DRIFT_STOPS_BEFORE_INSTALL=true
~~~

可以通过明确 CLI version 参数或受控 release input 实现，但 Mac orchestrator 必须先验证 approved release，target primitive 不得自行选择“最新版本”。

### 4.3 Required ADAPT — F3

~~~text
tools/n3w_t1_fresh_product_bootstrap.py
tests/tools/test_n3w_t1_fresh_product_bootstrap.py

tools/n3w_t1_fresh_product_staging_host.py
tests/tools/test_n3w_t1_fresh_product_staging_host.py

.github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml
~~~

冻结边界：

~~~text
IMMUTABLE_PAYLOAD_CONTAINS_DYNAMIC_RUN_AUTHORITY=false
STATIC_HISTORICAL_AUTHORIZATION_ALONE_CAN_APPLY=false
V2_RUN_CONTEXT_OUTSIDE_PAYLOAD_ROOT=true
STARTED_MARKER_BINDING_REQUIRED_BEFORE_FIRST_F3_MUTATION=true
F3_ONE_SHOT_ACTION_CLAIM_ALLOWED=true
F3_RECOVERY_STATE_MACHINE=false
~~~

run context 至少绑定：

~~~text
run_id
release_id
release_sha256
source_head
target_binding_sha256
production_marker_sha256
action=F3_DEPLOY
~~~

如果 action 已领取后失败，正常路径进入 forensic + reflash，不恢复 F3。

### 4.4 Provision and F4 initial policy

初始实现默认不修改：

~~~text
tools/n3w_t1_device_provisioning_host.py
tools/n3w_t1_f4_activation_host.py
tools/n3w_t1_f4_reboot_authority.py
tools/n3w_t1_f4_reboot_verify.py
~~~

原因：

- Provision 现有 start/verify 语义可由 orchestrator 单次调用；
- F4 已有实机关闭的 transaction / one-shot / no-replay / rollback；
- F4 CLI 已允许传入 distinct authorization IDs；
- V2 可以从 run_id + action 确定性派生内部 action ID，无需删除 F4 guard。

只有 focused test 证明接口存在真实缺口时，才允许把对应文件加入当前 branch diff，并必须在 progress doc 中记录 exact reason。

正常 V2 不调用任何 `repair-*` 命令。

### 4.5 Orchestrator fixed sequence

~~~text
verify approved release locally
-> SSH epoch #1
-> host key binding
-> fresh qualification
-> build plan
-> one operator approval
-> marker STARTED
-> HOST_BASELINE
-> F3
-> Provision
-> F4 prepare/activate/accept/persist/cert
-> controlled reboot
-> close epoch #1
-> wait SSH
-> SSH epoch #2
-> post-reboot acceptance
-> marker ACCEPTED
-> close epoch #2
-> final result
~~~

mutation phase 不自动 retry。

## 5. R3 — Post-reboot acceptance + release integration

### 5.1 ADD

~~~text
tools/n3w_t1_post_reboot_acceptance.py
tests/tools/test_n3w_t1_post_reboot_acceptance.py
~~~

target-local acceptance 优先直接调用/包装现有：

~~~text
tools/n3w_t1_f4_reboot_verify.py
~~~

不复制已经存在的 Docker/systemd/TLS/MQTT/HA/certificate 验收逻辑。

V2 只补：

- V2 STARTED marker/run/release/target binding；
- approved release/source binding；
- Mac external probes；
- 90 s bounded observation；
- acceptance hash；
- marker ACCEPTED。

### 5.2 External acceptance

至少覆盖：

~~~text
TCP_8883
TLS_CA
TLS_HOSTNAME_SNI
INVALID_CREDENTIAL_REJECTED
HOMEASSISTANT_HTTP_READY
~~~

2026-10-20 修订：上列仅为 Mac 外部探测集合。Manager/HA 自身认证连接由 `runtime_service_auth` 独立证明，不允许 Mac 使用生产身份登录；详见当前架构合同 §7、源码设计 §6.1–6.3。观察要求包含连接连续性、就绪状态和关键错误，不能只看重启计数。结果为 acceptance `/2`，旧字段不复用语义。

### 5.3 Release builder

V2 source work需要提供可测试的 release builder/validator，但最终 production exact release 只能在 source merge 后从 exact main 构建。

候选文件：

~~~text
tools/n3w_t1_f5_v2_release_builder.py
tests/tools/test_n3w_t1_f5_v2_release_builder.py
.github/workflows/n3w-t1-f5-v2-source-ci.yml
.github/workflows/n3w-t1-f5-v2-exact-production-release-ci.yml
~~~

可以参考 archived V1 release builder 的 artifact hash/index/durable verification 逻辑，但必须删除 V1 phase-authority 假设，并改用 V2 release schema。

最终 release CI 不允许长期把旧 artifact ID 当作生产 authority。所有输入必须与 exact merged V2 source head/tree 绑定。

## 6. Whole-source regression matrix

合并前最低要求：

~~~text
QUALIFICATION
- exact fresh contract PASS
- wrong OS/board/arch FAIL_REFLASH_REQUIRED
- Docker/product residue FAIL_REFLASH_REQUIRED
- SSH/read failure STOP_UNAVAILABLE
- qualification is read-only

MARKER
- duplicate start rejected
- mismatched run/release/target rejected
- fsync/atomic write tested
- accept only from exact STARTED
- no reset/repair/reopen surface

HOST_BASELINE
- exact package versions only
- candidate drift stops before apt install
- no product service start

F3
- run context outside immutable payload
- static legacy authorization cannot authorize apply
- current STARTED marker required
- action replay rejected
- failure does not expose resume path

F4
- existing F4 source regression remains green
- distinct internal action IDs generated from one top-level run
- repair commands not reachable from normal V2 orchestrator

FORENSICS
- freeze original error first
- read-only snapshot
- unreachable target => explicit UNAVAILABLE
- snapshot/manifest completion before REFLASH_REQUIRED
- no reflash disposition before session close terminal state

REBOOT / ACCEPTANCE
- real boot identity must change
- existing F4 reboot verifier PASS required
- external TLS/MQTT/HA probes
- 90 s observation
- marker ACCEPTED last

FINAL RESULT
- deployment PASS alone != production PASS
- pre-ACCEPTED failure => REFLASH_REQUIRED
- durable ACCEPTED + later Mac cleanup failure => device remains accepted
- public result secret scan
~~~

## 7. File boundary

### Allowed source additions

~~~text
tools/n3w_t1_production_v2_contract.py
tools/n3w_t1_ssh_transport.py
tools/n3w_t1_fresh_armbian_qualification.py
tools/n3w_t1_production_marker.py
tools/n3w_t1_failure_forensics.py
tools/n3w_t1_production_v2.py
tools/n3w_t1_post_reboot_acceptance.py
tools/n3w_t1_f5_v2_release_builder.py

tests/tools/test_n3w_t1_production_v2_contract.py
tests/tools/test_n3w_t1_ssh_transport.py
tests/tools/test_n3w_t1_fresh_armbian_qualification.py
tests/tools/test_n3w_t1_production_marker.py
tests/tools/test_n3w_t1_failure_forensics.py
tests/tools/test_n3w_t1_production_v2.py
tests/tools/test_n3w_t1_post_reboot_acceptance.py
tests/tools/test_n3w_t1_f5_v2_release_builder.py

.github/workflows/n3w-t1-f5-v2-source-ci.yml
.github/workflows/n3w-t1-f5-v2-exact-production-release-ci.yml
~~~

### Allowed existing source adaptations

~~~text
tools/n3w_t1_fresh_host_baseline.py
tests/tools/test_n3w_t1_fresh_host_baseline.py

tools/n3w_t1_fresh_product_bootstrap.py
tests/tools/test_n3w_t1_fresh_product_bootstrap.py

tools/n3w_t1_fresh_product_staging_host.py
tests/tools/test_n3w_t1_fresh_product_staging_host.py

.github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml
~~~

### Conditional-only adaptations

~~~text
tools/n3w_t1_device_provisioning_host.py
tests/tools/test_n3w_t1_device_provisioning_host.py

tools/n3w_t1_f4_activation_host.py
tests/tools/test_n3w_t1_f4_activation_host.py

tools/n3w_t1_f4_reboot_authority.py
tests/tools/test_n3w_t1_f4_reboot_authority.py

tools/n3w_t1_f4_reboot_verify.py
tests/tools/test_n3w_t1_f4_reboot_verify.py
~~~

这些 conditional 文件只有在 focused source test 证明现有接口无法满足 V2 frozen contract 时才能修改。

不允许扩大到 firmware / ESP32 / radio / pairing business logic。

## 8. Source PR policy

本 branch 将承载完整 V2 implementation。

~~~text
SOURCE_PR=ONE_DRAFT_PR
SOURCE_BRANCH=feat/n3w-t1-f5-v2-source-implementation-20261019
SOURCE_BASE=4223f23d2579241f6568a1ba3fbbccf26b3bc3c1

MERGE_BEFORE_WHOLE_SOURCE_REVIEW=false
T1_ACCESS_BEFORE_SOURCE_CLOSURE=false
BOARD_ACCESS=false
~~~

CI 较长时不反复轮询；给出 PR/CI 链接并 STOP。

源码关闭后：

~~~text
source whole review
-> exact-head CI
-> merge decision
-> merge
-> fresh main rebind
-> exact V2 release build
-> fresh-T1 read-only qualification
-> explicit live deployment authorization
~~~

## 9. Current stop

~~~text
WORK_PACKAGE_PREPARATION=CLOSED
PRODUCT_SOURCE_IMPLEMENTATION=false

NEXT_ONE_GATE=
N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R1_FOUNDATIONS_20261019_01

AUTO_EXECUTE_NEXT_GATE=false

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
STOP=true
~~~
