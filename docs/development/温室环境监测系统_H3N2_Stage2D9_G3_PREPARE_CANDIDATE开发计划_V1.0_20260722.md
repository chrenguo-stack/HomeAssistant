# 温室环境监测系统 H3/N2 Stage 2D-9 G3 PREPARE_CANDIDATE 开发计划

**版本：** V1.1  
**日期：** 2026-07-22  
**起始基线：** `main=2a5272546f25b1b29cf1d6682cf1fc14f1c1be83`  
**开发分支：** `feature/h3-n2-stage2d9-g3-prepare-candidate-20260722-v1`  
**默认执行门：** `LOCKED`

## 1. 阶段范围

Stage 2D-9 在已经通过的 Stage 2D-8 G2 只读验收之上，只增加一次候选配置持久化事务的验证能力。阶段终点是：generation 1 candidate 进入 `PREPARED`，active generation 0 不变，重启后 `PREPARED` 可恢复，然后停止。

本阶段不包含激活、清理、Broker 连接或生产环境联调。

## 2. 开发顺序

| 阶段 | 内容 | 需要实板 |
|---|---|---:|
| P0 | 范围、协议、状态与禁止项冻结 | 否 |
| P1 | host 事务模型、失败注入和重启恢复矩阵 | 否 |
| P2 | Stage 2D-9 manifest gate 与默认锁定模板 | 否 |
| P3 | ESP32-C6 G3 PREPARE harness 和隔离 writable NVS port | 否，compile-only |
| P4 | 专用板与完整产品板 compile-only | 否 |
| P5 | 双 clean build、可重复性、不可变 G3 Artifact 与 locked recovery | 否 |
| P6 | 公共脱敏证据模板、私有证据格式和一键执行包 | 否 |
| P7 | U1 本地主机 Artifact 验证 | 用户主机，只读 |
| P8 | 精确 D2 审核与一次实板 PREPARE | 是，需新 D2 |
| P9 | 私有证据提取、公共 L1 闭环和阶段关闭 | 否 |

## 3. Host 模型验收矩阵

当前 P1/P2 覆盖：正常 EMPTY -> PREPARED；volatile key 未加载；错误 action；generation 绑定错误；candidate slot 非空；授权非一次性、允许重放或已经消费；candidate profile 写后、PREPARED commit 前断电；PREPARED commit 后、结果回传前断电；MQTT session 非空；ACTIVATE/CLEANUP 授权意外出现；manifest 默认锁定；manifest 拒绝 ACTIVATE/CLEANUP；PREPARE manifest 只允许 `gh2d8_p2d9/gh2d8_s2d9`。

该命名继续使用冻结 Stage 2D-8 隔离驱动所接受的 `gh2d8_` 前缀，但不复用 G2 的 `gh2d8_nvs/gh2d8_state`，因此可以在不修改已验收驱动源码的前提下建立独立 Stage 2D-9 存储边界。

## 4. 固件设计约束

G3 harness 必须独立于冻结 Stage 2D-8 G2 Artifact，不修改或重建 V64。新的 G3 Artifact 使用新的版本号、源绑定和哈希。默认镜像必须保持：

```text
execution_authorized=false
prepare_authorization_present=false
activate_authorization_present=false
cleanup_authorization_present=false
wifi=false
mqtt=false
broker=false
efuse=false
```

实际 PREPARE 授权不得编译进公共源码或 Artifact。授权只能在执行包中私有注入，并绑定 candidate digest 与 generation。

## 5. 证据分层

公共 Git：计划、协议、CI、默认锁定 manifest、源/Artifact 哈希、脱敏 L1、状态。  
私有存储：板卡绑定、串口路径、授权 JSON、原始串口、Flash 日志、candidate profile 明文或凭据值。

## 6. 当前状态

```text
P0=complete
P1=complete
P2=complete
P3=in_progress
P4=not_started
P5=not_started
P6=not_started
P7=not_started
P8=not_authorized
P9=not_started
EXECUTION_GATE=LOCKED
```
