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

## 已确认事实

T1 当前运行 `greenhouse-manager 0.4.64`，核心容器均在运行。Mosquitto 已存在
`dynamic-security.json` 和 `mosquitto.db`，同时保持 `allow_anonymous true`。

当前 `greenhouse-manager` 没有 `/var/lib/greenhouse-manager` 持久化挂载。只读审计没有发现：

- SYSTEM_ID、系统根密钥和系统 CA；
- MANAGER_ID；
- Manager registration、credential lifecycle 和 retirement outbox 持久状态。

缺少持久挂载不能单独证明容器内部或其他旧路径不存在状态。因此合同必须先执行独立的
“隐藏运行状态分类”，不得直接把主机判定为全新无状态系统。

## 源码模块

```text
greenhouse_manager.bootstrap.persistence_migration
greenhouse_manager.bootstrap.persistence_migration_cli
```

入口：

```text
greenhouse-persistence-migration-plan <baseline.json>
```

正式 CLI 默认只接受上述精确基线文件 SHA-256。它只生成计划并输出 JSON，不创建候选目录、
不修改容器、不复制 Broker 数据，也不执行初始化、备份、恢复或匿名关闭。

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
Broker 两个角色仍来源于真实 Mosquitto 持久目录，只有在后续候选装配阶段才允许复制到完整、
可加密备份的快照根。

## 分阶段合同

```text
P0_BINDING_REFRESH
P1_HIDDEN_STATE_CLASSIFICATION
P2_PRIVATE_CANDIDATE_ROOT
P3_IDENTITY_INITIALIZE_OR_IMPORT
P4_MANAGER_STATE_ASSEMBLY
P5_COMPLETE_PORTABLE_INVENTORY
P6_MOUNT_AND_SHADOW_VALIDATION
P7_COMMIT_OR_ROLLBACK
```

关键分支：

- 若只读分类证明不存在任何旧身份和业务状态，后续可以走“新系统初始化”候选路径；
- 若发现旧身份或业务状态，必须使用明确的导出/导入适配器，不得生成替代身份覆盖旧状态；
- 若证据不完整、路径冲突或状态部分存在，立即失败关闭。

## 回滚合同

后续真实执行前必须保存并绑定：

- 当前 Manager 镜像、版本和完整挂载集合；
- 当前匿名兼容状态；
- 候选根的创建前不存在证明；
- 服务连续性探针和回滚触发条件。

回滚时恢复旧镜像和旧挂载集合，保持匿名状态不变，并保留候选根用于取证；不得自动删除。

## 当前门状态

```text
design_complete=true
runtime_hidden_state_classified=false
candidate_root_prepared=false
manager_state_materialized=false
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
