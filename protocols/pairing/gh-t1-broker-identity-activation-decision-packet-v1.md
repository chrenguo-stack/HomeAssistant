# gh-t1-broker-identity-activation-decision-packet-v1

状态：M2.4g-5r Draft

## 1. 目的

在操作员决定是否授权真实 T1 Broker 身份激活之前，以单个只读流程重新生成并绑定所有易漂移材料，输出一份新的 activation readiness bundle 和精确授权确认字符串。

该流程不创建 authorization，不 claim authorization，不安装 production adapters，不执行 live apply。

## 2. 输入

命令接收四个显式输入：

1. activation handoff 目录；
2. inactive migration stage 目录；
3. 预期 retained topic；
4. 新建的 `greenhouse-m2-runtime-bindings-*` 私有输出目录。

输出目录必须为非符号链接目录，权限精确为 `0700`，所有材料文件权限精确为 `0600`。

## 3. 只读生成顺序

流程必须依次执行：

1. 记录 Mosquitto、greenhouse-manager、Home Assistant 的运行身份；
2. 重新生成 Home Assistant MQTT target gate；
3. 重新生成 production executor contract；
4. 重新运行 live mount gate；
5. 重新生成 production adapter skeleton；
6. 重新生成 production driver contract；
7. 捕获新的 runtime binding manifest；
8. 立即执行 production driver preflight；
9. 生成 activation readiness bundle；
10. 仅生成 bundle-bound authorization request；
11. 再次读取三个服务的运行身份并要求与开始时完全一致。

## 4. 允许的运行时读取

流程只允许读取：

- Docker container metadata；
- Home Assistant MQTT config-entry 指纹与目标连通性；
- Mosquitto bind mount 与基线配置；
- handoff、stage 和既有私有材料。

流程不得执行 Docker restart、create、start、stop、rm、cp、Compose、systemd 或 SSH 操作。

## 5. 输出

stdout 只允许包含：

- 脱敏 readiness 摘要；
- 脱敏 authorization request；
- 精确操作员确认字符串；
- PASS 与固定安全标志；
- 私有 artifact 目录路径。

不得输出：

- MQTT 密码；
- bootstrap secret；
- authorization token；
- handoff 中的凭据内容；
- Mosquitto 实际 bind-mount 路径。

## 6. 固定安全状态

成功输出必须保持：

- `OPERATOR_DECISION_REQUIRED=true`；
- `AUTHORIZATION_CREATED=false`；
- `CURRENT_SERVICES_MODIFIED=false`；
- `PRODUCTION_DRIVER_INSTALLED=false`；
- `EXECUTION_ENABLED=false`；
- `preserve_anonymous=true`；
- `anonymous_closure_enabled=false`。

## 7. 决策边界

流程输出的确认字符串仅用于向操作员展示下一步将绑定的精确 bundle 和 Broker runtime。未收到操作员明确提交该字符串前，系统不得：

- 创建 authorization；
- claim authorization；
- 生成可执行事务；
- 修改或重启 Mosquitto；
- 修改 Home Assistant；
- 写入真实 ESP32-C6 节点凭据。
