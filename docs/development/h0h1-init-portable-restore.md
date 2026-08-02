# H0/H1：V0.7 身份对齐、greenhouse-init 与可移植恢复源码合同

## 当前状态

```text
source_contract_implemented=true
host_only_harness_implemented=true
v07_identity_alignment_included=true
t1_read_only_audit_executed=true
t1_manager_persistence_gap_confirmed=true
persistence_migration_contract_implemented=true
runtime_hidden_state_classified=true
legacy_system_id_adoption_required=true
legacy_system_id_adoption_contract_implemented=true
legacy_adoption_host_only_harness_implemented=true
candidate_root_prepared=false
real_backup_created=false
real_restore_executed=false
anonymous_mqtt_closed=false
production_services_modified=false
ready_for_live_apply=false
```

本阶段只提供源码、测试、CLI、只读证据和 GitHub CI。真实 T1 写操作仍必须等待新的明确授权。

## 模块与入口

```text
greenhouse_manager.bootstrap.system_init
greenhouse_manager.bootstrap.portable_restore
greenhouse_manager.bootstrap.identity_guard
greenhouse_manager.bootstrap.anonymous_closure
greenhouse_manager.bootstrap.persistence_migration
greenhouse_manager.bootstrap.legacy_adoption
```

已安装入口：

```text
greenhouse-init
greenhouse-portable-restore
greenhouse-system-identity-guard
greenhouse-persistence-migration-plan
```

`legacy_adoption` 当前只校验分类证据并生成计划；不提供生产写入函数或生产执行 CLI。
`runtime/` 不导入 `bootstrap/`。首次初始化、离线恢复、接纳和迁移计划不是长期运行 Manager 的启动副作用。

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

`greenhouse-persistence-migration-plan` 只读取精确绑定的无敏感值基线并输出计划，不提供执行开关。
这些参数和计划只是源码层安全门，不构成生产授权。生产阶段还必须重新绑定主机、镜像、路径、
备份、授权、回滚和提交后审计。

## T1 只读分类结论

精确只读审计和隐藏状态分类确认：

- T1 运行 Manager `0.4.64`；
- Mosquitto Dynamic Security 和持久化数据库存在；
- 匿名兼容仍开启；
- Manager 没有 `/var/lib/greenhouse-manager` 持久化挂载；
- 正式 SYSTEM_ID 文档、根密钥、系统 CA、MANAGER_ID 未发现；
- registration、credential lifecycle 和 retirement outbox 结构化状态未发现；
- 当前 `GH_SYSTEM_ID` 已存在并持续用于接收遥测；
- 因此不得生成新 SYSTEM_ID，必须显式接纳现有 SYSTEM_ID。

分类结果 SHA-256：

```text
4e95fd661df371c9d124c17a4a892aca6db41e0fb7e202b4116bf804e425483a
```

详细合同见：

- `docs/development/h0h1-persistence-migration.md`；
- `docs/development/h0h1-legacy-system-id-adoption.md`。

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
- policy 敏感字段被拒；
- CLI 从 0600 passphrase 文件读取，不输出 passphrase；
- T1 基线、分类和源码绑定漂移均失败关闭；
- 现有 SYSTEM_ID 被保留，不生成替代 SYSTEM_ID；
- 正式 Manager SQLite 只创建当前 schema 和 provenance，业务行保持零；
- 不从日志重建 registration、credential、NODE_ID lease 或 outbox；
- 合成候选根十角色加密备份和第二目录恢复通过；
- 所有真实 T1、服务、网络和板卡操作保持关闭。

## GitHub CI

工作流 `H0 H1 initialization and portable restore CI` 执行：

1. V0.7/C-07 focused tests；
2. bootstrap unit 和 CLI integration tests；
3. Ruff；
4. 两主机 host-only harness；
5. Manager 持久化迁移 host-only harness；
6. 旧 SYSTEM_ID 接纳 host-only harness；
7. source boundary 和无敏感值输出检查；
8. 生成包含实际 BASE_SHA、SOURCE_SHA、changed-files、review patch、三个 harness result和
   SHA256SUMS 的 Artifact。

生产 T1、生产 Broker 和板卡均不在该工作流中。

## 后续真实阶段

```text
source/Draft review
→ 精确绑定的私有 SYSTEM_ID 读取与指纹验证
→ 私有候选持久根准备
→ 保留旧 SYSTEM_ID 的正式身份接纳
→ 零业务行正式 Manager 状态装配
→ Broker 一致性快照和完整角色清单
→ 私有可移植备份准备与授权
→ 第二台 T1 离线恢复
→ identity conflict / takeover gate
→ 隔离 Broker anonymous-closure full test
→ 真实服务切换与回滚门
→ H0/H1 故障矩阵和连续运行
```
