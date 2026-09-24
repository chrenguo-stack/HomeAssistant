# N3W_PROJECT_WORKING_CONTEXT

> Status: durable public project working context  
> Version: `N3W_PROJECT_WORKING_CONTEXT_VERSION=1.1`  
> Scope: N3-W development for the greenhouse monitoring system  
> Repository: `chrenguo-stack/HomeAssistant`

## 0. Purpose

This file is the durable **public long-term working context** for N3-W development.

It exists to keep stable project conventions out of individual chat handoffs. A new-chat handoff should describe only the current stage, current evidence, current authorization state, and the next bounded step. It should not repeatedly copy the same development habits, communication rules, GitHub workflow, evidence rules, or public/private boundaries.

```text
PUBLIC_LONG_TERM_CONTEXT=this file
CURRENT_DYNAMIC_STATE=docs/development/N3W_CURRENT_STATE.md
CURRENT_STATE_INDEX=docs/development/N3W_CURRENT_STATE_INDEX.md
KNOWN_FAILURE_GUARDS=docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
STAGE_DELTA=current formal handoff
PRIVATE_RUNTIME_CONTEXT=USER_MANAGED_OUTSIDE_PUBLIC_GIT
```

This file does **not** contain live passwords, private host locators, private network addresses, raw board identities, credentials, setup secrets, private keys, or other sensitive material.

---

## 1. Authority and freshness

Use the authority closest to the thing being proven.

When information conflicts, prefer:

```text
1. fresh exact repository / runtime / physical evidence
2. current N3W_CURRENT_STATE.md and N3W_CURRENT_STATE_INDEX.md
3. current stage-specific formal handoff
4. this long-term working context for stable conventions
5. historical handoffs and historical progress documents
6. conversation inference
```

A historical fact is not automatically a current fact.

Before claiming a live service, board, branch, pull request, artifact, or physical route is current, perform the smallest necessary fresh read-only check.

```text
FRESH_READONLY_REBIND_BEFORE_LIVE_CLAIM=true
HISTORICAL_STATE_IS_NOT_CURRENT_STATE=true
INFERENCE_IS_NOT_PROVEN_FACT=true
```

If a handoff names an exact historical handoff-standard authority, read that exact commit. Do not assume current `main` contains the same historical standard file.

---

## 2. Primary execution principle

The governing rule is:

```text
PRIMARY_EXECUTION_PRINCIPLE=ACCURACY_SAFETY_EFFICIENCY_VERIFIABILITY_FIRST
TEST_PRODUCT_NOT_TEST_FRAMEWORK=true
```

Practical meaning:

- choose the simplest method that gives reliable evidence;
- use read-only inspection before mutation whenever possible;
- do not add an executor, framework, manifest layer, branch, or CI job unless it solves a real engineering need;
- do not turn acceptance tooling into a second product architecture;
- stop at the first substantive mismatch unless the current contract explicitly allows continuation;
- after a failure, classify what actually failed before designing a repair;
- do not automatically cross into the next physical or mutation gate.

---

## 3. Communication style

User-facing replies should be concrete and easy to follow.

```text
COMMUNICATION_STYLE=PLAIN_DIRECT_CONCRETE
ABSTRACT_TERM_DENSITY=LOW
EXPLAIN_WHAT_HAPPENED=true
EXPLAIN_WHY=true
EXPLAIN_NEXT_ACTION=true
```

Default order:

1. what is happening now;
2. why it matters;
3. what to do next;
4. exact fields, hashes, commands, or error codes only where they are useful.

Prefer ordinary Chinese over repeated abstract labels such as `authority`, `gate`, `rebind`, `contract`, and `closure`. When an exact project term is necessary, keep the term but explain its concrete meaning.

Commands and exact identifiers must remain precise even when the surrounding explanation is simplified.

---

## 4. GitHub working method

GitHub is the durable shared engineering workspace.

```text
TEAM_SHARED_WORKSPACE=GITHUB
CHAT_SESSIONS_ARE_EPHEMERAL=true
DURABLE_ENGINEERING_ARTIFACTS_GO_TO_GITHUB=true
```

Source, tests, reusable tools, important design decisions, current-state records, known-failure guards, formal handoffs, and reproducibility information should be committed when they have continuing engineering value.

Secrets and private runtime locators are excluded from this rule.

### 4.1 Use short, phased GitHub operations

Long GitHub operations are deliberately split into small stages so that a timeout, truncation, or tool failure does not force a large operation to be repeated.

```text
GITHUB_OPERATION_MODE=PHASED_SHORT_CALLS
LARGE_MONOLITHIC_GITHUB_CALLS=AVOID
VERIFY_AFTER_REPOSITORY_WRITE=true
BLIND_REPLAY_AFTER_TOOL_FAILURE=false
```

Preferred sequence:

```text
A. fresh read-only repository / PR / branch rebind
B. inspect the small set of relevant files
C. decide the exact change
D. write a small bounded file set
E. re-fetch / compare and verify the resulting commit
F. check CI separately
G. merge only after the required review/decision
```

Do not combine unrelated repository reads, large searches, multiple sequential writes to the same file, CI polling, and merge into one long operation.

If a repository operation is interrupted, resume from the last **proven Git commit or remote state**. Do not assume an unconfirmed mutation succeeded and do not blindly repeat it.

### 4.2 Branch and pull-request defaults

For active engineering changes:

- use a purpose-specific branch;
- use a Draft PR while review or physical validation is incomplete;
- preserve exact head SHA for reviews and artifacts;
- do not merge merely because CI is green;
- treat merge as a separate decision when the current stage requires user approval;
- keep documentation-only alignment distinct from product-source authority.

Historical frozen branches or artifacts are evidence, not automatically deployment candidates.

---

## 5. Development environment convention

The Mac development environment is versioned and audited separately from handoffs.

Current environment authority is referenced by:

```text
docs/development/N3W_CURRENT_STATE_INDEX.md
docs/development/local-environment-records/
```

Do not copy volatile package versions, disk state, worktree state, or local paths into every handoff. Read the current environment record when the task actually depends on them.

Stable environment rules:

- host-side Python development uses the project virtual environment;
- ESPHome remains isolated from the host project Python environment when dependency requirements conflict;
- do not casually install or upgrade packages in a working environment to make one command pass;
- rerun the versioned local-environment doctor after meaningful host/toolchain changes;
- local environment warnings are not product failures unless evidence shows they affect the product result;
- prefer existing installed tools; do not install tooling on T1 or another target merely for convenience unless explicitly approved.

```text
LOCAL_ENVIRONMENT_CHANGE_REQUIRES_RECHECK=true
DEPENDENCY_ISOLATION_PRESERVED=true
TARGET_HOST_TOOL_INSTALL_DEFAULT=false
```

### 5.1 macOS ESP32-C6 serial / esptool guard

For physical ESP32-C6 work on macOS, keep the host serial/toolchain diagnosis separate from board diagnosis.

```text
MACOS_ESPTOOL_DEFAULT_INVOCATION=python3 -m esptool
USB_SERIAL_PATH_IS_LOCATOR_NOT_IDENTITY=true
RESOURCE_BUSY_BEFORE_PORT_OPEN_IS_NOT_BOARD_FAILURE=true
BLIND_ESPTOOL_RETRY_AFTER_RESOURCE_BUSY=false
```

Stable rules:

- prefer the project/current Python interpreter with `python3 -m esptool` instead of assuming a standalone `esptool` executable uses the same Python and `pyserial` environment;
- before relying on a board-tool result, confirm the selected interpreter can import both `esptool` and `serial`, and record their versions in private evidence when toolchain ambiguity matters;
- if `esptool` reports `Resource busy` before successfully opening the port, classify it first as a host/toolchain access failure; it does not prove ROM communication, Flash access, or a board hardware defect;
- check both `/dev/cu.usbmodem*` and `/dev/tty.usbmodem*`; an empty `lsof` result alone is not enough to blame DriverKit or the board;
- if no owner is visible, use a non-data-writing POSIX open/close probe on both device nodes. If POSIX open succeeds, inspect the Python/`pyserial`/standalone-wrapper path before USB re-enumeration or board-level recovery;
- do not repeatedly run `esptool` against a persistent open failure. Classify the host failure first, then perform at most the bounded retry allowed by the current gate;
- on zsh, do not use a bare unmatched wildcard as a device-count oracle because `no matches found` can terminate the command. Use Python `pathlib/glob`, zsh null-glob syntax, or another zero-match-safe enumeration method;
- a USB pathname is only a locator. Bind physical identity from fresh silicon evidence, keep raw identity private, and expose only a public-safe hash when needed.

These rules are about host/tooling correctness. They must not be used to infer application runtime health.

---

## 6. Default physical roles

Unless a stage-specific handoff explicitly overrides the roles:

```text
BOARD_A_DEFAULT_ROLE=STATIONARY_RELAY_GATEWAY
BOARD_B_DEFAULT_ROLE=PRIMARY_DEVICE_UNDER_TEST
T1_DEFAULT_ROLE=MANAGER_BROKER_HOMEASSISTANT_HOST
```

These are working roles, not permanent hardware identities.

Public GitHub documentation should use role names and public-safe hashes when identity binding is required. Raw board identity material belongs outside the public repository.

A physical test must still freshly confirm power, location, role, and relevant runtime state before relying on them.

---

## 7. Evidence rules

Use the strongest evidence that directly proves the claim.

### 7.1 N3-W telemetry acceptance

For Manager-visible Direct/Relay acceptance, durable canonical state is preferred over the presence or absence of an INFO log line.

```text
MANAGER_CANONICAL_DURABLE_STATE=PRIMARY_ACCEPTANCE_ORACLE
INFO_LOG_ABSENCE_ALONE=NOT_PRODUCT_FAILURE
```

This preserves the existing KF-010 guard: a missing INFO line can be a logging false negative.

### 7.2 Radio and delivery evidence

- successful API submission is not automatically proof of asynchronous RF delivery;
- source review, CI, artifact binding, flashing, and physical behavior are separate proofs;
- a historical low-level radio error must not be claimed fixed without appropriate post-fix evidence;
- a timing gap must not be attributed to one internal phase without phase-specific evidence.

### 7.3 Serial is not a passive observer

Opening an application serial port can reset or disturb the board.

```text
APPLICATION_SERIAL_AS_PASSIVE_ORACLE=false
```

Use non-intrusive Manager/Broker/durable-state evidence when it can answer the question.

### 7.4 Evidence and conclusion must match

Use explicit classifications:

```text
PASS
FAIL
NOT_EXECUTED
INCONCLUSIVE
UNKNOWN_FRESH
```

Do not turn `NOT_EXECUTED`, missing logs, stale evidence, or an operator assumption into `PASS`.

---

## 8. Authorization and mutation rules

Read-only inspection does not grant mutation authority.

Any live, physical, credential, firmware, NVS, Broker, Manager, DynSec, or comparable mutation must stay inside the exact authorization granted for that action.

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
AUTHORIZATION_SCOPE_EXPANSION=false
CONSUMED_AUTHORIZATION_REPLAY=false
```

For one-shot authorization:

- claim it only when entering the authorized action;
- once claimed, treat it as consumed according to its contract even if execution later fails;
- never silently reuse a consumed or superseded authorization;
- an operator override is evidence for that one bounded action only unless explicitly stated otherwise;
- a historical target override must not become a permanent identity rule.

After a substantive failure:

```text
AUTO_REPAIR=false
AUTO_RETRY=false
AUTO_REFLASH=false
STOP_AND_REVIEW=true
```

unless the exact current contract explicitly permits a bounded retry.

### 8.1 Fresh-silicon / replacement-board flash guard

A new or replacement ESP32-C6 must not inherit an existing board's write procedure merely because the hardware family is the same.

```text
FRESH_SILICON_REQUIRES_READONLY_IDENTITY_PREFLIGHT=true
EXISTING_BOARD_DELTA_WRITE_POLICY_TRANSFER=false
VIRGIN_BOARD_FULL_ERASE_DEFAULT=false
EXACT_ARTIFACT_FLASH_LAYOUT_REQUIRED_BEFORE_FIRST_WRITE=true
```

Before the first persistent write to fresh silicon:

- confirm chip family, public-safe silicon identity hash, silicon revision when available, Flash size, Secure Boot state, and Flash Encryption state with the minimum read-only ROM-level queries required by the gate;
- keep raw MAC / hardware identity in private evidence only;
- prove the exact artifact's first-write layout from artifact/provisioning authority. The evidence must establish the required bootloader, partition-table, OTA-data, application, factory-image, or equivalent `flash_args` relationship and exact offsets/hashes as applicable;
- do not reuse an existing-board partial write such as “OTA data + application only” unless the artifact authority explicitly proves it is valid for the fresh board;
- do not perform whole-chip erase merely because a board is new or assumed blank;
- keep artifact-specific offsets, hashes, and image names in the stage handoff/current-state evidence rather than in this durable runbook.

A successful source build or existing-board deployment does not by itself prove fresh-silicon provisioning compatibility.

---

## 9. User / assistant execution split

The user is the physical operator and final decision maker. The assistant owns technical analysis, command design, safety boundaries, evidence interpretation, and repository-quality engineering work.

When the assistant cannot directly access a physical board or private T1 runtime, it should give the user a complete bounded command or operation package rather than pretending the action was executed.

For mechanical user operations, prefer a complete batch when the later commands do not depend on earlier safety results.

Do not default to:

```text
one tiny command
→ wait for one line
→ another tiny command
→ repeat
```

Use separate steps only where an earlier result genuinely determines whether the next action is safe.

---

## 10. Public / private information boundary

Public GitHub may contain:

- source and tests;
- public-safe architecture and process rules;
- sanitized runtime conclusions;
- artifact IDs and hashes;
- hashed device identities where necessary;
- sanitized timing and acceptance evidence;
- reproducibility and recovery instructions that do not expose secrets.

Do not commit:

- passwords or tokens;
- private keys or setup secrets;
- private host addresses or private SSH locators;
- raw credentials;
- raw NVS dumps;
- raw board identity material when a public-safe hash is sufficient;
- private runtime logs containing sensitive values.

```text
PUBLIC_REPOSITORY_SECRET_VALUES_ALLOWED=false
PRIVATE_RUNTIME_LOCATORS_ALLOWED=false
```

Private working context is maintained outside the public repository and may be loaded separately when needed.

---

## 11. What belongs in a handoff

A handoff is a **stage delta**, not a complete project encyclopedia.

It should contain only what the next session needs that is not already durable in this file or the current-state documents.

Required concepts:

- why the chat is switching;
- current project route and stop point;
- exact current repository/candidate/artifact authorities needed by the next step;
- fresh live baseline or explicit `UNKNOWN_FRESH` items;
- newly proven facts;
- current blocker, if any;
- relevant closed/forbidden routes only;
- authorization ledger entries that can still affect execution;
- exactly one next gate;
- exact allowed/forbidden scope for that gate;
- execution method;
- expected structured result;
- what happens after PASS or FAIL;
- any important artifact not yet durably shared to GitHub;
- a compact new-chat start prompt.

Do **not** repeat the full contents of this file in every handoff.

```text
HANDOFF_IS_STAGE_DELTA=true
DUPLICATE_LONG_TERM_RULES_IN_HANDOFF=false
```

A handoff may restate a long-term rule only when:

- the next gate is unusually sensitive to that rule;
- the stage introduces a temporary stricter override;
- the rule is required for a self-contained physical operation package.

---

## 12. Minimum new-chat read set

For an N3-W continuation, the default public read set is:

```text
1. current formal handoff
2. docs/development/N3W_PROJECT_WORKING_CONTEXT.md
3. docs/development/N3W_CURRENT_STATE.md
4. docs/development/N3W_CURRENT_STATE_INDEX.md
5. docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
6. exact handoff standard authority, only when the handoff specifies one
```

Then perform the smallest fresh read-only rebind needed for the current gate.

Do not reread the full project history unless current evidence is insufficient.

---

## 13. Team-workspace completeness

The existing project-wide collaboration standard remains applicable:

```text
docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md
```

A meaningful development result that exists only in chat or a temporary local directory is not durably shared.

Every formal handoff should state:

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=<n>
TEAM_SHARE_COMPLETENESS=PASS|FAIL
```

If a valuable artifact cannot be committed, record a public-safe recovery locator/hash and explain why it remains outside GitHub.

---

## 14. Maintenance rule

Update this file only when a **stable working convention** changes.

Do not update it for:

- a new sequence number;
- a new physical observation;
- a new candidate SHA;
- a new one-shot authorization;
- a temporary failure;
- a single gate result.

Those belong in current state, progress alignment, known failures, or the current handoff.

A change to this file should explain the durable process need it addresses and should update the handoff template when the change affects new-chat continuation.

```text
N3W_PROJECT_WORKING_CONTEXT_VERSION=1.1
STABLE_CONVENTIONS_ONLY=true
STAGE_SPECIFIC_VALUES_PROHIBITED=true
HANDOFF_TEMPLATE_EXPECTED_TO_REFERENCE_THIS_FILE=true
```
