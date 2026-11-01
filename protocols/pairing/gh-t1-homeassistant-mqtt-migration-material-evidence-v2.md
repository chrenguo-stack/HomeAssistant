# T1 Home Assistant MQTT 迁移材料证据 V2

状态：M2.4i Draft

## 1. 修正原因

V1 将 Broker target 纳入 credential binding 指纹，并在在线验证前要求仅存在一个唯一候选。这会将同一 username/password/client ID 的 `mqtt-update.json` 与含 Broker target 的 `reconfigure-values.json` 错误视为两个绑定，也会被历史失效材料阻塞。

V2 将“credential identity”和“Broker target topology”分离：

- credential binding 仅由 username、password、client ID、port 构成；
- Broker target 仍由 Home Assistant 容器网络拓扑和 TCP 可达性独立验证；
- 同一 credential 的多个副本和不同 schema 表达归并为一个绑定；
- 允许保留历史材料，但只有能使用当前正确 client ID 读取 retained telemetry 的绑定才可入选；
- 必须恰有一个 live-authenticated binding，零个或多个均失败闭锁。

## 2. 选择流程

1. 在受限根目录内定位 mode `0600`、单硬链接且父目录私有的候选文件；
2. 解析允许的两个 schema；
3. 按 username、password、client ID、port 去重；
4. 过滤到当前冻结 Home Assistant username、client ID 和 1883 port；
5. 对每个候选建立临时只读订阅连接；
6. 仅保留可读取指定 retained telemetry 且 payload node identity 正确的绑定；
7. 要求恰有一个成功绑定；
8. 再次验证错误 client ID 被拒绝；
9. 独立解析 Home Assistant 到 Broker 的 target topology；
10. 复核受保护服务、Broker config 和 Dynamic Security state 全程不变。

## 3. 安全边界

与 V1 相同：

- 不读取或写入 Home Assistant `.storage`；
- 不发布 MQTT 消息；
- 不修改或重启任何容器；
- 不修改 Broker、Dynamic Security、Compose 或节点；
- 不创建、认领、消费或复用生产授权；
- 不调用生产执行器；
- 不下发节点凭据；
- 不关闭 anonymous MQTT；
- 普通输出不包含 username、password、client ID、Broker host 或源路径。

## 4. 成功边界

```text
material_evidence_verified=true
historical_or_duplicate_material_tolerated=true
broker_target_excluded_from_credential_deduplication=true
live_authenticated_binding_count=1
ready_for_homeassistant_official_reconfigure_handoff=true
ready_for_live_apply=false
operator_action_authorized=false
```
