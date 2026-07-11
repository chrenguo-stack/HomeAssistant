# gh-t1-shadow-migration-v1 真实 Broker 影子迁移

状态：Draft / M2.3f  
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

## 6. 真实快照 shadow candidate

`greenhouse-manager-t1-shadow` 必须以已经通过 `greenhouse-manager-t1-backup verify` 的同机回退包为唯一输入，并满足以下边界：

- 使用 manifest 记录的精确 Mosquitto 镜像 ID；
- 只修改解压后的配置和数据副本；
- 候选容器使用 `--network none`，只允许容器内 loopback 探测；
- 恢复快照文件的数值 UID/GID，并使新增 Dynamic Security 文件归属于快照数据所有者；
- 管理员密码不得出现在 argv、环境变量、报告或回退包中；
- 验证 legacy anonymous 应用 Topic 发布/订阅、指定真实 retained Topic 恢复，以及匿名 `$CONTROL/#` 无法创建客户端；
- 无论成功或失败都删除候选容器；
- 不停止、重启、重建或修改当前 `mosquitto` 和 `greenhouse-manager`。

该 gate 通过只证明“当前真实配置和 retained 数据可以在隔离副本中加载 Dynamic Security 并保持 legacy 路径”；它不授权在真实 Broker 上加载插件。下一阶段仍需生成真实服务账号、执行影子客户端 ACL 验证，并准备单节点回退步骤。
