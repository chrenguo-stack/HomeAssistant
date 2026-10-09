# N3-W P4 私有现场执行器、Pending TTL 与一次性人工授权：实施设计（2026-10-09）

## 0. 设计门与约束

TASK=N3W_PR522_P4_PRIVATE_FIELD_ORCHESTRATOR_AND_PENDING_TTL_AUTHORIZATION_DESIGN_20261009_01
DESIGN_RESULT=PREPARED_DESIGN_ONLY
SOURCE_OR_T1_MUTATION=false
BOARD_ACCESS=false
SECRET_IMPORT=false
P4_FIRST_BOOT=false
MERGE=false
STOP=true

仓库：chrenguo-stack/HomeAssistant。
设计时主分支：d423211b6196c2f2f0f01dff072c4f877fbe58ee。
PR #522 冻结源码：58107b36fc20ccbef014d13cbfb708186395441c；OPEN/DRAFT/unmerged。
PR #529 R4 只读源码：4306fbd39e4ecc9ab27329712d989eca0c90816a；OPEN/DRAFT/unmerged。
PR #528 R4 文档：ab6e18aeeb40f25da4e9d0c08eff5d9e21bc836b；OPEN/DRAFT/unmerged。
PR #474、#527 仍然 OPEN/DRAFT/unmerged。
R4 独立源码审查： https://github.com/chrenguo-stack/HomeAssistant/pull/529#issuecomment-6072471821 。
R4 模拟 CI：74/74 PASS，完整 PR-head CI 12/12 PASS；这些不能作为现场授权。

历史 P3 四区写入及回读是 CLOSED_PASS，当前干净板仍未发生产品正常启动；历史 P4 首次启动前 T1 只读预检是 CLOSED_PASS、授权已消耗，不得当作新一次 SSH 的授权。历史五身份私有快照精确 SHA256：
81a4601421d0f85a6295a8d901fa91692e61c27306c36bc673796f856bbd1e0c。
产品精确构建源：629f096a32e087087ea32d30707dcc3cd6295e5d；artifact 11469977052；release ZIP SHA256 55155717f7d8cbe1eb7cd856d42ffd2ac937b364fbbd80d52f1d37b47a46856c。硅片只负责 P3 物理板绑定，不能替代产品运行时 hardware_id。

## 1. 必须分别使用的三个工具

| 阶段 | 允许读取什么 | 正确身份数 | 禁止什么 |
| --- | --- | --- | --- |
| H1，Mac 本地静态预检 | 固定源码、私有快照、目标主机和 SSH 密钥的本地证据 | 历史快照恰好 5 个 | 任何 SSH、联网写入、实板启动 |
| H2，新授权的 T1 首次启动前只读预检 | 同一 T1 的 Manager/Broker、TLS、pairing.sock、SQLite 只读 | 当前身份仍恰好 5 个，新 pending 必须为 0 | hello、secret import、数据库写入或重启 |
| P4-C，首次产品启动并产生 hello 后 | 同一 Manager 上新 pending 加五历史身份，真实 LCD 光学 QR | 历史 5 + 唯一新身份 1 | 未绑定 QR 直接导入 |

重要：PR #529 的 host_readonly.remote_snapshot_once 实际是“产生新 pending 之后”的身份投影工具，要求 new_count=1。严禁在 H2 阶段调用它来伪装五身份 preboot PASS。H2 要实现独立的、仅期望五身份、无配对或秘密入口的最小只读探针，接受独立审查。

## 2. Mac 现场执行器的最小边界

推荐只做一个按阶段路由的薄执行器，而不是再建立通用远程命令执行框架。三条可单独运行的固定入口：preflight-local（无 SSH）、preflight-host-readonly（新授权只读 SSH）、bind-and-import-once（以后单独授权，可能涉及 Manager 变更）。权限最小化，默认只读且无法隐式升级到 import。

在第一次对 T1 发出命令之前：
1. Mac 本地先核对仓库与 PR 的 exact HEAD、Git blob SHA256/Git blob SHA、模块导入路径与每一层执行器代码。不能仅检查 bridge_handoff.py 和 remote_projection.py；还必须验证实际运行的 host_readonly.py、validator.py、Mac launcher、后续专用预检及导入入口。不从可随意更改的当前工作树暗中导入 Python 模块。提交漂移、字节漂移、路径变化、未知依赖均 STOP。
2. 验证 Python 版本及必要的只读程序源可解析、AST 和命令白名单检查；静态禁止动态执行、SQLite 写操作、shell=True 和任意 SSH 代码串。最终发送给 SSH 的程序字节需绑定构建结果。上游 R4 pin 要以 PR #529 exact HEAD 为准，而非错误地宣称 main 已含修补。
3. 验证原有五身份私有快照：路径及其上级不得为符号链接；文件必须是当前操作者所有、0600、普通文件，SHA256 与冻结值相同，schema 精确、五个去重排序哈希一致。读取方式防止检查后文件被替换（可使用 fd/fstat/单次已验证读取）；不在 GitHub/chat 打印原始文件或私有路径。
4. 从预先单独批准的私有现场记录读取 T1-A 目标与主机公钥指纹；两份信息与 R4 固定投影源码内的目标哈希必须一致。使用已存在、固定且本地可信的 known_hosts 和严格主机密钥验证，不允许 StrictHostKeyChecking=no、自动接受新密钥或静默更新 known_hosts。实际 Mac 用户、SSH 配置、跳板或 ProxyCommand 如果不符合预设，则 STOP 并单独审查，不自动“修通”。不把 Mac 私人 T1 地址、SSH 用户凭据或密钥路径写进公开设计文档。
5. 设置本地私有证据目录，限制 owner 权限；只允许哈希、结果代码、事件顺序、耗时和幂等状态进入后续公共归档。关闭 shell tracing、PTY/回显、调试日志、core dump 与原始 stdin/stderr 记录；必要的私有证据也不能混入 GitHub Actions。
6. 在此阶段确定真实 LCD 第五页 QR 的光学读取方式与 T1 导入通道，完成全部模拟验证；正式首次启动之后不临时安装程序、不下载脚本、不启动 CI、不要求重新讨论方案。

任何一项本地校验缺失时：
H1_RESULT=STOP_BEFORE_SSH
BOARD_BOOT_ALLOWED=false

## 3. H2 独立授权、只读实时预检

旧 P4 preboot 的 PASS 是历史证据，不能复用当时已用完的授权。未来 H2 必须单独得到“仅一次、仅同一 T1、仅允许固定只读程序、指定截止时间”的授权，再执行。

H2 读取并重新核对：
- T1 目标、可信 SSH 主机身份、Manager 与 Broker 固定容器 ID、StartedAt、restart_count=0；
- Manager host-network、空 ports、Broker 8883 IPv4/TLS CA/leaf/hostname/SNI、auto 地址模式和有效 pending TTL=120s；
- Manager-owned pairing.sock 路径、socket 类型/0600/安全父目录及 CLI 存在性，仅查看不执行 import；
- 按现行 Docker mount 查找注册、凭据、replay SQLite，拒绝 mount 漂移和路径符号链接；只用 mode=ro 与 PRAGMA query_only=ON，检查 schema 和原有五个身份两次一致、没有新 pending；
- 确定是否已经有另一个首次配对进程或待处理交易，存在则 STOP，不允许“清空后继续”。

H2 完毕后提供精简安全标志，不显示任何私有主机地址或身份原文。当前容器或 T1 身份改变时，旧 H2 证据作废，需要一个新的独立现场评估；不得自动修复、重启 Manager/Broker、重放老 H2 执行票据。

H2_RESULT=PASS 仅证明当前“首次启动前同一 T1 的只读状态”，不代表以后导入授权、R4 post-hello 绑定或产品 P4 全流程通过。

## 4. 首次启动前必须锁定一次配对尝试和人工授权

采用两阶段、一次性凭据。避免把单个 live_attested=true、operator_continue=true 或 self-supplied SHA 当作授权。

A. 初始准备（尚未产生新 hardware_id/pairing_id）：
- 操作者明确批准这块 P3 完成的干净板、此 T1 目标、此固件构建与这一次 P4 正常首次启动；“板端首次启动许可”与“Manager 可能写入 Setup Secret 的额外许可”必须分别授予、可单独拒绝。
- 在首次启动前独立拿到秘密导入权限的有界预授权，只针对这个唯一尝试 ID、准确源码、T1 和板硅片绑定。不能事前捏造运行时 hardware_id 或 pairing_id；真正交易身份只能随后从光学 QR + Manager pending 绑定。
- Mac 私有 owner-only 持久账本中创建唯一 attempt_id，记录授权来源、时间界限、固件/执行器哈希、T1 指纹、硅片绑定哈希和许可范围；除系统保护的具体操作之外，不可从可伪造的 Python 函数参数自动签发。
- 所有独立授权都必须在首次 hello 之前准备完毕；提交秘密的最后一次人工确认可在 P4-C 结束后以短时、本地、明确动作完成，不应在 120 秒窗口内回到聊天申请许可。

B. 绑定新身份后：
- 真实光学 QR 在本地不回显渠道输入；其完整内容和 Setup Secret 仅在易失内存中短暂持有；不得通过 macOS 命令行参数、终端历史、进程环境变量、完整 shell transcript、GitHub/comment/API 传送。
- 从 QR 解析并核对产品 runtime hardware_id 与 pairing_id 的哈希，以及当前 Manager 唯一 pending 记录。将 attempt_id 与这些原始身份的哈希、Manager 会话版本和截止时间正式关联；拒绝未知二维码来源、扫描失败、读到多台板、多个 pending 或其他历史身份。
- 在真正发送前显示不含秘密的最小确认信息；人工做一次短时本地“继续”动作。动作必须与同一已绑定 attempt_id 对应，不得复用、远程脚本自行触发或跨会话继承。

C. 消耗语义：
- 实际不可逆发送前，必须原子记录 CLAIMED_FOR_IMPORT 并持久化（例如独占创建、持久账本事务、fsync 文件及目录），只有该独占领取者可以执行一次真实发送。
- 在发送前已失败且可以证明没有真实发送的状态可 STOP_NO_SEND，但不能自动再次提交；若已经 CLAIMED 或网络/IPC 超时导致无法证明是否送达，一律 CONSUMED_UNKNOWN + STOP。客户端进程重启、Mac 关机/崩溃或脚本重跑都不能创建第二次导入。
- 不以删除账本、改 attempt_id、重置装置/Manager、重导入相同 secret 来制造重试。若必须补救，另立新的、审查过的现场事故处理门，不能利用本设计权限。

## 5. 120 秒有效期与最终导入前检查

现有源码证明：
- host/greenhouse-manager/src/greenhouse_manager/ops/n3w_setup_secret_handoff_delivery_gate.py（PR #522 所引用版本的 blob 09270f4c512b83efecd438c9f26394f3e99b64f8）已有 pretransfer 与 predelivery 门；会从 SQLite mode=ro + query_only 中确认同一硬件的当前 pairing_id、pending、expires_at，并要求最小剩余时间。predelivery 还要求含明文 Setup Secret 的私有 handoff 文件及 owner/mode；其 CLI 使用 --expected-hardware-id 参数。
- host/greenhouse-manager/src/greenhouse_manager/ops/n3w_pairing_cli.py（blob 1dc70189873f4d33f3de1e5bb6524c434d73b5ef）的 import-payload --payload-stdin 已存在，内部解析完整 GHN3W2 光学 payload，然后经 Manager-owned pairing.sock 送入；此命令无需在 argv 填写 raw hardware_id / pairing_id / secret。
- host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_simplified_pairing.py（blob eba36d66bb094147dfcb5cfb021fb5f6f3ee02c3）可见 import_setup_secret 检查同一 pairing_id 及 PENDING 状态，但在该函数中没有显式读取 expires_at 并强制 TTL；不能仅以 PENDING 判定 120 秒合同完整成立。是否存在其它调用层 TTL 保障，后续还需逐层核对，不能猜测已具备。
- PR #529 R4 post-hello read-only 投影源码要求最少 60 秒剩余时间且 read_at 不超过 10 秒。

设计收敛：
1. Manager hello 被接受时开始短期配对窗口（现行有效值 120 秒）；从同一 Manager 的 authoritative expires_at 推导剩余时间，不能用“设备通电后过了多少秒”替代。
2. P4-C 的 R4 验证通过、真实 QR 哈希匹配唯一新 pending、无旧 node_id/credential/replay/retirement 关系，才能进入 P4-D；在正式进口前即刻追加 read-only pending+TTL 检查（后者需与 Manager 当前运行版本一致）。
3. 候选策略沿用 R4 的 60 秒最小剩余时间和 10 秒读取新鲜度；实际预算须留出光学 QR 读取、操作者本地确认、最终验证、IPC 超时与产品提交所需时间。不能只依靠首次扫码时的剩余时间；任何时钟漂移、不明时区、超过截止时间或检查后间隔太长都 STOP。
4. 现有 delivery gate 的 CLI 以原始 hardware_id 作命令行参数，**不可原样作为无敏感 argv 的最终现场入口**。其 predelivery 依赖明文 handoff 文件，也不能在“默认仅易失内存”的安全合同下直接套用。优先复用其 _pending_session 等已审核、纯只读的逻辑，设计一个版本固定、仅通过内存/受控 stdin 传递私有身份的安全适配层；若方案必须采用 handoff 临时文件，必须先单独获批受控 tmpfs、owner/mode 及安全删除和残留风险，并更新接受条件。
5. 需要在最终不可逆发送点收敛 time-of-check/time-of-use（读后状态变化）问题：若 Manager 实际导入执行路径没有在其受保护的事务或锁下同时检查同一 pending 与 TTL，则应提出一个最小、独立审核的 Manager 端临界区修补。仅 Mac 前置查询即使在 60 秒内也不能声称已完全关掉竞态。正式生产导入要有清晰的 accepted / unknown / rejected 结果合同。
6. 真正的秘密交付另写独立、单一用途、版本固定的 Mac-to-T1 导入器；只允许完整光学 payload 经标准输入进入 greenhouse-manager-pairing import-payload --payload-stdin，经过原有 Manager-owned pairing.sock。不能把 secret 交给 PR #529 的只读 SSH 投影入口，不能添加 serial/NVS 或 direct SQLite 写入捷径。
7. 导入返回 accepted=true 仅代表该步骤接收/处理成功，不等于 Manager COMMIT，更不等于中断前零 canonical telemetry、重启后两个严格递增数据点。

## 6. P4 实际执行状态机和停止点（未来才可授权）

| 阶段 | 唯一允许动作 | 通过条件与必须停止处 |
| --- | --- | --- |
| G0 准备 | 本地 H1 + 独立授权的 T1 H2；原有 P3 板不通电 | private baseline 5/5、容器连续性、所有工具已安装、导入权限预授权和持久账本 ready；STOP_1 在首次正常启动前 |
| G1 启动 | 单次授权的正常产品首次启动、正常 Wi-Fi 配置 | 真实 Manager hello、新 pending、LCD 第五页 GHN3W2；STOP_2 在 QR 私有采集前，采集通道已经就绪 |
| G2 绑定 | 私密光学读取 QR，R4 source-bound 只读核对当前唯一新 pending | old 5 + new 1、真实 runtime hardware/pairing 匹配，未过期；STOP_3 在任何秘密发送前，操作者就地确认 |
| G3 导入 | 完整最终只读 TTL 检查 + 原子消耗授权 + 一次且仅一次 stdin 导入 | 接收状态分类为 ACCEPTED / REJECTED / UNKNOWN，后两者强制 STOP；不得自动重复 |
| G4 COMMIT | 只读确认当前 Manager 已 COMMIT / 已批准凭据 | 仅在真实 canonical count=0 的极短窗口且有独立物理许可，才允许单次受控断电；否则 INVALID_WINDOW，STOP 不补做 |
| G5 恢复 | 按独立物理方案重启观察 | boot session 合法，至少两个严格递增 canonical 样本；STOP_5；P5/P6 地址迁移另门进行 |

最终产品首次配对结束与后续地址 A->B 迁移是不同验收对象。P4-G4 的断电窗口不可靠时，不能为了通过测试去清除身份/重置历史；必要时把中断试验明确标为 NOT_PERFORMED/INVALID_WINDOW 并单独规划新的合法干净样机试验。

## 7. 必要模拟测试与复核矩阵

所有测试必须只使用模拟 T1、虚拟二维码、假身份和假秘密，不运行真实 SSH / Manager/板。

| ID | 模拟场景 | 期待结果 |
| --- | --- | --- |
| F01 | 本地 launcher / host_readonly / validator / 投影任一 SHA、import path 发生漂移 | 在 SSH 和秘密加载前 STOP |
| F02 | 私有快照被替换、符号链接、错误 owner/mode 或 4/6 个历史身份 | STOP，拒绝 H1 |
| F03 | Mac 原有 SSH host-key 不匹配或 unknown、目标地址哈希与 T1-A 不匹配 | STOP，禁止自动修复 known_hosts |
| F04 | 在 H2 误调用要求 new_count=1 的 R4 post-hello binder | 明确 PHASE_MISMATCH，STOP |
| F05 | 首次启动前读到第六个身份或现有 pending | H2 失败，不能擅自清理 |
| F06 | 改写 boolean 操作确认或伪造自报 grant | 不构成可用授权，零 secret 发送 |
| F07 | 初始授权已准备但没有真实 QR + 唯一 Manager pending | 无法绑定 attempt，STOP |
| F08 | 不同真实新 hardware/pairing/boot 或同一 QR 的第二个任务请求 | 授权不匹配 / 无法重复领取 |
| F09 | R4 读取超过 10s、剩余 TTL 少于 60s、时钟不可信或到期 | STOP，0 次发送 |
| F10 | 从 R4 readback 到 import 之间 pending 被撤销/换成另一配对 ID | 最终再检查或 Manager 原子条件拒绝 |
| F11 | 旧 gate CLI 把 raw hardware_id 放进 argv，或需要落盘 plaintext secret | 作为字段导入路径不合格，拒绝选用 |
| F12 | 本地确认未做、超期、来源不符或重复尝试 | STOP，不能靠布尔值旁路 |
| F13 | ledger CLAIM 后 Python 崩溃、Mac 断电、IPC 超时或 ACK 丢失 | 消耗账本保留，UNKNOWN，零自动重发 |
| F14 | 同一 attempt 的两个并发子进程领取 | 仅一个可能 CLAIM，至多一次发送 |
| F15 | 旧 R3 import_once 或 ssh_manager_stdin_transport 被调用 | 仍然全拒绝 |
| F16 | Manager importer 只检查 PENDING、不检查 expires_at 的模拟场景 | 视为仍有 TTL 原子边界缺口，不可批准真实进口 |
| F17 | import accepted=true 但 Manager 尚未 COMMIT | 只能 IMPORT_ACCEPTED，不得判定 P4 PASS |
| F18 | COMMIT 后第一条 canonical 已被接受 | 中断测试 INVALID_WINDOW，禁止抹掉历史重试 |
| F19 | 任何私有值进入日志/argv/GitHub/artifact/异常追踪 | 严格失败；不得提交该证据 |
| F20 | R4 原有 74 案与其它已冻结 source contract | 全部保留为回归基线，新增 CI 须另给 exact HEAD |

## 8. 最短可执行开发路线（不是现场授权）

阶段 R5a：实现 Mac H1 本地 source/validator/SSH 身份检查及独立 H2 五身份只读探针、无秘密一键 mock 测试。单独的 source repair 分支基于 exact PR #529 HEAD；必须受 frozen-blob 检查。先通过 synthetic CI 与独立源码复核，STOP；不实际 SSH。

阶段 R5b：实现真实光学 QR 私有输入适配、pregrant/ledger/claim 消耗、Manager at-use TTL 原子合同、单用途秘密 stdin importer 的模拟接线。尽可能复用已有 Manager pairing CLI/IPC 与 delivery gate 检查逻辑；只有证明 Manager 现有进口路径不具备锁内 TTL 检查时才申请最小 Manager 代码修补。模拟并发/断线/超时/进程重启，必须先独立复核，STOP。

阶段 R5c：新授权的 Mac-local no-SSH 预检，随后另行授权的 host-only read-only T1 实时兼容性测试；禁止复用旧 P4 preboot 执行票据，完成后 STOP。实测前仍不能批准板启动。

阶段 P4 实板：另立明确 P4 first-normal-boot 和 Setup Secret import 双授权，确保 R5c、光学输入、独立许可、现场操作者、全部 STOP 状态都 READY，才能进入上面的 G1-G5。不能把执行器准备完成等价成许可。

尽量少改动现有 Manager/固件；开发测试优先不改变 P3 已冻结的板端 artifact。若确需 Manager 改动，必须单列变更、CI 和部署/回退授权，不能悄悄替换现行 T1 服务。

## 9. 本门设计结论与下一唯一任务

DESIGN_REVIEW_SCOPE=FIELD_ORCHESTRATOR_PENDING_TTL_AND_OPERATOR_AUTHORIZATION
DESIGN_RESULT=PASS_DESIGN_ONLY
R4_SOURCE_REVIEW=PASS_SOURCE_BOUNDARY_ONLY
A4_ACTUAL_T1_COMPATIBILITY=OPEN
A5_AT_USE_PENDING_TTL_AND_RACE=OPEN
A6_DURABLE_ONESHOT_IMPORT_AND_HUMAN_APPROVAL=OPEN
MAC_FIELD_ORCHESTRATOR_IMPLEMENTED=false
MAC_FIELD_ORCHESTRATOR_REAL_READINESS=false
H2_NEW_LIVE_AUTHORIZATION_GRANTED=false
P4_FIRST_NORMAL_BOOT_AUTHORIZED=false
P4_REAL_SETUP_SECRET_IMPORT_AUTHORIZED=false
T1_ACCESS=false
BOARD_ACCESS=false
SECRET_IMPORT=false
PR_MERGE=false

NEXT_ONE_GATE=N3W_PR522_P4_PRIVATE_FIELD_ORCHESTRATOR_R5A_MAC_SOURCE_AND_PREBOOT_READONLY_SOURCE_REPAIR_AND_SYNTHETIC_REGRESSION_20261009_01
NEXT_GATE_CLASS=NONLIVE_SOURCE_ONLY
NEXT_GATE_BASE=4306fbd39e4ecc9ab27329712d989eca0c90816a
NEXT_GATE_LIMIT=H1_MAC_STATIC_AND_H2_FIVE_IDENTITY_READONLY_ONLY
NEXT_GATE_EXCLUDES=LIVE_T1_SSH;P4_BOOT;REAL_QR;SETUP_SECRET_IMPORT;MANAGER_MUTATION;MERGE
NEXT_GATE_STOP=AFTER_EXACT_SOURCE_CI_AND_INDEPENDENT_REVIEW_HANDOFF
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
