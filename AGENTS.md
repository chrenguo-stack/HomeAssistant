# Repository development instructions

For work involving GitHub Actions, pull requests, ESPHome or ESP32-C6 builds, greenhouse-manager tests, MQTT or Dynamic Security, T1 live validation, release preparation, development handoff, or development-efficiency changes, read and follow:

- `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
- `docs/development/local-ai-task-splitting-rules.md`

The local task-splitting rules define the verified Mac development environment and require AI assistants to identify work that can be run locally, split independent work packages when safe, reuse local fast tests and cached firmware builds, and reserve Docker, GitHub required gates, board validation, and T1 production validation for their appropriate environments.

System instructions, security boundaries, explicit user decisions, production authorization requirements, and repository safety rules take precedence.

These workflow documents do not authorize production mutations, credential generation, anonymous MQTT closure, T1 writes, or reuse of consumed or expired production authorization.

对于任何新建模块、重构已有模块、或清理孤立代码的工作，读取并遵循：
- `docs/development/module-lifecycle-rules.md`
