# N3W T1 F5 V2 源码设计 — Fresh Armbian -> Deploy -> Reboot -> Acceptance

Date: 2026-10-19

## 0. Gate

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V2_SOURCE_DESIGN_20261019_01
RESULT=SOURCE_DESIGN_STARTED_AND_FROZEN_ON_CANDIDATE

SOURCE_IMPLEMENTATION=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~

本设计落实 V2 架构，不继续扩展 V1 的 inventory/recovery 状态机。

## 1. Source architecture

建议正常量产源码收敛为四个清晰责任面：

~~~text
Mac:
  n3w_t1_production_v2.py
  n3w_t1_fresh_armbian_qualification.py
  n3w_t1_post_reboot_acceptance.py

T1:
  n3w_t1_production_marker.py

Existing business primitives:
  n3w_t1_fresh_host_baseline.py
  n3w_t1_fresh_product_staging_host.py
  n3w_t1_device_provisioning_host.py
  n3w_t1_f4_activation_host.py
  n3w_t1_f4_reboot_authority.py
  n3w_t1_f4_reboot_verify.py
~~~

V2 入口不再直接依赖：

~~~text
n3w_t1_minimal_baseline_readonly_inventory.py
V1 per-phase production authority
V1 failed-run terminalizer
V1 UNKNOWN-run adjudication
~~~

这些文件可保留为历史/工程诊断工具，先不删除，避免在 V2 source stabilization 前扩大 diff。

## 2. Fresh Armbian qualification

新增：

~~~text
tools/n3w_t1_fresh_armbian_qualification.py
~~~

它只回答一个问题：

> 当前 T1 是否严格等于 Standard Fresh Armbian contract？

输出稳定 schema：

~~~json
{
  "status": "PASS|FAIL",
  "checks": {
    "HOST.OS_ARCH": "PASS|FAIL",
    "HOST.ARMBIAN_IDENTITY": "PASS|FAIL",
    "HOST.FIRSTBOOT": "PASS|FAIL",
    "HOST.SSH_TRUST": "PASS|FAIL",
    "HOST.PRIVILEGE": "PASS|FAIL",
    "HOST.NETWORK_TIME": "PASS|FAIL",
    "HOST.STORAGE": "PASS|FAIL",
    "HOST.APT_SOURCE": "PASS|FAIL",
    "HOST.DOCKER_ABSENT": "PASS|FAIL",
    "HOST.PRODUCT_ABSENT": "PASS|FAIL"
  },
  "read_only": true,
  "mutation_performed": false
}
~~~

不输出 UNKNOWN ownership 分类；读取失败就是对应 check FAIL。

## 3. Minimal production marker

新增 target helper：

~~~text
tools/n3w_t1_production_marker.py
~~~

目标端只维护一个小型 durable state：

~~~text
/var/lib/n3w-production/run.json
~~~

### 3.1 start

生产 approval 完成后、HOST_BASELINE mutation 前执行 marker start。

必须使用 atomic create + fsync，且拒绝已有 marker。

字段：

- schema；
- run_id；
- release_id；
- release_sha256；
- source_head；
- target_binding_sha256；
- ssh_host_key_sha256；
- plan_sha256；
- state=STARTED；
- replay_allowed=false；
- created_at。

### 3.2 accept

只有 post-reboot acceptance 全部 PASS 后允许 marker accept。

要求 exact current STARTED binding 一致，然后 atomic replace 为：

~~~text
state=ACCEPTED
acceptance_sha256=<hash>
accepted_at=<time>
T1_PRODUCTION_READY=true
~~~

### 3.3 no recovery command

首版不存在：

~~~text
resume
repair
clear
reset
force
reopen
~~~

若 marker 已存在且不是当前正常 run 可接受状态，production entrypoint STOP，并提示重装 Armbian。

## 4. Mac production orchestrator

新增或重写为：

~~~text
tools/n3w_t1_production_v2.py
~~~

固定流程：

1. verify exact release locally；
2. establish managed SSH epoch #1；
3. verify trusted host key；
4. run fresh qualification；
5. build one production plan；
6. display one approval summary；
7. operator enters one production approval；
8. target marker start；
9. HOST_BASELINE；
10. F3 product deploy；
11. Provision；
12. F4 activate/persist/cert；
13. controlled reboot；
14. close pre-reboot epoch；
15. wait SSH；
16. establish epoch #2；
17. run independent post-reboot acceptance；
18. target marker accept；
19. close SSH；
20. emit final public/private results。

没有自动 retry mutation。

## 5. Reuse of existing primitives

### HOST_BASELINE

保留 exact package/environment 安装能力。

V2 入口前 fresh qualification 已要求 Docker absent，因此 HOST_BASELINE 不需要处理任意历史 Docker 状态。

成功后必须验证：

- exact docker.io version；
- exact docker-compose-v2 version；
- Docker active；
- storage contract。

### F3

保留 exact payload/image/staging/atomic transfer 能力。

V2 应把“V1 phase-context authorization”替换为一个简单的 V2 run-context binding：

~~~text
run_id
release_id
source_head
target_binding_sha256
production_marker_sha256
stage=F3
~~~

业务部署逻辑不重写。

### Provision

继续执行一次性的 per-device product initialization。

必须确保重复调用在同一个 V2 run 中不会发生；orchestrator 只调用一次，目标 marker + product state 提供 fail-closed 防护。

### F4

保留：

- prepare；
- activate；
- runtime acceptance；
- persistence；
- certificate audit/timer；
- reboot actuation；
- post-reboot verification。

删除/旁路仅为 V1 per-phase authority 服务的 parent claim/recovery glue；不改变已经验证过的 Broker/Manager/HA 行为。

## 6. Post-reboot acceptance implementation

新增：

~~~text
tools/n3w_t1_post_reboot_acceptance.py
~~~

它与部署函数分离，避免“自己部署、自己宣布成功”。

输入：

- approved release；
- run ID；
- target binding；
- pre-reboot boot identity；
- expected service/image/certificate contract。

输出：

~~~text
POST_REBOOT_ACCEPTANCE=PASS|FAIL
T1_PRODUCTION_READY=true|false
~~~

### 6.1 target-local read-only checks

- new boot identity；
- systemd unit enabled/active；
- Docker exact images/containers；
- restart count；
- mounted persistent data；
- certificate identity；
- timer/service state；
- release marker/source binding。

### 6.2 Mac external checks

至少：

- TCP 8883 reachable；
- TLS handshake + CA + hostname/SNI；
- Manager MQTT authenticated connection；
- Home Assistant MQTT authenticated connection；
- invalid credential rejection；
- Home Assistant HTTP readiness。

有条件时复用现有 F4 runtime acceptance，而不是复制逻辑。

### 6.3 observation

90 秒观察，采样关键 process/container/systemd state。

任何关键 restart/failure：

~~~text
ACCEPTANCE=FAIL
~~~

## 7. Result contract

V2 只公开稳定、少量字段。

私有 evidence root 保存详细 probe 输出；public record 只允许 hash/boolean/status。

最终：

~~~text
PASS requires:
  qualification PASS
  marker STARTED
  all deployment stages PASS
  real reboot proven
  post-reboot acceptance PASS
  marker ACCEPTED
  session closed
~~~

部署成功但 session cleanup 失败时：

- T1 device acceptance 可以保留 PASS；
- overall production process FAIL；
- 不把设备状态伪造成未部署。

## 8. Error handling

V2 error policy 不需要穷举所有错误文本。

错误只映射到四类：

~~~text
PRE_MUTATION_FAIL
MUTATION_FAIL_REFLASH_REQUIRED
POST_REBOOT_ACCEPTANCE_FAIL_REFLASH_REQUIRED
PROCESS_CLEANUP_FAIL
~~~

UNKNOWN 只影响证据精度，不改变 target policy：

- mutation 已开始或无法证明未开始 -> reflash required；
- 不自动 replay。

## 9. Source migration strategy

为了降低一次性重写风险，建议三步：

### R1 — add new V2 surfaces

新增 qualification / marker / acceptance / orchestrator skeleton 与 unit tests。
旧 V1 文件保留但 V2 不调用。

### R2 — adapt business primitive boundaries

让 HOST_BASELINE/F3/Provision/F4 接受 V2 run-context，并证明业务行为与旧 accepted implementation 等价。

### R3 — isolated end-to-end

用隔离 Linux target 运行：

~~~text
fresh qualification
-> marker
-> host baseline
-> deploy
-> provision
-> activate
-> simulated reboot boundary
-> acceptance
~~~

CI closure 后再构建 exact V2 release。

## 10. Test matrix

最低必须覆盖：

- exact fresh host PASS；
- wrong OS/arch FAIL；
- firstboot 未完成 FAIL；
- sudo/network/DNS/NTP/storage FAIL；
- Docker already installed FAIL；
- 任意 product residue FAIL；
- marker duplicate start FAIL；
- marker crash-before/after-fsync；
- same run replay FAIL；
- different release/target binding FAIL；
- HOST_BASELINE failure => no later phase；
- F3/Provision/F4 failure => no later phase；
- SSH unexpected loss after marker => fail/no replay；
- reboot command not proven => acceptance FAIL；
- boot ID unchanged => acceptance FAIL；
- exact image drift => acceptance FAIL；
- service restart loop => acceptance FAIL；
- TLS/auth/HA readiness failure => acceptance FAIL；
- accept marker only after all checks；
- public evidence secret scan；
- Ctrl-C/session cleanup；
- same exact release on two isolated clean targets。

## 11. Files expected to change

Candidate implementation set:

~~~text
ADD
tools/n3w_t1_fresh_armbian_qualification.py
tools/n3w_t1_production_marker.py
tools/n3w_t1_production_v2.py
tools/n3w_t1_post_reboot_acceptance.py

ADD TESTS
tests/tools/test_n3w_t1_fresh_armbian_qualification.py
tests/tools/test_n3w_t1_production_marker.py
tests/tools/test_n3w_t1_production_v2.py
tests/tools/test_n3w_t1_post_reboot_acceptance.py

ADAPT
tools/n3w_t1_fresh_host_baseline.py
tools/n3w_t1_fresh_product_staging_host.py
tools/n3w_t1_device_provisioning_host.py
tools/n3w_t1_f4_activation_host.py
tools/n3w_t1_f4_reboot_authority.py
tools/n3w_t1_f4_reboot_verify.py
release builder / CI workflows
~~~

Do not delete V1 tools in the first source PR.

## 12. Source review questions

在写产品代码之前，必须再确认：

1. Standard Fresh Armbian 的 exact image/OS/board contract 是否与实际官方镜像一致；
2. Docker absent 是否符合真实 fresh image；
3. product residue allowlist 是否足够小且确定；
4. marker 是否必须在 HOST_BASELINE 前写入；
5. F3/F4 中哪些 authorization glue 可以删除而不改业务语义；
6. post-reboot acceptance 是否完全覆盖“可投入使用”；
7. 90 秒观察窗口是否足够；
8. target reflash 后 Mac production ledger 如何标记历史 run closed，不阻止新 OS identity 的新 run。

## 13. Current boundary

~~~text
SOURCE_DESIGN=FROZEN_CANDIDATE
PRODUCT_SOURCE_IMPLEMENTATION=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false

NEXT_ONE_GATE=N3W_T1_F5_PRODUCTION_PROCESS_V2_SOURCE_DESIGN_REVIEW_20261019_01
AUTO_EXECUTE_SOURCE_IMPLEMENTATION=false
STOP=true
~~~
