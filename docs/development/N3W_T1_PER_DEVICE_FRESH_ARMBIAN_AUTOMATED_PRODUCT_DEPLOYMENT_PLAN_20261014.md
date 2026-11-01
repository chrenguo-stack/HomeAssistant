# N3-W T1 逐台 fresh Armbian + 自动产品部署执行计划

Date: 2026-10-14
Architecture authority: `docs/adr/0010-t1-per-device-fresh-armbian-automated-product-deployment.md`
Status: APPROVED_PLAN / SOURCE_AND_LIVE_EXECUTION_NOT_ENTERED

## 1. 目标

在一台逐台安装并完成首次启动的官方 Armbian T1 上，用 repository-owned 自动化完成：

```text
host readiness
→ exact product delivery
→ per-device product provisioning
→ service activation
→ end-to-end acceptance
```

成功后形成可重复的单机安装手册、自动部署命令、失败恢复方式和验收记录。该计划不使用
Golden Master、Final Seal、raw disk capture 或 clone boot。

## 2. 当前事实与未关闭项

```text
REAL_T1_ARMBIAN_DOCKER_NETWORK_BASELINE=PROVEN
FRESH_BOOTSTRAP_SOURCE_CLOSURE=PASS_FOR_HISTORICAL_SINGLE_HOST_SCOPE
HOST_ONLY_AND_ISOLATED_CI=PASS
END_TO_END_FRESH_T1_PRODUCT_DEPLOYMENT=NOT_PROVEN
PRODUCTION_SERVICE_ACTIVATION_ON_NEW_FRESH_ROUTE=NOT_PROVEN
```

当前已知 blocker：

```text
AVAILABLE_BYTES=9229160448
OLD_TRANSPORT_REQUIRED_BYTES=12671384447
OLD_TRANSPORT_MARGIN_BYTES=-3442223999
ROOT_CAUSE=compressed_payload_plus_three_materialized_image_tars_plus_container_store_plus_fixed_5_GiB_reserve
```

历史 R3 在第一个 Home Assistant image load/binding 阶段停止并回滚；相关 cross-store
binding source defect已经修复，但最新 replacement artifact 没有在真实 T1 上重新完成传输、
部署和服务启动。因此新计划从源码 gap review 开始，不把历史 CI 冒充 live PASS。

## 3. Gate 总览

| Gate | 内容 | T1 | Mutation | 结束条件 |
| --- | --- | --- | --- | --- |
| F0 | source rebind、复用/删除清单、delivery 方案选择 | 否 | 否 | 设计和 blocker 清单冻结 |
| F1 | 最小 installer/transport source repair | 否 | 否 | tests/CI/focused review PASS |
| F2 | fresh T1 read-only preflight | 是 | 否 | host、容量、网络、Docker、空白状态 PASS |
| F3 | 自动产品部署实机演练 | 是 | 是，需明确授权 | images/program/state/provisioning 完成或安全 STOP |
| F4 | 服务激活与端到端验收 | 是 | 是，需独立授权 | Broker/Manager/HA、TLS/ACL/MQTT/readiness PASS |
| F5 | 安装流程固化与重复性复核 | 可选第二次 fresh install | 按 gate 授权 | 文档、恢复、验收和设备台账闭环 |

每个 gate 都必须保持 `AUTO_EXECUTE_NEXT_GATE=false`。

## 4. F0 — Source rebind and gap review

```text
GATE=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F0_SOURCE_REBIND_AND_GAP_REVIEW_20261014_01
SCOPE=GITHUB_AND_LOCAL_SOURCE_ONLY
```

任务：

1. fresh rebind main、PR #541、candidate、CI 和 ADR-0010；
2. 重新映射 minimal baseline、fresh bootstrap、explicit provisioning、activation 和 acceptance；
3. 确认哪些 Golden Master/Seal/clone 分支应从 active path 删除；
4. 对 Manager、HA、Broker 三个镜像确认可发布 registry/digest 和现有 tar authority；
5. 在 direct digest pull 与 one-image-at-a-time stream 中选择一个默认 delivery contract；
6. 重算实际 T1 峰值容量，不沿用“全包解压 + 三 tar”模型；
7. 冻结 F1 最小源码修改、测试和 rollback 合同。

```text
PASS_IF=one bounded delivery route selected; active source seams and exact tests identified; no live assumptions promoted to PASS
STOP_BOUNDARY=before T1 access or any source implementation outside the approved F1 list
```

## 5. F1 — Installer and transport source repair

F1 只实现 F0 冻结的最小路径。目标合同：

```text
EXACT_IMAGE_BINDING=true
ALL_THREE_IMAGE_TARS_MATERIALIZED_TOGETHER=false
PRECLAIM_READONLY=true
AUTHORIZATION_BEFORE_FIRST_DOCKER_MUTATION=true
PARTIAL_FAILURE_ROLLBACK=true
PRODUCTION_SERVICES_START=false
```

若采用 registry pull：

- 只允许 exact digest，不允许浮动 tag；
- 先证明 T1 registry/DNS/TLS 可达；
- Manager image 必须有可验证的发布 authority；
- pull 后验证 architecture、digest 和运行绑定。

若采用 Mac stream：

- 每次只传输/stream 一个 exact image；
- load + verify 后立即释放该 image 的 staging copy；
- 每步重新检查实际 free bytes；
- 不在 T1 长期保存完整三镜像 payload。

F1 必须通过 focused tests、host-only full-fresh CI、ARM64 image binding、HA isolated runtime、
public repository safety 和最终 focused review。

## 6. F2 — Fresh T1 read-only preflight

用户负责完成 official Armbian 安装和首次启动。F2 只读核对：

- exact Armbian release/architecture 和首次启动完成；
- SSH 管理、网络、DNS、时间同步；
- machine-id 非空，SSH host keys 存在；
- Docker/Compose 状态和 storage root；
- filesystem/free-space 与新 delivery model 匹配；
- 生产端口未开放；
- 产品 containers/images/volumes/networks/paths/units/identity/secrets 不存在，或被精确分类；
- 没有旧 transaction、authorization 或 staging residue。

F2 PASS 只表示可以申请 F3 授权，不授权任何安装。

## 7. F3 — 实机自动部署演练

F3 使用 exact source/artifact 和一次性明确授权。部署顺序：

```text
claim authorization
→ obtain and verify images using the F1 delivery contract
→ install public program/config/unit/guard material
→ run explicit product provisioning
→ verify identity/secret/state ownership and stopped boundary
→ stop before production service activation
```

F3 成功条件：

- exact images、公共程序和配置安装完成；
- SYSTEM_ID、MANAGER_ID、CA/TLS、service credentials 和 DynSec 在 T1 本地生成；
- Manager/HA/Broker 初始状态为空且权限正确；
- ingress guard 已就位；
- transaction 完成且无 staging/rollback residue；
- 正式服务仍未越权启动。

## 8. F4 — 服务激活与端到端验收

F4 需要独立 live authorization。验收至少包括：

- Broker TLS listener、server-name 和 CA 验证；
- Manager、Home Assistant、Broker service readiness；
- Manager 和 HA 使用独立最小权限 MQTT credentials；
- DynSec ACL 和 anonymous/invalid-client rejection；
- HA 自动 MQTT bootstrap、重启后不重复创建 integration；
- Manager 空白业务状态、无历史 node/pairing/replay 数据；
- reboot 后 identity、credentials 和 service state 稳定；
- public-safe acceptance report 和私有设备台账均完整。

板卡配对和 NVS 操作仍属于后续独立 physical gate，不自动进入。

## 9. 现场问题处理规则

可以现场诊断和修复，但不能直接在 T1 上形成不可追溯的最终状态。

| 问题阶段 | 处理方式 |
| --- | --- |
| preclaim/read-only 发现不匹配 | 不 claim；保存脱敏证据；回 GitHub 修 source/test；fresh CI 后重做 F2 |
| claim 后、首个 mutation 前失败 | authorization 按合同处理；确认是否 consumed；不猜测重放 |
| image/program 安装中失败 | 停服务；执行 transaction-owned rollback；保留 bounded evidence；新 source/artifact/auth 后再试 |
| provisioning 失败 | 保留 durable transaction；只允许 source-defined resume/rollback，不删除 marker 假装 fresh |
| activation/acceptance 失败 | 停止扩展；保持或恢复安全服务边界；修源码和测试后用新授权复验 |

统一规则：

```text
DIRECT_UNTRACKED_TARGET_PATCH=false
SOURCE_FIRST_FIX=true
TEST_BEFORE_RETRY=true
FRESH_ARTIFACT_BINDING_BEFORE_RETRY=true
CONSUMED_AUTHORIZATION_REPLAY=false
IMPORTANT_ENGINEERING_ARTIFACTS_TO_GITHUB=true
```

## 10. 最终完成定义

一台 official fresh Armbian T1 满足以下条件后，新路线首次实机演练才算完成：

```text
FRESH_ARMBIAN_HOST_READINESS=PASS
AUTOMATED_PRODUCT_DEPLOYMENT=PASS
EXPLICIT_PRODUCT_PROVISIONING=PASS
PRODUCT_SERVICE_ACTIVATION=PASS
TLS_ACL_MQTT_ACCEPTANCE=PASS
REBOOT_STABILITY=PASS
ROLLBACK_OR_RECOVERY_PATH=VERIFIED_OR_EXPLICITLY_DEFERRED_WITH_GUARD
PUBLIC_ACCEPTANCE_RECORD=PASS
PRIVATE_DEVICE_LEDGER=PASS
BOARD_ACCESS=false
```

## 11. 当前停止点

```text
ARCHITECTURE_DECISION=APPROVED
PLAN=APPROVED
F0=NOT_ENTERED
F1=NOT_ENTERED
F2=NOT_ENTERED
F3=NOT_ENTERED
F4=NOT_ENTERED
T1_ACCESS=false
LIVE_MUTATION=false
NEW_ROUTE_LIVE_AUTHORIZATION_GRANTED=false
AUTO_EXECUTE_NEXT_GATE=false
```

下一步只进入 F0 repository/source gap review。
