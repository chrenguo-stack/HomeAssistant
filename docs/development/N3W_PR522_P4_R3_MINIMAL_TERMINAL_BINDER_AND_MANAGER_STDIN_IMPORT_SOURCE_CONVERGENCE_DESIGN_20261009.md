# N3-W P4 R3：Mac Terminal 身份绑定与 Manager 现有标准输入导入最小收敛设计（2026-10-09）

```text
TASK=N3W_PR522_P4_R3_MINIMAL_TERMINAL_BINDER_AND_MANAGER_STDIN_IMPORT_SOURCE_CONVERGENCE_DESIGN_20261009_01
DESIGN_ONLY=true
SOURCE_BASE_PR=522
SOURCE_BASE_HEAD=58107b36fc20ccbef014d13cbfb708186395441c
MAIN_READONLY_BASE=d423211b6196c2f2f0f01dff072c4f877fbe58ee
R3_REVIEW=FAIL_SOURCE_BOUNDARY_AND_FIELD_IMPORT_NOT_READY
R3_SOURCE_SYNTHETIC=60_OF_60_PASS_HISTORICAL
OLD_R4_R5A_CHECK_TOOL_PRS=529_531_532_CLOSED_UNMERGED
MAC_TERMINAL=PRIMARY_EXECUTION_INTERFACE
T1_IP=OPERATOR_SELECTED_FROM_CURRENT_SITE_CONNECTION
FROZEN_IP_HASH_AS_NEW_GATE=false
EXTRA_SSH_HOST_KEY_PIN_AS_NEW_GATE=false
EXTRA_MAC_SOURCE_VERIFICATION_LAUNCHER=false
LIVE_T1_ACCESS=false
BOARD_ACCESS=false
REAL_QR_CAPTURE=false
SETUP_SECRET_IMPORT=false
MANAGER_MUTATION=false
PR_MERGE=false
STOP=true
```

## 1. 为什么要收敛，以及什么是权威

P4 需要的只是 **把屏幕上真正的二维码与 Manager 现有 pending 记录核对，确认后通过现有 Manager 通道接收 Setup Secret**。Mac 始终只用 Terminal。现场在每次操作前选取当前可达的 T1 IP，沿用既有 SSH 客户端配置及系统默认安全检查，不建立长期不变的 IP SHA、另加主机密钥清单或自校验 Python 启动器；**不关闭现有 SSH 验证**，也不因 IP 改变自动擦除节点配对信息。

PR #529、#531、#532 的附加 Mac 检查工具已经关闭且未合并。PR #528 的 R4 工具设计及 #530 的旧 R5a 现场执行器设计不再作为本任务实施权威；其中旧版冻结 IP/主机指纹方案不得被照搬。保留其历史记录以便审计。

本设计严格以 PR #522 原始 R3 源码为基准：`bridge_handoff.py` Git blob `e277949c3db5675bd460124832a382d6a2765539`、`validator.py` `3b7dc0d085dcda52fda0334840d75d5f8678bc1b`、`host_readonly.py` `b5732e2ae716c2bba9b5313aadec6cd8abf7b776`；Manager `n3w_pairing_cli.py` `1dc70189873f4d33f3de1e5bb6524c434d73b5ef`，`n3w_pairing_local_ipc.py` `ca709cbe7d86b70055f88800de2b4d6751fd95ff`，`n3w_simplified_pairing.py` `eba36d66bb094147dfcb5cfb021fb5f6f3ee02c3`，`registration.py` `230eeb45ce4aa2cf0a084d89eef901676500114d`。

前轮精确只读复核记录：https://github.com/chrenguo-stack/HomeAssistant/pull/522#issuecomment-6073053284 。旧 R3 CI 60 项 PASS 是源码模拟测试证据，不是现场导入通过。

## 2. 原有系统已经具备的部分

1. **二维码格式**：`bridge_handoff.parse_qr` 检查 `GHN3W2:hardware_id:pairing_id:setup_secret` 的格式，`capture_private_qr` 支持从非回显本地 TTY 输入，不写日志；光学 QR 来自真实产品 LCD，不能由 Manager 伪造替代。
2. **身份核对**：`bridge_handoff._project_once/project_readonly/bind_qr` 和 `validator.verify_sqlite_pairing` 在源码层支持旧五身份 + 唯一新 pending、二维码匹配、无旧 node_id/凭据/退役历史、只读 SQLite 状态核对及到期时间初次判断。两套代码功能有重合，应以一个最小绑定逻辑为主，避免再造第三套检查器。
3. **现有入口**：在真实 Manager 容器内，`greenhouse-manager-pairing import-payload --payload-stdin` 可从标准输入读取完整的一行 GHN3W2 内容，解析后调用 `import_setup_secret_over_socket`，通过 Manager 自有 Unix socket 向 coordinator 交付；命令行参数不含原始二维码或 Setup Secret。**当前入口存在，不等于本 P4 绑定和授权已接通。**
4. **现有状态保障**：`registration.Registry.approve` 源码检查 pending 是否过期，但 `SimplifiedPairingCoordinator.import_setup_secret` 自身只查 pairing ID 与 PENDING，**没有显式检查 expires_at**；`registry.get` 仅读取记录，不会自动将过期时间判为拒绝。不能把“最终批准检查过期”当作“秘密导入这一刻也检查过期”。
5. **ADR-0008**：`UNPAIRED -> PAIRING_PENDING -> Setup Secret PoP -> BUNDLE_DELIVERED -> durable receipt -> Manager COMMIT -> PROVISIONED`。导入返回 `accepted=true` 只表明 Secret 接收，不等于 COMMIT。

## 3. 收敛后的唯一实际操作流程

### G0. 首次产品正常启动之前：准备并 STOP

在 Mac Terminal 使用现行连接方式；只检查既有 P3 固件/板绑定、历史五身份私有快照、T1 上现行 Manager/IPC 只读可用情况和当前 pending TTL，准备全部命令和录入二维码的非回显通道。历史 P4 preboot PASS 保留，但不能拿已消耗的现场执行许可重复 SSH。

- 操作者每次从现场事实确定当前 T1 地址；网络变化时先停下来确定连接目标，再继续既有 SSH 流程。不要永久写死 T1 IP 或额外主机密钥指纹。
- 只将五个原身份的哈希用于本轮 R3 对比，不将五个原始硬件 ID 公开或上传 GitHub。
- 不连接新 USB、不对实板通电、不运行 import。

### G1. 获得新 pending 后：用原 R3 核对身份

未来另有明确实板启动授权后，真实板产生一次新 pending，在本地从屏幕光学扫描二维码。通过已经存在、经核实的 Mac Terminal / Manager 只读操作取得当次 Manager 注册数据库与凭据数据库的最新事实；不执行任何远程**任意 Python 文本**。

- 严格要求 5 个历史身份没有被修改；新身份 **恰好一个**；二维码硬件 ID 与 pairing ID 精确对应这条新 pending，初次出现、无旧 node_id/已分配凭据/其他配对历史。
- 使用现有 `validator.verify_sqlite_pairing` 或精简过的 `bridge_handoff`，不要同时强制跑两条等价检查路径。如果选择 Validator 路径，replay SQLite 只读结果也须按其既有源码合同提供；不得假装另一程序已取到了它。
- 初次绑定检查可保留原 R3 60 秒最小剩余时间策略，必须从 Manager 的 `expires_at` 计算，不能用“通电以来多少秒”代替，不能固定假定当前运行时 TTL 一定是 120 秒。
- **真正的取证通道**：优先复用 Manager 容器里已经存在的只读数据库读取能力和现有命令；下一源码修补门先以源码/模拟测试证明这条读取路线能在当前容器成立。如缺少能力，只允许为既有 Manager CLI 增加最小的只读 pending 状态查询入口或固定只读数据投影，不新建常驻服务、自定义通用 SSH 执行器、新的主机身份验证系统。是否需要新增接口，必须先做能力/依赖检查，不预判已经存在。

### G2. 人工确认后：仅一次通过已有入口导入

未来在首次启动与敏感导入**另行批准**之后，绑定 PASS，显示无秘密的硬件/配对哈希和剩余时间，操作者在 Mac Terminal 做一次明确确认。读取秘密不回显、不留 Shell 历史。完整二维码只经一次标准输入导给 **Manager 现有 `import-payload --payload-stdin`**，命令使用该场景内实际 Manager 容器与 pairing.sock，既不把 Setup Secret 放 argv，也不放环境变量、GitHub 或普通日志。

最终发送前复核唯一当前 pending、同一 pairing ID、有效 TTL 和最小余额。并且 **Manager 在真正执行 `import_setup_secret` 时自身必须再次检查** 当前 pairing 仍 PENDING、pairing ID 未变、当前时刻严格早于 expires_at。单靠 Mac 读一次数据库不能封闭查后到发送前的竞态。以 Manager 现有锁/事务为基础做最小修改，先由源码分析明确锁顺序及 race，不新增外部状态服务；模拟并发/过期/状态变化。客户端允许做最薄的一次性尝试记录：在发送前本地私有目录原子标记本轮尝试已消费，未知超时立即 STOP，不自动重发、不自动重新创建 importer；不设计新自定义配对身份体系或大型授权服务。

**禁止**把 `bridge_handoff.OneShotImporter` 的空方法（永远 reject）改成一个任意 `transport` 回调或一般化 SSH stdin 派发器。真实送达只用现有 Manager CLI/IPC 路径。

### G3. 结果和验收

导入器只显示无秘密的 `ACCEPTED`、`REJECTED` 或 `UNKNOWN`，无响应/超时/进程中断一律 UNKNOWN + STOP，不自动重试。若 accepted，则 **只记录已接收 Setup Secret**；必须另行只读确认产品完成 PoP、凭据接收、持久化回执与 Manager COMMIT，才能判定首次配对完成。后续受控断电与 canonical 数据验收仍属独立物理门，不能提前执行。

## 4. 必须删除或保留的代码：下一源码修补门

| 文件/模块 | 方向 | 理由 |
|---|---|---|
| `tools/.../p4_private_qr_pending_identity_binder/host_readonly.py` | **待依赖核对后删除**，或至少完整停用任意程序 `remote_snapshot_once` | 它接受调用者传入任何未绑定的 Python 程序，是 R3 的 A2 阻断；同时嵌有旧固定 T1 地址/源码合同 |
| `tools/.../p4_private_qr_pending_identity_binder/remote_projection.py` | 若仅被旧 `host_readonly` 使用则删除；否则缩小使用范围 | 避免重复强制绑定 IP/旧 Docker/TLS 静态身份 |
| `tools/.../p4_private_qr_pending_identity_binder/test_host_readonly.py` | 随被删模块替换，**不能仅删测试掩盖旧漏洞** | 以选定单一路径的最新模拟测试替代 |
| `bridge_handoff.py` | **保留光学 QR 解析与匹配；删除无用旧导入包装入口须先验证调用关系** | 保留产品核心的身份绑定 |
| `validator.py` | **优先保留只读 SQLite 验证与预启动历史快照合同** | 不重新实现第二套身份规则 |
| `host/greenhouse-manager/.../n3w_pairing_cli.py` | 保留 `import-payload --payload-stdin`；仅在事实证明缺少最小只读读数能力时补一个只读 CLI 入口 | 不重建导入传输协议 |
| `n3w_pairing_local_ipc.py` | **保留**现有导入协议、Unix socket 和秘密缓冲区清理 | 已有 Manager 拥有的通道 |
| `n3w_simplified_pairing.py` / `registration.py` | 只针对真实 Import 到期时间和锁内 pending 状态补最小防竞态逻辑 | 解决必要的 A5；不改恢复/密钥生命周期 |
| R4/R5A PR #529/#531/#532 及其 Mac launcher | **不采纳，不重开，不部署** | 用户明确取消；全部已关闭未合并 |

上述是**计划文件清单，不是已执行的删除操作**。在下一门源码修补之前，必须先按 PR #522 实际引用、构建/CI/部署的证据确认不会误删其他模块；未知依赖则 STOP，缩小删除范围。

## 5. 具体模拟测试：下一源码修补必须通过

| 测试类别 | 检查内容 |
|---|---|
| 现有核心保留 | 旧 R3 60 项相关用例按新目录/接口重新整理；合法光学 QR + 5 老身份 + 1 新 pending 能通过 |
| 源码删减范围 | 删除旧 SSH helper 后引用、CI 导入和旧假阳性均得到处理；恶意调用者不能再提交任意远程程序给所谓只读接口 |
| 正常变更 IP | 使用不同的合成 T1 现行 IP、相同 Manager 状态，身份绑定不依赖固定旧 IP 哈希；不禁用既有 SSH 默认验证 |
| 异常身份 | 旧历史身份被改、额外新设备、多个 pending、错误二维码、错配 pairing ID、已退役/已有 node_id/credential 都 STOP |
| TTL 临界 | 已过期、剩余 0/59/60 秒、查后超时、Manager pending 被更换或取消；只读绑定与正式进口各自拒绝 |
| 并发竞态 | 查询通过后 Session 被变更、刚好到期、另一线程批准/取消导致状态变化，Manager 导入在锁内或等效的原子状态检查处拒绝 |
| 一次性尝试 | 一个 import 请求；连接失败可证明未发送仍 STOP；请求后超时/进程重启/ACK 丢失 UNKNOWN，不自动二次 import |
| Secret 通路 | 真正 stdin -> Manager CLI -> Manager-owned Unix socket -> Coordinator；不能把原始 QR/Secret 写入 argv、普通日志、GitHub |
| 结果区分 | `accepted=true` != COMMIT，后续产品状态没有成功时不能报 P4 PASS |
| 无关回归 | Direct/Relay、原有 KF-050、Broker、P3 artifact、Manager 其他 IPC 操作都不被改动 |

仅用合成 T1、假二维码、假身份、假 Setup Secret、模拟时间及线程；不打开任何真实 SSH、不访问板、不导入真实秘密。

## 6. 开发分步与 STOP

```text
DESIGN_DECISION=MAC_TERMINAL_AND_EXISTING_MANAGER_STDIN
R3_A1_QR_BINDING=SOURCE_PASSED_KEEP
R3_A2_ARBITRARY_REMOTE_SOURCE=REMOVE_OR_FAIL_CLOSED
R3_A3_RUNTIME_READER=MINIMAL_EXISTING_CLI_OR_FIXED_READONLY
R3_A4_REAL_T1=NOT_EXECUTED
R3_A5_IMPORT_PENDING_TTL_AT_USE=SOURCE_REPAIR_REQUIRED
R3_A6_OPERATOR_CONFIRMATION_AND_UNKNOWN_STOP=SMALLEST_ONE_SHOT_FLOW
PRODUCT_SECRET_INTERFACE=MANAGER_UDS_UNCHANGED
IP_FROZEN_ADDITIONAL_GATE=DISALLOWED
EXTRA_HOST_KEY_FINGERPRINT_GATE=DISALLOWED
EXTRA_MAC_SOURCE_LOADER=DISALLOWED
P4_FIRST_NORMAL_BOOT=NOT_AUTHORIZED
REAL_SECRET_IMPORT=NOT_AUTHORIZED
NEXT_ONE_GATE=N3W_PR522_P4_R3_MINIMAL_TERMINAL_BINDER_SOURCE_CONVERGENCE_AND_SYNTHETIC_20261009_01
NEXT_GATE_LIMIT=SOURCE_ONLY_R3_BINDER_AND_EXISTING_IMPORT_EDGE_WITH_SIMULATED_TESTS
NEXT_GATE_MUST_START=DEPENDENCY_MAP_AND_MANAGER_AT_USE_LOCK_REVIEW
NEXT_GATE_EXCLUDES=REAL_T1;REAL_BOARD;REAL_QR;REAL_SECRET;MERGE
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
```

下一门应先取证 **哪些代码实际调用旧任意 SSH helper、哪些 Manager 锁保护已有 pending/导入**，随后才修改源码；如果发现必须改变生产 Manager 服务协议，单独标明范围并独立复核，不能暗中扩大任务。该门结束后必须有合成回归、源码独立复核、GitHub 证据，不自动进入物理首次配对。
