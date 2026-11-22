# N3-W T1 OTA V1.2 · R8 单版本候选 CI 通过至备用机预检交接

`HANDOFF_TEMPLATE_VERSION=1.4`

交接日期 2026-11-22（新加坡时间）

## 1. 目标与停点

- **任务和交接原因**　继续原定 R8，目标为备用 T1 上 Home Assistant `2026.10.0 → 2026.10.4`。按 V1.2 验收正常升级、失败后恢复旧版和数据，以及关键边界断电续办。本轮用户要求完成 GitHub 对齐，在新对话继续。
- **已完成到**　当前 `2026.10.4` 环境的数据备份和隔离解密还原通过。HA 和 Manager 原镜像均已离机校验。备用 T1 容量已只读复测。R8 单版本候选通过本地测试和 GitHub CI，新的恢复包已回读校验。
- **当前状态**　候选可进入实机执行包审查和写前只读复核。备用机最后仍运行原 `2026.10.4`，R8 新恢复包尚未部署，独立 `2026.10.0` 测试环境尚未建立，U 盘资格与切换后容量待验证。目前无本阶段实机写入授权。

## 2. 代码与证据

- **仓库主线**　[`main`](https://github.com/chrenguo-stack/HomeAssistant/tree/4fde1b7c5cc0aa224fa3574b8b4cc638edd93647) 核对时为 `4fde1b7c5cc0aa224fa3574b8b4cc638edd93647`。[PR #815](https://github.com/chrenguo-stack/HomeAssistant/pull/815) 为开放草稿，head `741a1463e7de065401749e47e59d30b295d5d6e8`。
- **R8 修复候选**　[草稿 PR #821](https://github.com/chrenguo-stack/HomeAssistant/pull/821) 叠加于 #815。分支 `review/t1-ota-r8-single-ha-20261122`，head `eac5794afbeef265dee0f5f60d5e5223de111e35`，源码树 `dc19ce0a7cba40a2810e9cf50b50540698a5767b`。两份 PR 均未合并。单版本及 USB 归档设计在 [V1.2 修订正文](https://github.com/chrenguo-stack/HomeAssistant/blob/1deb6422a136347d6ca9a852d5c07247b532f688/docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md)。
- **CI 终态**　在前次连续 3 次查询停止后，本次 GitHub 对齐重新核对 1 次。#821 精确 head 返回 13 项工作流，全部成功。[HA 目标绑定及恢复包](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/45024175717) · [Manager A-to-B](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/45024175726)。新对话仅在实际状态变化或准备推进时复核。
- **验证记录**　本地受影响测试 166 项通过。扩展验证 311 项通过、2 项跳过；执行环境缺 Docker 或 AF_UNIX 权限涉及的 4 项留给 CI。已验证正常单版本装载、失败新版释放、原数据还原、断电前后续办、U 盘缺失、额外镜像引用及实际释放不足。正式实机步骤仍待验。 [累计证据](https://github.com/chrenguo-stack/HomeAssistant/blob/ed70a0c12b6147ce0e8adb4e2c879c6aafb67df8/docs/status/n3w-t1-r8-readonly-preparation.md)

| 用途 | 固定产物与校验摘要 |
| --- | --- |
| #821 新 HA 恢复安装包 | [Actions 工件 14755286389](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/45024175717/artifacts/14755286389)，97749 字节。ZIP SHA-256 `3e8d9be4100392403aef5af15c9782fe866db77be159dbe5c53814eda486c15e`，清单 SHA-256 `f3dd26c2074c721e45d37f134cf9f90a1e269370b11eaf992e1f892b9053cd6c`，`ha-recovery.pyz` SHA-256 `823a4522a34aae926913e8980fb9442af457084ff4243c74419ccdd66ff6a4e7`。已校验清单内 11 件文件，包内四个修改模块与测试源码逐字节匹配，CLI 可执行。 |
| 测试前代 HA 和兼容 Manager | [Actions 工件 14716899788](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44930275030/artifacts/14716899788)，源码 `741a1463e7de065401749e47e59d30b295d5d6e8`，ZIP SHA-256 `1d4f857de78e5967ff94978411b813c8b7af0391d56e52ff3407ab480f0ae277`。使用 ARM64 HA `2026.10.0-0c73235a`、Manager `fresh-741a1463e7de`。Mac 已回读验证两份归档。 |
| 正式 OTA 目标 HA | [Actions 工件 13391983948](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/41976542377/artifacts/13391983948)，源码 `fb7cfc857003ace3d368521d76ca2320ba399736`，ZIP SHA-256 `df95749cec1e48796d2cf3241d19739601fe7be78c48638284d10eec786e4fd2`。内部归档 835309535 字节，SHA-256 `eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973`。Mac 已回读验证。 |

三份工件在本次查询时均未过期。新恢复包以 #821 为源码依据，旧恢复包 14717720726 留作缺口复现和历史对照。两份应用镜像产物的用途与新恢复包、现场运行镜像分别核对。

## 3. 必须继承的结论

- **设计和源码**　同一 HA OTA 的前代与目标在内置盘至多驻留一个。升级前验证 USB 恢复点，释放前代后复测，再导入目标。回滚先停写、验证原盘材料、按事务证明释放本笔失败目标，复测后装回前代，并按写入边界还原所需数据。容量按当前阶段的一份镜像及其工作区核算；共享层和已释放空间以实测为准。日常运行与断电接管所需内容保留在内置盘，镜像包、备用镜像与历史加密备份优先归档到 U 盘。
- **最后实机基线**　备用 T1 为 ARM64，标准 Compose 服务。HA `2026.10.4-5881590f` 的运行 ID 为 `sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365`。Manager 为 `fresh-44e7d7472714`，Broker 为 `2.1.2-3184566d`，以 [最近完整服务回执](https://github.com/chrenguo-stack/HomeAssistant/blob/315d6f5d6e37ef589544828360e735bc585399b8/docs/status/n3w-t1-r8-readonly-preparation.md) 为比对依据。当时 HA HTTP 401 符合未认证探测预期，HA 和 Manager 的 MQTT 认证通过。操作者确认现场无节点，未观察到新自然收数符合预期。进入 R8 后以已知测试收数和 Recorder 历史建立证据，候选部署后的运行状态目前为 `UNKNOWN_FRESH`。
- **原环境回退材料已保全**　`R8_CURRENT_BACKUP_PASS` 和 `R8_MAC_ENCRYPTED_COPY_VERIFIED=true`。加密数据归档 2107619 字节，SHA-256 `951e03aa715f44f41bededc9beb1e5ff8efd15e6fc57f6a2e798b851a8481f46`。同机密钥解密、隔离恢复和 6 个 SQLite 校验均通过。Mac 的原 HA 和 Manager 归档分别为 2447090176、62957568 字节，SHA-256 分别为 `6502b8cdbf706d746e32311fdaa39ffc5ca703d76f766806bbb21d3c71278d1f`、`4c1dbbc999aa678057da96da1d8161907ce9e8c25ef004e88c7fb725ac3db9fe`。密钥和私有副本路径在操作者现场。备份后原应用恢复、Broker 同一实例、事务未变。 [恢复回执](https://github.com/chrenguo-stack/HomeAssistant/blob/315d6f5d6e37ef589544828360e735bc585399b8/docs/status/n3w-t1-r8-readonly-preparation.md)
- **容量未放行**　`/dev/mmcblk2p2` 总量 14453903360 字节，已用 9681948672 字节，实际可用 **4755177472 字节**，使用率 68%。Docker、containerd、HA 数据和 OTA 事务目录报告同一分区。单个 HA 镜像最大展开量 2448486400 字节，基线余量高于该下限，但还须算导入及恢复工作区。最终判断以每次释放完成后、对应导入前的实测余量和已签发预算为准。U 盘已见 ext4，未挂载估计可用 28148965376 字节，正式资格、独占和当前实测容量待验。
- **约定的 R8 数据范围**　指定路径中未找到历史 R32 的匹配旧版备份。用户已同意用精确 `2026.10.0` 自行初始化的独立测试数据。历史 R32 数据迁移列为未覆盖。应保留原运行数据，防止旧版接触已由 `2026.10.4` 使用的数据。原 HA 正占用 OTA 目标标签，准备时要处理标签冲突和实际空间。原 Manager 缺候选自检能力，进入 R8 前须建立已验证的兼容 Manager 基线。测试期间 Broker 固定。
- **归档候选仍待逐项确认**　八个历史执行目录合计约 521 MB，仅为候选分配量。两个旧 Manager 镜像在事务记录有引用，Docker 汇总的 5.536 GB 可回收量无法归因到安全对象。未进行迁出、清理或全局 prune。

## 4. 执行范围与授权

- **可继续**　在原范围内连续进行 GitHub、精确产物和执行包核对，离线验证，容量和回退方案准备。备用 T1 的只读现场操作由操作者从 Mac 执行，使用已确认的 SSH 主机身份。命令提供可复制的无注释版本。
- **授权状态**　用户批准过使用独立前代测试数据、原环境停服备份与恢复，以及 #821 源码修改和当前余量复测。备份与恢复授权已执行完成，回执 `R8_CURRENT_BACKUP_PASS`。本轮未领取或消费新的 R8 安装、切换或断电授权。
- **暂停边界**　试验镜像装载或移除、数据目录或启动配置切换、恢复包部署及启用、USB 写入及现场归档迁移、正式安装和断电注入均需与备用机、候选和回退入口相符的授权。保持盘上既有资料。主线合并、生产发布、其他设备与 Broker OTA 在本次范围外。

## 5. 下一步

1. **写前只读复核**　重新绑定 `main`、PR #815/#821、工件 14755286389/14716899788/13391983948 及备用机。读取最小现场基线，核对实际启动单元、运行镜像、现有事务和 USB 身份、挂载命名空间及现时内置盘余量。已通过的备份校验仅在材料或绑定变化时补验。
2. **交付可审的前代切换与恢复执行包**　说明旧版独立测试数据如何形成、兼容 Manager 如何固定、如何在原数据和镜像有可验证回退入口的前提下处理目标标签冲突。明确何时释放哪个精确镜像、何时实测容量、失败如何恢复到原 `2026.10.4`。完成只读预检及离线故障路径验证，停在对应实机写入授权前。
3. **获准后建立前代和推进验收**　先核验前代版本和真实运行身份、本机 MQTT、HA HTTP、受控收数及可查询历史。再按对应授权部署恢复包、验证 U 盘与容量并启动正式 OTA。分别验证升级成功、失败目标释放后从 U 盘回滚、关键边界断电续办。各用例记录释放后实测余量和数据恢复结果。

**完成条件**　#821 或等效且重新验证的候选，能在备用机按单版本装载规则完成原定升级和故障恢复，确认版本、服务、受保护数据及事务终态，并归档实机回执。任何设备、镜像、介质、回退材料、容量或授权身份漂移都在相关写入前停下；现场若已经变更，按该笔事务绑定的恢复入口核对后续动作。

## 6. 必读定位与归档

- **仓库规则**　[AGENTS.md](https://github.com/chrenguo-stack/HomeAssistant/blob/4fde1b7c5cc0aa224fa3574b8b4cc638edd93647/AGENTS.md)、[最小必读范围](N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set)、[模板 1.4](templates/NEW_CHAT_HANDOFF_TEMPLATE.md)。
- **任务资料**　先读 [V1.2 设计修订](https://github.com/chrenguo-stack/HomeAssistant/blob/1deb6422a136347d6ca9a852d5c07247b532f688/docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md) 第 4、5、6、9、10 节，再按 [当前状态](N3W_CURRENT_STATE.md) 与 [状态索引](N3W_CURRENT_STATE_INDEX.md) 顶部 R8 条目定位。使用 [固定目标清单](https://github.com/chrenguo-stack/HomeAssistant/blob/741a1463e7de065401749e47e59d30b295d5d6e8/infra/n3w-t1/upgrades/homeassistant-2026.10.4.json) 核对目标。遇到容量或旧启停问题，按需读 [已知故障](KNOWN_FAILURES_AND_REGRESSION_GUARDS.md) 顶部 R8 条目及 R7 停机记录。
- **已归档**　[R8 累计证据](../status/n3w-t1-r8-readonly-preparation.md)、[旧候选缺口复现](https://github.com/chrenguo-stack/HomeAssistant/blob/02ca2ad77d276356b7e166495db50807fa8bd832/tools/execution_packages/n3w/t1_ota_spare_readonly/r8_rollback_space_verification.py)、[R7 固定交接](https://github.com/chrenguo-stack/HomeAssistant/blob/82f738dd37a5ad99f66e9e69679027fa843d0ca0/docs/development/N3W_T1_OTA_V1_2_R7_BASELINE_PASS_TO_R8_NEW_CHAT_HANDOFF_V1.0_20261122.md) 和第 2 节的源码、CI 与产物。
- **未归档重要资料**　无仅留在对话中的关键工程结论。原始终端材料、私有恢复路径和设备连接参数由操作者保留，公开 GitHub 采用脱敏回执和绑定摘要。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
AUTO_EXECUTE_NEXT_GATE=false
```

**新会话启动语**　阅读本交接及必读资料，续接备用 T1 的 R8 单版本 OTA 验收。先核对 PR #821 精确源码和已校验恢复包，核对备用机当前 `2026.10.4`、回退材料和 U 盘状态，准备独立 `2026.10.0` 前代切换执行包。以释放完成后、下一次导入前的实测余量作容量判断，在实机写入前核对对应授权。
