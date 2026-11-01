# gh-t1-broker-identity-production-adapter-skeleton-v1

状态：M2.4g-5h Draft

## 目标

本协议定义真实 T1 Broker 身份激活生产适配器的**不可调用骨架**。它只消费已经验证的 production executor contract 与通过的 live mount gate，冻结未来 mutation、postactivation、rollback 三个适配器的接口边界，不提供任何真实写入口。

## 输入绑定

骨架必须读取 mode 0600、非符号链接的两个 JSON 文件：

1. `gh.m2.t1-broker-identity-production-executor-contract/1`；
2. `gh.m2.t1-broker-identity-live-mount-gate/1`。

两者必须满足：

- contract SHA-256 完全一致；
- live mount gate 的全部 checks 为 true；
- `mount_binding_ready=true`；
- `current_services_modified=false`；
- `preserve_anonymous=true`；
- `anonymous_closure_enabled=false`。

骨架只保存 contract SHA-256 与 mount-binding SHA-256，不保存真实宿主机路径、密码或 Dynamic Security 请求内容。

## 适配器库存

必须固定存在三个名称：

- `mutation`；
- `postactivation`；
- `rollback`。

每个适配器在本阶段必须同时声明：

- `installed=false`；
- `callable=false`；
- `host_write_capability=false`；
- `docker_mutation_capability=false`；
- `authorization_claim_capability=false`。

## 禁止的执行接口

本阶段不得提供：

- execute 子命令；
- enable/apply/live 标志；
- 授权 claim；
- 宿主机目标路径参数；
- Docker create/start/stop/restart/rm/cp 调用；
- Mosquitto、Home Assistant、greenhouse-manager 或节点写入。

即使调用代码中的占位执行函数，也必须无条件失败并报告生产适配器未安装。

## 继续阻塞条件

以下条件必须保留：

1. production adapters 尚未安装；
2. 操作员授权尚未 claim；
3. Home Assistant 官方 MQTT UI/config-flow 尚未执行；
4. 实体节点凭据交付路径尚未验证。

其中任一条件存在时：

- `production_executor_available=false`；
- `execution_enabled=false`；
- `apply_enabled=false`；
- `operator_action_authorized=false`；
- `ready_for_live_activation=false`；
- `current_services_modified=false`；
- `preserve_anonymous=true`；
- `anonymous_closure_enabled=false`。

## 后续阶段

后续实现必须先在隔离的宿主机目录副本上提供可注入、可故障注入的 adapter implementation，并证明：

- 精确目标 allowlist；
- 同文件系统原子替换与 fsync；
- 仅重启 Mosquitto；
- 任一 mutation 后失败强制 rollback；
- rollback 失败为终止故障；
- Home Assistant 仍只能走官方 UI/config-flow；
- 实体节点未验证前不得关闭匿名兼容。
