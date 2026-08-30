# Repository development instructions

For work involving GitHub Actions, pull requests, ESPHome or ESP32-C6 builds, greenhouse-manager tests, MQTT or Dynamic Security, T1 live validation, release preparation, development handoff, or development-efficiency changes, read and follow:

- `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
- `docs/development/local-ai-task-splitting-rules.md`
- `docs/development/development-artifact-archive-rules.md`
- `docs/development/HANDOFF_DOCUMENT_CONTRACT.md`

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

For every newly generated development handoff:

- start from `docs/development/templates/N3W_FC4_DEVELOPMENT_HANDOFF_TEMPLATE_V1.0.md`;
- keep every required section, using `NOT_APPLICABLE` instead of deleting a section;
- preserve `EXECUTION_MODEL=HIGH_LEVEL_REASONING_PLUS_BOUNDED_CODEX_EXECUTION`;
- run `python3 tools/check_development_handoff.py --file <handoff>`;
- require handoff lint and public-repository safety to pass before declaring closeout complete.

Legacy handoffs without `HANDOFF_SCHEMA_VERSION` remain historical records and are not silently treated as schema-compliant.
