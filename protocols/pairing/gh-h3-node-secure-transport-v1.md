# gh-h3-node-secure-transport-v1

## 1. 定位

本文件冻结 Stage 2C-2 ESP32-C6 节点实现对 Stage 2B-1 与 Stage 2B-2 的映射，不新增密码学协议。

## 2. 发现顺序

1. 节点创建新的 UUID `request_id` 和 32 字节随机 nonce；
2. 浏览 `_greenhouse._tcp.local`；
3. mDNS 没有有效候选时发送 UDP `gh.discovery.query/1`；
4. 只接收与当前 request/nonce 精确匹配的 `gh.discovery.response/1`；
5. 单候选自动进入 claim-ready；多候选必须等待显式选择。

## 3. HTTP 顺序

```text
POST <pairing_path>/claim
POST <pairing_path>/sessions/<session_id>/establish
POST <pairing_path>/sessions/<session_id>/credentials
POST <pairing_path>/sessions/<session_id>/ack
```

所有 request/response 均为 JSON；响应必须为 200、`application/json`、无重定向且不超过 16384 字节。

## 4. 节点内存生命周期

- `PAIR_SECRET`：claim 和方向密钥派生完成后覆盖清除；
- X25519 私钥、shared secret、HKDF 中间值：派生结束立即覆盖；
- AEAD 方向密钥：ACK 成功或任一终止失败时覆盖；
- credentials：Stage 2C-2 只存 RAM；reset/destructor 时覆盖；
- 日志：只允许布尔状态、计数、阶段名和脱敏错误码。

## 5. ACK 语义限制

Stage 2C-2 模拟环境发送 `stored=true` 表示 RAM staging 成功。该结果不得作为正式持久化验收证据，也不得触发生产 MQTT 切换。
