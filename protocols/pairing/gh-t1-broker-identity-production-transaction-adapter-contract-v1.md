# gh-t1-broker-identity-production-transaction-adapter-contract-v1

状态：M2.4g-5q Draft

## 1. 目的

从已验证的 bundle-bound transaction plan 生成生产事务适配器的严格、不可调用合同，冻结未来真实 T1 激活所需的 adapter 清单、阶段顺序、命令 allowlist、文件事务、MQTT 控制与回退策略。

本阶段不安装任何 adapter，不 claim 授权，不提供 live apply。

## 2. 输入绑定

输入必须为 mode `0600` 的 transaction plan，并通过既有 verifier。合同必须绑定：

- transaction plan SHA-256；
- authorization 全文 SHA-256；
- readiness bundle SHA-256；
- production driver contract SHA-256；
- production executor contract SHA-256；
- mount binding SHA-256；
- runtime binding manifest SHA-256；
- production driver preflight SHA-256；
- Home Assistant target gate SHA-256。

## 3. adapter 清单

必须冻结以下 adapter，且本阶段全部保持 `installed=false`、`callable=false`：

1. authorization claim；
2. runtime revalidation；
3. complete snapshot；
4. host-file mutation；
5. Mosquitto restart；
6. Dynamic Security state wait；
7. Dynamic Security request；
8. postactivation audit；
9. rollback；
10. private journal。

每个 adapter 的 host write、Docker mutation、MQTT publish 和 authorization claim 能力均必须为 false。

## 4. 固定阶段顺序

未来执行顺序必须为：

1. claim authorization；
2. 重新验证 runtime；
3. 建立完整快照；
4. 原子修改宿主机文件；
5. 仅重启 Mosquitto；
6. 等待 Dynamic Security state；
7. 通过进程内 MQTT 发送精确 dynsec request；
8. 执行 postactivation audit；
9. 提交事务日志。

claim 后任一阶段失败均必须 rollback；rollback 失败为终止故障。

## 5. Docker 边界

仅冻结未来允许的两个命令：

```text
docker inspect mosquitto
docker restart mosquitto
```

禁止：

- shell；
- `docker exec/cp/create/start/stop/rm/run`；
- Docker Compose；
- systemd；
- SSH；
- 重启其他服务。

成功路径最多一次 Mosquitto 重启；rollback 可额外触发一次重启。

## 6. 文件事务

未来实现必须：

- claim 使用同文件系统 hardlink 后 unlink 原名称；
- 所有源文件和目标文件拒绝符号链接；
- 首次写入前建立完整快照；
- 使用同目录临时文件；
- fsync 文件；
- `os.replace` 原子替换；
- fsync 父目录；
- 保留权限和所有者；
- rollback 后校验完整快照。

## 7. MQTT 控制

Dynamic Security 控制只能使用进程内 `paho-mqtt`：

- 控制与响应 topic 使用冻结常量；
- 凭据来自 mode `0600` 绑定材料；
- request 来自 SHA-256 绑定 JSON；
- payload 只存在进程内存；
- 密码不得进入 argv、环境变量或 stdout；
- 禁止外部 MQTT CLI。

## 8. 日志与后续步骤

未来事务日志必须 mode `0600`，每阶段 append 后 fsync；禁止记录密码、token 或原始宿主机路径。

Home Assistant 官方 MQTT 重配置和真实节点凭据交付都不属于 Broker 激活事务，必须在 Broker postactivation 通过后另行执行。匿名访问不得在本事务中关闭。

## 9. 固定安全状态

合同生成和验证后必须保持：

- `production_transaction_adapters_installed=false`；
- `authorization_claimed=false`；
- `claim_enabled=false`；
- `production_executor_available=false`；
- `execution_enabled=false`；
- `apply_enabled=false`；
- `operator_action_authorized=true`；
- `ready_for_live_activation=false`；
- `current_services_modified=false`；
- `preserve_anonymous=true`；
- `anonymous_closure_enabled=false`。

## 10. 禁止入口

本阶段不得提供：

- `--claim`；
- `--execute`；
- `--apply`；
- `--live`；
- 任意宿主机路径参数。
