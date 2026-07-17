# ESPHome 节点 MQTT 启动配置适配器 V1

## 1. 目的

本合同把《节点 MQTT 认证与 anonymous 回退参考模型 V1》映射到 ESP32-C6、ESP-IDF 和 ESPHome 2026.4.3 的实际实现能力。

当前实现只用于源码验证、ESP32-C6 编译验证和后续非生产隔离测试。它不连接生产 T1，不生成或下发生产节点凭据，不升级生产节点固件，不修改生产 Broker、Manager 或 Home Assistant，anonymous 必须继续开启。

## 2. 上游兼容性结论

对 ESPHome 2026.4.3 源码进行精确检查后确认：

1. `MQTTClientComponent` 公开提供 `set_username()`、`set_password()`、`set_client_id()`、`enable()` 和 `disable()`；
2. ESP32 的 ESP-IDF MQTT backend 只在首次连接前调用一次 `initialize_()`，并在其中创建 `esp_mqtt_client`；
3. 后续 `disable()` 只断开连接，`enable()` 不销毁或重新初始化 backend；
4. 因此，在 MQTT backend 首次初始化后修改 username、password 或 Client ID，不能作为可靠的运行时身份切换机制；
5. ESP-IDF backend 当前把断开回调统一暴露为 `TCP_DISCONNECTED`，底层 connection-refused 信息只写入日志，没有通过公开 disconnect callback 传递。

对应的 ESPHome 2026.4.3 上游文件：

```text
esphome/components/mqtt/mqtt_client.h
esphome/components/mqtt/mqtt_client.cpp
esphome/components/mqtt/mqtt_backend_esp32.h
esphome/components/mqtt/mqtt_backend_esp32.cpp
```

结论：候选身份与 anonymous fallback 必须采用“写入期望配置—安全重启—启动前选择配置”的事务模型，不能依赖同一次运行中的 MQTT 凭据热切换。

## 3. 与抽象参考模型的映射

抽象模型仍保留以下安全语义：

- candidate 与 anonymous fallback 相互独立；
- candidate 激活必须有独立授权；
- candidate 提交必须有另一份独立授权；
- candidate 失败达到有界阈值后回退；
- 回退不得擦除 candidate；
- 未提交状态重启后优先恢复 anonymous；
- 已提交状态重启后以 candidate 为主，同时保留 anonymous fallback；
- 本地传感器、LCD、RS485 和电源保护不能依赖 MQTT 成功。

ESPHome 适配层按以下方式实现：

```text
运行期请求 candidate
  -> 只持久化 desired_profile=candidate
  -> App.safe_reboot()
  -> 适配器以 DATA 优先级先于 MQTT setup 运行
  -> 设置 candidate username/password/client_id
  -> MQTT backend 首次初始化
```

回退路径：

```text
candidate 连接连续失败达到阈值
  -> 只持久化 desired_profile=anonymous
  -> App.safe_reboot()
  -> 启动前清空 username/password
  -> 设置明确的 anonymous Client ID
  -> MQTT backend 首次初始化
```

## 4. 断开原因降级处理

ESPHome 2026.4.3 的 ESP32-IDF 公共接口不能可靠区分：

- 密码错误；
- Client ID 被拒；
- Broker 不可达；
- TCP 中断；
- Wi-Fi 短时中断。

因此本适配器明确记录：

```text
disconnect_classification=generic
failure_class=generic_candidate_connection_failure
```

认证拒绝原因不可精确归因。当前适配器不得输出“密码错误”“认证拒绝”或“传输故障”之类未经公开 API 证明的分类结论。

实现策略为：candidate 连续出现 3 次通用连接失败后，持久化 anonymous fallback 并安全重启。一次 candidate 成功连接会把失败计数清零。

这比抽象模型中的“认证拒绝计数与传输故障立即回退”更保守，也更符合 ESPHome 2026.4.3 的实际可观测能力。后续如升级 ESPHome 或扩展 backend 事件接口，必须重新建立兼容性证据后才能恢复精确分类。

## 5. 持久化边界

NVS/Preferences 中只保存固定长度、非秘密状态：

```text
magic
candidate_generation
desired_profile
candidate_failure_count
observation_success_count
committed
```

明确禁止保存：

```text
username
password
client_id
可恢复的凭据材料
```

本修订版的 candidate password 只允许通过非生产 `!secret` 注入隔离编译和测试固件。生产私有凭据写入路径仍未实现，不能用本组件直接制作生产固件。

公共诊断只允许输出：

- 当前配置类型；
- 状态阶段；
- candidate 代际；
- secret 是否存在；
- 不可逆的 16 字符指纹；
- 通用失败计数；
- 观察成功计数；
- 提交状态；
- anonymous fallback 是否存在。

不得输出 password、原始凭据或可恢复秘密。

## 6. 启动顺序合同

适配器必须使用：

```text
get_setup_priority() = setup_priority::DATA
```

ESPHome MQTT 组件使用 `setup_priority::AFTER_WIFI`。因此适配器先完成：

1. 加载并校验持久化状态；
2. 选择 candidate 或 anonymous；
3. 调用 MQTT username/password/client_id setters；
4. 注册 connect/disconnect callback；
5. 返回控制权。

随后 MQTT 组件才创建 ESP-IDF MQTT client。任何把 setters 移到 MQTT 首次初始化之后的修改都应被 CI 拒绝。

## 7. Candidate 激活与提交

### 7.1 激活

`request_candidate_activation(true)` 仅供后续隔离测试 harness 调用，并要求：

- 明确授权标志为真；
- 当前运行 anonymous；
- candidate secret 存在；
- 没有待执行重启；
- fallback 冷却期已经结束。

满足后只持久化目标状态并安全重启。它不创建授权、不验证授权签名、不生成密码，也不属于生产执行器。

### 7.2 观察

candidate 连接成功后进入 `AUTHENTICATED_OBSERVATION`。外部测试 harness 必须独立验证：

- fresh ingress；
- canonical telemetry；
- availability；
- Discovery；
- ACL；
- 现有实体身份；
- 本地传感器、LCD 和 RS485 连续运行。

每次完整观察成功才调用 `record_observation_success()`。达到 3 次只表示可以请求提交，不会自动提交。

### 7.3 提交

`request_candidate_commit(true)` 只在以下条件全部满足时成功：

- candidate 当前连接；
- 位于 `AUTHENTICATED_OBSERVATION`；
- 已有至少 3 次观察成功；
- 独立提交授权标志为真。

生产授权解析、一次性消费和现场事务仍不在本组件中。

### 7.4 回退

以下情况选择 anonymous 并安全重启：

- candidate 连续通用连接失败达到 3 次；
- 外部观察发现 continuity 或 ACL 失败；
- 测试 harness 请求 operator rollback。

回退保留 candidate 配置合同和代际。operator rollback 会清除提交标志，但不会擦除 candidate secret 本身；安全擦除仍属于后续凭据生命周期实现。

## 8. 隔离编译目标

仓库提供：

```text
firmware/esphome_rc/tests/greenhouse_mqtt_auth_compile.yml
```

该配置仅使用：

- TEST-NET 地址 `192.0.2.10`；
- `ci-node` 和 `ci-node-anon`；
- GitHub Actions 运行时生成的随机非生产 secret；
- ESP32-C6 DevKitM 和 ESP-IDF；
- ESPHome 2026.4.3。

CI 执行 `esphome config` 和 `esphome compile`，并扫描配置与编译日志，确认临时 secret 未出现在输出中。CI 结束时无条件删除临时 `secrets.yaml` 和日志。

## 9. 当前门状态

```text
boot_profile_adapter_source_implemented=true
esp32_c6_compile_validation_pending=true
isolated_runtime_fault_test_pending=true
real_board_test_pending=true
production_private_provisioning_missing=true
ready_for_node_credential_generation=false
ready_for_live_apply=false
ready_for_anonymous_closure=false
```

CI 编译通过后，只能推进非生产隔离 Broker 运行测试。真实 ESP32-C6 实板测试、生产凭据交付和首台节点迁移仍需单独通知操作者。

## 10. 安全边界

- anonymous 必须继续开启；
- 不访问 Home Assistant `.storage`；
- 不生成或下发生产节点凭据；
- 不升级生产节点固件；
- 不修改生产 T1；
- 不修改生产 Mosquitto、Manager 或 Home Assistant；
- 不调用生产 Dynamic Security 控制命令；
- 不重放 V70、V84～V96 或任何已消耗授权；
- `ready_for_live_apply=false`；
- `ready_for_anonymous_closure=false`。
