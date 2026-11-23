# N3-W T1 OTA V1.2 R8 PRE_U1 PASS → U1 PREPARE_REQUESTED 新会话交接 V1.0

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：继续“温室环境监测系统（ESP32-C6）”N3-W 的 T1 Core Stack OTA V1.2 R8 验收。当前目标是先用现有 U0-U13 正常 HA transaction 把备用 T1 从 exact Home Assistant 2026.10.4 准备到 exact 2026.10.0 predecessor 状态，再执行后续独立的 R8 2026.10.0 → 2026.10.4 正向验收。本次因对话上下文已很长而切换新会话。
- 已完成到：PR #824 executable source `ea68af045fdde8c32e66d688bc7a136a80b30122` 16/16 CI SUCCESS；exact recovery artifact 已安装到备用 T1；activation preflight 实机 PASS；当前 Manager 以 `natural_only` 监测模式兼容通过；exact 2026.10.0 target 与当前 2026.10.4 predecessor export 大小/摘要均已重新实测；当前仍停在 `PRE_U1`，没有新 HA transaction。
- 当前状态：`WAITING_FOR_OPERATOR_RESULT`。用户明确表示暂不在本对话执行已经准备好的 U1 命令；新对话将直接提供该命令的 Terminal 输出。不要在收到输出前假定命令已执行、U1 已创建或 USB 已挂载。

```text
CURRENT_STOP_POINT=PRE_U1
NEXT_EXPECTED_STOP_POINT=U1_PREPARE_REQUESTED
NEW_HA_TRANSACTION=false
TARGET_2026_10_0_LOADED=false
USB_TRANSACTION_WRITE=false
HA_MANAGER_STOPPED=false
```

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `review/t1-ota-r8-existing-tx-predecessor-prep-20261123`
  - PR: https://github.com/chrenguo-stack/HomeAssistant/pull/824
  - PR state: OPEN / DRAFT / mergeable at handoff preparation
- 核对时 main／本任务源码：
  - PR base/main snapshot: `7879981a809cdc2bc51d1aeeb45a7d6336c60214`
  - executable source head: `ea68af045fdde8c32e66d688bc7a136a80b30122`
  - executable head CI: `16/16 SUCCESS`
  - docs-alignment pre-handoff head: `675810ec68bc8dac71abc90dc2014afe5878dfd4`
- exact recovery artifact：
  - artifact ID: `14782528541`
  - name: `n3w-t1-ha-recovery-install-ea68af045fdde8c32e66d688bc7a136a80b30122`
  - ZIP SHA256: `dd2449ac934357a06e8889c3663add8ae2c018832b7c1db798aa9585e305973a`
  - manifest SHA256: `39e55949233f06afa535ac6dbc3ae3ca2fa72e04d8294c29c7dba0cefb2ee290`
  - installed PYZ SHA256: `ffc402f72fe56309b0f108c870230d8288dba740859232b9bc749abc354492b1`
- frozen exact 2026.10.0 target：
  - artifact run ID: `41275979177`
  - artifact ID: `13070404405`
  - artifact digest SHA256: `99eae7602eb2f8318bb7c0fff29d71fa61471071902b854a90666d4beb931b93`
  - target source head: `24382caae4a1f5d459297f86e8d18f10a848ca64`
  - target image: `local/n3w-homeassistant:2026.10.0-0c73235a`
  - archive size: `2448553472`
  - archive SHA256: `e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663`
- current predecessor measurement：
  - current HA: `local/n3w-homeassistant:2026.10.4-5881590f`
  - current HA image ID: `sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365`
  - `docker image save` measured size: `2447090176`
  - measured SHA256: `6502b8cdbf706d746e32311fdaa39ffc5ca703d76f766806bbb21d3c71278d1f`
  - internal available bytes at final read-only measure: `4748656640`
- 证据入口：
  - progress alignment: `docs/development/N3W_T1_OTA_V1_2_R8_PRE_U1_PASS_TO_U1_PREPARE_REQUESTED_PROGRESS_ALIGNMENT_20261123.md`
  - current state: `docs/development/N3W_CURRENT_STATE.md`
  - current state index: `docs/development/N3W_CURRENT_STATE_INDEX.md`
  - exact target authority: `infra/n3w-t1/upgrades/homeassistant-2026.10.0-r8-predecessor-preparation.json`
  - compatibility review: `infra/n3w-t1/upgrades/homeassistant-2026.10.0-r8-predecessor-preparation-compatibility-review.json`
  - final CI run for HA updater: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/45094584252
  - live PRE_U1 / read-only measurement evidence: PR #824 issue comments `7089147017`, `7089366939`, `7089423519`, `7089552674`, `7089661164`

## 3. 必须继承的结论

- 已证实：
  - R8 predecessor preparation 必须复用现有 HA U0-U13 durable transaction/recovery engine；不要恢复 scratch PR #823 的平行 state machine。
  - `ea68af04...` 已完成 16/16 CI SUCCESS，并已通过备用 T1 activation preflight。
  - live Manager 实际为 `local/greenhouse-manager:fresh-44e7d7472714`，不是仓库历史 authority 中的 `fresh-5b32e1ae8210`；它不含 optional OTA monitoring self-test，正确路径是 `monitoring_mode=natural_only`。
  - self-test 缺失本身不再是假失败；自然遥测证据不足或 capability probe 本身异常仍 fail-closed。
  - live Broker、Manager、Home Assistant、active Compose/env 在 activation preflight 前后均未改变。
  - 旧 HA USB transaction 保持 terminal `ROLLED_BACK/U13B_ROLLED_BACK`；新 transaction 必须新建，禁止 reopen 旧 COMMITTED/ROLLED_BACK transaction。
  - exact 2026.10.0 当前未加载到 Docker。
  - existing USB 是 ext4，身份已在私有运行时证据中绑定；最后一次测量时设备存在但 host namespace 未挂载，状态为 `ORIGINAL_MOUNT_REQUIRED`；不需要也不允许格式化。
  - 最终 read-only measure 没有创建 transaction、没有 USB transaction 写入、没有停止服务、没有 load/release image、没有 reboot。
- 待确认：
  - 用户下一条消息给出的 U1 命令运行结果。
  - 若 U1 成功：新 transaction ID、实际 USB mount/capacity、internal target spool、release pin 与 `U1_PREPARE_REQUESTED` exact document。
  - USB 实际剩余空间只有在受控挂载后才是 prepare-authority 的正式容量输入。
- 已排除：
  - scratch PR #823 / 新平行状态机：禁止继续。
  - 把 repository historical Manager tag 当作 live Manager identity：已证伪。
  - 强制要求 legacy Manager 提供 monitoring self-test：已修复。
  - 旧 `sha256sum -c -` operator command 路线：已弃用；后续摘要比较使用直接 digest equality。
  - 先前 checksum typo / mount-discovery 诊断 STOP 均发生在相应 mutation 前，未形成 OTA transaction 或业务状态漂移。

## 4. 执行范围与授权

- 可继续：
  - 用户已明确授权备用 T1 的 exact Home Assistant `2026.10.4 → 2026.10.0` predecessor-preparation transaction。
  - 授权范围包括：exact updater 使用、exact 10.0 candidate materialization、新 normal HA U0-U13 transaction、现有 USB binding、fresh exact 10.4 rollback image、fresh protected HA data backup、必要的 HA/Manager stop/start、在既有 gate 通过后释放 exact 10.4、导入/启动/验收 exact 10.0；失败时允许使用既有 U13B 自动恢复。
  - GitHub 源码复核、测试、CI 检查和归档可继续。
- 暂停边界：
  - USB format：禁止。
  - reboot / power cycle：禁止。
  - Broker OTA / Broker mutation：禁止。
  - PR #824 merge：禁止。
  - production release：禁止。
  - unrelated T1 mutation：禁止。
  - 当前已准备的下一条命令只允许推进到 `U1_PREPARE_REQUESTED`；不得在同一执行中自动进入 U1→U4。
- 授权状态：
  - bounded spare-T1 predecessor-preparation authorization: `ACTIVE`
  - authorization source: PR #824 comment `7087966758`
  - install authorization for the future new HA transaction: 尚未创建；当前没有可消费的新 install authorization。
  - 交接本身不新增任何授权。

## 5. 下一步

- 行动：
  1. 新会话先读取本交接、progress alignment、current state/index 和 V1.2 architecture 适用章节。
  2. 用户会直接贴出本对话最后已提供的“受控挂载 existing USB → publish exact 10.0 internal spool → materialize-candidate → maintenance PREPARE → stop at U1”的 Terminal 输出。
  3. 先解析实际最后成功 marker，不要假定整段 PASS，也不要重新生成/重跑命令。
  4. 若输出完整到以下 marker：
     ```text
     USB_MOUNTED_FOR_PREPARATION=PASS
     REMOTE_APPROVED_ENVELOPE_EXACT=PASS
     INTERNAL_TARGET_SPOOL_EXACT=PASS
     CANDIDATE_MATERIALIZED=PASS
     U1_TRANSACTION_EXACT=PASS
     SERVICES_UNCHANGED=PASS
     TARGET_10_0_NOT_LOADED=PASS
     USB_TRANSACTION_DIRECTORY_CREATED=false
     AUTHORIZATION_CLAIMED=false
     AUTHORIZATION_CONSUMED=false
     STOP_POINT=U1_PREPARE_REQUESTED
     LOCAL_RESULT=PASS
     ```
     则立即归档 U1 evidence，然后按 exact `ea68af04...` source 生成 prepare-authority，并推进 U1→U4。
  5. U1→U4 必须使用实测 predecessor export size `2447090176`、exact target size `2448553472` 和受控挂载后实际 USB free；不得用旧阶段估算替代。
- 完成条件：
  - 当前下一 gate：fresh normal HA transaction exact `U1_PREPARE_REQUESTED`；
  - HA/Manager/Broker 仍运行原组合；
  - exact 10.0 尚未加载；
  - 新 USB transaction directory 尚未写入；
  - authorization_claimed=false / authorization_consumed=false；
  - 结果与 transaction document 归档到 PR #824 和 progress/current-state。
- 失败／停点：
  - 若用户输出未到 `LOCAL_RESULT=PASS`，从最后成功 marker 分析。
  - 如果 failure 发生在 USB mount/identity/capacity：保持旧版，不继续 transaction/prepare。
  - 如果 internal spool 已存在但 U1 未创建：只读核对 exact spool/release pin/manifest，不重复上传或覆盖。
  - 如果 U1 已创建但后置验证失败：先读取 exact transaction document 和 runtime；禁止创建第二笔 transaction。
  - 任何状态不确定时先做最小只读 rebind；不要用猜测补状态，不要直接进入 U1→U4。

## 6. 必读定位与归档

- 仓库规则：
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`
  - `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.4
  - 适用仓库 `AGENTS.md`（如存在）
- 任务资料：
  - `docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md`：重点读第 1、3、4、5、6、9、10、11 节。
  - `docs/development/N3W_T1_OTA_V1_2_R8_PRE_U1_PASS_TO_U1_PREPARE_REQUESTED_PROGRESS_ALIGNMENT_20261123.md`：本轮 live/source/measurement 增量。
  - `docs/development/N3W_CURRENT_STATE.md` 与 `N3W_CURRENT_STATE_INDEX.md`：当前 route 入口。
  - `tools/n3w_t1_core_updater_ha_recovery_deploy.py`：`materialize-candidate`、candidate publication。
  - `tools/n3w_t1_core_updater_ha_recovery_startup.py`：prepare authority、U1→U4、original USB mount discovery。
  - `tools/n3w_t1_core_updater_ha_ipc.py`：maintenance PREPARE / HostOtaAdmission。
  - `tools/n3w_t1_core_updater_ha_usb_state.py`：U0-U13 state contract。
  - `infra/n3w-t1/upgrades/homeassistant-2026.10.0-r8-predecessor-preparation.json`：exact target authority。
  - `infra/n3w-t1/upgrades/homeassistant-2026.10.0-r8-predecessor-preparation-compatibility-review.json`：reverse-preparation compatibility。
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`：在进入 U5+ / 第一次停服前按需补读 U7/U9/U10 相关 guard。
- 已归档：
  - PR #824: https://github.com/chrenguo-stack/HomeAssistant/pull/824
  - progress alignment fixed source: https://github.com/chrenguo-stack/HomeAssistant/blob/3bc4c02c24bf3590def634f39e7bca9dabcaf660/docs/development/N3W_T1_OTA_V1_2_R8_PRE_U1_PASS_TO_U1_PREPARE_REQUESTED_PROGRESS_ALIGNMENT_20261123.md
  - current state/index 已在同一 candidate branch 对齐。
- 未归档重要资料：
  - 1 项：用户本地仍持有尚未执行的完整 Terminal 命令，其中含 private runtime locator/SSH 细节，按模板隐私规则不写入公开 GitHub。
  - 公开安全的执行合同、固定 target/predecessor identity、预期 marker、暂停边界均已归档。
  - 新会话由用户直接提供该命令的运行输出；若需重建命令，必须用 fresh private runtime rebind + 已归档 public contract 重建，不得从公开文档猜私有 locator。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=1
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：阅读本交接和适用仓库指令，按必读定位恢复任务。用户将直接贴出已经准备好的 U1 命令运行结果；先解析最后成功 marker 与实际 transaction/runtime 状态，在现有 bounded spare-T1 predecessor-preparation 授权内继续。完整 U1 PASS 后先归档，再推进 U1→U4；到达未授权边界时停止。
