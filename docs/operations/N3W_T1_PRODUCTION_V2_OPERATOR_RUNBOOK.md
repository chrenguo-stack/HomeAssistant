# N3-W T1 Production V2 操作员手册

> 状态：2026-10-22 操作手册版；产品源码不变。适用范围：一台新安装标准 Armbian 的同型号 T1。**本文件不是生产授权，也不授权重刷、登录实际 T1 或启动生产。** 每台新设备都需要自己的批准、身份绑定、独立执行和完整验收。

## 0. 先读：适用范围与停止规则

唯一正常路线：

```text
OFFICIAL_ARMBIAN_INSTALLED
→ EXACT_RELEASE_VALIDATION
→ STANDARD_FRESH_ARMBIAN_QUALIFICATION
→ ONE_PRODUCTION_APPROVAL
→ HOST_BASELINE / F3 / PROVISION / F4
→ CONTROLLED_REBOOT
→ SSH_EPOCH_2
→ POST_REBOOT_READINESS / POST_REBOOT_ACCEPTANCE
→ ACCEPTED
```

本流程不是维修、恢复或旧机器迁移工具。**不提供** resume failed run、repair target、清除/重置 marker、force acceptance、replay failed run。发现已存在生产目录、marker、Docker、产品容器、服务或数据库时不要清理以“通过”资格检查；停止，按结果分流。

安装完官方 Armbian 后，在生产程序接管之前，不要自行安装 Docker/Compose，也不要新建产品目录、证书、MQTT 密钥、Home Assistant 数据、systemd 产品单元、生产 marker 或任何 F3/F4/F5 staging。允许完成官方首次启动与网络/时间准备，但禁止手工“预装产品”。

**操作权限分隔：** 本手册中的下载、哈希、Git 检查属于 Mac 本地准备；读取设备 host key 或启动 SSH 是真实 T1 访问；执行器批准后会写入设备并启动服务；受控 reboot 会重启设备。每个边界均须由当次生产工单明确授权。不要把本文的示例当成现场批准。

## 1. 当前权威从哪里确认

进入一次新生产之前，先阅读：

- [当前状态](../development/N3W_CURRENT_STATE.md)
- [状态索引](../development/N3W_CURRENT_STATE_INDEX.md)
- [已知故障与回归保护](../development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md)
- [V2 冻结架构](../development/N3W_T1_F5_PRODUCTION_PROCESS_V2_SIMPLIFIED_ARCHITECTURE_CONTRACT_20261019.md)
- [T1-B 实机闭环](../development/N3W_T1_B_F5_V2_REAL_PRODUCTION_ACCEPTANCE_CLOSURE_20261022.md)

T1-B 曾在源码 `4733c09ab7653bacca6e197e63a583f500b45845` 下使用 `release_id=d34e6d132518376a595e3d42f5acc64a904d2d809e2c80332635f35a16af00df` 完成真实 ACCEPTED。此信息仅用于追溯，**不得作为未来每一台 T1 的自动授权**。Release 的 `source_head` 不必与仅增补文档的最新 main 相同；但不能忽略实际产品源码漂移。

当前实例的 Actions 下载入口：[run 39744898094](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/39744898094)，artifact ID 为 `12410429647`，ZIP 的 SHA-256 为 `2b7323e07575ef9a5703bbd7965af1278e3c7260c79fe9f1dcaab47dcc3424be`；GitHub 标示到期日 **2026-11-21**。**不要以 30 天 Actions artifact 当长期分发库**。过期、SHA 不同、无法取得可信 metadata 或找不到完整本地验证记录时，STOP；交由 release 管理流程获取重新验证的有效包，不能临时重打包冒充旧 release。

## 2. Mac 工作台与私有目录

工作站必须有 macOS、可交互 Terminal、Python 3、Git、OpenSSH 的 `ssh`/`scp`、`ssh-keygen`、`gh`（用于从 GitHub 下载和查询 metadata）及 `/usr/bin/false`。需要有仓库源码目录、经验证的 exact release，以及只属于本次生产的私有目录。执行器依赖同目录 Python 模块和 `Path(__file__).parent` 查找辅助工具；不要求直接运行所有内部阶段命令。Release 自身包括 `v2_mac_tools`，不等于双击可运行的应用。

下列命令只在 Mac 本地准备目录，不连接 T1。请在新的 Terminal 中逐段执行：

```bash
umask 077
mkdir -p "$HOME/Documents/N3W/production-private"
chmod 700 "$HOME/Documents/N3W/production-private"
command -v python3
command -v git
command -v ssh
command -v scp
command -v ssh-keygen
command -v gh
test -x /usr/bin/false
```

任何依赖缺失即 STOP。不要用 `sudo python3` 从 Mac 运行生产执行器；私有证据应由当前登录用户持有。不要把密码写入环境变量、命令行、Git 仓库或 shell 历史。

## 3. 取得 exact release，并进行真正的本地核验

正式交接应提供：`SOURCE_HEAD`、`SOURCE_TREE`、`RELEASE_ID`、`RELEASE_SHA256`、GitHub workflow run ID、run attempt、artifact ID/name、artifact ZIP digest、**GitHub run 和 artifact 的原始 JSON metadata**，以及下载完成后完整 `verify-bundle` 的 PASS 报告。操作员不得自行猜测任何一个值。

示例下载方式（下面的值为 T1-B 已验收的历史实例；只有生产工单再次明确指定此 release 时才使用）：

```bash
export N3W_RELEASE_RUN=39744898094
export N3W_RELEASE_ARTIFACT=12410429647
export N3W_PRIVATE="$HOME/Documents/N3W/production-private"
mkdir -p "$N3W_PRIVATE/release-download"
chmod 700 "$N3W_PRIVATE/release-download"
gh run download "$N3W_RELEASE_RUN" --repo chrenguo-stack/HomeAssistant --dir "$N3W_PRIVATE/release-download"
gh api "repos/chrenguo-stack/HomeAssistant/actions/runs/$N3W_RELEASE_RUN" > "$N3W_PRIVATE/run-metadata.json"
gh api "repos/chrenguo-stack/HomeAssistant/actions/artifacts/$N3W_RELEASE_ARTIFACT" > "$N3W_PRIVATE/artifact-metadata.json"
```

注意：`gh run download` 默认会展开 Actions artifact 的外层 ZIP，**不是**本项目 `verify-bundle --artifact-zip` 所要求的原始 GitHub artifact ZIP。完整验证必须另外保留**原始未解包 artifact ZIP**（可通过受支持的 GitHub artifact 下载渠道取得），核对 ZIP SHA 后传给工具。不能将解出的内部 tar 改名成 ZIP，也不能把 `gh run download` 的目录伪装成外层原始 ZIP。

源码的完整验证命令为：

```bash
python3 tools/n3w_t1_f5_v2_release_builder.py verify-bundle --repository "$N3W_SOURCE_REPO" --artifact-zip "$N3W_ARTIFACT_ZIP" --expected-artifact-sha256 "$N3W_ARTIFACT_ZIP_SHA256" --run-metadata-json "$N3W_RUN_METADATA" --artifact-metadata-json "$N3W_ARTIFACT_METADATA" --artifact-name "$N3W_ARTIFACT_NAME" --artifact-id "$N3W_ARTIFACT_ID" --run-id "$N3W_RELEASE_RUN" --run-attempt "$N3W_RUN_ATTEMPT" --source-head "$N3W_SOURCE_HEAD" --source-tree "$N3W_SOURCE_TREE"
```

所有 `N3W_...` 路径/值必须来自当次 release 工单，不能填空执行。**重要兼容限制**：当前 `verify-bundle` 除核对本地 `HEAD == SOURCE_HEAD` 外，还要求 `origin/main == SOURCE_HEAD`。若今天的 main 仅因文档前进而不再等于旧 release 的源码 SHA，直接在最新 checkout 上验证旧包会失败。**禁止**为让验证通过而伪造或改写 `origin/main` 引用；也不得把 `verify --destination` 这种目录级检查写成等同完整 `verify-bundle`。当前历史 release 必须保留原先真实 PASS 的完整绑定报告及其可核验来源；缺失时 STOP，由 release 管理流程解决，不进入生产批准。

完成完整验证后，使用经验证的 release 根目录（包含 `release.json`、`release.sha256`、`artifacts/`），并校验：

```bash
python3 "$N3W_SOURCE_REPO/tools/n3w_t1_f5_v2_release_builder.py" verify --destination "$N3W_RELEASE_ROOT"
```

`verify` 是额外的目录完整性检查，不能替代上述 GitHub 外层来源和内部包完整验证。后续执行器也会再次运行 `verify_release_directory`。

## 4. 取 T1-C SSH 主机身份，不信任网络扫描结果本身

**STOP — 以下步骤涉及现场设备身份取证。仅在新 T1 已被授权进入只读准备时执行。**

在 T1 本机可信控制台查看当前 `/etc/ssh/ssh_host_ed25519_key.pub`，独立核对机器标签与公钥，不从未经确认的 `ssh-keyscan` 结果直接建立信任。把已经核对的完整公钥作为操作员私有输入转移到 Mac。下面是 Mac 本地建文件模板（终端会等待操作员粘贴一整行 `ssh-ed25519 AAAA...`，按 Ctrl-D 结束）：

```bash
umask 077
cat > "$N3W_PRIVATE/t1-ed25519.pub"
chmod 600 "$N3W_PRIVATE/t1-ed25519.pub"
ssh-keygen -lf "$N3W_PRIVATE/t1-ed25519.pub" -E sha256
```

使用**实际**目标地址创建 `known_hosts`，不要在本文填入真实 IP；如果目标采用 `root@IP`，文件第一列必须是对应 IP，不是用户名。模板：

```bash
printf "T1 target host or IP: "\nread -r N3W_TARGET_HOST
export N3W_TARGET="root@$N3W_TARGET_HOST"
python3 - "$N3W_PRIVATE/t1-ed25519.pub" "$N3W_TARGET_HOST" "$N3W_PRIVATE/known_hosts" <<'PY'
import base64,hashlib,pathlib,sys
pub=pathlib.Path(sys.argv[1]).read_text().strip().split()
if len(pub)<2 or pub[0]!="ssh-ed25519":
    raise SystemExit("STOP: expected one ED25519 public key")
blob=base64.b64decode(pub[1],validate=True)\nif len(blob)<32 or blob[:4] != b"\\x00\\x00\\x00\\x0b" or blob[4:15] != b"ssh-ed25519":\n    raise SystemExit("STOP: invalid ED25519 blob")
digest=hashlib.sha256(blob).hexdigest()
path=pathlib.Path(sys.argv[3])
if path.exists() or path.is_symlink():
    raise SystemExit("STOP: known_hosts already exists")
path.write_text(f"{sys.argv[2]} ssh-ed25519 {pub[1]}\n")
path.chmod(0o600)
print("EXPECTED_HOST_KEY_SHA256="+digest)
PY
```

记录输出的 `EXPECTED_HOST_KEY_SHA256`（64 位小写十六进制），供后续执行器使用；它是 ED25519 **公钥二进制内容**的 SHA-256，不是把 `ssh-keygen -lf` 显示的 `SHA256:...` 文本直接拿来做参数。不要将私有目标地址、主机公钥或 known_hosts 上传公开仓库。首次确认失败、host-key mismatch、设备重装后 key 变化均 STOP，回到可信本机控制台重新建立**新的设备身份和新的 run**。严禁 `StrictHostKeyChecking=no`。

## 5. 自动资格检查和唯一真实生产入口

当前真实入口是 `tools/n3w_t1_production_v2_executor.py`。必填参数：

| 参数 | 含义 |
| --- | --- |
| `--release-root` | **已验证并解出的** release 根目录（不是 ZIP） |
| `--target` | `root@<实际目标IP或主机名>` |
| `--known-hosts` | 上一节的私有 host-key 文件 |
| `--expected-host-key-sha256` | 64 位十六进制公钥 blob SHA-256 |

可选 `--run-id`：省略后自动生成新随机 run ID；可选 `--evidence-root`：省略后在 `~/Documents/N3W/production-runs/<run_id>` 新建私有目录。推荐新机器**不传 `--run-id`，也不传 `--evidence-root`**，让程序自动生成独立身份与证据目录，避免误用上次的运行编号。终端必须交互，不能重定向 stdin 或设置自动答复。

**STOP — 下面这条命令不是只读操作。只有当完整 release 验证已 PASS、设备身份核对完成、工单明确授权这台新 T1 量产，才允许运行。** 运行后将打开 SSH 并先进行只读 qualification；操作员精确批准后会写入 marker，安装 Docker/产品、写配置并重启。

```bash
printf "64-character EXPECTED_HOST_KEY_SHA256: "\nread -r N3W_EXPECTED_HOST_KEY_SHA256
PYTHONPATH="$N3W_SOURCE_REPO/tools" python3 "$N3W_SOURCE_REPO/tools/n3w_t1_production_v2_executor.py" --release-root "$N3W_RELEASE_ROOT" --target "$N3W_TARGET" --known-hosts "$N3W_PRIVATE/known_hosts" --expected-host-key-sha256 "$N3W_EXPECTED_HOST_KEY_SHA256"
```

`N3W_SOURCE_REPO` 必须指向受信任的 exact-source checkout，且其中执行器和 sibling modules 与 `v2_mac_tools` 所冻结的字节一致；也可由发布流程把 exact `v2_mac_tools` 解出为完整同目录工具集后作为来源。**禁止混合新版 checkout 执行器和旧版 release 工具。**

资格检查十项均由同一入口自动执行，无须操作员手工运行探测脚本：

```text
HOST.OS_ARCH
HOST.ARMBIAN_IDENTITY
HOST.FIRSTBOOT
HOST.SSH_TRUST
HOST.PRIVILEGE
HOST.NETWORK_TIME
HOST.STORAGE
HOST.APT_SOURCE
HOST.DOCKER_ABSENT
HOST.PRODUCT_ABSENT
```

- `PASS`：设备满足 exact release 的 Standard Fresh Armbian 合同，可进入审批画面；
- `FAIL_REFLASH_REQUIRED`：明确发现 OS/Armbian/firstboot/磁盘/软件残留等硬条件不符合；STOP，不现场维修或清理，按工单重装官方镜像，再作为新设备重新检查；
- `STOP_UNAVAILABLE`：网络、SSH、只读命令或时间等证据不足；STOP，修复工位/连通性后只允许重做**只读资格检查**，不能据此认定产品故障，更不能假造 PASS。

特别注意：当前执行器把 qualification 包在同一执行入口中，**独立重做资格检查**需要使用既有只读资格核查路径或新建一份新 run；不得通过重放已经 STARTED 的 run 来重试。

## 6. 唯一人工生产批准与自动阶段

系统会打印 `RUN_ID`、`TARGET_BINDING_SHA256` 和 `PRODUCTION_APPROVAL_SUMMARY`，摘要包含 release ID/SHA、source head、target binding、SSH host-key SHA、actions、所需批准文本。操作员务必与工单逐项核对：目标设备、release、完整 actions 和现场主机身份。

唯一有效的第一次批准内容是：

```text
APPROVE N3W T1 F5 V2 PRODUCTION <当前屏幕显示的完整run_id>
```

必须在 `PRODUCTION_APPROVAL>` 提示下**人工**输入，不准脚本自动回答。任何身份或 release 不符即拒绝批准并 STOP。

注意：当前批准摘要不直接打印 `plan_sha256`；批准的是完整的结构化 plan，之后算出的 `plan_sha256` 会写进 STARTED marker，不能假称批准前已人工核验该 SHA。

批准后自动处理：

| 阶段 | 在做什么 |
| --- | --- |
| `MARKER_START` | 将本次 run 置为不可重放的 STARTED |
| `HOST_BASELINE` | 按 release 固定版本准备 Docker/Compose |
| `F3_DEPLOY` | 部署 release 内绑定的镜像和产品文件 |
| `PROVISION` | 生成本机独有的实例配置/身份 |
| `F4_PREPARE` | 检查并准备产品控制 |
| `F4_ACTIVATE` | 启动服务 |
| `F4_ACCEPT` | 验收当前运行 |
| `F4_PERSISTENCE` | 设置重启后保持运行 |
| `F4_CERT_AUDIT` | 检查证书运行状况 |
| `F4_CERT_TIMER` | 配置证书周期检查 |

不要人工穿插执行任一内部 helper，更不允许在执行过程中替换 release/工具或 SSH 目标。

## 7. 重启前二次在场确认与第二次密码

控制安装、校验结束后，程序会进入 `REBOOT_ARMING>`，要求当次完整 run ID：

```text
ARM N3W T1 F5 V2 CONTROLLED REBOOT <当前屏幕显示的完整run_id>
```

这表示操作者现在在场并能完成重启后的密码登录；不是第二次生产批准。只有确认有人可及时输入新 SSH 密码后才输入该文本；不要自动填充。源码允许在 arming 提示无限等待，错误输入继续等待。此处暂停不等于生产失败。

之后程序验证旧 SSH ControlMaster 断开且 TCP/22 连续两次不可达，进入 `REBOOT_PENDING`，等待设备重新上线，再打开 **SSH_EPOCH_2**。它需要第二次人工输入 root 登录密码，每个 epoch 最多一次密码认证；不要离开工作台。设备启动后仍需等待最长 300 秒的产品就绪检查；仅仅 SSH 能登录不算产品已准备好。

## 8. 重启后自动验收与成功条件

程序先完成 `POST_REBOOT_READINESS`，再执行已有的严格 target-local reboot verifier、外部 MQTT/TLS/HTTP 探测、运行状态证据及 90 秒稳定观察。检验必须证明新旧 boot 不同、服务状态符合预期，且不会用生产 MQTT 身份登录测试或打断现有连接。最后才会写入 `ACCEPTED` marker。

唯一完整成功组合：

```text
status=PASS
marker_state=ACCEPTED
device_acceptance=PASS
T1_PRODUCTION_READY=true
operator_session_closed=true
evidence_complete=true
reflash_required=false
terminal_stage=COMPLETE
executor_exit_code=0
```

只看到容器在运行、某几条日志、服务端口开放、SSH 重连或单个阶段 PASS，都不算最终成功。以程序最后 `PRODUCTION_RESULT` 和**目标端 durable marker**、完整验收证据一致为准。

### 成功后的只读核对

**STOP — 最终结果不是只看日志。** 先在 Mac 当前 run 的私有 evidence 目录中核对 `result-private.json`、`result-public.json`，确认 `status=PASS`、`marker_state=ACCEPTED`、`device_acceptance=PASS`、`T1_PRODUCTION_READY=true`、`operator_session_closed=true`、`evidence_complete=true`、`reflash_required=false`。随后比对 `release_id`、`release_sha256`、`source_head`、`target_binding_sha256`、`run_id_sha256`。

需要进行**额外现场只读核对**时，应使用经生产授权、与已安装包字节绑定的 `n3w_t1_f4_reboot_verify.py` 或执行器已产出的 post-reboot acceptance/运行快照证据。严格验收本身已经核验真实重启、systemd 必要单元、Docker 容器、Broker、Manager、Home Assistant、证书、持久化以及 90 秒连续性；不需要为了终验安装新组件、启动新服务或重启已合格设备。

当前源码不能证明 `n3w_t1_production_marker.py` 在验收后的 T1 上有永久命令入口：执行器只在临时 workspace 上传和调用它。也不能凭经验假设真实 Docker 容器名称。**因此本 Runbook 不提供猜测的 target-local 命令。** 如果证据互相矛盾、缺失，或者要重新读取 durable marker，必须 STOP，走单独授权的只读核对计划，先从 exact release/已安装服务取得工具与路径的直接证据，不得在 ACCEPTED 的 T1 上修补或清除状态。

## 9. 失败处置：不得 replay

| 最终观察 | 含义 | 操作 |
| --- | --- | --- |
| `STOP_UNAVAILABLE`，设备 marker 尚不存在 | 资料/连通性不足，未证明产品坏 | 停止生产，只允许重新准备并独立进行只读资格检查 |
| `FAIL_REFLASH_REQUIRED`（资格检查） | 不符合全新标准机合同 | 停止、按工单重装官方 Armbian，再新身份/新 run |
| `marker_state=STARTED` 且未 ACCEPTED | 已开始设备写入，当前生产执行失败 | 禁止继续/修复/重放；冻结 failure、完成只读取证、关闭会话，再按正式结果决定重刷 |
| `marker_state=ACCEPTED` 但 Mac cleanup/evidence finalize 失败 | 设备自身已耐久验收，操作员会话/证据不完整 | 保留设备及证据；不要重刷已合格设备，单独进行只读取证和证据修复评审 |

`STARTED` 之后的标准故障链：

```text
FAIL
→ FREEZE_FAILURE
→ FORENSIC_SNAPSHOT
→ EVIDENCE_MANIFEST
→ SESSION_CLOSE
→ REFLASH_DISPOSITION
```

取证可以记录个别探针 `UNAVAILABLE`，但必须诚实记录，不能填造 PASS。取证未完整冻结时不得删除目录、清 marker、手动替换服务或开始新 run。故障根因即使后来确认只是网络、密码或人工离岗，也不能重放已 STARTED 的 run。重刷是一个**新的、明确授权的破坏性操作**，不是脚本自动重试。

对 `ACCEPTED` 后 Mac 侧处理失败，应保留 `device_acceptance=PASS`、`T1_PRODUCTION_READY=true`、`reflash_required=false` 的设备事实，同时如实记录 `operator_session_closed=false` 或 `evidence_complete=false`；不能将这种不完整的流程声称为完整绿色闭环。

## 10. 私有证据与 GitHub 归档

Mac 私有位置存储：原始 run ID、target IP/主机名、root password（密码只能人工交互、不得写文件）、known_hosts、完整 SSH 公钥、全部私有 evidence、私有工作目录、可能含身份的调试输出及产物。原始 Setup Secret、MQTT 密码、私钥、token 一律不得写入 GitHub；不要把完整 Terminal 记录无检查直接粘贴 PR。

公开仓库只记录：经过脱敏的结果字段、run ID 的 SHA-256、source/release 身份、target binding 摘要、验证阶段 PASS/FAIL、结论及相关 CI/工单链接。标准公开摘要来自执行器的 `result-public.json`，上传前仍要进行隐私检查；它不能代替完整私有取证。

## 11. 生产完成后的 STOP

成功时记录最终 `PRODUCTION_RESULT`、`ACCEPTED` 证据绑定与工单关单；停止，不自动开始下一台机器。不访问 ESP32 板卡、不执行配对或传感器工作（另属单独流程）。

失败时按第 9 节冻结，不发出自动修复命令。任何新 release、修改 Mac 工具或修改执行器，必须重新审查对应 exact-source 验证边界，不能拿旧 T1-B 实机 PASS 自动承认新字节。

## 12. 源码核对索引

- [执行入口](../../tools/n3w_t1_production_v2_executor.py)
- [生产状态机](../../tools/n3w_t1_production_v2.py)
- [资格检查](../../tools/n3w_t1_fresh_armbian_qualification.py)
- [SSH 传输](../../tools/n3w_t1_ssh_transport.py)
- [发布包验证](../../tools/n3w_t1_f5_v2_release_builder.py)
- [marker](../../tools/n3w_t1_production_marker.py)
- [故障取证](../../tools/n3w_t1_failure_forensics.py)
- [重启后验收](../../tools/n3w_t1_post_reboot_acceptance.py)

**文档冻结边界：** 本 Runbook 是脚本化 Production V2 的操作说明，不是此前已经延期的 standalone executable，也不是对未验证新设备的放行。当前 release 长期分发问题仍单独存在，不能用文档掩盖。
