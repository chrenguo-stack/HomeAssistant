# N3W T1 F5 Production Process V1 — Whole-Source Closure Review

Date: 2026-10-17

## Gate

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V1_WHOLE_SOURCE_CLOSURE_AND_EXACT_RELEASE_PREPARATION_20261017_01
RESULT=BLOCKED_SOURCE_REPAIR_REQUIRED

PR=612
PR_STATE=OPEN_DRAFT
REVIEW_HEAD=97e9451fc2195b27d4e961c4db84f8e044542e60
BASE_MAIN=9c81b889d97ed896b80d27af15069d16af0e0bdb
MAIN_DRIFT=NONE
PR_HEAD_DRIFT=NONE

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
EXACT_PRODUCTION_RELEASE_BUILT=false
~~~

The phase-level F5/F4 integration closures remain valid. This review does not reopen their local claims.

The whole-source contract cannot yet be closed because the normal production entrypoint and its pre-F3 host path are not fully assembled.

## Closed phase facts retained

~~~text
F4_PREPARE=CLOSED_PASS
F4_ACTIVATE=CLOSED_PASS
F4_ACCEPT=CLOSED_PASS
PERSIST_CERT=CLOSED_PASS
REBOOT_CONTROL=CLOSED_PASS
FINALIZE=CLOSED_PASS
CLOSE_RUN=CLOSED_PASS

PHASE_LEVEL_CLOSURES_REOPENED=false
~~~

## Blocking findings

### B1 — normal production entrypoint has no concrete runtime backend

`tools/n3w_t1_production.py` defines the `ProductionBackend` protocol and the fixed phase loop, but its CLI `main()` only runs when an external caller injects `backend_factory`.

The repository's normal executable path has no such injection. Direct `run` therefore terminates with:

~~~text
exact_release_runtime_backend_required
~~~

This conflicts with the frozen F5-2/F5-6 contract:

- one normal production entrypoint drives the complete chain;
- the packaged entrypoint must be runnable outside repository-only test injection;
- the normal path must reach the real target authority and existing primitives.

Current tests use `FakeBackend`, so they prove orchestrator sequencing but do not close the actual packaged runtime entrypoint.

~~~text
B1=OPEN_BLOCKER
CLASS=SOURCE_INTEGRATION
~~~

### B2 — HOST_BASELINE mutation is not bound to F5 phase authority or approved package versions

`tools/n3w_t1_fresh_host_baseline.py` is still the pre-F5 form:

- CLI has only `self-check|check|install`;
- `install` accepts no F5 production phase context;
- there is no primitive-local one-shot production execution claim;
- when installation is needed it runs `apt-get update`, reads the current APT candidate and installs that candidate.

The frozen release contract explicitly requires approved Docker Engine / Compose package versions and says normal production must not install an unreviewed later candidate merely because it is current.

Therefore the current HOST_BASELINE mutation path cannot be used by the final F5 release.

~~~text
B2=OPEN_BLOCKER
CLASS=RELEASE_ENVIRONMENT_BINDING
~~~

### B3 — unified SSH adapter is not yet wired through the normal F2/F3 host path

`n3w_t1_ssh_transport.py` itself has real-sshd integration coverage and fail-closed child-session settings.

However the whole-source diff shows no F5 boundary integration in the allowlisted:

- `tools/n3w_t1_fresh_product_staging_host.py`;
- `tools/execution_packages/n3w/f2/t1_fresh_readonly_preflight/executor.py`.

The source work-package design required normal ssh/scp transport to use the one F5-owned adapter. Without a concrete runtime backend, the existing staging host remains a separate execution surface rather than part of the fixed normal F5 chain.

~~~text
B3=OPEN_BLOCKER
CLASS=ORCHESTRATION_TRANSPORT_INTEGRATION
~~~

### B4 — F5-6 packaged-entrypoint evidence is missing

The F5 source CI currently proves:

- focused source/unit tests;
- real sshd behavior for the transport adapter;
- static guards;
- the existing repository regression set.

It does not execute the actual normal packaged `n3w-t1-production run --release ...` path against a concrete runtime backend. The architecture review explicitly required the packaged call chain to run without repository-only dependency injection.

~~~text
B4=OPEN_BLOCKER
CLASS=ACTUAL_ENTRYPOINT_CI
~~~

## Non-blocking item reserved for F5-7

No complete F5 production release builder/archive exists yet. That is expected to be F5-7 work and is not itself a defect in the phase adapters.

But F5-7 must not freeze an artifact while B1-B4 remain open.

~~~text
F5_7_EXACT_RELEASE_STATUS=NOT_READY
REASON=SOURCE_CLOSURE_BLOCKED
~~~

## Required repair scope

The existing work-package manifest already permits boundary changes to:

- `tools/n3w_t1_fresh_product_staging_host.py`;
- `tools/n3w_t1_fresh_host_baseline.py`;
- F2 readonly preflight executor;
- their tests/workflows.

One new logical runtime composition module is recommended so `n3w_t1_production.py` does not absorb target transport/staging implementation details:

~~~text
PROPOSED_NEW_PATH=tools/n3w_t1_production_runtime.py
PROPOSED_NEW_TEST=tests/tools/test_n3w_t1_production_runtime.py
~~~

This is outside the frozen source-work-package `new_paths` list, so the manifest's scope-delta rule applies. Product source must not add that path until an explicit reviewed scope delta is accepted.

The repair must close all of the following together:

1. standalone normal `run --release` can construct the concrete runtime backend;
2. trusted host-key / two SSH epoch behavior remains owned by `SSHTransport`;
3. read-only preflight is reachable before production approval;
4. HOST_BASELINE installation requires exact approved OS/package policy and a durable one-shot phase-bound claim before APT mutation;
5. F3 / provisioning / F4 / reboot / FINALIZE / CLOSE_RUN dispatch uses target durable phase claims and existing accepted primitives;
6. reboot actuation remains one-shot and is never retried after the durable actuation marker;
7. actual packaged-entrypoint CI proves the assembled call chain without `FakeBackend` injection;
8. no repair command or arbitrary remote shell surface is exposed by the normal CLI.

## Scope boundary / STOP

~~~text
SOURCE_SCOPE_EXPANSION_REQUIRED=true
PRODUCT_SOURCE_REPAIR_STARTED=false
EXACT_RELEASE_BUILD_STARTED=false

NEXT_ONE_GATE=N3W_T1_F5_PRODUCTION_PROCESS_V1_RUNTIME_ENTRYPOINT_AND_HOST_BASELINE_SOURCE_REPAIR_20261017_01

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
STOP=true
~~~

F5-7 exact production release construction resumes only after the runtime-entrypoint/host-baseline repair closes and the whole-source review has no remaining blocker.
