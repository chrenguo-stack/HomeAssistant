# N3-W T1 显式 Provisioning 与 Boot 解耦源码修复设计（2026-10-13）

TASK=
`N3W_T1_EXPLICIT_DEVICE_PROVISIONING_COMMAND_AND_BOOT_DECOUPLING_SOURCE_REPAIR_DESIGN`

## 0. Gate 状态

~~~text
SOURCE_REPAIR_DESIGN=PASS
PRODUCT_SOURCE_MUTATION=false
T1_ACCESS=false
T1_MUTATION=false
R3_CLEANUP=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
AUTHORIZATION_08_GRANTED=false
~~~

Exact product source authority:

~~~text
PRODUCT_SOURCE_HEAD=3dbd9723063e1f5f14605b1bcf13bee4c54c84ab
~~~

PR #541 当前比该 source head 只增加 docs/ADR，没有产品源码漂移。

## 1. 当前源码真实情况

### 1.1 durable transaction 已有基础

当前：

~~~text
host/greenhouse-manager/src/greenhouse_manager/bootstrap/device_firstboot.py
~~~

已经拥有：

- private transaction root / record ownership 检查；
- atomic + fsync record；
- release binding；
- host binding；
- candidate binding；
- SYSTEM_ID SHA binding；
- durable stage；
- marker-last；
- active transaction resume 所需阶段信息。

但是当前单一入口：

~~~text
run_device_firstboot()
~~~

同时承担：

~~~text
if transaction absent:
    create transaction
    start new initialization

if transaction exists:
    resume

if completion exists:
    return already_complete
~~~

因此“开始一个全新 transaction”和“恢复旧 transaction”尚未在 API 层分权。

### 1.2 completed fast-path 仍缺 live-host verify

当前 `_complete_report()` 只证明：

~~~text
transaction.json
↔ FIRSTBOOT_COMPLETE.json
~~~

互相一致。

`run_device_firstboot()` 在 complete 存在时会直接返回，
还没有调用 current live OS/host identity read-only verifier。

该问题就是前一轮 A4 remaining blocker，必须吸收到新的 DEVICE_READY verify-only 路径。

### 1.3 当前 greenhouse-init 不能直接充当产品 provisioning CLI

当前：

~~~text
greenhouse-init
→ greenhouse_manager.bootstrap.cli:main
~~~

只管理 ADR-0004 `system_init`：

~~~text
initialize SYSTEM_ID / MANAGER_ID / SYSTEM_ROOT_KEY / system CA
verify system identity
~~~

它不拥有：

- Broker CA/TLS；
- service credential；
- DynSec；
- Manager/N3W empty state；
- instance runtime staging/commit；
- clone/release evidence；
- product activation。

因此不得把 `greenhouse-init` 直接扩成量产总入口。
它继续作为低层 identity constructor。

### 1.4 Host 上已有可复用 adapter 逻辑

`tools/n3w_t1_fresh_product_bootstrap.py` 已经实现：

- exact Manager image container invocation；
- create_identity；
- create_state；
- create_broker；
- initialize_dynsec；
- stage_instance_runtime；
- commit_instance_candidate；
- instance_stopped_postcheck。

这些逻辑可以抽取/复用到新的 host provisioning adapter，
不需要重新实现 cryptographic / DynSec constructor。

### 1.5 当前 activation 资产不能直接进入 UNPROVISIONED 自动启动

现有：

~~~text
n3wfc4-broker-activation.service
n3wfc4-services-activation.service
~~~

均有：

~~~text
WantedBy=docker.service
Restart=always
~~~

当前 NetworkManager dispatcher 还会：

~~~text
network event
→ reload guard
→ systemctl start n3wfc4-broker-activation.service
~~~

而 `install-systemd-persistence.sh` 当前会 enable：

~~~text
guard
broker activation
services activation
certificate timer
~~~

这组行为属于已经运行的现有生产拓扑，
但**不能原样成为黄金镜像 UNPROVISIONED 的 boot 行为**。

幸运的是当前 R8 fresh staging 并没有把 activation units/dispatcher 安装到 active final path，
因此 source repair 不需要破坏现有 R8 runtime contract；未来 golden-master install/activation
必须分层。

## 2. Source ownership 重新冻结

### 2.1 Pure provisioning contract

继续位于 bootstrap 层，禁止 socket/subprocess/docker import。

推荐先保留现有文件名以减小 delta：

~~~text
host/greenhouse-manager/src/greenhouse_manager/bootstrap/device_firstboot.py
~~~

但新增明确 API：

~~~text
inspect_device_provisioning()
start_device_provisioning()
resume_device_provisioning()
verify_device_ready()
~~~

并把 `run_device_firstboot()` 降为 transitional compatibility wrapper，
不作为正式 product entrypoint。

后续是否 rename 到 `device_provisioning.py` 单独处理，不与本轮 correctness repair 混做。

### 2.2 Host provisioning CLI / adapters

新增：

~~~text
tools/n3w_t1_device_provision.py
~~~

未来安装为概念命令：

~~~text
/usr/local/sbin/n3w-t1-provision
~~~

负责：

- CLI confirmation；
- clone/release evidence；
- host filesystem adapter；
- exact preloaded Manager image invocation；
- start/resume/status/verify 路由；
- public-safe JSON result；
- 不启动生产服务。

### 2.3 Resume systemd helper

新增定义：

~~~text
infra/n3w-t1/systemd/n3wfc4-provision-resume.service
~~~

其 contract 只能：

~~~text
resume-if-initializing
verify-if-device-ready
do-nothing-if-unprovisioned
~~~

禁止：

~~~text
start-new-provisioning-on-boot
~~~

### 2.4 Activation eligibility

本轮 source design 明确需要独立 gate，但建议放在 provisioning core repair 后的同一 source package
末端或紧邻 successor patch：

~~~text
tools/n3w_t1_product_activation_gate.py
~~~

它至少区分：

~~~text
UNPROVISIONED -> DENY
INITIALIZING -> DENY
DEVICE_READY without FACTORY_ACCEPTED -> DENY
FACTORY_ACCEPTED + exact binding -> ELIGIBLE
~~~

golden-master 不得把现有 activation units/dispatcher 作为自动 active boot chain 安装。

## 3. Pure API 精确语义

### 3.1 inspect_device_provisioning()

必须完全只读。

输入：

~~~text
transaction_root
candidate_root
release_id
read-only host verifier
~~~

输出状态之一：

~~~text
UNPROVISIONED
INITIALIZING
DEVICE_READY
CONFLICT
~~~

硬要求：

~~~text
transaction root absent
→ return UNPROVISIONED
→ DO NOT mkdir

transaction absent
→ DO NOT create transaction.json

completion absent
→ DO NOT create any marker
~~~

这是当前 `_private_root()` 自动 mkdir 行为不能直接用于 status 的原因。

### 3.2 start_device_provisioning()

只有该 API 能：

~~~text
no transaction
→ atomically create initial transaction
~~~

调用前必须已由 host CLI 验证 exact confirmation。

Pure contract 再次验证：

~~~text
no completion
no existing transaction
release exact
clone evidence accepted by adapter
production activation denied/stopped
~~~

然后：

~~~text
create transaction exactly once
→ INITIALIZING
→ execute provisioning engine
~~~

重复 start：

~~~text
transaction exists
→ MUST NOT create second transaction
→ return explicit ALREADY_INITIALIZING / fail-closed

DEVICE_READY exists
→ MUST NOT regenerate
→ return ALREADY_PROVISIONED / fail-closed
~~~

### 3.3 resume_device_provisioning()

硬要求：

~~~text
existing valid transaction required
completion absent
stage in resumable INITIALIZING set
~~~

绝对禁止：

~~~text
transaction absent
→ create one
~~~

这是 boot-time helper 唯一可以调用的 mutation API。

### 3.4 verify_device_ready()

完全 verify-only。

要求：

~~~text
valid completion marker
valid transaction
current live host verifier PASS

current_host_instance_id
==
transaction.host_instance_id
==
completion.host_instance_id
~~~

如果 completed disk 被放到另一 host：

~~~text
FAIL_CLOSED
~~~

不得调用 ensure/generate OS identity。

## 4. Adapter Protocol 调整

当前：

~~~text
ensure_os_identity()
~~~

同时有“保证存在/可能生成”的语义。

source repair 建议拆为：

~~~text
ensure_os_identity()
verify_os_identity()
~~~

其中：

`ensure_os_identity()`：
- 仅 start/resume transaction 可调用；
- 是否真实生成 machine-id/SSH 等仍由后续 target-Armbian Gate 冻结。

`verify_os_identity()`：
- read-only；
- status / DEVICE_READY verify 可调用；
- 不写 machine-id；
- 不写 SSH keys；
- 不启动网络/生产服务；
- 返回 stable host_instance_id。

在真实 Armbian adapter 尚未实现前，host-only fake adapter 足以关闭 pure source semantics；
不得因此宣称 OS identity live acceptance PASS。

## 5. Engine 内部重构

当前 `run_device_firstboot()` 的主体可拆成内部：

~~~text
_run_provisioning_transaction(
    existing_transaction_required=...
)
~~~

或等价 private helper。

推荐调用关系：

~~~text
start_device_provisioning
    → _create_transaction_once
    → _run_existing_transaction

resume_device_provisioning
    → _require_existing_transaction
    → _run_existing_transaction

verify_device_ready
    → _require_complete
    → verify_os_identity
    → compare bindings

inspect_device_provisioning
    → metadata only
~~~

不要使用一个容易误传的布尔参数：

~~~text
allow_create_transaction=True/False
~~~

作为 product authority；独立函数更容易做 CI 和静态审计。

## 6. CLI contract

`tools/n3w_t1_device_provision.py` 最小命令：

~~~text
n3w-t1-provision status

n3w-t1-provision start   --confirm "START DEVICE PROVISIONING: YES"
~~~

内部/维护命令可有：

~~~text
resume-if-needed
verify
~~~

但面向正常操作者不需要提供“resume start over”。

### start confirmation

必须 exact match：

~~~text
START DEVICE PROVISIONING: YES
~~~

错误/缺失 confirmation 在任何 mutation 前 STOP。

confirmation 不是 durable authority 本身；
durable authority 是 start 成功创建的 transaction。

## 7. Clone/release evidence interface

不要在本轮把工厂工装实现写死进 pure bootstrap。

定义 adapter report：

~~~text
verify_clone_release_evidence()
→ status=PASS
→ release_id
→ golden_image_sha256
→ clone_readback_verified=true
→ evidence_id/public-safe digest
→ secret_values_included=false
~~~

start 必须要求该 report 与当前 release 一致。

实际 evidence 来源可以以后是：

- 外部工厂数据库；
- offline writer output；
- 设备内 readback marker；
- 受控 production manifest。

source contract 不允许“文件存在就算 PASS”。

## 8. Host adapter 复用映射

从 `LiveFreshInstallerAdapters` 复用/抽取：

| 当前函数 | Provisioning 目标 |
| --- | --- |
| `_manager_json` | KEEP/EXTRACT host adapter helper |
| `create_identity` | REUSE |
| `create_state` | REUSE |
| `create_broker` | REUSE |
| `initialize_dynsec` | REUSE |
| `stage_instance_runtime` | REUSE |
| `commit_instance_candidate` | REUSE |
| `instance_stopped_postcheck` | REUSE |
| `load_images` | NOT provisioning；master-build only |
| `stage_public_runtime` | NOT provisioning；master-build only |
| `commit_public_candidate` | NOT provisioning；master-build only |

目标不是把整个 `n3w_t1_fresh_product_bootstrap.py` import 进产品 CLI，
而是把可复用 instance adapter 抽到单一 source authority，
避免 R8 和 provisioning 两份逻辑漂移。

建议新增：

~~~text
tools/n3w_t1_instance_provisioning_adapters.py
~~~

或将 adapter 放入明确的 host-side module。

R8 legacy wrapper 继续调用同一 adapter，保持回归兼容。

## 9. Activation / systemd source boundary

### 9.1 当前现有生产 runtime 保持

现有：

~~~text
n3wfc4-broker-activation.service
n3wfc4-services-activation.service
NetworkManager dispatcher
install-systemd-persistence.sh
~~~

已经有 KF-097 等 live acceptance，不在本轮直接大改其当前部署语义。

### 9.2 Golden image install 必须采用新路径

未来 golden-master public install 只允许 active-enable：

~~~text
safe host baseline
provision-resume helper
必要的 fail-closed guard
~~~

不得 enable：

~~~text
broker activation
services activation
certificate runtime activation
network dispatcher that auto-starts broker
~~~

直到 FACTORY_ACCEPTED + explicit activation。

### 9.3 Source guard tests

即使 activation unit 定义作为公共文件存在，也必须有 CI 证明 golden-master install path：

~~~text
UNPROVISIONED boot
→ broker activation not started
→ manager not started
→ HA not started

network event while UNPROVISIONED
→ never starts Broker
~~~

因此后续 master-build/activation source package必须重新审视当前 dispatcher 的
`systemctl start n3wfc4-broker-activation.service`。

## 10. Exact file delta — 第一轮 source repair 建议

### MODIFY

~~~text
host/greenhouse-manager/src/greenhouse_manager/bootstrap/device_firstboot.py
host/greenhouse-manager/tests/bootstrap/test_device_firstboot.py
host/greenhouse-manager/pyproject.toml
.github/workflows/h0h1-init-portable-restore-ci.yml
~~~

### ADD

~~~text
host/greenhouse-manager/src/greenhouse_manager/bootstrap/device_provisioning_cli.py
host/greenhouse-manager/tests/bootstrap/test_device_provisioning_cli.py

tools/n3w_t1_device_provision.py
tests/tools/test_n3w_t1_device_provision.py
~~~

### CONDITIONAL ADD / next hunk

~~~text
infra/n3w-t1/systemd/n3wfc4-provision-resume.service
tests/tools/test_n3w_t1_provision_resume_unit.py
~~~

### DO NOT MODIFY in first focused hunk

~~~text
system_init.py
fresh_product_state.py
fresh_broker.py
portable_restore.py
firmware
pairing/N3-W radio
R8 staging_host
R8 _08 authorization ledger
current Broker activation units
current dispatcher
current persistence installer
~~~

先把 start/resume/status/verify source authority做正确，再独立接 host/systemd activation。

## 11. Test matrix

### Plain boot / status

~~~text
no transaction + no completion
status = UNPROVISIONED
transaction_root not created
transaction.json not created
identity constructor calls = 0
production service calls = 0
~~~

### Explicit start

~~~text
wrong confirmation
→ no mutation

correct confirmation
→ transaction created exactly once
→ INITIALIZING
→ provisioning executes same boot
→ DEVICE_READY
→ production_service_start=false
~~~

### Duplicate start

~~~text
INITIALIZING
→ no second transaction
→ no new identity generation

DEVICE_READY
→ no new transaction
→ no identity regeneration
~~~

### Resume

~~~text
existing transaction required
transaction absent
→ resume fails/no-op
→ must not create transaction

power-loss stage matrix
→ restart via resume
→ completed components reused
~~~

### DEVICE_READY verify

~~~text
host A complete
current host A
→ PASS

copied complete state
current host B
→ FAIL_CLOSED

verify path
→ ensure_os_identity not called
→ create_identity not called
~~~

### Activation separation

~~~text
provisioning PASS
→ Broker/Manager/HA not started
→ activation_eligible=false until FACTORY_ACCEPTED
~~~

### Legacy regression

继续要求：

~~~text
R8 fresh installer tests PASS
H0/H1 bootstrap/restore PASS
F5 storage contract PASS
exact ARM64 payload PASS
public safety PASS
~~~

## 12. CI strategy

现有 `H0 H1 initialization and portable restore CI` 已经：

- compile bootstrap；
- ruff bootstrap；
- pytest bootstrap；
- 禁止 bootstrap import socket/subprocess；
- 禁止 bootstrap 直接执行 Docker。

新 pure provisioning contract 必须继续满足该边界。

新增 host tool 后：

`N3W T1 fresh bootstrap deployable payload CI` 不应立刻把 provisioning 当成 R8 live apply；
建议增加独立 workflow：

~~~text
N3W T1 explicit provisioning source CI
~~~

覆盖：

- pure contract；
- CLI confirmation；
- host adapter fake；
- start/resume separation；
- completed host drift；
- no production activation；
- no secret stdout。

后续 systemd/activation package 再接：

~~~text
N3W Broker ingress guard CI
golden-master source CI
~~~

## 13. 对当前 R1 blocker 的处置

~~~text
A1 legacy commit compatibility=CLOSED
A2 durable record ownership=CLOSED
A3 atomic write=CLOSED

A4 completed live host binding
→ absorbed into verify_device_ready()
→ SOURCE_REPAIR_REQUIRED
~~~

新的上游架构问题不是“再加一个 firstboot 开关”，而是：

~~~text
START_AUTHORITY
!=
RESUME_AUTHORITY
!=
VERIFY_AUTHORITY
~~~

这是下一轮 source repair 的中心。

## 14. Source repair 分两步

### P1 — pure authority split

目标：

~~~text
inspect/start/resume/verify four APIs
explicit confirmation CLI
completed live host binding
no boot auto-start semantics
legacy R8 regression
~~~

不安装真实 systemd，不碰 T1。

### P2 — host resume + activation guard

P1 独立 review PASS 后：

~~~text
host n3w-t1-provision wrapper
resume unit
golden-master install policy
activation eligibility gate
network-event no-auto-start guard
~~~

仍先 host-only/CI，再进入 T1 live gate。

这样避免一次同时改 transaction core 和 KF-097 已验证的生产 activation topology。

## 15. STOP

~~~text
SOURCE_REPAIR_DESIGN=PASS
PRODUCT_SOURCE_MUTATION=false
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
~~~

推荐下一门：

~~~text
NEXT_ONE_GATE=
N3W_T1_EXPLICIT_DEVICE_PROVISIONING_COMMAND_AUTHORITY_SPLIT_SOURCE_REPAIR_P1

SCOPE=
inspect/start/resume/verify pure authority split
explicit command confirmation contract
completed live-host verify
focused host-only tests
legacy R8 regressions

SYSTEMD_INSTALL=false
ACTIVATION_TOPOLOGY_MUTATION=false
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~

P1 source + CI 完成后 STOP，先做独立 source review，再进入 P2。
