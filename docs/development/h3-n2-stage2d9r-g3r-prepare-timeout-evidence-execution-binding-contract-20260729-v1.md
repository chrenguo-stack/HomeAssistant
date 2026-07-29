# H3/N2 Stage 2D-9R G3R PREPARE 超时证据执行绑定合同 V1

## 决策门

`D1-H3N2-STAGE2D9R-G3R-PREPARE-TIMEOUT-EVIDENCE-EXECUTION-BINDING-20260729-01`

## 目的

将 PR #200 冻结的脱敏证据记录器接入新的物理执行后继包，并生成仍未授权的请求：

`D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260729-07`

## 前序终态

请求 `-06` 永久保持：

- `CONSUMED_FAILED`；
- `PREPARE_RESULT_TIMEOUT`；
- `LOCKED_RECOVERY_COMPLETED`；
- 禁止重放和自动重试；
- PREPARE 1 次，VERIFY 0 次；
- locked recovery 已成功。

## 证据绑定

后继执行器在 PREPARE/VERIFY 串口与临时 Broker 生命周期中写入：

- `prepare-serial.redacted.jsonl`；
- `broker.redacted.jsonl`；
- `prepare-timeline.json`；
- `prepare-evidence-manifest.json`。

失败进入 locked recovery 之前必须完成终态证据持久化；成功或失败退出临时目录之前必须再次完成终态持久化。

主超时后只增加 5 秒只读延迟观察窗口，不重发命令，不扩大 PREPARE 次数。迟到结果只能分类为 `LATE_RESULT`，不能把已超时执行改判为成功。

## 分类

- `NO_RESULT`
- `SERIAL_RESET`
- `BROKER_DISCONNECT`
- `LATE_RESULT`
- `UNRECOGNIZED_RESULT`

正常按时收到 PREPARE pass 时，成功证据可使用 `PREPARE_PASS`。

## 隐私与权限

- 命令材料、凭据、MAC、IP、USB/用户路径不保留原文；
- 未知行只保留 SHA-256；
- 证据目录 `0700`；
- 证据文件 `0600`；
- 原子写入并执行 `fsync`。

## 冻结边界

- 修正基线保持 `776517efcac0c6cf03cabe0572b773dedc89e9bb2793ccb0d9f9585ea6fa601f`；
- immutable payload TAR 保持 `3a3e96c267fd53723e7cbe6cbce959a90d2bf3f08adedcf97255395f91adc4ea`；
- recovery payload TAR 保持 `08cff687947c2f9b9cbd2df09f16b14b95beeacf2de5683055d6572fafd6cf8f`；
- locked recovery 仍限制在测试分区，最多一次；
- 不授权 ACTIVATE、CLEANUP 或生产操作。

## 本轮禁止事项

本轮只允许源码、测试、CI、Artifact、Draft PR 和未授权请求 `-07`。禁止连接或枚举板卡、USB/串口、esptool、Flash/NVS、Broker、PREPARE、VERIFY、Ready、合并、发布、标签或部署。
