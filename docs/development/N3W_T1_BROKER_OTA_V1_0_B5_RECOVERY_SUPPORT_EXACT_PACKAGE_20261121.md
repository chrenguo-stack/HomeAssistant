# N3-W T1 Broker OTA V1.0 — B5 Recovery Support Exact Package

DATE=2026-11-21  
STATUS=CLOSED_PASS  
STACKED_BASE_PR=818  
STACKED_BASE_HEAD=b5716c7899755338f4ab1cae62c57dd7495c9924  
B4_STATUS=CLOSED_PASS  
PRODUCT_AUTHORITY=T1_Core_Stack_OTA_V1.2  
T1_ACCESS=false  
PRODUCTION_MUTATION=false  
MERGE=false  

## 1. 目标

B3/B4 已经证明 Broker Recovery Point、自动接管与终态生命周期。

B5 的职责不是构建 Broker 目标镜像，而是把这些恢复能力封装成一个可复现、可验证、可安装的宿主 exact package：

```text
Broker recovery support package
├ t1-core-updater.pyz
├ n3wfc4-core-updater-broker-recovery.service
└ manifest.json
```

它解决“仓库里有源码，但真实 T1 开机时没有固定可执行恢复引擎”的交付缺口。

## 2. exact updater pyz

pyz 由 exact `source_head` 的 Git blobs 构建，不从未绑定工作区复制源码。

模块集合冻结为 Generic V2 运行所需模块，并明确包含：

```text
n3w_t1_core_updater_broker_recovery.py
```

构建使用固定 ZIP 时间戳和固定文件集合，重复构建应产生相同 pyz bytes 和相同 manifest digest。

pyz 固定安装路径：

```text
/opt/n3w-t1-core-updater/t1-core-updater.pyz
```

该路径与 B4 systemd unit 的 ExecStart 一致。

## 3. package manifest

`manifest.json` 绑定：

- exact source head；
- pyz SHA256 / size / install mode / install path；
- recovery unit SHA256 / size / install mode / install path；
- exact pyz module set；
- `t1_access=false`；
- `production_service_start=false`；
- `board_access=false`。

package file set 必须恰好为 3 个文件，额外文件和缺失文件都 fail closed。

## 4. 安装模拟合同

B5 提供可注入 root/systemctl 的安装原语，但不在真实 T1 执行。

固定目标：

```text
/opt/n3w-t1-core-updater/t1-core-updater.pyz
/etc/systemd/system/n3wfc4-core-updater-broker-recovery.service
```

第一次安装：

1. 验证 package manifest digest；
2. 验证 exact pyz 和 unit；
3. 验证目标父目录和现有目标状态；
4. 原子发布文件并 fsync；
5. `systemctl daemon-reload`；
6. 仅执行 `systemctl enable n3wfc4-core-updater-broker-recovery.service`；
7. 验证 enabled；
8. 验证 unit 没有被 start。

明确禁止：

```text
enable --now
start
stop
restart
Broker/Manager/Home Assistant runtime mutation
```

## 5. 幂等与失败回滚

- 两个目标均为 exact bytes/mode 时允许重复安装；
- 任一目标漂移立即 STOP；
- 只存在一个目标视为 partial state，STOP；
- unit 已 active 时 STOP；
- 首次安装若 enable 或后续验证失败，删除本次新建文件、撤销本次 enable、daemon-reload；
- 已存在 exact 安装不因重复运行改写文件。

## 6. CI authority

新增：

```text
.github/workflows/n3w-t1-core-updater-broker-recovery-support-ci.yml
```

分类：

```text
class=EXACT
draft_policy=run
```

同阶段完成：

- `N3W_CI_POLICY_MANIFEST_V1.json` 注册；
- fast-source exact closure trigger 注册；
- dedicated CI governance contract test；
- exact artifact upload；
- re-download 后再次 verify；
- re-downloaded pyz 实际执行 `--help` 并证明存在 `recover-broker-pending`。

## 7. 本阶段不做

```text
Broker target image build=false
Broker A->B target manifest=false
T1 package install=false
systemd live enable=false
real reboot=false
real Broker downtime=false
merge=false
release=false
```

B5 通过后，下一阶段才进入 Broker 目标镜像/target manifest 与 isolated Mosquitto A→B package simulation。


## 8. B5 closure

```text
B5_STATUS=CLOSED_PASS
B5_EXECUTABLE_HEAD=e650f5db373d5cd65fd601c676f3f605998ba132
B5_EXACT_HEAD_CI=14/14_SUCCESS
B5_EXACT_RUN=44914839856

B5_ARTIFACT_ID=14711625754
B5_ARTIFACT_NAME=n3w-t1-core-updater-broker-recovery-support
B5_ARTIFACT_DIGEST=sha256:77f440f3da068dca61d5f12b44fb704ca29690a16be0a95322024657beadf949
B5_ARTIFACT_SIZE_BYTES=254039
B5_MANIFEST_SHA256=092af89974e3ce0584933e18a10288386ce5ff8cfddd2c36a19c66e67f142cf2
B5_UPDATER_SHA256=5a13a910cdfdb4d07b23fb7bd8c5bac1bb31a59a310787e4dd2dbf617df7dd4a
B5_UNIT_SHA256=d5bea0c625edfcf46729170eac30872ae8a11c59fce14c89c6c585d46438ce19

T1_ACCESS=false
PRODUCTION_MUTATION=false
SYSTEMD_LIVE_ENABLE=false
BROKER_TARGET_IMAGE=false
BROKER_LIVE_APPLY=false
MERGE=false
RELEASE=false
```

The dedicated exact workflow built the package from the exact Git source head, uploaded it, re-downloaded it, re-verified the manifest/module set and executed the packaged pyz to prove the `recover-broker-pending` command is present. The earlier B5 CI-policy failure was limited to a stale repository workflow-count assertion (84 -> 85); the policy checker itself had `errors=[]`. Repair head `e650f5d...` added the explicit workflow registration assertion and all 14 exact-head workflows then succeeded.

B5 closes only the host recovery-support packaging foundation. The Broker target release/image and target manifest remain unfrozen. The next source stage is target-image/manifest work plus isolated Mosquitto A-to-B deterministic package simulation; no T1 access or live systemd/Broker mutation is implied.
