# N3-W T1 minimal-host fresh bootstrap R6 progress（2026-10-12）

R5 已 CLOSED_PASS。R6 开始把验证对象从“host-only 模型”换成真实的 ARM64 三镜像。

本轮先修复一个必须在 R6 关闭前消除的绑定问题：fresh installer 会生成新的随机 system_id，但旧 production Compose 仍固定写死 greenhouse。现在 Compose 的 system_id、Manager/Provisioning username 和 client id 改为从 fresh credential bundle 的 runtime.env 注入；deployment gate 不再要求固定 greenhouse，而是检查这些字段是否与同一个 system_id 严格一致。

R6 新增 exact ARM64 CI，计划证明：

1. 从当前 exact source 构建 ARM64 Manager image；
2. fresh identity/state/broker constructors 确实存在于该 exact Manager image 中并可在 network-none 下执行；
3. Home Assistant 和 Mosquitto 使用已冻结 ARM64 manifest digest；
4. Broker UID1883 可以读取 promotion 后的 TLS runtime 文件；
5. fresh system_id 与 Compose 中的 Manager/Provisioning identities 完整一致；
6. 使用 exact ARM64 HA/Broker 跑 Home Assistant MQTT config-flow 隔离 runtime；
7. 上传 Manager/HA/Broker 三个 tar + binding.json；
8. 同一 workflow 重新下载 artifact 并逐文件 SHA 验证。

本轮仍不访问真实 T1，不启动真实生产服务，不访问板卡。

```text
R5_STATUS=CLOSED_PASS
R6_SOURCE_COMMITTED=true
R6_CI=PENDING
R6_EXACT_ARM64_ARTIFACT=PENDING
T1_ACCESS=false
LIVE_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR541=OPEN_DRAFT
MERGE=false
```
