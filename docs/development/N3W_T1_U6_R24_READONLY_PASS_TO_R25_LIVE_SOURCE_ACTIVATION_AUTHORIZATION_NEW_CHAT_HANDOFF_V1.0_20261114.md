# N3-W T1 U6 R24 Read-only PASS → R25 Live Source Activation Authorization 新会话交接 V1.0

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：继续 Home Assistant mandatory-USB OTA 生命周期收口。当前会话已完成 R24 真实 T1 只读预检和 R25 source-activation successor 的源码、测试、CI 与独立复核；因会话较长，在 live mutation 授权边界切换新会话。
- 已完成到：
  - R24 real-T1 read-only preflight：`CLOSED_PASS`，run `U6-R24-READONLY-PREFLIGHT-20261114T005555Z`，RC=0，零 mutation。
  - R25 source authority：`da65fdd97e96c5b627341afd4eefd98105b858cf`。
  - R25 fresh CI：16/16 SUCCESS；HA target-binding source job：537 passed。
  - R25 final exact source review：PASS；`NEW_BLOCKER_COUNT=0`。
- 当前状态：可继续，但已到 **R25 live one-shot source activation 显式授权边界**。R25 尚未授权、未认领、未消费。新会话不要重复 R24 只读预检，也不要单独再跑 R25 `--preflight-only`；R25 `--execute` 自身在 staging/claim 前强制执行 fresh embedded preflight。

```text
R24_REAL_T1_READONLY_PREFLIGHT=CLOSED_PASS
R25_SOURCE_CLOSURE=CLOSED_PASS
R25_SOURCE_AUTHORITY_HEAD=da65fdd97e96c5b627341afd4eefd98105b858cf
NEXT_ONE_GATE=R25_LIVE_ONE_SHOT_SOURCE_ACTIVATION_EXPLICIT_AUTHORIZATION
R25_STANDALONE_PREFLIGHT_REQUIRED=false
R25_EXECUTE_EMBEDDED_PREFLIGHT_REQUIRED=true
```

## 2. 代码与证据

- 仓库／分支／PR：
  - Repository: `chrenguo-stack/HomeAssistant`
  - Branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR: https://github.com/chrenguo-stack/HomeAssistant/pull/807
  - PR state at handoff: OPEN / DRAFT / UNMERGED
- 核对时 main／本任务源码：
  - main: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - R25 exact tested source authority: `da65fdd97e96c5b627341afd4eefd98105b858cf`
  - docs alignment head before this handoff commit: `cfd223cc2184ad2554a8b80a81e5ec855db3375c`
  - docs-only advances must not replace `da65fdd9...` as R25 execution source authority.
- R25 exact blobs:
  - executor: `f3e3ad25cda278f8ed5888bfee11573ac5fdd29e`
  - manifest: `d0777d9c3c22d23ec195629e10ada845da6704f4`
  - focused test: `ed3823c84d675d7c921813c1aaaa8ae9eda4ab34`
  - HA target-binding workflow: `97a5dd86a5ecb8d526083b2aba5bd27e9af67102`
  - target prepare_host blob: `59b06d3aa595a6c4801b96d6b992b174a700ca31`
  - target install module blob: `c1da3f299d7091d2b49455299e7ad77801fc02dd`
- 证据入口：
  - R24 real-T1 PASS archive: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6868920233
  - R25 terminal source closure / authorization boundary: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6869836965
  - R25 HA target-binding CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43537781232
  - R25 Manager A-to-B CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43537781127
  - 当前状态文档：`docs/development/N3W_CURRENT_STATE.md`、`N3W_CURRENT_STATE_INDEX.md`、`N3W_PROJECT_WORKING_CONTEXT.md`，最新 working-context authority = V7.4。

## 3. 必须继承的结论

- 已证实：
  - R23 U5 IPC source activation 已 PASS；其一次性授权已 claimed+consumed，`replay_permitted=false`，不得重放。
  - 真实 durable transaction 仍是 `U5_INSTALL_REQUESTED_REVALIDATING`，SHA-256 `adfcf60d958c112edf61e2f4e31d73b16229fd027180ed68b87b8953231f0144`；不得 resubmit INSTALL。
  - R24 真实 T1 只读预检 PASS：target content exact、V1.2 content authority exact、predecessor runtime exact、服务/容器/IPC healthy、predecessor recovery residue 为空，且 transaction/USB/service/source 均未 mutation。
  - R24 观察到的 `/dev/sdX`、UUID/fingerprint 仅是运行证据，不是跨会话业务 authority。
  - R25 只激活两个文件：`tools/n3w_t1_core_updater_ha_prepare_host.py` 与新 `tools/n3w_t1_core_updater_ha_install.py`。
  - R25 不重启 OTA daemon；当前 daemon 进程不会被 reload。激活后由独立 Python import 验证两个新源码可加载，当前 daemon 继续使用已加载 backend。
  - R25 不写 USB、不改 transaction/USB transaction metadata、不进入 U6/U7+。
  - R25 execute 必须先 fresh embedded preflight；只有 preflight PASS 后才 staging，再 claim 授权。
  - R25 rollback：恢复 predecessor `ha_prepare_host.py`，删除新增的 `ha_install.py`；最多 1 次，无自动 retry。
  - R25 predecessor live `ha_prepare_host.py` SHA-256 = `fd2898cf9d63ae143b9620e56a19e9789306c802440bb9424cfc30064bc53005`；prestate 要求 `ha_install.py` 不存在。
- 待确认：
  - 仅剩用户是否明确授权 **R25 live one-shot source activation**。
  - 授权后需创建 grant-only successor，并在该授权 head 上 fresh CI + exact review；未完成前不得 live execute。
- 已排除：
  - 不再重复 R24 real-T1 read-only preflight。
  - 不单独重复 R25 `--preflight-only`；execute 内置 preflight 是唯一需要的写前 fresh preflight。
  - 不复用 R23 授权；R23 已 consumed/no-replay。
  - R25 不负责 U5→U6 transaction transition，也不负责 predecessor archive export。
  - 不允许 INSTALL resubmit、service restart、USB mutation、U6/U7+、board access 或 merge。

## 4. 执行范围与授权

- 可继续：
  - 新会话先做最小 fresh rebind：main、PR #807 当前 docs-only head、R25 exact source authority `da65fdd9...`、R25 terminal CI/closure。
  - 不改变设计的源码复核、文档/归档、CI 检查可连续推进。
  - **只有用户明确授权 R25 live one-shot source activation 后**，才可创建 grant-only successor；该 successor 只能把 manifest authorization 从 ungranted 改为 granted，并同步 focused-test 授权态预期，不得改变 executor/目标源码/执行合同。
- 暂停边界：
  - 当前必须停在 R25 live mutation 授权边界；现有对话未授予 R25 live mutation。
  - 未授权前禁止：T1 source deployment、remote staging、authorization claim、service restart、transaction/USB mutation、U6/U7+、board access、merge。
  - 授权后 grant-only successor 必须 fresh CI + exact review PASS 才能执行。
  - execute 后若出现 `STOP_UNKNOWN`、post-invoke transport/result uncertainty、claim persistence uncertainty，按 consumed/no-replay 处理，不得自动重试。
- 授权状态：

```text
R25_LIVE_EXECUTION_AUTHORIZED=false
R25_AUTHORIZATION_GRANTED=false
R25_AUTHORIZATION_CLAIMED=false
R25_AUTHORIZATION_CONSUMED=false
R25_REPLAY_PERMITTED=false
R25_CONFIRMATION=EXECUTE U6 R25 SOURCE ACTIVATION: YES
```

交接本身不授予 R25 live 权限。

## 5. 下一步

- 行动：
  1. fresh rebind 当前 PR head，并确认它只是 `da65fdd9...` 之后的 docs/handoff advance；R25 executor/manifest/test/workflow blobs不得漂移。
  2. **不要运行 R24 或 R25 standalone read-only preflight。**
  3. 直接进入 `R25_LIVE_ONE_SHOT_SOURCE_ACTIVATION_EXPLICIT_AUTHORIZATION`；等待/取得用户明确授权。
  4. 用户授权后创建 **grant-only successor**：
     - `live_execution_authorized: false -> true`
     - `authorization_state.granted: false -> true`
     - `claimed=false / consumed=false / replay=false` 保持不变
     - focused test 只同步授权态预期
     - executor、R25 source targets、gate ID、confirmation、执行合同不得改变。
  5. 对授权 successor 执行 fresh 16/16 CI 和 final exact review。
  6. 通过后执行 R25 `--execute`；其内置 preflight 必须 PASS 后才允许 staging/claim。
  7. 成功后要求：两个 target source exact、import validation PASS、U5 transaction SHA 不变、host/services/broker MainPID 不变、IPC U5 healthy、无 service/USB/transaction/U6 mutation；然后停止在真正 U6 transaction gate 前。
- 完成条件：

```text
R25_STATUS=U6_R25_SOURCE_ACTIVATION_PASS
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
SOURCE_ACTIVATED=true
U5_PRESERVED=true
IMPORT_VALIDATION=true
SERVICE_RESTART=false
TRANSACTION_MUTATION=false
USB_MUTATION=false
U6_TRANSITION=false
U7_PLUS=false
```

- 失败／停点：
  - embedded preflight 在 claim 前 STOP：归档实际原因，不做手工“修复后重跑”，先判断是否仍未 claim。
  - claim persistence unknown 或 execute 已调用后的 transport/result unknown：按 consumed/no-replay，禁止重放。
  - source mutation 后失败：只允许 executor 内定义的单次 rollback；归档 rollback 结果后停止。
  - proven success 后 remote/local cleanup failure：显式 STOP，不能回滚已经证明成功的 source activation。
  - 无论 PASS/STOP，都不得顺势进入 U6 transaction；下一门 gate 另行定义。

## 6. 必读定位与归档

- 仓库规则：
  - `AGENTS.md`
  - `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
  - `docs/development/local-ai-task-splitting-rules.md`
  - `docs/development/development-artifact-archive-rules.md`
  - `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`
  - [工作上下文的读取规则](./N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set)
- 任务资料：
  - 本交接文档。
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`：先读 V7.4 顶部 authority 和 §12 Minimum new-chat read set。
  - `docs/development/N3W_CURRENT_STATE.md`：读取最新 R24/R25 顶部块。
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`：读取最新 R24/R25 索引块。
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`：按 R25 的 unknown/no-replay、source activation/rollback、T1 live mutation 相关 guard 补读；不要重读全历史。
  - `tools/execution_packages/n3w/r7a/u6_source_activation_r25/executor.py` 与 `manifest.json`：执行前必须按 exact source authority `da65fdd9...` 核对。
- 已归档：
  - R24 real-T1 PASS：PR #807 comment `6868920233`。
  - R25 terminal source closure：PR #807 comment `6869836965`。
  - 三份状态 authority 已在 `cfd223cc2184ad2554a8b80a81e5ec855db3375c` 对齐。
- 未归档重要资料：
  - 无未归档的公共关键资料。
  - R24 raw evidence 仍按项目规则保存在用户私有本地证据区；公开交接仅保存 public-safe 摘要，不在仓库写入私有地址、known-hosts 路径、凭据或原始设备身份。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：阅读本交接、`AGENTS.md` 和 working context V7.4 顶部 authority，fresh rebind PR #807 与 R25 source authority `da65fdd9...`。**不要重复 R24 只读预检，也不要单独执行 R25 `--preflight-only`；直接进入 R25 live one-shot source activation 显式授权边界。** 未获授权时停止；获授权后只做 grant-only successor → fresh CI → exact review → R25 `--execute`，并停在真正 U6 transaction gate 前。
