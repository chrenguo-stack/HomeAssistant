# Repository development instructions

For work involving GitHub Actions, pull requests, ESPHome or ESP32-C6 builds, greenhouse-manager tests, MQTT or Dynamic Security, T1 live validation, release preparation, development handoff, or development-efficiency changes, read and follow:

- `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
- `docs/development/local-ai-task-splitting-rules.md`
- `docs/development/development-artifact-archive-rules.md`
- `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`

The project treats the user, high-level model, Codex, and other bounded executors as one development team. GitHub is the durable shared collaboration workspace; chat, Codex sessions, local scratch paths, and temporary directories are ephemeral workspaces. Valuable source, tests, tools, decisions, handoffs, review artifacts, and other continuation-critical outputs are not durably complete while they exist only in a private session. Share them through GitHub as soon as practical, bind them by commit/hash, and use review/archive branches with explicit non-production status when they are not yet approved. Never commit secrets or use this rule to bypass authorization, rollback, branch-protection, or physical-safety boundaries.

The primary execution principle is accuracy, safety, efficiency, and verifiability. Workflow conventions and role assignments are means, not goals. `HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION` may be used as a default coordination pattern, but task decomposition and role allocation should adapt when another bounded approach materially improves correctness, safety, efficiency, or auditability.

The local task-splitting rules define the verified Mac development environment and require AI assistants to identify work that can be run locally, split independent work packages when safe, reuse local fast tests and cached firmware builds, and reserve Docker, GitHub required gates, board validation, and T1 production validation for their appropriate environments.

System instructions, security boundaries, explicit user decisions, production authorization requirements, and repository safety rules take precedence.

These workflow documents do not authorize production mutations, credential generation, anonymous MQTT closure, T1 writes, or reuse of consumed or expired production authorization.

The development artifact archive rules apply to every meaningful development,
diagnostic, validation, and live-acceptance boundary. A new boundary must not
start while a previous boundary still reports unarchived critical results;
archive-recovery work is the only permitted continuation, and it does not
claim or consume a pending physical authorization.

对于任何新建模块、重构已有模块、或清理孤立代码的工作，读取并遵循：
- `docs/development/module-lifecycle-rules.md`
