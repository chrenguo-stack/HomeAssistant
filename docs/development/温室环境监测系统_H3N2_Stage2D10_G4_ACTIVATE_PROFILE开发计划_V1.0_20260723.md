# 温室环境监测系统 H3/N2 Stage 2D-10 G4 ACTIVATE_PROFILE 开发计划

- **版本：** V1.0
- **日期：** 2026-07-23
- **起始基线：** `main=25a21b38d470992b09c64820d46f56b39917f0dc`
- **开发分支：** `feature/h3-n2-stage2d10-g4-activate-profile-20260723-v1`
- **阶段分类：** C 类源码开发；进入不可变候选或实板前保持 B 类验证方式
- **默认执行门：** `LOCKED`

## 1. 上一阶段输入

Stage 2D-9 G3 已完成一次专用测试板 PREPARE，并通过自动重启后的只读 VERIFY：

```text
active_generation=0
candidate_generation=1
candidate_state=PREPARED
candidate_digest_match=true
active_unchanged=true
persistent_write_count=1
mqtt_operation_attempted=false
```

D2 `D2-H3N2-STAGE2D9-G3-V69-20260723-02` 已消费并永久退役。任何 Stage 2D-8、V67、V68、V69 D2 均不得重放。

## 2. 本阶段唯一目标

Stage 2D-10 只验证 first-enrollment 的 G4 `ACTIVATE_PROFILE` 路径：

```text
reboot/read-only recover PREPARED
→ bind exact recovered candidate without rewriting it
→ isolated candidate MQTT validation
→ VERIFIED
→ fresh generation-bound ACTIVATE authorization
→ start candidate runtime
→ fresh QoS 1 round trip
→ commit active marker last
→ promote candidate session to active
→ automatic firmware restart
→ read-only verify active generation 1
→ stop
```

期望终态：

```text
active_generation=1
candidate_generation=0
active_state=ACTIVE
active_digest_match=true
marker_last_observed=true
active_session_after_activation=true
probe_session=false
candidate_session=false
recovery_required=false
```

本阶段不执行或授权 `CLEANUP_TEST_STATE`。测试命名空间和 active generation 1 的清理必须留给后续独立阶段和独立授权。

## 3. 必须补齐的恢复桥

现有 Stage 2D-7 acceptance package 在同一启动内支持：

```text
CONFIG_LOADED → PREPARED → VALIDATING → VERIFIED → ACTIVATED
```

但 Stage 2D-9 在 PREPARE 后自动重启。新的 G4 进程必须从已持久化的 `NO_ACTIVE_PREPARED` 恢复，不得再次执行 PREPARE。

Stage 2D-10 必须增加一个只读、零写入的 recovered-PREPARED adoption 合同：

- 读取并认证 candidate generation 1；
- runtime-injected candidate profile 与持久化 bundle 字段完全一致；
- active generation 必须为 0；
- persistence status 必须为 `no_active_prepared`；
- adoption 不需要写授权，不增加 persistent write count；
- adoption 不启动 MQTT；
- adoption 成功后才允许进入 candidate validation；
- 任一字段、generation、digest 或状态不一致均失败关闭。

为避免修改已冻结 G3 executor，本阶段采用新的 G4 coordinator/component，不复用或改写 V69 executor。

## 4. 开发顺序

| 阶段 | 内容 | 实板/网络 |
|---|---|---|
| S0 | 基线、范围、禁止项和输入状态冻结 | 否 |
| S1 | recovered-PREPARED、validation、activation、证据和回滚合同 | 否 |
| S2 | portable G4 coordinator、host fake ports 和 deterministic fault matrix | 否 |
| S3 | 默认锁定 manifest、边界 gate、统一 preflight | 否 |
| S4 | 最小 ESP32-C6 与完整 RC2 compile-only target、GitHub CI | 否 |
| S5 | 专用 G4 command executor、隔离 Broker package、证据格式稳定 | 否；只生成定义 |
| S6 | 双 clean build、不可变候选和 locked recovery | 否 |
| S7 | 用户主机只读 Artifact/Broker package 校验 | 用户主机，只读 |
| S8 | 单次 G4 实板授权、执行、只读重启复核和私密证据闭环 | 是，必须新 D2 |
| D4 | Ready 与 squash merge | 仅 GitHub，独立授权 |

候选冻结前不得连接真实或临时 Broker，不得访问实板或物理 NVS。

## 5. Host 故障矩阵

至少覆盖：

1. 正常 recovered PREPARED adoption，零写、零 MQTT；
2. recovery status 不是 `no_active_prepared`；
3. active generation 不为 0；
4. candidate generation 不为 1；
5. runtime candidate 与持久化 bundle 任一字段不一致；
6. 持久化 candidate 无效或解密失败；
7. validation 配置失败；
8. validation start 失败；
9. validation auth/TLS/ACL/round-trip 失败；
10. validation 成功但无 ACTIVATE 授权；
11. stale/wrong generation ACTIVATE 授权；
12. 双层授权只有一层可消费；
13. activation candidate start 失败；
14. marker commit 前 round-trip 失败；
15. commit 明确失败且旧无-active 权威可证明；
16. marker 已提交但返回失败，进入 reboot-required；
17. marker-last 未证明；
18. promotion 失败，进入 reboot-required；
19. 正常 activation，active generation 1、candidate generation 0；
20. activation authorization 不可重放；
21. 自动重启后的 read-only recovery 精确恢复 active generation 1；
22. G4 阶段禁止 cleanup、二次 activation 和生产主题。

## 6. 安全与产品边界

开发期默认禁止：

- 连接任何真实 Broker、生产 Mosquitto 或 Home Assistant；
- 修改 M401A、T1、greenhouse-manager 或生产容器；
- 实板烧录、运行、串口访问或物理 NVS 读写；
- eFuse 读取/烧写、Secure Boot 或 Flash Encryption；
- 修改生产 `f1_0_rc2.yml` 和既有产品 packages；
- 使用 `homeassistant/#`、`gh/v1/` 或生产凭据；
- 重放任何历史 D2；
- 在同一授权内执行 cleanup；
- 未经 D4 将 PR 标记 Ready、合并或发布。

隔离 Broker 只允许后续候选使用：

- 独立临时配置和 ACL；
- test-only CA、username、password、client ID；
- `gh-test/<run-id>/...` 主题；
- 非生产主机、端口和网络；
- 无 Home Assistant Discovery；
- 运行结束后可证明清理。

## 7. 人工决策门

- **D1：** 仅当必须改变已冻结 generation、marker-last、凭据字段或 first-enrollment 语义时触发。
- **D2：** 不可变 G4 候选、私密材料、隔离 Broker、板卡、串口、命令和 locked recovery 全部冻结后，才请求一次精确实板授权。
- **D3：** 仅在实板结果与冻结验收标准冲突时请求异常处置。
- **D4：** PR 最终 HEAD 的全部 CI 和实板证据闭环后，单独请求 Ready 与 squash merge。

## 8. 当前队列

```text
ASSISTANT_QUEUE=
  define recovered-PREPARED adoption contract;
  implement portable G4 coordinator;
  add host fault matrix and boundary gate;
  add compile-only targets and CI;
  keep all execution gates locked

USER_OPERATION_QUEUE=empty
USER_DECISIONS_PENDING=none
DEVICE_OPERATION_AUTHORIZED=false
BROKER_OPERATION_AUTHORIZED=false
PRODUCTION_IO_AUTHORIZED=false
READY_MERGE_RELEASE_AUTHORIZED=false
```
