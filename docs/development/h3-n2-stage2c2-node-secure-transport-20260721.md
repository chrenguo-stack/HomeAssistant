# H3/N2 Stage 2C-2 节点网络传输与安全通道开发说明

**基线：** `main = 2b676c3e6ec24c5a65fe8405d35eea3427adaafe`  
**开发分支：** `feature/h3-n2-stage2c2-node-secure-transport-20260721-v47`  
**范围：** ESP32-C6 非生产配对客户端、跨语言密码学合同、模拟端到端闭环

## 1. 本阶段目标

在 Stage 2C-1 的传输无关状态核心之上加入：

- `_greenhouse._tcp.local` mDNS Manager 服务浏览；
- 最大 1400 字节的 UDP 回退发现；
- 禁止重定向、5 秒以内超时、最大 16 KiB 响应的 HTTP 客户端；
- 与 Manager Stage 2B-1 字节级一致的 X25519、HKDF-SHA256、ChaCha20-Poly1305；
- `claim → establish → credentials → encrypted ACK` 完整模拟闭环；
- 凭据只暂存在 `RamCredentialBundle`，不写 NVS、不修改 MQTT 配置。

## 2. 网络边界

### 2.1 mDNS

- 查询 `_greenhouse._tcp.local`；
- TXT 必须精确包含 `schema/manager_id/system_id/scheme/pairing_path/protocol/priority/ttl_s`；
- 未知、重复或缺失字段拒绝；
- `pairing_path` 只允许绝对路径和 URL unreserved 字符，拒绝查询串、片段、百分号编码、空段和 `.`/`..`；
- 候选仍由 Stage 2C-1 核心执行本地地址、TTL、容量和多 Manager 显式选择规则。

### 2.2 UDP 回退

- mDNS 没有产生候选时才进入 UDP；
- query 与 response 必须完全回显当前 `request_id` 和 32 字节 nonce；
- datagram 上限 1400 字节；
- 目标只允许 limited broadcast、loopback、RFC1918 或 IPv4 link-local；
- 仅接受本地 IPv4 来源；
- 默认 3 次、有界指数退避，最多 5 次；
- 每次尝试最多处理 32 个响应，避免持续数据报导致无界接收循环；
- 无效、超限和陈旧响应不进入候选表。

### 2.3 HTTP

- 当前只执行 Stage 2B-2 已冻结的局域网 `http` bootstrap；
- `https` 候选在没有受信任 bootstrap CA 前显式拒绝，不降级猜测；
- 只发送 `application/json`；
- 禁止自动重定向；
- 默认超时 5000 ms，配置上限仍为 5000 ms；
- Content-Length 和累计响应均受 16384 字节上限约束；
- `Content-Type` 必须为 `application/json`；
- JSON 必须完整终止，未知、重复字段、尾随内容、嵌入 NUL 和 `\u0000` 拒绝；
- 不记录请求体、响应体、证明、密钥、凭据或密码。

### 2.4 调度限制

当前 mDNS、UDP 和 HTTP API 是**同步、有界的实验实现**。两个 Stage 2C-2 编译目标只创建内存 discovery context，不调用真实网络闭环。

在 Stage 2C-3 或后续生产接线前，必须把完整网络事务放入独立 FreeRTOS worker/task，并通过消息或状态快照回传 ESPHome 主循环；不得从 `loop()`、显示 lambda 或其他实时组件回调中直接执行完整配对事务。本阶段不把同步实验 API 视为生产调度接口。

## 3. 安全通道兼容合同

实现严格复用 `gh-h3-secure-pairing-transport-v1`：

1. secure proof transcript 行顺序不变；
2. `PAIR_SECRET` HMAC-SHA256 证明不变；
3. X25519 shared secret 不直接作为 AEAD key，并显式拒绝全零 shared secret；
4. salt 为 `HMAC(PAIR_SECRET, "gh.pair.secure-salt/1" || 0x00 || SHA256(transcript))`；
5. HKDF info 为 `"gh.pair.secure-keys/1" || 0x00 || SHA256(transcript)`；
6. 前 32 字节为 manager→node，后 32 字节为 node→manager；
7. nonce 使用方向前缀加 64 位大端 sequence；
8. AAD 使用键排序、无空格 canonical JSON；
9. 认证失败、方向错误、nonce 错误和重放均不推进 receive sequence，并清空调用方旧明文；
10. base64url 必须为无 padding 的 canonical 编码；
11. Manager 确认 channel established 后清除节点侧 `PAIR_SECRET`；完成或失败时清除临时密钥；
12. PSA 临时 key slot、HKDF 中间值、明文和请求证明在完成后主动覆盖。

跨语言向量由 Manager Stage 2B-1 实现生成，C++ 节点实现逐字段验证公钥、共享秘密、proof、方向密钥、凭据密文和 ACK 密文。

## 4. RAM-only 凭据

`RamCredentialBundle` 仅保存当前进程内的：

- system/node identity；
- broker host/port/TLS server name/CA；
- MQTT username/client ID/password；
- credential generation。

安全评审后进一步冻结：

- bundle 禁止复制，只允许受控移动；
- 自定义移动会复制到唯一目标后主动覆盖源对象，避免短字符串优化区残留；
- destructor、reset、失败和成功交接路径均调用覆盖清除；
- cJSON 解析树在释放前递归覆盖字符串，避免 MQTT 密码和 CA 的解析副本残留。

明确禁止：

- NVS、Preferences、文件系统或 flash 持久化；
- 调用正式 MQTT username/password setter；
- 修改 `greenhouse_mqtt_auth`；
- 切换正式 MQTT profile；
- 修改生产 RC2 YAML。

模拟闭环中的 `stored=true` 只表示本 Stage 2C-2 RAM staging 已完成，用于验证 Manager ACK 消费语义；正式 NVS 语义必须在后续阶段重新验收。

## 5. 编译目标

- 最小 ESP32-C6：`board_lab/h3_node_pairing_secure_transport/greenhouse_pairing_secure_transport_board_lab.yml`
- 完整产品板：`f1_0_rc2_h3_node_pairing_secure_transport_board_lab.yml`

两个目标均为非生产实验配置，不自动发起真实配对，不修改原生产 RC2 YAML。

## 6. 验收项目

- transport core 本地目标、路径、响应大小和重试边界测试；
- RAM credential move-only、ACK canonical JSON 和清除测试；
- Manager 生成的跨语言密码学向量；
- X25519 低阶/全零 shared secret 拒绝测试；
- AEAD 认证失败、方向错误、重放和旧明文清除测试；
- C++ 节点与实际 Manager endpoint 的 claim→establish→credentials→ACK 子进程闭环；
- 最小 ESP32-C6 编译；
- 完整 RC2 产品板编译；
- 临时秘密不出现在配置或编译日志；
- 源码扫描确认不存在 NVS 写入、正式 MQTT 切换和生产凭据。

## 7. 未完成范围

- 实板、M401A、T1、Home Assistant 或真实 Broker 测试；
- 正式异步 worker/task 调度与取消；
- 正式 NVS 双槽/原子持久化；
- 正式 MQTT profile 切换和回滚；
- LCD 第五页最终状态接线；
- HTTPS bootstrap CA 与证书生命周期。
