# N3-W T1 OTA V1.2 R8 单镜像 CI PASS → 备用 T1 预检新会话交接 V1.0

`HANDOFF_TEMPLATE_VERSION=1.4`
`ARCHIVE_RECOVERY=true`

> 本文件在新会话恢复时发现此前仅完成于对话现场、未进入 GitHub 后补归档。内容以 PR #821 精确 HEAD、GitHub Actions 产物、R7 已归档实机证据以及上一轮最终停点重新绑定；不把未重新取得的实机状态写成 fresh PASS。

## 1. 目标与停点

- 任务／交接原因：继续 T1 Core Stack OTA V1.2 的 R8 单版本 Home Assistant 实机验收；目标是让备用 T1 先恢复到独立、可回滚的 `2026.10.0` 前代基线，再用 PR #821 的单镜像 OTA 实现验证 `2026.10.0 → 2026.10.4`。
- 已完成到：
  - PR #821 单镜像源码闭环；
  - 本地聚焦测试完成；
  - PR #821 HEAD 的 GitHub CI 13/13 SUCCESS；
  - PR #821 recovery install artifact 已生成并校验；
  - 上一轮备用 T1 仍运行 `2026.10.4`，写操作未开始。
- 当前状态：可继续只读预检；**停止在任何备用 T1 实机写入之前**。
- 容量判定冻结规则：T1 同一业务内置盘始终只要求驻留一个 HA 版本；正常升级先释放旧版，失败回滚先释放失败新版。容量结论只能使用**释放完成后、下一次导入前**重新测得的实际可用字节，不能用释放前余量，也不能要求同时容纳两个完整版本。

## 2. 代码与证据

- 仓库：`chrenguo-stack/HomeAssistant`
- PR #821：<https://github.com/chrenguo-stack/HomeAssistant/pull/821>
- PR #821 状态：Draft / open / unmerged。
- Base：`741a1463e7de065401749e47e59d30b295d5d6e8`
- 精确 HEAD：`eac5794afbeef265dee0f5f60d5e5223de111e35`
- Head branch：`review/t1-ota-r8-single-ha-20261122`

PR #821 关键源码：

```text
tools/n3w_t1_core_updater_ha_usb.py
tools/n3w_t1_core_updater_ha_usb_state.py
tools/n3w_t1_core_updater_ha_mounted_media.py
tools/n3w_t1_core_updater_ha_recovery_startup.py
tests/tools/test_n3w_t1_core_updater_ha_usb_r2.py
```

单镜像行为：

```text
NEW_TRANSACTION_INTERNAL_REQUIRED=max(INSTALL_PEAK, RECOVERY_PEAK)
NORMAL_INSTALL=verify materials -> journal release intent -> release predecessor -> remeasure -> import target
ROLLBACK=verify original rollback materials -> journal target release intent -> release failed target -> remeasure -> import predecessor
OLD_TRANSACTION_COMPATIBILITY=sum(INSTALL, RECOVERY)
NO_GLOBAL_DOCKER_PRUNE=true
EXACT_IMAGE_OWNERSHIP_REQUIRED=true
```

PR #821 CI：
- HEAD `eac5794afbeef265dee0f5f60d5e5223de111e35`
- 13 workflow runs all completed SUCCESS。
- HA exact target binding run：`45024175717`
- source job：SUCCESS
- exact-binding job：SUCCESS

Recovery install artifact：
- artifact id：`14755286389`
- artifact name：`n3w-t1-ha-recovery-install-eac5794afbeef265dee0f5f60d5e5223de111e35`
- GitHub ZIP SHA-256：`3e8d9be4100392403aef5af15c9782fe866db77be159dbe5c53814eda486c15e`
- `manifest.json` SHA-256：`f3dd26c2074c721e45d37f134cf9f90a1e269370b11eaf992e1f892b9053cd6c`
- `ha-recovery.pyz` SHA-256：`823a4522a34aae926913e8980fb9442af457084ff4243c74419ccdd66ff6a4e7`
- artifact manifest `source_head=eac5794afbeef265dee0f5f60d5e5223de111e35`

Frozen OTA target：
- target：`local/n3w-homeassistant:2026.10.4-5881590f`
- target archive SHA-256：`eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973`
- target archive size：`835309535`
- expected predecessor：`local/n3w-homeassistant:2026.10.0-0c73235a`
- platform：`linux/arm64`

Frozen `2026.10.0` image authority：
- workflow run：`41275979177`
- artifact id：`13070404405`
- artifact name：`n3w-t1-fresh-exact-arm64-24382caae4a1f5d459297f86e8d18f10a848ca64`
- source head：`24382caae4a1f5d459297f86e8d18f10a848ca64`
- artifact size：`2538800086`
- artifact ZIP SHA-256：`99eae7602eb2f8318bb7c0fff29d71fa61471071902b854a90666d4beb931b93`
- HA reference：`local/n3w-homeassistant:2026.10.0-0c73235a`
- upstream ARM64 manifest digest：`sha256:0c73235a9140a9b02e4bf618d06d8c496b12ae70656ecddb0e02ad31ad122be4`

## 3. 必须继承的结论

### 已证实

1. PR #821 的新事务不再要求内置盘同时容纳 predecessor + target；容量公式是两阶段峰值取最大值。
2. 两条回滚路径都先验证原 USB 回退材料，再释放失败 target，并在下一次 predecessor import 前重新测量空间。
3. 精确镜像删除只允许在独占 tag / image id / container 使用关系被证明后发生；没有使用全局 prune。
4. PR #821 exact source 与 recovery install artifact 已完成 CI 闭环。
5. 上一轮备用 T1 最后 fresh 证据运行 HA `2026.10.4`；最近一次释放前实测可用空间为 `4755177472` bytes。这个数值**只作为释放前基线，不能用于 R8 容量 PASS 判定**。

### 待确认

以下必须重新从备用 T1 取得 fresh read-only evidence：

- 当前 HA 是否仍为 `2026.10.4`，且 exact image/ref 未漂移；
- `2026.10.0` 是否仍驻留本机；
- 当前 HA USB transaction 的 phase/status/digest；
- 原绑定 U 盘是否仍存在、UUID 是否唯一匹配、当前是否已挂载；
- U 盘上的 `2026.10.4` predecessor archive 与 HA data backup 是否仍可重新验真；
- recovery package/service 是否仍未部署；
- 当前 internal/Docker free bytes；
- `2026.10.0` 切换所需前代镜像/数据材料是否已经足够，或仍需单独准备。

### 已排除

- 不再使用“释放前必须同时容纳两个 HA 版本”作为 R8 容量门。
- 不把旧的 U6/U7 摘要直接等同于本轮有效回退材料；必须重验。
- 不让 `2026.10.0` 直接读取已经被 `2026.10.4` 写过的数据目录。
- 不在预检阶段部署 recovery package、停止服务、删除镜像、导入镜像或修改 USB 内容。

## 4. 执行范围与授权

- 可继续：
  - GitHub / artifact / source 独立只读复核；
  - 开发、模拟测试和 GitHub 归档；
  - 备用 T1 严格只读预检；
  - 准备独立 `2026.10.0` 前代切换执行包，但默认必须处于未授权、不可执行状态。
- 暂停边界：
  - 任何 service stop/start/restart；
  - Docker container/image remove/load/tag；
  - HA 数据目录替换/恢复；
  - U 盘写入或重新格式化；
  - recovery package 安装、systemd daemon-reload/enable；
  - 正式 R8 OTA；
  - reboot；
  - merge/release。
- 授权状态：`LIVE_WRITE_AUTHORIZATION=NONE`。上一轮或其他事务的授权不得复用。

## 5. 下一步

1. 运行备用 T1 R8 strict read-only preflight，一次核对：
   - 当前运行版本和健康；
   - exact image residency；
   - internal/Docker 可用空间；
   - HA USB transaction；
   - 原绑定 U 盘存在/挂载状态；
   - 可读取时重新验证 `2026.10.4` rollback image archive + HA data backup。
2. 根据预检结果冻结独立 `2026.10.0` predecessor-switch execution package：
   - current `2026.10.4` recovery point 必须先被证明；
   - `2026.10.0` image/data baseline 必须独立于当前 10.4 数据；
   - package 默认无 live authorization；
   - release 后必须实测空间，只有实测结果满足下一次 import 才继续。
3. 到达第一次实机写入前，重新核对用户对**该 exact package / exact target / exact mutation scope**的授权；无授权即 STOP。
4. 前代 `2026.10.0` 健康基线建立后，再启动正式 R8 `2026.10.0 → 2026.10.4` 单镜像 OTA 验收。

完成条件：
- predecessor switch PASS；
- 备用 T1 fresh `2026.10.0` 健康；
- current `2026.10.4` rollback point 可验证；
- R8 OTA 正常升级、故障回滚、关键断电恢复按 V1.2 要求完成；
- 证据和 handoff 对齐 GitHub。

## 6. 必读定位与归档

- 根规则：`AGENTS.md`
- 开发效率：`docs/skills/greenhouse-github-development-efficiency/SKILL.md`
- 本地任务拆分：`docs/development/local-ai-task-splitting-rules.md`
- 归档规则：`docs/development/development-artifact-archive-rules.md`
- 团队共享：`docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`
- 工作上下文：`docs/development/N3W_PROJECT_WORKING_CONTEXT.md`
- OTA V1.2：`docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md`
- 已知故障：`docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`，重点继承 KF-158 停机状态误判规则。
- 上一阶段交接：`docs/development/N3W_T1_OTA_V1_2_R7_BASELINE_PASS_TO_R8_NEW_CHAT_HANDOFF_V1.0_20261122.md`
- 本轮只读预检入口：`tools/execution_packages/n3w/t1_ota_r8_spare_preflight/preflight.py`

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
LIVE_WRITE_AUTHORIZATION=NONE
NEXT_SAFE_ENTRY_POINT=R8_SPARE_T1_STRICT_READONLY_PREFLIGHT
```
