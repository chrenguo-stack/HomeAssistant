# T1 Broker 身份隔离快照事务适配与故障注入 V1

**阶段：** M2.4g-5e / M2.4g-5e-FI  
**状态：** Draft  
**适用对象：** `greenhouse-manager` 仓库侧验证  
**禁止对象：** 真实 T1 活动 Mosquitto、Home Assistant、greenhouse-manager 与实体节点

## 1. 目标

本协议定义 Broker 身份迁移的 mutation、postactivation 和 rollback 适配器形态，并只在由 fresh rollback 解包得到的临时快照上验证。验证覆盖成功事务、强制回退和分阶段故障注入，为后续 M2.4g-5f 的真实 Broker executor 设计提供证据；本阶段不提供任何真实主机写入口。

## 2. 不可突破的边界

1. 输入必须是已验证的 inactive stage、activation handoff 与 handoff 内 fresh rollback；stage 名称、manifest SHA-256、Broker 基线配置 SHA-256、rollback 相对路径和 rollback SHA-256 必须完全匹配。
2. handoff、stage、fresh rollback 和其中的身份材料仅作为只读源；执行前后必须比较完整文件清单、权限和 SHA-256。
3. 所有可变文件只能位于运行时创建的 `0700` 临时目录中；工作快照从已验证的 rollback 基线复制生成。
4. 所有候选容器名必须位于 `gh-m2-isolated-*` 命名空间；不得使用或接受 `mosquitto` 等活动服务名。
5. 每个候选容器必须显式使用 `docker create --network none`，只能挂载临时快照目录。
6. Dynamic Security 请求必须从 handoff 的精确私有文件读取，并通过标准输入交给候选容器内 `mosquitto_rr`；请求正文和凭据不得进入普通报告。
7. `allow_anonymous true` 必须保留；匿名应用 Topic 与 retained 状态必须可读，匿名 `$CONTROL` 必须被拒绝。
8. Home Assistant 只验证 handoff 中的目标身份与 client ID 约束，不修改 `.storage`，不模拟或替代官方 MQTT UI/config-flow。
9. 本阶段报告必须固定声明：`production_executor_available=false`、`live_activation_enabled=false`、`apply_enabled=false`、`active_paths_modified=false`、`current_services_modified=false`。

## 3. 隔离适配器

### 3.1 mutation adapter

mutation adapter 在临时工作快照中完成：

- 校验 handoff 内 `mosquitto-plugin.conf` 与冻结插件配置完全一致；
- 写入临时 bootstrap password-init 文件；
- 创建并启动 `--network none` Mosquitto 候选；
- 等待候选生成 `dynamic-security.json`，固定为 `0600`；
- 通过 bootstrap 身份执行 handoff 中的精确 Dynamic Security 请求；
- 验证 provisioning 身份具有控制能力；
- 删除 bootstrap admin，并确认其失效；
- 再次确认 provisioning 身份仍可工作。

适配器输出满足事务协调器既有 mutation 契约，但仅表示隔离候选完成，不表示真实 Broker 已修改。

### 3.2 postactivation adapter

postaudit 必须全部通过：

- 候选运行正常；
- Broker 配置相对基线发生预期变化；
- Dynamic Security 插件已配置，状态文件存在且为 `0600`；
- 匿名兼容仍开启；
- 匿名 retained 状态可读；
- Home Assistant 正确身份与 client ID 可读 retained 状态；
- 错误 client ID 被拒绝；
- provisioning 可访问 `$CONTROL`；
- bootstrap admin 已被拒绝；
- 匿名 `$CONTROL` 被拒绝。

成功后必须删除隔离候选，不保留可运行容器。

### 3.3 rollback adapter

任何已经开始写入临时工作快照的异常都必须进入 rollback adapter。rollback 必须：

1. 强制删除候选容器并确认无残留；
2. 删除工作快照；
3. 从不可变 baseline 重新复制工作快照；
4. 比较完整文件清单、权限和 SHA-256，确认基线恢复；
5. 确认配置中不存在认证插件，且 `dynamic-security.json` 不存在；
6. 使用另一个 `--network none` rollback probe 启动恢复快照，并确认匿名 retained 状态可读；
7. 删除 rollback probe。

任何一项不完整都必须显式报告 `rollback failed`，不得将部分恢复标记为成功。

## 4. 故障注入矩阵

必须覆盖以下阶段：

| fault phase | 注入位置 | 验收 |
|---|---|---|
| `after_snapshot_write` | 临时配置与 bootstrap 材料开始写入后 | 强制回退完成 |
| `mosquitto_start` | 候选创建后、启动前 | 候选清理并回退 |
| `dynamic_security_init` | 候选启动后、状态初始化前 | 候选清理并回退 |
| `after_exact_request` | 精确 Dynamic Security 请求成功后 | 身份状态被回退 |
| `provisioning` | provisioning 验证前 | 强制回退完成 |
| `bootstrap_delete` | bootstrap 删除前 | 强制回退完成 |
| `postactivation` | postactivation 审计入口 | 强制回退完成 |
| `rollback_incomplete` | rollback 完整性确认前 | 明确报告 `rollback failed` |

除 `rollback_incomplete` 外，每个场景都必须返回 `rollback_completed=true`；所有场景都不得修改 handoff、stage 或活动服务。

## 5. CLI 与输出

无安装启动器与包入口只接受：

```text
greenhouse-manager-t1-broker-identity-isolated-transaction \
  HANDOFF_DIRECTORY STAGE_DIRECTORY \
  --expected-retained-topic gh/... \
  [--fault-phase PHASE | --fault-matrix]
```

该 CLI 的“执行”只表示创建临时快照和 `--network none` 候选。它没有 authorization 参数、没有 live apply 参数，也没有活动 Compose、Broker 数据目录或服务名参数，因此不能升级为真实 T1 激活入口。

## 6. 进入下一开发门的条件

M2.4g-5e 与 M2.4g-5e-FI 仅在以下条件同时满足时完成：

- 隔离成功路径全部检查通过；
- 完整故障矩阵通过；
- handoff 与 stage 不变；
- 候选容器无残留；
- greenhouse-manager CI、M0 vertical slice CI、M2 Dynamic Security CI 全部通过；
- 仓库仍不存在生产 Broker executor 或真实 T1 live activation CLI。

完成本门后仍不得操作真实 T1。M2.4g-5f 必须另行独立评审，并重新执行真实 preactivation、重新生成 fresh handoff/rollback 与短时授权。
