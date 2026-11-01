# 节点 MQTT 认证与 anonymous 回退参考模型 V1

## 1. 目的

本合同在 V96 同步重连证据和节点固件能力门之后，冻结候选固件的认证状态机、失败分类、回退策略和隔离故障矩阵。

当前阶段只建立纯模型、测试和实现接口，不连接生产 T1，不生成或下发节点凭据，不升级生产节点固件，不访问 Home Assistant `.storage`，不关闭 anonymous。

## 2. 基线绑定

```text
repository_base=f9ac6ebbbca05fbf7c1f49d30a2d6fb6bd56ba44
manager_source_version=0.4.89
system_id=greenhouse
node_id=gh-n1-a9f2f8
target_username=ghn_gh-n1-a9f2f8
target_client_id=gh-n1-a9f2f8
generation=1
```

V96 已证明现有节点仍通过 anonymous 稳定运行，且其历史运行时 Client ID 与目标固定 Client ID 不同。因此候选固件必须显式切换 Client ID，不能继承历史自动值。

## 3. 固定状态

```text
LEGACY_ANONYMOUS
CANDIDATE_STAGED
CANDIDATE_CONNECTING
AUTHENTICATED_OBSERVATION
FALLBACK_ANONYMOUS
COMMITTED
```

约束：

- anonymous fallback 在所有状态中必须存在；
- candidate 只保存代际、目标 username、目标 Client ID、秘密存在标志和不可逆指纹；
- 公共诊断不得包含密码或可恢复秘密；
- candidate 激活和迁移提交是两个独立授权动作；
- 激活前和提交前均默认 fail-closed；
- MQTT 故障不得破坏传感器采集、LCD 五页、RS485、电源保护或本地告警。

## 4. 默认策略

```text
auth_failure_threshold=3
observation_success_threshold=3
retry_cooldown_s=300
```

语义：

- 明确的认证拒绝累计到 3 次后自动进入 `FALLBACK_ANONYMOUS`；
- DNS、TCP、Wi-Fi、Broker 不可达等传输故障立即回退，但不消耗认证拒绝计数；
- 认证成功后必须完成至少 3 个连续观察周期，才允许单独请求提交授权；
- 回退后 candidate 保留，至少等待 300 秒才能再次受控激活；
- 未提交状态重启后优先恢复 anonymous；
- 已提交状态重启后以 candidate 为主连接，同时继续保留 anonymous fallback。

## 5. 事件与转移

### 5.1 Candidate 激活

```text
CANDIDATE_STAGED|FALLBACK_ANONYMOUS
  -- ACTIVATE + explicit authorization --> CANDIDATE_CONNECTING
```

没有精确授权时必须拒绝激活。

### 5.2 认证成功

```text
CANDIDATE_CONNECTING
  -- AUTH_OK --> AUTHENTICATED_OBSERVATION
```

### 5.3 认证拒绝

```text
CANDIDATE_CONNECTING
  -- AUTH_REJECTED x 1..2 --> CANDIDATE_CONNECTING
  -- AUTH_REJECTED x 3 --> FALLBACK_ANONYMOUS
```

### 5.4 传输故障

```text
CANDIDATE_CONNECTING|AUTHENTICATED_OBSERVATION|COMMITTED
  -- TRANSPORT_FAILURE --> FALLBACK_ANONYMOUS
```

### 5.5 连续性或 ACL 失败

```text
AUTHENTICATED_OBSERVATION
  -- OBSERVATION_FAILED --> FALLBACK_ANONYMOUS
```

### 5.6 提交

```text
AUTHENTICATED_OBSERVATION
  -- 3 successful observations + explicit commit authorization --> COMMITTED
```

提交授权不能由激活授权替代，也不能重放历史授权。

## 6. 隔离故障矩阵

纯模型必须覆盖并通过以下 7 类场景：

1. 正确认证、连续观察并受控提交；
2. 连续认证拒绝达到阈值后回退；
3. Broker 不可达立即回退且不消耗认证拒绝预算；
4. telemetry、availability、Discovery 或 ACL 连续性失败后回退；
5. candidate 已暂存但未提交时重启，恢复 anonymous 且保留 candidate；
6. 已提交后重启，以 candidate 为主连接并保留 fallback；
7. 公共诊断只输出布尔值、计数、代际和指纹，不输出密码。

通过结果：

```text
status=node_mqtt_auth_fallback_fault_matrix_passed
scenario_count=7
passed_scenario_count=7
candidate_firmware_reference_model_validated=true
```

## 7. ESPHome 实现路线

候选固件采用 ESPHome external component，不使用已经移除的旧式 custom component。

ESPHome MQTT 客户端现有接口可设置 username、password、固定 Client ID，并提供 enable/disable 与连接回调。候选 external component 负责：

- 从私有存储读取 candidate 和 fallback 槽；
- 在受控切换前关闭 MQTT；
- 设置对应 username、password 和 Client ID；
- 重新启用 MQTT 并根据断开原因分类；
- 执行认证拒绝计数、回退和冷却；
- 仅发布脱敏诊断；
- 不接管传感器、LCD、RS485 和本地控制主循环。

生产节点密码不得作为公开 YAML、Git 文件或公共构建输入。`secrets.yaml` 只允许用于隔离测试中的非生产秘密；生产交付仍需单独验证私有 NVS/Preferences 写入路径。

由于当前节点采用 ESP32-C6、ESP-IDF 和 ESPHome 2026.4.3，MQTT 运行时切换必须经过编译验证和真实开发板故障测试，不能只依据桌面模型认定可投产。

## 8. 当前门状态

```text
ready_for_candidate_firmware_design=true
candidate_firmware_reference_model_validated=true
ready_for_candidate_firmware_build=true
ready_for_isolated_firmware_test=false
ready_for_real_board_capability_test=false
ready_for_node_credential_generation=false
ready_for_live_apply=false
ready_for_anonymous_closure=false
```

下一阶段允许开发 external component 骨架和非生产隔离测试配置。仍禁止生产凭据生成、节点生产 OTA、T1 写操作和 anonymous 关闭。

## 9. 安全边界

- 不重放 V70、V84～V96 或任何已消耗授权；
- 不访问 Home Assistant `.storage`；
- 不生成、读取、输出或下发生产节点密码；
- 不调用生产 Dynamic Security 控制命令；
- 不修改生产 Manager、Mosquitto、Home Assistant 或节点；
- anonymous 必须继续开启；
- 所有真实节点测试必须另建回滚、只读证据和短时精确授权。
