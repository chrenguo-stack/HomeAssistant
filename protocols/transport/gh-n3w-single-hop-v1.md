# GH N3-W ESP-NOW 单跳传输合同 V1

状态：Draft / host-only contract gate

## 1. 范围

N3-W 只允许 ESP-NOW 子节点向一个 Wi-Fi 中继发送自身遥测。子节点不得转发其他节点，
中继不得形成 Mesh 或多跳路由，也不得直接发布 canonical state 或 Home Assistant Discovery。

本合同冻结入口与安全边界，不提供 ESP-NOW 驱动、生产 Manager 接线、密钥下发或实板执行能力。

## 2. 端到端安全边界

- 子节点与 Manager 使用每节点、按 epoch 轮换的 256-bit 应用密钥。
- 正式实现必须使用经审计库提供的 AES-256-GCM；不得自制密码算法。
- 96-bit nonce 固定为 `uint64_be(boot_session) || uint32_be(seq)`；不得对 session 截断、哈希或随机替换。
- `boot_id` 固定为 `boot_<16 位小写十六进制>`，其中十六进制部分是每节点身份生命周期内持久化的非零 64-bit
  单调 session counter。节点必须先原子递增并持久化 counter，再用新值发送第一帧；
  换 key epoch、备份、镜像或恢复快照均不得回退该 counter。
- 同一 key epoch 下禁止复用 `boot_id + seq`；`seq` 达到 `2^32-1` 后必须停发并原子建立新 boot。
  如果节点不能证明 session counter 未丢失、未回退或已成功持久化，必须 fail closed，并在重新配发新 key epoch
  和 Manager 提供大于既有高水位的 session floor 前禁止使用旧密钥加密。session counter 达到 `2^64-1` 时必须停发并
  轮换节点身份，不得归零。
- AAD 覆盖 schema、transport、gateway_id、node_id、hop_count、key_epoch、boot_id 和 seq。
- 中继只封装密文，不持有子节点应用明文，也不能替子节点生成有效 AEAD tag。
- Manager 在解密后必须再次绑定外层与内层的 `node_id`、`boot_id` 和 `seq`。
- Manager 必须持久化每个 `node_id` 的最高 session counter，以及统一的
  `node_id + boot_id + seq` replay 集合。状态必须在 canonical pipeline 接受帧前原子提交；持久化状态不可用、
  损坏或回退不确定时，入口必须在 AEAD 解密前 fail closed。

ESP-NOW 链路层加密不能替代上述应用层 AEAD。

## 3. MQTT 网关入口

中继使用已有网关入口：

```text
gh/v1/<system_id>/ingress/gateway/<gateway_id>/<node_id>/frame
```

QoS 为 1，Retain 为 false。Broker 身份必须绑定 `<gateway_id>`，Manager 还必须验证该网关当前被授权承载该
`<node_id>`。中继不得写 `state/#` 或 `homeassistant/#`。

## 4. `gh.relay/1` 必填字段

```json
{
  "schema": "gh.relay/1",
  "transport": "esp_now",
  "gateway_id": "gateway_001",
  "node_id": "node_001",
  "hop_count": 1,
  "key_epoch": 1,
  "boot_id": "boot_0000000000000001",
  "seq": 1,
  "nonce_b64": "<12 bytes, base64>",
  "ciphertext_b64": "<1..1024 bytes, base64>",
  "tag_b64": "<16 bytes, base64>"
}
```

未知字段可忽略；缺失或类型错误必须拒绝。Manager MQTT 回调在 JSON 解析前将外层载荷限制为 4096 bytes，
解码后的密文限制为 1..1024 bytes。`hop_count` 只能为 1，任何 0、2 或更大值都必须 fail closed。

## 5. Manager 恢复路径

1. 解析 topic 并校验 system、gateway、node；
2. 验证网关身份、节点状态、网关到节点授权和 key epoch；
3. 验证持久化 replay registry 可用、boot session 未回退、nonce 派生规则和帧大小；
4. 用外层头作为 AAD 执行 AEAD 解密；
5. 校验内层 `gh.telemetry/1` 的 `node_id + boot_id + seq` 与外层完全相同；
6. 将解密后的原始遥测交给已有节点 ingress validator；
7. 原子提交最高 session 与 `node_id + boot_id + seq`，统一处理直连与中继路径；提交失败时不得进入
   canonical pipeline。

中继路径不得建立第二个 NODE_ID、第二套 Discovery 或第二份 Home Assistant 设备。由直连切换到中继，或由中继
切回直连时，较旧或重复序列不得回滚 canonical state。

## 6. Fail-closed 结果

以下任一条件必须在进入 canonical pipeline 前拒绝：topic/载荷绑定不一致、未授权网关、节点 retired、未知 key
epoch、session counter 回退、replay registry 不可用、nonce 不匹配、AEAD 失败、内外身份不一致、帧超限、
非单跳或重复 `node_id + boot_id + seq`。

诊断只记录固定错误码和非敏感身份；不得记录密钥、明文、nonce 前像或完整密文。

## 7. 后续独立门

- Manager 正式入口和上述持久化 replay registry 的生产实现；
- ESP32-C6 子节点与 Wi-Fi 中继驱动；
- 密钥配置、轮换和撤销；
- ESPHome config 与编译；
- 隔离双板链路和故障矩阵；
- 实板与生产授权。

上述项目均不由本合同自动授权。
