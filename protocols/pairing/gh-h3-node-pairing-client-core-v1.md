# gh-h3-node-pairing-client-core-v1

## 1. 目的

定义 H3/N2 Stage 2C-1 的 ESP32-C6 节点侧、传输无关的配对状态机和候选选择合同。

该版本用于把已冻结的 Manager 发现、claim 和安全会话协议映射为节点端状态和严格输入边界。它不实现 UDP socket、mDNS 浏览、HTTP 请求、X25519、AEAD、凭据写入或 MQTT 切换。

## 2. 产品约束

- 配对流程不得阻塞本地传感器采集、LCD 五页显示、低电保护或 RS485 读取；
- 找不到 Manager 时节点继续离线工作，不重启；
- 多个 Manager 候选不得按 priority 静默选择；
- Stage 2C-1 不改变现有 MQTT、API、OTA 或 Wi-Fi 行为；
- 配对秘密不得出现在日志、实体状态、MQTT、命令行或编译输出；
- 编译通过不等于真实网络、密码学或凭据存储验收通过。

## 3. 状态

```text
unbound
  → discovering
  → claim_ready                    # 仅一个有效候选
  → selection_required             # 多个有效候选
  → claim_ready                    # 用户显式选择
  → claim_sent
  → secure_offer_received
  → channel_established
  → credentials_staged
  → committed
```

错误状态：

- `recoverable_failure`
- `terminal_failure`

`committed` 状态不得重新开始配对，除非后续恢复出厂或受控撤销流程先清除绑定。

## 4. 发现上下文

节点开始发现时冻结：

- `request_id`：canonical UUID；
- `nonce`：32 字节无填充 base64url；
- `hardware_id`；
- protocol：`gh-h3-secure-pairing/1`。

接收候选时必须同时匹配本轮 `request_id` 和 `nonce`。不匹配的数据不得加入候选集。

发现请求 JSON：

```json
{
  "schema": "gh.discovery.query/1",
  "request_id": "UUID",
  "nonce": "32-byte-base64url",
  "hardware_id": "ghw-c6-...",
  "protocols": ["gh-h3-secure-pairing/1"]
}
```

## 5. Manager 候选

候选字段：

```json
{
  "schema": "gh.manager.candidate/1",
  "manager_id": "manager-id",
  "system_id": "greenhouse",
  "host": "manager.local",
  "scheme": "http",
  "port": 47110,
  "pairing_path": "/v1/pairing",
  "protocol": "gh-h3-secure-pairing/1",
  "priority": 100,
  "ttl_s": 120
}
```

约束：

- host 仅允许 `.local` 名称或本地 IPv4；
- scheme 仅允许 `http` 或 `https`；
- port 范围 1–65535；
- pairing path 必须为安全绝对路径；
- ttl 范围 1–3600 秒；
- exact endpoint 重复观察只刷新 TTL；
- 同一 Manager ID 的冲突 endpoint 必须保留为多个候选；
- 候选容量固定且有上限；
- 一个候选可自动解析；
- 两个及以上候选必须显式选择，priority 只用于展示排序，不构成授权。

候选过期使用无符号毫秒差值，允许 `millis()` 回绕。

## 6. Claim

claim transcript：

```text
gh.pair.claim/1
<manager_id>
<hardware_id>
<pairing_id>
```

证明：

```text
claim_proof = base64url_no_padding(
  HMAC-SHA256(PAIR_SECRET, transcript)
)
```

claim 请求：

```json
{
  "schema": "gh.pair.claim/1",
  "manager_id": "manager-id",
  "hardware_id": "ghw-c6-...",
  "pairing_id": "UUID",
  "claim_proof": "32-byte-base64url"
}
```

只有 `claim_ready` 且候选已解析时才能生成 claim。Stage 2C-1 只生成文档，不发送网络请求。

## 7. 后续安全状态入口

Stage 2C-1 只校验以下状态入口，不执行密码学：

- secure offer：session UUID、manager nonce、manager X25519 公钥、固定 cipher suite；
- channel established；
- credentials staged：NODE_ID 和非零 credential generation；
- credentials committed。

Stage 2C-2 必须用真实 X25519、HKDF-SHA256 和 ChaCha20-Poly1305 驱动这些入口，禁止通过测试方法在生产 YAML 中跳过密码学。

## 8. 秘密生命周期

- `PAIR_SECRET` 仅在组件内存中用于 claim HMAC；
- dump config 只报告 secret present，不报告内容或摘要；
- committed 后尽力覆盖并清空字符串缓冲区；
- Stage 2C-2 必须进一步定义重启恢复、NVS 加密和 factory reset 清除语义。

## 9. Stage 2C-1 验收门

- transport-independent C++ core 在主机编译并通过状态测试；
- 最小 ESP32-C6 目标编译；
- 完整 RC2 产品板目标编译；
- 配对秘密不出现在配置或编译日志；
- 源码不包含 UDP、HTTP、mDNS browse、X25519、AEAD 或 MQTT credential mutation；
- 不修改真实节点、M401A、T1、Home Assistant 或 Broker。
