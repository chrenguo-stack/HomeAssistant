# T1 Manager 提交后审计外部执行结果绑定 V2

状态：M2.4g-6y Draft

## 1. 修正原因

V70 实机生产执行结果使用历史 target wrapper 合同。该私有结果文件包含 `repository_sha`、`manager_version` 和单次 `authorization_id`，但不包含 `transaction_id`。V1 将所有外部结果都强制绑定到 `transaction_id`，与真实 V70 文件结构不一致，会导致只读持续性审计错误地安全关闭。

## 2. 两种允许的绑定模式

### 2.1 新执行包

结果文件包含 `transaction_id` 时，必须同时满足：

1. `transaction_id` 与已提交 journal 一致；
2. `authorization_id` 与 journal 一致；
3. 执行、postactivation、Manager 身份迁移和镜像保留均为成功终态；
4. 未回滚、未关闭 anonymous、未下发节点凭据。

该模式输出：

```text
execution_result_binding_mode=journal-transaction-id
```

### 2.2 历史 target wrapper

结果文件不包含 `transaction_id` 时，只允许 target wrapper schema，并必须同时满足：

1. `authorization_id` 与 journal 一致；
2. 调用方显式提供并精确匹配历史 `repository_sha` 与 `manager_version`；
3. `status=manager_identity_production_execution_succeeded`；
4. `bound_source_bundle_sha_exact=true`；
5. `bound_source_repository_sha_exact=true`；
6. `greenhouse_manager_image_preserved=true`；
7. Mosquitto、Home Assistant 未变化，节点未修改；
8. 未回滚、未关闭 anonymous、未下发节点凭据。

该模式依靠“显式 transaction workspace + 单次 authorization + 精确源码身份”完成历史兼容绑定，输出：

```text
execution_result_binding_mode=legacy-single-use-authorization
```

## 3. 禁止的降级

不得仅凭 schema、文件名或成功状态选择结果；不得忽略 authorization；不得在缺少历史源码 SHA 或版本时接受无 `transaction_id` 的 wrapper；不得重新运行历史生产执行或复用已消费授权来补齐证据。

## 4. 只读不变性

审计开始和结束时必须比较 transaction workspace 与 execution result 文件指纹。审计不得写文件、claim 授权、调用生产执行器、重启服务、发布 MQTT、修改 Home Assistant、下发节点凭据或关闭 anonymous。

## 5. 版本关系

本文件取代 `gh-t1-manager-identity-postcommit-external-result-binding-v1.md` 中“所有结果必须同时包含 transaction_id 与 authorization_id”的绝对要求。V1 其余只读、安全和外部文件指纹要求继续有效。
