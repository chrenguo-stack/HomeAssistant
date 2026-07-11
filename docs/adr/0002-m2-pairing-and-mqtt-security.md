# ADR-0002：M2 零配置配对、运行时凭据与 MQTT 安全边界

- 状态：已接受（按用户确认采用 LCD 动态二维码）
- 日期：2026-07-11
- 关联：Issue #17、`gh-mqtt-v1`

## 1. 背景

N0.3、N1/M0 和 M1 已完成。当前真实节点通过匿名 MQTT 向 T1 发布遥测，`greenhouse-manager` 负责 canonical state、availability 和 Home Assistant Discovery。该方案只适用于受控局域网实验：

- Mosquitto 允许匿名连接；
- Broker 地址在编译期由 `secrets.yaml` 写入；
- 节点没有正式 HARDWARE_ID、注册状态和凭据生命周期；
- manager 目前无持久状态卷；
- MQTT 未启用 TLS，1883 严禁暴露到公网。

产品目标要求用户只完成 Wi-Fi 配网和一次明确的设备确认，不需要理解 MQTT、端口、Docker、账号、ACL 或证书。同时节点必须在配对失败、Broker 离线或主机损坏时继续本地采集和 LCD 显示。

## 2. 已核对的实现约束

1. ESPHome MQTT 的 broker、username 和 password 属于固件配置项。纯 YAML 适合实验，不足以实现运行时下发、双槽切换、轮换和撤销。
2. Mosquitto Dynamic Security 支持在 Broker 运行时维护 client、group、role 和 ACL。
3. ESP32-C6 可使用 ESP-IDF NVS 保存运行时配置；量产安全存储需要与 Flash Encryption/NVS Encryption 一起规划。
4. T1 上的 Mosquitto、Home Assistant 和其他服务可能共享现有 listener，M2 迁移不得直接关闭匿名访问并破坏既有服务。
5. 6 位验证码不能单独承担密钥功能，只能用于人眼核对。

参考：

- Mosquitto Dynamic Security：<https://mosquitto.org/documentation/dynamic-security/>
- Mosquitto Authentication：<https://mosquitto.org/documentation/authentication-methods/>
- ESPHome MQTT：<https://esphome.io/components/mqtt/>
- ESP32-C6 NVS Encryption：<https://docs.espressif.com/projects/esp-idf/en/stable/esp32c6/api-reference/storage/nvs_encryption.html>

## 3. 决策

### 3.1 身份分层

| 标识 | 生成方 | 是否可变 | 用途 |
|---|---|---:|---|
| `hardware_id` | 制造/首次烧录 | 否 | 标识具体硬件 |
| `node_id` | manager | 可迁移、默认稳定 | 业务 Topic 和 HA 设备身份 |
| `system_id` | greenhouse-init | 从备份恢复 | 隔离不同温室系统 |
| `manager_id` | greenhouse-init | 主机实例级 | 多主机冲突和配对归属 |

推荐 HARDWARE_ID：

```text
ghw-c6-98a316a9f2f8
```

现有真实节点迁移时保留 `node_id=gh-n1-a9f2f8`，避免 Home Assistant 创建第二台设备。

### 3.2 设备动态生成的一次性 PoP

不在机身或包装保留固定二维码，也不在制造环节写入不可更改的长期 PoP。

节点在首次进入未配对状态时，使用 ESP32-C6 硬件随机数生成至少 128 位 `pairing_pop`：

- 与当前配对 epoch 一起写入设备 NVS；
- 只在 LCD 的配对页面显示动态二维码；
- 用户扫码后由 UI 安全地交给 manager；
- 配对成功后立即标记已消费并从可显示状态清除；
- 恢复出厂、明确重新配对或用户要求“生成新二维码”时，生成全新的 pairing_pop；
- 旧二维码和旧 pairing_pop 永久失效；
- pairing_pop 不通过 MQTT、mDNS、UDP、日志或 Home Assistant 明文发送。

为适配 128×64 LCD，二维码采用紧凑内容，不使用冗长 URL：

```text
GHP1:<hardware_id末12位>:<128-bit pairing_pop Base32>:<校验码>
```

LCD 上的 6 位短码由当前 pairing_pop 和 transcript 派生，只核对当前会话，不作为密钥。

配对成功后二维码页面必须消失。已配对设备只有在以下明确动作后才能重新显示新二维码：

1. 原 manager 下发经过认证的“进入重新配对”命令；或
2. 用户执行现有恢复出厂序列，清除 Wi-Fi/配对状态并重新生成 pairing_pop。

不保留包装二维码的后果是：若 LCD 损坏且原 manager/备份同时丢失，只能通过有线维护或重新刷写恢复；系统不得为绕过该限制而自动信任局域网设备。

### 3.3 发现与用户确认

- manager 使用 mDNS 广播，并提供 UDP 回退；
- 未配对节点只发送不含秘密的发现/hello；
- 未知节点进入 `pending`，不得自动接纳；
- 用户在 Home Assistant 配套集成或安装向导中扫码并确认；
- 发现多个 manager 时不得按 RSSI、响应速度或 ID 自动选择；
- 配对后节点记住 `manager_id`，除非撤销、迁移或恢复出厂，否则拒绝其他主机接管。

### 3.4 Bootstrap 安全会话

独立 bootstrap 命名空间：

```text
gh/bootstrap/v1/node/<hardware_id>/hello
gh/bootstrap/v1/node/<hardware_id>/challenge
gh/bootstrap/v1/node/<hardware_id>/response
gh/bootstrap/v1/node/<hardware_id>/bundle
gh/bootstrap/v1/node/<hardware_id>/ack
```

规则：

- QoS 1、不 retain；
- 带 `pairing_id`、随机 nonce、过期时间和版本；
- 除初始 hello 外必须验证 HMAC；
- bundle 必须加密，禁止明文下发密码或 CA；
- 每硬件和源地址限速，manager 限制 pending 数量。

安全会话只组合成熟原语：

1. manager 与节点各生成临时 X25519 密钥；
2. 使用 PoP 对双方公钥、nonce、hardware_id、manager_id 和 pairing_id 的完整 transcript 做 HMAC-SHA256；
3. 使用 X25519 shared secret + HKDF-SHA256 派生会话密钥；
4. 使用 AES-256-GCM 加密 credential bundle；
5. 节点校验 transcript、有效期和 GCM tag 后才写 pending 槽。

### 3.5 节点运行时组件

新增本地 ESPHome external component：`greenhouse_pairing`，负责：

- HARDWARE_ID 和 pairing PoP；
- manager 发现和多主机冲突；
- 配对状态机与安全握手；
- active/pending 两套 MQTT 凭据；
- NVS 持久化和 generation；
- 安全切换、失败回退、轮换和撤销；
- LCD 配对二维码、短码和错误状态；
- 网络失败时保持本地采集完全独立。

正式 N2 固件最终由该组件持有运行时 MQTT 连接，不长期依赖修改 ESPHome MQTT 私有字段。现有官方 `mqtt:` N1 路径在迁移期保留为功能开关和回退。

### 3.6 每节点凭据与 ACL

```text
username: ghn_<node_id>
password: 32 random bytes, base64url
client_id: <node_id>
generation: monotonic integer
```

节点默认拒绝，仅允许：

- 写自身 `gh/v1/<sid>/ingress/node/<node_id>/#`；
- 读自身 `gh/v1/<sid>/out/node/<node_id>/#`；
- 禁止写 `state/#`、`homeassistant/#`、其他节点和 Dynamic Security control Topic。

manager 使用独立服务账号。Dynamic Security 管理权限进一步拆给 provisioning service account；正常遥测进程不永久持有超范围权限。Home Assistant 使用独立账号。

### 3.7 双槽切换

节点保存 active、pending、generation、manager_id、system_id、Broker endpoint、CA 和最后成功状态，不保存秘密日志。

切换顺序：

1. manager 创建新 client/ACL；
2. bundle 写 pending；
3. 节点用 pending 建立测试连接并发布 claim；
4. manager 验证后发送 commit；
5. 节点将 pending 提升为 active；
6. manager 在宽限期后撤销旧凭据。

任何步骤失败回到 active，不影响本地功能。首次配对没有 active 时保持未配对并继续离线采集。

### 3.8 主机持久化与恢复

M2 将改变 manager 当前完全无状态设计：

- 增加专用持久卷；
- 保存注册表、node_id 映射、generation、撤销状态和审计事件；
- 秘密不进入日志、retained Topic、HA 或 Git；
- Dynamic Security 配置和 manager 注册表成对备份；
- 备份包用用户恢复密钥加密；
- T1 重装先恢复 system_id、manager_id、CA 和注册表；
- 无有效备份时不得静默生成新系统并接管旧节点。

### 3.9 TLS 分阶段启用

1. 先在受控 LAN 完成账号、ACL、注册状态机和双槽切换；
2. 再将系统 CA 和 TLS listener 加入同一 bundle；
3. 最终生产验收必须使用 TLS，明文账号+ACL 只算实验里程碑；
4. 首次 CA 信任由已经通过 PoP 认证的加密配对会话建立；
5. 处理设备时间未同步、证书续期、主机名变化和 CA 轮换。

## 4. 不采用的方案

- **全设备共享 bootstrap 密码**：单台被读出即可伪装全部设备。
- **仅使用 6 位验证码**：熵不足，容易离线穷举。
- **编译期写入每机长期 MQTT 密码**：无法零配置、轮换、撤销和恢复。
- **发现后自动信任局域网设备**：陌生设备会被静默接纳。
- **首个 PR 直接关闭匿名 listener**：可能破坏 Home Assistant、Node-RED 和现有 MQTT 用户。

## 5. 实施阶段

| 阶段 | 交付 |
|---|---|
| M2.0 | ADR、pairing 协议、威胁模型和迁移计划 |
| M2.1 | manager 注册表、模拟节点、pending/approve/reject |
| N2.1 | external component 骨架与 NVS 双槽 |
| M2.2 | Dynamic Security client/role/ACL 和签发 |
| N2.2 | 实板加密 bundle、claim、commit/rollback |
| M2.3 | 撤销、轮换、备份恢复和匿名迁移 |
| M2.4 | TLS、CA 首次信任和证书生命周期 |
| M2.5 | 多节点、越权、重放、恢复失败和 72 小时验收 |

## 6. 影响

优点：用户无需理解 MQTT；每设备可独立撤销；主机恢复有边界；Wi-Fi/LoRa 网关共享模型；现有 M1 可逐步迁移。

代价：节点侧需要 external component；manager 需要持久卷；配对 UI 需要配套集成；配对恢复依赖 LCD 或有线维护路径；TLS 和 Flash Encryption 增加制造及恢复复杂度。
