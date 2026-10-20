# F5 V2 重启后非扰动验收合同与源码修复 — 2026-10-20

## 本门状态与范围

```text
TASK=N3W_T1_F5_V2_NONDISRUPTIVE_POST_REBOOT_ACCEPTANCE_CONTRACT_AND_SOURCE_REPAIR_20261020_01
BASE_MAIN=1a0689f2c1c6566a397f065ff546ad26ef02046d
BASE_PR_HEAD=e2f8a612887f227833f41baada28f79d0aeb61c7
SOURCE_BRANCH=fix/n3w-t1-f5-v2-real-production-executor-20261020
SOURCE_PR=628
RESULT=SOURCE_AND_CONTRACT_IMPLEMENTED_LOCAL_TESTS_PASS_CI_PENDING
REPOSITORY_MUTATION=true
T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PRODUCTION_RELEASE_BUILD=false
MERGE=false
AUTO_EXECUTE_NEXT_GATE=false
```

用户授权仅覆盖本次合同、源码、测试和归档修复。保持 PR #628 为草稿；本次不执行生产、不重刷、不重启、不合并，也不重用旧授权。下一停止点为本次源码与 CI 复核；精确发布包重建及实机验收属于之后单独决定的门。

## 已确认问题与判断边界

1. 旧 Mac executor 读取 system CA，而 Broker TLS 使用 `/etc/n3wfc4/tls/ca.pem`。两条 CA 链独立，不能混用。旧路径可能先因 TLS 验证失败而停止，所以本门不宣称真实 T1 已发生连接接管。
2. 一旦 TLS 与认证成功，用生产用户名、密码和相同 ClientID 登录会使旧连接被替换。MQTT 5 的 Clean Start=1、未设置 Session Expiry（默认为 0）还带来会话清理影响。修改这两个参数不能消除同 ClientID 接管；1883 与 8883 同属一个 Broker，也不能靠换 listener 隔离。
3. 90 秒首尾容器重启计数相同，不足以证明 MQTT 连续连接、HTTP 就绪和关键系统服务无错误。

协议依据：MQTT 5 §3.1.4、§3.1.2.11.2（[OASIS 原文](https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html)）；Mosquitto v2.1.2 `src/handle_connect.c` 的身份认证、同 ClientID 查找及旧连接清理顺序。该结论来自源码与协议分析，实机是否实际发生必须另有证据。

采用现有身份的只读认证证据方案；不新增探测身份、不修改 DynSec/ACL/clientid、不修改 Provision、Manager/HA 业务逻辑，也不引入额外管理服务。保留现有 F4 完整验收一次，复用已安装 F4 verifier 增加轻量快照入口。

## 当前合同

| 项目 | 修复后的行为 |
| --- | --- |
| TLS | 只信任 Broker CA，固定校验 `armbian`；不加载系统默认 CA、不关闭证书/主机名校验 |
| Mac 外部探测 | TCP 8883、TLS CA、TLS hostname/SNI、随机非生产身份认证拒绝、HA `/api/` readiness |
| 拒绝证据 | 仅有效 MQTT 5 CONNACK 0x86/0x87；成功、服务器忙、TLS 错误、超时、短包、畸形包均不算通过 |
| 服务自身认证 | F4 配置/身份验证 + Broker 精确用户名/ClientID 成功连接日志 + 服务 namespace 内持有的唯一预期 loopback MQTT 连接 |
| 非扰动边界 | 不读取/导出生产密码，不用生产身份从 Mac 登录；不创建/删除身份，不 SCP，不创建目标验收工作目录 |
| 观察起点 | F4 完整验证后、外部探测前建立基线；每项探测后检查连续性 |
| 最终观察 | 探测后一个 90 秒窗口，每样本后最多等 2 秒；完成样本间隔不超过 15 秒，至少 7 个有效有序样本 |
| 失败规则 | 任意样本失败立即停止，不允许后续恢复冲销；STARTED 后冻结、只读取证、关闭会话、要求重刷 |
| 正常周期变化 | 证书 oneshot 的健康执行/结束允许，失败或新增高优先级错误不允许 |
| 结果 | acceptance `/2`，`external_probes` 与 `runtime_service_auth` 分开，run/release/source/host-key/boot/control 与观察摘要参与结果哈希 |

连接指纹包含 socket inode、持有进程及启动标识、两端地址/端口，仅返回 SHA-256。Broker 经过 Docker NAT/proxy，不能声称其日志 peer 地址等于服务端 `/proc` 地址；本合同使用上述组合证据，而不是伪造地址相等证明。连接事件累计摘要可识别采样间发生又恢复的 MQTT 重连。有限采样不保证捕获每个任意短暂的 HTTP 抖动。日志缺失、截断、连接归属不唯一均是证据不足而停止，不应直接升级为产品故障。

快照同时覆盖容器 ID/StartedAt/RestartCount/Running、HA HTTP、核心 systemd ActiveState/Result/ExecMainStatus/NRestarts/启动标识，以及本次 boot 的高优先级错误游标。控制清单与 F4 事务哈希每次检查。完整 F4 verifier 不在每 2 秒采样里重复执行。

## 实现与发布路径

- `tools/n3w_t1_production_v2_executor.py`：删除生产密码导出和正向登录，修正 CA，严格解析负向响应，调用已安装 `--snapshot`，连续采样且失败即停。
- `tools/n3w_t1_post_reboot_acceptance.py`：新结果合同、基线与外部探测后的连续性、观察覆盖检查、证据哈希。
- `tools/n3w_t1_f4_reboot_verify.py`：只读快照；不写 reboot claim、事务或 marker。
- 已有 F4/reboot control package 和 F5 Mac 工具包源清单包含以上文件。测试校验打包后的文件集合/大小/摘要；未新增需额外安装的运行模块。
- 候选打包 byte-binding smoke PASS：临时生成 reboot control package 与 Mac tools tar，逐字节核对修改文件及 control manifest 摘要；输入为本地候选工作树，非 exact production authority，不保存为生产发布包。
- 生产发布必须在审阅合并之后从新的 exact main 重建 F4/reboot control、release inputs 和最终 release；旧发布包不能代表此次修复。当前门不构建或发布生产 artifact。
- 保留既有状态机：ACCEPTED 之前失败不能 READY；ACCEPTED 之后清理失败仍保留 READY。

当前架构合同 §7、源码设计 §6.1–6.3、工作包 §5.2 已同步。历史 R3 入口/关闭文档和旧 executor 修复记录保留原始事实，并加显式 superseding 注记；旧 `/1` 或旧 CI PASS 不被重新解释为本门通过。

## 本地验证与剩余验证

- 本地 Python 3.12 / pytest 9.1.1：R3/executor/acceptance/F4 verifier/发布构建器/marker 合同组 **127 passed**。
- F4 activation/certificate/authority/verifier/reboot package/ingress 关联组 **129 passed**；两组存在重复测试，不相加冒充唯一数量。
- 修改的 F4 source 与新增/修改测试通过仓库 Ruff；executor 原有非本门 lint 项不顺手重构。
- 覆盖：严格拒绝解析、随机非生产身份、零密码读取、只读入口、真实本地 `/proc` 连接归属、CLI 输出、认证日志缺失/截断/身份错配、短暂重连/重启/错误/HTTP 失败、无序/无穷/NaN/超大间隔时间样本、健康证书周期、结果哈希绑定。
- 本地无 Docker/Mosquitto，三项隔离 Broker 集成测试未运行，按条件 skip，不能记为通过。已加入独立 ARM64 CI job，使用锁定 Mosquitto 2.1.2 ARM64 manifest、临时凭据、loopback 发布端口，证明旧同 ID 登录接管（含 1883→8883）和新探测保持两个原连接可用，并验证 DynSec 正确密码/错误 ClientID 拒绝。
- CI 结果待本次提交之后复核；真实 T1 非扰动验收仍 NOT_EXECUTED。KF-122 保持 OPEN。

## 归档审计

本门源码、测试、合同、故障记录与进度均在同一 PR 提交；无生产凭据/私钥/目标原始地址进入提交。临时补丁脚本、pytest 缓存与可重现打包中间物归为可丢弃；其有价值结果均已记录于本文件和测试。

```text
ARCHIVE_CLASSIFICATION=PUBLIC_SAFE
PRIVATE_EVIDENCE_REQUIRED=false
KNOWN_FAILURES_UPDATED=true
SOURCE_FILES=3
TEST_FILES=4
WORKFLOW_FILES=1
DOC_FILES=10
NEW_UNTRACKED_BEFORE_STAGE=2
VALUABLE_LOCAL_ONLY_RESULT_COUNT=0
UNARCHIVED_CRITICAL_RESULT_COUNT=0
NEXT_ONE_GATE=N3W_T1_F5_V2_NONDISRUPTIVE_POST_REBOOT_ACCEPTANCE_SOURCE_AND_CI_REVIEW_20261020_01
```

## 首轮远端反馈与夹具修订

- 首次源码归档 commit `d82a428b364143b1aaaf585e16a0f6b190a5e759`，tree `b3c9949b4663d10b1fccf4ffe165e73532491f82`，与本地候选树完全一致。命令行推送缺少凭据，使用已连接 GitHub API 原子更新分支；不复制或搜索认证秘密。
- F5 source CI [39437492081](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/39437492081)：R1/R2/R3 PASS；隔离 MQTT 的新路径测试 PASS，两个旧路径断开测试因预期过窄 FAIL。实际收到合法的 `e0 01 8e`（Session Taken Over），测试此前只认带显式零属性长度的长一字节形式。夹具改为按 MQTT 包长度读取，并接受这两种合法 0x8e 表示；产品负向 CONNACK 校验没有放宽。
- Public safety [39437491606](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/39437491606)：假日志中的私网示例地址命中规则；改为文档专用地址，未修改扫描规则/例外清单。该地址是测试合成值，不是目标信息。
- 此次修订只有两个测试文件和本记录；无产品源码变动。新提交 CI 待复核。上述失败不冒充实机或产品失败。
