# N3-W 最终闭环公共脱敏归档

## 结论

N3-W 已按以下分类完成阶段退出审计：

`N3W_COMPLETE_WITH_RECORDED_DEVIATIONS`

本归档是公开仓库可保存的脱敏摘要。它不包含完整运行证据、私有证据摘要、私有固件摘要、原始设备标识、凭据、密钥材料、私有路径、主机地址、端口映射、原始 live sequence/boot/session tuple 或一次性授权文本。

## 仓库绑定

- 仓库：`chrenguo-stack/HomeAssistant`
- 审计源 main：`972e55b459c9095d5cbf1fd3aabbe312e55ab578`
- 审计源 tree：`3a4b1d4971756a8d3a53fec8cb5f1e2a32dcb154`
- M14 公共脱敏归档：PR `#314`，已合并
- ESP-NOW 信道恢复修复：PR `#315`，已合并；其 merge commit 即上述审计源 main
- 旧 M08 successor handoff：PR `#307`，已关闭且未合并，作为 superseded 历史记录保留

## N3-W 阶段结论

路线图 V0.7 将 N3-W 定义为 Wi-Fi 版 ESP-NOW 单跳、路径租约与切换，阶段退出重点是不产生重复设备、不允许 canonical state 回滚。

最终闭环结论：

- M01–M05 链已关闭。
- M06 exact-main host-only 语义证明通过；真实 physical E2E 明确延期，`M06_LIVE_PASS=false`，且该延期不再构成 N3-W exit blocker。
- M07–M12 已通过。
- M13 按 `PASS_WITH_RECORDED_EXECUTION_DEVIATION` 关闭，outage timing 偏差永久保留。
- M14 按 `PASS_WITH_RECORDED_READONLY_VALIDATION_RECOVERY_DEVIATIONS` 关闭，只读恢复历史永久保留。
- P6 以及 concurrency/capacity/power-loss 继续延期至 S1 field validation。

## Home Assistant 身份连续性

身份连续性结论继承已经冻结的 M14 验收：

- 同一目标身份对应 1 个 Home Assistant Device 和 6 个实体。
- 无重复 unique ID。
- 无外部设备绑定。
- 本次 ESP-NOW 信道切换摘要没有重新执行或声称新的 Home Assistant registry 双快照，因此不会把本次物理恢复测试误写成新的身份连续性证明。

## ESP-NOW 信道恢复物理验收

PR #315 合并后，exact-main private firmware 已经完成两板部署和真实双板验收。

最终物理事实：

- 隔离 AP 恰好执行一次 2.4 GHz 信道变化；具体信道号不进入本公共归档。
- Child 与 Relay 均自动恢复。
- 恢复后 active path 仍为 Relay。
- 恢复后使用应用密钥 epoch 2。
- 服务 restart count 为 0。
- 恢复不需要重新刷写固件。
- 恢复不需要重新发送 PATH 命令。
- 恢复不需要重新发送 KEY 命令。

因此，PR #315 所针对的 connected-STA channel recovery blocker 已由真实双板物理验收关闭。

## 声明边界

- M06 physical E2E 仍是明确延期项，不得改写为 live PASS。
- M13 的执行时间偏差不得删除或重新分类。
- M14 的只读验证恢复历史不得删除或重新分类。
- 不制造不存在的 pre-M01 独立 registry 哈希对。
- M07 transcript 不作为独立 Home Assistant identity proof。
- host-only、compile-only 或静态合同结果不得冒充新的实板/live 验收。
- N3-L 当前仅具备进入独立 scope discovery 的资格；本归档不构成 N3-L 授权。

机器可读摘要见：

`docs/acceptance/n3w-final-closure-public-archive-20260814.json`
