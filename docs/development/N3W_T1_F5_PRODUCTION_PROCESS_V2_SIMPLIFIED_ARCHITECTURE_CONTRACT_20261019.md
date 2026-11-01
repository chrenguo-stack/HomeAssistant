# N3W T1 F5 V2 简化量产路线架构合同 — 2026-10-19

## 0. Gate

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V2_SIMPLIFIED_ARCHITECTURE_CONTRACT_20261019_01
RESULT=DESIGN_CONTRACT_FROZEN_ON_CANDIDATE

BASE_MAIN=9c81b889d97ed896b80d27af15069d16af0e0bdb
BRANCH=design/n3w-t1-f5-v2-fresh-armbian-production-20261019

F5_V1_IMPLEMENTATION_LINE=SUPERSEDED_ARCHIVE_ONLY
F5_V2_NORMAL_START_STATE=STANDARD_FRESH_ARMBIAN
F5_V2_IN_PLACE_RECOVERY=false
F5_V2_REFLASH_ON_NONSTANDARD_OR_FAILED_TARGET=true
F5_V2_FINAL_POST_REBOOT_ACCEPTANCE=MANDATORY

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~

本合同重新收敛 F5 的正常量产路线。ADR-0010 的“逐台官方 Armbian、逐台自动部署、逐台验收”方向保持不变，
但 F5 V1 为兼容复杂历史状态引入的资产分类、UNKNOWN 重入和阶段恢复机制不再进入正常量产路径。

F5 V2 的目标不是“尽量把任意旧 T1 修到可部署”，而是：

> 只接收符合标准的全新 Armbian；自动完成运行环境与产品部署；真实重启；独立验收；
> 验收通过才允许标记为量产合格。

## 1. 顶层路线

~~~text
OFFICIAL_ARMBIAN_INSTALLED
-> EXACT_RELEASE_VALIDATION
-> STANDARD_FRESH_ARMBIAN_QUALIFICATION
-> ONE_PRODUCTION_APPROVAL
-> PRODUCTION_RUN_CLAIM
-> HOST_BASELINE_INSTALL
-> PRODUCT_DEPLOY
-> DEVICE_PROVISION
-> PRODUCT_ACTIVATE_AND_PERSIST
-> ONE_CONTROLLED_REBOOT
-> INDEPENDENT_POST_REBOOT_ACCEPTANCE
-> PRODUCTION_READY
~~~

正常量产不包含 target-local repair、历史 Docker 资产鉴定、旧产品状态迁移或失败现场修补。

## 2. Standard Fresh Armbian 合同

F5 V2 只接受满足全部硬条件的 T1。

### 2.1 身份与平台

~~~text
OS_ID=ubuntu
OS_VERSION=26.04
OS_CODENAME=resolute
ARMBIAN_VERSION=26.05.0
ARMBIAN_BOARD=S912-Phicomm-T1
ARCHITECTURE=arm64
~~~

必须能通过受信 SSH host key 确认目标身份。主机密钥失配直接 STOP。

### 2.2 首启与系统基础

必须同时满足：

- Armbian firstboot 已完成并处于成功终态；
- SSH 可用；
- passwordless sudo -n 可用于受控生产工具；
- NetworkManager 正常；
- IPv4 默认路由存在；
- DNS 可解析；
- NTP 已同步；
- 根文件系统空间达到 release 的最低要求；
- APT 源符合冻结的 Ubuntu resolute/arm64 策略。

### 2.3 “全新”的产品边界

全新 T1 必须不存在以下任何对象：

- N3W / greenhouse / HomeAssistant 产品目录；
- N3W systemd service/timer；
- N3W 生产授权、run ledger、recovery ledger；
- 产品证书、产品秘密、产品数据库；
- 1883/8883/8123/产品专用端口上的既有产品监听；
- 旧 F3/F4/F5 staging 或 production marker。

### 2.4 Docker 规则

F5 V2 将“Docker 尚未由产品安装”作为标准 fresh baseline：

~~~text
DOCKER_ENGINE_INSTALLED=false
DOCKER_PRODUCT_OBJECTS=NONE
~~~

如官方 Armbian 镜像未来改变并预装 Docker，必须通过新的架构修订显式改变此合同，不在运行时猜测。

因此正常 F5-8 不再枚举、分类任意 Docker container/image/network/volume，也不再因为“不认识某个对象”补 UNKNOWN 规则。

## 3. Fresh qualification 的结果与处置

exact release 必须先在 Mac 本地验证，因为 release 本身决定允许的 Docker/Compose 版本、容量要求和后续精确绑定。
之后才连接 T1 做 fresh qualification。

target 已被成功观察后的处置只有两类：

~~~text
PASS -> 允许进入量产
FAIL_REFLASH_REQUIRED -> 已证明不符合 Standard Fresh Armbian；不修现场，重新安装官方 Armbian
~~~

如果因为 SSH/网络/取证命令等原因根本无法证明 target 状态，则属于：

~~~text
STOP_UNAVAILABLE -> 没有 target mutation；先修复工位/连接问题，可重新执行只读 qualification
~~~

STOP_UNAVAILABLE 不是第三种 target 状态，也不允许据此进入生产或要求重装。它只表示“证据不足”。

F5 V2 不再尝试判断旧 Docker/历史对象是否“也许可以留着”。

## 4. 生产运行 authority 简化

V1 的逐 phase durable claim 对“失败后现场恢复”有价值，但 V2 正常量产不再支持原地恢复，因此正常路径收敛为一个最小 target run marker。

生产批准后、任何产品 mutation 前，T1 创建一次性 durable run marker，至少绑定：

- run ID；
- release ID / release SHA；
- source head；
- target identity；
- approved plan digest；
- created/started state；
- replay_allowed=false。

状态只需要：

~~~text
STARTED
ACCEPTED
~~~

任何 production mutation 之后发生失败、断线、UNKNOWN 或进程崩溃：

~~~text
TARGET_RESULT=NOT_ACCEPTED
REUSE_TARGET_WITHOUT_REFLASH=false
REPLAY_RUN=false
~~~

不需要在目标上继续建立复杂 phase recovery 状态机。

但“一个人工生产批准”不等于删除所有内部一次性安全守卫。现有 F3/F4 已验证的 transaction、no-replay、atomic claim 等内部保护可以继续保留，由 V2 orchestrator 根据同一个 top-level run 自动派生内部 action/authorization ID。正常操作员不会再次批准，也不会看到 repair 入口。

## 5. 失败政策

### 5.1 qualification 前失败

没有生产 mutation：

- 修复生产工位连接问题可以重试；
- T1 不满足 fresh contract，则重装 Armbian；
- 不创建产品 run。

### 5.2 run STARTED 且尚未 ACCEPTED 时任意失败

V2 冻结如下硬顺序：

~~~text
FAIL
-> FREEZE_EVIDENCE
-> FORENSIC_SNAPSHOT_COMPLETE
-> SESSION_CLOSE
-> TARGET_MARKED_REFLASH_REQUIRED
-> REFLASH_ALLOWED
~~~

具体规则：

1. 立即停止正常生产流程和所有后继 mutation；
2. 先冻结 Mac 本地 run/event/error 状态，禁止后续步骤覆盖原始失败事实；
3. 在仍然可用的当前 SSH epoch 内，只读采集 forensic snapshot；
4. 生成固定格式的 failure-summary、evidence manifest 和 bundle SHA-256；
5. 完成 managed SSH session cleanup/close，并证明没有遗留本 run 的连接资源；
6. 仅在上述步骤完成后，在 Mac 生产台账中把该 target/run 标记为 REFLASH_REQUIRED；
7. 此时才允许重新安装官方 Armbian；
8. 同一个 run 永不 replay；重装后的目标必须重新通过 fresh qualification，并建立全新的 run。

~~~text
FAILURE_FORENSIC_SNAPSHOT_REQUIRED=true
REFLASH_BEFORE_FORENSIC_SNAPSHOT=false
TARGET_LOCAL_REPAIR_BEFORE_REFLASH=false
REPLAY_RUN=false
~~~

FORENSIC_SNAPSHOT_COMPLETE 表示取证流程已经完成并形成不可歧义的 manifest，而不是假定每个远端 probe 都成功。
如果 T1 已断线或某项只读 probe 无法执行，必须把该项记录为 UNAVAILABLE/失败原因并进入 manifest；不得伪造 PASS，
也不得因为目标不可达而永久阻塞后续重装。

TARGET_MARKED_REFLASH_REQUIRED 是 Mac 侧生产台账/结果状态，不要求在即将被重装的 T1 上再写一个额外 repair marker。
T1 上原有 STARTED marker 保持原样作为失败现场的一部分，直到重装擦除。

SESSION_CLOSE 的完成条件允许两种等价结果：managed SSH/ControlMaster 被正常关闭，或已经确认该连接资源不存在。目标掉线本身不能造成“永远不允许重装”的死锁。

### 5.3 durable ACCEPTED 之后的 process-only failure

如果 post-reboot acceptance 已 PASS，并且 target marker 已经原子写成 ACCEPTED，之后仅发生 Mac 侧 session cleanup、public result 生成或本地归档失败，则：

~~~text
DEVICE_ACCEPTANCE=PASS
T1_PRODUCTION_READY=true
OVERALL_PROCESS=FAIL
REFLASH_REQUIRED=false
~~~

此时不得为了修复生产工位证据问题而重装一台已经被 durable acceptance 证明合格的 T1。后续只允许只读 inspect/evidence-finalization，不允许重新执行产品 mutation。

### 5.3 外部持久状态

如果未来引入工厂注册表、云端设备登记、外部 CA/证书签发或其他 T1 重装不能消除的外部状态，
必须单独定义 revoke/close 事务。该事务不允许被“重刷 T1”隐式代替。

当前首版 F5 V2 不假设存在这类外部平台。

## 6. Release-bound host baseline and production deployment

HOST_BASELINE 的 Docker/Compose 安装版本必须来自当前 exact release contract，而不是“运行当天 APT 的最新 candidate”。

~~~text
APT_CANDIDATE_MUST_EQUAL_RELEASE_VERSION=true
PACKAGE_VERSION_DRIFT=STOP_BEFORE_INSTALL
SILENT_LATEST_UPGRADE=false
~~~

release 中至少绑定 docker.io、docker-compose-v2 的准确 Ubuntu package version 与 source policy。如 exact version 不可取得，构建新 release；不得在现场自动放宽。

### 6.1 Production deployment

量产主体只做固定顺序：

~~~text
RUN_START
HOST_BASELINE
F3_PRODUCT_DEPLOY
PROVISION
F4_ACTIVATE
PERSISTENCE_AND_CERTIFICATE
REBOOT
FINAL_ACCEPTANCE
RUN_ACCEPTED
~~~

要求：

- 一次生产批准；
- 重启前一个 SSH connection epoch；
- 重启后一个 SSH connection epoch；
- 每个 epoch 最多一次密码认证；
- exact release bytes；
- normal path 不暴露 repair 命令；
- 不允许 operator 跳过阶段；
- 不允许 global force/override。

## 7. 最终验收是量产裁决，不是附加检查

部署程序正常返回不能直接得到 Production PASS。

唯一正式成功条件：

~~~text
POST_REBOOT_PRODUCTION_ACCEPTANCE=PASS
T1_PRODUCTION_READY=true
~~~

验收必须在真实重启之后从一个新的 SSH epoch 执行，并尽量使用外部可观察结果，而不是仅相信部署阶段自己的 success report。

现有已实机验收的 n3w_t1_f4_reboot_verify.py 继续作为 target-local acceptance 核心，不在 V2 重写同一套 Docker/systemd/TLS/Manager/Home Assistant/certificate 检查。V2 只在其外层增加 run-marker/release 绑定、Mac 外部探测和 90 秒稳定观察。

### 7.1 必验项目

#### 主机与 release

- 目标 host key / target identity 与本次 run 一致；
- boot identity 已变化，证明真实重启；
- OS/arch 仍满足合同；
- installed release ID/source head 与本次批准 release 完全一致；
- production run marker 为 STARTED，且与当前 target/release/run 一致。

#### Docker / systemd

- Docker Engine/Compose 为批准版本；
- Broker、Home Assistant、Manager 对应 exact images；
- 预期 containers 正在运行；
- 不存在未知 N3W 产品 container；
- systemd persistence 已启用；
- 关键服务无 crash/restart loop。

#### Broker / TLS / credentials

- TLS listener 可从 Mac 侧真实建立连接；
- 只信任 Broker CA `/etc/n3wfc4/tls/ca.pem`，固定校验 `armbian` 的 hostname/SNI；不得使用独立的 system CA 或关闭验证；
- 目标机上的 Manager / Home Assistant 自身已认证连接；以 F4 完整验证、精确身份的 Broker 认证日志、服务进程持有的预期端口连接共同证明；
- Mac 不得使用生产用户名、密码、ClientID 正向登录，不导出生产密码；
- 独立随机、非生产身份的错误凭据必须收到有效 MQTT 5 CONNACK 认证拒绝（0x86/0x87）；TLS 失败、超时、忙碌或协议错误不能冒充拒绝；
- 必需 ACL/Dynamic Security 状态有效。

#### Manager / Home Assistant

- Manager 进程健康；
- Home Assistant HTTP readiness 通过；
- MQTT integration 状态正确；
- 不产生重复 integration/device bootstrap；
- 基础业务状态能够读取。

#### persistence / certificate

- reboot 后 Broker/Manager/Home Assistant 自动恢复；
- 证书身份未因 reboot 异常重建；
- certificate lifecycle timer/service 状态符合产品合同；
- 持久化目录与权限符合规范。

#### 稳定观察

在最终验收窗口内不得出现：

- container 重启循环；
- systemd 单元反复失败；
- Broker/Manager/HA readiness 抖动；
- 新的关键错误状态。

观察窗口固定为外部探测完成后的 90 秒，不另加第二个 90 秒窗口。外部探测开始前建立只读基线，每个探测后检查连接与事件连续性；最终窗口每次采样后最多等待 2 秒，完成样本间隔不得超过 15 秒，覆盖不足即失败。采样包含容器 ID/StartedAt/restart count、服务持有的连接指纹、Broker 身份连接事件摘要、HA `/api/` 就绪状态、关键 systemd 状态及新增高优先级错误。健康的证书 oneshot 周期切换允许，失败不允许。任何失败立即停止且不可由后续恢复冲销。

有限采样不承诺捕获每一个瞬时 HTTP 抖动；MQTT 重连另用连接事件累计摘要捕捉。日志缺失/截断属于证据不足，不能宣布产品故障或验收通过。结果使用 acceptance `/2`，分别记录 `external_probes` 与 `runtime_service_auth`，绑定 run/release/boot/control manifest 和观察摘要；旧 `/1` 结果不能升级解释为本合同已通过。

本节由 2026-10-20 非扰动修复门修订，详见：`N3W_T1_F5_V2_NONDISRUPTIVE_POST_REBOOT_ACCEPTANCE_SOURCE_REPAIR_20261020.md`。

### 7.2 最终输出

最终公共结果至少包含：

~~~text
FINAL_OUTCOME=PASS|FAIL
T1_PRODUCTION_READY=true|false
RELEASE_ID=<sha256>
SOURCE_HEAD=<git-sha>
TARGET_BINDING_SHA256=<sha256>
SSH_HOST_KEY_SHA256=<sha256>
BOOT_CHANGED=true|false
POST_REBOOT_ACCEPTANCE=PASS|FAIL
SESSION_CLOSED=true|false
BOARD_ACCESS=false
~~~

只有 PASS 才把 target run marker 原子更新为 ACCEPTED。

## 8. Failure forensic snapshot

每次 run STARTED 之后的失败都必须产生最小、稳定、可追查的只读取证包。至少记录：

- run_id、release_id、release_sha256、source_head；
- target_binding_sha256、ssh_host_key_sha256；
- failed_stage、last_success_stage、error_code；
- mutation_started、reboot_executed、post_reboot_acceptance_started；
- pre/post boot identity（若可取得）；
- production marker 状态及 hash；
- Docker containers/images 的只读摘要与关键 restart count；
- 关键 systemd unit 状态；
- 关键监听端口/进程摘要；
- 与失败阶段直接相关的有限日志尾部；
- 关键产品文件/manifest/hash 的只读绑定；
- 每个无法取得的 probe 的显式 UNAVAILABLE 原因；
- evidence manifest SHA-256 与整个 bundle SHA-256；
- session close 结果；
- final target disposition = REFLASH_REQUIRED。

详细原件只保存在生产 Mac 私有 evidence root。GitHub/public result 只保存允许公开的 hash、布尔值、阶段、错误码和关系结果，
不得上传密码、私钥、MQTT 明文凭据、原始私有地址或 unrestricted stdout/stderr。

该 forensic snapshot 只用于定位源码/环境/运行问题，不承担恢复、修复或继续执行职责。

## 9. V2 不做的事情

正常量产明确不做：

- 旧 Docker object ownership 推断；
- 旧产品状态修复；
- 失败后 phase replay；
- UNKNOWN -> 自动新 run；
- target-local source patch；
- Docker prune；
- 删除不明目录/卷/网络；
- 为通过量产而临时放宽检查；
- 无验收直接标记 ready；
- ESP32 板卡验收。

## 10. 对现有 F3/F4 的处理

已有 F3、Provisioning、F4 的业务能力和历史实机证据不因 V2 失效。

但它们在 V2 正常量产中的“授权/恢复包装层”允许重新收敛：

~~~text
KEEP_BUSINESS_PRIMITIVES=true
KEEP_ACCEPTED_RUNTIME_BEHAVIOR=true
REUSE_V1_PHASE_RECOVERY_AUTHORITY=false
NORMAL_PATH_TARGET_REPAIR=false
~~~

V2 source design 应优先复用其业务函数与验收逻辑，删除为旧 phase-recovery 状态机服务的耦合，而不是重写 Broker、Manager、HA 业务逻辑。

## 11. 验收和开发边界

V2 源码在进入真实 T1 之前，必须完成：

1. fresh Armbian qualification 单元/负向测试；
2. run marker crash/replay 测试；
3. exact release/package binding；
4. HOST_BASELINE -> F3 -> Provision -> F4 的打包调用链测试；
5. reboot 前后模拟；
6. post-reboot acceptance 行为测试；
7. failure forensic snapshot 与“先取证后重装”顺序测试；
8. public/private evidence 扫描；
9. isolated Linux 端到端测试。

最后使用重新安装的 fresh T1-B 做一次真实完整 V2 验收。

## 12. 当前 T1-B

当前 T1-B 已经经历 V1 历史生产尝试与 HOST_BASELINE，因此不再作为 V2 的 Standard Fresh Armbian 基线。

V2 实机验收前：

~~~text
T1_B_REFLASH_REQUIRED=true
REUSE_CURRENT_T1B_STATE=false
~~~

该要求不是“修复当前 inventory UNKNOWN”，而是 V2 新鲜基线合同的直接结果。

## 13. 关闭条件

F5 V2 关闭必须同时满足：

~~~text
SOURCE_REVIEW=PASS
CI=PASS
EXACT_RELEASE=PASS
STANDARD_FRESH_ARMBIAN_QUALIFICATION=PASS
REAL_T1_FULL_DEPLOYMENT=PASS
REAL_REBOOT=PASS
POST_REBOOT_PRODUCTION_ACCEPTANCE=PASS
T1_PRODUCTION_READY=true
REPOSITORY_CONVERGENCE=PASS
~~~

## 14. 下一步

本合同之后进入 V2 source design。不得继续修补 V1 inventory UNKNOWN 正常路径。

~~~text
NEXT_ONE_GATE=N3W_T1_F5_PRODUCTION_PROCESS_V2_SOURCE_DESIGN_20261019_01
AUTO_EXECUTE_PRODUCT_SOURCE=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
STOP=true
~~~
