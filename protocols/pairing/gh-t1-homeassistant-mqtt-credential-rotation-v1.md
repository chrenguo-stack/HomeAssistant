# Home Assistant MQTT 凭据轮换合同 V1

## 目的

在 Home Assistant 明文 MQTT 密码材料因公开仓库脱敏而不可恢复时，
只轮换既有 Home Assistant Dynamic Security 客户端的密码，不改变
username、client ID、role、ACL、Manager 身份、节点身份或匿名兼容策略。

## 前置事实

- Dynamic Security 已加载且状态为已部分激活。
- Home Assistant 客户端、固定 client ID 与 role 已存在。
- Manager 已迁移，Home Assistant 与节点尚未完成运行身份迁移。
- anonymous 必须保持启用。
- Home Assistant `.storage` 不得由工具读取或写入。
- 旧明文密码不可恢复，不能把状态文件中的密码派生值视为回滚凭据。

## 授权范围

操作员必须明确授权 `homeassistant_password_only`。授权只允许：

1. 在 T1 本地生成 32 字节高熵随机密码；
2. 使用已验证的 provisioning control 身份调用
   `setClientPassword`；
3. 写入本地私有的官方 UI 重新配置交接材料；
4. 使用新凭据进行只读 retained telemetry 验证。

授权不包含：

- 关闭匿名；
- 下发节点凭据；
- 修改 Manager 身份；
- 升级生产 Manager 镜像；
- 直接修改 Home Assistant `.storage`；
- 重建 role、ACL、client ID 或 username。

## 执行门

执行前必须同时满足：

- Mosquitto、Home Assistant、Manager 均运行且重启计数为 0；
- Broker 配置与 Dynamic Security 状态为已验证的部分激活模型；
- exactly one provisioning options material 能通过 `getClient` 控制请求；
- Home Assistant 客户端绑定、role 和 client ID 精确匹配；
- anonymous 仍启用；
- 私有交接目录不存在，避免覆盖旧材料。

## 事务顺序

1. 记录受保护服务、Broker 配置和 Dynamic Security 状态指纹；
2. 生成新密码并预写 mode 0600 的待提交交接材料；
3. 通过 MQTT v5 request/response API 执行 `setClientPassword`；
4. 验证新 username/password/client ID 三元组可读取 retained telemetry；
5. 验证错误 client ID 被拒绝；
6. 验证 Dynamic Security 除目标 password 字段外完全不变；
7. 验证受保护服务未重启或重建；
8. 提交私有 journal，并输出不含秘密的结果。

## 失败与恢复

- 任何前置检查失败时不得执行密码变更。
- 密码变更后的验证失败时，事务不得声称回滚到旧密码，因为旧明文不存在。
- 应保留新密码的私有交接材料和失败 journal，以便重新验证或再次生成新密码。
- anonymous 保持启用，因此 Home Assistant 现有匿名运行路径不会因单独轮换
  尚未使用的认证身份密码而中断。
- 在 Home Assistant 官方 MQTT“重新配置”成功并完成运行后检查前，
  `homeassistant_identity_runtime_verified` 必须保持 false。

## 成功判据

- provisioning control 身份验证通过；
- `setClientPassword` 响应无错误；
- 新三元组可读取预期 retained telemetry；
- 错误 client ID 被拒绝；
- 目标 password hash 已变化；
- 非 password Dynamic Security 状态完全不变；
- 私有 UI 交接材料已创建；
- anonymous 保持开启；
- 没有服务重启、节点凭据交付或 `.storage` 访问。
