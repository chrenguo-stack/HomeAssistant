# T1 Broker 身份迁移真实 Mount 绑定门 v1

状态：M2.4g-5g Draft

## 1. 目的

本协议在生产 executor 编码前，对真实 T1 当前运行中的 Mosquitto 容器、Compose 来源、配置与数据 bind mount、镜像、基线配置和 fresh rollback 之间的绑定关系执行只读校验。

本阶段不安装生产 executor，不消费操作员授权，不创建、启动、重启、复制或删除容器，也不修改任何真实 T1 文件。

## 2. 输入

门禁只接受：

1. M2.4g-5f 生成的私有 production executor contract JSON；
2. 与该 contract 绑定的 activation handoff；
3. 与 handoff 绑定的 inactive migration stage；
4. handoff 内的 fresh rollback archive；
5. 预期 retained telemetry Topic。

contract 文件必须为普通文件、非符号链接并使用 `0600` 权限。

## 3. Contract 重绑定

门禁必须：

- 验证 contract 内部 SHA-256；
- 从当前 handoff 与 stage 重新构建 contract；
- 要求重建结果与输入 contract 全文完全一致；
- 拒绝 stage、rollback、material 或 Dynamic Security request 的任何漂移。

## 4. 真实 Mosquitto 容器绑定

门禁只读执行 `docker inspect mosquitto` 并要求：

- 容器状态为 `running`；
- restart count 为 0；
- live image ID 与 fresh rollback 记录的 Mosquitto image ID 一致；
- `/mosquitto/config` 恰好存在一个可写 bind mount；
- `/mosquitto/data` 恰好存在一个可写 bind mount；
- 两个 mount source 不相同；
- mount source 为真实目录且不是符号链接。

不接受 Docker named volume、临时文件系统、相对路径、多重 mount 或只读 mount。

## 5. Compose 来源绑定

Mosquitto 必须具有完整的 Docker Compose 标签：

- `com.docker.compose.project.working_dir`；
- `com.docker.compose.project.config_files`。

工作目录和配置文件必须真实存在、不是符号链接；配置文件必须位于工作目录内。

Mosquitto config/data mount source 必须均位于同一 Compose deployment 工作目录下。门禁输出只包含路径指纹，不输出原始宿主机路径。

## 6. Broker 基线校验

门禁必须只读检查：

- live `mosquitto.conf` SHA-256 与 production executor contract 的基线指纹一致；
- `allow_anonymous true` 仍生效；
- 当前配置没有启用任何 plugin、global_plugin 或 auth_plugin；
- `/mosquitto/data/dynamic-security.json` 尚不存在；
- 匿名客户端仍可读取指定 retained telemetry Topic。

任何一项失败均阻止后续生产 executor 接入。

## 7. 运行时与残留校验

门禁必须要求：

- Mosquitto、greenhouse-manager、Home Assistant 均在运行；
- 三者 restart count 均为 0；
- 不存在任何 M2 restore、shadow、package rehearsal、stage rehearsal 或 isolated 候选容器残留。

## 8. 允许的命令

本门禁只允许只读命令：

- `docker inspect`；
- `docker exec ... cat/test/mosquitto_sub`；
- `docker ps -a --format`。

禁止：

- `docker create`；
- `docker start`；
- `docker restart`；
- `docker stop`；
- `docker rm`；
- `docker cp`；
- `docker compose up/down/recreate`；
- 任何宿主机写文件操作。

## 9. 输出

输出为 secret-free JSON，至少包含：

- contract SHA-256；
- mount binding SHA-256；
- image ref、Compose 工作目录、Compose 配置文件、config source、data source 的短指纹；
- Broker 基线、匿名兼容、Dynamic Security 未启用、retained 可读、服务健康和无候选残留检查；
- 运行时摘要。

输出必须保持：

```json
{
  "read_only": true,
  "mount_binding_ready": true,
  "production_executor_available": false,
  "execution_enabled": false,
  "apply_enabled": false,
  "operator_action_authorized": false,
  "ready_for_live_activation": false,
  "current_services_modified": false,
  "preserve_anonymous": true,
  "anonymous_closure_enabled": false
}
```

## 10. 安全边界

该门禁通过仅表示生产 executor 的宿主机写入目标可被精确绑定，不表示：

- 已授权真实 T1 迁移；
- 已安装生产 executor；
- 已验证 Home Assistant UI 重配置；
- 已验证实体节点凭据交付；
- 可以关闭匿名访问。

## 11. 下一门禁

M2.4g-5h 可在仓库内实现默认禁用的 production adapter skeleton，但必须继续满足：

- 无公共 live-apply CLI；
- 未提供 contract、短时单次授权、fresh rollback 与 live mount gate 绑定时不可执行；
- mutation 入口前重新运行全部只读门禁；
- Home Assistant 与节点迁移仍保持人工/实体设备边界；
- 真实 T1 首次写入必须另行提供严格操作员门禁。
