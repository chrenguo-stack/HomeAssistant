# gh-t1-shadow-migration-v1 真实 Broker 影子迁移

状态：Draft / M2.3c  
关联：Issue #17、`gh-dynsec-profile-v1`

## 1. 阶段门

真实 Broker 迁移必须依次通过：

1. T1 隔离 Dynamic Security 验证；
2. 真实 T1 只读预检；
3. 配置与数据卷备份及恢复演练；
4. Dynamic Security 插件以 shadow 模式加载；
5. 创建独立 provisioning、manager、Home Assistant 和节点账号；
6. 使用影子客户端验证 ACL；
7. 单节点切换与回退；
8. 稳定观察后才评估关闭匿名访问。

禁止从“允许匿名”直接跳到“全局禁止匿名”。

## 2. 只读预检

`greenhouse-manager-t1-preflight` 只允许执行：

- 读取 mosquitto/greenhouse-manager 的运行状态、镜像和 RestartCount；
- 读取 Mosquitto 与 manager 版本；
- 读取 Mosquitto 主配置，并只输出白名单安全指令；
- 检查 Dynamic Security 插件文件是否存在。

禁止发布或订阅 MQTT、读取密码文件内容、输出容器环境变量、修改文件、重启服务或创建账号。

## 3. 报告安全

报告不得包含密码、环境变量、完整容器 inspect、遥测载荷或非白名单配置项。预检失败只返回固定 gate 和脱敏状态，不回显任意命令错误输出。

## 4. 本阶段退出条件

- 两个真实容器保持 running；
- Dynamic Security 插件文件存在；
- 当前匿名状态未被工具改变；
- 真实 Broker 尚未加载 Dynamic Security；
- 报告为 `ready=true` 后才允许生成备份/恢复演练方案。

## 5. Legacy anonymous shadow

Mosquitto 的 `allow_anonymous true` 只决定匿名客户端能否连接；加载 Dynamic Security 后，匿名 Topic 权限必须通过 anonymous group 明确授予。迁移期临时角色允许：

```text
publishClientSend    #
subscribePattern     #
publishClientReceive #
unsubscribePattern   #
subscribePattern     $SYS/#
publishClientReceive $SYS/#
unsubscribePattern   $SYS/#
```

并以更高优先级显式拒绝匿名发布或订阅 `$CONTROL/#`。由于 MQTT 的 `#` 不匹配以 `$` 开头的 Topic，`$SYS/#` 必须单独列出。

该宽权限角色只用于保持 legacy manager、Home Assistant 和节点在逐个迁移期间正常工作。它不得授予认证节点，也不得在关闭匿名访问后保留为可连接路径。隔离测试必须同时验证 legacy 应用 Topic 可用、`$SYS` 只读、`$CONTROL` 拒绝，以及每节点认证 ACL 不被放宽。
