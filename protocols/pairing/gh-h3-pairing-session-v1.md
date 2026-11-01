# gh-h3-pairing-session-v1

## 1. 目的

定义 H3 manager 在收到 `gh.pair.hello/1` 后使用的一次性配对会话核心。该版本冻结状态机、PoP transcript、凭据签发双门和回滚语义，不冻结最终网络传输封装。

## 2. 前置条件

1. `RegistrationRegistry` 已接受一个当前 pending hello；
2. 用户从节点 LCD 扫描或输入 32 字节 `PAIR_SECRET`；
3. manager 不得通过 MQTT 传播 `PAIR_SECRET`；
4. `PAIR_SECRET`、MQTT 密码和未来会话密钥不得进入日志、Git、YAML 或进程参数。

## 3. Offer

```json
{
  "schema": "gh.pair.offer/1",
  "session_id": "UUID",
  "hardware_id": "ghw-c6-...",
  "pairing_id": "UUID",
  "manager_nonce": "32-byte-unpadded-base64url",
  "expires_at": "UTC timestamp",
  "max_proof_attempts": 3
}
```

会话有效期不得晚于 pending registration 的有效期。

## 4. PoP transcript

按 ASCII 和换行符拼接：

```text
gh.pair.proof/1
<session_id>
<hardware_id>
<pairing_id>
<node_nonce>
<manager_nonce>
```

证明值：

```text
proof = base64url_no_padding(
  HMAC-SHA256(PAIR_SECRET, transcript)
)
```

规则：

- 使用常量时间比较；
- 默认最多三次失败；
- 达到上限后清除内存秘密并锁定；
- 成功后同一 proof 不得再次消费；
- 同一 pairing ID 只能创建一个 manager session。

## 5. 凭据签发双门

Broker 凭据只在以下条件全部成立时签发：

1. PoP 已验证；
2. 持久 registration 已由用户明确批准；
3. NODE_ID 已分配；
4. session 未过期；
5. 该 session 尚未消费。

签发复用正式 `NodeProvisioningPlan` 和 `DynsecProvisioner`。

## 6. 交付状态

```text
open
→ proof_verified
→ credentials_issued
→ consumed
```

终止状态：

```text
failed
expired
```

- `credentials_issued` 重试必须返回同一内存 bundle，不得重复创建 Broker 身份；
- 只有收到交付确认后进入 `consumed`；
- 未确认时执行 abort 或超时必须删除已签发 Broker 身份；
- 回滚失败必须显式报错，不得伪装成功。

## 7. 凭据 bundle

```json
{
  "schema": "gh.pair.credentials/1",
  "system_id": "...",
  "node_id": "...",
  "broker_host": "...",
  "broker_port": 8883,
  "broker_tls_server_name": "...",
  "ca_pem": "...",
  "mqtt_username": "...",
  "mqtt_client_id": "...",
  "mqtt_password": "...",
  "credential_generation": 1
}
```

此文档只定义明文数据模型。最终传输必须在 Stage 2B 中放入经过 ECDH 派生的 AEAD 信道，未完成前不得用于生产凭据交付。

## 8. 安全边界

- 当前实现的 session secret 仅驻留进程内存；
- 当前版本不提供重启后的 session 恢复；
- 当前版本不实现 mDNS、UDP、HTTP、ECDH 或 AEAD；
- 模拟和 CI 通过不能替代 ESP32-C6 实板或生产主机验收。
