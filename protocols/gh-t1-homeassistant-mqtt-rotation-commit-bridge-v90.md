# T1 Home Assistant MQTT 轮换提交桥 V90

## 背景

V87 已通过 Dynamic Security `setClientPassword` 修改 Home Assistant MQTT 密码，并完成新凭据、错误 client ID 拒绝、provisioning 控制身份与 anonymous retained 兼容验证，但严格状态比较因顶层 `changeIndex` 从 13 增加到 14 而失败闭锁。

V89 已确认：

- 唯一非凭据差异为 `$.changeIndex`；
- `changeIndex` 从 13 增加到 14；
- clients、roles、groups 及 Home Assistant 非凭据身份字段均未变化；
- Home Assistant 新凭据可用，错误 client ID 被拒绝；
- provisioning 控制身份、anonymous 与受保护服务稳定。

## Mosquitto 官方持久化合同

Mosquitto Dynamic Security 源码在成功执行 `setClientPassword` 后调用 `dynsec__config_batch_save()`；该函数将 `changeindex` 加 1 并标记配置需要保存。配置保存时，`changeIndex` 被写入顶层 JSON。因此本次 13 到 14 的变化是密码修改产生的预期持久化修订号，不是 ACL、身份或业务策略漂移。

## V90 边界

V90 仅允许：

- 只读复核 V86/V87 私有 handoff、当前 Broker 状态与凭据探针；
- 验证唯一非凭据差异严格为 `changeIndex: 13 -> 14`；
- 备份 V87 失败 journal；
- 将 V87 journal 从 `failed_after_mutation` 更新为 `committed`；
- 标记 Home Assistant 官方界面重新配置已就绪。

V90 禁止：

- 调用任何 Dynamic Security 修改命令；
- 修改 Broker 配置或 Dynamic Security 状态；
- 重启、停止、删除或升级任何容器；
- 访问 Home Assistant `.storage`；
- 修改 Manager、provisioning、节点身份；
- 下发节点凭据或关闭 anonymous。
