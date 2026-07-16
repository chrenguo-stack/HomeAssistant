# T1 provisioning 控制身份恢复现场授权

## 授权声明

操作员于 2026-07-16 明确声明：

> 同意执行 provisioning_control_identity_password_recovery：仅轮换既有 ghs_greenhouse_provisioning 的密码，保持 username、client ID、role/ACL、anonymous、Manager、Home Assistant 与节点身份不变；允许一次 Mosquitto 受控重启及失败时自动回滚重启；不访问 Home Assistant .storage，不下发节点凭据，不升级生产镜像。

## 授权范围

- 仅允许替换既有 `ghs_greenhouse_provisioning` 客户端的 `encoded_password`；
- 保持 `gh-provisioning-greenhouse` client ID 与 `gh-service-greenhouse-provisioning` role/ACL；
- 允许一次 Mosquitto 受控停止、状态替换和启动；
- 验证失败时允许恢复原始状态并再次启动 Mosquitto；
- 必须保持 anonymous 开启；
- 禁止修改 Manager、Home Assistant、节点身份或下发节点凭据；
- 禁止访问 Home Assistant `.storage`；
- 禁止升级或替换生产 Manager/Mosquitto/Home Assistant 镜像；
- 授权不得用于 Home Assistant 密码轮换、节点迁移或 anonymous 关闭；
- 现场执行器必须一次性、固定私有输出目录、防重放并失败闭锁。
