# H0/H1：旧 SYSTEM_ID 显式接纳与空白正式 Manager 状态合同

## 授权与证据绑定

源码合同来源：

```text
D1-H0H1-PR260-LEGACY-SYSTEM-ID-ADOPTION-CONTRACT-AND-HOST-ONLY-MIGRATION-HARNESS-CREATION-20260802-01
```

只读分类来源：

```text
D1-H0H1-PR260-EXACT-HEAD-T1-HIDDEN-RUNTIME-STATE-READ-ONLY-CLASSIFICATION-AUTHORIZATION-20260802-01
```

精确证据：

```text
PR                             #260
BASE_SHA                       ba6255cb3cb4067efd72b23f81f1a799c2c0026e
CLASSIFIED_SOURCE_HEAD_SHA     6a7e898cb7df50cd10545ef1795820ab8ac96e98
CLASSIFIED_ARTIFACT_ID         8832916787
CLASSIFIED_ARTIFACT_SHA256     914d6ce19203096f45603487bf161a7841491701202ead3a917e2bd001c09780
T1_BASELINE_RESULT_SHA256      8408e29885fdce1efb0500c0b2a1783b0ea9751fdf156b1c177dd2695cf46d85
T1_CLASSIFICATION_RESULT_SHA256 4e95fd661df371c9d124c17a4a892aca6db41e0fb7e202b4116bf804e425483a
```

## 分类结论

T1 不是空白新系统。只读分类确认：

- `greenhouse-manager 0.4.64` 正在运行；
- `GH_SYSTEM_ID` 存在并持续用于接收遥测；
- 日志中存在大量已接受遥测和少量配对信号；
- 未发现正式 SYSTEM_ID 文档、根密钥、系统 CA、MANAGER_ID；
- 未发现可识别的 registration、credential lifecycle 或 retirement outbox 结构化数据；
- 容器可写层未发现状态相关文件；
- Manager 没有 `/var/lib/greenhouse-manager` 持久化挂载。

因此分类为：

```text
LEGACY_RUNTIME_OR_CONFIGURATION_STATE_PRESENT
```

必须走“旧配置显式接纳”，禁止走“生成全新 SYSTEM_ID”。

## 身份接纳规则

1. 未来私有执行从当前 Manager 容器环境读取原始 `GH_SYSTEM_ID`；原值不得写入公开证据。
2. 原值的 SHA-256 前 24 位必须与已分类指纹一致。
3. 候选根中的正式 `system-identity.json` 必须保留该 SYSTEM_ID。
4. 不生成替代 SYSTEM_ID，不覆盖当前系统身份。
5. 可以在隔离候选根中生成新的正式 MANAGER_ID、SYSTEM_ROOT_KEY 和系统 CA，因为分类没有发现可导入的正式材料。
6. 新生成材料只属于候选根；在后续服务切换门之前不得挂载到生产 Manager。
7. `INITIALIZED.json` 必须 marker-last，并绑定分类结果 SHA-256、SYSTEM_ID 指纹和 `legacy_system_id_adopted=true`。

当前源码只实现分类结果校验和接纳计划生成，不提供生产写入函数或生产执行 CLI。
真实身份接纳必须在后续私有候选执行门中另行实现、绑定和授权。

## 无结构化旧 Manager 数据边界

分类只证明“没有发现可识别的结构化旧 Manager 数据”，不证明历史上从未发生配对、注册或凭据操作。

允许的正式 Manager 初始状态：

- 使用当前 `0.4.98` registration、credential assignment 和 retirement outbox schema；
- 所有业务表初始行为零；
- 写入一条独立 provenance 记录，绑定分类结果和 SYSTEM_ID 指纹；
- 明确记录 `structured_legacy_manager_state_imported=false`；
- 明确记录 `anonymous_nodes_reconstructed=false`。

禁止：

- 从遥测日志推断或伪造 registration；
- 从 MQTT Topic 推断 credential generation；
- 为现有匿名节点伪造 assignment、NODE_ID lease 或 retirement outbox；
- 把日志中的 pairing 字样当作完整配对证据；
- 以空白正式数据库为理由立即关闭匿名 MQTT。

现有匿名节点保持现状，后续逐台走明确的正式登记与凭据迁移流程。

当前源码不提供真实 Manager 数据库写入入口。零业务行数据库只在 host-only harness 的临时目录中
由当前 runtime store 合成，用于验证合同可行性。

## 候选根合同

```text
container_path=/var/lib/greenhouse-manager
mount_type=private_bind_mount
root_mode=0700
member_mode=0600
host_path=后续私有授权绑定
```

候选根创建前必须不存在，且所有路径组件不得为符号链接。完整角色布局：

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

Broker 两个文件只能在后续私有候选装配门中从一致性快照复制。当前源码合同不读取或复制生产 Broker 文件。

## 回滚绑定

任何候选写入前必须重新读取并绑定：

- 当前 Manager 镜像标签、镜像 ID、版本和完整挂载集合；
- 环境变量名称集合和 SYSTEM_ID 指纹；
- 匿名 MQTT 当前状态；
- Broker Dynamic Security 与 persistence 文件摘要；
- 候选根创建前不存在证明；
- Home Assistant、Mosquitto、Manager 的连续性探针。

后续失败时恢复原镜像和原挂载集合，保持匿名兼容不变。候选根保留用于取证，不自动删除。

## Host-only harness

`tools/h0h1_legacy_adoption_harness.py` 只在临时目录中执行：

1. 使用合成分类证据验证接纳计划；
2. 接纳合成旧 SYSTEM_ID，证明 SYSTEM_ID 未变化；
3. 生成新的候选 MANAGER_ID、根密钥和 CA；
4. 用当前运行时 store 创建零业务行 Manager SQLite；
5. 写入合成 Broker 状态；
6. 验证十角色清单、0700/0600 权限和加密备份；
7. 在第二个临时目录恢复，验证 SYSTEM_ID 保持且 activation disabled。

Harness 不连接 T1，不使用 Docker，不访问网络，不启动子进程，不修改生产服务。

## 当前门状态

```text
runtime_hidden_state_classified=true
legacy_system_id_adoption_contract_implemented=true
host_only_legacy_adoption_harness_implemented=true
raw_legacy_system_id_privately_bound=false
candidate_root_prepared=false
formal_identity_materialized=false
empty_formal_manager_state_materialized=false
broker_snapshot_materialized=false
portable_backup_verified=false
execution_authorized=false
ready_for_restore=false
ready_for_anonymous_closure=false
ready_for_deployment=false
```

本合同不授权 T1 写入、候选根创建、容器修改或重启、真实身份生成、真实备份、恢复、匿名关闭、Ready、合并或部署。
