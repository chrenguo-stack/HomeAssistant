# Repository development instructions

For work involving GitHub Actions, pull requests, ESPHome or ESP32-C6 builds, greenhouse-manager tests, MQTT or Dynamic Security, T1 live validation, release preparation, development handoff, development-efficiency changes, execution-package generation, authorization validation, or physical-test preparation, read and follow:

- `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
- `docs/development/local-ai-task-splitting-rules.md`
- `docs/development/development-lessons-and-validation-rules.md`

The local task-splitting rules define the verified Mac development environment and require AI assistants to identify work that can be run locally, split independent work packages when safe, reuse local fast tests and cached firmware builds, and reserve Docker, GitHub required gates, board validation, and T1 production validation for their appropriate environments.

The development lessons and validation rules are a continuously maintained record of recurring failure patterns, root causes, required regression tests, delivery-equivalence checks, and conditions that require stabilization before further physical authorization or successor layering. Relevant findings must be converted into reusable rules and automated validation rather than remaining only in chat or handoff documents.

System instructions, security boundaries, explicit user decisions, production authorization requirements, and repository safety rules take precedence.

These workflow documents do not authorize production mutations, credential generation, anonymous MQTT closure, T1 writes, board access, USB or serial enumeration, esptool, Flash/NVS, Broker startup, PREPARE, VERIFY, ACTIVATE, CLEANUP, or reuse of consumed or expired authorization.

对于任何新建模块、重构已有模块、或清理孤立代码的工作，读取并遵循：
- `docs/development/module-lifecycle-rules.md`
