# N3-W T1 P3 U5 只读预检

## 当前停点

- P3 恢复回执为 `U4_RECOVERY_PASS`，事务为 `U4_READY_TO_INSTALL / ACTIVE`，SHA-256 为 `00167d489d785af6a458cd09826b9293dc29ec6c85b02ac75772017633d6f154`。该回执来自已执行的 U1→U4 恢复。[PR #807 实机回执](https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6968950587)
- 本预检以同一笔 U4 为入口，绑定归档 `835299595` 字节、SHA-256 `be30c4778bf537258d9e3825524c79532f20e8eb7a82136f560110d8f44b418d`，并从原 P3 的已消费授权账本核对 HA、Manager 和 Broker 的运行基线。
- 上述实机结果来自 U4 恢复。新预检的实机结果等待操作者 Mac 使用已固定 SSH 主机密钥执行。当前 P3 的 U5 INSTALL 一次性授权尚未绑定。

## 预检入口

`tools/execution_packages/n3w/r7a/u13b_p3_u1_u4_recovery/preflight.py`

- `--mode source-check` 核对当前工作树、原 P3 manifest、冻结源码和 U4 恢复入口。要求本地有原 P3 提交 `cddadc5bff1a00d4392de33680a5b0ad0acace1e`。
- `--mode read-only` 需要操作者本地传入 `--t1-ssh-target`、`--known-hosts`、`--expected-host-key-sha256` 和新建私有 `--evidence-root`。两种模式均传入本包的 `--expected-commit`。
- 远端只读取两笔既有账本、U4 Host 事务、按新文件系统 UUID 解析的 USB、该文件系统在当前进程及 OTA daemon 命名空间的 mountinfo、USB 五份事务元数据、目标字节、运行容器及部署文件。Manager 只发一次 IPC `status`。USB 挂载须已存在且具有产品要求的选项。预检不创建挂载、不改事务、不提交 INSTALL。
- 私有回执写入操作者本地的 `p3-u5-readonly-result.json`。终端输出采用白名单；GitHub 归档可用终端摘要与私有回执 SHA-256，保留原始 SSH、设备和进程信息在本地。

## U5 候选的进入条件

`P3_U5_READONLY_PREFLIGHT_PASS` 表示 U4、USB、目标、运行基线和 IPC 只读状态已经核实。摘要还报告部署哈希是否匹配及现场批准清单、发布策略的匹配结果。哈希或发布授权不匹配，需要在设计候选前复核。已审查的 daemon 固定入口只接受十六进制后缀的产品镜像标签，本笔 P3 的验收标签为 `2026.10.4-u13b-acceptance-v1`，原 P3 使用进程内适配器提供验收绑定。只有现场只读证据和对应部署源码才能确定当前可用的 INSTALL 路径。

后续候选需独立证明它可以按 P3 事务提交一次安装意图、核对 USB 先于 Host 持久化、处理提交后状态未知，并在 Host 与 USB 同为 `U5_INSTALL_REQUESTED_REVALIDATING` 时停下。安装意图使用新的一次性授权。旧 P3 和恢复授权均已消费。
