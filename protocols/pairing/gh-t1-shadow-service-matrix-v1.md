# gh-t1-shadow-service-matrix-v1 真实 T1 快照服务身份候选

状态：Draft / M2.3j  
关联：ADR-0002、`gh-dynsec-profile-v1`、Issue #17、PR #35

## 1. 目标

在已经验证通过的 T1 同机回退包副本中加载 Dynamic Security，并在 `--network none` 候选容器内创建以下身份：

- provisioning：`gh-provisioning-greenhouse`；
- greenhouse-manager：`gh-manager-greenhouse`；
- Home Assistant：`gh-homeassistant-greenhouse`；
- 真实节点身份：`gh-n1-a9f2f8`。

候选只修改解压后的快照副本，不停止、重启、重建或重新配置当前 `mosquitto`、`greenhouse-manager`、Home Assistant 或真实节点。

## 2. 执行入口

```bash
greenhouse-manager-t1-shadow-services \
  /opt/greenhouse-m2-backups/<rollback-archive>.tar.gz \
  --expected-retained-topic \
  gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry
```

可通过 `--system-id` 和 `--node-id` 覆盖默认值，但本阶段正式候选固定使用 `greenhouse` 与 `gh-n1-a9f2f8`。

## 3. 隔离与秘密处理

1. 使用回退包 manifest 记录的精确 Mosquitto image ID；
2. 候选容器固定使用 `--network none`；
3. 管理密码通过一次性初始化文件加载，生成状态后立即删除；
4. 服务和节点密码只存在于进程内存、临时 0600 客户端配置和候选 Dynamic Security 状态；
5. Dynamic Security 请求载荷通过 stdin 传给容器内 `mosquitto_rr`，密码不进入 argv；
6. 临时客户端配置复制后立即从宿主临时目录删除；
7. 成功或失败均强制删除候选容器和临时目录；
8. 输出报告不包含用户名密码以外的秘密数据，也不包含任意密码值。

## 4. 验证矩阵

候选必须同时验证：

1. 节点 `gh-n1-a9f2f8` 发布自身 ingress，manager 能接收；
2. 节点发布其他 node ID ingress 被拒绝；
3. manager 发布 canonical state，Home Assistant 能接收；
4. manager 发布当前两类 Discovery，Home Assistant 能接收；
5. manager 不能发布 `homeassistant/status`、节点 ingress 或 `$CONTROL/#`；
6. Home Assistant 只能发布 `homeassistant/status`，不能写 canonical state 或 ingress；
7. provisioning 可以执行 Dynamic Security 请求并接收响应，但不能读写应用 Topic；
8. 四类 username 必须与冻结的唯一 client ID 同时匹配；
9. 注入 client 创建后失败时，按 `deleteClient` → `deleteRole` 回滚；
10. 回滚后 client 和 role inventory 均不存在；
11. legacy anonymous 在回滚后仍能使用非 `$` 应用 Topic；
12. legacy anonymous、节点、manager 和 Home Assistant 均不能创建 Dynamic Security client；
13. 真实 retained canonical telemetry 能从快照数据库恢复。

## 5. 成功报告

成功输出使用：

```text
schema = gh.m2.t1-shadow-service-candidate/1
network = none
service_identity_matrix = true
client_id_binding = true
provisioning_control_only = true
transaction_rollback = true
legacy_anonymous_after_rollback = true
current_services_modified = false
```

任一检查失败必须返回非零状态，且不得把部分通过报告为成功。

## 6. 安全门

本候选通过后，才允许开始生成真实迁移包、宿主机秘密存储方案和客户端认证改造。即使本候选通过，也不得立即关闭 `allow_anonymous true`；必须先依次迁移 manager、Home Assistant、节点和 provisioning，并完成稳定性观察与可验证回退。
