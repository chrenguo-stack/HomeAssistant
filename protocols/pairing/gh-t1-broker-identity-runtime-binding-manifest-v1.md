# gh-t1-broker-identity-runtime-binding-manifest-v1

状态：M2.4g-5l Draft

## 目的

本协议定义真实 T1 Mosquitto 运行时路径与容器身份的私有绑定材料。该材料用于后续 production driver 的再次验证，不提供执行能力。

## 输入绑定

生成前必须验证：

- production executor contract；
- production Broker driver contract；
- 已通过的 live mount gate；
- contract、skeleton、driver 与 mount-binding SHA-256；
- Mosquitto 当前容器仍为 running 且 restart count 为 0；
- 当前 image、image ref、Compose 工作目录、Compose 文件和 config/data bind mount 仍与 live mount gate 一致；
- `mosquitto.conf` 仍匹配冻结基线；
- `dynamic-security.json` 仍不存在。

## 私有内容

manifest 包含执行阶段必须使用但不得输出到普通日志的真实值：

- Mosquitto container ID、image ID、image ref、started-at；
- Compose 工作目录与配置文件路径；
- `/mosquitto/config` 和 `/mosquitto/data` 的宿主机来源路径；
- `mosquitto.conf` 与未来 Dynamic Security state 的宿主机路径；
- 路径对应的 device、inode、mode、uid、gid；
- 配置和 Compose 文件 SHA-256。

manifest 文件必须为 mode `0600`，所在目录必须为私有目录，且目录名称以 `greenhouse-m2-runtime-bindings` 开头。

## 写入边界

生成器只允许：

1. 执行 `docker inspect mosquitto`；
2. 读取已绑定的宿主机配置和目录元数据；
3. 在与 live Compose 部署完全分离的私有输出目录中原子写入 manifest；
4. 对 manifest 文件和父目录执行 `fsync`。

输出目录在创建之前必须确认不位于 Compose 工作目录、Mosquitto config 或 data 目录内。

禁止：

- Docker restart/exec/cp/create/start/stop/rm；
- 写入 Mosquitto、Home Assistant、manager、Compose 或节点路径；
- claim 操作员授权；
- 输出真实路径到标准输出；
- 生成 execute/apply/live 入口。

## 标准输出

标准输出只能包含：

- manifest 文件名；
- 输出目录短指纹；
- contract、driver、mount-binding 和 manifest SHA-256；
- 安全状态字段。

不得包含 manifest 内的真实宿主机路径。

## 当前状态

```text
runtime_binding_captured=true
read_only_capture=true
production_driver_installed=false
production_executor_available=false
execution_enabled=false
apply_enabled=false
operator_action_authorized=false
ready_for_live_activation=false
current_services_modified=false
preserve_anonymous=true
anonymous_closure_enabled=false
```
