# 温室环境监测系统 H3/N2 Stage 2D-7—2D-8 G2 汇总集成记录

**版本：** V1.0  
**日期：** 2026-07-22  
**集成分支：** `integration/h3-n2-stage2d8-g2-closure-20260722-v1`  
**目标分支：** `main`  
**当前状态：** Draft 集成验证，禁止 Ready、合并和发布

## 1. 集成目标

将以下已经冻结并完成独立验证的累计开发成果，以一个可审计的汇总集成分支接入当前 `main`：

1. PR #166：Stage 2D-7 隔离验收包；
2. PR #167：Stage 2D-8 隔离设备驱动；
3. PR #168：不可变 V64 G2 源码与 Artifact 元数据；
4. PR #172：G2 专用测试板实板验收脱敏证据闭环。

本集成不修改上述冻结分支，不重建 V64，不接触测试板、Broker、eFuse 或生产环境。

## 2. 冻结输入

```text
MAIN_AT_INTEGRATION_START=dd06eb06c762791999e4cb3bd22c2dac17aa3fd0
STAGE2D8_G2_EVIDENCE_HEAD=04562e50147e200fe408c66dee001f25ea1af0b9
FROZEN_STAGE2D8_SOURCE=6cf37c29311601f4f83238cc8401c81ea7b9a1f0
FROZEN_V64_ZIP_SHA256=662d9d4d850eea603d5defafb2b3c84a8bc07fae3a4b51229479b2a0a71e8ea9
G2_MERGED_SHA256=a3ff73ddc11115849e160637cd63e2f44c699e595c5c6aa43575f9d7626ed47d
PRIVATE_EVIDENCE_ARCHIVE_SHA256=a29db874961f9baa34137837fdbd31f1018d4fd8b7f01a2b5922bf512790a6fb
```

## 3. 集成方法

使用一个双父提交进行内容汇总：

```text
INTEGRATION_MERGE_COMMIT=8fa431704e6b506d0bb94d927d65697d1606fee2
PARENT_1_CURRENT_MAIN=dd06eb06c762791999e4cb3bd22c2dac17aa3fd0
PARENT_2_FROZEN_EVIDENCE_HEAD=04562e50147e200fe408c66dee001f25ea1af0b9
UNION_TREE_SHA=32cbd4401b20cf3b48e8c5e8f6bfe570dfc9defc
```

当前 `main` 相对 Stage 2D-7 起始基线仅新增 10 个本地开发环境与分阶段开发规范文件；Stage 2D-7—2D-8 累计分支新增的 61 个路径与这 10 个路径无重叠。汇总树保留双方完整内容，没有使用冲突覆盖或手工改写冻结文件。

## 4. 已完成结构验证

```text
CURRENT_MAIN_IS_ANCESTOR=true
FROZEN_EVIDENCE_HEAD_IS_ANCESTOR=true
MAIN_ONLY_PATHS_PRESERVED=10
STAGE2D7_TO_STAGE2D8_PATHS_IMPORTED=61
OVERLAPPING_PATH_COUNT=0
FROZEN_BRANCHES_MODIFIED=false
FROZEN_ARTIFACT_REBUILT=false
```

从当前 `main` 到集成提交的差异只包含 Stage 2D-7—2D-8 G2 累计路径；从冻结证据提交到集成提交的差异只包含当前 `main` 后续新增的 10 个开发环境与流程规范路径。

## 5. 后续验证门

汇总 Draft PR 必须完成：

- 公共仓库安全 CI；
- Stage 2D-7 host 故障矩阵与边界门；
- Stage 2D-8 driver host 故障矩阵、manifest 门和边界门；
- dedicated ESP32-C6 compile-only；
-完整 RC2 产品板兼容 compile-only；
- V64 源码、Artifact 索引和验收证据一致性检查；
- 本地开发环境工具 CI；
- 生产固件与既有产品 packages 未被修改检查。

CI 全部通过后才进入 D4 审核。D4 之前，PR 必须保持 Draft。

## 6. 禁止事项

本阶段继续禁止：

- 修改 PR #166、#167、#168、#172 的冻结分支；
- 重新生成或替换 V64 Artifact；
- 重放任何 D2 授权；
- 连接或操作专用测试板；
- eFuse、Secure Boot、Flash Encryption 操作；
- Wi-Fi、MQTT、Broker、测试密钥和可写 NVS 实机执行；
- M401A、T1、Home Assistant、Mosquitto、greenhouse-manager 或生产环境操作；
- 将汇总 PR 标记 Ready、合并或发布。

## 7. 当前结论

```text
INTEGRATION_SOURCE_ASSEMBLED=true
INTEGRATION_DRAFT_PR_PENDING=true
CI_VALIDATION_PENDING=true
D4_READY_MERGE_RELEASE=not_requested
PRODUCTION_ENVIRONMENT_MODIFIED=false
```
