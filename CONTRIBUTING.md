# 开发与提交规则

## 分支

- `main`：稳定基线，不直接进行大范围试验。
- `feature/<scope>-<name>`：功能开发。
- `fix/<scope>-<name>`：缺陷修复。
- `docs/<name>`：文档和协议。
- `chore/<name>`：仓库、构建和维护。

## 提交信息

采用简化 Conventional Commits：

- `feat:` 新功能
- `fix:` 修复
- `docs:` 文档或协议
- `test:` 测试
- `refactor:` 不改变外部行为的重构
- `build:` 构建、依赖和 CI
- `chore:` 维护

## 协议优先

涉及以下内容时，应先修改 `protocols/` 或新增 ADR：

- MQTT 主题和字段；
- 配对、身份和凭据；
- ESP-NOW 或 LoRa 帧格式；
- availability、去重和路径租约；
- Home Assistant 设备身份和 Discovery 行为。

## 合并要求

- 不提交真实 Wi-Fi 密码、MQTT 密码、私钥、证书私钥或设备密钥；
- 新功能应附最小测试或明确的实板验收步骤；
- 影响两个 SKU 的修改必须分别说明 Wi-Fi 版和 LoRa 版影响；
- 未完成代码应使用功能开关隔离，不得破坏主路径；
- 通过 Pull Request 合并到 `main`，保留审查记录。
