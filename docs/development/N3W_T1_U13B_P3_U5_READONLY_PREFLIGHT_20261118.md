# N3-W T1 P3 U5 只读预检

## U4 基线与预检

- P3 恢复回执为 `U4_RECOVERY_PASS`，事务为 `U4_READY_TO_INSTALL / ACTIVE`，SHA-256 为 `00167d489d785af6a458cd09826b9293dc29ec6c85b02ac75772017633d6f154`。该回执来自已执行的 U1→U4 恢复。[PR #807 实机回执](https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6968950587)
- 本预检以同一笔 U4 为入口，绑定归档 `835299595` 字节、SHA-256 `be30c4778bf537258d9e3825524c79532f20e8eb7a82136f560110d8f44b418d`，并从原 P3 的已消费授权账本核对 HA、Manager 和 Broker 的运行基线。
- 操作者在预检提交 `bb05236958e1b0e451e7c5e392870e9d16cef773` 上完成实机只读检查，结果为 `P3_U5_READONLY_PREFLIGHT_PASS / EXIT_CODE=0`。私有回执 SHA-256 为 `99ceecf381c58cbd32439f37f0b9ca90f220a835b10040b302728fbc9f3bc70a`。主机与 USB 同为 U4，容器基线和目标字节一致，IPC 状态为 `READY_TO_INSTALL`。[PR #807 预检归档](https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6970090094)
- 现场安装文件匹配既有部署参考。标准 OTA 入口的批准清单和固定发布策略均与本笔 P3 验收事务不匹配，错误分别为 `approved_manifest_transaction_drift` 和 `ha_prepare_policy_binding_drift`。随后为本笔事务单独签发 U5 安装意图授权，见实机执行回执。

## 预检入口

`tools/execution_packages/n3w/r7a/u13b_p3_u1_u4_recovery/preflight.py`

- `--mode source-check` 核对当前工作树、原 P3 manifest、冻结源码和 U4 恢复入口。要求本地有原 P3 提交 `cddadc5bff1a00d4392de33680a5b0ad0acace1e`。
- `--mode read-only` 需要操作者本地传入 `--t1-ssh-target`、`--known-hosts`、`--expected-host-key-sha256` 和新建私有 `--evidence-root`。两种模式均传入本包的 `--expected-commit`。
- 远端只读取两笔既有账本、U4 Host 事务、按新文件系统 UUID 解析的 USB、该文件系统在当前进程及 OTA daemon 命名空间的 mountinfo、USB 五份事务元数据、目标字节、运行容器及部署文件。Manager 只发一次 IPC `status`。USB 挂载须已存在且具有产品要求的选项。预检不创建挂载、不改事务、不提交 INSTALL。
- 私有回执写入操作者本地的 `p3-u5-readonly-result.json`。终端输出采用白名单；GitHub 归档可用终端摘要与私有回执 SHA-256，保留原始 SSH、设备和进程信息在本地。

## U5 候选的进入条件

`P3_U5_READONLY_PREFLIGHT_PASS` 表示 U4、USB、目标、运行基线和 IPC 只读状态已经核实。摘要还报告部署哈希是否匹配及现场批准清单、发布策略的匹配结果。哈希或发布授权不匹配，需要在设计候选前复核。已审查的 daemon 固定入口只接受十六进制后缀的产品镜像标签，本笔 P3 的验收标签为 `2026.10.4-u13b-acceptance-v1`，原 P3 使用进程内适配器提供验收绑定。只有现场只读证据和对应部署源码才能确定当前可用的 INSTALL 路径。

后续候选需独立证明它可以按 P3 事务提交一次安装意图、核对 USB 先于 Host 持久化、处理提交后状态未知，并在 Host 与 USB 同为 `U5_INSTALL_REQUESTED_REVALIDATING` 时停下。安装意图使用新的一次性授权。旧 P3 和恢复授权均已消费。

## P3 U4→U5 安装意图候选

- 入口为同目录下的 `install_intent.py`。沿用 P3 已冻结的验收 manifest、原实机执行的完整依赖集合、产品 `request_install()` 和 USB 事务元数据写入方法。现场 OTA IPC 只查询状态。现场批准清单、发布策略和服务进程保持原样。
- 按原只读回执完整摘要复核现场，使用绑定的验收 manifest 和 USB 内的归档重新校验目标。校验异常在领取授权之前停止。进入写入时，先领取新的安装意图授权，再先写 USB 并核对镜像，最后写主机。成功要求两端均处于 `U5_INSTALL_REQUESTED_REVALIDATING`，IPC 返回对应状态，服务及容器连续，随后结束。
- 宿主账本落在专用 U5 目录。出现 SSH 超时、账本残留或一端写入时，使用 `--mode status` 只读核对账本和两端状态，禁止自动重试或自行修复。出现 USB U5、主机 U4 时停止并报告两端分歧。
- 源码验证使用 `--mode source-check`。候选需有原 P3 提交对象。执行必须使用在已验证候选之上、仅新增 `install_intent_grant.json` 的授权提交。新授权编号为 `N3W_T1_U13B_P3_U4_TO_U5_INSTALL_INTENT_20261118_01`，绑定候选提交、预检回执、U4 事务、目标归档、U5 上限和有效期。原 P3 与 U1→U4 恢复授权均不能重放。

## U5 实机执行回执

操作者在授权提交 `974b2fadba200a769b18ddbb6d1a2beb33decab7` 上执行 `install_intent.py --mode execute`。该提交绑定候选 `63e2c470eace97bfb15c0e7ff9ad7380e6884668`、阶段上限 U5 和本笔恢复事务。[授权提交](https://github.com/chrenguo-stack/HomeAssistant/commit/974b2fadba200a769b18ddbb6d1a2beb33decab7) · [P3 源码 CI](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44256709066)

```text
STATUS=P3_U5_INSTALL_INTENT_PASS
EXIT_CODE=0
STAGE=u5_verified
TRANSACTION_PHASE=U5_INSTALL_REQUESTED_REVALIDATING
TRANSACTION_SHA256=53141824bb5bd89f0911e217900ad50acee44cf6ef0ead891e867042a89dfe12
USB_METADATA_MATCHES=true
IPC_PHASE=INSTALL_REQUESTED_REVALIDATING
AUTHORIZATION_ID=N3W_T1_U13B_P3_U4_TO_U5_INSTALL_INTENT_20261118_01
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
U6_PLUS=false
RECEIPT_SHA256=cfef0e884513b93defb184bee46b46bb17268ab789a3b9abdbf3656604ea9577
```

主机和 USB 的 U5 事务记录一致，OTA IPC 状态与之相符。实机在 U5 停止。完整的 `install-intent-result.json` 留在操作者 Mac，以上摘要用于 GitHub 归档。后续可复用原 P3 已验证的 U6–U11 源码，从本笔 U5 事务接续。实机执行需另行授权。
