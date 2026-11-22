# N3-W T1 OTA V1.2 · R7 运行基线通过至 R8 实机验收交接

`HANDOFF_TEMPLATE_VERSION=1.4`

交接日期 2026-11-22（新加坡时间）

## 1. 目标与停点

- **目标**　按原路线在备用 T1 验收 Home Assistant `2026.10.0 → 2026.10.4`。依据 OTA V1.2 验证升级成功后业务恢复，并在原定失败场景验证能够自动回到健康运行状态。
- **已完成到**　R7 实机退出旧 OTA 运行方式，恢复 Clean Reference 标准应用管理。随后用严格只读检查得到 `RUNNING_BASELINE_PASS`。本轮用户要求完成 GitHub 对齐和交接，R8 由新对话继续。
- **当前状态**　R7 运行基线收口。备用 T1 当前健康运行于 `2026.10.4`。R8 固定候选要求 `2026.10.0` 前代，需先确认可恢复的数据基线和恢复授权。V1.2 恢复组件尚未部署，U 盘未完成资格检查，R8 实机执行尚未开始。

## 2. 代码与证据

- **仓库与分支**　归档在现有 [R7 审查分支](https://github.com/chrenguo-stack/HomeAssistant/tree/review/t1-ota-r7-clean-reference-20261122)。产品候选为 [PR #815](https://github.com/chrenguo-stack/HomeAssistant/pull/815)，源码分支 `feat/t1-ota-v1-2-alignment-20261120`。本轮为文档归档。
- **提交绑定**　`main` 核对时为 `4fde1b7c5cc0aa224fa3574b8b4cc638edd93647`。PR #815 候选为 `741a1463e7de065401749e47e59d30b295d5d6e8`。R7 恢复包构建源码为 `84da7cd68e2f65fb011c32db1c3683b76a48112b`。实机运行组成以第 3 节回执为准。
- **R7 可复核入口**　[最终执行器 6e9928a](https://github.com/chrenguo-stack/HomeAssistant/blob/6e9928a04fb81b9613c5e46e422eb10770926785/tools/execution_packages/n3w/t1_legacy_ota_cutover/executor.py)、[只读观察器 3af2bf6](https://github.com/chrenguo-stack/HomeAssistant/blob/3af2bf616d5e56c69f695b18a16d5377bb070950/tools/execution_packages/n3w/t1_ota_spare_readonly/observe.py)、[实机回执与修订过程](https://github.com/chrenguo-stack/HomeAssistant/blob/851d0fb958fb1858171b862ef5a068151abc4591/docs/status/n3w-t1-r7-legacy-ota-cutover-precheck.md#spare-t1-cutover-and-strict-r7-running-baseline-passed)。
- **CI 对齐快照**　对 PR #815 精确候选核对一次，接口返回的 25 项工作流均已完成并成功。与本任务直接相关的 [精确源码](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44930275080)、[初始化源码](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44930275103)、[HA 目标绑定](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44930275032)、[公开仓库安全检查](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44930275063)。以新会话核对的实际候选提交作为后续判断依据。

| 产物 | GitHub Actions | 绑定摘要 |
| --- | --- | --- |
| 备用 T1 出厂 ARM64 三镜像，HA `2026.10.0-0c73235a` | [运行 41275979177](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/41275979177)，ID `13070404405` | 源码 `24382caae4a1f5d459297f86e8d18f10a848ca64`，ZIP SHA-256 `99eae7602eb2f8318bb7c0fff29d71fa61471071902b854a90666d4beb931b93` |
| R8 固定目标 HA `2026.10.4-5881590f` | [运行 41976542377](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/41976542377)，ID `13391983948` | 源码 `fb7cfc857003ace3d368521d76ca2320ba399736`，ZIP SHA-256 `df95749cec1e48796d2cf3241d19739601fe7be78c48638284d10eec786e4fd2`，内层镜像归档 SHA-256 `eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973` |
| R7 使用的 V1.2 恢复包 | [运行 44924757335](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44924757335)，ID `14715501376` | 源码 `84da7cd68e2f65fb011c32db1c3683b76a48112b`，ZIP SHA-256 `078500292fba59c2acd187ca3613258a7c6d1c6594113d925e98352d4bc9b055`，清单 SHA-256 `9cfad52a76670474cb328d3d22c0a7d4985f38f3e79fbe68e82a6b6550c8fa48`，`ha-recovery.pyz` SHA-256 `f39629268ffeab9906f9de8cb60362d604d5b9150ef4c13571926b00921e6b84` |

表中三个产物在 2026-11-22 核对时均未过期。出厂构建提供容器镜像，恢复方案仍需匹配的数据基线和回退备份。

## 3. 必须继承的结论

- **初始化修复已在备用 T1 验证**　先取得 `R7_PROVISION_RESUME_NOOP_PASS / UNPROVISIONED / NOOP`，随后部署通过 `R7_PROVISION_DEPLOY_PASS`。初始化服务为 `active/exited`。旧式初始化记录缺失时，以匹配的 Clean Reference R2A、R2B 与运行身份记录确认来源。 [初始化与防回归记录](https://github.com/chrenguo-stack/HomeAssistant/blob/0b206e46ab427d22161e8565e56d4f3fda384710/docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md)
- **实机切换与只读基线通过**　`R7_LEGACY_CUTOVER_PASS`、`RUNNING_BASELINE_PASS`、`diagnostic_only=false`、`errors={}`、`EXIT_CODE=0`。旧 `n3w-t1-ha-ota.service` 已停用，应用服务使用标准 Compose 启停。HA HTTP 401 符合未带认证信息的探测预期。HA 和 Manager 的 MQTT 认证通过，监听及镜像引用与 Compose 一致，三项容器重启计数均为 0。
- **备用 T1 观测组成**　`linux/arm64`。Broker 为 `local/n3w-mosquitto:2.1.2-3184566d`，Manager 为 `local/greenhouse-manager:fresh-44e7d7472714`，HA 为 `local/n3w-homeassistant:2026.10.4-5881590f`，HA 镜像 ID 为 `sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365`。当次可用空间 `4759891968` 字节，运行存储可写。新会话需以新鲜观测确认设备、磁盘、服务及介质，历史观测只作为比对依据。
- **连续性与历史状态**　切换期间 Broker 为同一运行实例，应用数据挂载保持，Stack 为 `COMMITTED`（摘要 `39c076050122402f93b4956523129e4555df210d8e45caea1ababd88f1ee3d0b`），HA USB 事务为 `ROLLED_BACK`（摘要 `a427bef98d2886234bf706eb1347f09148429e44c79ab08f01e1071dd0722492`），旧 Manager 事务为空。旧服务覆盖备份 `.95-n3w-ha-ota.conf.r7-backup` 已复用并保留，SHA-256 为 `cee2d95971a1d91adeec4f7974d0bac1f4b7eab379168e91459d3d07641f1800`。
- **停机判定**　前两次进入停机的尝试均验证回退成功。最终成功回执显示 systemd 和两个原容器均退出为 `137`，主进程和控制进程均无 PID，两个容器停止且无重启、无 Docker 运行时错误和 OOM 标记。停机验收依据进程和容器状态，退出码作为诊断证据。修订执行器另有 19 项离线模拟通过记录。 [现场实证与测试范围](https://github.com/chrenguo-stack/HomeAssistant/blob/851d0fb958fb1858171b862ef5a068151abc4591/docs/status/n3w-t1-r7-legacy-ota-cutover-precheck.md)
- **待确认**　V1.2 包在 T1 上不存在，IPC socket、重试 timer 和启动恢复 service 均未激活。末次 USB 复检为 `NOT_REQUESTED`。更早实机曾看到约 29.8 GiB 的 ext4 USB 分区，在宿主机和其他挂载命名空间均无挂载。新会话重新核对设备身份、挂载和容量，挂载路径为 `UNKNOWN_FRESH`。
- **R8 的数据约束**　当前 HA 镜像即冻结目标。[目标清单](https://github.com/chrenguo-stack/HomeAssistant/blob/741a1463e7de065401749e47e59d30b295d5d6e8/infra/n3w-t1/upgrades/homeassistant-2026.10.4.json)绑定前代 `2026.10.0-0c73235a`。排除在现有 `2026.10.4` 上重复应用同一镜像或让 `2026.10.0` 读取已被较新版本使用的 HA 数据。沿用原定版本组合和 V1.2 规则。

## 4. 执行范围与授权

- **可继续**　新会话先做 GitHub、产物和恢复方案的只读核对。涉及备用 T1 的终端取证按项目约定由用户在 Mac 执行，命令可直接复制且无注释。用私有现场资料核对 SSH 主机身份。开发、离线验证和 GitHub 归档可在原范围连续推进。
- **已执行授权**　用户批准过备用 T1 的 R7 标准运行方式切换，该操作已完成并有通过回执。历史 V1.0 实验授权仍按其原有范围和记录处理。
- **暂停边界**　先确定现有 `2026.10.4` 数据的保存范围、备份位置、验真和回退入口，核对能否获得匹配的 `2026.10.0` 数据基线。恢复或重装、部署或启动 V1.2 恢复组件、将介质用于写入以及执行 OTA 均按相应阶段核对授权。当前无 R8 实机写入授权。本轮只归档，交接本身不授予权限。
- **现场约束**　范围限备用 T1。保留现有 U 盘数据，格式合格可复用。历史故障注入覆盖及旧事务只作证据。主线合并、生产发布、主机外的板卡操作以及 Broker OTA 不属于此次 R8。

## 5. 下一步

1. **先做 R8 只读准备**　重新核对 `main`、PR #815 和三类精确产物，检查冻结目标清单。用最小现场检查确认备用 T1 仍对应最后一次 R7 回执、设备与存储实际状态，以及 U 盘是否已挂载和可用。源代码、产物或现场状态发生变化时，针对变更补验。
2. **提交可执行的前代恢复方案**　绑定备用 T1、`2026.10.0` 镜像和匹配的数据基线。列清现有数据的要保留项、备份位置、摘要与可恢复性证明，以及恢复失败时回到 `2026.10.4` 的入口。执行前停在专项授权。没有匹配数据或回退材料时保留当前健康环境。
3. **恢复获准后按原 R8 线路验收**　先验证 `2026.10.0` 前代严格基线，复核版本、镜像、HA HTTP、MQTT、Broker、存储和事务终态。再按对应授权完成 V1.2 恢复组件部署与候选预检、U 盘资格核对和 OTA 实机验收。成功时验证目标镜像、服务恢复与数据连续性。按原定失败场景验证自动恢复、前代及关键业务健康，并分别归档结果。任何前代身份、数据、介质、候选或授权漂移都在受影响操作前停下。

## 6. 必读定位与归档

- **仓库规则**　[AGENTS.md](https://github.com/chrenguo-stack/HomeAssistant/blob/4fde1b7c5cc0aa224fa3574b8b4cc638edd93647/AGENTS.md) · [最小必读范围](N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set) · [交接模板 1.4](https://github.com/chrenguo-stack/HomeAssistant/blob/4fde1b7c5cc0aa224fa3574b8b4cc638edd93647/docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md)。
- **任务资料**　[当前状态](N3W_CURRENT_STATE.md)和[状态索引](N3W_CURRENT_STATE_INDEX.md)顶部备用 T1 R7 / R8 条目；[V1.2 架构](https://github.com/chrenguo-stack/HomeAssistant/blob/480afb109de59477b11f6d1cdf794f656eb39805/docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md)的 1、3、5、6、9、10、11 节；[R8 精确目标清单](https://github.com/chrenguo-stack/HomeAssistant/blob/741a1463e7de065401749e47e59d30b295d5d6e8/infra/n3w-t1/upgrades/homeassistant-2026.10.4.json)。处理停机误判时补读 [R7 防回归条目](https://github.com/chrenguo-stack/HomeAssistant/blob/0b206e46ab427d22161e8565e56d4f3fda384710/docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md)及 KF-158。
- **已归档**　[R7 停机、回退、最终切换与基线实机证据](https://github.com/chrenguo-stack/HomeAssistant/blob/851d0fb958fb1858171b862ef5a068151abc4591/docs/status/n3w-t1-r7-legacy-ota-cutover-precheck.md)；第 2 节的执行源码、候选与构建产物；当前状态、索引及本交接均在 R7 审查分支。
- **未归档重要资料**　无仅存在于对话、且缺少公开等价证据的工程结论。原始终端输出和机器专用 SSH 参数留在私有现场资料，GitHub 使用脱敏回执。含现场连接参数的临时启动脚本保留在私有上下文。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
AUTO_EXECUTE_NEXT_GATE=false
```

**新会话启动语**　阅读本交接与必读资料，继续 N3-W T1 OTA V1.2 的原定 R8 验收，目标为备用 T1 上 `2026.10.0 → 2026.10.4`。从 GitHub、精确产物和备用 T1 的最小只读核对开始。备齐并核验前代数据、现有数据备份和回退方案后，在实机写入前核对授权。
