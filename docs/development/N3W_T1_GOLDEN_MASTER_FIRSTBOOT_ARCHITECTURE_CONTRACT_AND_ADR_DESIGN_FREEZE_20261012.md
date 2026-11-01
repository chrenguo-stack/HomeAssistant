> **2026-10-13 SUPERSEDED TRIGGER MODEL NOTE**：本文件冻结的 master/instance 数据边界、Seal、clone uniqueness、restore/upgrade、factory/user ownership 等架构继续有效；但“first boot 作为新初始化触发器”的含义已被后续设计取代。当前 authority 要求 BOOT_STARTS_NEW_PROVISIONING=false，只有显式 provisioning command 才能开始全新实例化；boot 仅可 resume 已开始 transaction 或 verify DEVICE_READY。详见 `docs/development/N3W_T1_EXPLICIT_DEVICE_PROVISIONING_COMMAND_AND_BOOT_DECOUPLING_DESIGN_FREEZE_20261013.md` 与修订后的 ADR-0009。

# N3-W T1 黄金母盘与每机首次初始化架构合同冻结（2026-10-12）

TASK=
`N3W_T1_GOLDEN_MASTER_FIRSTBOOT_ARCHITECTURE_CONTRACT_AND_ADR_DESIGN_FREEZE`

## 0. Gate 状态

~~~text
DESIGN_FREEZE=PASS
SOURCE_REPAIR=false
T1_ACCESS=false
T1_MUTATION=false
R3_CLEANUP=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
AUTHORIZATION_08_GRANTED=false
~~~

本 Gate 只冻结量产生命周期和后续实现合同，不修改产品源码，不把 source closure 表述为 live acceptance。

长期决策入口：

- `docs/adr/0009-t1-golden-master-firstboot-production-lifecycle.md`

## 1. Authority resolution

本轮按“有权决定什么”而不是只按日期排序：

1. V0.7：长期产品架构、身份/恢复边界、阶段依赖；
2. 已接受 ADR（尤其 ADR-0004）：具体初始化、身份、恢复合同；
3. V0.5：未被 V0.7/ADR 替代的 H0/H1 原始验收含义；
4. main 已批准 S1 计划：黄金镜像、首启初始化是正式开发路线；
5. main process：黄金镜像/批量写入如何授权和验收；
6. 当前 R8 文档：单机 fresh-bootstrap 的当前实现范围；
7. PR #127：未合并，仅作历史细化参考。

冻结结论：

~~~text
GOLDEN_MASTER_ROUTE=CONFIRMED
COMMON_IMAGE_PLUS_PER_DEVICE_INIT=FORMAL_PROJECT_DIRECTION
R8_ARCHITECTURE_ALIGNMENT=NEEDS_REPAIR
~~~

## 2. R8 scope correction

R8/F5 的安装工具修复继续有效：

~~~text
PRODUCT_SOURCE_HEAD=5ed613673ec1ead29a1153d0e3916bdd3539a3fb
F5=CLOSED_SOURCE
~~~

但其 source closure 的范围收窄为：

- 单台 clean/minimal T1 fresh install 的 artifact/storage/imports/identity/bootstrap 合同；
- 不覆盖 golden master Seal；
- 不覆盖 disk image capture；
- 不覆盖 clone OS identity uniqueness；
- 不覆盖 firstboot power-loss recovery；
- 不覆盖 factory acceptance；
- 不覆盖 cross-clone live uniqueness。

因此不重开 F5，也不把 R8 单机安装结果直接当成量产母盘。

## 3. Target production lifecycle

~~~text
MASTER RELEASE AUTHORITY

BUILD
→ VALIDATED
→ SEALED
→ CAPTURED

PER-DEVICE AUTHORITY

UNINITIALIZED
→ INITIALIZING
→ DEVICE_READY
→ FACTORY_ACCEPTED
→ ACTIVE
~~~

对应生产流程：

~~~text
clean T1 / controlled build target
→ install public OS/Docker/product image baseline
→ validate common software
→ Seal
→ capture exact disk image
→ clone to target T1
→ device firstboot
→ factory acceptance
→ ship
→ user Home Assistant onboarding
→ ACTIVE
~~~

## 4. Golden master contents

母盘中允许相同：

- OS / Docker / Compose 公共基线；
- HA/Manager/Broker exact images；
- public source/templates/image-lock；
- systemd definitions / ingress-guard program；
- firstboot/seal/audit/recovery/upgrade 工具。

母盘中禁止存在最终实例值：

- SYSTEM_ID / MANAGER_ID；
- root keys；
- system CA / Broker CA private key；
- Broker TLS private key；
- MQTT service passwords / Broker admin secret；
- initialized DynSec；
- instance Manager/N3W DB；
- HA Owner / token / test .storage；
- node/pairing/relay/replay/test state；
- final machine-id；
- SSH host private keys；
- clone-collision-causing host/network identity residue。

## 5. Per-device firstboot contract

firstboot 必须：

1. 由 sealed-state + 本机 durable transaction 触发；
2. 不依赖 R8 `_08` 或历史人工 one-shot authorization；
3. 在稳定对外服务前生成 OS/host uniqueness；
4. 复用 ADR-0004/system-init 等现有 identity constructor；
5. 复用 fresh_state/fresh_broker/DynSec/service credential constructor；
6. marker-last；
7. power-loss 后复用已 commit 的身份，不重新生成；
8. unknown/mixed state fail-closed；
9. 完成后普通重启和升级不重新初始化。

## 6. Factory/user boundary

工厂 firstboot 生成基础 OS/product identity 和服务秘密。

工厂验收可以在受控环境启动实际产品服务做 readiness，但必须：

- guard 在 Broker 对外监听之前有效；
- 不创建正式 HA Owner；
- 不留下测试 node/registry/history/retained state；
- 不把工厂测试凭据变成用户账号；
- 验收结果绑定 exact release + host identity + product identity 摘要。

用户拥有：

- Home Assistant Owner；
- 用户密码/token；
- 家庭/地区/通知配置；
- 后续节点 pairing/assignment。

## 7. Clone uniqueness acceptance

同一 captured image 写入 A/B 两台 T1 后至少自动验证：

~~~text
A.machine_id != B.machine_id
A.ssh_host_fingerprint != B.ssh_host_fingerprint
A.host_instance_id != B.host_instance_id
A.SYSTEM_ID != B.SYSTEM_ID
A.MANAGER_ID != B.MANAGER_ID
A.system_ca_public_identity != B.system_ca_public_identity
A.broker_ca_public_identity != B.broker_ca_public_identity
A.broker_tls_public_identity != B.broker_tls_public_identity
A.service_credentials cannot authenticate to B
B.service_credentials cannot authenticate to A
business_state(A)=EMPTY
business_state(B)=EMPTY
simultaneous_LAN_collision=NONE
reboot_identity_stable=PASS
firstboot_rerun_idempotent=PASS
~~~

公共 evidence 只保存无秘密摘要/挑战结果。

## 8. New clone vs restore

**Fresh clone：**
生成新 OS identity 和新 SYSTEM_ID/CA/credentials。

**Backup restore：**
遵循 ADR-0004，保留备份 SYSTEM_ID/CA/credentials/business state；
目标主机 OS identity 不复制旧主机的 machine-id/SSH host keys；
原系统仍在线时必须经过 identity-claim/takeover 才能激活恢复副本。

**Upgrade：**
保留所有长期 identity；不得重新进入 firstboot。

**Factory reset：**
本 Gate 不通过“删 marker 重跑 firstboot”定义，后续另行冻结。

## 9. Capacity contract split

现有 R8 `MIN_POST_PEAK_FREE_BYTES=5 GiB` 只保留为当前安装工具的保守历史策略。

后续分为：

~~~text
MASTER_BUILD_WORKSPACE_REQUIREMENT
PRODUCT_RUNTIME_MIN_FREE_REQUIREMENT
UPGRADE_ROLLBACK_WORKSPACE_REQUIREMENT
~~~

流式 image load 的定位：

~~~text
STREAMING_SOURCE_REPAIR_NOW=HOLD
STREAMING_ROLE=MASTER_BUILD_OPTIMIZATION_ONLY
~~~

只有 master build workspace 仍被真实构建条件阻断时，再决定是否实现 streaming。

## 10. Current R8 mapping

| 当前能力 | 归属 |
| --- | --- |
| F5 storage authority/imports fail-close | KEEP in master-build |
| exact offline artifact/image binding | KEEP |
| three-image docker load | MASTER_BUILD |
| /opt/HomeAssistant public tree | MASTER_BUILD |
| Compose/systemd/guard definitions | MASTER_BUILD + instance rendering |
| create_identity | FIRSTBOOT |
| create_state | FIRSTBOOT |
| create_broker | FIRSTBOOT |
| initialize_dynsec | FIRSTBOOT |
| service credentials | FIRSTBOOT |
| CA/TLS key generation | FIRSTBOOT |
| stopped_postcheck | SPLIT master/instance/factory audit |
| per-device full payload transport/load | RETIRE from normal clone production |
| R8 _08 | current bounded live lineage only; not firstboot |

## 11. Astra blockers disposition

Astra independent review reported five architecture blockers.

本 design freeze 关闭 architecture-definition 层：

~~~text
AB1_SCOPE_SPLIT=CLOSED_DESIGN
AB2_SEAL_CONTRACT=CLOSED_DESIGN
AB3_FIRSTBOOT_RECOVERY=CLOSED_DESIGN
AB4_FACTORY_USER_ACTIVATION=CLOSED_DESIGN
AB5_CLONE_RESTORE_UPGRADE=CLOSED_DESIGN

ARCHITECTURE_BLOCKER_COUNT=0
IMPLEMENTATION_BLOCKER_COUNT>0
LIVE_ACCEPTANCE_PENDING=true
~~~

实现仍缺：

- source decomposition；
- Seal implementation/audit；
- firstboot durable transaction；
- OS identity implementation；
- service activation ordering；
- exact clone A/B acceptance harness；
- runtime/upgrade capacity thresholds；
- live acceptance。

## 12. R3 / authorization boundary

~~~text
R3_RETAINED=true
R3_CLEANUP=false
AUTH_03=CONSUMED_NO_REPLAY
AUTH_04_05_06_07=SUPERSEDED_UNGRANTED
AUTH_08=NOT_GRANTED
LIVE_APPLY=false
~~~

本 Gate 不以清理 R3 解决容量，也不改变任何历史 authorization。

## 13. Source delta principle

后续 source repair 必须优先重构编排，不重写核心业务：

KEEP：

- `system_init` / initialization verifier；
- `fresh_product_state`；
- `fresh_broker`；
- DynSec/ACL provisioning and audit；
- F5 storage authority；
- image RootFS/config binding；
- current credential/permission/redaction guards。

主要改动：

- split public install vs instance initialization；
- split `stage_runtime()` 中 public/instance responsibilities；
- add Seal + Seal audit；
- add durable firstboot orchestrator + systemd gate；
- add factory audit；
- add clone uniqueness acceptance harness。

## 14. STOP and recommended next gate

本 Gate 到此停止，不进入产品源码修改。

推荐下一门先做源码拆分设计与独立 review：

~~~text
NEXT_ONE_GATE=
N3W_T1_GOLDEN_MASTER_FIRSTBOOT_SOURCE_DECOMPOSITION_AND_REPAIR_DESIGN

SOURCE_MUTATION=false
T1_ACCESS=false
T1_MUTATION=false
R3_CLEANUP=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
AUTHORIZATION_08_GRANTED=false
~~~

该 Gate 应输出 exact file/function mapping、兼容保留范围、source repair package 和 CI matrix，
经复核后才进入实际 source repair。
