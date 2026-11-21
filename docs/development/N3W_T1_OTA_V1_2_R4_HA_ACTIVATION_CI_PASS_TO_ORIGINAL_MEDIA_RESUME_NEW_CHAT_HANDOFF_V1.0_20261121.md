# N3-W T1 OTA V1.2 从 HA 启动验证通过到原 U 盘恢复续办

`HANDOFF_TEMPLATE_VERSION=1.4`

交接日期：2026-11-21

## 1. 目标与停点

- 将温室环境监测系统 N3-W 的 T1 OTA 工程从 V1.0 对齐到 V1.2。架构和 R1–R10 路线已进入 `main`，R1 工程收敛和 R2 源码设计已归档，R3 已建立从 `main` 出发的干净实现分支。当前继续 **R4，先打通 Home Assistant（HA）单组件 OTA**。
- 已完成到 HA 目标镜像启动意图、启动确认与按写入边界恢复。该批源码的本地回归和 GitHub CI 已通过。
- 用户要求在此停下并切换对话。**新会话从“原 U 盘重新可用时，宿主自动续办恢复”继续。** 此停点仍处于 R4，完成度以本交接第 3 节为准。

## 2. 代码与证据

| 对象 | 核对结果 |
|---|---|
| 仓库 | [chrenguo-stack/HomeAssistant](https://github.com/chrenguo-stack/HomeAssistant) |
| `main` | `4fde1b7c5cc0aa224fa3574b8b4cc638edd93647`。[架构 PR #812](https://github.com/chrenguo-stack/HomeAssistant/pull/812) 和 [路线 PR #813](https://github.com/chrenguo-stack/HomeAssistant/pull/813) 均已合并。 |
| 实现分支 | `feat/t1-ota-v1-2-alignment-20261120`，[PR #815](https://github.com/chrenguo-stack/HomeAssistant/pull/815) 为开放的草稿。 |
| R4 已验证源码 | `2bd14fd4f4269eeb13c09d19cdfef01d4924c1c5`，树 `3fbe5a3d0435ffaf20b825890ccc0018910d569c`。本地工作区干净，分支、PR 和远端提交一致。[源码差异](https://github.com/chrenguo-stack/HomeAssistant/commit/2bd14fd4f4269eeb13c09d19cdfef01d4924c1c5) |
| R1–R3 记录 | [PR #814](https://github.com/chrenguo-stack/HomeAssistant/pull/814) 为开放的文档草稿，核对提交 `41c06c1abf6ccaf05b977237a5b7bad3710f8031`。 |
| CI | 该 R4 提交有 **18 个成功、4 个策略跳过**，全部结束。4 个跳过属于 fresh-install ARM64 和 fresh-bootstrap payload 两类工作流。[HA 目标绑定](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44862170121) · [Manager A-to-B](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44862169906) · [公开仓库安全检查](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44862170010) · [全部检查](https://github.com/chrenguo-stack/HomeAssistant/pull/815/checks) |
| 部署 | R4 源码处于评审状态。本轮 T1、USB 和服务运行基线为 `UNKNOWN_FRESH`，实机验收待 R7–R9。 |

## 3. 必须继承的结论

- **源码。** 复用现有设备上的普通 U 盘与单笔事务目录，核对恢复材料后才允许释放本笔独占的旧镜像。首次停服前已有持久化启动配置与恢复责任。已实现加密的 HA 数据备份、旧镜像释放后的事实核对、目标镜像导入、目标启动和旧版恢复入口。
- **恢复分界。** 在 `BINDING` 阶段中断时，恢复旧镜像选择并保留原 HA 数据目录。持久写入 `WRITES_POSSIBLE` 后，按可能已有新版写入处理，停住写入方，使用绑定备份恢复数据，再启动旧版。启动许可仅在本次安装执行期间有效，U11 需要观测到目标镜像和受保护挂载。缺原盘时已有 `RECOVERY_MEDIA_REQUIRED` 过程状态。
- **本地与 CI。** 本地 Python 3.12.14 共 289 项通过，另有 3 项依赖 Docker、原生 Unix 套接字或精确 U1 包而未在本地执行。故障注入覆盖目标镜像漂移、绑定后中断、写入意图落盘失败、启动前后中断和缺原盘。GitHub CI 结果独立列于第 2 节。
- **待完成。** 已模拟原盘缺失后再次调用恢复入口的行为。宿主在原盘重新可用时如何自行触发续办，仍待实现和验证。随后完成正式升级器交付接线、按影响验收与持久提交，再按路线推进 R5、R6 和后续实机阶段。源码、模拟、CI 和真实部署分别取证。

## 4. 执行范围与授权

- **可继续。** 用户已授权依 R1–R10 路线推进。新会话完成 R4 的相关源码修改、确定性模拟、复核、提交到实现分支和适用 CI，可连续进行。
- **暂停边界。** T1、物理 USB、Docker 运行环境和服务、合并与发布需要按对应阶段和已有授权核对。需要用户操作 T1 时，提供可直接复制的 Mac Terminal 指令，由用户执行并回传结果。
- **历史分支。** [#807](https://github.com/chrenguo-stack/HomeAssistant/pull/807)、[#809](https://github.com/chrenguo-stack/HomeAssistant/pull/809)、[#810](https://github.com/chrenguo-stack/HomeAssistant/pull/810)、[#811](https://github.com/chrenguo-stack/HomeAssistant/pull/811) 核对时均为开放的历史草稿。禁止合并或关闭这些 PR，禁止恢复旧 Phase-A / Phase-B 执行线。
- **授权状态。** 本交接的继续范围为源码与模拟。当前实机执行授权为无。任何历史已认领、已消费、过期或被替代的授权保持原状态。

## 5. 下一步

```text
NEXT_ONE_GATE=N3W_T1_OTA_V1_2_R4_ORIGINAL_MEDIA_AUTOMATIC_RECOVERY_RESUME
```

1. 重新核对远端 `main`、实现分支和 PR #815 的源码与 CI，核对 #814 的设计文档。工作从第 2 节的 R4 提交接续。若发现分支或架构依据漂移，先核对差异和现有证据。
2. 从宿主现有恢复入口接入原盘重新可用后的自动续办。核对 systemd 服务、原盘发现和恢复入口的关系，复用原事务锁、绑定盘和材料验证，以及两条已有恢复分支。恢复由宿主推进，状态接口只负责展示。
3. 用确定性测试验证缺盘、错盘、原盘返回、重复通知及恢复过程中断。证明错盘保留等待，原盘返回可续办，动作受同一锁串行保护。已完成的数据交换、前代镜像导入和启动在重入时按持久记录与实际运行状态协调。
4. 将源码、测试、精确提交和 CI 结果写回 PR #815。若遇到恢复材料身份不符或介质不可验证，保留事务与恢复材料，归档可重现证据。涉及真实设备或重要合并时按第 4 节停下。

## 6. 必读定位与归档

- [仓库 AGENTS.md](https://github.com/chrenguo-stack/HomeAssistant/blob/4fde1b7c5cc0aa224fa3574b8b4cc638edd93647/AGENTS.md)、[工作上下文第 12 节](N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set)、[当前状态](N3W_CURRENT_STATE.md)、[当前状态索引](N3W_CURRENT_STATE_INDEX.md)、[交接模板 1.4](templates/NEW_CHAT_HANDOFF_TEMPLATE.md)。
- [V1.2 架构与路线](N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md) 第 4、5、5.1、6 节和附录 A，[R2 源码对齐设计](https://github.com/chrenguo-stack/HomeAssistant/blob/41c06c1abf6ccaf05b977237a5b7bad3710f8031/docs/development/N3W_T1_OTA_V1_2_R2_SOURCE_ALIGNMENT_DESIGN_20261120.md) 的四阶段接线与实施顺序。
- 固定在 R4 评审提交阅读 [宿主恢复入口](https://github.com/chrenguo-stack/HomeAssistant/blob/2bd14fd4f4269eeb13c09d19cdfef01d4924c1c5/tools/n3w_t1_core_updater_ha_recovery_startup.py)、[USB 事务控制](https://github.com/chrenguo-stack/HomeAssistant/blob/2bd14fd4f4269eeb13c09d19cdfef01d4924c1c5/tools/n3w_t1_core_updater_ha_usb.py)、[开机恢复单元](https://github.com/chrenguo-stack/HomeAssistant/blob/2bd14fd4f4269eeb13c09d19cdfef01d4924c1c5/infra/n3w-t1/systemd/n3w-t1-ha-recovery-startup.service) 和 [故障注入测试](https://github.com/chrenguo-stack/HomeAssistant/blob/2bd14fd4f4269eeb13c09d19cdfef01d4924c1c5/tests/tools/test_n3w_t1_core_updater_ha_usb_r2.py)。遇到状态误判时补读 V1.2 第 170–171 行及 KF-168 历史记录。
- 已归档：PR #814 的 R1–R3 记录、PR #815 的 R4 源码与 CI、本交接的独立文档归档。未归档重要资料：无。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：

> 继续温室环境监测系统（ESP32-C6）N3-W 的 T1 OTA V1.2。先读本交接和适用仓库规则，重新核对 `main`、`feat/t1-ota-v1-2-alignment-20261120`、PR #815 和 R2 设计。已验证的 R4 源码为 `2bd14fd4f4269eeb13c09d19cdfef01d4924c1c5`。接续 R4 原 U 盘重新可用后的宿主自动恢复，完成源码、确定性模拟及 GitHub 归档。实机、合并和发布按交接边界处理。
