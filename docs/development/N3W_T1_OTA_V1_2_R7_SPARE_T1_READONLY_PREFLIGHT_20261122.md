# N3-W T1 OTA V1.2 R7 备用 T1 只读预检

2026-11-22。状态为已准备，等待操作者确认并在备用 T1 上执行。预检用于核对候选与备用机当前运行基线，确定后续实机验证所需条件。安装恢复包、改变服务、接管事务和介质写入另行授权。

## 固定候选

| 对象 | 依据 |
| --- | --- |
| PR #815 候选源码 | [`84da7cd68e2f65fb011c32db1c3683b76a48112b`](https://github.com/chrenguo-stack/HomeAssistant/commit/84da7cd68e2f65fb011c32db1c3683b76a48112b) |
| R6 终态 | [24 项工作流全部通过，ARM64 两种回执及三镜像下载复验通过](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44924757245/job/136908307028) |
| 恢复包 | [14715501376](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44924757335/artifacts/14715501376)，清单 SHA-256 `9cfad52a76670474cb328d3d22c0a7d4985f38f3e79fbe68e82a6b6550c8fa48`，11 个文件已逐字节核验 |
| 观测脚本 | [固定源码](https://github.com/chrenguo-stack/HomeAssistant/blob/3ef0c90f6ac46a0b78bc20503a409089c5629c1e/tools/execution_packages/n3w/t1_ota_spare_readonly/observe.py)，SHA-256 `00935467a0b6f8a496bbb1ad16dbb824227ee101df4c43f4203518979a4280ee` |

## Mac Terminal 命令

确认设备是本次获准取证的备用 T1。使用 Mac 已知的 SSH 别名或 `user@host`，主机密钥需已在本地确认。Mac 使用已登录且可访问仓库的 `gh` 和 `python3`；备用 T1 使用 Python 3.11 或更新，并通过本来已有的 root 登录或当前账号的无交互 sudo 执行读取。若测试盘已有挂载，提供实际完整路径；未挂载时留空，之后再确认空间。

```bash
(
  set -e
  printf '%s' '备用 T1 的 SSH 目标（输入后回车） '
  IFS= read -r t1_target
  test -n "$t1_target"
  printf '%s' '测试 U 盘的现有挂载路径（未挂载可直接回车） '
  IFS= read -r usb_mount
  r7_work="$(mktemp -d "${TMPDIR:-/tmp}/n3w-r7.XXXXXXXX")"
  gh api -H 'Accept: application/vnd.github.raw+json' 'repos/chrenguo-stack/HomeAssistant/contents/tools/execution_packages/n3w/t1_ota_spare_readonly/observe.py?ref=3ef0c90f6ac46a0b78bc20503a409089c5629c1e' > "$r7_work/observe.py"
  printf '%s  %s\n' '00935467a0b6f8a496bbb1ad16dbb824227ee101df4c43f4203518979a4280ee' "$r7_work/observe.py" | shasum -a 256 -c -
  gh run download 44924757335 --repo chrenguo-stack/HomeAssistant --name 'n3w-t1-ha-recovery-install-84da7cd68e2f65fb011c32db1c3683b76a48112b' --dir "$r7_work/package"
  python3 "$r7_work/observe.py" --ssh "$t1_target" --package "$r7_work/package" --usb-mount "$usb_mount"
)
```

命令在 Mac 临时目录保存材料，复核脚本摘要、恢复清单及其中 11 个文件。SSH 通过标准输入传送观测程序，在备用 T1 的内存文件中加载库。仅读取现有 Docker、systemd、HA HTTP、Broker 会话证据、事务文件和空间元数据。R7 使用实际组件状态作为后续审批输入。

## 结果核对

- 回传最后一行 JSON。 `R7_OBSERVATION_COLLECTED` 表示生成了观测报告。先检查 `errors`、三项运行身份、HA 版本、活动事务及两次读取是否一致，再决定 R7 是否通过。遇到其他版本或现有活动事务时，先保存状态和候选差异。
- `mqtt_authenticated` 是来自现有 Broker 日志的会话证据，日志覆盖不足单独记录。可用空间以当前挂载的文件系统为准。 `NOT_REQUESTED` 表示本次把 USB 测量留空。后续安装预算仍需核对完整候选材料、前代恢复量、HA 数据和暂存余量。
- 脚本已通过真实恢复包字节、篡改拒绝、SSH 标准输入组装、内存 ZIP 导入和模拟基线报告验证。待执行环境为备用 T1。

R6 完整证据见 [复核归档](https://github.com/chrenguo-stack/HomeAssistant/blob/68983eb95e99cb8c086d38cd2f346b65a43b44fd/docs/development/N3W_T1_OTA_V1_2_R6_HOME_ASSISTANT_OVERALL_REVIEW_20261121.md)。
