# N3W T1 F5 V2 real-T1 production executor source repair — 2026-10-20

## 0. Gate

```text
TASK=N3W_T1_F5_V2_REAL_T1_PRODUCTION_EXECUTOR_SOURCE_REPAIR_20261020_01
BASE_MAIN=1a0689f2c1c6566a397f065ff546ad26ef02046d
SOURCE_BRANCH=fix/n3w-t1-f5-v2-real-production-executor-20261020
SOURCE_PAYLOAD_HEAD_BEFORE_PROGRESS_DOC=8e2a5ae9168a6c323e8508d0af075a85ee718fdd

REPOSITORY_MUTATION=true
T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

This repair was entered only after the exact-main release had been built and locally verified and a freshly reflashed T1-B had passed all ten read-only Standard Fresh Armbian qualification checks.

No target mutation is authorized by this source-repair gate.

## 1. Blocker being repaired

The existing V2 source had the R2/R3 orchestration state machine and unit-test adapters, but no concrete real-T1 adapter or production CLI.

The review also found two interfaces that a real executor could not safely bridge without bounded source changes:

1. F4 live primitives require distinct successor authorization IDs for prepare, activate, runtime acceptance, persistence, certificate audit, certificate timer, reboot-control installation and reboot.
2. F3 host staging only accepted historical GitHub Actions artifact identity, while the production authority is the frozen exact release. The exact release already contains the hash-bound F3 payload and image artifacts and must be sufficient for execution.

## 2. Bounded implementation

### 2.1 Concrete production executor

Added:

```text
tools/n3w_t1_production_v2_executor.py
tests/tools/test_n3w_t1_production_v2_executor.py
```

The executor wires the already-versioned primitives into the frozen V2 order:

```text
exact release verify
-> managed SSH epoch #1
-> fresh qualification
-> one interactive top-level production approval
-> V2 marker STARTED
-> release-bound HOST_BASELINE
-> exact-release F3
-> Provision
-> F4 prepare
-> F4 activate
-> F4 runtime acceptance
-> F4 persistence
-> F4 certificate audit
-> F4 certificate timer
-> reboot-successor control install
-> one-shot reboot claim
-> controlled reboot
-> SSH epoch #2
-> target-local reboot verifier
-> Mac-side external acceptance probes
-> 90-second critical restart observation
-> V2 marker ACCEPTED
-> session close
-> final result
```

The production approval is deliberately inside the orchestrated execution path after release/SSH/qualification/plan construction and before marker creation or product mutation.

There is no non-interactive `--approved` CLI bypass.

### 2.2 Exact-release F3 source

`tools/n3w_t1_fresh_product_staging_host.py` now supports a second, mutually exclusive input mode:

```text
--release-f3-payload
--release-f3-images
```

The release-local mode reconstructs the already-frozen F3 outer file set from the release artifacts, rejects unsafe/unexpected tar members, binds the image-set source head to the payload source head, then reuses the existing F3 verification and apply path.

The existing GitHub artifact mode remains available for its historical workflows.

### 2.3 F4/reboot authority alignment

`tools/n3w_t1_production_v2.py` now derives distinct deterministic internal IDs for:

```text
F4_PREPARE
F4_ACTIVATE
F4_ACCEPT
F4_PERSISTENCE
F4_CERT_AUDIT
F4_CERT_TIMER
REBOOT_CONTROL_INSTALL
REBOOT_CONTROL
```

No Provision or F4 business primitive was rewritten.

### 2.4 Release packaging

`tools/n3w_t1_f5_v2_release_inputs_builder.py` now includes the concrete executor and its release verifier in `v2_mac_tools`.

A source-repaired production run therefore requires a newly built exact-main release after merge. The previously built release remains valid evidence for the pre-repair source but is not production authority for this repaired source.

## 3. Failure and safety boundaries

The executor reuses the existing fail-closed R3 behavior:

```text
pre-marker failure -> no target production mutation authority
post-STARTED failure -> freeze failure -> read-only forensics
                     -> close operator session
                     -> REFLASH_REQUIRED
post-reboot acceptance failure -> same forensic/reflash ordering
durable ACCEPTED + later cleanup failure -> preserve T1_PRODUCTION_READY
```

No mutation retry, normal-path repair command, management SSH key installation or board operation was added.

The external MQTT authentication probes intentionally occur before the frozen 90-second no-critical-restart observation. They use the exact provisioned service identities required by the R3 acceptance contract; the observation window begins only after those probes complete.

## 4. Focused source/CI coverage

The repair adds or extends tests for:

- approval placement and rejection of dual approval authority;
- distinct F4/reboot internal authorization boundaries;
- exact target transaction byte hashing;
- exact-release F3 materialization and unsafe-member rejection;
- concrete executor CLI without approval bypass;
- required R3 external probe surface;
- release-input packaging of the executor;
- source CI compilation and focused test inclusion.

## 5. First exact-head CI feedback and dependent binding repair

The first draft-PR CI at head `d0eada11a62596838b924e8da17edbab32a7d097` found two concrete issues:

```text
F5_V2_SOURCE_CI=FAIL
CAUSE=R3 approval callback was passed to R2 but missing from the R3 execute signature

F2_READONLY_PREFLIGHT_SOURCE_CI=FAIL
CAUSE=expected blob for tools/n3w_t1_fresh_product_staging_host.py was stale
```

The R3 callback signature defect was repaired directly.

The F2 failure was only an exact-source binding consequence of the approved staging-host change. The F2 executor behavior and read-only contract were not changed. Its executor and manifest now bind the repaired staging-host blob:

```text
STAGING_HOST_BLOB=47718484ecffc2e4e7cab9505a1833cf7f5c8d7a
```

This dependent alignment is required so the existing F2 regression guard continues to prove the exact current source instead of rejecting an intentionally changed file.

## 6. Independent CI review blocker and R2 repair

The independent exact-head review at:

```text
REVIEW_HEAD=036ef98946d9d0bf7fc5ff216c6a0f55081ef858
CI=15/15_SUCCESS
```

found one real-adapter blocker that CI had not covered.

The concrete adapter opened `/var/tmp/n3w-f5-v2-executor.*` and uploaded three tool files inside `start_ssh_epoch()`. Therefore the real order was:

```text
SSH epoch
-> target temp-directory/file writes
-> read-only qualification
-> production approval
```

That contradicted the frozen V2 authority order and made a later qualification report of `read_only=true` / `mutation_performed=false` misleading at the whole-run level.

R2 repairs only that boundary:

```text
start_ssh_epoch()
-> establish managed SSH only
-> verify trusted host key
-> zero remote workspace creation
-> zero SCP

qualification()
-> read-only probes only
-> zero remote workspace creation

approval denied
-> close managed SSH
-> zero target workspace/file mutation

approval PASS
-> start_marker() becomes the first adapter path allowed to open
   the remote temporary workspace
-> marker STARTED is attempted under the conservative STARTED failure boundary
-> HOST_BASELINE and later product mutation remain after marker start
```

Focused tests now fail if the remote workspace is opened during SSH establishment or qualification, and verify that the marker-start adapter path is the first one that opens it.

No T1 was accessed while making this repair.

## 7. R2 CI review blocker and R3 repair

The R2 exact-head review at:

```text
REVIEW_HEAD=0ccd6db9d207f9d100b0ab9613f3d66327f29df6
CI=15/15_SUCCESS
```

confirmed the pre-approval write blocker was closed, but found the same class of violation at the second SSH epoch.

The concrete adapter still opened the remote workspace inside `start_post_reboot_epoch()`, so the real order was:

```text
real reboot
-> SSH epoch #2
-> target /var/tmp creation + SCP
-> post-reboot acceptance
```

That violates the frozen separation between deployment and independent read-only post-reboot acceptance.

R3 repairs only that boundary:

```text
start_post_reboot_epoch()
-> establish SSH epoch #2
-> verify trusted host key
-> zero remote workspace creation
-> zero SCP

post_reboot_acceptance()
-> STARTED marker read
-> target-local reboot verifier
-> Mac external probes
-> 90-second restart observation
-> zero executor workspace creation

all acceptance checks PASS
-> accept_marker()
-> first post-reboot path allowed to create the temporary workspace
-> upload marker tool
-> durable ACCEPTED transition
```

Focused regression tests now fail if the workspace is opened during SSH epoch #2 or during post-reboot acceptance, and prove that the ACCEPTED marker path is the first post-reboot adapter path that opens it.

No T1 was accessed while making this repair.

## 8. Current state

```text
SOURCE_REPAIR_IMPLEMENTED_CANDIDATE=true
SOURCE_REVIEW_PENDING=true
EXACT_HEAD_CI_PENDING=true
DRAFT_PR_PENDING=true

T1_ACCESS=false
T1_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

The already reflashed T1-B remains untouched after its successful read-only qualification.

## 9. Next gate

```text
NEXT_ONE_GATE=N3W_T1_F5_V2_REAL_T1_PRODUCTION_EXECUTOR_SOURCE_REPAIR_R3_CI_REVIEW_20261020_01
AUTO_EXECUTE_NEXT_GATE=false
```

The next gate must review the exact PR head, focused CI and changed-file boundary. It must not merge or execute the real T1 production run.
