# N3-W P4 R3：Mac Terminal → 只读 Pending → 光学二维码绑定 → 一次标准输入导入：最小设计（2026-10-09）

```text
TASK=N3W_PR522_P4_R3_TERMINAL_QR_PENDING_BINDER_AND_ONESHOT_STDIN_IMPORT_DESIGN_20261009_01
DESIGN_ONLY=true
SOURCE_BASE_PR=534
SOURCE_BASE_HEAD=b60d05a1610ed10e14b859fa64dd760eeb7c2bb7
PREDECESSOR_DESIGN_PR=533
ORIGINAL_P4_PR=522
MAIN_REBOUND_HEAD=d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR534_REVIEW=PASS_WITH_FIELD_INTEGRATION_GAPS
PR534_CI=14_OF_14_PASS
MAC_TERMINAL_PRIMARY=true
CURRENT_T1_IP_SELECTED_AT_USE=true
NEW_FROZEN_T1_IP_GATE=false
EXTRA_SSH_HOSTKEY_MANIFEST=false
INDEPENDENT_MAC_TRUST_LAUNCHER=false
MANAGER_IMPORT_INTERFACE=EXISTING_IMPORT_PAYLOAD_STDIN_AND_UDS
REAL_T1_SSH=false
REAL_BOARD_BOOT=false
REAL_QR_CAPTURE=false
REAL_SETUP_SECRET_IMPORT=false
MANAGER_LIVE_MUTATION=false
MERGE=false
STOP=true
```

## 1. 目的与冻结依据

本任务只补齐最后一段连接：通过 Mac Terminal 连接当下可用的 T1 IP，从 **正在使用的 Manager** 读取真实、最新、严格只读的 pending 事实；Mac 本地核对 LCD 光学二维码；人明确确认后，把完整二维码 **恰好一次**交给现有 Manager CLI / Unix socket。不是重新开发一个 SSH 身份检查程序、远程 Python 命令平台、配对协议或新的常驻服务。现场 IP 变化仅更新操作者本次连接目标，不额外绑定历史 IP 或新增 SSH 主机公钥钉死规则；系统原生 SSH 行为和授权规则不在此任务中关闭或替换。

权威源码：PR #534 exact HEAD b60d05a1610ed10e14b859fa64dd760eeb7c2bb7；上一轮独立复核 https://github.com/chrenguo-stack/HomeAssistant/pull/534#issuecomment-6073296534 。原 R3 `bridge_handoff.py` blob e277949c3db5675bd460124832a382d6a2765539，`validator.py` blob 3b7dc0d085dcda52fda0334840d75d5f8678bc1b，Manager `registration_cli.py` blob 690a1a153d9ce747241442ff1341ad46fe7fc354，`n3w_pairing_cli.py` blob 1dc70189873f4d33f3de1e5bb6524c434d73b5ef，`n3w_pairing_local_ipc.py` blob ca709cbe7d86b70055f88800de2b4d6751fd95ff。PR #534 已将旧 `host_readonly.py`/`remote_projection.py` 等通用 SSH Python 派发源从修补分支删除；不得复活。PR #529/#531/#532 及早期设计 #528/#530 已关闭未合并，不是实施来源。

**本设计不代表现场已部署。** P3 板四区写入和回读历史通过；干净板尚未发生正常产品首次启动。历史 T1 只读预检许可已经使用，不得直接复用；本门不安排 SSH、写板、导入、重启或合并。

## 2. 实际源码核对：什么能直接用，什么不能

| 已有组件 | 源码事实 | 本次决定 |
|---|---|---|
| `greenhouse-manager-pairing import-payload --payload-stdin` | 现有 CLI 接收完整一行 GHN3W2，经 `import_setup_secret_over_socket` 走 Manager-owned pairing.sock；命令参数无需放原始秘密 | **保留原样**，无新协议/导入端口 |
| `SimplifiedPairingCoordinator.import_setup_secret`（PR #534） | 取得 coordinator 锁后在 Registry 锁下检查 pairing_id、PENDING 和 `now < expires_at`，真实 IPC 走 Manager 本机时钟 | **保留**，不在客户端自造 TTL 权威 |
| `bridge_handoff.parse_qr/capture_private_qr/bind_qr` | 支持本地无回显私有 TTY、规范二维码校验、二维码哈希与投影比对 | **复用**，但旧 `OneShotImporter` 和 `ssh_manager_stdin_transport` 永远 reject，不能冒充已有执行器 |
| `validator.verify_sqlite_pairing` | 严格数据库只读验证、旧五身份 + 新一身份，涉及 registration/credential/replay；`runtime_authority_pass` 是外部布尔输入 | 用作语义/模拟对照，**不能把布尔真值当作实时 T1 取证** |
| `greenhouse-manager-registration list/events` | `registration_cli.main()` 经 `RegistrationRegistry(database)`，其构造连接是读写，并调用 `_initialize()` | **不合格**：不能将现有 `list` 标成纯只读现场入口 |
| `greenhouse-manager-n3w-setup-secret-delivery-gate pretransfer` | `_pending_session` 已用 SQLite `mode=ro` + `PRAGMA query_only=ON` 读取单个 pending/TTL | 可**复用无副作用检查思路**，但现有 CLI 的 `--expected-hardware-id` 把原始硬件 ID 放 argv，且不能一次证明五旧 + 一新 + credential/history；不直接作为现场终端入口 |
| Manager-owned Unix socket | 产品接口已有 `gh.pair.setup-secret-import/1`，入站秘密不通过公开文件或 CLI 参数传递 | 保留 socket/处理线程/权限/协议，不写数据库捷径 |

注意：现有 `registration list` 不是纯只读；新查询必须在 `RegistrationRegistry()` 实例化**之前**分流，不能因为返回 JSON 没有写入字段就认定没有副作用。

## 3. 选定方案：扩展现有注册管理 CLI 一条固定只读查询

新增一个 **固定用途** 的 `greenhouse-manager-registration p4-pending-readonly` 子命令，优先只改现有 `host/greenhouse-manager/src/greenhouse_manager/ops/registration_cli.py` 及一个小的独立只读函数/测试；如文件分层需要，可放在现有 ops 内的纯只读函数，不创建新的可长期运行服务、Mac 安全启动器或通用远程命令执行器。`main()` 必须在构造 `RegistrationRegistry` 之前进入此分支；只使用 SQLite URI `mode=ro`、`PRAGMA query_only=ON`，无 create/migrate/initialize、PRAGMA 写入、事务修改、备份覆盖。实际 Manager 所用 registration、credential、replay 三个库的**当前路径及挂载**必须经下一源码门证据验证，不能假定路径和权限可用；不能偷偷把所有数据库复制到 Mac 后再检查。

查询只输出无秘密的版本化 JSON，建议 `schema=n3w.p4.terminal-pending-readonly/1`，字段限定 `read_at`（UTC）、`historical_count=5`、`historical_hardware_hashes`（排序后的旧五 SHA256）、`new_count=1`、`hardware_sha256`、`pairing_sha256`、`expires_at`、`pending_state`、`first_registration_no_history`、`credential_history_clear`、`replay_linkage_clear`、`read_only=true`。数值、格式与键集合固定；不输出真实 hardware_id、原始 pairing_id、Setup Secret、socket 内容或私有 IP。若现场只允许较窄的数据库访问权限，**必须明确 FAIL/STOP，而不是从缺失数据推断历史为空**。

读数验证规则：注册、pairing_sessions、events、registration_node_history、node_id_leases、retirement_outbox、credential_assignments 等原 R3 范围内来源必须完整、无歧义；Manager 当前五个历史身份与 Mac 私有原始快照精确一致；恰好一条真实新 pending，首次 hello、epoch 兼容字段、未绑定 node_id，二维码硬件/配对 ID 哈希恰好匹配；不接受已经批准、已退役或有凭据/节点历史的记录。replay 表的主键是 NODE_ID，不是 hardware_id：只能在已知唯一对应关系下排除相关 replay，不能仅凭查不到硬件 ID 声称 replay 为空。存在无法证明的交叉库关联则 STOP。

多数据库分步读取不是单一原子快照；在同一最短只读窗口读取两遍关键身份/pending/expiry 及状态指纹，不一致 STOP。最后 Manager 导入仍以 PR #534 的 Manager 锁内 pending/expiry 判断作为最终权威，不把 Mac 先前读到的旧状态当作不可变事实。数据库正在使用的 WAL/共享权限/只读打开兼容性需要模拟与后续现场只读门证明。

从 Mac 通过已有 SSH 连接当次 T1；只有在需要时使用当次选定 Manager 容器内**固定 CLI 子命令**，不通过 SSH stdin 发送任意 Python 程序文本。Mac 本地将 JSON 投影转为原 `bridge_handoff.bind_qr` 所需的字段或一次性最小结构适配；若旧函数通过可以自报的 `live_attested` 三个布尔字段产生真值，不得伪造这三项。下一源码门应将“读数来自本次受控只读 CLI + 读取时间”与 `bind_qr` 的数据语义分清楚，改为明确的本地绑定成功状态，而不是手填 `runtime_authority_pass=True`。只校验必要 P4 身份/生命周期，不复活被用户取消的固定 TLS/静态 T1 IP 条件。

## 4. 现场唯一操作顺序（未来另行授权；本门不执行）

**G0 — 首次启动前**。预先完成版本、模拟测试、Mac Terminal 私有证据目录和 QR 扫描通道准备；由操作者使用当前 T1 IP 和原有 SSH 方式选择唯一 Manager 实例，核对旧五身份/无新 pending 的只读基线与实际配置的 pending TTL。历史 P4 preboot 证据不等于新授权。产品正常开机许可和稍后的敏感导入许可必须分别明确取得，不能在短暂 pending 窗口内回聊天等待。STOP_0：没有新许可不启动板。

**G1 — 产品第一次正常启动后**。真实产品向当前 Manager 发送 HELLO，Manager 生成唯一 pending，设备 LCD 第五页展示 GHN3W2。使用 Mac 原有无回显私有终端/扫码器读完整二维码到进程内存，不写 shell history、argv、环境变量、终端转录或文件；Mac 本地解析后只保留本次比对所需的哈希并限制秘密在内存中的存活范围。

**G2 — 绑定**。Mac 通过一次固定只读 CLI 查询当时的 Manager，核对原有五个身份 + 唯一新 pending、状态及历史、设备和配对两项哈希。先用真实 `expires_at` 计算余量，默认首轮预留至少 60 秒、读数距确认不超过 10 秒；这两项是现场准备策略，不等于配置上的 TTL 恒为 120 秒。任何二维码错配、身份漂移、多 pending、数据库访问不完整、过期或时钟异常立即 STOP，零秘密发送。STOP_1：显示无秘密摘要，等待现场操作者明确确认。

**G3 — 恰好一次提交**。G0 阶段先预授权本次敏感操作（尚不知道真实运行时二维码身份时不得预填硬件/配对号）；G2 绑定后把授权绑定本次观察到的 hardware_hash + pairing_hash + Manager pending 会话和期限。现场操作者在当前 Mac Terminal 明确确认一次，不接受可伪造的 `operator_continue=True` 函数参数当作授权。最终发送前再读**新鲜的只读 pending 状态**，若不满足最低剩余 TTL/当前 pairing 变化则 STOP。随后使用本次私有证据目录内极小的 owner-only `0600` 一次性已消费标记：仅存 attempt_id、两项身份哈希、时刻和 `CLAIMED`，以独占创建和 fsync 在真正发送之前持久化；不存秘密，也不引入新的服务或通用票据系统。标记存在则终止，客户端崩溃/SSH 断线/无响应不能自动再提交。该本地标记只控制本次 Mac 工作流，不宣称阻止另一台未经授权的 Mac 或外部调用者直接调用 Manager CLI。

真正的发送只允许 **SSH 的标准输入 → 当前 Manager 容器内 `greenhouse-manager-pairing import-payload --payload-stdin` → Manager-owned pairing.sock**；通过固定的 subprocess 参数数组执行，不经 `shell=True`、`sh -c` 的插值，不把二维码放入进程参数、环境变量、日志或 CI；不让任何通用 SSH 命令运行二维码内容。不要临时生成一个第二套秘密转发协议；命令执行成功与否必须按现有 `gh.pair.setup-secret-import-result/1` 的 `accepted`/`code` 分类。

**G4 — 结果确认与停止**。返回 `accepted=true` 只记为 `IMPORT_ACCEPTED`，后续还需独立只读验证真实产品完成 PoP、凭据包持久化最终回执、Manager COMMIT，才可记 P4 成功。明确拒绝或任何未知状态（SSH 已投递不明、CLI/IPC 超时、stdout 不完整、连接中断、进程被杀、重启）都不得自动重发；标记保持已消费，STOP，单独走获批的事故判定/恢复门。不要通过清库、重建历史、重置 Manager 或设备来恢复测试窗口。

**关于时间**：导入时的最终有效性由 PR #534 Manager 内 Registry 锁检查 `PENDING`、精确 pairing_id、`now < expires_at`，Mac 端新鲜查询只帮助减少无意义操作。若不证明 Manager 已安装包含该修补的**实际版本**，即使本地脚本模拟成功也不允许真实导入。120 秒是注册表代码默认值，必须先读取运行时配置；现场不能为了赶时间跳过人工 STOP。

## 5. 下一源码门的明确最小范围

| 部位 | 必做范围 | 禁止范围 |
|---|---|---|
| `registration_cli.py` + 必要只读查询函数 | 仅新增 `p4-pending-readonly` 固定分支，必须在 Registry 读写初始化之前；只读多数据库，固定 JSON 输出，零秘密 | 不加新的远程命令执行器、不写 Manager DB、不新增常驻服务 |
| 原 R3 `bridge_handoff.py` 与测试 | 复用 QR 格式、无回显光学输入、pending↔QR 比对；小型适配到新查询结构；旧禁用导入类保留为禁用或经依赖审查明确删除 | 不把 Boolean 自报当真实身份来源，不让绑定本身自动导入 |
| Mac Terminal 运行指引 / 必要的局部最小适配 | 现场选当前 IP，预授权、无回显 QR、一次确认、最小持久已消费标记、秘密只走 STDIN；模拟断线不重试 | 不新造 frozen IP / host key 清单、Mac 独立安全启动器、通用 SSH 动态代码文本 |
| 原有 Manager pairing CLI/UDS | **原则上零修改**，只连接现有 `import-payload --payload-stdin` | 不新建 Setup Secret 接口，不修改 MQTT/N3W key 生命周期 |
| Registry/Coordinator | PR #534 锁内 pending-at-use TTL 审核结果继续复用；必须证明现场 Manager 运行的是该代码 | 不重复实现另一套导入 TTL 状态机 |

如查询需要读取未被现有 Manager 镜像/挂载暴露的数据库，首先用 host-only 和合成证据解释缺口，再申请最窄补充；不得为闭环临时复制真实 SQLite 到 Mac、访问未经授权 T1 或执行读写 CLI。下一源码门结束后仍须独立审核，不自动执行真实 P4。

## 6. 下一源码门合成测试清单

1. `registration list` 原路径可能触发 `_initialize`，新增 `p4-pending-readonly` **绝不能创建/更改 SQLite 或 WAL 内容**；用只读文件、哈希/mtime、spy 和 SQLite URI 检验。
2. 正常五旧 + 一新 pending、合法 LCD 合成 QR、仅哈希 JSON、不输出原始硬件 ID/配对 ID/Secret；Manager TTL 由实际 expires_at 而非本地计时猜测。
3. 五旧身份变动、4/6 个旧身份、多一个新身份、多 pending、孤立事件、已有 NODE_ID/lease/凭据/退役记录、replay 关联不明、SQLite schema/version/path 漂移：全部拒绝。
4. 双库三库快照之间发生状态变化、Manager 临时重启/不同容器、私有历史快照格式错误、读数超过 10 秒：全部 STOP；不得把自报布尔真值当活证据。
5. 旧 IP 更换为另一个合成当前 IP 后，正常 SSH 操作设计不依赖固定旧 IP 哈希；**不测试绕开或关闭既有 SSH 服务器身份验证**。
6. 本地二维码失败、不回显、输入过长、重复扫码和扫码器输出换行；不得写 shell history/env/argv/log/GitHub，不能用字符串原文充当公开模拟结果。
7. 一次人工确认前零导入；已取消/未确认零导入；同一尝试第一次 claim 后不可第二次发送；两进程抢 claim 仅一人获胜；崩溃在 claim 后和发送后未知结果都 STOP。
8. 通过伪造 stdout、socket accepted、Manager 当前状态改变、TTL=0/59/60、未知 ACK、CLI 超时、SSH 退出码非零、stderr 异常，证明无自动重试、无假 COMMIT。
9. 现有 Manager socket 管道端到端合成成功与明确拒绝；最新 PR #534 的 1250 Manager、46 R3 用例保持通过，新只读分支与新适配所有 synthetic PASS。
10. 现有 Wi-Fi Direct/ESP-NOW、Broker、KF-050、Manager repair/credential lifecycle、P3 冻结固件 artifact 均无无关改动。

## 7. 工程 STOP 与验收结论

```text
DESIGN_DECISION=EXISTING_MANAGER_REGISTRATION_CLI_READONLY_SUBCOMMAND_PLUS_R3_BINDER
STATIC_T1_IP_AS_TRUST_SOURCE=REJECTED
ADDED_SSH_HOSTKEY_PINNING=REJECTED
ARBITRARY_REMOTE_PYTHON=REJECTED
EXISTING_CLI_IMPORT_PAYLOAD_STDIN=RETAINED
CURRENT_REGISTRATION_CLI_LIST_IS_STRICT_READONLY=false
NEW_PENDING_READONLY_SUBCOMMAND=NOT_IMPLEMENTED
QR_MANAGER_PENDING_WIRING=NOT_IMPLEMENTED
ONESHOT_ATTEMPT_CLAIM=NOT_IMPLEMENTED
MANAGER_TTL_AT_USE=PR534_SOURCE_ONLY
REAL_P4_FIELD_READY=false
CI_FOR_NEXT_SOURCE_GATE=REQUIRED
INDEPENDENT_SOURCE_REVIEW_AFTER_IMPLEMENTATION=REQUIRED
NEXT_ONE_GATE=N3W_PR522_P4_R3_TERMINAL_QR_PENDING_BINDER_AND_ONESHOT_STDIN_IMPORT_SOURCE_REPAIR_AND_SYNTHETIC_20261009_01
NEXT_GATE_SCOPE=SOURCE_AND_SYNTHETIC_ONLY
NEXT_GATE_BASE=THIS_DESIGN_PR_EXACT_HEAD
NEXT_GATE_MUST_FIRST=CONFIRM_REAL_MANAGER_DB_MOUNTS_AND_READONLY_CLI_DEPENDENCIES_FROM_REPO
NEXT_GATE_EXCLUDES=LIVE_T1;BOARD;REAL_QR;REAL_SECRET;MANAGER_DEPLOY;MERGE
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
```

此文档是下一源码门的实施范围，不是运行命令包或现场授权。