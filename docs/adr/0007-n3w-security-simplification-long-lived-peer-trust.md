# ADR-0007：N3-W 安全架构简化与长期节点互信

- 状态：已接受
- 日期：2026-08-16
- 适用范围：N3-W Wi-Fi 监测节点、Manager、MQTT、ESP-NOW 单跳转发
- 基线：`ab0adabe7d66c389f0496cf6d8386832c67debfe`
- 关联：ADR-0002、ADR-0003、N3-W Product Completion S3/S4/S5

## 1. 决策摘要

现有 N3-W 安全实现已经证明了很多安全边界，但在产品完成阶段暴露出明显的工程过度设计：首次配对、运行凭据、ESP-NOW peer authorization、grant TTL、authorization epoch、key epoch、临时 X25519、Manager authority time、私有 package/sidecar/env 等机制层层叠加，使开发、测试、恢复和现场诊断成本显著高于温室监测产品本身需要承担的复杂度。

本 ADR 决定在不退化到“所有设备共用一个 MQTT 密码”的前提下，采用更简单的安全模型：

1. **出厂固件仍然完全通用、设备中立。** 出厂时不写入 NODE_ID、Manager、Home Assistant、现场 Wi-Fi、其他节点 MAC、peer 关系或客户级秘密。
2. **首次配对使用设备自己生成的一次性 Setup Secret / pairing PoP。** 不再要求首次配对使用临时 X25519 密钥交换。
3. **每台节点继续使用独立、长期有效的 MQTT 运行身份。** 节点 A 泄露不等于节点 B/C 的 MQTT 身份泄露。
4. **同一 `SYSTEM_ID` 下、已经被 Manager 正式注册且未被安全撤销的节点，默认互为可信节点。** 不再为每次 Child↔Relay 建立有限期 Manager peer grant。
5. **ESP-NOW 使用长期系统级 peer trust credential。** Manager 为每个系统维护一把 256-bit `SYSTEM_PEER_KEY`；合法节点在注册后获得当前 key 和 `PEER_TRUST_GENERATION`。正常 Wi-Fi 故障、重启、Relay 切换不会让该凭据过期。
6. **具体 Child↔Relay 的 ESP-NOW LMK 仍然是 pair-specific。** 两端根据同一个 `SYSTEM_PEER_KEY` 和双方身份确定性派生 16-byte LMK，不需要 Manager 在每次故障时在线发 grant。
7. **只有真正的安全事件才轮换系统 peer trust key。** 普通节点新增、普通断线、Wi-Fi 恢复、Relay 切换不触发轮换。
8. **秘密来源收敛为一个 canonical private store。** 不再允许同一活动实验环境长期存在多份含义不清的 `.env`、候选密码和临时 secret source-of-truth。

本 ADR 覆盖并替代 ADR-0002 中过度复杂的 bootstrap X25519 会话部分，以及当前 S5 中有限期 peer grant / endpoint ephemeral X25519 / authorization-time 驱动的 peer trust 方案。ADR-0002 中“每节点独立 MQTT 身份、动态二维码、秘密不进 Git/日志、节点独立撤销、离线本地功能不受 MQTT 影响”等原则继续有效。

## 2. 产品体验目标

用户看到的产品流程只应是：

```text
新节点开机
  → 配置 Wi-Fi
  → 扫描 LCD 动态二维码 / 明确确认设备
  → Manager 注册
  → 自动获得自己的 MQTT 身份和系统 peer trust 凭据
  → 完成
```

之后：

```text
Wi-Fi 正常
  → 节点直接 MQTT

Wi-Fi 故障
  → 节点发现附近同系统合法节点
  → 本地互相认证
  → 自动建立 ESP-NOW 加密单跳
  → 经可联网节点转发

Wi-Fi 恢复
  → 自动回到 Direct
```

用户不需要理解或输入 MQTT 用户名、MQTT 密码、LMK、key epoch、authorization epoch、grant TTL、X25519、HKDF 或 peer relationship。

## 3. 制造与首次注册

### 3.1 制造阶段

所有 Wi-Fi 监测节点使用同一份通用固件。制造阶段禁止写入：

- NODE_ID；
- SYSTEM_ID / MANAGER_ID；
- Home Assistant 信息；
- 客户 Wi-Fi；
- MQTT 账号或密码；
- 其他节点 MAC / NODE_ID；
- ESP-NOW peer relationship；
- SYSTEM_PEER_KEY；
- 每对节点 LMK。

制造测试只验证硬件、基础固件、传感器、显示、Flash 和基本无线能力。

### 3.2 一次性 Setup Secret

节点处于未注册状态时，使用 ESP32-C6 硬件随机数产生 256-bit `SETUP_SECRET`：

- 只用于当前首次注册/重新配对；
- 通过 LCD 动态二维码向现场用户展示；
- 不通过普通 MQTT、mDNS、UDP、HA entity 或日志明文广播；
- 配对成功后从可显示状态清除并标记已消费；
- 恢复出厂或明确重新配对时生成新的值。

### 3.3 简化后的 bootstrap 加密

首次注册不再建立临时 X25519 key pair。改为：

1. Manager 和节点交换随机 nonce、`pairing_id`、`hardware_id`、`manager_id`；
2. 使用 `SETUP_SECRET` 对 transcript 做 HMAC-SHA256，证明双方持有用户扫码得到的同一秘密；
3. 使用 HKDF-SHA256 从 `SETUP_SECRET + transcript` 派生一次性 256-bit bootstrap AEAD key；
4. 使用 AES-256-GCM 加密正式 credential bundle；
5. bundle 成功确认后销毁本次 bootstrap key，并消费 `SETUP_SECRET`。

这样仍然保留：身份确认、完整性、机密性、防重放和一次性配对边界；但删除了 endpoint 临时 X25519、公钥 transcript、跨语言 X25519 实现和对应的大量状态。

代价是首次配对不再提供 X25519 的前向保密。考虑到 `SETUP_SECRET` 为设备现场随机生成、一次性显示、配对成功后消费并清除，本项目接受这一权衡。

## 4. MQTT：每台设备一张长期门禁卡

Manager 在节点注册成功后，为该节点生成独立 MQTT 运行身份：

```text
node_id
client_id
username
password = 32 random bytes
credential_generation
```

规则：

- 每台节点凭据独立；
- 正常运行不轮换 generation；
- 只有显式密码轮换、凭据损坏恢复或安全事件才递增 generation；
- Broker ACL 仍然限制节点只能写自己的 ingress、读自己的 out；
- Manager、Home Assistant 继续使用独立服务身份；
- MQTT 密码不进入公共 Git、普通日志、HA entity、OTA manifest；
- 节点退役/被盗可以立即单独吊销自己的 MQTT 身份。

节点端保留 active/candidate 两槽的安全切换能力，但双槽只服务于真正的凭据轮换和恢复，不参与正常启动或每次网络重连。

## 5. ESP-NOW：长期系统互信，而不是临时搭档证

### 5.1 SYSTEM_PEER_KEY

Manager 为每个 `SYSTEM_ID` 创建并持久化：

```text
SYSTEM_PEER_KEY = 32 random bytes
PEER_TRUST_GENERATION = 1..N
```

所有已经正式注册、未被安全撤销的 N3-W 节点，在自己的安全 credential bundle 中获得当前 `SYSTEM_PEER_KEY` 和 generation。

它长期有效：

- 重启不失效；
- Wi-Fi 临时故障不失效；
- Child/Relay 角色变化不失效；
- Relay 选择变化不失效；
- 正常新增节点不要求旧节点换 key；
- 不设置 30 秒、几分钟或几小时的 peer grant TTL。

### 5.2 新增节点

新增节点 D 注册后只需得到当前系统的 `SYSTEM_PEER_KEY`：

```text
A/B/C 已持有 generation N
D 注册
  → Manager 给 D 同一个 generation N 的 SYSTEM_PEER_KEY
  → A/B/C 不需要重新刷写
  → A/B/C 不需要重新配对
  → A/B/C 不需要人工录入 D
```

因此满足“用户可随时增加新节点，旧节点无需重新刷写或人工写入新节点信息”的产品约束。

### 5.3 节点互相认证

Relay advertisement 仍只是“附近有候选节点”的不可信提示。真正建立 peer 前，双方执行一个很小的 challenge-response：

```text
Child → Relay: node_id, mac, boot_nonce, challenge
Relay → Child: node_id, mac, boot_nonce, HMAC proof
Child → Relay: HMAC proof
```

proof 使用当前 `SYSTEM_PEER_KEY`，并绑定：

- protocol domain；
- SYSTEM_ID；
- PEER_TRUST_GENERATION；
- 双方 NODE_ID；
- 双方 MAC；
- boot nonce / challenge nonce。

因此旧抓包不能直接重放建立新的 peer。

这里的“Manager 授权”发生在节点加入系统时，而不是发生在每一次 Wi-Fi 故障时。只要节点仍持有当前系统 peer credential，即视为系统成员。

### 5.4 pair-specific LMK

ESP-NOW 仍使用 per-peer 16-byte LMK，但 LMK 不再通过 endpoint X25519 临时密钥交换生成。

双方确定性派生：

```text
LMK = HKDF-SHA256(
    key = SYSTEM_PEER_KEY,
    info = domain || SYSTEM_ID || PEER_TRUST_GENERATION
           || ordered(NODE_ID_A, NODE_ID_B)
           || ordered(MAC_A, MAC_B)
)[0:16]
```

结果：

- A↔B 和 A↔C 的 LMK 不同；
- 两端无需交换 LMK；
- Manager 无需为每个 pair 存储 LMK；
- Manager 无需在每次故障时在线；
- 新节点加入不要求旧节点预先保存新节点的 MAC/LMK；
- 节点发现后即可根据双方实际身份计算 LMK。

## 6. Relay 资格与安全身份分离

“节点是否合法”和“节点此刻是否适合作为 Relay”分成两个简单问题：

### 安全身份

```text
是否属于同一 SYSTEM_ID？
是否持有当前 PEER_TRUST_GENERATION 的 SYSTEM_PEER_KEY？
```

### Relay 选择

```text
Wi-Fi 是否可用？
是否有上行？
是否 relay_capable？
电量是否过低？
是否过载？
RSSI/链路质量是否合适？
```

Relay health 继续影响“选谁转发”，但不再产生一个有限期安全 grant。这样可以删除 Manager authority-time 对每次 peer 建立的硬依赖。

## 7. 撤销、退役与 SYSTEM_PEER_KEY 轮换

需要区分普通退役和安全失陷。

### 7.1 普通故障/更换/退役

若设备只是物理损坏、正常退役且没有泄露风险：

- 单独注销该节点 MQTT 身份；
- 注册表标记 retired；
- 不要求全系统立即轮换 `SYSTEM_PEER_KEY`。

### 7.2 被盗、秘密疑似泄露、安全撤销

共享长期 peer credential 的明确代价是：某一合法节点被完整读取后，攻击者可能获得 `SYSTEM_PEER_KEY`，从而在本地 ESP-NOW 层冒充同系统成员，直到系统 peer key 轮换。

因此安全撤销执行：

1. 立即吊销失陷节点的 MQTT 凭据；
2. `PEER_TRUST_GENERATION += 1`；
3. 生成新的 `SYSTEM_PEER_KEY`；
4. 通过各节点自己的独立 MQTT 安全通道向其下发新 generation；
5. 合法节点切换后不再接受旧 generation 的 peer proof；
6. 已被吊销节点无法通过 Broker 获得新 key。

这是本简化设计最主要的安全权衡。项目接受“罕见安全失陷时进行一次系统级 peer rekey”，换取日常运行不再维护复杂的 per-pair grant/TTL/ephemeral X25519 生命周期。

## 8. 单一 canonical private source-of-truth

实验和生产都必须遵守：一个活动系统只有一个明确的 canonical secret source。

建议逻辑结构：

```text
private-store/
  system.json
  service-identities/
    manager
    homeassistant
  peer-trust/
    generation
    system-peer-key
  nodes/
    <node_id>/
      mqtt-credential
      state
  lab-only/
    tester
```

规则：

- `tester` 只属于实验室，不属于产品节点安全架构；
- 不允许通过扫描历史 `.env` 猜当前 secret；
- package 可以引用 canonical store 的一次性渲染结果，但 package 本身不反向成为新的 secret authority；
- 当前 generation 必须显式记录；
- 旧 generation 只做只读归档；
- 活动 Broker / Manager / firmware 渲染全部绑定同一 current generation。

## 9. 明确废弃的复杂机制

在新实现达到测试等价后，以下机制从 N3-W 产品 peer establishment 路径删除：

- 每次 Child↔Relay 的 endpoint ephemeral X25519；
- per-session shared secret；
- Manager finite peer grant；
- peer `authorization_id` 生命周期；
- peer grant `issued_at_ms/expires_at_ms`；
- 每次 peer 建立依赖 Manager authority Unix time；
- peer grant replay SQLite store；
- `authorization_epoch` 作为正常 peer 建立条件；
- `key_epoch` 与每次 peer grant 强绑定；
- 每次 Wi-Fi 故障都重新向 Manager 申请“临时搭档授权”。

这些内容在迁移完成前可以暂时保留在旧代码路径用于回归对照，但不得继续扩展。

## 10. 明确保留的现有能力

以下已有成果不因本 ADR 推翻：

- 通用出厂固件原则；
- registration / APPROVED / retired 身份状态；
- NODE_ID 与 HARDWARE_ID 的既有生命周期；
- 每节点独立 MQTT credential；
- Broker ACL；
- telemetry schema；
- Child→Relay reliable fragment/ACK/cache；
- Relay→MQTT unified ingress；
- Manager replay/sequence/canonical state；
- Direct/Relay path lease 与切换逻辑；
- Home Assistant identity continuity；
- 节点离线采集和 LCD 独立运行；
- OTA/恢复能力。

## 11. 生产环节影响

### 制造

更简单：所有节点刷同一固件，不产生客户 secret，不维护工厂节点表。

### 安装

更简单：用户只配 Wi-Fi 并扫描动态二维码。Manager 自动生成 NODE_ID、MQTT credential 和系统 peer credential。

### 新增设备

更简单：只给新设备发当前系统 peer credential；旧节点完全不需要重新刷写或人工更新。

### Wi-Fi 故障转发

明显更简单：节点间本地 challenge-response 后直接派生 LMK，不要求 Manager 此刻在线发有限期 grant。

### 日常维护

明显更简单：正常情况下 MQTT 密码和 SYSTEM_PEER_KEY 都长期稳定，不因重启、断网或 Relay 切换频繁轮换。

### 安全事件

比原方案更“粗粒度”：单台节点的 MQTT 身份仍可立即单独吊销；若节点秘密被盗取，则需要系统级 peer key rotation。这是有意接受的复杂度/安全权衡。

## 12. 迁移实施顺序

### Phase A：新 trust core，旧路径保持不动

- 新增纯 host 版 long-lived peer trust primitive；
- 实现 HMAC peer proof；
- 实现 deterministic pair LMK；
- 添加 test vectors；
- 旧 S5 grant path 暂不删除。

### Phase B：Manager canonical credential model

- Manager 增加 `SYSTEM_PEER_KEY` + `PEER_TRUST_GENERATION`；
- 注册成功 bundle 增加 peer trust credential；
- 新增明确的 security-revoke/rekey API；
- canonical private store 成为唯一 secret authority。

### Phase C：固件简化

- 未注册 Setup Secret + QR；
- HMAC/HKDF/AES-GCM bootstrap；
- NVS 保存长期 peer trust credential；
- ESP-NOW discovery 后本地互认证并确定性派生 LMK；
- 删除正常路径对 Manager grant/time 的依赖。

### Phase D：删除旧复杂路径

在 host、compile、双板物理和恢复测试通过后删除：

- endpoint X25519 peer handshake；
- finite grant wire/schema；
- peer grant replay store；
- authority-time-only-for-grant 依赖；
- 旧生命周期测试。

### Phase E：重新建立干净实验基线

- 新 canonical lab private root；
- 新 manager/HA/tester/node credentials；
- 新 SYSTEM_PEER_KEY generation；
- 新 Child/Relay build；
- 从零完成 Direct、Wi-Fi-loss、ESP-NOW Relay、Wi-Fi-recovery E2E；
- 不复用 R8 历史 secret 候选作为新基线。

## 13. 最低验收矩阵

必须覆盖：

1. 工厂固件不含任何节点/客户/peer 私有信息；
2. 第一次注册成功并消费 Setup Secret；
3. 新节点获得独立 MQTT 凭据；
4. 新节点获得当前 SYSTEM_PEER_KEY；
5. 新节点加入后旧节点无刷写、无重新配对、无人工 peer 配置；
6. 同系统节点 HMAC challenge-response PASS；
7. 不同 SYSTEM_ID 失败；
8. 错误 SYSTEM_PEER_KEY 失败；
9. 旧 generation 在 rekey 后失败；
10. 相同 pair 两端派生相同 LMK；
11. 不同 pair 派生不同 LMK；
12. Wi-Fi 故障时无 Manager 在线 grant 仍可建立 Relay；
13. Wi-Fi 恢复后回 Direct；
14. 单节点 MQTT revoke 不影响其他节点；
15. security revoke + system peer rekey 后被撤销节点不能获得新 generation；
16. local sensor/LCD 在所有网络失败场景继续工作。

## 14. 当前实施边界

本 ADR 只是产品架构决策和后续代码迁移依据。它不把现有 R8 私有凭据、板卡或生产环境自动转换为新方案，也不把历史 physical PASS/FAIL 重新分类。

代码迁移应从 host-only、无板卡的 primitive 和测试开始；旧 S5 physical package、旧 tester/manager secret、旧有限期 peer grant 均不得被当成新架构的 current credential source。
