# N3-W 最终产品验证与路线 C 分阶段收口计划

版本：V1.0  
日期：2026-08-19  
状态：执行参考 / 备份  
终点：完成路线 C，将最终 N3-W clean integration 合入 `main`

## 1. 当前冻结状态

- PR #324 Phase 5 已完成并冻结为 PASS。
- PR #324 exact HEAD：`147ead29b5963150e17d582492b148854b0250b4`。
- PR #324 tree：`9c62b1c87549120e0b8f53b0bd949ce5b00a0569`。
- PR #324 仍为 Open / Draft / Unmerged。
- R5 两板实验继续保持 `CONSUMED_PASS`，但其物理证明范围必须收窄为“Direct MQTT 故障后的自动 Relay 路径”，不能解释为“真实 Wi-Fi 失联后的自动 Relay”。
- 尚未完成的最终产品级物理能力包括：真实 Wi-Fi 失联后的自动发现/认证/Relay、第三节点动态加入、两个失联节点同时 Relay、多 Relay failover。
- N3-L 未开始。

本计划遵循：`ONE_BOUNDARY_ONE_VALIDATION`、不重放 R5、不复用已消费授权、不修改生产 Broker/Manager/Home Assistant、不提前进入 N3-L。

## 2. 阶段划分

| 阶段 | 名称 | 主要输出 |
|---|---|---|
| FC-0 | 验收合同修正与冻结 | 明确 R5 已证明与未证明范围 |
| FC-1 | R5→Phase5 active firmware 等价性审计 | 识别 active firmware 行为差异 |
| FC-2 | Final Firmware Artifact 材料化 | 唯一三板实测固件与哈希绑定 |
| FC-3 | 三板物理测试授权前准备 | 独立三板执行包与边界 |
| FC-4 | Three-board Final Product E2E | 最终三板产品级物理证据 |
| FC-5 | 证据与 KNOWN_FAILURES 收口 | `N3W_FINAL_PHYSICAL_PRODUCT_VALIDATION=PASS` |
| FC-6 | 路线 C 集成准备 | 从 current main 建立 clean integration branch |
| FC-7 | Route C exact-head CI 与等价性门 | final main merge candidate |
| FC-8 | Ready / Merge / post-merge closure | N3-W 最终进入 main |

FC-4 是当前计划中唯一新增的物理实板阶段。

## 3. FC-0 — 最终产品验收合同修正

保持 `R5=CONSUMED_PASS` 不变，但冻结其解释边界：R5 已证明 Direct MQTT 故障检测、DISCOVERY、authenticated Relay、ESP-NOW Relay、Manager canonical ingress 与 Direct recovery。

以下能力不得再引用 R5 作为物理 PASS：真实 STA Wi-Fi 失联、无 Direct IP 路径情况下的发现、真实 Wi-Fi 恢复、第三节点动态加入、两个失联节点同时 Relay、多 Relay failover。

`KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` 应增加一条永久规则：应用层 MQTT 上行故障不能等价替代真实 Wi-Fi/STA 失联验收。

FC-0 PASS：

```text
R5_SCOPE_CORRECTED=true
REAL_WIFI_TEST_CONTRACT_FROZEN=true
THREE_BOARD_TEST_CONTRACT_FROZEN=true
```

## 4. FC-1 — Active Firmware 等价性审计

只读比较：

```text
R5_VALIDATED_HEAD=d5ccf7f53e450eb46a2285b0c6d8f41403ea0df7
PHASE5_FINAL_HEAD=147ead29b5963150e17d582492b148854b0250b4
```

按 normal RC2 实际依赖面审计变化，并分类为：`ACTIVE_BEHAVIOR`、`BUILD_ONLY`、`LEGACY_UNSELECTED`、`TEST_ONLY`、`CI_ONLY`、`DOC_ONLY`、`DELETED_RETIRED_CODE`。

重点检查 simplified runtime、Wi-Fi disconnect/recovery、ESP-NOW discovery/channel handling、peer authentication、LMK derivation、NVS credential persistence、Direct/Relay state machine、N3W2 telemetry、relay ingress、BOOT_ID/SEQ continuity 与 normal RC2 dependency graph。

若 active behavior 无未解释差异，则 R5 对其实际已证明部分继续有效；若存在 active delta，则把相关变化直接纳入 FC-4，而不是机械重放旧 R5。

FC-1 PASS：

```text
FIRMWARE_DELTA_FULLY_CLASSIFIED=true
UNEXPLAINED_ACTIVE_DELTA=0
FINAL_PHYSICAL_SCOPE_DEFINED=true
```

## 5. FC-2 — Final Firmware Artifact 材料化

FC-4 不使用历史 d5cc artifact。应从最终准备实测的 exact source HEAD 材料化唯一 firmware artifact，并冻结 source HEAD/tree、firmware tree、ESPHome/toolchain 版本以及 bootloader/partition/app/factory image/package 哈希。

同时确认 factory firmware 保持 generic：不预置 NODE_ID、SYSTEM_ID、peer identity、peer key、用户 Wi-Fi 或 Manager 现场绑定信息。

FC-2 PASS：

```text
FINAL_N3W_FIRMWARE_ARTIFACT=FROZEN
```

## 6. FC-3 — 三板物理执行授权前准备

设备为 BOARD_A / BOARD_B / BOARD_C，三块板使用相同硬件类别和同一个 final factory image。测试继续使用独立实验环境，不访问或修改生产 Broker/Manager/Home Assistant。

FC-4 使用新的独立 authorization；禁止复用 R5 授权、重放 R5 或复用已消费 S5 private package。

## 7. FC-4 — Three-board Final Product E2E

FC-4A：A/B 使用同一 generic factory image 独立 first-use 与 registration，由 Manager 自动分配不同 NODE_ID，Direct telemetry 正常。

FC-4B：保持 A 正常联网，使 B 发生真实 STA Wi-Fi 失联。必须证明 B 的 Direct IP 路径不可用，并由 B 自动进入 discovery、发现并认证合法 Relay、形成 ESP-NOW Relay 到 A，再由 A 上报 Manager。不得以 Broker client disable、ACL deny 或 MQTT credential rejection 代替真实 Wi-Fi failure。

FC-4C：恢复 B 的真实 Wi-Fi，要求自动返回 Direct，并保持 boot-session/SEQ/canonical state 连续。

FC-4D：在 A/B 已完成使用后动态加入 C。A/B 不重刷、不重新配对、不人工录入 C 信息；C 使用同一 generic factory image 独立注册并获得新的 NODE_ID。

FC-4E：让 C 发生真实 Wi-Fi 失联，要求其自动发现、认证并选择任一合法 Relay，不要求人工指定固定 Relay。

FC-4F：验证 A 可联网而 B/C 同时失联时，两者均可独立通过 Relay 上报，且 NODE_ID、BOOT_ID、SEQ、canonical state 不互相污染。

FC-4G：验证多 Relay failover。B 已处于 Relay 模式后，当前 Relay 不再可用时，B 应自动重新发现并切换到另一合法 Relay，不依赖 Manager PATH 指令、人工 Relay 选择、重新配对或新的有限期 peer grant。

FC-4H：恢复 A/B/C 正常 Wi-Fi，三者最终均回到 Direct，NODE_ID 稳定，无 duplicate device、stale relay ownership 或 canonical rollback。

最终必需矩阵：

```text
GENERIC_IDENTICAL_FACTORY_FIRMWARE=PASS
INDEPENDENT_REGISTRATION_A=PASS
INDEPENDENT_REGISTRATION_B=PASS
LATE_REGISTRATION_C=PASS
EXISTING_NODES_NO_REFLASH_ON_C_JOIN=PASS
EXISTING_NODES_NO_REPAIR_ON_C_JOIN=PASS
B_REAL_WIFI_LOSS=PASS
B_DISCONNECTED_DISCOVERY=PASS
B_AUTHENTICATED_RELAY=PASS
B_REAL_WIFI_RECOVERY=PASS
C_REAL_WIFI_LOSS=PASS
C_AUTOMATIC_RELAY_SELECTION=PASS
C_AUTHENTICATED_RELAY=PASS
SIMULTANEOUS_B_C_RELAY=PASS
MULTI_RELAY_FAILOVER=PASS
NO_PATH_AUTHORITY=PASS
NO_FINITE_PEER_GRANT=PASS
NO_MANUAL_PEER_CONFIG=PASS
CANONICAL_STATE_CONTINUITY=PASS
N3W_THREE_BOARD_FINAL_PRODUCT_E2E=PASS
```

## 8. FC-5 — 证据与产品状态收口

三板测试后先做 host-only closure，不立即集成。公共仓库仅保存 sanitized summary、exact HEAD、artifact hashes、terminal result 与 regression conclusions；原始私有证据继续保存在 private evidence root。

任何新问题都按“现象 → 根因 → 修复 → regression guard”补充到 `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`。

只有完成该阶段才允许：

```text
N3W_FINAL_PHYSICAL_PRODUCT_VALIDATION=PASS
```

## 9. FC-6 — 路线 C：Clean Final Integration

路线 C 只在 FC-5 PASS 后开始。

不直接 merge PR #323，也不直接把 stacked PR #324 当成最终 main PR。先冻结 current main exact SHA/tree，再从 current exact `main` 建立新的 clean integration branch，将最终 N3-W 产品状态集成进去。

任何 conflict 必须逐项分类为 `CURRENT_MAIN_CHANGE`、`N3W_FINAL_REQUIRED`、`RETIRED_N3W_CODE` 或 `UNRELATED_CHANGE`，禁止机械 ours/theirs。

必须防止已退休 PATH ownership、finite gateway grant、旧 X25519 product runtime、旧 product_core/product_runtime、旧 S2/S3/S5 authority、operator-supplied NODE_ID 与 historical live workflows 重新进入 active product tree。

随后执行 integration equivalence gate：路线 C active firmware 必须与已经通过三板物理验收的 active firmware 等价。若 conflict resolution 导致 active firmware 行为改变，则重新评估 targeted physical test / Final E2E，不能直接 merge。

## 10. FC-7 — Route C exact-head 最终 CI

在 clean integration branch 上执行真正面向 `main` 的 final CI，包括 Manager full tests、lint、cross-language、simplified runtime、Child/Relay/full RC2 compile、repository safety、NODE_ID、canonical replay/high-water、C06 regressions 和 retired-authority absence guards。

所有 current exact-head workflows 必须 terminal 且无 failure，并确认：

```text
ACTIVE_LEGACY_AUTHORITY=0
RETIRED_WORKFLOW_REINTRODUCED=false
OLD_PRODUCT_RUNTIME_REINTRODUCED=false
```

随后创建新的 Final Integration PR：`base=main`，`head=integration/n3w-final-...`。该 PR 才是路线 C 的最终 PR。

## 11. FC-8 — Ready / Merge / post-merge closure

即使 FC-7 全 PASS，也只冻结 `ROUTE_C_READY_CANDIDATE=true`，不得自动 Ready/merge。

Ready 和 Merge 分别需要独立明确授权。merge 前再次只读确认 PR/head/base/CI/mergeable 无漂移，merge 时使用 expected-head SHA 约束。

Route C 完成终态：

```text
N3W_FINAL_PHYSICAL_PRODUCT_VALIDATION=PASS
ROUTE_C_FINAL_PR=MERGED
MAIN_CONTAINS_FINAL_N3W=true
MAIN_ACTIVE_LEGACY_AUTHORITY=0
FINAL_MAIN_CI=PASS
POSTMERGE_REGRESSION=PASS
PR323=SUPERSEDED
PR324=SUPERSEDED_BY_FINAL_INTEGRATION_PR
N3W=PRODUCT_CLOSED
```

此后才允许为 N3-L 建立新的独立规划和授权。

## 12. 推荐执行链

```text
FC-0 验收合同修正
→ FC-1 firmware delta audit
→ FC-2 final artifact
→ FC-3 三板授权前 gate
→ FC-4 A/B/C Final Product E2E
→ FC-5 evidence / known failures / terminal
→ N3-W FINAL PHYSICAL PASS
→ FC-6 clean integration from current main
→ integration equivalence audit
→ FC-7 exact-head full CI / final PR
→ Ready authorization
→ Merge authorization
→ FC-8 post-merge exact-main closure
→ ROUTE C COMPLETE
→ N3-W PRODUCT CLOSED
```

## 13. 当前执行边界

本文件提交仅作为开发参考和备份，不代表 FC-0 已经开始执行；不修改 PR #324、不重新运行 R5、不访问板卡、不触发三板物理测试、不进入 N3-L、不授权 Ready/merge。
