# gh-h3-node-secure-transport-v1

## 1. 定位

本文件冻结 Stage 2C-2 ESP32-C6 节点实现对 Stage 2B-1 与 Stage 2B-2 的映射，不新增密码学协议。

## 2. 发现顺序

1. 节点创建新的 UUID `request_id` 和 32 字节随机 nonce；
2. 浏览 `_greenhouse._tcp.local`；
3. mDNS 没有有效候选时发送 UDP `gh.discovery.query/1`；
4. 只接收与当前 request/nonce 精确匹配的 `gh.discovery.response/1`；
5. UDP 每次尝试最多处理 32 个响应，datagram 不超过 1400 字节；
6. UDP 目标和响应来源均限本地 IPv4 范围；
7. 单候选自动进入 claim-ready；多候选必须等待显式选择。

## 3. HTTP 顺序

```text
POST <pairing_path>/claim
POST <pairing_path>/sessions/<session_id>/establish
POST <pairing_path>/sessions/<session_id>/credentials
POST <pairing_path>/sessions/<session_id>/ack
```

所有 request/response 均为严格 JSON；响应必须为 200、`application/json`、无重定向且不超过 16384 字节。`pairing_path` 只允许无歧义绝对路径，不允许查询串、片段、百分号编码、空段或 `.`/`..`。

## 4. 密码学拒绝规则

- X25519 全零 shared secret 必须拒绝；
- base64url 必须为无 padding canonical 编码；
- envelope direction、session、content type、nonce 和 sequence 必须全部匹配；
- AEAD 认证失败、错误方向和重放不得推进 receive sequence；
- 解密失败必须清空调用方既有明文输出。

## 5. 节点内存生命周期

- `PAIR_SECRET`：Manager 确认 channel established 后覆盖清除；
- X25519 私钥、shared secret、HKDF 中间值和 PSA 临时 key slot：派生结束立即清理；
- claim/establish proof JSON：HTTP 调用完成后覆盖；
- AEAD 方向密钥：ACK 成功或任一终止失败时覆盖；
- credentials：Stage 2C-2 只存 RAM，禁止复制；受控移动后覆盖源对象，reset/destructor 时覆盖；
- cJSON 凭据解析树：释放前递归覆盖字符串；
- 日志：只允许布尔状态、计数、阶段名和脱敏错误码。

## 6. 调度限制

Stage 2C-2 的 mDNS、UDP 和 HTTP 实现为同步、有界实验接口。非生产编译目标不得自动执行真实网络事务；后续生产接线必须使用独立 worker/task，不能从 ESPHome 主循环或显示回调直接调用完整配对闭环。

## 7. ACK 语义限制

Stage 2C-2 模拟环境发送 `stored=true` 表示 RAM staging 成功。该结果不得作为正式持久化验收证据，也不得触发生产 MQTT 切换。
