# T1 节点同步重连只读证据 V96 记录

## 1. 执行结论

```text
status=node_synchronized_reconnect_evidence_succeeded
schema=gh.m2.t1-node-synchronized-reconnect-evidence/1
repository_sha=9b70576bcac47c9e3f95cedfd467652b517c1b11
manager_source_version=0.4.87
system_id=greenhouse
node_id=gh-n1-a9f2f8
RC=0
```

脚本 SHA-256：

```text
8ff1fa10f3810804b0bc99619c5bb6e33b9b97917a37787743bbdc3cf1d5312b
```

执行包含一次由操作者在 `READY_FOR_NODE_RECONNECT=true` 后进行的目标节点普通断电重启。未重启 T1，未修改节点配置，未升级固件。

## 2. 只读与安全边界

```text
read_only=true
preserve_anonymous=true
anonymous_closure_enabled=false
homeassistant_storage_read=false
node_credentials_delivered=false
production_manager_upgraded=false
current_services_modified=false
```

同时确认未创建、领取或消耗授权，未执行生产事务，未输出秘密值或源码路径。

## 3. Broker 与预配置身份

```text
anonymous_enabled=true
node_identity_exact=true
node_role_exact=true
node_acl_exact=true
node_acl_count=10
node_credential_material_present=true
protected_services_stable=true
broker_config_and_state_stable=true
```

绑定哈希：

```text
broker_config_sha256=8fbd8cd18259ac071d602ffaf85ecdb4033aed57bf4c0889801ccabf403c2c84
dynamic_security_state_sha256=0d21faa86f4d3f47d64a027de5d2bf524803f5a1d4ecd5d3b070996fcf416320
```

## 4. 同步运行时归因

```text
runtime_connection_anonymous=true
synchronized_reconnect_observed=true
authenticated_node_connection_observed=false
candidate_connection_count=1
candidate_client_id_count=1
connection_attribution_source=synchronized_broker_connection_log_and_fresh_ingress
```

关键新发现：

```text
observed_client_id_matches_target=false
legacy_runtime_client_id_differs_from_target=true
observed_client_id_fingerprint=97b32e78cb7b4ad3
```

原始 Client ID 未写入记录。该发现说明现有 anonymous 固件的运行时 Client ID 与未来 Dynamic Security 固定目标 `gh-n1-a9f2f8` 不同。候选认证固件必须显式切换 Client ID，不能继承历史值。

## 5. 数据与实体连续性

```text
canonical_retained_continuous=true
availability_retained_continuous=true
discovery_retained_continuous=true
fresh_ingress_observed=true
fresh_ingress_after_synchronized_reconnect=true
availability_state=online
component_count=19
existing_entity_identity_continuous=true
```

V93 的 35 秒 fresh ingress 观察失败已由 V94/V96 的更长同步窗口证明属于观察窗口问题，不是 topic 或节点身份错误。

## 6. 结果语义

V96 证明：

- 当前节点通过 anonymous 稳定运行；
- Broker 连接日志可用于同步归因；
- 当前运行时 Client ID 与未来认证目标不同；
- 预配置节点身份、角色、ACL 和凭据材料未漂移；
- retained、Discovery、fresh ingress 和 19 个组件身份连续；
- 三个受保护服务和 Broker 状态稳定。

V96 不证明：

- 当前节点固件已支持 username/password 和固定 Client ID；
- candidate/fallback 双槽已经实现；
- anonymous 自动回退已经验证；
- 节点凭据可以生成或下发；
- 已获得生产写操作授权；
- 可以关闭 anonymous。

## 7. 后续门

```text
ready_for_node_migration_design=true
ready_for_node_credential_generation=false
ready_for_live_apply=false
ready_for_anonymous_closure=false
```

下一阶段进入“节点固件 MQTT 认证能力门”，先完成设计和隔离能力验证。任何生产写入仍需新的证据链、回滚和一次性精确授权。
