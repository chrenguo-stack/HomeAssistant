# N3-W T1 R2C target-Armbian 只读取证准备 — 2026-10-13

## 1. 本轮结论与版本绑定

```text
TASK=N3W_T1_GOLDEN_MASTER_R2C_TARGET_ARMBIAN_SEAL_ADAPTER_READONLY_EVIDENCE_PREPARATION_20261013_01
DELIVERABLE=DOCUMENTED_EVIDENCE_SCHEMA_AND_EXECUTION_CONTRACT
PREPARATION_GATE_RESULT=PASS
EXECUTABLE_PACKAGE_IMPLEMENTED=false
EXECUTION_READY=false
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
CANDIDATE_REF=plan/n3w-t1-full-fresh-install-from-zero-20261010
PREPARATION_BASE=1006cc07694f3da7cc232907bb4f7f6354cea5cf
REVIEWED_R2A_R2B_SOURCE_HEAD=51ea220ac5510f4a55f0166bbab7f1cec5bed407
CLOSURE_HEAD=e946d1cb60a4256c66553ee382e061ae3c031a83
SOURCE_TEST_WORKFLOW_DRIFT=false
PR541_STATE=OPEN_DRAFT
PREPARATION_BASE_CI=27/27_PASS
R2A_SOURCE_REPAIR=CLOSED_SOURCE
R2B_HOST_INDEPENDENT_SOURCE_REPAIR=CLOSED_SOURCE
A1_A10=CLOSED_SOURCE
R2C_TARGET_ARMBIAN_SEAL_ADAPTER=NOT_ENTERED
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
```

GitHub compare 证明 reviewed source → preparation base 共前进两次提交，仅六个
`docs/development/` 文件变化；源码、测试、工作流未变化。main 与交接一致。
本轮只提交文档合同，不新增执行器、不修改已关闭的 R2A/R2B 或 P2B 工具。
文档准备通过不等于可执行包已通过测试，更不等于目标机取证通过。

读取依据：当前 working context、current state/index、KNOWN_FAILURES 中 KF-113，
R2 build/final-seal source design 第 6 节、P2B execution closure、ADR-0009。
历史 P2B 证明的是当时当前主机状态；本轮无 fresh live baseline。

## 2. 完成条件与三层证据

九类要求各自必须有字段、限定读取方法、公开表示和停止规则。
本合同将结果分成三层，不能相互替代：

1. `CAPTURE_COMPLETE`：目标版本、文件、配置与依赖材料采集完整。
2. `STATIC_MECHANISM_REVIEW`：能从目标机实际安装内容说明条件、读取来源、生成者和先后关系；不能仅有文件摘要。
3. `CONTROLLED_CLONE_BOOT`：清除身份后的真实启动、两台克隆差异及重启稳定性，另行受控验收。

即使前两层通过，仍保持：

```text
OS_IDENTITY_SEMANTICS_PROVEN=false
CONTROLLED_CLONE_BOOT_EVIDENCE_REQUIRED=true
R4_CLONE_UNIQUENESS_ACCEPTANCE_REQUIRED=true
REAL_SEAL_MUTATION_EXECUTABLE=false
DISK_CAPTURE_READY=false
```

## 3. 九类字段及只读采集矩阵

以下是未来执行器的规范，不是本轮已经执行的命令。方法编号定义在第 4 节。
所有类别都记录 provenance、完整性、状态和 reason；权限不足、截断或不认识的行为均不能填为不存在。

| ID | 必须回答的问题与精确字段 | 限定采集方法 / 对象 | 可公开表示 | 不满足时 |
| --- | --- | --- | --- | --- |
| E1 | `os_release`、`armbian_release`、`architecture`、`systemd_version`、`package_versions`、`executable_binding` | C1、C2；R1 读取 `/etc/os-release`、`/etc/armbian-release` 的允许键；C3 查询 systemd/openssh-server/network-manager/netplan.io/对应 Armbian 文件 owner | OS/板型/架构/软件版本、程序摘要；禁止 hostname | 不是预期 Armbian 26.05.0 / arm64 / S912-Phicomm-T1 则 STOP_TARGET_DRIFT；缺命令不安装 |
| E2 | `firstrun_body_complete`、`body_sha256`、`identity_control_flow`、`helper_dependencies`、`conditions`、`writes_declared_by_source` | R1 完整读取 `/usr/lib/armbian/armbian-firstrun` 的源码作为数据，绝不运行；C3 绑定包；R1 读取静态引用的 identity helpers，按预算封闭依赖 | 程序摘要、非敏感行号及人工审阅的控制流结论；源码原文不自动公开 | 动态 eval/source、外部下载或无法解析的 helper 影响身份语义时 STOP_UNRESOLVED_IMPLEMENTATION |
| E3 | `firstrun_config_present`、`setting_names`、`identity_setting_classes`、`config_parse_complete`、`source_references` | R2 解析 `/etc/default/armbian-firstrun`；只采 E2 明确读取并影响 hostname/machine-id/SSH/network/first-run 开关的键；只按数据解析，不 source shell | 键名与 boolean/default/custom/absent 分类；具体 hostname、网络值和密码不输出 | 未知赋值、命令替换或无法确定生效值时 STOP_CONFIG_UNRESOLVED；不能以缺配置推断默认安全 |
| E4 | `etc_machine_id`、`dbus_machine_id`、`path_relation`、`mount_relation`、`contents_equal`、`boot_condition_contract`、`fallback_sources` | R1 元数据及受限内存比较两个路径；C5 判断 `/etc/machine-id` 是否 mountpoint；C4、C3 读取 machine-id commit / firstboot 实际 unit、drop-ins、目标版本已安装手册/包内说明 | regular/symlink/missing/empty/uninitialized/valid/invalid；同 inode、同内容、挂载关系及机制来源 | populated 仅记录当前状态；没有 missing/empty/uninitialized 区别和 D-Bus fallback 证据则 STOP_SEMANTICS_GAP，禁止试改来验证 |
| E5 | `ssh_key_metadata`、`key_families`、`keygen_conditions`、`ssh_units`、`hostkey_path_classes`、`package_helpers`、`socket_activation` | R1 仅 stat 私钥；公钥只在内存比较/摘要，不输出原值；R2 读取 sshd_config 及 Include 的 HostKey/HostCertificate/Include 条目；C4 读取 ssh.service/sshd.service/ssh.socket/sshd-keygen.service 及具体 helpers | key family、权限、存在性、生成者/条件/依赖；路径以 approved/custom 分类 | 私钥路径自定义、helper 未封闭、socket 提前开放或关系不明确均 STOP；不得执行 ssh-keygen 或 keygen service |
| E6 | `nm_state_inventory`、`profile_inventory`、`netplan_inventory`、`effective_identity_sources`、`dhcp_identity_classes`、`mac_identity_classes`、`unknown_identity_state` | R3 限定 `/var/lib/NetworkManager`、`/etc/NetworkManager`、`/run/NetworkManager`、`/usr/lib/NetworkManager/conf.d`、`/etc/netplan`、`/run/netplan`、`/lib/netplan`、`/run/systemd/network`；R2 解析配置身份键，C4 network/netplan units | 文件种类/计数、来源优先级、字段名、default/generated/custom/unknown 分类；SSID/IP/MAC/UUID/租约值不输出 | 空 `/etc` profile 目录不算通过；secret_key/lease 只读元数据；未知状态、renderer 或配置优先级不清则 STOP_NETWORK_IDENTITY_UNKNOWN |
| E7 | `journal_roots`、`directory_identity_relation`、`journal_storage_policy`、`namespace_units`、`journal_boot_order` | R3 仅枚举 `/var/log/journal`、`/run/log/journal` 一层目录与子项元数据；内存比较目录名和当前 machine-id；R2 journald.conf/drop-ins 的 Storage/SplitMode；C4 journald/flush units | count、matches-current/other/unknown、存储策略；不公开目录原名，不读日志正文 | 历史/命名空间目录不能自动认定可删；未知路径或没有生效策略时 STOP_JOURNAL_CLASSIFICATION |
| E8 | `seed_metadata`、`seed_owner_unit`、`seed_load_save_order`、`alternate_seed_mechanisms`、`boot_entropy_limit` | R1 仅 stat `/var/lib/systemd/random-seed`；C4 systemd-random-seed.service；由已安装包与实际 unit 判断其他 seed owner，存在则限定补读其 unit/config 元数据 | 存在/权限/大小、owner 和机制结论；不读取、不哈希、不输出种子内容 | 未知 seed owner、helper 或启动依赖时 STOP_SEED_MECHANISM_UNKNOWN；不能用当前 seed 存在证明克隆熵独立 |
| E9 | `unit_dependency_graph`、`condition_evaluation`、`activation_edges`、`current_boot_timestamps`、`identity_before_network`、`identity_before_ssh`、`unresolved_edges` | C4 对 E2/E4/E5/E6/E7/E8 发现的精确 unit 名闭包读取；包括 network-pre/network/network-online、SSH socket、netplan-configure；R3 读取相关 wants/requires symlink，C6 限定监听端口分类 | unit 名与 Before/After/Requires/Wants/触发关系、单次 boot 时间、可达顺序 supported/contradicted/unknown | After 不证明一定启动，Requires 不证明顺序；ConditionFirstBoot 当前跳过不证明克隆会触发；缺边或时间为零保持 UNKNOWN，不试启动服务 |

R2 的九类编号保持原顺序，E2/E3 分开计数。证据只说明当前安装机制；最终中性状态采用
missing、empty 或其他状态，必须等静态证据解释完成再作后续设计，本文不提前选择。

## 4. 限定读取与命令合同

### 4.1 文件读取原语（未来实现）

- R1：逐路径 `lstat`；只对批准的普通文件以 `O_RDONLY|O_NOFOLLOW|O_CLOEXEC` 打开，
  同一描述符 fstat/read，读前后 inode/size/mtime 变化则 STOP。拒绝设备、FIFO、socket。
  遇 symlink 先记录关系；只允许已审阅的同根链接，循环、越界、自定义终点均 STOP。
- R2：在内存解析 R1 得到的文本，输出正面允许字段，拒绝 shell 执行、模板求值及命令替换。
  网络配置允许字段：connection.type/uuid/stable-id/interface-name、ethernet 或 wifi 的
  cloned-mac-address/generate-mac-address-mask、ipv4.dhcp-client-id/dhcp-iaid、
  ipv6.dhcp-duid/dhcp-iaid/addr-gen-mode，以及 netplan renderer/dhcp-identifier/
  dhcp4/dhcp6/match.macaddress/set-name/macaddress。身份值只输出分类和本次内部相等关系。
  NM 全局默认项需绑定到实际安装版本及生效来源，不能把这些 profile 字段当作完整默认配置。
- R3：`os.scandir` + `lstat`，按名字排序，不跟随目录 symlink；E6 深度最多 3，
  E7 深度最多 2；总条目最多 512。原始文件名可能含身份，公开时使用 role + ordinal。
  lease、seed、NM secret_key、SSH 私钥和 journal 文件只读取元数据，禁止读取正文。
- 每普通文本最多 1 MiB；每命令输出最多 256 KiB；总私有结果最多 8 MiB；
  helper 最多 16 个、unit 最多 48 个、引用深度最多 4。任何超过预算均 STOP_TRUNCATED，
  不截断后宣称完整、不自动扩大扫描到整个 `/etc`、`/var` 或全部 systemd units。
- 目标已安装手册可以作为版本语义证据，先以包清单确定准确路径，再在内存有界解压读取；
  缺手册/源码时记录缺口，不能联网安装或用另一版本资料冒充目标事实。

### 4.2 只读命令正面清单（argv，无 shell）

| ID | 精确命令形式 | 输出处理 |
| --- | --- | --- |
| C1 | `systemd --version`；`uname -m` | 只保存版本/features 和架构；不运行 uname -a |
| C2 | `python3 -B --version` | 仅核对远端已安装解释器；缺失即 STOP |
| C3 | `dpkg-query -W -f=${binary:Package}\t${Version}\t${Architecture}\n systemd openssh-server network-manager netplan.io`；`dpkg-query -S <approved-absolute-path>`；`dpkg-query -L <resolved-package>` | 参数数组原样传递，不让 shell 展开；包名/路径来自前次已验证结果；只过滤本合同相关路径 |
| C4 | `systemctl --no-pager show <approved-unit> --property=Id,Names,LoadState,FragmentPath,DropInPaths,UnitFileState,ActiveState,SubState,Before,After,Wants,Requires,ConditionResult,Conditions,ExecStart,ExecStartPre,ExecStartPost,TriggeredBy,Triggers,ActiveEnterTimestampMonotonic,InactiveExitTimestampMonotonic` | 原始输出仅进入受限内存；Exec 参数和路径必须经过分类后写证据；读取 FragmentPath/DropInPaths 指向的已批准 unit 文本，核对磁盘与 loaded 配置，无 daemon-reload |
| C5 | `findmnt --noheadings --mountpoint /etc/machine-id --output TARGET,FSTYPE,OPTIONS` | 不采 SOURCE；用匹配与否加 errno 分类，不把所有非零当 absent |
| C6 | `ss -H -ltn` | 在内存只提取 SSH 对应端口监听是否存在及 wildcard/loopback/specific 分类；原地址丢弃；不能因此证明外部可达 |

所有命令使用固定安全 PATH，验证解析后的 executable 与包来源；不使用 `shell=True`。
`<...>` 代表受严格校验的单个 argv，不是用户拼接 shell。每命令超时 10 秒，总远端
预算 120 秒；超时终止只读探针、保存已有结果，禁止重新连接自动重跑。
unit 白名单闭包只含矩阵涉及的身份/网络/SSH owner；发现不在预算或范围内的依赖则 STOP。
不使用 `systemctl status`、journal 日志全文、nmcli 全量 profile、环境变量全量转储或 sshd 全量配置输出。

完整脚本控制流可在私有审阅材料中保留，但只允许确认无秘密的包源码片段。
配置中的密码/PSK/token、私钥与 seed 正文不保存到任何证据文件。未能安全投影的字段记
`WITHHELD_REQUIRES_PRIVATE_REVIEW`，停止语义通过判定，不能只存摘要假装已理解行为。

## 5. 新执行授权与传输边界（尚未授予）

```text
PROPOSED_GATE=N3W_T1_GOLDEN_MASTER_R2C_TARGET_ARMBIAN_SEAL_ADAPTER_READONLY_EVIDENCE
PROPOSED_CONFIRMATION=READONLY R2C TARGET ARMBIAN EVIDENCE: YES
ACTUAL_T1_EXECUTION_AUTHORIZATION_REQUIRED=true
ACTUAL_T1_EXECUTION_AUTHORIZATION_GRANTED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
P2B_AUTHORIZATION_CLAIMED=true
P2B_AUTHORIZATION_CONSUMED=false
P2B_AUTHORIZATION_REPLAY_PERMITTED=false
```

未来执行前还必须完成与本合同一致的最小探针/执行器实现、隔离测试与源码复核，绑定
准确 commit/blob/hash，并取得本次新的目标只读授权。不得直接复用旧 P2B confirmation、
authorization 或 manifest。旧 P2B executor 仅为设计参考，当前 probe 不覆盖 E1–E9 全集。
若下一会话尚无合格执行器，只能先做仓库内实现与复核，不能借本合同开始 SSH。

最终操作入口由 Mac Terminal 执行；远端只以 SSH stdin 传递绑定后的只读程序，
使用已有 Python 的 `-B`，不 scp、不落地脚本、不 pip/apt 安装。
私有 SSH target 与 host-key trust 在 Mac 上单独核对；未知/变化 host key 停止，
不得自动 accept-new、清除 known_hosts 或放宽验证。SSH/sudo 必须非交互且超时有界。

授权绑定：新 execution_id、probe/source SHA、目标受保护标识、范围和有效期。
Mac 私有目录 0700、文件 0600、O_EXCL 创建一次性 claim，先于首次远端请求。
claim 已存在或传输结果未知时只恢复本地记录，不重连、不重放；需要新的明确决定。
不在 T1 写授权账本。执行器必须持久保存 start/result/exit 状态及输出摘要。

“只读”指没有主动配置/产品/身份写入或服务操作；正常 SSH/sudo 审计日志、读取带来的
OS 元数据变化不保证为零。因此本 gate 不宣称整盘 bit-exact 不变，不用于已 final-sealed
母盘，也不能借此跳过日后的 shutdown/offline capture 顺序。

禁止：任何 machine-id/SSH/NM/journal/seed 中性化，运行 firstrun/keygen/firstboot，
systemctl start/stop/restart/reload/enable/disable/daemon-reload、netplan apply/generate、
nmcli 修改、Docker 查询/启动、网络修复、重启/关机、磁盘采集、板卡访问。

## 6. 结构化证据合同

schema 名：`gh.n3w.t1-r2c-readonly-evidence/1`。顶层只允许下列键；额外键拒绝。

| 键 | 类型及约束 |
| --- | --- |
| `schema` | 上述固定字符串 |
| `execution_id` | 新的一次性标识；非 P2B 标识 |
| `source_head` / `probe_sha256` / `contract_sha256` | 40/64/64 位 hex；执行前冻结，未实现时不得填假值 |
| `authorization` | grant_id、granted、claimed、consumed、replay_permitted；本轮全无执行授权 |
| `target_binding` | private binding 验证结果、E1 platform、same_boot；原始定位信息禁止进入 public projection |
| `requirements` | 恰好 E1–E9；每类含第 3 节指定字段和下述公共包络 |
| `capture_status` | NOT_EXECUTED / COMPLETE / INCOMPLETE / FAILED |
| `static_review_status` | NOT_EXECUTED / SUPPORTED / CONTRADICTED / INCONCLUSIVE |
| `stop_reasons` | reason code 数组；不放原始 stderr、地址、配置值 |
| `boundaries` | t1_access、intentional_target_write、service_mutation、board_access、merge，实际记录不得伪填 |
| `os_identity_semantics_proven` | 此只读 gate 固定 false |
| `controlled_clone_boot_required` | 固定 true |
| `disk_capture_ready` | 固定 false |
| `public_projection_review` | NOT_REVIEWED / PASS / FAIL |

每类别公共包络：`status=OBSERVED|ABSENT|UNKNOWN|ERROR|NOT_EXECUTED`、`complete`、
`reason_code`、`method_ids`、`provenance`、`fields`。每个 field 均有 value（可 null）与
状态；未知不写 false。ABSENT 只能来自已验证目录/文件读取的 ENOENT，E2 主程序缺失等
必要项 absent 仍不能满足整体 COMPLETE。身份相等比较需要两个成功读取值，否则 UNKNOWN。
provenance 包含文件角色、程序/配置来源、包版本、行号/摘要和读取返回码；敏感名称用角色替代。

单次 boot 稳定性通过 `/proc/sys/kernel/random/boot_id` 在内存前后比较，仅保存 boolean；
程序/配置集合读前后摘要连续，运行时元数据允许自然变化但不得越过身份/boot 变化。
不声称该检查提供原子全机快照。变化、权限不足、无输出、命令不存在、未解析引用、预算溢出
分别记录，任何一项影响关键字段均 INCOMPLETE/STOP。

public projection 是另一个正面允许字段输出，不是私有 JSON 简单删几个键。
公开仅保存平台版本、角色/枚举、count、boolean、源码/合同/脱敏证据摘要与审阅结论。
不公开 raw hostname/machine-id/fingerprint/SSH locator/IP/MAC/SSID/UUID、原始目录名、
密码、seed、private key 或完整原始输出。不使用低熵敏感值的普通 hash 代替脱敏。
私有执行材料保存在仓库外；公共证据仅绑定经审阅后的报告 SHA-256/字节数。

## 7. 通过、停止与后续边界

- preparation PASS：九类映射完整；命令只有观察；schema/隐私/预算/授权和停止条件明确。
- capture COMPLETE：E1–E9 均有完备材料，安全投影通过；不等于 clone semantics PASS。
- static review SUPPORTED：具体解释目标版本中性化后各机制的条件、fallback 和依赖，
  逐结论引用 evidence；无证据不能用通用 Linux 经验补齐。
- 任一重要缺口：STOP_EVIDENCE_GAP；证据缺失不是源码或运行故障，不重新打开 A1–A10。
- 意外主动写入/服务操作：STOP_BOUNDARY_VIOLATION，保留证据、报告已发生动作；不自动修复或回滚。
- 受控克隆启动、真实 Seal adapter、磁盘镜像和工厂 A/B 唯一性验收仍属后续独立范围。

后续执行 closure 必须分别列出 capture/static review/clone evidence 三项，列出九类完整性、
未知项与原因、授权使用状态、remote exit、同 boot 检查、公开审阅结果和剩余工作。
任何结果都不能自动进入 Seal、provisioning 或服务 activation。

## 8. 本轮文档复核与停止记录

桌面逐项复核（不是执行器测试，也未连接 T1）：

| 情形 | 预期分类 |
| --- | --- |
| 九类材料齐全但没有克隆启动 | capture 可 COMPLETE；semantics=false；clone test required |
| NM /etc profile 为零但 /var/lib 未读 | INCOMPLETE / STOP_NETWORK_IDENTITY_UNKNOWN |
| machine-id 读取权限不足 | UNKNOWN，不能当 empty 或 absent |
| firstrun 动态 helper 或脚本超过预算 | STOP_UNRESOLVED_IMPLEMENTATION / STOP_TRUNCATED |
| SSH 仅有 After，没有触发/条件证据 | 顺序 UNKNOWN，不能声称身份先于可达 |
| 私钥/seed 读取请求或配置秘密进入输出 | 拒绝读取/公开，STOP_BOUNDARY_VIOLATION |
| 已 claim 后连接超时、无可靠 remote exit | execution UNKNOWN，禁止重放 |
| 目标版本与 P2B 不同、boot 中途变化 | STOP_TARGET_DRIFT / STOP_TARGET_CHANGED |

```text
R2C_EVIDENCE_REQUIREMENT_COUNT=9
R2C_EVIDENCE_FIELD_SET_FROZEN=true
TARGET_READONLY_COMMAND_SET_FROZEN=true
PRIVATE_PUBLIC_EVIDENCE_BOUNDARY_FROZEN=true
STRUCTURED_CLOSURE_SCHEMA_FROZEN=true
PREPARATION_GATE_RESULT=PASS
EXECUTOR_TESTS=NOT_APPLICABLE:DOCUMENTATION_ONLY
TARGET_COMMANDS_EXECUTED=false
ACTUAL_T1_EXECUTION_AUTHORIZATION_GRANTED=false
NEXT_ROUTE=N3W_T1_GOLDEN_MASTER_R2C_TARGET_ARMBIAN_SEAL_ADAPTER_READONLY_EVIDENCE
NEXT_ROUTE_PREREQUISITE=REVIEWED_EXACT_EXECUTABLE_PACKAGE_AND_NEW_EXPLICIT_AUTHORIZATION
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
```

本轮范围为新建本合同与更新 current state/index 三个文档，不新增 KF（沿用 KF-113），
不变更 ADR 或已冻结产品设计。文档检查使用 git diff --check、九项/边界人工复核和现有
公共仓库安全检查；不重跑无关固件或实机测试。CI 的结果按准确提交单独读取并报告，
不把前序提交的绿色结果算作新文档提交的结果。

归档分类：三份文档 PUBLIC_SAFE；本轮无 private raw evidence、无新增源码/测试，
无必须留在聊天或临时目录的工程成果。成功提交后以 Git commit 和远端逐字比对作为归档绑定。

提交前复核结果：九类覆盖、只读命令边界、未知值不冒充否定值、P2B 不重放、
公开脱敏以及不跨入执行六项均 PASS；`git diff --cached --check` 与现有
`tools/check_public_repository_safety.py` 通过。交接 base 的 27 项 CI 在第三次检查时
全部通过；本轮新提交 CI 尚待远端注册，不混用这两个提交的结果。
