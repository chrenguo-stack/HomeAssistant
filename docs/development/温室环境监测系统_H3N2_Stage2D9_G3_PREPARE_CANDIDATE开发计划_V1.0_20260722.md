# 温室环境监测系统 H3/N2 Stage 2D-9 G3 PREPARE_CANDIDATE 开发计划

**版本：** V1.2  
**日期：** 2026-07-22  
**起始基线：** `main=2a5272546f25b1b29cf1d6682cf1fc14f1c1be83`  
**开发分支：** `feature/h3-n2-stage2d9-g3-prepare-candidate-20260722-v1`  
**Draft PR：** `#174`  
**默认执行门：** `LOCKED`

## 1. 阶段范围

Stage 2D-9 在已经通过的 Stage 2D-8 G2 只读验收之上，只增加一次候选配置持久化事务的验证能力。阶段终点是：generation 1 candidate 进入 `PREPARED`，active generation 0 不变，自动重启后 `PREPARED` 可只读恢复和 digest 复核，然后停止。

本阶段不包含激活、清理、Broker 连接或生产环境联调。

## 2. 开发顺序

| 阶段 | 内容 | 需要实板 |
|---|---|---:|
| P0 | 范围、协议、状态与禁止项冻结 | 否 |
| P1 | Host 事务模型、失败注入和重启恢复矩阵 | 否 |
| P2 | Manifest gate、默认锁定模板和私有命令协议 | 否 |
| P3 | ESP32-C6 locked harness、token-gated executor 和隔离 writable NVS port | 否，compile-only |
| P4 | 专用板、命令面关闭 executor、完整产品板 compile-only | 否 |
| P5 | 双 clean build、可重复性、不可变 G3 Artifact、确定性 seed 和 locked recovery | 否 |
| P6 | 公共/私有证据格式、U1 校验器和单次执行协议 | 否 |
| P7 | U1 本地主机 Artifact 验证 | 用户主机，只读 |
| P8 | 生成精确 D2 审核包并执行一次实板 PREPARE | 是，需新 D2 |
| P9 | 私有证据提取、公共 L1 闭环和阶段关闭 | 否 |

## 3. Host 验收矩阵

P1/P2 共 21 个用例，覆盖：正常 `EMPTY -> PREPARED`；volatile key 未加载；错误 action；generation 绑定错误；candidate slot 非空；授权非一次性、允许重放或已经消费；candidate profile 写后、PREPARED commit 前断电；PREPARED commit 后、结果回传前断电；MQTT session 非空；ACTIVATE/CLEANUP 授权意外出现；manifest 默认锁定；manifest 拒绝 ACTIVATE/CLEANUP；PREPARE manifest 只允许 `gh2d8_p2d9/gh2d8_s2d9`；PREPARE/VERIFY 命令形状、unlock digest、candidate digest、全零秘密、suffix、schema 替换和测试标识隔离。

该存储命名继续使用冻结 Stage 2D-8 隔离驱动所接受的 `gh2d8_` 前缀，但不复用 G2 的 `gh2d8_nvs/gh2d8_state`，因此在不修改已验收驱动源码的前提下建立独立 Stage 2D-9 存储边界。

## 4. 固件设计约束

G3 harness 独立于冻结 Stage 2D-8 G2 Artifact，不修改或重建 V64。正式 V67 Artifact 绑定：

```text
IMPLEMENTATION_SOURCE_COMMIT=dda4dc25f201242cb566f1498a26200529e35227
EXECUTOR_SOURCE_BINDING=70780dd1e826e07e32e12c66268c5dc564863420
ARTIFACT_ZIP_SHA256=4f9b53908576ffb20ce2653418279dbd45817528a6168b24565447f760ad5dce
G3_MERGED_SHA256=ae109c3e3982adf7c916529d309be57912ff7310b05afa42d431d578ea4745ca
LOCKED_RECOVERY_MERGED_SHA256=54fb10601a0fbf448948d3f7d687281b33e85220c64bcdcabfae896dd3d98a1a
SEED_SHA256=0ea36f26c5048f69b223884a13613fbd645b58c2ce42eafc6f9d9cd55bb089af
```

Artifact gate 固定为 `LOCKED`。Artifact 不授权 Flash、PREPARE、VERIFY、ACTIVATE、CLEANUP、网络、eFuse 或生产操作。

V67 源码和 Artifact 只包含 private one-time unlock preimage 的 SHA-256；不包含 preimage、持久化密钥、authorization digest、candidate 私密命令或实际凭据。公共 compile-only executor 使用全零 digest，命令面关闭。

## 5. 证据分层

公共 Git：计划、协议、CI、默认锁定 manifest、源/Artifact 哈希、脱敏 L1、状态和 Artifact 索引。  
私有存储：板卡绑定、串口路径、授权 JSON、原始/脱敏串口、Flash 日志、启动前后测试分区、candidate 内部秘密值。  
一次性秘密：unlock preimage、持久化密钥和完整私密命令，只存在于精确 D2 执行包和运行期内存。

## 6. 当前状态

```text
P0=complete
P1=passed_ci
P2=passed_ci
P3=passed_compile
P4=passed_compile
P5=passed_frozen_v67
P6=complete
P7=pending_user_host_u1
P8=not_authorized
P9=not_started
EXECUTION_GATE=LOCKED
```

P7 只读校验通过前，不生成可执行 D2 授权文件；P8 的精确审核包必须使用最终 Artifact 哈希、runner、launcher、命令组和停止条件重新绑定。在 D2 前不连接测试板、不执行 Flash、不打开 writable NVS。
