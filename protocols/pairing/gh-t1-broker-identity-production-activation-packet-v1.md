# T1 Broker 身份生产激活执行包 V1

状态：M2.4g-5x Draft

## 1. 目的

本执行包是唯一允许进入真实 Broker 身份激活事务的命令行入口。它只接受 5w 准备包生成的短时授权、事务计划、adapter contract 与最终执行确认，并调用 5u 编排器执行一次原子事务。

## 2. 双重显式授权

执行必须同时满足：

1. 5w 创建的 authorization 当前有效、未 claim、未消费；
2. 调用 CLI 时显式传入 `--enable-production-execution`；
3. `EXECUTE-M2-BROKER-ACTIVATION:*` 与准备包中的 execution request 完全一致。

任一条件不满足时，不得建立 transaction workspace、claim 授权或修改 Broker。

## 3. 输入边界

执行包仅接受：

- mode-0700 的 5w preparation artifact 目录；
- mode-0700 的 5r runtime artifact 目录；
- 已验证 activation handoff；
- `gh/` 命名空间 retained topic；
- 精确 execution confirmation；
- 独立 mode-0700 `greenhouse-m2-production-transactions-*` 目录。

所有 authorization、plan、contract、manifest 和 bundle 文件必须为 mode 0600、非符号链接，并由各自 summary 文件解析，不允许手工替换路径。

## 4. 实际变更范围

成功事务允许：

- 原子更新 Mosquitto config bind source；
- 创建 Dynamic Security state；
- 仅重启 Mosquitto；
- 使用进程内 MQTT v5 创建身份、角色和匿名兼容组；
- 删除 bootstrap admin；
- 保留匿名访问与 retained state。

禁止：

- 重启或修改 greenhouse-manager；
- 重启或自动修改 Home Assistant；
- 修改 Home Assistant `.storage`；
- 向实体节点下发凭据；
- 关闭匿名访问；
- 创建或重建容器、Compose、systemd 或 SSH 操作。

## 5. 运行时审计

执行前后必须保存三个容器的 private inspect 快照，并验证：

- 三个容器 ID 与 image ID 均不变；
- 三个服务最终均为 running；
- greenhouse-manager 和 Home Assistant 的 started-at 与 restart count 不变；
- 成功时 Mosquitto started-at 必须变化。

## 6. 成功条件

成功报告必须同时包含：

```text
BROKER_IDENTITY_ACTIVATED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
HOMEASSISTANT_RECONFIGURED=false
NODE_CREDENTIALS_DELIVERED=false
PRESERVE_ANONYMOUS=true
ANONYMOUS_CLOSURE_ENABLED=false
```

## 7. 失败与回退

执行 CLI 返回失败时，shell 包仍必须采集 after runtime inventory。mutation 已开始的失败必须由编排器完成完整 rollback；rollback 失败属于终止故障，只能依据私有 journal 和现场运行状态继续处置，禁止自动重试或复用授权。
