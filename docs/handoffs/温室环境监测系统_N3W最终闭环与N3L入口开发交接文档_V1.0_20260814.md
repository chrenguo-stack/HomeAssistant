# 温室环境监测系统 N3-W 最终闭环与 N3-L 入口开发交接文档

**版本：** V1.0  
**日期：** 2026-08-14  
**交接范围：** N3-W 最终阶段退出、PR #315 双板信道恢复物理验收、公共脱敏归档、N3-L 独立入口  
**仓库：** `chrenguo-stack/HomeAssistant`

---

## 1. 最终结论

N3-W 已完成最终总体只读闭环审计，阶段分类冻结为：

`N3W_COMPLETE_WITH_RECORDED_DEVIATIONS`

N3-W 当前 exit blocker 为 0。

这表示 N3-W 已满足进入后续独立阶段规划的条件，但不表示 N3-L 已经开始或获得授权。

---

## 2. 当前 GitHub 基线

- source main：`972e55b459c9095d5cbf1fd3aabbe312e55ab578`
- source tree：`3a4b1d4971756a8d3a53fec8cb5f1e2a32dcb154`
- PR #314：M14 公共脱敏归档，已合并。
- PR #315：connected-STA ESP-NOW channel recovery 修复，已合并；merge commit 为当前 source main。
- PR #307：旧 M08 successor handoff，已关闭且未合并，保留为 superseded 历史记录。

本交接所在归档分支只应增加公共安全的 acceptance/handoff 文件，不修改 firmware、runtime、protocol、service 或既有验收文件。

---

## 3. 路线图边界

路线图 V0.7 明确：

- N3-W：Wi-Fi 版 ESP-NOW 单跳、路径租约与切换；进入下一阶段的重点是“不重复设备、不回滚”。
- N3-L：LoRa 版星形单跳、普通节点网关化、ACK、重试和诊断。
- N3-L 是独立工作流；需要新的 scope discovery、合同、PR/CI、隔离集成、固件与实板阶段门。

V0.7 同时强调架构基线不等于实现完成度，实时状态应由 status / acceptance / handoff 记录。

---

## 4. N3-W 最终冻结矩阵

```text
M01-M05_CHAIN=CLOSED

M06_HOSTONLY_SEMANTIC_PROOF=PASS
M06_PHYSICAL_E2E=EXPLICITLY_DEFERRED
M06_LIVE_PASS=false
M06_N3W_EXIT_BLOCKER=false

M07=PASS
M08=PASS
M09=PASS
M10=PASS
M11=PASS
M12=PASS

M13=PASS_WITH_RECORDED_EXECUTION_DEVIATION
M14=PASS_WITH_RECORDED_READONLY_VALIDATION_RECOVERY_DEVIATIONS

ESPNOW_CHANNEL_RECOVERY_PHYSICAL_ACCEPTANCE=PASS

N3W_EXIT_BLOCKERS=0
N3W_FINAL_CLASSIFICATION=N3W_COMPLETE_WITH_RECORDED_DEVIATIONS
```

### 必须继续保留的偏差和延期

1. M13 Broker outage 的执行时间偏差继续保留。
2. M14 只读验证中的恢复历史继续保留。
3. M06 physical E2E 继续明确延期，不得写成 live PASS。
4. P6 与 concurrency/capacity/power-loss 继续延期到 S1 field validation。

---

## 5. PR #315 与双板物理闭环

PR #315 修复 connected STA 已关联后 AP 信道变化时的 ESP-NOW 恢复路径。公开代码合同包括：

- 持续观察 associated STA channel。
- STA 信道变化时 fail closed。
- 更新既有 encrypted ESP-NOW peer。
- 要求新的 authenticated Probe/ProbeAck 后才恢复 Relay telemetry。
- connected-STA recovery path 不主动夺取 Wi-Fi channel ownership。
- channel recovery helper 不修改 desired PATH、selected key epoch、boot/session 或 sequence state。

随后 exact-main private firmware 已完成 Child/Relay 两板部署，并完成真实双板自动恢复验收。

公共可记录结果：

```text
TWO_BOARD_AUTO_RECOVERY_ACCEPTANCE=PASS
EXACTLY_ONE_AP_CHANNEL_TRANSITION=true
CHILD_RECOVERED=true
RELAY_RECOVERED=true
ACTIVE_PATH_AFTER_RECOVERY=relay
APPLICATION_KEY_EPOCH_AFTER_RECOVERY=2
SERVICE_RESTART_COUNT=0
REFLASH_REQUIRED_FOR_RECOVERY=false
PATH_REISSUE_REQUIRED_FOR_RECOVERY=false
KEY_REISSUE_REQUIRED_FOR_RECOVERY=false
```

具体 AP 信道号、板卡身份、私有固件摘要和完整运行证据不进入公共交接。

---

## 6. Home Assistant 身份连续性证据边界

M14 已独立证明：

- 目标 NODE_ID 对应 1 个 Home Assistant Device。
- 共 6 个目标实体。
- 无重复 unique ID。
- 无 foreign device binding。
- 有效只读窗口内身份和 registry chronology 保持不变。

本次 PR #315 信道切换物理验收没有重新声称新的 HA registry 双快照。因此：

`IDENTITY_CONTINUITY_EVIDENCE_SOURCE=M14_FROZEN_EVIDENCE`

不能把物理信道恢复摘要扩展解释为新的 M14 身份复验。

---

## 7. 私有证据和公开仓库边界

完整物理运行证据、private firmware artifacts、私有证据 digest、板卡标识、网络地址、凭据、PMK/LMK/application key、私有路径以及一次性授权历史继续保留在受限 custody 中，不进入公共仓库。

公共仓库只保存：

- public GitHub SHA/PR 状态；
- PASS/FAIL/DEFERRED 分类；
- sanitized invariant outcome；
- 非重放边界；
- 阶段完成度和下一阶段入口条件。

N3-W 最终机器可读公共摘要：

`docs/acceptance/n3w-final-closure-public-archive-20260814.json`

N3-W 最终人类可读公共摘要：

`docs/acceptance/n3w-final-closure-public-archive-20260814.md`

---

## 8. N3-L 下一阶段入口

当前只允许得出：

```text
N3L_ENTRY_ELIGIBLE=true
N3L_AUTHORIZED=false
```

N3-L 首个开发动作应是独立的 scope discovery，而不是直接写 LoRa 固件或进行实板发送。

建议顺序：

1. 重新绑定 fresh main / tree 和路线图 V0.7。
2. 冻结 N3-L scope：普通 LoRa 环境监测节点、gateway candidate、GATEWAY_ID lease、node ingress / gateway ingress 双入口隔离。
3. 明确 EWM22M 应用帧、认证、ACK/retry、replay、诊断和 gateway eligibility 的现有实现与缺口。
4. 建立 host-only contract 与测试。
5. 通过独立 Draft PR / CI 审查。
6. 再进入 isolated integration、private firmware、实板基本链路。
7. N4-L 的多网关选举、租约切换和容量验证不得提前并入 N3-L。

N3-L 首版不实现 LoRa Mesh，也不引入专用无传感器 LoRa 中继器。

---

## 9. 新会话恢复要求

下一位开发者或 AI 接手时，应先只读确认：

- main 是否仍从 `972e55b459c9095d5cbf1fd3aabbe312e55ab578` 合法前进，或记录新的合法 main；
- N3-W 最终公共归档是否已经合并，或仍处于 Draft PR；
- PR #315 仍为 merged；
- PR #307 仍为 closed/unmerged superseded；
- `N3W_COMPLETE_WITH_RECORDED_DEVIATIONS` 没有被改写成无偏差 PASS；
- M06 physical E2E 仍保持 deferred；
- 未重放 N3-W 已消费的 physical/runtime 授权；
- 未在缺少独立 scope gate 时开始 N3-L。

满足后，才建立 N3-L scope discovery 的独立授权边界。

---

## 10. 当前停止点

```text
N3W_COMPLETE=true
N3W_COMPLETE_WITH_RECORDED_DEVIATIONS=true
N3W_EXIT_BLOCKERS=0

N3L_ENTRY_ELIGIBLE=true
N3L_AUTHORIZED=false

N3W_RUNTIME_MUTATION_REQUIRED=false
N3W_BOARD_OPERATION_REQUIRED=false
N3W_AP_MUTATION_REQUIRED=false
```

本交接文档本身不授权 N3-L runtime、MQTT、LoRa RF、板卡、Flash、服务或生产网络动作。
