# N3-W 新会话交接：KF-147 R14 official U5 preflight → 已条件授权 INSTALL

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：继续 Home Assistant mandatory-USB OTA 的 U4→U5 收口。本轮已完成 R13 writable-mount real-T1 PASS、R14 official U5 read-only preflight successor 源码修复与 fresh CI 收口；因切换新对话停止，不再执行 T1。
- 已完成到：R13 real-T1 `POST_REBOOT_U4_MOUNT_RESTORATION_PASS`；R14 repaired exact source `340d5b4641735acd49c822139d4be75fea86aae0` 的 fresh CI 16/16 SUCCESS。
- 当前状态：可继续。下一物理动作是 **R14 真实 T1 official U5 只读 preflight**。R14 尚未访问真实 T1。

## 2. 代码与证据

- 仓库／分支／PR：`chrenguo-stack/HomeAssistant`；`fix/kf147-u3-recovery-and-error-visibility-20261110`；PR #807（open / draft / unmerged）。
- PR base：`fix/kf147-post-destructive-stop-readonly-forensic-20261110` @ `ab277001dc9b31dcccb4d36b1507cec5f26d5a1d`。注意：**PR base 不是 main**。
- 核对时 main：`3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`。
- 本任务 R14 可执行源码：
  - HEAD `340d5b4641735acd49c822139d4be75fea86aae0`
  - TREE `7fd26a27a76769aab949e235e68d93ea1b4fb333`
  - executor blob `5fa5233fc3e7c63d0ab21f9ab41df74b270a1ec7`
  - manifest blob `830e1e523740d415b569e24963b79e83b64bfc48`
  - focused test blob `abe41fd07e642a1a07e343cd624adb1cc38716cc`
  - SSH transport blob `5bc28b30e696bd3d0f5ae4c98fd81b8f8679aaa7`
- R14 gate：`N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_OFFICIAL_U5_PREFLIGHT_R14_20261113_01`。
- fresh CI：16/16 SUCCESS。关键 run：
  - HA target-binding `43345439735` SUCCESS
  - Manager A-to-B `43345439966` SUCCESS
  - Core Stack authority `43345439970` SUCCESS
  - fast source/exact closure `43345439912` SUCCESS
  - Public repository safety `43345439973` SUCCESS
  - storage/image lifecycle `43345439701` SUCCESS
- R13 实机执行源码：`6e1023b9cdfabb3997d2b7b0813f644f0df599e2`；R13 current terminal manifest blob `0720f548e099cbc74775aa0df80e7e3a0a9696bb`。
- 证据入口：
  - PR #807 R13 real-T1 PASS：comment `6840995131`
  - R14 首次 CI stale-gate 根因与修复：comment `6841101656`
  - R14 repaired CI waiting：comment `6841107966`
  - R14 fresh CI CLOSED_PASS + 下一授权说明：comment `6841229801`

## 3. 必须继承的结论

- 已证实：
  - R2 V1.2 8 文件 source activation 已真实 PASS；当前 T1 安装源码为 8/8 V1.2 target。
  - R13 real-T1 writable-mount restoration PASS，授权已 `claimed=true / consumed=true / replay=false`，不可重放。
  - 当前 T1 仍是 `U4_READY_TO_INSTALL`；transaction SHA-256 `dc6252c231269582233065558bdd21f7b52307a6e06b7d0104e594689853f259`。
  - target archive：SHA-256 `eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973`，size 835,309,535 bytes。
  - R13 后 USB mount 为 `rw,nodev,nosuid,noexec`，OTA service / Manager / HA / Broker 健康，IPC `READY_TO_INSTALL`。
  - R14 是只读-only preflight；没有 `--execute`、mount/umount、INSTALL 或 U5 mutation 路径。
  - R14 首次 CI 失败的唯一 focused 原因是 top-level + embedded remote 两处 stale R7 gate literal；已在 `340d5b46...` 修复，fresh CI 16/16 SUCCESS。
- 待确认：
  - 新对话必须 fresh rebind PR #807、branch head 和 main；若 R14 executable files 漂移，停止实机执行。
  - R14 real-T1 preflight 尚未执行，真实现场要重新证明 R13 terminal、writable mount、8/8 source、U4 transaction、target、runtime、IPC。
- 已排除：
  - 旧 R11 `U4_TO_U5_INSTALL_INTENT_TRANSITION_R11` 已 superseded，仍绑定 pre-V1.2 三文件源码与 fixed container ID，**禁止直接重放**。
  - 旧 R7 official-preflight 母版不可直接运行；R14 已替代。
  - `/dev/sda1` 等 `/dev/sdX` 仅是运行时观测，不得作为持久产品身份。

## 4. 执行范围与授权

- 可继续：
  - fresh rebind repository / PR / branch / exact R14 source；
  - R14 真实 T1 `--preflight-only`，只读；
  - R14 PASS 后，连续完成新的 V1.2-compatible U4→U5 INSTALL-intent successor 的源码设计/实现、源码复核、模拟测试、GitHub 归档和 fresh CI；
  - 在 exact successor + fresh CI PASS 后，将本轮用户授权绑定为 one-shot grant 并执行，不需要再次询问用户。
- 暂停边界：
  - R14 preflight 若 STOP：不得 INSTALL，先按实际 STOP 做 forensic/repair。
  - INSTALL successor 执行允许：IPC INSTALL request、Host transaction 从 U4 进入 `U5_INSTALL_REQUESTED_REVALIDATING`、对应 USB transaction metadata 更新；目标 archive 不得改写。
  - 禁止：直接重放 R11、自动重试已消费授权、source deployment、service restart、HA/Manager/Broker image mutation、U6+、board access、merge。
  - INSTALL successor 若 claim 后 STOP：授权视为已消费，不得重放；先 forensic close。
- 授权状态：
  - 来源：用户在 2026-11-13 当前对话明确指令：“新对话中继续 R14 真实 T1 official U5 只读 preflight，PASS后直接INSTALL，无需再申请授权”。
  - 目标：R14 PASS 后的 **新 exact V1.2-compatible U4→U5 INSTALL-intent successor**。
  - 候选：当前尚未生成，因此授权尚未绑定到 manifest，`claimed=false / consumed=false`。
  - 有效条件：R14 real-T1 PASS；successor 不扩大到 U6+；source review/测试/fresh CI PASS；exact candidate 与现场无漂移。
  - 当前状态：**条件授权已授予，等待 R14 PASS 后自动绑定；无需再向用户申请 INSTALL 授权。**

## 5. 下一步

- 行动：
  1. fresh rebind PR #807 / branch / main；确认 R14 executable source 仍为 `340d5b4641735acd49c822139d4be75fea86aae0` 或证明后续仅 docs-only。
  2. 按 exact R14 package 执行真实 T1 `--preflight-only`。
  3. PASS 后立即归档结果；不要再次询问授权。
  4. 以 superseded R11 的 U4→U5 transition 合同为功能参考，但绑定 R14 terminal + 8/8 V1.2 source + dynamic container identity，生成新的 successor（建议 R15 命名，实际以仓库现状为准）。
  5. successor source review / focused tests / fresh CI 全 PASS 后，把当前条件授权写入 exact manifest（one-shot、non-replay），然后执行 INSTALL/U5 transition。
  6. INSTALL 成功后停止在 U5，归档真实结果；U6+ 另行处理。
- 完成条件：
  - R14 real-T1 `official_u5_preflight_pass=true` / RC 0，且无 mutation；
  - 新 INSTALL successor fresh CI PASS；
  - live transition 返回 `U5_INSTALL_INTENT_TRANSITION_PASS`，Host/USB phase 都为 `U5_INSTALL_REQUESTED_REVALIDATING`，无 split state，无 U6+；
  - 所有 public-safe 证据归档 PR #807 / current-state docs。
- 失败／停点：
  - R14 STOP：停在 U4，不执行 INSTALL。
  - INSTALL preclaim STOP：授权未必消费，按 result 判断，不自动重跑。
  - INSTALL claim 后 STOP：one-shot 已消费，禁止重放；检查 host/USB phase 是否 split，先 forensic close。
  - CI 同一 run 最多主动查询 3 次；仍未终态则给链接并停轮询。

## 6. 必读定位与归档

- 仓库规则：
  - `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
  - [工作上下文的读取规则](../N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set)
  - `docs/development/development-artifact-archive-rules.md`
  - `docs/development/local-ai-task-splitting-rules.md`
  - `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`
- 任务资料：
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`：优先读取顶部 2026-11-13 authority。
  - `docs/development/N3W_CURRENT_STATE.md` / `N3W_CURRENT_STATE_INDEX.md`：核对当前 gate 和授权。
  - `tools/execution_packages/n3w/r7a/kf147_official_u5_preflight_successor/{executor.py,manifest.json}`：R14 exact preflight。
  - `tools/execution_packages/n3w/r7a/kf147_post_r2_u4_writable_mount_restoration_successor/manifest.json`：R13 terminal evidence contract。
  - `tools/execution_packages/n3w/r7a/kf147_u4_to_u5_install_intent_transition_successor/`：只作为历史功能参考；其 R11 manifest 已 superseded，禁止执行。
- 已归档：PR #807 comments `6840995131`, `6841101656`, `6841107966`, `6841229801`；本交接文件。
- 未归档重要资料：无。私有 T1 地址、host key、known_hosts 路径和原始 evidence root 不写入公开 GitHub；新对话使用已有私有上下文。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：阅读本交接和适用仓库指令，fresh rebind PR #807、branch、main 与 R14 exact package。先执行 R14 真实 T1 official U5 只读 preflight；PASS 后按本交接中的既有条件授权直接收敛并执行新的 V1.2-compatible U4→U5 INSTALL-intent successor，无需再次申请授权；到 U5 后停止。
