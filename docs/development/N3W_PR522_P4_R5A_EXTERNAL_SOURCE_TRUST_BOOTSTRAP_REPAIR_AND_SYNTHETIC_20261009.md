# N3-W P4 R5A 外部可信启动链修补与完整模拟回归（2026-10-09）

```text
TASK=N3W_PR522_P4_R5A_EXTERNAL_SOURCE_TRUST_BOOTSTRAP_REPAIR_AND_SYNTHETIC_20261009_01
REPAIR_BASE=9abb89d219475558ff80f03279362cab291ef279
SOURCE_ONLY=true
R5A_TRUSTED_LAUNCHER_CREATED=true
R5A_SELF_REFERENTIAL_SOURCE_PIN_REMOVED=true
R5A_FD_PINNED_KNOWN_HOSTS=true
R5A_H2_LIVE_ENABLED=false
R5A_SYNTHETIC_TESTS=113_OF_113_PASS
R5A_CI_COMMIT=9c030baacc503662616217986c11c2a33d401ff5
R5A_CI=12_OF_12_PASS
R5A_INDEPENDENT_SOURCE_REVIEW=PENDING
T1_ACCESS=false
BOARD_ACCESS=false
SETUP_SECRET_IMPORT=false
P4_FIRST_NORMAL_BOOT=false
MERGE=false
STOP=true
```

## 1. 冻结 GitHub 权威

- Repository: `chrenguo-stack/HomeAssistant`.
- PR #522: `58107b36fc20ccbef014d13cbfb708186395441c`, still Draft/unmerged.
- PR #529 R4 HEAD: `4306fbd39e4ecc9ab27329712d989eca0c90816a`, still Draft/unmerged.
- PR #531 R5A HEAD: `9abb89d219475558ff80f03279362cab291ef279`, still Draft/unmerged.
- PR #532 successor repair branch: `fix/n3w-pr522-p4-r5a-external-trust-bootstrap-20261009`, based exactly on PR #531 frozen HEAD.
- Original R5A independent review finding: https://github.com/chrenguo-stack/HomeAssistant/pull/531#issuecomment-6072704402.

本修补没有修改旧 R4 包中的 `bridge_handoff.py`、`remote_projection.py`、`host_readonly.py`、`validator.py`，不修改生产固件、Manager 或 Broker。

## 2. 实施的源码信任链

R5A 原缺陷：把 `APPROVED_R5A_SOURCE_GIT_BLOB` 放在需要自身校验的 `field_preboot_readonly.py` 中，填写自身哈希后会改变自身源码，无法形成可靠的自举验证；且 Python 在执行自身之前不能可靠地先证明自身源代码未被改动。

本修补：

1. **新增 `r5a_verified_entry.py`**，专用于加载前源代码校验和 Mac 本地 H1。它先按外部冻结的 Git blob 校验 `field_preboot_readonly.py` 的**实际文件字节**，并逐个校验四个原 R4 依赖，然后才从这些经过校验的字节执行 Python 编译/模块加载。
2. **删除 `field_preboot_readonly.py` 的自引用哈希常量与自身校验。** 外部启动器持有独立的 `FIELD_MODULE_BLOB`，无需让目标源码引用自己的最终 SHA。
3. 源码装载检查普通文件、路径符号链接及上级目录符号链接；文件 SHA 漂移、中途替换、缺失依赖、被篡改的预启动代码均拒绝加载。
4. `r5a_verified_entry.py` 只暴露 `load_verified_field_module` 与 `verify_mac_h1_only` 等本地接口，**不提供现场 SSH 或导入 CLI**；直接运行模块也拒绝。
5. **外部启动器本身不能自证可信。** 现场首次执行前必须从独立批准的固定 commit / Git blob 或外部受信签名清单，先核对启动器的完整字节和受信源头，之后才能加载。不能把随意编辑的本地 manifest 或项目文档当成独立信任根；本文件是审查用归档，不是现场授权令牌。

源码层面校验锚点：

```text
R5A_EXTERNAL_LAUNCHER=r5a_verified_entry.py
R5A_LAUNCHER_GIT_BLOB=0385ead98e56de49015682728a7982b31c76a7ab
R5A_FIELD_MODULE_GIT_BLOB=e43b4782df140527bef2f1c155cb52b8f42d36fd
R5A_R4_BRIDGE_GIT_BLOB=e277949c3db5675bd460124832a382d6a2765539
R5A_R4_REMOTE_PROJECTION_GIT_BLOB=7b3ba146583b61271b41390736b67207c8d4c14e
R5A_R4_HOST_READONLY_GIT_BLOB=0c62bc1b006eb2feab2e89d393cd477ad0912d83
R5A_R4_VALIDATOR_GIT_BLOB=3b7dc0d085dcda52fda0334840d75d5f8678bc1
```

源代码 `r5a_verified_entry.py` 的可信性必须靠独立的版本和下载完整性检查，不存在“自己校验自己”的特例。Git blob SHA 只说明指定内容是否与已批准的版本一致；是否批准版本、Mac 用户/SSH 主机身份、设备来源仍由独立现场授权确认。

## 3. SSH known_hosts 检查与使用绑定

原流程校验已批准的 `known_hosts` 文件哈希和主机公钥后，实际 SSH 命令再按原路径重新读取，检查与使用之间存在文件被替换的窗口。

新流程使用 `_verified_known_hosts`：

1. 对原本已冻结的 `known_hosts` 做路径、owner/mode、哈希和 `ssh-keygen -F` 查找。
2. 将同一次校验的字节复制到仅本进程持有的临时普通文件描述符；`ssh-keygen` 使用 `/dev/fd/N` 查找该文件内容，核对允许的一条主机公钥指纹。
3. 最终 SSH 使用同一个已验证的 `/dev/fd/N`，通过 `pass_fds=(N,)` 传递，杜绝 SSH 因原 `known_hosts` 路径被替换而读取另一份内容的路径竞争。
4. 不允许 `StrictHostKeyChecking=no`、自动更新主机密钥、网络跳板或重新信任未知主机。异常均 STOP，原文件不自动修复。
5. **Mac OpenSSH 对 `/dev/fd/N` 的实际兼容性尚未在真实 Mac/T1 执行验证。** 不把 Python CI mock 断言等同于现场兼容性。真实 H2 之前必须另设 Mac 本地与宿主机只读验证门。

## 4. H1/H2 权限边界

`FIELD_H2_LIVE_EXECUTION_ENABLED = False` 是当前版本硬禁止现场 SSH 的显式 STOP；本阶段绝不将其改为 True。测试模拟时才局部替换为 True，且所有 subprocess 均被测试替身拦截。

这项硬停止**不是未来的一次性 H2 人工授权实现**；Python 进程内部的布尔值不能代替独立审批和持久授权消费机制。现场实际授权仍须独立实现及复核，不得绕开外部启动器调用 `preboot_host_once` 即宣称已获准。

H1 合法正向结果仅包含源码校验 PASS、私有基线 PASS、SSH 主机公钥 PASS、组装只读程序通过检查，明确声明 **REMOTE_PROGRAM_NOT_EXECUTED**、H2 not authorized、STOP true。H2 首次启动前五身份核验在模拟环境验证，未访问真实 T1；R4 post-hello 唯一新增身份投影独立保留。

P4 实板首次正常启动、真实光学 QR、120 秒 pending TTL at-use 和一键 Setup Secret 导入全部仍未授权。

## 5. 完整模拟回归矩阵

PR #532 本次新增 16 项 `test_r5a_verified_entry.py`，加上原有 97 项，共 113 项。主要覆盖：

| 检查 | 期待结果 |
| --- | --- |
| 外部加载器加载 frozen R5A + 四个 R4 依赖 | PASS，先固定字节再 import |
| 源码自我哈希常量缺失 | PASS，取消循环引用 |
| 某个源文件在 import 前被恶意改成可执行代码 | 拒绝加载，无恶意代码执行 |
| 四个依赖任一哈希漂移 | FAIL before import |
| 源码或依赖替换成符号链接、源文件丢失 | FAIL before import |
| 合成私有 baseline（五历史身份、0600、SHA）、仿真 SSH key、真实加载器的完整 H1 调用 | PASS_LOCAL_NO_SSH（SSH-keygen 由模拟器替代） |
| Mac 快照内容漂移/错误 owner/mode | FAIL，不继续主机检查 |
| 主机公钥信任锚点缺失或错误 | FAIL |
| known_hosts 原路径在检查后被替换 | 从同一 FD 读取原已验证内容；原路径下次校验失败 |
| SSH 参数与主机密钥使用 | 必须采用 `UserKnownHostsFile=/dev/fd/N`、`pass_fds` |
| 未获准真实 H2 | 必须在任何 SSH 之前 STOP |
| H2 simulated 第六身份、pending 会话、缺 SQLite 字段 | 全部 STOP |
| SSH 错误、超时、JSON 错误、过期或错误阶段回包 | 全部 STOP |
| 机密、Setup Secret、真实 SSH、产品固件、Manager 修改 | 本轮没有真实操作或机密材料 |

所有新增场景使用合成私有快照、合成主机密钥和 subprocess 模拟器。完整 H1 正向链的本地目标地址哈希因真实 T1-A 为私密现场材料，测试中使用局部模拟值；源绑定和地址哈希守卫另有独立测试。不得称已做完整真实 Mac 环境或 T1 核验。

CI 证据：
- R5A 实体 GitHub Actions [专项模拟运行](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/37873071250)，运行结果 `Ran 113 tests in 1.227s`、`OK`。
- 同 exact source commit `9c030baacc503662616217986c11c2a33d401ff5` 的 GitHub workflow 12/12 PASS，包含公开仓库安全检查。

## 6. 后续审查与停止点

```text
R5A_B1_SELF_REFERENTIAL_HASH=REPAIRED_SOURCE_PENDING_INDEPENDENT_REVIEW
R5A_B2_OPERATOR_H2_ONESHOT_PERMISSION=OPEN_NOT_IMPLEMENTED
R5A_B3_LOCAL_H1_SYNTHETIC_POSITIVE=PASS_SYNTHETIC
R5A_B4_KNOWN_HOSTS_PATH_TOCTOU=REPAIRED_SOURCE_PENDING_MAC_COMPATIBILITY
R5A_NEW_TESTS=16_PASS
R5A_TOTAL_SYNTHETIC=113_PASS
A4_LIVE_T1=OPEN_NOT_RUN
A5_MANAGER_PENDING_TTL_AT_USE=OPEN
A6_DURABLE_ONESHOT_SECRET_IMPORT=OPEN
R5A_FIELD_LIVE_READY=false
LIVE_T1_AUTHORIZATION=false
P4_FIRST_NORMAL_BOOT_AUTHORIZED=false
REAL_SETUP_SECRET_IMPORT_AUTHORIZED=false
NEXT_ONE_GATE=N3W_PR522_P4_R5A_EXTERNAL_TRUST_BOOTSTRAP_R2_INDEPENDENT_SOURCE_REVIEW_20261009_01
NEXT_GATE_CLASS=READONLY_SOURCE_REVIEW_NONLIVE
AUTO_EXECUTE_NEXT_GATE=false
MERGE=false
STOP=true
```

本门完成后应先对 exact GitHub HEAD、source loader、fd 使用和真实 CI 进行独立源码复核；不能仅因 113 项模拟测试全绿就打开 Mac/T1/配对授权。
