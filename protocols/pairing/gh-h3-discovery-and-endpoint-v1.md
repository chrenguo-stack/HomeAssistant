# gh-h3-discovery-and-endpoint-v1

## 1. 目的

定义 H3/N2 Stage 2B-2 的局域网 Manager 发现与节点配对端点。该协议承载 Stage 2B-1 的 `gh-h3-secure-pairing/1`，不替代其 X25519、HKDF-SHA256、ChaCha20-Poly1305、序列号和加密交付确认。

## 2. 安全边界

- mDNS 与 UDP 发现只提供候选元数据，不提供 Manager 身份认证；
- UDP nonce 只用于请求—响应关联和拒绝陈旧响应，不是认证证明；
- `PAIR_SECRET` 只通过节点二维码与受信任本地 UI 输入 Manager 内存；
- `PAIR_SECRET` 不得出现在 mDNS TXT、UDP、HTTP、MQTT、日志或命令行；
- 节点 claim 必须携带基于 `PAIR_SECRET` 的 HMAC 证明，不能只凭 `hardware_id` 和 `pairing_id` 抢占会话；
- 节点凭据和 delivery ACK 必须使用 Stage 2B-1 AEAD envelope；
- 当前端点可使用局域网 HTTP，因为秘密材料保持在 AEAD 内；发现记录必须显式携带 `scheme=http|https`，不得由节点猜测；
- 正式产品仍可在后续版本增加 HTTPS，但不得改变 Stage 2B-1 内层加密要求。

## 3. Manager Candidate

```json
{
  "schema": "gh.manager.candidate/1",
  "manager_id": "manager-a",
  "system_id": "greenhouse-a",
  "host": "greenhouse.local",
  "scheme": "http",
  "port": 8443,
  "pairing_path": "/v1/pairing",
  "protocol": "gh-h3-secure-pairing/1",
  "priority": 10,
  "ttl_s": 30
}
```

规则：

- `manager_id` 表示本机 Manager 实例；
- `host` 只能是局域网地址或以 `.local` 结尾的 mDNS 名称；
- `system_id` 表示温室系统身份；
- `priority` 只用于稳定展示排序，不能用于多 Manager 自动选择；
- 同一 `manager_id` 的新观测覆盖旧观测；
- 超过 `ttl_s` 的候选必须删除；
- 候选超过一个时，节点必须进入“多主机待选择”状态，由用户显式选择。

## 4. mDNS

服务类型：

```text
_greenhouse._tcp.local.
```

TXT 字段：

- `schema`
- `manager_id`
- `system_id`
- `scheme`
- `pairing_path`
- `protocol`
- `priority`
- `ttl_s`

SRV port 为本地配对 HTTP/HTTPS 端口。A 记录提供局域网 IPv4 地址。本版本 Manager 广告器只声明 IPv4；ESP32-C6 节点端后续可扩展 IPv6 浏览，但不得改变候选选择规则。

mDNS 注册使用严格名称检查，不允许自动改名。服务名冲突必须显式失败，防止显示身份与实际 Manager 实例发生静默偏移。

## 5. UDP 回退发现

### 5.1 Query

```json
{
  "schema": "gh.discovery.query/1",
  "request_id": "UUID",
  "nonce": "32-byte-base64url",
  "hardware_id": "ghw-c6-...",
  "protocols": ["gh-h3-secure-pairing/1"]
}
```

### 5.2 Response

```json
{
  "schema": "gh.discovery.response/1",
  "request_id": "same UUID",
  "nonce": "same nonce",
  "candidate": {"schema": "gh.manager.candidate/1"}
}
```

规则：

- 单个 datagram 最大 1400 字节；
- 只接受 loopback、RFC1918、IPv4 link-local、IPv6 ULA/link-local 来源；
- 默认同一源地址每 60 秒最多 12 次；
- schema 和字段必须精确匹配，未知字段拒绝；
- Manager 只在协议交集包含 `gh-h3-secure-pairing/1` 时响应；
- 无效、超限或非本地请求静默丢弃，避免形成放大器；
- 响应必须原样回显 `request_id` 与 `nonce`；
- 节点只接受与当前未过期 query 完全匹配的响应。

UDP 目标端口和广播策略由部署配置冻结，不写死在协议核心。本版本实现支持绑定明确端口并由后续镜像配置选择。

## 6. 受信任 QR 导入与节点 Claim

用户扫描节点二维码后，受信任本地 UI 调用 Manager 内部接口：

```text
import_scanned_pairing(hardware_id, pairing_id, pairing_secret)
```

该调用在内存中创建 Secure Offer，并计算节点 claim 证明的期望值。

节点计算 ASCII transcript：

```text
gh.pair.claim/1
<manager_id>
<hardware_id>
<pairing_id>
```

claim 证明：

```text
claim_proof = base64url_no_padding(
  HMAC-SHA256(PAIR_SECRET, transcript)
)
```

随后节点请求：

```http
POST /v1/pairing/claim
Content-Type: application/json
```

```json
{
  "schema": "gh.pair.claim/1",
  "manager_id": "manager-a",
  "hardware_id": "ghw-c6-...",
  "pairing_id": "UUID",
  "claim_proof": "32-byte-HMAC-base64url"
}
```

规则：

- Manager 必须使用常量时间比较验证 `claim_proof`；
- `claim_proof` 必须绑定节点显式选择的 `manager_id`，不得跨 Manager 重放；
- 格式错误或证明错误返回 `403 proof_rejected`；
- 无效 claim 不得绑定源 IP、消费 session 或增加 Stage 2B-1 proof 错误计数；
- 有效 claim 响应为 `gh.pair.secure-offer/1`，不得包含 `PAIR_SECRET`；
- 首次成功 claim 将 session 绑定到节点源 IP；同一 IP 可幂等重试，其他 IP 获得冲突或不存在响应；
- session 进入 failed、expired 或 consumed 后，网络 registry 必须删除映射并清零内存中的 claim proof 摘要。

## 7. HTTP 端点

路由：

- `GET /healthz`
- `POST /v1/pairing/claim`
- `POST /v1/pairing/sessions/{session_id}/establish`
- `POST /v1/pairing/sessions/{session_id}/credentials`
- `POST /v1/pairing/sessions/{session_id}/ack`
- `POST /v1/pairing/sessions/{session_id}/abort`
- `GET /v1/pairing/sessions/{session_id}/status`

### 7.1 Establish

```json
{
  "schema": "gh.pair.establish/1",
  "node_nonce": "32-byte-base64url",
  "node_public_key": "32-byte-X25519-public-key-base64url",
  "proof": "32-byte-HMAC-base64url"
}
```

### 7.2 Credentials Request

```json
{"schema":"gh.pair.credentials-request/1"}
```

若操作人尚未批准注册并分配 NODE_ID，返回 `409 pairing_conflict`。成功响应为 `gh.pair.envelope/1`，其内容类型为 `gh.pair.credentials/1`。

### 7.3 ACK

请求体为 Stage 2B-1 `node_to_manager` 方向 `gh.pair.envelope/1`。内层内容必须是精确的 `gh.pair.delivery-ack/1`。

## 8. 资源限制

- 仅允许本地地址来源；
- POST 必须使用 `application/json`；
- 不支持 chunked request；
- body 最大 16384 字节；
- socket 读取超时 5 秒；
- 默认每源 IP 每 60 秒最多 30 个 HTTP 请求；
- UDP 与 HTTP 速率限制器默认最多跟踪 1024 个源地址，达到上限时拒绝新的来源；
- 默认最多 16 个并发处理线程，饱和时返回 503；
- 只允许 GET/POST；
- 响应设置 `Cache-Control: no-store`、`X-Content-Type-Options: nosniff` 和 `Connection: close`；
- 服务不记录请求 body、二维码秘密、凭据密文明文或密码学 key。

## 9. 生命周期

HTTP、UDP 和 mDNS 由同一个 `PairingNetworkService` 管理：

1. 启动 HTTP；
2. 启动 UDP；
3. 注册 mDNS；
4. 任一步失败，关闭已启动服务并进入 closed 状态；
5. 正常关闭时先停止 HTTP/UDP，再注销 mDNS；
6. closed 后不得重新启动同一实例。

## 10. 未完成范围

本协议与实现不包含：

- Manager 主程序默认启用；
- 生产端口、防火墙和容器网络冻结；
- 本地 UI 扫码页面；
- ESP32-C6 mDNS 浏览、UDP query 和 HTTP client；
- TLS 终止；
- session 加密持久化和进程重启恢复；
- M401A/T1/真实节点验收。

这些内容属于 Stage 2B-3 部署集成与 Stage 2C 节点固件。
