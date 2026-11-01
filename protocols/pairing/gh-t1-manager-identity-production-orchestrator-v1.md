# greenhouse-manager 身份迁移生产事务编排 V1

- 阶段：M2.4g-6l
- 状态：Draft
- 范围：真实 T1 上 `greenhouse-manager` 独立 MQTT 身份迁移的生产事务状态机
- 关联：Issue #17、#94；6e～6k

## 1. 目标

本协议定义 manager 身份迁移的最终生产编排边界。编排器必须把 6j 单次授权、6i 新鲜回滚包、6k 第二次确认门、6f driver contract、6e adapter contract、manager preparation 和真实 runtime binding 绑定为一次不可重放的事务。

本阶段首先交付库级编排器和注入式测试接口。默认不安装真实主机 adapters，不提供命令行执行入口，也不授权修改真实 T1。

## 2. 固定安全边界

事务只能修改和重建 `greenhouse-manager`：

- 不得修改、重启或重建 Mosquitto；
- 不得修改、重启或重建 Home Assistant；
- 不得修改节点或下发节点凭据；
- 不得编辑 Home Assistant `.storage`；
- 必须保留匿名兼容；
- 不得关闭匿名访问；
- 普通输出和 journal 不得包含密码、精确 Client ID、Compose/.env 内容、回滚包内容或原始主机路径。

## 3. 输入与绑定

生产执行请求必须重新构建 6k gate，并绑定：

- `authorization_id` 与授权有效期；
- execution preparation 名称、有效期和 manifest SHA-256；
- fresh rollback archive SHA-256；
- driver contract SHA-256；
- adapter contract SHA-256；
- runtime binding SHA-256；
- live binding SHA-256；
- 第二次精确确认字符串。

执行确认格式：

```text
EXECUTE-M2-MANAGER-MIGRATION:
<authorization-id>:
<execution-manifest-16>:
<rollback-16>:
<live-binding-16>
```

比较必须使用常量时间字符串比较。确认错误时不得创建事务、领取授权或修改服务。

## 4. 默认禁用

库级入口默认：

```text
production_transaction_adapters_installed=false
production_manager_driver_installed=false
production_executor_available=false
execution_enabled=false
apply_enabled=false
ready_for_manager_migration_apply=false
current_services_modified=false
```

只有后续独立实现并审核通过的真实主机 adapters 和唯一 execute CLI，才能显式传入执行能力。不存在 adapters 时必须 fail closed。

## 5. 固定执行顺序

1. 重新生成并验证 production execution request；
2. 验证第二次精确确认；
3. 创建 mode 0700 私有事务目录与 mode 0600 journal；
4. adapters 捕获并验证当前 manager-only 快照；
5. 再次运行 6k gate，要求所有关键绑定与首次请求一致；
6. 使用同文件系统 hardlink + unlink 原子领取授权；
7. 将授权标记为 claimed/consumed，并绑定 transaction ID；
8. 原子安装 manager 密码、认证环境与 Compose overlay；
9. 只重建 `greenhouse-manager`；
10. 执行 postactivation audit；
11. 全部通过后提交事务；
12. 任何 post-claim 失败均执行强制回滚；回滚失败为终止状态。

## 6. adapters 报告契约

### 6.1 prepare

必须证明：

```text
production_transaction_adapters_installed=true
production_manager_driver_installed=true
execution_entrypoint_installed=false
greenhouse_manager_only=true
mosquitto_target_allowed=false
homeassistant_target_allowed=false
node_target_allowed=false
current_services_modified=false
```

### 6.2 mutation

必须证明：

```text
mutation_started=true
manager_material_installed=true
greenhouse_manager_recreated=true
manager_restart_count_zero=true
mosquitto_modified=false
homeassistant_modified=false
nodes_modified=false
preserve_anonymous=true
anonymous_closure_enabled=false
```

### 6.3 postactivation

必须验证：

- manager 独立身份认证成功；
- ingress 订阅正常；
- canonical state 发布正常；
- availability 发布正常；
- Home Assistant Discovery 发布正常；
- 断线重连正常；
- 既有设备和实体连续；
- 节点凭据仍未下发；
- 匿名兼容仍保留。

### 6.4 rollback

必须恢复并验证：

- manager material；
- Compose binding；
- `greenhouse-manager` 旧运行状态；
- 旧匿名数据路径；
- 既有 Home Assistant 实体；
- Mosquitto、Home Assistant 和节点未被修改。

## 7. journal

journal 必须逐阶段原子写入、fsync，并至少包含：

```text
preparing_snapshot
snapshot_ready
authorization_claimed
mutation_started
mutation_completed
postactivation_verified
rollback_started
rollback_completed
rollback_failed
committed
```

`rollback_failed` 必须包含 `terminal=true`，且不得继续执行或自动重试。

`rollback_started`、`rollback_completed` 与 `rollback_failed` 必须保留首次主失败的脱敏粗粒度诊断：

- `failed_phase` 只能取固定 allowlist 值，不得写入自由文本；
- `failure_exception_class` 只能写入经过格式和长度校验的异常类名；
- `rollback_failed` 还必须以同样规则记录 `rollback_exception_class`；
- `rollback_completed` 必须包含 `rollback_verified=true`；
- 不得写入异常 message、traceback、凭据、主机路径或容器标识。

上述 journal 字段用于事务终态审计和 legacy fallback；6q 的独立细粒度
`failure-diagnostic.json` 与 `rollback-failure-diagnostic.json` 仍是定位 driver 子阶段的首选证据，且不得被 journal 覆盖。

## 8. 验收矩阵

进入真实 execute CLI 前必须覆盖：

- 默认禁用；
- 错误第二次确认；
- snapshot/prepare 失败且授权未领取；
- 二次 6k 绑定漂移且授权未领取；
- claim 冲突和授权重放；
- 各写入阶段故障；
- manager 重建失败；
- 身份、订阅、canonical、availability、Discovery、重连和实体连续性失败；
- 所有 post-claim 失败均完成验证回滚；
- 回滚失败进入终止状态。

## 9. 后续门

本协议和库级编排器合并后，下一子阶段才可实现真实主机受限 adapters、execute CLI 和完整故障矩阵。真实 T1 apply 仍必须重新生成 6e/6f/6i/6j，完成第一次确认、创建短时授权、通过 6k，并取得第二次精确确认。
