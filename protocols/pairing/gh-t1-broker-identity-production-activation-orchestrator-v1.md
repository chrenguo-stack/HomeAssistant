# T1 Broker 身份生产激活编排协议 V1

状态：M2.4g-5u Draft

## 1. 目的

本协议将短时单次授权、readiness bundle、事务计划、生产 adapter contract、executor contract、runtime binding manifest、生产 Broker driver 和事务 adapters 绑定为一个可审计的生产激活状态机。

当前模块只提供 Python 调用接口，不提供命令行 live apply 入口。

## 2. 执行请求

执行请求必须重新验证：

- authorization 当前有效、未消费且与 readiness bundle 一致；
- readiness bundle、transaction plan、adapter contract、executor contract 和 runtime manifest 的内部签名；
- 全部 SHA-256、Broker runtime fingerprint、Home Assistant binding 和 activation scope 的交叉绑定；
- transaction plan 内记录的 authorization document SHA-256 与当前授权文件完全一致。

执行确认字符串格式：

```text
EXECUTE-M2-BROKER-ACTIVATION:<bundle前16位>:<runtime fingerprint>:<adapter contract前16位>
```

缺少精确确认或 `execution_enabled=true` 时必须拒绝执行。此前仅针对 readiness bundle 给出的授权意向确认不能替代本执行确认；代码版本、运行时绑定或 adapter contract 变化后必须重新生成并重新确认。

## 3. 执行前顺序

真实写入前必须完成：

1. 建立独立 mode-0700 transaction root 和 workspace；
2. 建立 mode-0600、每阶段 fsync 的私有 journal；
3. 注入与 runtime manifest 绑定的 production Broker driver；
4. 调用 production adapters 完成 config/data 完整快照；
5. 确认快照阶段没有修改当前服务；
6. 再次验证 authorization 和全部绑定；
7. 使用同文件系统 hardlink + source unlink 原子 claim 授权；
8. 将 claimed authorization 原子标记为 consumed。

授权 claim 不可逆，不能恢复为未消费状态。

## 4. 激活顺序

claim 后顺序固定为：

1. journal `authorization_claimed`；
2. adapter mutation；
3. 验证 Mosquitto 已重启、bootstrap admin 已删除、provisioning 身份可用；
4. adapter postactivation audit；
5. 验证全部 Broker、Home Assistant 候选身份、client ID、匿名 retained 和控制 Topic 边界；
6. journal `committed`。

成功结果只表示 Broker 身份激活完成。Home Assistant 仍未重配置，实体节点凭据仍未交付，匿名兼容仍保持开启。

## 5. 故障与回退

mutation 开始后的任何异常必须：

- journal `rollback_started`；
- 调用完整 config/data snapshot rollback；
- 仅重启 Mosquitto；
- 验证 baseline config、完整 inventory、Dynamic Security state 缺失和匿名 retained 可读；
- journal `rollback_completed`。

回退失败必须 journal `rollback_failed`，并作为终止故障报告，禁止将事务标记为成功。

## 6. 安全边界

- 模块没有 CLI；
- 默认 `execution_enabled=false`；
- 不自动创建授权；
- 不修改 Home Assistant `.storage`；
- 不向实体节点写入凭据；
- 不关闭匿名访问；
- journal 和 stdout 禁止密钥及原始宿主机路径。
