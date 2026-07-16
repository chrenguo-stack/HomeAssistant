# T1 Home Assistant MQTT 官方重配置后验收 V92

## V91 缺陷

V91 在只读预检阶段返回 `dynamic_security_not_configured`。现场 Broker 配置 SHA 与 V90 成功状态一致，Dynamic Security 状态文件、provisioning 控制身份和 anonymous 均未发生已知变化。

代码复核确认，V91 仅匹配插件路径中的 `dynamic-security`，而当前 Mosquitto 插件名称使用 `mosquitto_dynamic_security`。因此该结果属于检测器字符串匹配缺陷，不代表插件未配置。

## V92 修正

V92：

- 同时接受 `plugin` 与 `global_plugin`；
- 将插件路径中的连字符和下划线统一后再识别 Dynamic Security；
- 要求存在且仅存在一条 Dynamic Security 插件绑定；
- 要求存在且仅存在一条指向 `dynamic-security.json` 的 `plugin_opt_config_file`；
- 继续绑定既有 Broker 配置 SHA 和 Dynamic Security 状态 SHA；
- 保持 V91 的只读运行时身份、连接、错误 client ID、anonymous retained 与受保护服务稳定性检查。

## 边界

V92 不修改 Broker、Dynamic Security、Home Assistant、Manager、节点身份或任何容器；不访问 `.storage`；不打印或移动秘密；不授权 anonymous 关闭；V91 不得重放。
