# 节点 MQTT 运行时身份迁移方案 V1

## 1. 方案定位

本方案定义第一台真实 Wi-Fi 监测节点从 anonymous MQTT 兼容路径迁移到独立 Dynamic Security 身份所需的固件能力、凭据生命周期、事务顺序、回滚和验收边界。当前只冻结设计，不执行节点凭据生成、Broker 密码修改、节点配置或生产固件升级。

固定试点节点：

```text
system=greenhouse
node_id=gh-n1-a9f2f8
username=ghn_gh-n1-a9f2f8
client_id=gh-n1-a9f2f8
role=gh-node-greenhouse-gh-n1-a9f2f8
```

## 2. 迁移原则

1. anonymous 在整个节点试点和稳定性观察期间继续开启。
2. 节点本地传感器采集、LCD 五页显示、电源保护不得依赖 MQTT 认证成功。
3. 凭据只在 T1 私有目录与节点私有存储中存在，不进入聊天、Git、Issue、普通日志、截图或公开构建产物。
4. 先验证节点固件具备认证和回退能力，再生成新密码；不得反向安排。
5. 一次授权只覆盖一个节点、一个密码代际、一次 Broker 密码变更和一次节点交付事务。
6. 节点迁移与关闭 anonymous 是两个独立里程碑。

## 3. 节点固件能力门

节点候选固件必须在隔离环境和实板上证明：

- 支持固定 MQTT username、password、client ID；
- 密码不出现在串口日志、API 日志、崩溃转储或诊断实体中；
- 支持 `candidate` 与 `fallback` 两个连接配置槽；
- candidate 认证连续失败达到阈值后自动回到 anonymous fallback；
- fallback 不清除 candidate，便于诊断后重试；
- 认证切换不影响传感器采集、LCD、RS485 和本地告警；
- 支持确认当前激活代际，但只输出代际与指纹，不输出密码；
- 支持安全擦除退役代际；
- 重启、断电、Wi-Fi 丢失、Broker 不可达时均不会卡住本地功能。

当前 F1.0/ESPHome 运行固件尚未完成上述能力验收，因此本阶段不得生成节点新密码。

## 4. 首台节点交付方式

首台真实节点推荐使用**本地 USB 有线交付**：

1. T1 在精确授权后生成节点新密码并写入私有 handoff；
2. 操作者在受控电脑上建立一次性私有副本；
3. 通过 USB 将候选配置写入节点私有存储；
4. 节点首次认证成功后立即删除电脑临时副本；
5. 不通过现有 anonymous MQTT、Home Assistant 实体、网页参数、串口 stdout 或远程明文 API 传输密码。

OTA 可用于交付已经具备安全凭据槽的候选固件，但首个密码本身不应打入公开或可复用的 OTA 二进制。后续产品化配网可另行设计一次性 PoP/TLS 安全会话，不纳入本次 M2 试点。

## 5. 写事务顺序

仅在新的只读证据链、独立回滚和短时精确授权全部有效时执行：

1. 生成新密码代际，保存在 T1 新建私有目录（目录 `0700`、文件 `0600`）。
2. 保存 Broker 状态回滚副本及其权限、属主、SHA-256；不覆盖历史 handoff。
3. 通过 provisioning 控制身份仅轮换目标节点的密码；username、client ID、角色和 ACL 不变。
4. 使用临时验证客户端验证新密码和固定 client ID；错误 client ID 必须被拒绝。
5. 保持 anonymous 开启，确认真实节点仍通过原路径持续上报。
6. 通过本地 USB 将 candidate 代际交付给节点。
7. 节点切换 candidate；观察 Broker 精确认证连接、fresh ingress、规范 state 与 HA 实体连续性。
8. 成功后提交事务；失败则节点自动回 anonymous，并按回滚合同恢复 Broker 密码或保留已验证的新密码等待重新交付。
9. 执行只读后审计；授权立即标记 consumed，禁止重放。

## 6. 回滚模型

### 6.1 节点侧优先回滚

由于 anonymous 继续开启，首选回滚是节点自动切回 anonymous fallback。该路径不修改 retained 状态，不改变实体 identity，不要求重启 Broker、Manager 或 Home Assistant。

### 6.2 Broker 侧回滚

以下任一情况触发 Broker 密码回滚：

- 新凭据临时验证失败；
- 错误 client ID 未被拒绝；
- 节点认证连接异常占用或反复踢线；
- ACL 语义比较失败；
- Dynamic Security 出现目标密码以外的状态漂移；
- 受保护服务发生非预期重启。

回滚后必须重新验证 provisioning、Manager、Home Assistant、anonymous retained 兼容路径及目标节点匿名上报。

## 7. 首次认证验收

必须同时满足：

- Broker 日志精确显示 `client_id=gh-n1-a9f2f8` 与期望 username；
- 同一 client ID 只有一个活动连接；
- fresh ingress telemetry 持续到达；
- retained telemetry、availability、Discovery 前后身份连续；
- Home Assistant 原设备、约 20 个实体及实时数据连续；
- Manager 与 Home Assistant 认证连接不受影响；
- 节点禁止发布 `$CONTROL/#`、`homeassistant/#` 和 `gh/v1/greenhouse/state/#`；
- 节点只能发布自己的 ingress，并只能订阅自己的 out 路径；
- 节点断网、重启、错误密码和 Broker 暂停时均能回退，LCD 与采集持续；
- 未访问 Home Assistant `.storage`；
- 未升级生产 Manager、Mosquitto 或 Home Assistant 镜像；
- anonymous 仍为开启状态。

## 8. 稳定性观察与后续门

首次成功后至少完成短周期重启/断网矩阵和长周期在线观察。观察期内保留 anonymous fallback，不删除回滚材料，不进入 anonymous 关闭。

只有 Manager、Home Assistant、节点三方认证均长期稳定，且匿名回退、恢复和实体连续性均通过后，才可以单独启动“关闭 anonymous”里程碑。该里程碑必须重新建立 fresh evidence、回滚和单次精确授权。
