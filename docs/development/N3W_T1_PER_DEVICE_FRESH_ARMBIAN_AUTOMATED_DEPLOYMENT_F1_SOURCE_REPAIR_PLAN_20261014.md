# N3-W T1 逐台 fresh Armbian 自动产品部署 F1 源码修复计划

TASK=`N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F1_INSTALLER_AND_TRANSPORT_SOURCE_REPAIR_20261014_01`

## 0. Entry

```text
F0_CLOSURE_HEAD=4396bb9e1661c3f2c10a742a37d485cd38a18d5e
F0_POST_CLOSURE_CI=27_SUCCESS_0_FAILURE_0_PENDING
PR_541=OPEN_DRAFT_UNMERGED
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

F1 采用两段式源码修复，避免把 host baseline、provisioning policy、systemd activation
boundary 和 transport v2 一次性混成一个不可审查的大提交。

## 1. F1A

```text
F1A=FRESH_HOST_BASELINE_PROVISIONING_AND_ACTIVATION_BOUNDARY_SOURCE_REPAIR
```

本提交：

1. 增加 repository-owned fresh Armbian Docker Engine + Compose baseline checker/installer；
2. Docker 安装从 Ubuntu apt 当前 candidate 解析 exact package version，并以 package=version 安装；
3. 只启用 Docker，不拥有 Broker/Manager/HA 启动权限；
4. 将 explicit provisioning 的 clone-only preflight 改为 fresh-host/release readiness；
5. 保留用户显式命令语义：
   `sudo n3w-t1-provision start --confirm "START DEVICE PROVISIONING: YES"`；
6. 增加 fresh F3 staged-systemd installer，只 enable ingress guard + provisioning resume，
   显式 disable production activation units；
7. 增加独立 production activation enable helper，供未来 F4 使用；
8. 保留历史 persistence installer，不改写既有历史 acceptance authority。

F1A 不访问 T1，不安装 Docker，不启动生产服务。

## 2. F1B

F1A CI/review PASS 后进入：

```text
F1B=ONE_IMAGE_AT_A_TIME_TRANSPORT_V2_AND_REAL_PROVISION_HOST_WIRING
```

F1B 负责：

- transport schema /2；
- runtime-only payload + three separately bound image tar files；
- small capacity sidecar；
- authorization claim before first docker load；
- one-image transfer -> SHA verify -> load -> runtime binding -> tar delete -> free-space recheck；
- remove Golden Master from active fresh artifact/call path；
- real installable `n3w-t1-provision` host adapter and `resume-if-needed` wiring；
- F3 stopped boundary postcheck。

## 3. Stop

```text
AUTO_EXECUTE_F1B=false
STOP_AFTER_F1A_CI_AND_FOCUSED_REVIEW=true
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```
