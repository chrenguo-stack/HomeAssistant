# H3/N2 Stage 2D-9R G3R 基线聚合摘要修正合同 V1

## 决策

本层仅修正证据与源码合同，不执行任何实板操作。

旧预期聚合摘要 `0735d98c7b4e2a698b42d39bdded1dd04f97b9441270e8bc03be347d369c8793` 永久登记为错误派生摘要。它不等于已冻结六个组成字段的规范化 JSON SHA-256。

六个组成字段保持不变：板卡身份摘要、串口身份摘要、`chip_id` 输出摘要、`flash_id` 输出摘要、测试分区摘要及长度。按执行器实际 schema 重新计算后的摘要为 `776517efcac0c6cf03cabe0572b773dedc89e9bb2793ccb0d9f9585ea6fa601f`，与 B2 的只读观测一致。

## B2 绑定

B2 永久保持 `CONSUMED_PASS`，结果摘要为 `f46565e0f4445781cbd84d2685bea6dcee7961ea7e7f48cd4bd7568a3e747082`。B2 未发生 Flash/NVS 写入或擦除，也未启动 Broker、PREPARE、VERIFY、ACTIVATE 或 CLEANUP。

## MAC 候选证据

B2 只保留了候选数量 2，没有保留候选摘要集合，因此不能事后选择其中一个候选。新策略只保存每个候选、标签和来源行的 SHA-256；候选不唯一时保持 `AMBIGUOUS_CANDIDATES`，不选择、不作为阻塞型硬件身份。

## 后继闭包

本层生成源码冻结的修正闭包与未授权 H5 请求草稿。H5 是主机侧、一次性、限时的独立决策门；只有 H5 被精确批准并成功消费后，才允许生成仍未授权的物理请求 `-05`。

本层不创建 `PHYSICAL_D2_REQUEST_05.json`，不授权任何物理执行。

## 禁止事项

本层禁止板卡连接与枚举、串口、esptool、Flash/NVS、Broker、PREPARE、VERIFY、ACTIVATE、CLEANUP、Ready、merge、release、tag 和 deployment。
