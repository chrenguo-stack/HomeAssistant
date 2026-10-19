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
-> STANDARD_FRESH_ARMBIAN_QUALIFICATION
-> EXACT_RELEASE_VALIDATION
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

## 3. Fresh qualification 的结果只有两类

~~~text
PASS -> 允许进入量产
FAIL -> 不修现场；重新安装官方 Armbian 后重新检查
~~~

没有第三类“尝试判断这个旧对象是不是可以留着”。

F5 V2 仍可以输出具体失败原因，方便定位镜像、网络、磁盘或硬件问题，但这些原因不改变生产政策。

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

## 5. 失败政策

### 5.1 qualification 前失败

没有生产 mutation：

- 修复生产工位连接问题可以重试；
- T1 不满足 fresh contract，则重装 Armbian；
- 不创建产品 run。

### 5.2 run STARTED 之后任意失败

一律：

1. 停止正常生产流程；
2. Mac 保存失败/UNKNOWN 证据；
3. 不做 target-local repair；
4. 不 replay 同一个 run；
5. 如需要再次生产该 T1，重装官方 Armbian；
6. 重新通过 fresh qualification；
7. 建立全新的 run。

### 5.3 外部持久状态

如果未来引入工厂注册表、云端设备登记、外部 CA/证书签发或其他 T1 重装不能消除的外部状态，
必须单独定义 revoke/close 事务。该事务不允许被“重刷 T1”隐式代替。

当前首版 F5 V2 不假设存在这类外部平台。

## 6. Production deployment

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
- CA、server certificate、hostname/SNI 合同通过；
- Manager 可认证连接；
- Home Assistant 可认证连接；
- 错误凭据被拒绝；
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

首版建议观察窗口为 90 秒。若后续证据表明不足，再以独立变更调整，不默认扩展成长 soak。

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

## 8. V2 不做的事情

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

## 9. 对现有 F3/F4 的处理

已有 F3、Provisioning、F4 的业务能力和历史实机证据不因 V2 失效。

但它们在 V2 正常量产中的“授权/恢复包装层”允许重新收敛：

~~~text
KEEP_BUSINESS_PRIMITIVES=true
KEEP_ACCEPTED_RUNTIME_BEHAVIOR=true
REUSE_V1_PHASE_RECOVERY_AUTHORITY=false
NORMAL_PATH_TARGET_REPAIR=false
~~~

V2 source design 应优先复用其业务函数与验收逻辑，删除为旧 phase-recovery 状态机服务的耦合，而不是重写 Broker、Manager、HA 业务逻辑。

## 10. 验收和开发边界

V2 源码在进入真实 T1 之前，必须完成：

1. fresh Armbian qualification 单元/负向测试；
2. run marker crash/replay 测试；
3. exact release/package binding；
4. HOST_BASELINE -> F3 -> Provision -> F4 的打包调用链测试；
5. reboot 前后模拟；
6. post-reboot acceptance 行为测试；
7. public/private evidence 扫描；
8. isolated Linux 端到端测试。

最后使用重新安装的 fresh T1-B 做一次真实完整 V2 验收。

## 11. 当前 T1-B

当前 T1-B 已经经历 V1 历史生产尝试与 HOST_BASELINE，因此不再作为 V2 的 Standard Fresh Armbian 基线。

V2 实机验收前：

~~~text
T1_B_REFLASH_REQUIRED=true
REUSE_CURRENT_T1B_STATE=false
~~~

该要求不是“修复当前 inventory UNKNOWN”，而是 V2 新鲜基线合同的直接结果。

## 12. 关闭条件

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

## 13. 下一步

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
