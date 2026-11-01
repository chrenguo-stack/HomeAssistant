# 节点 MQTT 认证隔离实验室 V1

## 1. 目的

本合同定义节点 MQTT 认证候选方案进入真实 ESP32-C6 实板测试之前的非生产隔离环境，用于验证：

- anonymous 与 candidate 两条连接路径可同时存在；
- candidate 凭据失效时 Broker 能明确拒绝；
- candidate 失效不影响 anonymous 路径；
- Broker 停止、恢复及凭据恢复具有确定结果；
- ESPHome 运行时测试固件能够编译，并只输出脱敏状态；
- 所有实验材料可完整销毁，不进入生产 T1、生产 Broker 或生产节点。

当前阶段不连接生产网络，不访问 Home Assistant `.storage`，不生成或下发生产节点凭据，不升级生产节点固件，不修改生产 T1，anonymous 必须继续开启。

## 2. 固定软件与身份

```text
Mosquitto image=eclipse-mosquitto:2.0.22
ESPHome=2026.4.3
MCU=ESP32-C6
framework=ESP-IDF
host endpoint=127.0.0.1:18883
candidate username=ghn_ci-node
candidate client ID=ci-node
anonymous client ID=ci-node-anon
observer username=gho_ci-observer
```

以上均为 CI/实验室专用身份，不得替换为生产节点 ID、生产用户名或生产密码。

## 3. 私有工作区

实验室创建时必须使用独立临时目录：

```text
workspace mode=0700
marker mode=0600
manifest mode=0600
private secret file mode=0600
Mosquitto config mode=0600
ACL mode=0600
password file mode=0600
```

私有 secret 文件只存在于临时工作区，不提交到 Git，不写入 CLI 参数，不写入公共报告。

Mosquitto password file 采用文件内转换方式：

```text
mosquitto_passwd -U /lab/passwd
```

禁止使用会把密码放入进程参数的批处理明文参数模式。转换完成后必须确认原始 candidate 与 observer 密码均未残留在 password file 中。

## 4. Broker 配置

隔离 Broker 使用：

```text
listener 1883
allow_anonymous true
persistence false
connection_messages true
log_dest stdout
password_file /lab/passwd
acl_file /lab/acl
```

容器仅映射到主机回环地址，不暴露到局域网。容器名称、用户名和密码在公共报告中只允许输出固定测试 ID或不可逆指纹；不得输出容器 ID、原始秘密或工作区路径。

## 5. ACL

节点仅允许发布与其 Client ID 绑定的实验室状态主题：

```text
pattern write lab/state/%c/#
```

测试控制主题限定为：

```text
lab/control/ci-node-anon/#
lab/control/ci-node/#
```

observer 只允许：

```text
read  lab/state/#
write lab/control/#
```

隔离环境不包含 Home Assistant Discovery、生产 canonical state、生产 ingress 或生产 control topic。

## 6. 隔离 Broker 故障矩阵

GitHub CI 必须按顺序完成：

1. 创建 secret-free 计划；
2. 创建私有工作区并启动固定版本 Mosquitto；
3. anonymous 连接并发布自身 heartbeat；
4. candidate 使用正确凭据连接并发布自身 heartbeat；
5. observer 收到两条 heartbeat；
6. 在 Broker password file 中把 candidate 替换为随机失配值；
7. candidate 使用原始私有凭据连接时被拒绝；
8. anonymous 仍能连接和发布；
9. 恢复 candidate 原始私有凭据；
10. candidate 和 anonymous 再次同时通过；
11. 停止 Broker；
12. 使用相同私有材料重新启动 Broker；
13. candidate 和 anonymous 再次同时通过；
14. 删除容器和整个私有工作区。

CI 报告必须包含以下状态：

```text
node_mqtt_isolated_lab_plan_created
node_mqtt_isolated_lab_created
node_mqtt_isolated_lab_valid_smoke_succeeded
node_mqtt_isolated_lab_candidate_invalidated
node_mqtt_isolated_lab_invalid_smoke_succeeded
node_mqtt_isolated_lab_candidate_restored
node_mqtt_isolated_lab_stopped
node_mqtt_isolated_lab_started
node_mqtt_isolated_lab_destroyed
```

每份报告必须保持：

```text
secret_values_included=false
production_execution_invoked=false
current_services_modified=false
homeassistant_storage_read=false
node_credentials_delivered=false
preserve_anonymous=true
anonymous_closure_enabled=false
ready_for_live_apply=false
ready_for_anonymous_closure=false
```

## 7. ESPHome 运行时测试固件

仓库提供：

```text
firmware/esphome_rc/tests/greenhouse_mqtt_auth_runtime.yml
```

该固件只面向隔离 Broker 和后续专用测试板。它包含：

- anonymous 启动配置；
- candidate 启动配置；
- candidate 激活测试入口；
- observation success/failure 测试入口；
-独立 commit 与 rollback 测试入口；
- 每 5 秒发布一次脱敏 heartbeat。

heartbeat 只允许包含：

```text
profile
phase
mqtt_connected
candidate_failure_count
observation_success_count
ready_for_commit
anonymous_fallback_present
candidate_secret_present
candidate_generation
candidate_secret_fingerprint
last_failure_class
secret_values_included=false
```

不得包含 password、username 原值、可恢复凭据或生产 topic。

YAML 中的 `request_candidate_activation(true)` 与 `request_candidate_commit(true)` 仅代表隔离测试 harness 已触发对应动作，不是生产授权实现。生产授权创建、签名、消费和防重放仍未实现。

## 8. ESP32-C6 编译门

专用 CI 必须同时执行：

```text
esphome config greenhouse_mqtt_auth_compile.yml
esphome compile greenhouse_mqtt_auth_compile.yml
esphome config greenhouse_mqtt_auth_runtime.yml
esphome compile greenhouse_mqtt_auth_runtime.yml
```

构建期间只生成一次性非生产 Wi-Fi 与 candidate secret，并在配置及编译日志中搜索这些随机值。出现任何值即失败。无论构建成功或失败，临时 secret 和日志都必须删除。

## 9. 与真实实板测试的边界

隔离 Broker CI 能证明：

- Broker 配置和 ACL 可运行；
- 正确/错误 candidate 凭据行为符合预期；
- anonymous 路径保持可用；
- ESP32-C6 测试固件能够编译；
- 公开报告与日志不包含临时 secret。

它不能证明：

- ESP32-C6 Preferences 在断电后的真实保持行为；
- candidate 连续失败三次后的自动安全重启和 anonymous 回退；
- Wi-Fi 断开、Broker 断开和节点断电组合故障；
- LCD、传感器、RS485 和本地计算在认证切换期间持续运行；
- 生产私有凭据写入、更新和擦除。

这些事项必须在专用测试板上完成。不得直接使用当前生产节点进行首次实验。

## 10. 当前门状态

隔离 Broker 与双配置编译全部通过后，状态应为：

```text
isolated_broker_fixture_validated=true
candidate_valid_and_invalid_paths_validated=true
anonymous_fallback_path_validated=true
runtime_test_firmware_compiled=true
isolated_runtime_fault_test_pending=true
real_board_test_pending=true
production_private_provisioning_missing=true
ready_for_node_credential_generation=false
ready_for_live_apply=false
ready_for_anonymous_closure=false
```

下一门是专用 ESP32-C6 测试板运行时故障矩阵。进入该门时才需要操作者进行烧录、断电和网络故障操作。

## 11. 安全边界

- anonymous 必须继续开启；
- 不访问 Home Assistant `.storage`；
- 不生成或下发生产节点凭据；
- 不升级生产节点固件；
- 不修改生产 T1；
- 不修改生产 Mosquitto、Manager 或 Home Assistant；
- 不调用生产 Dynamic Security 控制命令；
- 不重放 V70、V84～V96 或任何已消耗授权；
- 不把实验室随机 secret 输出到 GitHub 日志、公共 JSON 或 Git；
- `ready_for_live_apply=false`；
- `ready_for_anonymous_closure=false`。
