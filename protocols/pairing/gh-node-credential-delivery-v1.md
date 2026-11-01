# gh-node-credential-delivery-v1

## 1. 目的

M2.4g-3 定义 ESP32-C6 节点接收、验证、切换和回退 MQTT 运行时凭据的最小闭环。

本协议只冻结节点侧状态机、持久化顺序和验证门，不向真实节点发送凭据，不修改现有 ESPHome 固件，不启用真实 Broker Dynamic Security，也不关闭匿名兼容。

## 2. 安全目标

节点凭据交付必须同时满足：

- 密码不进入 YAML、Git、OTA manifest、日志、诊断实体或 Home Assistant 状态；
- 新凭据先写入非活动槽，旧连接保持可用；
- generation 严格递增；
- 候选连接成功并确认 client ID 后才能发送 claim；
- manager 返回匹配 generation 的 commit 后才能切换活动槽；
- 活动槽指针必须原子提交；
- 旧槽在宽限期内保留，可因连接回归失败而恢复；
- 任一失败、超时或 commit 前重启都回到旧活动槽或匿名迁移路径；
- MQTT 失败不影响传感器采集、LCD 显示、阈值判断和其他本地离线功能。

## 3. 明确不采用的交付方式

禁止：

- 把 MQTT 密码编译进 ESPHome YAML 或 C++ 常量；
- 把密码写入 OTA manifest、URL query、命令行参数或普通日志；
- 通过 Home Assistant 实体、MQTT Discovery、明文 retained Topic 或普通 Web API 下发；
- 收到 bundle 后直接覆盖当前活动凭据；
- 在候选连接验证前撤销匿名或旧 generation；
- 依赖一次 OTA 成功作为凭据提交成功的证明。

## 4. 交付载荷

节点只接受已由 `gh-pairing-v1` 安全会话保护的 bundle。解密后的最小 MQTT 字段为：

```text
host
port
client_id
username
password
generation
grace_seconds
```

外层必须经过会话完整性和防重放验证。解密后的正文只允许存在于受控内存和 NVS 写入路径，不得被格式化到异常、日志或测试报告。

迁移包中的 `payload/node/<node_id>/mqtt-credentials.json` 仅是 T1 本机的暂存来源，不是允许直接复制到节点的传输格式。真实交付前必须由受控 provisioning 流程封装为安全 bundle。

## 5. 双槽持久化模型

节点使用两个凭据槽和独立元数据：

```text
credential_slot_a
credential_slot_b
active_slot
delivery_phase
rollback_slot
generation
checksum
```

槽内容至少包含 MQTT 字段、schema 和 generation。每个槽写入后必须重新读取并校验完整性摘要。

`active_slot` 是唯一决定启动时正式连接凭据的指针。不得通过先清空旧槽再写新槽实现切换。

### 5.1 状态

```text
stable
staged
verified
claim_sent
committed_grace
```

### 5.2 正常顺序

```text
stable
  → 写非活动槽并校验
staged
  → 使用候选槽建立独立 MQTT 连接
verified
  → 以候选身份发送 claim
claim_sent
  → 收到 manager 对相同 node_id/generation 的 commit
  → 原子更新 active_slot
committed_grace
  → 观察窗口通过
stable
```

宽限期结束后才允许删除旧槽，并停止节点自身的匿名/旧凭据回退尝试。Broker 全局 `allow_anonymous true` 的关闭仍是更晚的独立门。

## 6. 候选连接验证

候选连接验证必须确认：

- DNS/网络可达；
- MQTT CONNACK 成功；
- 实际 client ID 与 bundle 中 client ID 一致；
- 能向自身 ingress/register Topic 发布 claim；
- 能从自身 out/confirm Topic 收到 commit；
- generation 与硬件身份、node_id 映射一致。

仅 TCP 连接成功不等于凭据验证成功。

候选连接不得替代当前活动连接，直到 commit 完成。为避免 ESP32-C6 内存峰值，固件可以短暂暂停正式遥测发送，但必须保持本地采集和显示；验证结束后立即释放候选 MQTT client。

## 7. 原子提交与断电恢复

### 7.1 commit 前断电

若重启时状态为：

```text
staged
verified
claim_sent
```

节点必须清除 pending 元数据，继续使用原活动槽；首次迁移尚无活动槽时继续使用受控匿名兼容路径。不得自动把候选槽提升为活动槽。

### 7.2 active pointer 提交后断电

若 `active_slot` 已原子指向新槽且状态为 `committed_grace`：

- 新槽校验通过：继续使用新槽并恢复宽限期观察；
- 新槽损坏或不可读：立即恢复 `rollback_slot`；
- 没有可用 rollback 槽但仍处于首次迁移宽限期：恢复匿名迁移路径并报告非秘密错误码；
- 不得删除旧槽后再判断新槽是否可用。

### 7.3 稳定状态槽损坏

若稳定状态的活动槽校验失败：

- 停止使用损坏凭据；
- 保持全部本地功能；
- 若匿名迁移门仍存在，可进入受限恢复流程；
- 否则进入 `recovery_required`，不得静默重新配对或接受其他 manager。

## 8. 回退触发

以下情况必须回退 pending 或 committed candidate：

```text
candidate_dns_failed
candidate_connect_rejected
candidate_identity_mismatch
claim_publish_failed
claim_rejected
commit_timeout
commit_generation_mismatch
pending_slot_invalid
post_commit_connectivity_regression
boot_before_commit
active_slot_invalid
```

报告只包含错误码、generation、hardware_id 尾号和 pairing_id 前缀，不包含 host、username、password、client ID 或载荷正文。

## 9. ESPHome 当前路线

当前 F1.0/N1 节点仍基于 ESPHome。建议实现为仓库内本地 external component，而不是 YAML lambda 拼接：

```text
components/
  greenhouse_credential_store/
  greenhouse_pairing_transport/
```

`greenhouse_credential_store` 负责：

- 通过 ESP-IDF NVS API 读写两个命名槽；
- 校验 schema、generation 和摘要；
- 原子提交 `active_slot` 元数据；
- 启动恢复；
- 只向上层暴露脱敏状态和错误码。

`greenhouse_pairing_transport` 负责：

- 解密并验证 bundle；
- 创建短生命周期候选 MQTT client；
- claim/commit 协议；
- 调用 credential store 的 stage/commit/rollback；
- 与 ESPHome 主 MQTT/网络生命周期协调。

不得把运行时密码写入 ESPHome substitutions、secrets.yaml、编译日志或实体属性。

由于 ESPHome 内建 MQTT 组件主要面向静态配置，正式实现前必须验证其运行时重连和动态凭据替换能力。若不能在不重启整机、不泄露密码且不破坏现有遥测的条件下完成，则外部组件应直接使用 ESP-IDF MQTT client 管理候选与正式连接，或把本功能排入 ESP-IDF 组件化固件阶段。

## 10. ESP-IDF 后续路线

正式 ESP-IDF 组件建议拆分：

```text
gh_credential_store
gh_pairing_session
gh_mqtt_runtime
gh_local_runtime
```

其中 `gh_local_runtime` 不依赖 MQTT 状态机；网络或认证迁移失败不得阻塞传感器采集、LCD 和本地策略。

NVS 提交应使用单事务元数据更新，或等价的双记录 sequence/CRC 方案。生产实现还需评估 NVS encryption、flash encryption 和 secure boot，但这些不能替代配对会话加密和日志脱敏。

## 11. manager 对账

manager 的秘密无关生命周期账本必须与节点 ACK 对齐：

```text
bundle_stored  → pending generation 已写槽
claim_sent     → 候选身份已通过 Broker 验证
committed      → 节点 active pointer 已切换
rolled_back    → 节点仍使用旧 generation/匿名迁移路径
```

manager 只有收到 `committed` 并通过观察窗口后，才允许撤销旧 generation。若 manager 已更新账本而节点回退，必须进入 `recovery_required`，不得假定节点处于新 generation。

## 12. 验收矩阵

仓库模拟必须覆盖：

- 首次匿名→认证迁移；
- 已认证 generation N→N+1 轮换；
- generation 回退拒绝；
- 错误密码/连接拒绝；
- client ID 不匹配；
- claim 后 commit 前断电；
- active pointer 提交后断电；
- 新槽损坏；
- commit 后连接回归失败；
- 宽限期结束删除旧槽；
- 所有摘要和事件不含秘密；
- 全过程 `local_operation_available=true`。

## 13. 真实节点门

本协议和模拟测试通过后，仍必须保持：

```text
node_credential_delivery_path_unverified
ready_for_live_apply = false
```

只有完成下列独立阶段后才能移除阻断项：

1. ESPHome external component 或 ESP-IDF 组件实现；
2. 开发板离线测试和断电故障注入；
3. 使用非生产凭据的隔离 Broker 双槽迁移；
4. 真实 `gh-n1-a9f2f8` 的显式门禁 OTA；
5. 保留匿名兼容条件下完成连接、claim、commit、回退和 HA 实体不重复验证；
6. 观察窗口通过。

当前阶段不向真实节点写入任何凭据，也不授权 OTA。
