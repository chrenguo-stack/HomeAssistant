# N3W T1 F5 V2 exact release inputs producer source repair — 2026-10-20

## 0. Gate

~~~text
TASK=N3W_T1_F5_V2_EXACT_RELEASE_INPUTS_PRODUCER_SOURCE_REPAIR_20261020_01
RESULT=SOURCE_REPAIR_IMPLEMENTED_CI_PENDING

BASE_MAIN=4a1d58d240530b9e2dba249643915caf55948faf
BASE_TREE=1501a013232397e6d896a631b694135d786f908b
SOURCE_BRANCH=fix/n3w-t1-f5-v2-exact-release-inputs-producer-20261020
SOURCE_PR=626

PREVIOUS_BLOCKER=EXACT_MAIN_RELEASE_INPUT_ARTIFACT_PRODUCTION_PATH_MISSING
PREVIOUS_BUILD_READY=false

SOURCE_REPAIR_ONLY=true
EXACT_PRODUCTION_RELEASE_BUILD_EXECUTED=false
T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
~~~

## 1. 问题

F5 V2 已经有：

- exact production release workflow；
- release builder；
- exact-main、source tree、artifact set 和 hash/size 校验。

但正式 release workflow 需要一个：

~~~text
n3w-t1-f5-v2-release-inputs-<exact-main-sha>
~~~

作为输入，仓库中此前没有生产路径负责生成这个 artifact。

因此生产 release 的“消费者”已经存在，但“生产输入生成者”缺失。直接触发 release workflow 只会因为缺少合法输入而失败。

## 2. 修补后的链路

本修补把缺失的一段补齐：

~~~text
exact merged main
-> exact-main F3 deployable payload
-> exact-main F4 control + reboot control packages
-> exact V2 release-inputs producer
-> reviewed release-inputs artifact
-> exact production release workflow
~~~

最后一步仍属于后续独立 gate，本 gate 不执行。

## 3. 新增 release profile

新增：

~~~text
infra/n3w-t1/production/f5-v2-release-profile.json
~~~

用于冻结不应由 workflow 临时猜测的生产 release 输入：

- Standard Fresh Armbian OS/board/architecture；
- exact docker.io package version；
- exact docker-compose-v2 package version；
- apt source policy；
- public evidence field allowlist。

profile 本身进入 Git，因此会和 exact main source tree 一起被冻结。

## 4. 新增 exact release-inputs builder

新增：

~~~text
tools/n3w_t1_f5_v2_release_inputs_builder.py
tests/tools/test_n3w_t1_f5_v2_release_inputs_builder.py
~~~

builder 只做本地 artifact 验证和重新打包，不访问 T1。

它要求并验证：

~~~text
f3_payload
f3_image
f4_control
reboot_control
v2_mac_tools
transport_contract
~~~

并验证：

- exact source head/tree；
- production authority 时 origin/main 必须等于 source head；
- F3 artifact 文件集合；
- F3 runtime payload、payload manifest、executor、host wrapper、host baseline、capacity sidecar；
- 三个 ARM64 image tar 的 hash/size；
- F3 transport/capacity/source binding；
- F4 control artifact、report、inner manifest source binding；
- reboot control artifact、report、inner manifest source binding；
- secret / service-start / board safety boundary；
- V2 Mac tool exact file set；
- 最终 release-inputs 可重新计算为合法 V2 release contract。

## 5. 新增 producer workflow

新增：

~~~text
.github/workflows/n3w-t1-f5-v2-release-inputs-ci.yml
~~~

该 workflow 仅允许人工触发，不在 PR 或普通 push 自动生产 release inputs。

运行时必须提供：

~~~text
f3_run_id
f4_run_id
~~~

并 fail-closed 验证：

- 当前 checkout 就是 exact current main；
- F3 run 来自固定 F3 workflow；
- F4 run 来自固定 F4 workflow；
- 两个 run 的 head 都等于当前 exact main；
- branch 都是 main；
- run 已 completed / success；
- exact F3/F4/reboot artifact 名各只有一个且未过期；
- 下载内容通过 release-inputs builder 完整验证。

最终只上传：

~~~text
n3w-t1-f5-v2-release-inputs-<exact-main-sha>
~~~

并在上传后重新下载和验证。

## 6. 上游 artifact 可生成性

F4 exact control workflow 原本已经支持 manual dispatch。

本修补给：

~~~text
.github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml
~~~

增加 manual dispatch，因此在 source repair 合并后，可以从同一个 exact main 重新生成 F3 artifact。

这一步只构建 GitHub artifact，不访问 T1、不启动生产服务。

## 7. 下游 release provenance 收紧

现有：

~~~text
.github/workflows/n3w-t1-f5-v2-exact-production-release-ci.yml
~~~

现在不再接受“任意 successful workflow 只要碰巧生成同名 artifact”。

它要求 release-inputs run 必须来自：

~~~text
.github/workflows/n3w-t1-f5-v2-release-inputs-ci.yml
event=workflow_dispatch
head_sha=current exact main
head_branch=main
status=completed
conclusion=success
~~~

因此 producer 身份也成为 production release provenance 的一部分。

## 8. CI 回归保护

N3W T1 F5 V2 source CI 已加入：

- release-inputs builder 编译；
- focused unit tests；
- producer workflow manual-only 检查；
- F3 workflow manual-dispatch 可用性检查；
- exact release consumer -> producer path binding；
- release profile schema；
- 六类冻结 artifact 名称和 production-main fail-closed 检查。

## 9. 安全边界

~~~text
REPOSITORY_SOURCE_MUTATION=true
GITHUB_ARTIFACT_PRODUCTION=false
EXACT_PRODUCTION_RELEASE_BUILD_EXECUTED=false

T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
~~~

本 source repair 不授权：

- F3 exact-main artifact 构建；
- F4 exact-main artifact 构建；
- release-inputs artifact 正式生成；
- exact production release build；
- T1 qualification；
- T1 live deployment。

## 10. 当前停止点

~~~text
SOURCE_REPAIR_IMPLEMENTED=true
SOURCE_CI=PENDING
SOURCE_REVIEW=PENDING
MERGE=false

NEXT_ONE_GATE=
N3W_T1_F5_V2_EXACT_RELEASE_INPUTS_PRODUCER_SOURCE_REPAIR_CI_REVIEW_20261020_01

AUTO_EXECUTE_NEXT_GATE=false
STOP=true
~~~
