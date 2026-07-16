# Home Assistant MQTT 凭据轮换合同 V2

## 修订原因

T1 V83 只读诊断确认，当前 Mosquitto Dynamic Security 客户端对象不保存
`password` 字段，而是保存 `encoded_password`。V1 把持久化凭据字段固定为字符串
`password`，因此 V82 在任何修改之前以
`homeassistant_state_identity_binding_drift` 失败闭锁。

V2 不再假定凭据派生值的字段名或 JSON 表示类型。当前现场必须精确识别
`encoded_password`；兼容测试允许历史 `password` 字段，但同一状态中只能存在一个
受支持的凭据字段。

## 冻结范围

轮换只允许修改既有 Home Assistant Dynamic Security 客户端的密码派生材料。
以下内容必须保持不变：

- username；
- 固定 client ID；
- role 与 ACL；
- provisioning、Manager 和节点身份；
- anonymous 兼容策略；
- Home Assistant `.storage`；
- 所有容器的身份、镜像、启动时间与重启计数。

## 状态差异验证

执行前后必须：

1. 精确找到一个目标 username；
2. 目标对象中只能存在 `encoded_password` 或历史兼容 `password` 之一；
3. 前后凭据字段名必须相同；
4. 凭据材料的规范 JSON 指纹必须变化；
5. 将目标凭据值替换为固定占位符后，完整 Dynamic Security 状态必须逐项相等；
6. 新 username/password/client ID 三元组必须可读取预期 retained telemetry；
7. 错误 client ID 必须被拒绝。

凭据派生材料可以是字符串或结构化 JSON；报告不得输出其值、长度、内部键或原始
指纹，只可输出截断后的比较指纹和字段类别。

## 失败闭锁

- 前置身份、role、client ID 或状态结构不匹配时，不得尝试轮换；
- provisioning control 身份不可用时，不得发送修改请求；
- 修改请求成功后若实时认证或状态差异验证失败，不得声称回滚，因为旧明文密码已因
  公开仓库脱敏而不可恢复；
- 必须保留新密码的私有本地材料和失败 journal，以便继续恢复；
- anonymous 始终保持启用。

## 成功后状态

成功轮换只证明 Broker 中的新 Home Assistant 身份凭据有效。
在操作员通过 Home Assistant 官方 MQTT 重新配置流程提交新值，并完成只读运行后检查
之前：

- `homeassistant_identity_runtime_verified=false`；
- `homeassistant_official_reconfigure_pending=true`；
- `ready_for_anonymous_closure=false`。
