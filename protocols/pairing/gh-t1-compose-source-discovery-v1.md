# gh-t1-compose-source-discovery-v1

## 1. 目的

M2.4c 真实 T1 就绪审计不能通过固定文件名猜测 Compose 来源，也不能假定所有服务属于同一个 Compose 项目。

真实 T1 当前已确认采用两个独立部署来源：

- Mosquitto：独立 Compose 项目；
- greenhouse-manager：项目仓库内的独立 Compose 项目。

审计必须逐服务识别并验证各自的真实来源。

## 2. 权威来源

每个运行容器通过 Docker Compose labels 提供来源：

```text
com.docker.compose.project
com.docker.compose.project.working_dir
com.docker.compose.project.config_files
```

审计必须分别读取：

```text
mosquitto
greenhouse-manager
```

只允许执行只读命令：

```text
docker inspect -f '{{json .Config.Labels}}' <container>
```

## 3. 单个服务来源规则

每个容器都必须满足：

1. project、working_dir、config_files 三个 label 均存在且非空；
2. working_dir 解析为规范化绝对路径；
3. 相对 config_files 路径相对于该 working_dir 解析；
4. 多个配置文件保持 label 中的原始顺序；
5. 每个配置文件必须存在；
6. working_dir 必须存在。

任一容器来源不完整时，`compose_metadata_consistent` 必须失败。

## 4. 多项目部署

不同服务可以合法属于不同的 Compose 项目、不同工作目录和不同配置文件。

因此，不得要求：

- project 名称相同；
- working_dir 相同；
- config_files 相同。

审计应按规范化后的：

```text
working_dir + 有序 config_files
```

对来源分组，生成一个或多个 deployment 记录。同一来源的多个容器可以合并到同一个 deployment；不同来源必须分别保留。

`compose_metadata_consistent=true` 表示所有被审计容器都提供了完整、可解析的来源，不表示所有容器来自同一个 Compose 项目。

## 5. `.env` 权限

每个 deployment 的候选 `.env` 路径固定为：

```text
<working_dir>/.env
```

规则：

- `.env` 不存在：允许，不构成权限失败；
- `.env` 存在：必须为普通文件且权限为 `0600`；
- 任一已存在 `.env` 不是 `0600`：`compose_env_private=false`。

审计只读取路径、存在性、权限和 SHA-256，不读取或输出内容。

权限修复必须作为审计外的独立显式步骤执行，并在修改前后验证 SHA-256 不变。

## 6. 报告结构

多项目报告示例：

```json
{
  "source": "docker_compose_labels",
  "projects": ["ha_docker", "t1"],
  "deployments": [
    {
      "projects": ["ha_docker"],
      "containers": ["mosquitto"],
      "directory": "/opt/ha_docker",
      "files": [],
      "env": {}
    },
    {
      "projects": ["t1"],
      "containers": ["greenhouse-manager"],
      "directory": "/opt/HomeAssistant/infra/compose/t1",
      "files": [],
      "env": {}
    }
  ],
  "container_sources": {},
  "metadata_consistent": true,
  "metadata_reason": null
}
```

单项目时，为兼容已有工具，还可以同时输出顶层：

```text
project
directory
files
env
```

多项目时这些顶层单值字段必须为 `null` 或空集合，调用方应使用 `deployments`。

## 7. 门禁定义

- `compose_metadata_consistent`：所有目标容器的 Compose labels 完整且可解析；
- `compose_directory_present`：所有 deployment 工作目录存在；
- `compose_configuration_present`：所有 deployment 的全部配置文件存在；
- `compose_env_private`：所有已存在的 deployment `.env` 均为 `0600`。

任何门禁失败都只能阻断并报告，不得自动修复运行栈。

## 8. 兼容回退

只有当所有目标容器完全没有 Compose labels 时，才允许回退到显式传入目录并枚举标准 Compose 文件名。

如果 labels 已存在但不完整，不得使用回退目录掩盖问题。

## 9. 安全边界

来源发现不得：

- 创建、停止或重启容器；
- 调用 `docker compose up/down`；
- 修改 Compose 文件或 `.env`；
- 创建秘密目录；
- 修改 Broker、manager、Home Assistant 或节点；
- 将就绪报告解释为真实迁移授权。
