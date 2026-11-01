# gh-pairing-v1 配对与凭据生命周期协议

状态：Draft / M2.0 设计审查  
关联：ADR-0002、`gh-mqtt-v1`

## 1. 目标与角色

本协议定义发现、用户确认、PoP 证明、安全会话、NODE_ID 分配、MQTT 凭据签发、双槽提交、轮换、撤销和恢复。

- **node**：ESP32-C6 Wi-Fi 节点或 Wi-Fi 网关；
- **manager**：T1 上的 `greenhouse-manager`；
- **UI**：Home Assistant 配套集成/安装向导；
- **broker**：Mosquitto；
- **operator**：扫码和确认的用户。

普通 LoRa 子节点不直接执行本协议，由网关承载注册入口。

## 2. 标识与动态配对凭据

`hardware_id`：`ghw-<platform>-<12 lowercase hex>`，由芯片身份/首次初始化确定，恢复出厂后不变。  
`node_id`：manager 分配，同一 system 唯一。  
`pairing_id`：每次握手唯一的 128 位 UUID。  
`pairing_epoch`：每次生成新二维码时单调递增。  
`manager_id/system_id`：由 greenhouse-init 生成并从备份恢复。

不在机身或包装保存固定二维码。节点在未配对状态使用硬件随机数生成至少 128 位 `pairing_pop`，存入 NVS，并只在 LCD 显示动态二维码：

```text
GHP1:<hardware_id末12位>:<pairing_pop的Base32编码>:<校验码>
```

示例结构：

```json
{
  "version": 1,
  "hardware_id": "ghw-c6-98a316a9f2f8",
  "pairing_epoch": 3,
  "pairing_pop": "<128-bit-or-more random value>",
  "model": "greenhouse-wifi-c6"
}
```

规则：

- pairing_pop 不得出现在 Topic、日志、诊断或 Home Assistant 状态；
- 配对成功后该 pairing_pop 标记已消费，二维码页面消失；
- 恢复出厂或明确重新配对时生成全新 pairing_pop 和 epoch；
- 旧二维码不得再次被接受；
- 6 位 display_code 只做人眼核对；
- LCD 损坏且原 manager/备份丢失时，只允许有线维护或重新刷写，不允许静默接管。

## 3. 发现与多主机

Manager mDNS：`_greenhouse-manager._tcp.local`。

TXT 最小字段：

```text
proto=1
manager_id=<uuid>
system_hint=<non-secret suffix>
bootstrap_port=<port>
tls=0|1
```

mDNS 超时后节点使用带随机抖动的 UDP probe。发现多个 manager 时进入 `pending_manager_choice`，不得自动选择；只有成功完成 PoP 握手的 manager 成为 owner。

## 4. Bootstrap Topic

```text
gh/bootstrap/v1/node/<hardware_id>/hello
gh/bootstrap/v1/node/<hardware_id>/challenge
gh/bootstrap/v1/node/<hardware_id>/response
gh/bootstrap/v1/node/<hardware_id>/bundle
gh/bootstrap/v1/node/<hardware_id>/ack
```

| 项目 | 规则 |
|---|---|
| QoS | 1 |
| Retain | false |
| 配对窗口 | 仅未配对/明确重新配对 |
| 正式遥测 | 禁止 |
| PoP/密码 | 禁止明文 |
| challenge 超时 | 默认 120 秒 |
| 并发会话 | 每硬件最多 1 个 |

Bootstrap listener 只允许 bootstrap 命名空间。匿名访问仅允许用于受控 LAN 迁移；所有安全消息仍必须经过 PoP/HMAC 和会话加密。

## 5. 状态机

| 状态 | 进入 | 退出 |
|---|---|---|
| `factory` | 无 Wi-Fi；生成/恢复当前 pairing epoch | Wi-Fi 保存 |
| `discovering` | Wi-Fi 可用、无 owner | manager 候选 |
| `pending_user` | manager 收到 hello | approve/reject/timeout |
| `handshake` | UI 提供 PoP | 会话成功/失败 |
| `credential_pending` | bundle 验证成功 | claim/rollback |
| `commit_pending` | manager 收到 claim | paired/rollback |
| `paired` | active 凭据提交 | rotate/revoke/reset |
| `rotating` | 新 generation | paired/rollback |
| `revoked` | manager 撤销 | re-pair/reset |
| `recovery` | 主机恢复/迁移 | paired/manual action |

重启后从 NVS 恢复，不得跳过确认或自动清除 revoked。

## 6. 消息

### 6.1 hello：`gh.pair.hello/1`

```json
{
  "schema": "gh.pair.hello/1",
  "pairing_id": "<uuid>",
  "pairing_epoch": 3,
  "hardware_id": "ghw-c6-98a316a9f2f8",
  "model": "greenhouse-wifi-c6",
  "fw_version": "F1.0-RC2-N2.0",
  "node_nonce": "<32-byte base64url>",
  "capabilities": ["mqtt-runtime-credentials", "lcd-pairing-qr"],
  "sent_at_ms": 120345
}
```

hello 只是不可信线索，不能触发正式账号创建。其严格结构由 `schemas/gh.pair.hello-1.schema.json` 定义；未知字段一律拒绝，`node_nonce` 必须是 32 字节随机值的无填充 Base64url。

### 6.2 challenge：`gh.pair.challenge/1`

```json
{
  "schema": "gh.pair.challenge/1",
  "pairing_id": "<uuid>",
  "hardware_id": "<hardware_id>",
  "manager_id": "<uuid>",
  "system_id": "<system_id>",
  "manager_nonce": "<32-byte base64url>",
  "manager_ephemeral_pub": "<X25519 public key>",
  "expires_at": "<RFC3339>",
  "transcript_mac": "<HMAC-SHA256>"
}
```

### 6.3 response：`gh.pair.response/1`

```json
{
  "schema": "gh.pair.response/1",
  "pairing_id": "<uuid>",
  "hardware_id": "<hardware_id>",
  "node_ephemeral_pub": "<X25519 public key>",
  "display_code": "482193",
  "transcript_mac": "<HMAC-SHA256>"
}
```

display_code 只做人眼核对，不是密钥。

### 6.4 bundle：`gh.pair.bundle/1`

外层：

```json
{
  "schema": "gh.pair.bundle/1",
  "pairing_id": "<uuid>",
  "hardware_id": "<hardware_id>",
  "generation": 1,
  "nonce": "<AES-GCM nonce>",
  "ciphertext": "<base64url>",
  "tag": "<base64url>"
}
```

解密后：

```json
{
  "node_id": "gh-n1-a9f2f8",
  "system_id": "greenhouse",
  "manager_id": "<uuid>",
  "mqtt": {
    "host": "<broker host>",
    "port": 8883,
    "client_id": "gh-n1-a9f2f8",
    "username": "ghn_gh-n1-a9f2f8",
    "password": "<32 random bytes base64url>"
  },
  "trust": {
    "ca_pem": "<system CA>",
    "server_name": "<broker name>"
  },
  "generation": 1,
  "grace_seconds": 300
}
```

### 6.5 ack：`gh.pair.ack/1`

```json
{
  "schema": "gh.pair.ack/1",
  "pairing_id": "<uuid>",
  "hardware_id": "<hardware_id>",
  "node_id": "<node_id>",
  "generation": 1,
  "phase": "bundle_stored|claim_sent|committed|rolled_back",
  "reason": "ok"
}
```

## 7. 密钥派生

```text
shared = X25519(node_private, manager_public)
salt   = SHA256(pairing_pop)
info   = SHA256(canonical_transcript)
key    = HKDF-SHA256(shared, salt, info, 32)
```

challenge/response 使用 `HMAC-SHA256(pairing_pop, canonical_transcript)`。bundle 使用 AES-256-GCM，AAD 至少包含 schema、pairing_id、hardware_id、generation。

实现不得直接对任意 JSON 字符串做 HMAC；使用 canonical CBOR 或明确字段的长度前缀编码。

## 8. Claim 与 commit

```text
gh/v1/<sid>/ingress/node/<node_id>/register
gh/v1/<sid>/out/node/<node_id>/confirm
```

claim：`gh.register/1`，至少包含 node_id、hardware_id、manager_id、generation、boot_id、claim_nonce、cap_hash。

manager 验证账号身份、Topic、generation 和 hardware_id 映射后发送 commit；节点收到 commit 才将 pending 提升为 active。

## 9. ACL

节点允许：

```text
write gh/v1/<sid>/ingress/node/<node_id>/#
read  gh/v1/<sid>/out/node/<node_id>/#
```

显式禁止 state、homeassistant、`$CONTROL` 和其他 node_id。

manager 允许读取 ingress，写 state/out/homeassistant。Dynamic Security control 权限应由独立 provisioning service account 持有。

## 10. 错误码、重放与限流

错误码：

```text
ok expired user_rejected unknown_hardware pop_mismatch
transcript_invalid replay_detected multiple_managers
credential_store_failed secure_connect_failed claim_rejected
commit_timeout generation_rollback revoked recovery_required
rate_limited internal_error
```

- pairing_id 只用一次；
- nonce 至少 256 位；
- manager 保存近期 pairing_id/nonce 摘要；
- 同 hardware_id 同时一个会话；
- 失败使用 1、2、4、8、15、30、60 秒退避；
- generation 不得回退，灾难恢复例外必须用户确认；
- 日志仅记录错误码、hardware_id 尾号和 pairing_id 前缀。

## 11. 轮换、撤销与恢复

轮换顺序：创建 generation+1 → 写 pending → 测试连接 → claim → commit → 宽限期 → 撤销旧凭据。不得先撤销旧凭据。

撤销后节点停止正式 MQTT，但本地功能继续；不会自动开放重新配对。HA 保留设备并显示离线/撤销。

有备份时恢复 system_id、manager_id、CA、Dynamic Security 和注册表，节点无需重新配对。无备份时必须逐台在 LCD 生成并扫描新二维码，不得凭同一 Wi-Fi 静默接管。\n\n已配对设备的正常重新配对由原 manager 发送认证命令，节点随后生成新的 pairing epoch。原 manager 已丢失时，用户执行现有恢复出厂序列；节点清除 Wi-Fi、owner 和凭据，重新启动 Captive Portal，并生成全新动态二维码。

## 12. 现有节点迁移

```text
legacy node_id: gh-n1-a9f2f8
hardware_id: ghw-c6-98a316a9f2f8
```

1. 保留匿名 N1 和 OTA 回退；
2. N2 增加 pairing component，默认不切换；
3. manager 建立 shadow registration；
4. 用户扫码；
5. secure claim；
6. HA unique_id 保留原 node_id；
7. 确认 20 个实体不重复；
8. 最后禁止该节点匿名 ingress。

## 13. 验收

- 未扫码只能 pending，不能发布正式状态；
- 错误 PoP、重放、过期、多主机均拒绝；
- ACL 越权测试通过；
- 凭据不出现在日志、retained、HA 或 Git；
- pending 失败回退 active；
- manager/Broker/节点重启不破坏状态；
- 备份恢复无需重配；无备份必须逐台确认；
- 匿名迁移失败可恢复 N1；
- 账号+ACL 通过后再进入 TLS 生产验收；
- 72 小时无重复设备、凭据漂移或本地采集中断。
