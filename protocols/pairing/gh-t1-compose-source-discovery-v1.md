# gh-t1-compose-source-discovery-v1

## 1. 问题

M2.4c 第一次真实 T1 只读审计发现，运行栈的 Compose 来源不能通过在预设目录中枚举以下固定文件名可靠确定：

```text
compose.yaml
compose.yml
docker-compose.yaml
docker-compose.yml
```

Compose 允许使用任意文件名、多个 `-f` 文件和非默认工作目录。因此，文件名猜测不能作为真实迁移门的依据。

## 2. 权威来源

真实运行容器应通过 Docker Compose 写入的容器 labels 提供来源信息：

```text
com.docker.compose.project
com.docker.compose.project.working_dir
com.docker.compose.project.config_files
```

M2 就绪审计必须分别读取 `mosquitto` 与 `greenhouse-manager` 的上述 labels。

## 3. 一致性规则

两个真实容器必须同时满足：

1. 三个 label 均存在且非空；
2. `project` 完全相同；
3. `working_dir` 完全相同；
4. `config_files` 完全相同；
5. `config_files` 中列出的每个文件均存在；
6. 相对配置路径必须相对于 `working_dir` 解析；
7. 多个配置文件按 label 中的逗号分隔顺序记录。

任一容器 label 缺失、不完整或相互不一致时，就绪门必须阻断并只报告原因，不得尝试自动修改运行栈。

## 4. 兼容回退

对于没有 Compose labels 的旧测试环境，可以回退到显式传入的目录并枚举标准文件名。只有至少发现一个标准 Compose 文件时，回退来源才可视为有效。

真实 T1 优先使用容器 labels，不得以回退目录覆盖已存在但不一致的实时 labels。

## 5. `.env` 权限

`.env` 从实时 `working_dir/.env` 读取。迁移就绪门要求：

```text
mode = 0600
```

审计只能读取并报告权限。权限修复必须作为独立、显式的主机安全步骤执行；不得在只读审计内部自动 `chmod`。

## 6. 报告要求

`compose` 报告至少包含：

```json
{
  "source": "docker_compose_labels",
  "requested_directory": "/path/used/as/fallback",
  "project": "compose-project-name",
  "directory": "/actual/working/dir",
  "files": [],
  "env": {},
  "metadata_consistent": true,
  "metadata_reason": null
}
```

新增门：

```text
compose_metadata_consistent
```

报告只能包含路径、文件模式和 SHA-256，不得包含 `.env` 内容或任何秘密值。

## 7. 安全边界

来源发现仅允许执行：

```text
docker inspect -f '{{json .Config.Labels}}' <container>
```

不得：

- 创建、停止或重启容器；
- 调用 `docker compose up/down`；
- 修改 Compose 文件或 `.env`；
- 创建秘密目录；
- 修改 Broker、manager、Home Assistant 或节点；
- 将就绪报告解释为真实迁移授权。
