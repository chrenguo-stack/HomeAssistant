# H0/H1：V0.7 身份对齐、greenhouse-init 与可移植恢复源码合同

## 当前状态

```text
source_contract_implemented=true
host_only_harness_implemented=true
v07_identity_alignment_included=true
t1_read_only_audit_executed=true
t1_manager_persistence_gap_confirmed=true
persistence_migration_contract_implemented=true
runtime_hidden_state_classified=false
real_backup_created=false
real_restore_executed=false
anonymous_mqtt_closed=false
production_services_modified=false
ready_for_live_apply=false
```

本阶段只提供源码、测试、CLI、只读基线证据和 GitHub CI。真实 T1 写操作仍必须等待新的明确授权。

## 模块与入口

```text
greenhouse_manager.bootstrap.system_init
greenhouse_manager.bootstrap.portable_restore
greenhouse_manager.bootstrap.identity_guard
greenhouse_manager.bootstrap.anonymous_closure
greenhouse_manager.bootstrap.persistence_migration
```

对应入口：

```text
greenhouse-init
greenhouse-portable-restore
greenhouse-system-identity-guard
greenhouse-persistence-migration-plan
```

`runtime/` 不导入 `bootstrap/`。首次初始化、离线恢复和迁移计划不是长期运行 Manager 的启动副作用。

## 默认关闭合同

所有会产生文件或改变身份的动作默认关闭：

```text
greenhouse-init initialize
  --enable-initialization
  --confirm INITIALIZE-NEW-GREENHOUSE-SYSTEM

greenhouse-portable-restore create
  --enable-create
  --confirm CREATE-PORTABLE-GREENHOUSE-BACKUP

greenhouse-portable-restore restore
  --enable-restore
  --confirm RESTORE-PORTABLE-GREENHOUSE-BACKUP

greenhouse-system-identity-guard claim
  --enable
  --confirm CLAIM-GREENHOUSE-SYSTEM-IDENTITY

greenhouse-system-identity-guard release
  --enable
  --confirm RELEASE-GREENHOUSE-SYSTEM-IDENTITY
```

`greenhouse-persistence-migration-plan` 只读取精确绑定的 secret-free 基线并输出计划，不提供执行开关。

这些参数和计划只是源码层安全门，不构成生产授权。生产阶段还必须重新绑定主机、镜像、路径、
备份、授权、回滚和提交后审计。

## T1 只读基线缺口

精确只读审计确认：

- T1 运行 Manager `0.4.64`；
- Mosquitto Dynamic Security 和持久化数据库存在；
- 匿名兼容仍开启；
- Manager 没有 `/var/lib/greenhouse-manager` 持久化挂载；
- 系统身份、Manager 身份以及 registration/credential/outbox 角色未在持久目录中发现；
- 真实备份、恢复、匿名关闭和部署均继续阻塞。

缺少持久挂载不能证明容器内部或旧路径不存在状态。必须先完成隐藏运行状态分类，再决定走新系统
初始化还是显式旧状态导入。详细合同见 `docs/development/h0h1-persistence-migration.md`。

## 可移植角色清单

inventory 文件是 0600 JSON string mapping，必须精确包含：

```text
system_identity
system_root_key
system_ca_certificate
system_ca_private_key
manager_identity
manager_registration_state
manager_credential_lifecycle_state
manager_retirement_outbox_state
broker_dynamic_security_state
broker_persistence_state
```

同一 Manager SQLite 文件可以同时承载 registration、credential lifecycle 和 outbox；
清单仍必须分别声明三个逻辑角色，防止恢复时漏掉其中一个语义层。

## Host-only 测试矩阵

- 两个空白主机独立初始化，SYSTEM_ID、MANAGER_ID 和 CA 独立；
- marker-last 和重复初始化幂等；
- partial/tampered 初始化失败关闭；
- 缺少角色、错误权限、错误 passphrase 和密文篡改失败关闭；
- 加密备份 verify 和第二主机恢复 round trip；
- 恢复后保持 activation disabled；
- 同一 SYSTEM_ID 双主机同时 claim 被拒；
- 原主机 release 后恢复主机可 claim；
- Manager、Home Assistant 和节点认证 policy 完整；
- 匿名 publish/subscribe 均被拒；
- policy secret-bearing 字段被拒；
- CLI 从 0600 passphrase 文件读取，不输出 passphrase；
- T1 基线绑定、只读证据和持久化缺口漂移均失败关闭；
- 十角色目标布局完整，但隐藏状态未分类时执行保持阻塞；
- 持久化迁移计划不得启用真实备份、恢复、匿名关闭或部署。

## GitHub CI

工作流 `H0 H1 initialization and portable restore CI` 执行：

1. V0.7/C-07 focused tests；
2. bootstrap unit 和 CLI integration tests；
3. Ruff；
4. 两主机 host-only harness；
5. Manager 持久化迁移 host-only harness；
6. source boundary 和 secret-free output 检查；
7. 生成包含实际 BASE_SHA、SOURCE_SHA、changed-files、review patch、两个 harness result 和
   SHA256SUMS 的 Artifact。

生产 T1、生产 Broker 和板卡均不在该工作流中。

## 后续真实阶段

```text
source/Draft review
→ T1 精确绑定只读状态分类
→ 私有候选持久根准备
→ 身份初始化或旧状态显式导入
→ Manager 状态装配与完整角色清单
→ 私有可移植备份准备与授权
→ 第二台 T1 离线恢复
→ identity conflict / takeover gate
→ 隔离 Broker anonymous-closure full test
→ 真实服务切换与回滚门
→ H0/H1 故障矩阵和连续运行
```
