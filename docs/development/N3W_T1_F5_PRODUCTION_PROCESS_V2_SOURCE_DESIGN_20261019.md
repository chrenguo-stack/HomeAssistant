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

建议正常量产源码收敛为五个清晰责任面：

~~~text
Mac:
  n3w_t1_production_v2.py
  n3w_t1_fresh_armbian_qualification.py
  n3w_t1_post_reboot_acceptance.py
  n3w_t1_failure_forensics.py

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
  "status": "PASS|FAIL|STOP",
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

不输出 UNKNOWN ownership 分类。

- `PASS`：全部关键事实已证明满足 Standard Fresh Armbian；
- `FAIL`：已经证明 target 不符合 fresh contract，输出 `reflash_required=true`；
- `STOP`：SSH/网络/只读命令等原因导致证据不足，输出 `reflash_required=false`，允许修复工位/连接后重新执行只读 qualification。

release 必须先在 Mac 本地验证，再把 release 中冻结的 OS/package/capacity 条件传入 qualification。

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

HOST_BASELINE 的安装输入必须来自 exact release，而不是现场动态选择最新 APT candidate。

建议接口：

~~~text
n3w_t1_fresh_host_baseline.py
  --phase install
  --approved-release <path>
~~~

执行规则：

- 从 release 读取 docker.io / docker-compose-v2 的 exact package version 和 source policy；
- apt-cache candidate 必须与 release version 完全一致；
- 不一致或 exact version 不可取得时，在 apt-get install 前 STOP；
- apt-get install 使用明确的 package=version；
- 安装后再次验证 dpkg version、Docker server version、Compose version、Docker active 和 storage contract。

### F3

保留 exact payload/image/staging/atomic transfer 能力。

当前 main 的 F3 payload 把固定 AUTHORIZATION_ID 写入 immutable payload manifest；该字符串不能继续作为 V2 的生产授权。

V2 必须把“immutable package identity”和“本次 run authority”分离：

~~~text
IMMUTABLE F3 PAYLOAD:
  source_head
  payload/image/file hashes
  transport/capacity contract
  NO dynamic run authorization

EXTERNAL V2 RUN CONTEXT:
  run_id
  release_id
  release_sha256
  source_head
  target_binding_sha256
  production_marker_sha256
  action=F3_DEPLOY
~~~

run context 必须放在 immutable payload root 之外，并由 F3 apply 在第一次产品 mutation 前验证当前 V2 STARTED marker。
固定历史 AUTHORIZATION_ID 可以删除或降级为非安全语义的 action label，不能单独使 apply 合法。

为了防止同一 STARTED run 内误调用两次 F3，允许保留一个很小的 one-shot F3 action claim。
它只证明 F3 action 已领取，不提供 recovery/resume 状态机；失败后整机按 V2 policy 进入 forensic + reflash。业务部署逻辑不重写。

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
- post-reboot verification；
- 现有 transaction / atomic claim / no-replay / rollback guard。

V2 首版不要为了“只有一次人工批准”去删除这些已实机验证的内部安全守卫。

正确模型是：

~~~text
ONE HUMAN PRODUCTION APPROVAL
-> V2 orchestrator
-> deterministic internal action IDs derived from run_id + action
-> existing F4 one-shot guards
~~~

操作员不再逐项批准，但 target 仍保留内部一次性防重放。所有 repair-* 命令继续从 normal path 隔离。

只有确实属于未合并 V1 top-level per-phase authority 的 wrapper 才不进入 V2；不要把 main 中已经关闭验收的 F4 transaction guard 当成 V1 冗余删除。

## 6. Post-reboot acceptance implementation

新增：

~~~text
tools/n3w_t1_post_reboot_acceptance.py
~~~

它与部署函数分离，避免“自己部署、自己宣布成功”。

实现上优先包装现有 n3w_t1_f4_reboot_verify.py，而不是复制已有 target-local 验收逻辑。现有 verifier 已覆盖真实 reboot、F4 transaction、systemd persistence、exact runtime images、TLS、Manager、Home Assistant MQTT、负向认证、certificate lifecycle 等关键合同。

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

第一层直接调用/复用现有 F4 reboot verifier。

V2 额外只补：

- V2 STARTED marker 与 run/release/target binding；
- approved release/source head 与 installed product release 的一致性；
- V2 acceptance 所需但现有 F4 verifier 尚未输出的公开摘要；
- marker 必须在所有验收 PASS 后才允许切换 ACCEPTED。

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

任何 run STARTED 且尚未 durable ACCEPTED 的 FAIL/UNKNOWN 必须进入统一 failure-finalization 路径：

~~~text
FAIL
-> FREEZE_EVIDENCE
-> FORENSIC_SNAPSHOT_COMPLETE
-> SESSION_CLOSE
-> TARGET_MARKED_REFLASH_REQUIRED
-> REFLASH_ALLOWED
~~~

如果 target 已经 durable ACCEPTED，而之后只发生 Mac session cleanup/public-result/archive 失败，则保留 DEVICE_ACCEPTANCE=PASS、T1_PRODUCTION_READY=true，overall process 记 FAIL，但不得标记 REFLASH_REQUIRED。

## 9. Failure forensic implementation

新增：

~~~text
tools/n3w_t1_failure_forensics.py
~~~

该模块只做只读取证与证据封装，不做恢复、删除、重启、服务启动或任何 target mutation。

### 9.1 freeze first

orchestrator 捕获失败后必须先把当前内存中的 run/release/target/stage/error/last-success 状态原子写入 Mac 私有 evidence root。
从这一刻起，后续 cleanup 失败也不得覆盖原始失败事实。

### 9.2 bounded read-only snapshot

若当前 managed SSH epoch 仍可用，则在同一个 epoch 内采集：

- production marker 及 hash；
- boot identity；
- Docker container/image/restart 摘要；
- 关键 systemd unit 状态；
- 关键 listener/process 摘要；
- 与 failed_stage 直接相关的有限日志尾部；
- release/product manifest/hash binding。

如果某项因目标断线、命令不可用或权限问题无法读取，记录 UNAVAILABLE + reason。snapshot completion 不要求伪造每个 probe 成功。

### 9.3 evidence manifest

固定生成：

~~~text
failure-summary.json
forensic-snapshot.json
evidence-manifest.json
~~~

manifest 绑定每个 evidence file 的 size/SHA-256，并计算 bundle SHA-256。

FORENSIC_SNAPSHOT_COMPLETE=true 的含义是：取证程序已经终止并生成完整 manifest，所有成功/失败/UNAVAILABLE 项均已明确记录。

### 9.4 session close before reflash disposition

取证 manifest 完成后，orchestrator 必须关闭或确认 managed SSH epoch 已不存在，并清理本 run 的 ControlMaster/socket/private temp resources。

只有 session cleanup 达到可证明终态后，Mac production ledger 才写：

~~~text
TARGET_DISPOSITION=REFLASH_REQUIRED
REFLASH_ALLOWED=true
~~~

session cleanup 的可证明终态包括：正常关闭，或确认本 run 的 ControlMaster/socket 已经不存在。目标本身失联不能造成永久禁止重装。

该 disposition 写在 Mac 侧，不要求再修改失败 T1。T1 上 STARTED marker 留作现场证据，随后由 Armbian 重装自然擦除。

### 9.5 public evidence

公开摘要只允许包含 release/source/run hash、阶段、错误码、布尔状态、evidence bundle SHA-256、session close 结果和 REFLASH_REQUIRED。
原始地址、密码、私钥、MQTT 明文凭据、完整日志和 unrestricted stdout/stderr 只留 Mac 私有 evidence root。

## 10. Source migration strategy

为了降低一次性重写风险，建议三步：

### R1 — add new V2 surfaces

新增 qualification / marker / acceptance / orchestrator skeleton 与 unit tests。
旧 V1 文件保留但 V2 不调用。

### R2 — adapt business primitive boundaries

- HOST_BASELINE 接受 release-bound exact package versions；
- F3 接受 payload 外部 V2 run-context + STARTED marker binding；
- Provision 保持单次显式 start/verify；
- F4 保留现有 transaction/no-replay/rollback guards，由 one human approval 自动派生内部 action IDs；
- 证明业务行为与旧 accepted implementation 等价。

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

## 11. Test matrix

最低必须覆盖：

- exact fresh host PASS；
- wrong OS/arch FAIL；
- firstboot 未完成 FAIL；
- sudo/network/DNS/NTP/storage FAIL；
- Docker already installed -> FAIL/reflash_required；
- 任意 product residue FAIL；
- marker duplicate start FAIL；
- marker crash-before/after-fsync；
- same run replay FAIL；
- different release/target binding FAIL；
- HOST_BASELINE failure => no later phase；
- F3/Provision/F4 failure => no later phase + forensic-before-reflash；
- SSH unexpected loss after marker => fail/no replay；
- reboot command not proven => acceptance FAIL；
- boot ID unchanged => acceptance FAIL；
- exact image drift => acceptance FAIL；
- service restart loop => acceptance FAIL；
- TLS/auth/HA readiness failure => acceptance FAIL；
- accept marker only after all checks；
- public evidence secret scan；
- failure triggers freeze-before-cleanup ordering；
- target unreachable still produces COMPLETE manifest with UNAVAILABLE probes；
- forensic collector performs no mutation；
- reflash disposition cannot be written before snapshot + session close；
- Ctrl-C/session cleanup；
- cleanup failure after durable ACCEPTED preserves device acceptance and does not require reflash；
- exact APT version unavailable stops before package mutation；
- F3 run-context stored outside immutable payload root；
- F3 static/historical authorization string alone cannot authorize apply；
- one human approval deterministically drives distinct internal F4 action IDs；
- same exact release on two isolated clean targets。

## 12. Files expected to change

Candidate implementation set:

~~~text
ADD
tools/n3w_t1_fresh_armbian_qualification.py
tools/n3w_t1_production_marker.py
tools/n3w_t1_production_v2.py
tools/n3w_t1_post_reboot_acceptance.py
tools/n3w_t1_failure_forensics.py

ADD TESTS
tests/tools/test_n3w_t1_fresh_armbian_qualification.py
tests/tools/test_n3w_t1_production_marker.py
tests/tools/test_n3w_t1_production_v2.py
tests/tools/test_n3w_t1_post_reboot_acceptance.py
tests/tools/test_n3w_t1_failure_forensics.py

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

## 13. Source review questions

在写产品代码之前，必须再确认：

1. Standard Fresh Armbian 的 exact image/OS/board contract 是否与实际官方镜像一致；
2. Docker absent 是否符合真实 fresh image；
3. product residue allowlist 是否足够小且确定；
4. marker 是否必须在 HOST_BASELINE 前写入；
5. F3 static authorization 如何降级为非 authority，并由 payload 外 V2 run-context/marker 取代；
6. F4 已有内部 transaction/no-replay guard 哪些必须原样保留；
7. post-reboot acceptance 如何最大化复用现有 F4 reboot verifier；
8. 90 秒观察窗口是否足够；
9. target reflash 后 Mac production ledger 如何标记历史 run closed，不阻止新 OS identity 的新 run；
10. forensic snapshot 的最小证据集合、UNAVAILABLE 语义和 session-close completion contract 是否足够支持源码缺陷追查；
11. durable ACCEPTED 后仅 Mac cleanup 失败时，如何完成 evidence finalization 而不误要求 reflash。

## 14. Current boundary

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
