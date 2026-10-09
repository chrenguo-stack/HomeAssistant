# N3-W P4 T1 Fresh Manager — One-shot Source Review and Failure-Recovery Closure (2026-10-09)

## 1. Exact authority and scope

```text
TASK=N3W_P4_T1_FRESH_MANAGER_ONE_SHOT_DEPLOY_EXECUTOR_AND_ROLLBACK_TEST
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR540=OPEN_DRAFT
EXACT_CODE_REVIEW_HEAD=e077f952a7b1ec124de7c6c2031f653dcb4e977c
CANDIDATE_SOURCE=3d86d6bfaf361dc3a3d7295d046f541a544d552d
LIVE_MANAGER_REPLACEMENT_AUTHORIZED=false
T1_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

本轮是 source-only 实现与独立源码复核。交接文档开头的「完整执行器尚未实现」是历史冻结点；PR #540 在交接后继续推进，当前已经包含执行器、独立救援、systemd 单次监督、operator 和模拟测试。Review 绑定上述 **代码** HEAD；此文档及 CURRENT_STATE 归档提交会推进 PR HEAD，不改变已复核代码。

## 2. 冻结的产品决定

- 旧设备在旧 Manager 内的历史配对关系由用户明确放弃，不能在新 Manager 恢复。
- 新 Manager 是 **Manager-only fresh business state**：三块独立新空白 RW 持久源，注册/credential/replay 三种业务计数预启动要求 0/0/0，relay-keys 空。不能复用历史五身份 baseline。
- T1、Broker、TLS、网络、system identity 和 Manager 服务侧已有 secret 只读挂载保持；不清空 Broker DynSec、retained、HA 历史。
- 原 Manager container、原始三 RW 来源及历史 R5 root-private backup 必须保留；旧 Compose 三挂载不是重建权威。当前 **live Docker inspect 六挂载**和原容器 ID/镜像是唯一运行态基准。
- R5 原 Manager 冷备份、隔离恢复和原版恢复已实机 CLOSED_PASS。本门不重新执行。ESP32-C6 已断电且不带传感器，不做无发送端的 90 秒 telemetry 等待。

## 3. 实际审查范围

```text
ENTRY=fresh_manager_operator.py
TRANSACTION=fresh_manager_deploy.py
RESCUE=fresh_manager_recovery.py
SYSTEMD=fresh_manager_systemd_unit.py
RUNTIME_PARITY=cutover_contract.py
FRESH_STATE=fresh_state_contract.py
TEST_FILES=test_fresh_manager_deploy.py,test_fresh_manager_recovery.py,test_fresh_manager_operator.py,test_cutover_contract.py,test_fresh_state_contract.py
```

当前实现的单次正常顺序为：

1. 旧 Manager 和 Broker 身份、候选不可变 image ID、旧 R5 私有 rollback authority、六挂载、服务网络/安全参数、用户权限等检查。
2. 创建三个独立、所有权符合运行 UID/GID 的 **空白** RW 目录，不复制原数据库；三个旧 RO secret source 维持只读。
3. 创建不启动的 shadow Manager，比较新旧运行配置及挂载；任何不一致均在原 Manager 停止之前 STOP。
4. 建立 root-private 0600 事务记录（原容器、候选镜像、Broker 身份、阶段），原 Manager 停止并仅改名保留。
5. 从当前真实 Docker inspect 生成候选 create args，严格保持六挂载；新 Manager 先以 restart=no 启动、通过健康/配对 socket/P4 CLI/TLS 8883 TCP 和空白 SQLite/relay key 检查。
6. 每次容器创建后立即持久化新容器真实 ID，再继续运行态比较；成功才更新 restart policy 并记录 committed，监督收尾再次确认。
7. 任一步失败由 systemd ExecStopPost 在仍具备 Docker/systemd 条件下尝试：核验候选身份、停止候选、移走候选名称、还原 parked 原容器名称和原 RW 数据源，验证原容器与 Broker。失败现场和新数据源保留供 root-private 取证，不自动第二次尝试。

## 4. 定向发现、修复与回归保护

| 发现 | 修复 | 保护 |
|---|---|---|
| 新测试夹具缺少原容器 ID / 8883 环境，导致 10 项 synthetic ERROR | 补充合成 inspect 身份及正确端口 | 真实可用的 0/0/0 候选顺序测试 |
| 之前只测 transaction 的注入失败，未充分测 **rollback 实际决策** | 增加候选身份、镜像、parked 原容器、start failure、Broker drift、不同中断窗口的纯模拟测试 | 不误删/误停未知候选，旧 Manager 可恢复时恢复 |
| committed 后至 systemd 最终确认前，候选崩溃可能只报错 | systemd 专属 finalization 失败时撤销本次 commit 并尝试原容器 rollback，再返回 STOP | 新增加速窗口场景验证 |
| 状态文件重命名虽原子，缺少父目录持久化同步 | 临时文件 fsync + 原子 replace + 父目录 fsync | 减少突然掉电时事务记录丢失窗口；不承诺物理断电自动恢复 |
| candidate create 后 ID 尚未可靠存盘时出现后续检查异常 | 在 create 返回 ID 时先写入事务记录，再验证 stopped shadow / candidate 合同 | 回退仅按真实候选容器 ID/immutable image 对象执行 |
| Shadow 比较范围缺少部分 Docker 运行安全字段 | 增补安全参数、网络、restart 细节等校验 | 遇到运行配置漂移，在停旧 Manager 前 fail-closed |

## 5. CI and exact-source review

```text
CI_WORKFLOW=N3W P4 Manager cold backup synthetic tests
CI_RUN_ID=37936241579
CI_RESULT=SUCCESS
SYNTHETIC_TESTS=93_PASS
PUBLIC_REPOSITORY_SAFETY_RUN_ID=37936241468
PUBLIC_REPOSITORY_SAFETY=PASS
EXACT_SOURCE_REVIEW=PASS_SOURCE_ONLY
CURRENT_GATE=CLOSED_PASS_SOURCE_ONLY
```

- 审查了核心事务、独立 recovery、监督 operator、systemd 执行边界和六挂载/空库合同，新增测试对最重要的异常时刻作了专门覆盖。
- GitHub CI 只运行模拟数据、模拟容器状态和静态检查。**没有**在本轮连接 T1、运行真实 Docker create/stop/rename/start、打开板卡或导入任何 secret。
- 当前通过代表「具备申请单次受控生产替换授权的源码基础」，**不是**「T1 新 Manager 已部署」或「P4 首次配对成功」。

## 6. 下一阶段必须现场复核的条件

下一阶段单独获得用户的 **一次性、不可重放的 live production Manager replacement 授权**后，仍必须由一条受监督的 Mac Terminal 指令自动完成：

1. fresh readonly rebind 当前 live Manager/Broker、不可变候选镜像 ID、R5 私有归档、当前六挂载、T1 root-private staging 文件准确版本及权限；
2. 自动核查 Docker/systemd 监督可用及 rollback 原容器可启动条件，禁止旧 Compose 替代；
3. 同一作业完成单次切换、postflight、必要时自动救援；只输出 PASS / STOP 摘要；
4. 仅在 host-side PASS 后停止本轮。不得自动启动板卡、复用旧五身份快照或导入 Setup Secret。

对宿主机断电、Docker 守护进程失效、root-private 文件系统损坏，程序不能承诺百分之百自动恢复，必须保留明确的人工救援路线。Broker 旧设备账号/ACL/retained 信息也仍需未来独立处理，不能宣称 T1 完全恢复出厂。

## 7. Final STOP

```text
NEXT_ONE_GATE=N3W_P4_T1_FRESH_MANAGER_ONE_SHOT_LIVE_DEPLOY
READY_TO_REQUEST_EXPLICIT_LIVE_AUTHORIZATION=true
LIVE_MANAGER_REPLACEMENT_AUTHORIZED=false
P4_FIRST_NORMAL_BOOT_AUTHORIZED=false
P4_SETUP_SECRET_IMPORT_AUTHORIZED=false
R5_BACKUP_REPLAY=false
NO_SENSOR_TELEMETRY_WAIT=false
PR540_MERGE=false
STOP=true
```
