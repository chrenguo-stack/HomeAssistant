# T1 Broker 身份激活执行准备包 V1

状态：M2.4g-5w Draft

## 1. 目的

本准备包在新鲜的只读 activation decision packet 基础上，使用操作员针对该 bundle 的精确确认创建短时、单次授权，并生成事务计划、生产 adapter contract 和最终 execution request。

该流程不 claim 或消费授权，不重启服务，不修改 Mosquitto、Home Assistant 或实体节点。

## 2. 输入

- mode-0700 的 `greenhouse-m2-runtime-bindings-*` 目录；
- 该目录中 readiness bundle 对应的精确 `AUTHORIZE-M2-BROKER-BUNDLE:*` 确认；
- 独立的 mode-0700 `greenhouse-m2-execution-preparation-*` 输出目录。

旧 bundle、不同 runtime fingerprint 或不同代码版本的确认不得复用。

## 3. 生成材料

准备包依次生成：

1. 最长 1800 秒、单次、mode-0600 的 bundle-bound authorization；
2. 与 authorization document SHA-256 绑定的 transaction plan；
3. 与 plan、authorization、driver、executor、runtime、preflight 和 Home Assistant gate 全绑定的 production transaction adapter contract；
4. 只读 production execution request；
5. 独立的最终执行确认字符串：

```text
EXECUTE-M2-BROKER-ACTIVATION:<bundle前16位>:<runtime fingerprint>:<adapter contract前16位>
```

## 4. 只读服务边界

准备流程前后必须比较 Mosquitto、greenhouse-manager 与 Home Assistant 的：

- 运行状态；
- restart count；
- started-at；
- image ID。

任一变化都必须失败。允许的 Docker 操作只有 `docker inspect`。

## 5. Python 依赖边界

只读准备阶段只构建和验证 execution request，不建立 MQTT 会话，因此不得要求宿主机系统 Python 预装 `paho-mqtt`。生产 Broker driver 只能在真实执行阶段首次建立 MQTT 会话时加载 `paho-mqtt`；缺少该依赖时必须在任何 Broker 变更前以明确错误终止。

## 6. 安全输出

stdout 只允许输出：

- authorization summary；
- transaction plan summary；
- secret-free execution request；
- 最终执行确认；
- 明确的未执行状态。

authorization token 只能保存在 mode-0600 私有文件中，禁止写入 stdout。

## 7. 当前边界

成功准备后仍保持：

```text
AUTHORIZATION_CREATED=true
AUTHORIZATION_CLAIMED=false
EXECUTION_REQUEST_READY=true
LIVE_ACTIVATION_EXECUTED=false
CURRENT_SERVICES_MODIFIED=false
PRESERVE_ANONYMOUS=true
```

只有操作员再次确认最终执行字符串，并在授权有效期内运行独立执行包，才允许进入真实 Broker 事务。
