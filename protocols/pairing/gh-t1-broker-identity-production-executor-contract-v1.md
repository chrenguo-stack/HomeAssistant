# T1 Broker 身份迁移生产 Executor 契约 v1

状态：M2.4g-5f Draft

## 1. 目的

本协议定义真实 T1 Broker 身份迁移的生产 mutation、postactivation 与 rollback executor 在进入编码前必须满足的静态契约。

本阶段只生成并校验契约，不安装生产 executor，不提供 live apply 参数，不消费操作员授权，也不修改真实 T1。

## 2. 输入

契约构建器只接受：

1. 已通过 M2.4g-5a 校验的 Broker identity activation handoff；
2. 与 handoff 精确绑定的 inactive migration stage；
3. handoff 内的 fresh rollback archive；
4. handoff 内的 Broker、bootstrap、provisioning 与 Home Assistant 身份材料。

所有输入文件必须为普通文件、非符号链接并使用 `0600` 权限。

## 3. 绑定要求

构建器必须重新计算并校验：

- stage 目录名；
- `stage-manifest.json` SHA-256；
- 基线 Broker 配置 SHA-256；
- fresh rollback archive SHA-256；
- 每个 handoff material 文件 SHA-256；
- 精确 Dynamic Security request SHA-256。

任一绑定漂移必须停止，不得降级为警告。

## 4. Dynamic Security 请求边界

生产 executor 未来只允许应用已绑定请求中的以下命令类型：

- `setDefaultACLAccess`；
- `createRole`；
- `createGroup`；
- `setAnonymousGroup`；
- `createClient`。

请求必须满足：

- send、receive、subscribe 默认 deny；
- unsubscribe 默认 allow；
- 匿名客户端仍绑定 `gh-legacy-anonymous-shadow`；
- 至少包含 provisioning、manager、Home Assistant 和 node 四类客户端；
- username 与 client ID 均不可重复；
- 不允许夹带 `deleteClient`、`deleteRole`、密码轮换或关闭匿名访问命令。

bootstrap admin 的删除属于事务内独立步骤，必须在 provisioning 身份已验证后执行，不得写入预制请求。

## 5. mutation 作用域

未来生产 executor 只能修改 Broker 容器对应的以下目标：

- `/mosquitto/config/mosquitto.conf`；
- `/mosquitto/config/dynsec-password-init`；
- `/mosquitto/data/dynamic-security.json`。

必须满足：

- 只允许重启 `mosquitto`；
- 禁止 Compose recreate；
- 禁止重启 Home Assistant；
- 禁止重启 greenhouse-manager；
- 配置与 bootstrap secret 必须在同文件系统私有临时文件中完成写入；
- 文件内容和父目录均必须 `fsync`；
- 只能通过原子 replace 切换目标文件；
- mutation 前必须重新确认 fresh rollback 可用。

禁止触碰：

- Home Assistant `.storage`；
- T1 Compose 文件和 `.env`；
- manager 环境与运行凭据；
- 节点凭据交付目录；
- Home Assistant MQTT config entry 的内部存储。

## 6. 固定执行顺序

生产 executor 后续实现不得改变以下顺序：

1. 重新校验 handoff、stage 与 fresh rollback；
2. 重新绑定真实运行时和 Broker mount；
3. 创建同文件系统私有 staging 文件；
4. `fsync` Broker 配置和 bootstrap secret；
5. 原子替换 Broker 配置目标；
6. 只重启 Mosquitto；
7. 等待 Dynamic Security state 创建；
8. 应用精确绑定的 Dynamic Security request；
9. 验证 provisioning 身份；
10. 删除 bootstrap admin；
11. 运行只读 postactivation audit；
12. 将 Home Assistant 迁移交给官方 MQTT UI/config-flow；
13. 在 authenticated stability gate 通过前保留 fresh rollback。

## 7. 强制回退

一旦进入 mutation，任何异常都必须触发 rollback。

rollback 必须：

- 恢复完整 fresh snapshot inventory，而不是只恢复单个配置文件；
- 删除 Dynamic Security state；
- 只重启 Mosquitto；
- 验证匿名 retained state 可读；
- 将回退失败视为终止性故障，禁止继续 Home Assistant 或节点迁移。

## 8. Home Assistant 边界

Home Assistant 只能通过官方 MQTT integration UI/config-flow 完成账号、密码和 client ID 重配置。

生产 executor 不得：

- 写入 `.storage`；
- 调用未公开的内部 config entry 写接口；
- 自动替换 MQTT integration；
- 将 UI 操作伪装成已完成。

## 9. 节点凭据边界

实体节点真实凭据交付路径尚未验证，因此：

- 本契约标记 `real_device_path_verified=false`；
- 生产 executor 不得自动写入节点；
- 匿名访问关闭门必须继续保持阻塞。

## 10. 契约输出

契约输出为 secret-free JSON，至少包含：

- source、rollback 与 material SHA-256 绑定；
- Dynamic Security 命令类型和数量；
- mutation allowlist 与 denylist；
- 固定执行顺序；
- rollback、Home Assistant 与节点边界；
- 完整契约 SHA-256。

输出必须保持：

```json
{
  "contract_review_complete": true,
  "production_executor_available": false,
  "execution_enabled": false,
  "apply_enabled": false,
  "ready_for_live_activation": false,
  "current_services_modified": false,
  "preserve_anonymous": true,
  "anonymous_closure_enabled": false
}
```

## 11. 下一门禁

M2.4g-5g 才允许实现生产 adapter 代码。该实现仍必须默认禁用，并在任何真实 T1 执行前增加：

- 真实 mount binding 只读预检；
- 单次短时授权绑定；
- contract SHA-256 绑定；
- fresh rollback 再验证；
- 明确的操作员门禁；
- 真实 T1 故障注入前的独立评审。
