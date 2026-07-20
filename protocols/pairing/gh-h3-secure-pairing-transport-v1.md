# gh-h3-secure-pairing-transport-v1

## 1. 目的

定义 H3/N2 Stage 2B-1 的临时安全通道。该通道把 Stage 2A 的一次性配对会话、用户确认和 Broker 身份签发结果放入经过 QR 配对秘密认证的 X25519 + HKDF-SHA256 + ChaCha20-Poly1305 信道。

该版本冻结密码学 transcript、方向密钥、nonce、序列号、凭据密文和交付确认语义；不冻结 mDNS、UDP 或 HTTP 的最终承载端口。

## 2. 前置条件

1. manager 已创建 Stage 2A `gh.pair.offer/1`；
2. 节点与 manager 通过用户扫描或输入共享 32 字节 `PAIR_SECRET`；
3. `PAIR_SECRET` 不通过 MQTT、mDNS、UDP 广播或日志传播；
4. manager 与节点为每次配对生成新的 X25519 临时私钥；
5. 未建立本协议的 AEAD 信道前，不得发送 MQTT 密码、CA 内容或完整凭据 bundle。

## 3. Secure Offer

```json
{
  "schema": "gh.pair.secure-offer/1",
  "session_id": "UUID",
  "hardware_id": "ghw-c6-...",
  "pairing_id": "UUID",
  "manager_nonce": "32-byte-base64url",
  "manager_public_key": "32-byte-X25519-public-key-base64url",
  "cipher_suite": "X25519-HKDF-SHA256-CHACHA20-POLY1305",
  "expires_at": "UTC timestamp",
  "max_proof_attempts": 3
}
```

Secure Offer 的有效期不得晚于对应 Stage 2A pairing session。

## 4. QR 绑定的密钥交换证明

节点生成新的 X25519 临时密钥，并构造 ASCII transcript：

```text
gh.pair.secure-proof/1
<session_id>
<hardware_id>
<pairing_id>
<node_nonce>
<manager_nonce>
<manager_public_key>
<node_public_key>
<X25519-HKDF-SHA256-CHACHA20-POLY1305>
```

证明值：

```text
secure_proof = base64url_no_padding(
  HMAC-SHA256(PAIR_SECRET, transcript)
)
```

规则：

- transcript 同时绑定 manager 和 node 的临时公钥；
- 使用常量时间比较；
- 默认最多三次失败；
- 达到上限后终止底层 Stage 2A session 并清除内存秘密；
- 证明成功后，manager 在内部生成并验证 Stage 2A 原始 PoP，不把原始 PoP 发送到网络；
- X25519 共享秘密必须经过 HKDF，不得直接作为 AEAD key。

## 5. 方向密钥派生

```text
transcript_digest = SHA256(transcript)

salt = HMAC-SHA256(
  PAIR_SECRET,
  "gh.pair.secure-salt/1" || 0x00 || transcript_digest
)

key_material = HKDF-SHA256(
  input = X25519_shared_secret,
  salt = salt,
  info = "gh.pair.secure-keys/1" || 0x00 || transcript_digest,
  length = 64
)

manager_to_node_key = key_material[0:32]
node_to_manager_key = key_material[32:64]
```

不同方向必须使用不同密钥。完成派生后清除 `PAIR_SECRET` 副本和 manager 临时私钥引用。

## 6. Encrypted Envelope

```json
{
  "schema": "gh.pair.envelope/1",
  "session_id": "UUID",
  "direction": "manager_to_node",
  "sequence": 0,
  "content_type": "gh.pair.credentials/1",
  "nonce": "12-byte-base64url",
  "ciphertext": "base64url"
}
```

方向：

- `manager_to_node`
- `node_to_manager`

nonce：

```text
manager_to_node: 0x00000001 || uint64_be(sequence)
node_to_manager: 0x00000002 || uint64_be(sequence)
```

AAD 为以下 JSON 的 canonical UTF-8 编码，键排序、无空格：

```json
{
  "content_type": "...",
  "direction": "...",
  "schema": "gh.pair.envelope/1",
  "sequence": 0,
  "session_id": "..."
}
```

接收方必须严格要求下一连续序列号。认证失败、nonce 不匹配、方向错误、session 错误或 content type 错误时不得推进接收序列。

## 7. 凭据交付

manager 只有在以下条件全部成立后才加密 `gh.pair.credentials/1`：

1. Secure Proof 已通过；
2. Stage 2A PoP 已通过；
3. registration 已由用户批准并分配 NODE_ID；
4. Broker 身份签发成功；
5. secure channel 未过期。

同一 session 的凭据重试必须返回完全相同的 Encrypted Envelope，不重复签发 Broker 身份，也不消耗新的 sequence。

## 8. 加密交付确认

节点保存凭据后发送：

```json
{
  "schema": "gh.pair.delivery-ack/1",
  "node_id": "gh-n1-...",
  "credential_generation": 1,
  "stored": true
}
```

该文档必须通过 `node_to_manager` 方向 AEAD 发送。manager 校验全部字段与本次 bundle 完全一致后，才调用 Stage 2A `acknowledge_delivery` 并把 session 标记为 consumed。

未收到有效 ACK 前发生 abort 或过期，必须回滚已签发 Broker 身份。回滚失败必须显式报错。

## 9. 实现边界

本工作包提供：

- manager-side secure coordinator；
- non-production node reference；
- 加密 envelope 和重放防护；
- 凭据密文与 ACK 闭环；
- focused unit/contract tests。

本工作包不提供：

- mDNS 广播；
- UDP nonce 回退；
- HTTP/UDP 实际监听端点；
- 会话重启恢复；
- ESP32-C6 C++ 实现；
- 真实节点、M401A 或生产主机验收。

上述网络承载和固件实现属于 Stage 2B-2 / Stage 2C。
