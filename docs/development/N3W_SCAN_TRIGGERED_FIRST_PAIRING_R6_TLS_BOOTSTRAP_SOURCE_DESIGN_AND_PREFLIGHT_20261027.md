# N3-W 扫描触发首次配对 R6：TLS bootstrap source design / preflight

日期：2026-10-27  
阶段：R6 设计与源码预检  
范围：仅设计、只读源码复核、测试规划与 GitHub 归档；不进入产品源码实现，不访问 T1/Board，不合并。

## 1. 本轮结论

R6 可以进入后续源码实现阶段，但本文件本身不授权实现。

R3、R4、R5 已经建立了 R6 所需的服务端和节点前置条件：

- R3 已完成 47110 首次注册事务、identity/source 绑定的 47112 窗口、1800 秒统一事务截止时间以及 durable ledger/reconciliation；
- R4 已完成节点本地注册页面、扫码触发边界和 pending-final-ACK 优先级；
- R5 已完成扫码后才执行的 T1 发现、多 T1 明确选择，以及 selected full candidate 仅保留在节点 RAM；
- R5 的确认动作仍故意停在 `bootstrap_stage_pending`，没有 TLS bootstrap、Setup Secret 发送或 47112 pairing handoff。

R6 只补齐下面这段缺口：

```text
R5 selected candidate in RAM
-> node 与所选 T1:47110 建立 TLS
-> 在发送任何 Setup Secret 字节前校验所选 candidate 的 leaf certificate SHA-256
-> POST /v1/registration/confirm
-> 接收 exact 47112 locator + remaining deadline
-> 调用现有 SimplePairingClient 的 hello / HMAC / HKDF / encrypted credential delivery / final ACK
-> pending ACK 时使用 47110 /status 做 durable recovery
```

不建立第二套配对协议，不改变现有 HMAC/HKDF/credential bundle/final delivery-digest 语义。

## 2. fresh rebind 结果

本轮从 current main 重新绑定，未沿用旧对话结论作为源码事实。

当前 main：

```text
2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e
Merge PR #695: align R5 state and hand off to R6
```

PR #694：

- final reviewed head：`86501708eb17e3f946bb7a2abcd783db5fc3b041`
- merged：true
- merge/source main：`32c4eef68bce48ff7a379381ab0bfad60557ef57`
- final CI：16/16 SUCCESS

从 `32c4eef68...` 到 current main `2fbd0e9c...` 只增加/调整了 current-state 与 handoff 文档，没有 executable/product source drift。因此 R6 的源码起点仍是 R5 merge/source main 的实现血统。

## 3. 当前源码已经证明的接口

### 3.1 R5 节点候选

`RegistrationCandidateV1` 已包含：

- manager_id；
- system_id；
- system_id_hint；
- host；
- bootstrap port 47110；
- bootstrap path `/v1/registration/confirm`；
- TLS leaf SHA-256；
- busy；
- TTL/observed time。

R5 选中后，完整 candidate 只保存在 `selected_registration_candidate_` RAM 对象，不写 NVS，不暴露给手机。

### 3.2 当前 T1 47110 confirm

Manager 已实现：

```text
POST /v1/registration/confirm
schema = gh.registration.confirm/1
```

请求 exact fields：

```text
manager_id
system_id
hardware_id
pairing_id
setup_secret
```

成功响应已经返回：

```text
manager_id
system_id
pairing_host
pairing_port = 47112
pairing_path = /v2/pairing
expires_in_seconds
```

事务端已经保证：

- canonical TTL 恰好为 1800 秒；
- durable ACTIVE attempt 是事务开始 authority；
- exact duplicate 只能复用同一事务/同一 deadline；
- terminal pairing ID 不会被重新解释成新事务；
- expired / replay-detected 使用 terminal 语义；
- 47112 exact binding 包含 hardware_id + pairing_id + source_ip；
- 47112 每次请求仍重新检查当前 trusted product LAN。

因此 R6 不需要增加新的 T1 注册协议。

### 3.3 当前 47112 pairing

当前 `SimplifiedPairingEndpointApp` 已在 first-registration 模式中先校验：

- source IP；
- hardware ID；
- pairing ID；
- current intent 是否 active；
- shared expiry；
- durable ledger 是否与 RAM intent 一致。

只有这些检查通过后才：

```text
observe_hello()
-> mark_hello_observed()
-> import_setup_secret()
-> authorize_first_registration_deadline()
```

后续 `/begin`、`/establish`、encrypted credential bundle、final ACK 继续走既有 pairing coordinator。

### 3.4 当前 SimplePairingClient

当前客户端已经具备：

- device-generated Setup Secret；
- durable random pairing ID；
- Manager proof HMAC；
- node proof HMAC；
- HKDF bootstrap key；
- encrypted credential bundle 解密；
- peer/Broker bundle 持久化；
- final delivery digest ACK；
- terminal hello 的 ADR-0008 durable pairing-ID renewal；
- pending ACK 持久化。

真正需要拆开的只是当前 `run_once() -> discover_() -> hello -> pair` 耦合，以及 pending ACK 在 Manager restart 后只能重试旧 session、不能调用 47110 status 的缺口。

## 4. R6 节点侧结构

R6 新增一个窄职责的 bootstrap 层，不把 47110 TLS 逻辑塞进 pairing protocol。

建议源码结构：

```text
n3w_registration_bootstrap_client.h/.cpp
  - 解析/构造 47110 confirm/status 文档
  - 只理解 registration bootstrap schema
  - 不实现 HMAC/HKDF/credential pairing

n3w_esp32_registration_bootstrap_transport.h/.cpp
  - ESP32 TLS socket
  - pre-body leaf fingerprint pinning
  - bounded HTTP/1.1 POST
  - no redirect
  - bounded response

n3w_simple_pairing_client.h/.cpp
  - prepare_bootstrap()
  - pair_with_candidate()
  - resume_pending_ack()
  - recover_pending_ack_status()
  - resume_terminal_cleanup()
  - 继续承载既有 pairing cryptography

n3w_simple_product_component.h/.cpp
  - 编排 R5 candidate -> R6 bootstrap -> pairing
  - 浏览器/LCD 只接收状态，不接收 secret
```

生产实现名称允许按现有目录命名习惯微调，但职责边界不得合并成“浏览器直接调用 T1”或“新的 pairing protocol”。

## 5. 47110 TLS pinning 冻结规则

### 5.1 连接目标

只连接 R5 用户已经确认的 full candidate：

```text
candidate.host
candidate.bootstrap_port == 47110
candidate.bootstrap_path == /v1/registration/confirm
candidate.bootstrap_tls_sha256
candidate.manager_id
candidate.system_id
```

不重新用普通 manager discovery 找另一个目标，不自动换候选，不跟随 HTTP redirect。

### 5.2 pre-body pinning

顺序必须是：

```text
TCP connect
-> TLS handshake
-> 读取 peer leaf certificate DER
-> SHA-256
-> constant-time compare selected candidate fingerprint
-> exact match
-> 才允许构造/发送含 Setup Secret 的 HTTP request bytes
```

明确禁止：

- 先发 HTTP body，再事后检查证书；
- 只关闭 CN/hostname 校验；
- “接受任意证书 + 请求完成后比较 fingerprint”；
- TLS pin mismatch 后自动改连另一个 T1；
- redirect 到另一个 host/port；
- 把 fingerprint 显示给用户手工核对。

pin mismatch 必须先关闭连接，且该连接上 Setup Secret 发送字节数必须为 0。

### 5.3 HTTPS 只保护 bootstrap

47112 继续使用现有 pairing transport。其身份/密钥确认仍由 Setup Secret HMAC + HKDF + encrypted bundle 提供，不把 R6 扩大成 47112 TLS 重构。

## 6. confirm 请求和响应

### 6.1 confirm 请求

由节点内部直接生成：

```json
{
  "schema": "gh.registration.confirm/1",
  "manager_id": "<selected candidate>",
  "system_id": "<selected candidate>",
  "hardware_id": "<local hardware id>",
  "pairing_id": "<current durable pairing id>",
  "setup_secret": "<device-owned Setup Secret>"
}
```

手机、本地网页、URL、查询参数、HTML/JS 状态对象、公共日志均不得获得 `setup_secret`。

### 6.2 成功响应的严格检查

只在下列条件全部成立时进入 47112：

- schema 为 `gh.registration.confirm-result/1`；
- accepted 为 true；
- status 为 `accepted`；
- manager_id 与 selected candidate 完全相同；
- system_id 与 selected candidate 完全相同；
- pairing_host 是合法 IPv4，且仍属于节点当前 STA IPv4 子网；
- pairing_port 恰好为 47112；
- pairing_path 恰好为 `/v2/pairing`；
- expires_in_seconds 在 1..1800 内。

节点将剩余时间转换为**当前 boot 内的 monotonic deadline**：

```text
transaction_deadline_ms =
  bootstrap_response_received_now_ms
  + expires_in_seconds * 1000
```

它只是节点侧“不再继续过期事务”的保护；Manager durable deadline 仍是最终 authority。重试不得刷新这个 deadline。

成功响应生成一个仅供 pairing 使用的 `SimpleManagerCandidateV2`：

```text
manager_id = selected.manager_id
system_id  = selected.system_id
host       = pairing_host
port       = 47112
pairing_path = /v2/pairing
```

不再调用 legacy `discover_()`。

### 6.3 terminal confirm

47110 若返回：

```text
reason = expired | replay_detected
transaction_disposition = terminal
```

节点必须调用现有 durable `renew_pairing_intent_()` 语义：

- 先成功写入新 pairing ID；
- 再把 RAM 当前 ID 切到新值；
- Setup Secret 保留；
- 旧 pairing ID 不再使用；
- 返回新的注册 QR 状态；
- 后续重新扫码、发现、确认，才可建立新事务。

不得 whole-NVS reset。

### 6.4 pre-transaction failure

以下失败发生在 T1 尚未返回 accepted transaction 前：

- TLS connect 失败；
- pin mismatch；
- invalid/oversized response；
- registration_busy；
- bootstrap_unavailable；
- manager/system mismatch；
- trusted LAN 暂不可用；
- 浏览器关闭或扫描 session 过期。

这些失败不消费当前 pairing ID，不生成新 ID，不删除 Setup Secret。

为避免继续使用已经过期的 discovery 结果，R6 在一次 bootstrap 尝试失败后清除本次 selected candidate/discovery session；节点回到同一 pairing identity 对应的注册 QR，下一次由用户重新扫码/选择。

## 7. SimplePairingClient phase split

普通产品流冻结为：

```text
prepare_bootstrap()
-> R5 scan-triggered discovery / selection
-> R6 47110 bootstrap
-> pair_with_candidate(accepted_pairing_target, transaction_deadline_ms)
```

`pair_with_candidate()` 内继续使用当前已经测试过的：

```text
/hello
-> HMAC manager proof
-> /begin
-> HMAC node proof
-> /establish
-> HKDF
-> AEAD credential bundle
-> persist bundle + pending ACK
-> final ACK
```

R6 不复制这些算法，不增加第二套 session state。

现有 `run_once()` 可以暂时保留给 legacy/工程测试兼容，但普通 unregistered product loop 不得再调用它。必须有 source regression 直接证明 idle/product flow 中没有 `run_once()->discover_()` 路径。

## 8. final ACK 的成功条件

当前节点只检查“HTTP 请求成功且 status==200”，R6 必须收紧。

只有 47112 final-ACK 返回当前 pairing status schema，并明确表示已进入最终 consumed/committed success，才可以执行本地成功清理。

原因是 ADR-0011 已要求：47112 不能在 exact cross-store commit oracle 通过且 ledger durable COMMITTED 之前返回 committed-success。R6 节点不能把任意 200 或无法解析的 200 当成功。

如果 47112 ACK：

- 连接失败；
- 404/409/5xx；
- 200 但 schema/state 不符合 committed-success；

都保留 pending ACK，随后进入 47110 status recovery，而不是删除本地恢复证据。

## 9. pending-ACK 持久化升级

### 9.1 为什么必须升级

现有持久化记录只保存：

- 47112 host/port/path；
- session_id；
- delivery_digest。

这不足以在 Manager restart、session 丢失或 T1 IP 变化后安全执行 47110 status。

R6 新写入的 recovery record 必须自包含：

```text
state = ACK_PENDING | TERMINAL_CLEANUP
pairing_id
manager_id
system_id

bootstrap_host
bootstrap_port = 47110
bootstrap_tls_sha256

pairing_host
pairing_port = 47112
pairing_path = /v2/pairing
session_id
delivery_digest
```

hardware_id 不需要重复持久化；它由本机 MAC 稳定推导，并在 status 请求时使用。

记录不得保存 Setup Secret、MQTT password、application key、SYSTEM_PEER_KEY 或 CA private material。

### 9.2 on-disk versioning

当前 `pair_ack` blob 已有 magic + version + SHA-256 check。

R6 采用**新的持久化版本**写入扩展字段，同时 loader 保留旧版本识别能力：

- 新格式写入新的 version；
- 先读取 blob size/version，再按 exact version 解析；
- checksum 继续覆盖完整持久化结构；
- 旧版记录不得被当成损坏后自动删除。

旧版 pending ACK 因缺少 manager_id/bootstrap fingerprint，无法满足安全的 47110 status/relocation binding。因此兼容策略冻结为：

1. 仍允许按旧记录重试原 47112 final ACK；
2. 若旧 ACK 成功，按既有成功路径结束；
3. 若旧 ACK 不可达，不凭猜测补 fingerprint/manager identity，不进行 destructive terminal cleanup，不把 bundle 当正式 provisioned；
4. 保持 fail-closed pending 状态，留给后续专门的 legacy recovery，而不是在 R6 自动扩大信任。

R6 新事务必须全部写新格式，不产生新的 legacy pending record。

## 10. pending-ACK recovery

### 10.1 ACK_PENDING 优先于普通发现

启动时只要存在有效新格式 ACK_PENDING：

- 它优先于 ordinary registration QR/discovery；
- peer/Broker bundle 仍是 provisional；
- 不启动正常未注册节点的背景发现；
- 允许 bounded transaction recovery。

### 10.2 第一优先：原 47112 ACK

先尝试持久化的 exact：

```text
pairing_host:47112
pairing_path/sessions/<session_id>/ack
```

若得到严格 committed-success，保留 peer/Broker bundle，并执行本地 success cleanup。

否则不删除任何恢复状态，进入 47110 status。

### 10.3 第二优先：47110 status

status 请求：

```json
{
  "schema": "gh.registration.status/1",
  "manager_id": "<saved manager>",
  "system_id": "<saved system>",
  "hardware_id": "<local hardware id>",
  "pairing_id": "<saved old pairing id>",
  "delivery_digest": "<saved digest>"
}
```

它同样必须先做 leaf-fingerprint pinning，且不含 Setup Secret。

结果：

- committed / committed -> 本地 finalize success；
- rejected + expired/replay_detected + terminal -> 进入 TERMINAL_CLEANUP；
- pending/wait -> 保留 ACK_PENDING；
- unknown/wait -> 保留 ACK_PENDING；
- transport/TLS/protocol failure -> 保留 ACK_PENDING。

WAIT/UNKNOWN 绝不能触发 pairing-ID renewal、peer/Broker 删除或本地 provisioned。

### 10.4 T1 地址变化

只有在原 bootstrap_host 不可达时，pending-ACK recovery 才允许执行 bounded discovery。

重新定位候选必须同时精确匹配：

```text
manager_id
system_id
bootstrap_tls_sha256
```

只允许更新 recovery record 中的 bootstrap_host；不能接受“相同 system hint”、相同 IP、最近发现或优先级最高等弱匹配。

如果原证书已经旋转导致 fingerprint 不同，R6 自动恢复 fail closed，不替换 trust pin。

## 11. TERMINAL_CLEANUP 的掉电安全

收到 proven terminal-not-committed 后，先持久化：

```text
pending_ack.state = TERMINAL_CLEANUP
```

然后按下面顺序执行：

1. 如果当前 pairing-intent 仍等于 old pairing ID，使用现有 ADR-0008 primitive 生成并持久化 fresh pairing ID；
2. 如果 pairing-intent 已经是不同 ID，视为 renewal 已经完成，不再生成第二个；
3. 擦除 provisional Broker bundle；
4. 擦除 provisional peer bundle；
5. 最后擦除 pending-ACK recovery record；
6. Setup Secret 保留，供下一次 fresh user-confirmed transaction 使用；
7. 回到注册 QR，需要用户重新扫码/确认。

`TERMINAL_CLEANUP` marker 的优先级高于 ordinary `credentials_present` fast path。

因此任一步骤掉电后重启，都从 marker 继续幂等清理，不会出现：

```text
Manager 已回滚旧事务
但节点因为 peer/Broker 文件还在而误判“已正式配对”
```

## 12. 本地成功清理

无论成功来自：

- 47112 final ACK committed-success；
- 47110 status durable COMMITTED；

本地成功条件都一样：

1. peer/Broker bundle 必须仍完整、相互一致；
2. Setup Secret erase；
3. old pairing-intent erase；
4. pending-ACK record **最后 erase**；
5. RAM Setup Secret zeroize；
6. mark local provisioned；
7. 关闭注册 portal/discovery/bootstrap 状态；
8. 进入既有 runtime state load/MQTT 配置。

pending-ACK record 最后删除，使 success cleanup 中途掉电时仍有 durable recovery authority。

## 13. R6 产品状态编排

在 R5 的 RAM 状态上增加最小 R6 子状态即可，不再建立独立复杂状态机：

```text
WAIT_CONFIRM
-> BOOTSTRAP_TLS
-> BOOTSTRAP_CONFIRM
-> PAIRING
-> SUCCESS

可恢复 pre-transaction error
-> ERROR
-> same identity registration QR

ACK_PENDING
-> direct ACK
-> 47110 status
-> committed OR wait OR terminal cleanup
```

`bootstrap_stage_pending` 在 R6 implementation 中被真实 bootstrap 阶段替换。

手机确认后只收到“正在联机注册”；浏览器轮询 node-local status，绝不获得：

- Setup Secret；
- pairing ID；
- raw hardware ID；
- T1 IP/port；
- TLS fingerprint；
- 47112 session ID；
- delivery digest。

## 14. 超时与 bounded IO

R6 不允许 TLS/HTTP 阻塞主 loop 无界等待。

实现时必须给出独立、有限的：

- TCP connect timeout；
- TLS handshake timeout；
- request write timeout；
- response read timeout；
- max response bytes。

这些只是单次 I/O budget，不改变 Manager 的 1800 秒 transaction deadline。

一次 I/O timeout 不能刷新 transaction deadline。

## 15. Setup Secret 内存边界

设计不声称能够证明 C++/TLS/JSON 库产生的每一个不可变临时拷贝都被物理擦除。

可实现要求是：

- durable store 只有现有 device-owned Setup Secret NVS；
- 47110 HTTP 层不新增 secret NVS；
- 浏览器/portal 不持有 secret；
- 公共日志不输出请求 body；
- 可控 mutable byte buffers 在使用后清零；
- bootstrap client 对 request body 的生命周期限制在单次请求；
- Manager RAM intent 按现有 R3 规则处理；
- pairing commit 后现有 Setup Secret store 被删除并清零 RAM 主副本。

## 16. R6 implementation 预计修改面

节点：

```text
firmware/esphome_rc/components/greenhouse_n3w_core/
  n3w_registration_bootstrap_client.h/.cpp          (new)
  n3w_esp32_registration_bootstrap_transport.h/.cpp (new or equivalent)
  n3w_simple_product_component.h/.cpp
  n3w_simple_pairing_client.h/.cpp
  n3w_esp32_pairing_nvs.h/.cpp
  n3w_registration_portal.h/.cpp                    (status only, no secret)
```

测试：

```text
tests/n3w_registration/
  R6 bootstrap parser/transport contract tests
  pre-body pinning source guards
  pairing-client phase split tests
  pending-ACK v2->new-version compatibility tests
  terminal cleanup crash/reboot matrix
  product-loop no-idle-discovery regression
```

T1/Manager 产品源码原则上不需要协议扩展；R6 若发现服务端行为与已冻结 contract 不一致，只允许做当前 gate 内明确、局部、无设计歧义的修补，并必须单独证明没有扩大协议面。任何需要重新设计 47110/47112 的发现都应停止并回到设计 gate。

## 17. 必须新增/更新的测试

### A. TLS bootstrap

- selected candidate exact host/port/path only；
- exact 64-hex fingerprint；
- pin match 前 HTTP body write count == 0；
- pin mismatch 后 Setup Secret write count == 0；
- 3xx 不 follow；
- wrong manager/system success response rejected；
- wrong 47112 port/path rejected；
- invalid pairing_host rejected；
- expires_in_seconds 0、>1800 rejected；
- valid accepted response produces exact pairing target + monotonic deadline。

### B. secret boundary

- portal source/HTML/JSON 不引用 `setup_secret_base64url()`；
- phone-facing candidate/status objects不含 raw IDs/fingerprint/host；
- bootstrap request body不写日志；
- secret 不进入 pending-ACK record。

### C. pre-transaction retry

- TLS connect fail 不换 pairing ID；
- pin mismatch 不换 pairing ID；
- registration_busy 不换 pairing ID；
- bootstrap_unavailable 不换 pairing ID；
- failure 后 selected candidate 清空，需要 fresh scan/confirm；
- Setup Secret 保留。

### D. terminal bootstrap

- expired -> durable fresh pairing ID；
- replay_detected -> durable fresh pairing ID；
- NVS save failure不能把 RAM 切到未持久化 ID；
- whole-NVS erase 不可达。

### E. pairing reuse

- normal product flow调用 `pair_with_candidate`，不调用 `discover_()`；
- HMAC/HKDF/AEAD vectors unchanged；
- credentials bundle parser unchanged；
- final ACK 200 but invalid body != success；
- final ACK committed-success -> success cleanup。

### F. pending-ACK format

- new record round-trip；
- checksum corruption -> fail closed；
- new record包含 recovery identity 但无 secret；
- legacy blob仍可识别；
- legacy blob direct ACK 成功可完成；
- legacy blob direct ACK 失败不进入未绑定的 47110 status，不删除 provisional state。

### G. pending-ACK status

- original bootstrap host status success；
- host unreachable -> bounded discovery；
- relocation exact manager/system/fingerprint match only；
- different fingerprint fail closed；
- status COMMITTED preserves peer/Broker；
- WAIT/UNKNOWN retains state；
- terminal先持久化 TERMINAL_CLEANUP。

### H. crash matrix

分别模拟掉电发生在：

- TERMINAL_CLEANUP marker 已写、renew 前；
- fresh pairing ID 已写、Broker erase 前；
- Broker erase 后、peer erase 前；
- peer erase 后、ack erase 前；
- success 路径 Setup Secret erase 后；
- success 路径 pairing-intent erase 后、ack erase 前。

每一种都必须可重入，不能 false provisioned，不能重复生成多个新 pairing ID。

### I. R4/R5 guards

继续证明：

- idle unregistered 不主动发现 T1；
- pending ACK recovery 优先于 ordinary discovery；
- R5 multiple candidate 不自动选择；
- full selected candidate 仍只在 RAM；
- 手机仍看不到 fingerprint/IP/secret；
- 没有 T1/Board/live gate 被源码测试替代宣称通过。

## 18. false-PASS 检查清单

R6 implementation review 必须专门排除以下假通过：

1. TLS 请求成功后才检查 fingerprint；
2. `skip_cert_common_name_check` 被误当 pinning；
3. pin mismatch 时 body 已写出部分 bytes；
4. 任意 HTTP 200 被 final ACK 当成功；
5. 47110 accepted response未核对 manager/system/47112 locator；
6. bootstrap retry刷新 1800 秒 deadline；
7. pre-transaction failure错误更新 pairing ID；
8. WAIT/UNKNOWN status错误清理 provisional bundle；
9. terminal cleanup 未先持久化 marker；
10. ack record早于 peer/Broker 清理被删除；
11. pending ACK 被 ordinary `credentials_present` fast path误判 provisioned；
12. recovery relocation只匹配 system hint/IP 而不是 manager+system+fingerprint；
13. normal unregistered loop重新调用 legacy `run_once()->discover_()`；
14. 手机或 portal 获得 Setup Secret；
15. 旧 legacy pending ACK 被自动补造 trust identity 后做 destructive recovery；
16. R6 tests用 mocked“成功”替代对 exact request/response/fingerprint ordering 的检查。

## 19. preflight 结论

当前源码没有发现 R6 的结构性 blocker。

已经满足的前置条件：

- 47110 TLS server 与 candidate fingerprint authority 已存在；
- 47110 confirm/status schema 已实现；
- R3 transaction/ledger/reconciliation 已存在；
- 47112 identity/source/deadline binding 已存在；
- existing pairing cryptography 与 credential delivery 已存在；
- ADR-0008 durable pairing-ID renewal primitive 已存在；
- R4 portal 与 R5 candidate selection 已存在；
- pending ACK 在 product loop 中已经比 ordinary R5 discovery 优先。

R6 implementation 需要新增的真正能力只有：

1. ESP32 pre-body leaf-fingerprint pinning transport；
2. confirm/status parser 与 selected candidate handoff；
3. `SimplePairingClient` phase split；
4. recovery-capable pending-ACK persistence；
5. crash-safe terminal cleanup；
6. 对 final ACK success body 的严格解析；
7. 对上述路径的 source/simulation regression。

## 20. 本 gate 的停止点

本文件完成后，本 gate 停在：

```text
R6 source design / preflight complete
product source implementation not started
T1 access not performed
Board access not performed
live mutation not performed
merge not performed
```

下一阶段只有在进入新的 source implementation gate 后，才允许修改上面列出的节点产品源码和测试。

建议下一 gate：

```text
N3W_SCAN_TRIGGERED_FIRST_PAIRING_R6_TLS_BOOTSTRAP_SOURCE_IMPLEMENTATION_20261027_01
```

该建议不是本文件对 implementation 或 merge 的自动授权。
