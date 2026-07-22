# H3/N2 Stage 2D-7—2D-8 G2 汇总集成 D4 审核包

**版本：** V1.0  
**日期：** 2026-07-22  
**PR：** #173  
**状态：** 已完成 Draft 集成验证，等待最终记录提交 CI 与 D4 精确授权

## 1. 集成对象

```text
TARGET_BRANCH=main
MAIN_AT_INTEGRATION_START=dd06eb06c762791999e4cb3bd22c2dac17aa3fd0
INTEGRATION_BRANCH=integration/h3-n2-stage2d8-g2-closure-20260722-v1
UNION_COMMIT=8fa431704e6b506d0bb94d927d65697d1606fee2
VALIDATION_HEAD=7b2770e8611893bda8edebbd0164754625cbe18e
FROZEN_EVIDENCE_HEAD=04562e50147e200fe408c66dee001f25ea1af0b9
FROZEN_STAGE2D8_SOURCE=6cf37c29311601f4f83238cc8401c81ea7b9a1f0
```

## 2. 已验证内容

- 当前 `main` 与冻结 Stage 2D-7—2D-8 累计树无路径冲突；
- 双父汇总提交保留双方完整历史和内容；
- PR #166、#167、#168、#172 冻结分支未修改；
- V64 Artifact 未重建、未替换；
- Stage 2D-7 host 故障矩阵、冻结边界门、专用板和产品板 compile-only 通过；
- Stage 2D-8 driver 故障矩阵、manifest 默认拒绝、冻结边界门、专用板和产品板 compile-only 通过；
- V64 CI 已改为只验证冻结源码、Artifact 索引和实板证据，不再构建或上传新 V64；
- G2 实板验收及证据闭环保持 `passed`；
- F1.0-RC2、N1、M0、M2、greenhouse-manager、Stage 2B-3 和公共仓库安全 CI 通过；
- PR #170 的本地开发环境工具 CI 已通过，集成树保持该工具内容不变；
- 生产固件、现有产品 packages、M401A、T1、Home Assistant、Mosquitto 和 greenhouse-manager 运行环境均未修改。

## 3. 验证运行

```text
INTEGRATION_CI_RUN=29925293068
PUBLIC_SAFETY_RUN=29925292752
STAGE2D7_RUN=29925292704
STAGE2D8_DRIVER_RUN=29925292855
V64_REFERENCE_RUN=29925294462
F1_0_RC2_RUN=29925294627
N1_RUN=29925292989
M0_RUN=29925294580
M2_RUN=29925294434
GREENHOUSE_MANAGER_RUN=29925293027
STAGE2B3_RUN=29925297052
LOCAL_TOOLING_PARENT_RUN=29902898891
```

以上均为 `completed/success`。

## 4. 拟议 D4 动作

收到精确 D4 授权后，只执行：

1. 再确认 PR #173 为 open、Draft、mergeable；
2. 再确认 `main` 未出现未经复核的新提交；
3. 将 PR #173 标记 Ready；
4. 使用 **squash merge** 合并到 `main`；
5. 复核合并后的 `main` SHA 和必需 CI。

本 D4 不包含：

- 发布固件或创建 Release；
- 删除 PR #166、#167、#168、#172 的冻结分支；
- 删除私有证据；
- 操作测试板、eFuse、Wi-Fi、MQTT、Broker 或生产环境；
- 启动 Stage 2D-9 实板写入。

## 5. 停止条件

出现以下任一情况时，不执行 Ready 或合并：

- 最终记录提交的 CI 未全部通过；
- PR #173 不再 mergeable；
- `main` 在授权前前进且未完成重新审计；
- 冻结源码、Artifact、证据或生产路径出现漂移；
- 未收到原样、明确的 D4 授权文本。

## 6. 当前锁定状态

```text
PR_173_STATE=open_draft
READY_AUTHORIZED=false
MERGE_AUTHORIZED=false
RELEASE_AUTHORIZED=false
PRODUCTION_OPERATION_AUTHORIZED=false
NEXT_GATE=D4
```
