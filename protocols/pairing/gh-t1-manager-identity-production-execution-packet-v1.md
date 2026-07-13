# greenhouse-manager 身份迁移生产执行包 V1

- 阶段：M2.4g-6o
- 状态：Draft
- 范围：真实 T1 上 `greenhouse-manager` 独立 MQTT 身份迁移的唯一 production execute 入口
- 关联：Issue #17、#94、#96、#98、#100；6e～6n

## 1. 目的

本协议将 6l 事务编排器、6m 宿主机 adapters、6n 被动运行时探针和 6k 第二次确认门收敛为唯一生产执行入口。执行包只允许修改和重建 `greenhouse-manager`，并在事务提交前证明 Mosquitto 与 Home Assistant 容器完全未变化。

代码实现和合并不构成真实 T1 执行授权。真实执行仍必须重新生成短时材料并取得两次精确操作员确认。

## 2. 强制输入

执行入口必须同时接收：

- 6j 单次 authorization 文件；
- 仍新鲜的 6i execution preparation；
- 6f driver contract；
- 6b manager preparation；
- 私有 production transaction root；
- `SYSTEM_ID`；
- 一个持续上报的真实 `NODE_ID`；
- 该节点的精确 Discovery topic；
- 6k 生成的完整第二次确认；
- 精确目标 `greenhouse-manager`；
- `--execute-manager-migration`；
- `--enable-production-execution`。

缺少任一 enable flag、目标不匹配或第二次确认前缀不正确时，必须在首次 `docker inspect` 之前退出。

## 3. 只读容器基线

首次写入前分别执行：

```text
docker inspect greenhouse-manager
docker inspect mosquitto
docker inspect homeassistant
```

每个容器必须：

- 名称精确匹配；
- `running`；
- restart count 为 0；
- container ID 为 64 位十六进制；
- image ID 为 `sha256:<64 hex>`；
- `StartedAt` 非空。

普通输出不得包含 container ID、image ID 或主机路径。

## 4. 事务内保护服务门

protected-service guard 必须在 6n runtime probe 的 `verify_existing_entities()` 和 `postactivation_audit()` 内执行，从而保证检查发生在 6l orchestrator commit 之前。

成功路径要求：

- `greenhouse-manager` image ID 与迁移前一致；
- `greenhouse-manager` container ID 已改变；
- 新 manager 容器 running、restart count 0；
- Mosquitto 的 container ID、image ID、StartedAt、restart count 全部不变；
- Home Assistant 的 container ID、image ID、StartedAt、restart count 全部不变。

任一检查失败必须作为 post-claim failure 进入 manager rollback。

## 5. 回滚阶段保护

rollback 中 6m adapters 会再次调用实体连续性探针。guard 必须再次验证：

- Mosquitto 未变化；
- Home Assistant 未变化；
- manager image 未变化；
- manager rollback 后 running、restart count 0。

持续存在的 protected-service 漂移会使 rollback 验证失败，并进入 6l 的 `rollback_failed` 终止状态，不得自动重试。

## 6. 唯一命令入口

工具入口：

```text
host/greenhouse-manager/tools/
run_t1_manager_identity_migration_production_execution_packet.py
```

CLI 不提供默认目标、不提供 `--yes`、不从历史文件自动选择授权，也不扫描 `/tmp` 查找材料。所有路径和确认必须由当前受控流程显式传入。

执行器内部仍重新运行：

1. 6k transaction gate；
2. 6n continuity baseline；
3. 6m fresh rollback snapshot；
4. 6k binding revalidation；
5. atomic authorization claim；
6. manager-only mutation；
7. runtime/business/protected-service postactivation；
8. commit 或强制 rollback。

## 7. 成功输出

成功只输出紧凑、secret-free、path-redacted JSON，允许包含：

```text
transaction_id
authorization_id
production_execution_completed=true
authorization_claimed=true
authorization_consumed=true
manager_identity_migrated=true
postactivation_verified=true
greenhouse_manager_recreated=true
greenhouse_manager_image_preserved=true
mosquitto_unchanged=true
homeassistant_unchanged=true
node_credentials_delivered=false
preserve_anonymous=true
anonymous_closure_enabled=false
```

不得输出：

- MQTT 用户名、密码或完整 Client ID；
- container ID、image ID；
- Compose、`.env` 或 overlay 内容；
- rollback 内容；
- authorization token；
- 真实主机路径。

## 8. 失败语义

- claim 前失败：不消费授权，不修改服务；
- claim 后失败：必须执行 manager rollback；
- rollback 成功：命令仍非零退出，不把迁移标记为完成；
- rollback 失败：终止状态，保留 journal 和现场，不自动重试；
- protected-service 漂移：即使不是事务主动造成，也不得提交成功。

## 9. 固定边界

执行包不得：

- 修改、重启或重建 Mosquitto；
- 修改、重启或重建 Home Assistant；
- 修改节点或下发节点凭据；
- 编辑 Home Assistant `.storage`；
- 发布合成 MQTT 遥测；
- 修改 retained state；
- 关闭匿名兼容；
- 接收任意容器名或任意 Compose service target。

## 10. 真实 T1 前置门

6o 合并后，真实 T1 仍需重新执行：

1. 拉取并核对新的 main 与 CI；
2. 重新生成 6e/6f；
3. 重新生成 900 秒有效的 6i；
4. 生成 6j request；
5. 在第一次操作员确认处停止；
6. 操作员确认后创建短时单次 authorization；
7. 运行 6k 并在第二次精确确认处停止；
8. 第二次确认后才调用 6o execute packet。

本协议本身不授权任何真实 T1 写操作。
