# N3-W T1 最小宿主基线 Fresh Product Bootstrap Source Design（2026-10-11）

## 0. Gate 与结论

本设计落实已冻结决策：

```text
TARGET_T1_BASELINE=ARMBIAN + DOCKER + NETWORK ONLY
GATE=N3W_T1_MINIMAL_HOST_BASELINE_BOOTSTRAP_SOURCE_DESIGN_20261011_01
DESIGN_STATUS=COMPLETE
LIVE_T1_MUTATION=false
BOARD_ACCESS=false
PR541=OPEN_DRAFT
MERGE=false
```

正式安装程序不再要求 T1 预先存在温室产品 identity、secret、CA/TLS、DynSec、Manager DB、Home Assistant 配置、Docker volumes/networks、产品 systemd/dispatcher/guard。它们全部属于 installer/bootstrap 的创建责任。

Run #91 exact artifact 的 supply-chain 绑定结论继续有效，但其旧 executor 的“预创建产品状态存在性检查”与本设计冲突，因此不得作为下一次 live deployment 输入。

## 1. Source audit：哪些能力可以直接复用

### 1.1 System identity

现有：

```text
host/greenhouse-manager/src/greenhouse_manager/bootstrap/system_init.py
```

已经具备：

- 默认禁用、显式 confirmation；
- 新 system_id / manager_id；
- system root key；
- H0/H1 System CA；
- 0700/0600 私有权限；
- marker-last；
- partial state fail-closed；
- symlink 拒绝；
- verify + idempotent reread。

因此 fresh installer **复用该实现**，不再自造第二套 system identity 逻辑。

注意：H0/H1 System CA 与 Broker MQTT transport CA 仍是两个独立 authority，不合并。

### 1.2 三服务 MQTT credential bundle

现有：

```text
host/greenhouse-manager/src/greenhouse_manager/ops/t1_clean_service_credential_bundle.py
host/greenhouse-manager/src/greenhouse_manager/runtime/service_identity_plan.py
host/greenhouse-manager/src/greenhouse_manager/runtime/dynsec_api.py
```

已经具备：

- Manager / Provisioning / Home Assistant 三套独立随机密码；
- 固定唯一 MQTT client id；
- 精确 role/ACL 计划；
- 默认 deny 合同；
- Manager 与 Provisioning password-file；
- Home Assistant password + bootstrap metadata；
- 不预创建 node credential；
- manifest/report 不输出密码。

因此 fresh installer **复用该 bundle 和 ACL source authority**。

### 1.3 Home Assistant first-boot MQTT bootstrap

现有：

```text
infra/n3w-t1/homeassistant/custom_components/n3w_mqtt_bootstrap
```

已经冻结 fresh-only 规则：

- 只在 0 个 MQTT config entry 时自动创建；
- 使用 Home Assistant 官方 config-flow；
- 不直接修改 .storage；
- existing exact entry 可 no-op；
- mismatch / multiple entries fail closed；
- 密码来自只读 file mount；
- Broker endpoint metadata 不含密码。

该路线继续保留，不重新设计浏览器自动化或 storage patch。

### 1.4 Manager N3-W runtime state

现有：

```text
tools/n3w_t1_production_manager_state_prepare.py
```

可继续复用 replay DB、relay authorization DB、relay-key directory 的创建与 audit 逻辑。

但当前工具把一个已经存在且带
`h0h1_legacy_adoption_provenance` 的 Manager DB 当作前置条件，因此 **不能直接承担 fresh Manager DB creation**。

### 1.5 Offline image 与 exact artifact

现有三镜像供应链继续保留：

```text
Manager
Home Assistant
Mosquitto
```

正式 apply 内仍只允许 `docker load`，禁止 registry pull。

post-upload GitHub artifact re-download + manifest exact set + sidecar + image tar SHA/size 的 Run #91 机制继续作为后续 artifact gate 基础。

## 2. 必须修复的五个核心缺口

### G1. preflight 方向反了

旧 executor 要求这些对象**存在**：

- 45-volume frozen set；
- system identity；
- 11-file secret bundle；
- Manager clean DB/provenance；
- DynSec；
- ingress guard。

新 executor 必须反过来证明温室产品状态**不存在**，同时证明 Armbian / network / Docker 基础可用。

### G2. Fresh Manager DB 没有正式 production constructor

旧 CI 用手写 SQL 合成一个带 legacy provenance 的 DB，再交给 prepare 工具。

这不能成为 fresh-product installer。

新 source 必须增加正式 fresh Manager state creator，并只调用 Manager 自己的 runtime schema owner：

```text
RegistrationRegistry
CredentialLifecycleStore
ReplayRegistry
SqliteNodeApplicationKeyAdmin
```

fresh DB 不应再为了兼容旧 staging gate 人为创建
`h0h1_legacy_adoption_provenance`。

旧 legacy-adoption provenance 继续服务历史迁移路径；fresh-product path 与 legacy migration 必须分离。

### G3. Broker transport CA/TLS 缺少 repository-owned fresh creator

历史 S11 已证明生成后的证书合同可用，但当前正式 staging executor 依赖现场已经存在的 Broker CA/server cert。

新 source 必须增加 repository-owned Broker TLS bootstrap，至少冻结：

- 独立 Broker private CA；
- server private key；
- server certificate；
- DNS SAN `mqtt.greenhouse.local`；
- IPv4 SAN `127.0.0.1`；
- 如继续保留 hostname compatibility，再显式加入 `armbian`，不得从当前 DHCP IP 动态固化到源码；
- CA signing key root-only；
- server key 对 Broker UID1883 可读；
- Broker container 永不挂载 CA signing private key。

### G4. DynSec 初始化和三服务身份仍是分段历史执行

现有 source 已有 ACL 与 credential plan，但 production bootstrap 需要一个正式 orchestration：

```text
empty Broker data root
→ offline/network-none DynSec admin init
→ exact default ACL
→ create provisioning/manager/homeassistant roles + clients
→ verify exact static inventory
→ isolated runtime positive/negative matrix
→ promote candidate to final Broker state
```

Node account 数量必须保持 0，直到真实首次配对。

### G5. 当前 staging transaction 绑定旧现场状态

旧 rollback 以“恢复 legacy collision / preserved Manager DB / fixed 45 volumes”为基础。

Fresh path 不应继续扩展这套 legacy rollback。

新的失败模型是：

- baseline 必须 clean；
- 所有新产品对象都带 transaction ownership；
- commit 前在 candidate root 隔离验证；
- commit 后只允许删除/回退本 transaction 新建的对象；
- 不恢复任何旧温室业务状态；
- 遇到无法证明 ownership 的 partial state 就 STOP_RECOVERY_REQUIRED，不猜测、不覆盖。

这属于 fresh-install 的 fail-closed transaction，不是旧系统 rollback engine。

## 3. 新 installer 的阶段设计

### F0 — Minimal host preflight（只读）

必须证明：

```text
ARCH=aarch64
DOCKER_ENGINE=ready
DOCKER_COMPOSE=ready
NETWORKMANAGER_OR_EQUIVALENT=ready
DEFAULT_ROUTE=present
TIME_SYNC=acceptable
ROOT_CAPACITY=pass
PRODUCT_CONTAINERS=0
PRODUCT_IMAGES=0
PRODUCT_VOLUMES=0
PRODUCT_NETWORKS=0
PRODUCT_LISTENERS=0
PRODUCT_PATHS=absent
PRODUCT_UNITS=absent
PRODUCT_DISPATCHER=absent
PRODUCT_FIREWALL_CHAIN=absent
```

基础 SSH/NetworkManager/Docker 自身不属于产品 absence 检查。

任何旧 product state 残留都 STOP；installer 不在同一动作里“顺手清理未知旧状态”。

### F1 — Exact payload + transport preflight

Host wrapper：

- 只接受 exact GitHub run/artifact/name/digest；
- 本地验证 archive / manifest / executor / wrapper；
- remote staging root 使用 root-backed `/var/tmp`，禁止 `/tmp` tmpfs；
- 在 SCP 前读取目标文件系统可用空间；
- 同时校验 extraction peak 和 image-load peak；
- 不以单一固定 5 GiB 阈值替代 payload-aware peak calculation；
- archive 解压并完成 SHA verification 后立即删除 outer archive。

CI 必须把后续容量计算需要的 payload/image size 元数据写入 non-secret manifest。

### F2 — Load exact offline images

三镜像只从 artifact load：

```text
Home Assistant
Manager
Broker
```

推荐按最大镜像优先，且每个 tar：

```text
verify
→ docker load
→ exact image/config/platform verify
→ 删除该 staging tar
```

避免三份 tar 与完整 Docker 解包结果长期同时占用 root。

任何 load 失败：删除仅本 transaction 新建的 image refs，STOP。

### F3 — Candidate product identity

在 private candidate root 内调用现有 `initialize_system()`：

```text
new system_id
new manager_id
new system root key
new H0/H1 System CA
```

不读取旧 identity，不采用旧 SYSTEM_ID，不做 migration。

marker-last PASS 后才允许进入下一步。

### F4 — Fresh Manager state

新增 repository-owned fresh-state creator：

1. 创建 0700 Manager/N3-W candidate directories；
2. 用 `RegistrationRegistry` 创建 registration/pairing/history/lease/retirement schema；
3. 用 `CredentialLifecycleStore` 创建 credential schema；
4. 业务 row count 必须为 0；
5. 不创建 legacy-adoption provenance table；
6. 用现有 replay/key store source 创建：
   - replay.sqlite3；
   - relay-authorization.sqlite3；
   - relay-keys/；
7. audit 全部为 0；
8. bind 到本次新 system identity 的 fresh-product manifest，而不是 legacy provenance。

### F5 — Broker TLS + service credentials + DynSec candidate

分别生成：

- Broker private CA + server key/cert；
- root-only DynSec bootstrap admin secret；
- Manager / Provisioning / HA 三服务 credential bundle。

使用 exact Broker image、`--network none` 和 private candidate data root 初始化 DynSec。

随后使用既有 `service_identity_plan.py` 和 `dynsec_api.py` 创建三个服务角色/client。

候选必须证明：

```text
NODE_CLIENT_COUNT=0
SERVICE_CLIENT_COUNT=3
SERVICE_ROLE_COUNT=3
DEFAULT_DENY=exact
ADMIN_NOT_USED_BY_RUNTIME=true
PASSWORD_PLAINTEXT_OUTPUT=false
```

### F6 — Source/config/network/guard stage

从 exact payload 安装：

- production Compose；
- image-lock；
- Mosquitto config；
- HA configuration + custom component；
- readiness/deployment-gate tools；
- activation units；
- certificate lifecycle source。

创建：

```text
n3wfc4-private
n3wfc4-services
```

创建 fail-closed Broker ingress guard，顺序必须为：

```text
guard installed + readback PASS
→ 才允许未来 wildcard 8883 publication
```

此阶段 production Broker/Manager/HA 仍保持 stopped。

### F7 — Candidate-to-final commit + stopped postcheck

只在 F0–F6 全部 PASS 后 promote transaction-owned candidate 到 final paths。

最终 stopped-state 必须证明：

- exactly one fresh System Identity；
- exactly one clean Manager DB；
- N3-W state 0 nodes / 0 replay；
- exactly one Broker DynSec；
- exactly 3 service accounts + 0 node accounts；
- exactly one HA config root；
- exactly 3 production image refs；
- exact two Docker networks；
- guard active/enabled；
- production services installed but stopped/disabled according to activation policy；
- 8883/1883/8123/47111/47112 无非预期 listener；
- secrets 只在 T1 private paths；
- artifact/source hash binding preserved。

此 PASS 只代表 `FRESH_PRODUCT_STAGED=PASS`，不自动启动生产服务。

### F8 — Independent activation authorization

生产 activation 使用**新的 authorization identity**，不得复用：

```text
N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_03
```

该 ID 状态为：

```text
NOT_GRANTED_SUPERSEDED
CLAIMED=false
CONSUMED=false
```

新 authorization 只能在：

- source repair CI PASS；
- exact artifact binding PASS；
- T1 minimal-baseline normalization PASS；
- fresh F0 preflight PASS；
- staged postcheck PASS；

之后生成并由用户明确批准。

## 4. Home Assistant 边界

正式目标仍然是唯一一套 fresh HA：

```text
FINAL_PRODUCTION_HA_COUNT=1
```

HA config root 从空目录开始。

MQTT 自动配置继续使用 `n3w_mqtt_bootstrap`，官方 config-flow only。

HA loopback authenticated MQTT `127.0.0.1:1883` 与 node/Manager TLS `0.0.0.0:8883` 的现有双入口设计保留；1883 绝不能 wildcard/LAN publication。

## 5. Baseline normalization 与 installer 的关系

当前真实 T1 已清除：

```text
containers=0
images=0
build_cache=0
```

但仍有：

```text
docker_volumes=45
以及历史预创建 identity/secret/CA/DynSec/Manager state/units/guard 等产品状态
```

这些不会在 source design gate 删除。

顺序冻结为：

```text
source design
→ source repair + CI
→ exact clean-baseline normalization manifest
→ explicit live normalization authorization
→ normalize T1 to minimal baseline
→ fresh read-only F0
→ exact fresh bootstrap artifact
→ explicit fresh staging authorization
```

这样不会先把 T1 清空，再发现 installer 尚未具备从零创建能力。

## 6. Source repair 拆分

### R1 — Fresh state constructors

新增/重构：

- fresh Manager DB constructor；
- fresh N3-W runtime constructor/audit；
- fresh-product state manifest；
- legacy provenance 从 fresh contract 中移除。

### R2 — Broker TLS + DynSec bootstrap

新增 repository-owned：

- Broker CA/server cert generator + verifier；
- DynSec candidate initializer；
- 三服务 identity provisioning + exact audit；
- no-node guard。

### R3 — Minimal-baseline installer

把旧 staging executor 改为或替换成 fresh installer：

```text
preflight(clean absence)
→ load images
→ candidate identity/state/secrets
→ broker candidate
→ files/networks/guard
→ commit
→ stopped postcheck
```

旧 executor 作为 superseded historical implementation，不继续塞兼容分支。

### R4 — Host wrapper / artifact contract

- `/var/tmp`；
- remote filesystem preflight；
- payload-aware disk peak；
- sequential image-tar release；
- exact artifact re-download binding；
- no live registry pull。

### R5 — Host-only isolated full-fresh CI

从空 temporary host model 开始，证明：

- no pre-created product state；
- complete bootstrap；
- fail-closed on dirty baseline；
- partial candidate blocks replay；
- no secret stdout；
- node credential count 0；
- services remain stopped；
- fault injection only touches transaction-owned state。

### R6 — Exact ARM64 three-image CI

使用 frozen Manager / HA / Broker ARM64 image：

- execute bootstrap helpers inside exact images where required；
- validate cert/key UID paths；
- validate DynSec runtime matrix；
- validate HA MQTT config-flow isolated runtime；
- validate Compose/deployment gate；
- publish new exact artifact；
- post-upload re-download exact binding。

## 7. 不允许的捷径

禁止：

- 为满足旧 executor 而先手工创建 identity/secrets/DB；
- 保留 45-volume fingerprint 作为新产品 contract；
- 把 legacy provenance table 强行塞进 fresh DB；
- 把 Broker CA 私钥放进 image/artifact/GitHub；
- 在 apply 内 `docker pull`；
- 直接编辑 HA `.storage`；
- 预创建 node MQTT credential；
- 用管理员 MQTT 账号代替 provisioning service；
- 把当前 DHCP IP 固化进源码；
- 通过降低磁盘安全门槛绕过 transport 设计；
- 复用 `..._03`。

## 8. 当前关闭点

```text
SOURCE_DESIGN=PASS
TARGET_T1_BASELINE=ARMBIAN + DOCKER + NETWORK ONLY
RUN91_ARTIFACT_EVIDENCE=VALID_HISTORICAL_EXACT_BINDING
RUN91_DEPLOYMENT_INPUT=SUPERSEDED
OLD_STAGING_EXECUTOR=SUPERSEDED_FOR_FRESH_DEPLOYMENT
AUTHORIZATION_03=NOT_GRANTED_SUPERSEDED
T1_MUTATION=false
BOARD_ACCESS=false
PR_MERGE=false

NEXT_ONE_GATE=
N3W_T1_MINIMAL_HOST_BASELINE_BOOTSTRAP_SOURCE_REPAIR_R1_20261011_01
```
