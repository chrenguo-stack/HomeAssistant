# H0/H1：T1 基线缺口与 Manager 持久化迁移合同

## 授权与证据绑定

本合同来源于：

```text
D1-H0H1-PR260-T1-BASELINE-GAP-REMEDIATION-DESIGN-AND-HOST-ONLY-PERSISTENCE-MIGRATION-CONTRACT-CREATION-20260802-01
```

只读基线证据绑定：

```text
PR                 #260
BASE_SHA           ba6255cb3cb4067efd72b23f81f1a799c2c0026e
AUDITED_SOURCE     8efc47cabc01e274b62a0cec83448fbe4a56a56b
ARTIFACT_ID        8832112931
ARTIFACT_SHA256    407ae7e08d82672df647c8ea25eb8cbe1af25e6d796c0a7d85eb1bded637daf4
T1_BASELINE_SHA256 8408e29885fdce1efb0500c0b2a1783b0ea9751fdf156b1c177dd2695cf46d85
```

隐藏状态分类证据：

```text
CLASSIFIED_SOURCE_HEAD_SHA      6a7e898cb7df50cd10545ef1795820ab8ac96e98
CLASSIFIED_ARTIFACT_ID          8832916787
CLASSIFIED_ARTIFACT_SHA256      914d6ce19203096f45603487bf161a7841491701202ead3a917e2bd001c09780
CLASSIFICATION_RESULT_SHA256    4e95fd661df371c9d124c17a4a892aca6db41e0fb7e202b4116bf804e425483a
```

## 已确认事实

T1 当前运行 `greenhouse-manager 0.4.64`，核心容器均在运行。Mosquitto 已存在
`dynamic-security.json` 和 `mosquitto.db`，同时保持 `allow_anonymous true`。

当前 `greenhouse-manager` 没有 `/var/lib/greenhouse-manager` 持久化挂载。只读审计和分类没有发现：

- 正式 SYSTEM_ID 文档、系统根密钥和系统 CA；
- MANAGER_ID；
- Manager registration、credential lifecycle 和 retirement outbox 结构化状态；
- 容器可写层中的状态相关文件或打开的状态文件描述符。

但分类确认 `GH_SYSTEM_ID` 存在，且 Manager 已持续接受遥测。因此系统不是空白新系统，
迁移分支已经冻结为：

```text
LEGACY_CONFIGURATION_ADOPTION_REQUIRED
```

不得生成新 SYSTEM_ID。详细接纳合同见 `docs/development/h0h1-legacy-system-id-adoption.md`。

## 源码模块

```text
greenhouse_manager.bootstrap.persistence_migration
greenhouse_manager.bootstrap.persistence_migration_cli
greenhouse_manager.bootstrap.legacy_adoption
```

入口：

```text
greenhouse-persistence-migration-plan <baseline.json>
```

正式 CLI 默认只接受精确基线文件 SHA-256。它只生成计划并输出 JSON，不创建候选目录、
不修改容器、不复制 Broker 数据，也不执行身份接纳、备份、恢复或匿名关闭。

`legacy_adoption` 只提供分类校验、计划生成和 host-only harness；没有生产写入函数或生产执行 CLI。

## 目标持久化根

```text
container_path=/var/lib/greenhouse-manager
mount_type=private_bind_mount
root_mode=0700
member_mode=0600
host_path=必须在后续授权中绑定
```

默认逻辑角色布局：

```text
system_identity                    system-identity.json
system_root_key                    system-root.key
system_ca_certificate              system-ca.pem
system_ca_private_key              system-ca-key.pem
manager_identity                   manager-identity.json
manager_registration_state         manager/manager-state.sqlite3
manager_credential_lifecycle_state manager/manager-state.sqlite3
manager_retirement_outbox_state    manager/manager-state.sqlite3
broker_dynamic_security_state      broker/dynamic-security.json
broker_persistence_state           broker/mosquitto.db
```

三个 Manager 状态角色可以由同一 SQLite 文件承载，但清单必须分别声明三个逻辑角色。
Broker 两个角色仍来源于真实 Mosquitto 持久目录，只有在后续候选装配阶段才允许复制到一致性快照根。

## 已冻结迁移分支

```text
P0_BINDING_REFRESH
P1_HIDDEN_STATE_CLASSIFICATION                   已完成
A1_PRIVATE_SYSTEM_ID_CAPTURE                     未授权
A2_PRIVATE_CANDIDATE_ROOT                        未授权
A3_ADOPT_EXISTING_SYSTEM_ID                      未授权
A4_EMPTY_FORMAL_MANAGER_STATE                    未授权
A5_BROKER_SNAPSHOT_ASSEMBLY                      未授权
A6_PORTABLE_BACKUP_VALIDATION                    未授权
A7_SHADOW_AND_COMMIT_OR_ROLLBACK                 未授权
```

规则：

- 原始 `GH_SYSTEM_ID` 只在未来私有执行上下文读取；公开证据只保留指纹；
- 候选身份保留旧 SYSTEM_ID，同时生成新的正式 MANAGER_ID、根密钥和 CA；
- 正式 Manager SQLite 使用当前 schema，但所有业务表从零行开始；
- 只写 provenance，不从日志重建 registration、credential、lease 或 outbox；
- 现有匿名节点保持原连续性，后续逐台正式迁移；
- 任一指纹、镜像、挂载、Broker 摘要或匿名状态漂移立即失败关闭。

## 回滚合同

后续真实执行前必须保存并绑定：

- 当前 Manager 镜像标签、镜像 ID、版本和完整挂载集合；
- 当前环境变量名称集合和 SYSTEM_ID 指纹；
- 当前匿名兼容状态；
- Broker Dynamic Security 和 persistence 文件摘要；
- 候选根的创建前不存在证明；
- 服务连续性探针和回滚触发条件。

回滚时恢复旧镜像和旧挂载集合，保持匿名状态不变，并保留候选根用于取证；不得自动删除。

## 当前门状态

```text
design_complete=true
runtime_hidden_state_classified=true
legacy_system_id_adoption_required=true
legacy_system_id_adoption_contract_implemented=true
raw_legacy_system_id_privately_bound=false
candidate_root_prepared=false
formal_identity_materialized=false
manager_state_materialized=false
broker_snapshot_materialized=false
portable_backup_verified=false
execution_authorized=false
ready_for_real_backup=false
ready_for_restore=false
ready_for_anonymous_closure=false
ready_for_deployment=false
production_services_modified=false
```

本合同不授权修改 T1、升级 Manager、创建真实身份、创建真实备份、执行恢复、关闭匿名 MQTT、
将 PR 标记 Ready、合并或发布。
