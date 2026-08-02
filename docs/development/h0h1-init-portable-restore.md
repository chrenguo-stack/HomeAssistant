# H0/H1：V0.7 身份对齐、greenhouse-init 与可移植恢复源码合同

## 当前状态

```text
source_contract_implemented=true
host_only_harness_implemented=true
v07_identity_alignment_included=true
t1_read_only_audit_executed=false
real_backup_created=false
real_restore_executed=false
anonymous_mqtt_closed=false
production_services_modified=false
ready_for_live_apply=false
```

本阶段只提供源码、测试、CLI 和 GitHub CI。任何真实 T1 操作都必须等待新的明确授权。

## 模块与入口

```text
greenhouse_manager.bootstrap.system_init
greenhouse_manager.bootstrap.portable_restore
greenhouse_manager.bootstrap.identity_guard
greenhouse_manager.bootstrap.anonymous_closure
```

对应入口：

```text
greenhouse-init
greenhouse-portable-restore
greenhouse-system-identity-guard
```

`runtime/` 不导入 `bootstrap/`。首次初始化和离线恢复不是长期运行 Manager 的启动副作用。

## 默认关闭合同

所有会产生文件的动作默认关闭：

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

这些参数只是源码层安全门，不构成生产授权。生产阶段还必须重新绑定主机、镜像、路径、
备份、授权、回滚和提交后审计。

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
- CLI 从 0600 passphrase 文件读取，不输出 passphrase。

## GitHub CI

工作流 `H0 H1 initialization and portable restore CI` 执行：

1. V0.7/C-07 focused tests；
2. bootstrap unit 和 CLI integration tests；
3. Ruff；
4. host-only harness；
5. source boundary 和 secret-free output 检查；
6. 生成包含 SOURCE_SHA、changed-files、review patch、harness result 和 SHA256SUMS 的 Artifact。

Docker、Broker、T1 和板卡均不在该工作流中。

## 后续真实阶段

```text
source/Draft review
→ 第一台 T1 只读基线
→ 私有可移植备份准备与授权
→ 第二台 T1 离线恢复
→ identity conflict / takeover gate
→ 隔离 Broker anonymous-closure full test
→ 真实服务切换与回滚门
→ H0/H1 故障矩阵和连续运行
```
