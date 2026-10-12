# N3-W T1 黄金母盘 / Firstboot 源码拆分与修复设计（2026-10-12）

TASK=
`N3W_T1_GOLDEN_MASTER_FIRSTBOOT_SOURCE_DECOMPOSITION_AND_REPAIR_DESIGN`

## 0. Gate 状态

~~~text
SOURCE_DECOMPOSITION_DESIGN=PASS
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

本 Gate 只读取 exact product source 并冻结后续 source repair 包，不修改产品源码。

Source authority reviewed:

~~~text
PRODUCT_SOURCE_HEAD=5ed613673ec1ead29a1153d0e3916bdd3539a3fb
PR541_BRANCH=plan/n3w-t1-full-fresh-install-from-zero-20261010
ARCHITECTURE_AUTHORITY=docs/adr/0009-t1-golden-master-firstboot-production-lifecycle.md
~~~

## 1. 当前源码真实编排

当前：

`host/greenhouse-manager/src/greenhouse_manager/bootstrap/fresh_installer.py`

的 `run_fresh_staging()` 顺序精确为：

~~~text
preflight
→ before_mutation
→ load_images
→ create_identity
→ create_state
→ create_broker
→ initialize_dynsec
→ stage_runtime
→ commit_candidate
→ stopped_postcheck
~~~

任一 mutation 后失败进入 `cleanup()`。

因此当前 contract 把两类 lifecycle 放在同一事务：

~~~text
PUBLIC SOFTWARE / MASTER BUILD
  load_images
  public source / compose / unit / guard

PER-DEVICE INSTANCE
  identity
  state
  broker keys / credentials
  dynsec
  instance env / TLS
~~~

这正是 ADR-0009 要拆开的 source seam。

## 2. 当前函数级 ownership

### 2.1 `tools/n3w_t1_fresh_product_staging_host.py`

| 函数 | 当前职责 | 目标归属 |
| --- | --- | --- |
| `_artifact_metadata` / `_download_artifact` / `_verify_outer_artifact` | exact artifact transport | KEEP；master-build / single-host installer |
| `_read_payload_manifest` / `_transport_contract` | payload/transport binding | KEEP；master-build |
| `_remote_storage_probe_script` / `_remote_storage_report` | F5 actual Docker/containerd storage authority | KEEP；master-build |
| `_plan_transport` | R8 single-host install peak + fixed 5 GiB | KEEP as legacy install/master-build workspace policy；不得成为 runtime reserve |
| `_remote_prepare_payload` | SCP + full extract | KEEP initially；streaming HOLD |
| `_remote_load_images_sequentially` | sequential docker load/removal | MASTER_BUILD only if host-wrapper path retained |
| authorization ledger / claim observation | R8 bounded live apply | KEEP for R8 lineage；不得进入 product firstboot |
| `main()` preflight/apply | single-host wrapper | KEEP compatibility；later add separate master entrypoint rather than silently change semantics |

结论：该文件不应成为 clone firstboot 入口。它是 artifact/master-build transport 层。

### 2.2 `tools/n3w_t1_fresh_product_bootstrap.py`

| 函数/对象 | 当前职责 | 目标 |
| --- | --- | --- |
| `Runner` | host command adapter | REUSE |
| `_load_manifest` | exact payload integrity | REUSE in master build |
| `_preflight` | minimal host must have 0 product image/path/state | MASTER_BUILD / legacy fresh only；clone firstboot 必须使用另一 preflight |
| `_verify_runtime_image` | portable RootFS/config image binding | KEEP；master + factory audit |
| `LiveFreshInstallerAdapters.load_images` | load exact 3 images | MOVE_TO_MASTER_BUILD |
| `_manager_json` | execute exact Manager constructors in isolated container | KEEP as reusable host adapter pattern |
| `create_identity` | H0/H1 identity | MOVE_TO_FIRSTBOOT |
| `create_state` | empty Manager/N3W state | MOVE_TO_FIRSTBOOT |
| `create_broker` | Broker CA/TLS/service secrets | MOVE_TO_FIRSTBOOT |
| `initialize_dynsec` | isolated initial DynSec | MOVE_TO_FIRSTBOOT |
| `stage_runtime` | **mixed public + instance staging** | MUST_SPLIT |
| `commit_candidate` | **mixed public + instance commit** | MUST_SPLIT |
| `stopped_postcheck` | **mixed master/image + instance audit** | MUST_SPLIT |
| `cleanup` | **mixed image/public/instance rollback ownership** | MUST_SPLIT |
| `execute_apply` + `_claim_authorization` | manual R8 one-shot apply | KEEP R8 compatibility；NOT firstboot |
| `self_check` | R8 payload/source checks | KEEP and extend via separate new routes |

### 2.3 `fresh_installer.py`

当前 `FreshInstallerAdapters` Protocol 与 `run_fresh_staging()` 是完整 single-host transaction。

决策：

- **不删除、不改语义**；
- 作为 R8 / disaster-rebuild / regression compatibility path 保留；
- 不再向其中继续塞 Seal / clone / firstboot 分支；
- 新建两个较小 orchestration contract：
  - golden-master build contract；
  - per-device firstboot contract。

这样 F5 与既有 cleanup/no-replay 证据不会因为量产架构拆分而被不必要重写。

## 3. 可直接 KEEP 的底层构造器

以下模块本身不需要重新设计：

### 3.1 `bootstrap/system_init.py`

KEEP：

- `initialize_system()`
- `verify_initialization()`
- marker-last；
- partial state fail-closed；
- repeated initialization returns existing identity；
- SYSTEM_ID / MANAGER_ID / SYSTEM_ROOT_KEY / system CA separation。

它只负责产品 identity，不负责 OS machine-id / SSH host identity。

### 3.2 `bootstrap/fresh_product_state.py`

KEEP：

- `create_fresh_state()`
- `audit_fresh_state()`
- empty Manager DB；
- empty replay / relay authorization / relay-key state；
- exact SYSTEM_ID SHA binding。

### 3.3 `bootstrap/fresh_broker.py`

KEEP：

- `create_fresh_broker_materials()`
- `verify_fresh_broker_materials()`
- separate Broker transport CA；
- Broker TLS；
- 3 service credential bundle；
- `provision_fresh_service_identities()`
- `audit_fresh_dynsec_document()`。

### 3.4 ADR-0004 restore modules

KEEP：

- portable restore；
- identity conflict guard；
- new clone != restore 的语义继续由 ADR-0009 约束。

`identity_guard.py` 不是 fresh-clone host identity generator；它继续用于 restored SYSTEM_ID takeover/conflict contract。

## 4. `stage_runtime()` 精确拆分

当前 `stage_runtime()` 是最明显的 mixed ownership seam。

### 4.1 公共母盘部分：`stage_public_runtime()`

迁移这些行为：

~~~text
payload runtime-source/opt/HomeAssistant
→ /opt/HomeAssistant candidate

docker-compose.fresh.yml
→ canonical public compose template

image-lock.json

n3w-broker-ingress-guard executable

ingress guard systemd definition

future:
firstboot executable/unit
seal audit executable
factory audit executable
~~~

公共 staging 不得读取：

- SYSTEM_ID；
- service password；
- CA private key；
- DynSec；
- Manager DB。

### 4.2 每机实例部分：`stage_instance_runtime()`

迁移：

~~~text
identity/
manager/
n3w/
broker-data/dynamic-security.json
/opt/greenhouse-secrets
/etc/n3wfc4/tls
instance docker-compose.env
/var/lib/n3wfc4-homeassistant empty root
~~~

它必须显式接收已完成的 system identity，不允许隐式生成第二套身份。

### 4.3 Compose 处理

当前 Compose 文件是公共模板，但 `docker-compose.env` 是 instance material。

冻结：

~~~text
COMPOSE_TEMPLATE=MASTER_BUILD
COMPOSE_ENV=FIRSTBOOT
IMAGE_LOCK=MASTER_BUILD
INSTANCE_SECRETS=FIRSTBOOT
~~~

暂不改 Compose schema；R1 只建立边界，不同时重写 network/TLS/pairing contracts。

## 5. Final target ownership 拆分

当前：

~~~text
FINAL_DIRS:
  /var/lib/greenhouse-manager
  /var/lib/n3wfc4-broker
  /var/lib/n3wfc4-homeassistant
  /opt/greenhouse-secrets
  /opt/HomeAssistant
  /etc/n3wfc4

FINAL_FILES:
  /usr/local/sbin/n3w-broker-ingress-guard
  /etc/systemd/system/n3wfc4-broker-ingress-guard.service
~~~

冻结为：

### PUBLIC_FINAL_DIRS

~~~text
/opt/HomeAssistant
~~~

### PUBLIC_FINAL_FILES

~~~text
/usr/local/sbin/n3w-broker-ingress-guard
/etc/systemd/system/n3wfc4-broker-ingress-guard.service

future:
/usr/local/sbin/n3w-t1-firstboot
/etc/systemd/system/n3wfc4-firstboot.service
/usr/local/sbin/n3w-t1-golden-master-seal-audit
/usr/local/sbin/n3w-t1-factory-audit
~~~

### INSTANCE_FINAL_DIRS

~~~text
/var/lib/greenhouse-manager
/var/lib/n3wfc4-broker
/var/lib/n3wfc4-homeassistant
/opt/greenhouse-secrets
/etc/n3wfc4
~~~

### FIRSTBOOT_TRANSACTION_ROOT

建议新增：

~~~text
/var/lib/n3w-firstboot
~~~

候选成员：

~~~text
transaction.json
FIRSTBOOT_COMPLETE.json
FACTORY_ACCEPTED.json
~~~

exact schema/mode 在 firstboot source package 冻结；不得用 R8 authorization ledger 代替。

## 6. commit / cleanup ownership 必须拆开

当前 `commit_candidate()` 顺序逐目录 `os.rename()`，且 `created_paths` 是进程内列表。
当前 `cleanup()` 可删除：

- transaction-created final paths；
- loaded images；
- candidate containers。

这适合 R8 single transaction，但不能直接用于 clone firstboot。

### 6.1 Master commit

`commit_public_candidate()` 只拥有：

- public source；
- public tools/unit definitions；
- exact images。

失败清理只能移除**本次 master build 创建**的公共资源。

### 6.2 Firstboot commit

`commit_instance_candidate()` 只拥有：

- identity/state/broker/secrets/instance config；
- firstboot transaction-owned staging。

绝对不得因 firstboot 失败删除：

- `/opt/HomeAssistant`；
- preloaded HA/Manager/Broker images；
- sealed release manifest；
- public systemd/tool definitions。

### 6.3 Power-loss

firstboot 不使用进程内 `created_paths` 作为唯一恢复 authority。

必须以 durable transaction record 为 authority：

~~~text
PRECHECK
→ OS_IDENTITY
→ PRODUCT_IDENTITY
→ STATE
→ BROKER
→ DYNSEC
→ INSTANCE_STAGE
→ COMMIT
→ VERIFY
→ COMPLETE_MARKER
~~~

每阶段记录：

- release ID / source SHA；
- transaction schema；
- host identity binding；
- committed component digests / public-safe identities；
- next expected stage。

秘密值不写 transaction report。

## 7. postcheck 拆分

### 7.1 `master_postcheck()`

只验证：

- 3 exact images；
- image RootFS/config bindings；
- public `/opt/HomeAssistant` provenance；
- public Compose template；
- firstboot/seal/audit tools and units；
- no product listener；
- no product instance secret/state；
- no HA Owner / instance config；
- no initialized DynSec；
- master is seal-eligible。

它不能要求 `SYSTEM_ID` 存在。

### 7.2 `instance_stopped_postcheck()`

验证：

- system_init；
- empty fresh state；
- Broker material；
- service credentials；
- DynSec 3 service identities / zero node identities；
- Compose render；
- instance mounts；
- zero business rows；
- no production listener；
- firstboot complete marker。

### 7.3 `factory_postcheck()`

属于独立 factory audit：

- service readiness；
- guard-before-Broker-open；
- HA no Owner/test business data；
- reboot identity stability；
- evidence marker。

不能把 factory live service PASS 塞回 stopped firstboot postcheck。

## 8. 新 orchestration modules

为避免继续扩大 `fresh_installer.py`，新增两个小型 contract。

### 8.1 `greenhouse_manager.bootstrap.golden_master_installer`

纯 orchestration，不直接 import subprocess/socket/docker。

建议 Protocol：

~~~text
preflight_master()
load_images()
stage_public_runtime()
commit_public_candidate()
master_postcheck()
cleanup_master_candidate()
~~~

输出：

~~~text
gh.n3w.t1-golden-master-build/1
~~~

不生成 system identity。

### 8.2 `greenhouse_manager.bootstrap.device_firstboot`

纯 firstboot transaction contract，host-specific mutation 放 adapters。

建议 Adapter：

~~~text
preflight_clone()
ensure_os_identity()
create_identity()
create_state()
create_broker()
initialize_dynsec()
stage_instance_runtime()
commit_instance_candidate()
instance_stopped_postcheck()
write_complete_marker()
~~~

contract 本身管理 durable stage transition，不直接依赖人工 R8 authorization。

Schema：

~~~text
gh.n3w.t1-device-firstboot/1
~~~

## 9. Host-side executors

### 9.1 Master build executor

建议新增：

~~~text
tools/n3w_t1_golden_master_build.py
~~~

职责：

- 调用 F5 storage authority；
- exact image load/binding；
- public source stage/commit；
- master postcheck；
- 不生成 identity/secrets；
- 后续 D 类 live gate 使用独立 master-build authorization，不复用 `_08`。

现有 `n3w_t1_fresh_product_staging_host.py` 的 artifact download/storage probe 可以继续作为 host transport，
但不能通过改变 `apply` 含义把旧 R8 authorization 静默转成 master-build authorization。

### 9.2 Firstboot executor

建议新增：

~~~text
tools/n3w_t1_device_firstboot.py
~~~

该工具进入黄金母盘。

它使用预装 exact Manager image，通过 `docker run --network none` 调用现有 constructor，
从而不要求 host Python 安装 greenhouse-manager package。

它拥有：

- OS identity adapter；
- firstboot durable transaction；
- instance candidate root；
- instance-only commit/cleanup；
- stopped postcheck。

### 9.3 Seal

建议新增：

~~~text
tools/n3w_t1_golden_master_seal.py
~~~

分两个 operation：

~~~text
audit
seal
~~~

`audit` 可无 mutation；
`seal` 属 D 类受控 mutation。

Seal 必须使用 whitelist + forbidden inventory，不用“rm 几个目录”证明安全。

### 9.4 Factory audit

建议新增：

~~~text
tools/n3w_t1_factory_acceptance.py
~~~

只负责 factory evidence 与 marker，不承担用户 onboarding。

## 10. OS identity：本轮只冻结接口，不猜具体 Armbian 操作

项目源码目前没有：

- machine-id clone reset；
- SSH host-key clone reset；
- exact firstboot systemd ordering。

因此 R1 不应凭一般 Linux 经验直接写 live mutation。

先冻结接口：

~~~text
inspect_sealed_os_identity()
ensure_clone_machine_identity()
ensure_clone_ssh_host_identity()
verify_os_identity_stable()
~~~

source repair 可以使用可注入 filesystem/systemd adapters 和临时目录测试。

在真实命令进入 product source 前，需要一轮 target-Armbian exact contract review，至少确认：

- `/etc/machine-id` 与可能的 D-Bus machine-id；
- ssh unit exact name/order；
- host-key generation behavior；
- NetworkManager/DHCP persistent identity；
- hostname 是否为产品唯一 authority；
- firstboot 与 SSH/network exposure 的 ordering。

该 review 可以通过目标 Armbian image 或只读 T1 证据完成；本 Gate 不访问 T1。

## 11. Activation units 的处理

当前仓库已有：

- `n3wfc4-broker-ingress-guard.service`
- `n3wfc4-broker-activation.service`
- `n3wfc4-services-activation.service`

保留其基本顺序：

~~~text
guard
→ broker
→ authenticated readiness
→ manager + HA
~~~

但新增 firstboot 后必须最终形成：

~~~text
firstboot complete / device-ready
→ factory acceptance / explicit activation permission
→ guard
→ broker
→ service readiness
→ manager + HA
~~~

R1 不修改现有 activation unit；只添加 contract tests，防止未来业务 unit 绕过 firstboot/factory gate。

exact systemd dependency 在后续 unit source package 冻结。

## 12. R1：最小结构拆分 repair（推荐下一门）

第一轮 source repair **不直接实现完整量产 firstboot**。

目标只有：

1. 在 `LiveFreshInstallerAdapters` 内把：
   - public stage；
   - instance stage；
   - public commit；
   - instance commit；
   - master audit；
   - instance audit；
   - public cleanup ownership；
   - instance cleanup ownership
   分开；
2. 保持现有 `stage_runtime()/commit_candidate()/stopped_postcheck()/cleanup()` wrapper 行为兼容，
   让 R8 existing tests 继续 PASS；
3. 新增 pure `golden_master_installer.py` 和 `device_firstboot.py` contract skeleton；
4. 暂不接真实 machine-id / SSH mutation；
5. 暂不改变 current R8 payload/apply；
6. 暂不增加 live T1 action。

这样先证明“能拆开但没有破坏旧单机安装工具”。

### R1 exact expected files

MODIFY：

~~~text
tools/n3w_t1_fresh_product_bootstrap.py
host/greenhouse-manager/src/greenhouse_manager/bootstrap/fresh_installer.py   # only shared validation helper if needed; run_fresh_staging semantics unchanged
tests/tools/test_n3w_t1_fresh_product_bootstrap.py
.github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml           # only add decomposition regression if needed
~~~

ADD：

~~~text
host/greenhouse-manager/src/greenhouse_manager/bootstrap/golden_master_installer.py
host/greenhouse-manager/src/greenhouse_manager/bootstrap/device_firstboot.py
host/greenhouse-manager/tests/bootstrap/test_golden_master_installer.py
host/greenhouse-manager/tests/bootstrap/test_device_firstboot.py
~~~

R1 不添加 production systemd unit，不添加 host firstboot executable。

## 13. R1 CI matrix

### Existing regressions that must remain PASS

1. current R8 source contract suite；
2. F5 direct external containerd root generated probe；
3. non-empty imports fail-closed；
4. exact Docker archive RootFS/config binding；
5. authorization claim/no-replay；
6. cleanup rollback；
7. stopped postcheck owner split；
8. H0/H1 `test_h0h1_bootstrap.py`；
9. current clean deployment gate；
10. public safety / no secret output。

### New decomposition tests

MASTER:

~~~text
master contract never calls create_identity
master contract never calls create_state
master contract never calls create_broker
master contract never calls initialize_dynsec
master public targets exclude all INSTANCE_FINAL_DIRS
master rollback never removes pre-existing instance resources
master audit requires exact images/public files
master audit requires instance identity/secrets absent
~~~

FIRSTBOOT:

~~~text
firstboot contract never calls load_images
firstboot never owns /opt/HomeAssistant or preloaded images
firstboot instance commit only owns INSTANCE_FINAL_DIRS + transaction root
firstboot failure cleanup cannot delete public assets/images
durable transaction rejects release/schema/host-binding drift
completed stage is idempotent
mixed unknown committed state fails closed
R8 authorization ID is absent from firstboot contract
~~~

COMPATIBILITY:

~~~text
legacy run_fresh_staging adapter call order remains exact
legacy report schema remains gh.n3w.t1-fresh-installer-orchestration/1
legacy wrapper still produces same PASS/STOP semantics
~~~

## 14. R2：Master-build / Seal source package

R1 independently reviewed后再进入。

ADD/MODIFY 预计：

~~~text
tools/n3w_t1_golden_master_build.py
tools/n3w_t1_golden_master_seal.py
tests/tools/test_n3w_t1_golden_master_build.py
tests/tools/test_n3w_t1_golden_master_seal.py
infra/n3w-t1/... public release manifest/template
.github/workflows/n3w-t1-golden-master-ci.yml
current payload workflow / artifact builder as necessary
~~~

R2 负责：

- real master preflight；
- exact image/public source install；
- no-secret master audit；
- Seal audit；
- release manifest；
- disk-capture readiness contract。

仍不实现 clone OS identity mutation。

## 15. R3：Per-device firstboot source package

R2 + target Armbian OS-identity contract review 后进入。

预计：

~~~text
tools/n3w_t1_device_firstboot.py
tests/tools/test_n3w_t1_device_firstboot.py
infra/n3w-t1/systemd/n3wfc4-firstboot.service
firstboot transaction schemas/tests
instance rendering helpers
~~~

并修改 activation units 添加 firstboot/device-ready ordering。

R3 必须有 power-loss/fault-injection tests，不能只测 happy path。

## 16. R4：Factory acceptance / clone harness

预计：

~~~text
tools/n3w_t1_factory_acceptance.py
tools/n3w_t1_clone_uniqueness_audit.py
tests/...
workflow/harness...
~~~

source 完成后才进入真实 A/B clone physical gate。

## 17. Workflow strategy

当前 `n3w-t1-fresh-bootstrap-deployable-payload-ci.yml` 保留为 R8/single-host regression authority。

不要把它直接改名成 golden-master workflow 并失去历史含义。

新增独立：

~~~text
N3W T1 golden master source CI
N3W T1 firstboot transaction CI
~~~

可以复用同一 exact Manager/HA/Broker build logic，但 artifact schema 和 live authorization 语义分开。

`h0h1-init-portable-restore-ci.yml` 继续覆盖：

- system_init；
- portable restore；
- identity conflict；
- bootstrap module boundary。

新增 firstboot pure contract 位于 `greenhouse_manager.bootstrap` 时必须继续满足该 workflow 的：

~~~text
bootstrap modules do not import socket/subprocess
bootstrap modules do not execute docker
runtime does not depend on bootstrap
~~~

host mutation全部留在 `tools/` adapters。

## 18. 不做的大重构

为控制风险，明确不做：

- 不重写 `system_init.py`；
- 不合并 system CA 与 Broker CA；
- 不重写 DynSec provisioner；
- 不改变 pairing/N3-W credential lifecycle；
- 不重写 Compose 网络拓扑；
- 不同时修 B2 hostname/mDNS；
- 不重开 F5；
- 不删除 R8 executor；
- 不把 PR #127 整体搬入；
- 不为了新架构顺便实现 streaming；
- 不修改节点固件。

## 19. Source blocker classification

架构定义已经关闭，当前 blocker 转为 implementation。

~~~text
AB1..AB5=CLOSED_DESIGN
SOURCE_BLOCKER_SB1=MIXED_PUBLIC_INSTANCE_STAGE
SOURCE_BLOCKER_SB2=MIXED_COMMIT_AND_CLEANUP_OWNERSHIP
SOURCE_BLOCKER_SB3=MIXED_POSTCHECK
SOURCE_BLOCKER_SB4=NO_DURABLE_FIRSTBOOT_TRANSACTION
SOURCE_BLOCKER_SB5=NO_SEAL_IMPLEMENTATION
SOURCE_BLOCKER_SB6=NO_OS_IDENTITY_ADAPTER
SOURCE_BLOCKER_SB7=NO_FACTORY_CLONE_UNIQUENESS_HARNESS

SOURCE_BLOCKER_COUNT=7
~~~

R1 只关闭 SB1–SB3，并建立 SB4 contract skeleton。
SB5–SB7 由后续包关闭。

## 20. 当前 STOP

~~~text
SOURCE_DECOMPOSITION_DESIGN=PASS
PRODUCT_SOURCE_MUTATION=false
STREAMING_SOURCE_REPAIR_NOW=HOLD
R3_CLEANUP=false
AUTHORIZATION_08_GRANTED=false
T1_ACCESS=false
BOARD_ACCESS=false
MERGE=false
~~~

推荐下一门：

~~~text
NEXT_ONE_GATE=
N3W_T1_GOLDEN_MASTER_FIRSTBOOT_SOURCE_DECOMPOSITION_REPAIR_R1

SCOPE=
public/instance stage ownership split
public/instance commit-cleanup ownership split
master/instance postcheck split
golden-master + firstboot pure contract skeleton
legacy R8 compatibility regressions

OS_IDENTITY_LIVE_IMPLEMENTATION=false
SEAL_LIVE_IMPLEMENTATION=false
FIRSTBOOT_SYSTEMD_INSTALL=false
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~

R1 source + CI 通过后 STOP，先做独立 source review，再进入 R2。
