# N3W T1 F5 V1 source work-package preparation — 2026-10-17

## 1. Gate

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V1_SOURCE_WORK_PACKAGE_PREPARATION_20261017_01
RESULT=CLOSED_PASS_READY_FOR_SOURCE_IMPLEMENTATION

BASE_MAIN=9c81b889d97ed896b80d27af15069d16af0e0bdb
BASE_TREE=ffd168f596a98762e003797ce862e996b11e7671
MAIN_DRIFT=NONE
PR611_STATE=CLOSED_MERGED

ARCHITECTURE_CONTRACT_BLOB=c55cf899cee9f251b84b31c38f9441abda0122d3
ASTRA_REVIEW_BLOB=237f4400eab739aed89c9b65e793675bbc0832cd
POSTMERGE_ALIGNMENT_BLOB=20b98729728ba02b6402c778f3f87b8bac75a543

SOURCE_BRANCH=feat/n3w-t1-f5-production-process-v1-source-20261017
SOURCE_BRANCH_BASE=9c81b889d97ed896b80d27af15069d16af0e0bdb
SOURCE_BRANCH_PREEXISTING=false
SOURCE_BRANCH_CREATED=true

F5_SOURCE_SCOPE=F5_1_THROUGH_F5_6_ONE_COHERENT_SOURCE_WORK_PACKAGE
ONE_COHERENT_SOURCE_PR=true
PRODUCT_SOURCE_MUTATION=false
F5_SOURCE_IMPLEMENTATION_STARTED=false

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false

NEXT_ONE_GATE=N3W_T1_F5_PRODUCTION_PROCESS_V1_SOURCE_WORK_PACKAGE_IMPLEMENTATION_20261017_01
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
~~~

## 2. Preparation conclusion

Fresh rebind confirms that main is still the post-PR #611 authority and has not drifted from the accepted F5-0
architecture state. F5-1 through F5-6 are therefore prepared as one source work package rather than six separate
PRs or six production approvals.

This gate creates the dedicated source branch and freezes the implementation scope. It does not implement or modify
product source, does not access T1-B, does not touch ESP32 boards and does not merge anything.

The exact machine-readable scope is:
`docs/development/N3W_T1_F5_PRODUCTION_PROCESS_V1_SOURCE_WORK_PACKAGE_MANIFEST_20261017.json`.

## 3. Frozen source structure

Four new logical modules are the center of the work package:

1. `tools/n3w_t1_production.py` — Mac normal run/inspect/verify entrypoint and fixed stage orchestration.
2. `tools/n3w_t1_production_authority.py` — target durable run/phase authority, replay prevention and phase dispatch.
3. `tools/n3w_t1_ssh_transport.py` — one controlled SSH transport adapter, host-key checking, master lifecycle and cleanup.
4. `tools/n3w_t1_production_contract.py` — release/plan/result schema, check policy and public evidence allowlist.

Each module has one focused test file. A dedicated F5 source CI workflow is also reserved.

## 4. Existing adapters allowed to change

The work package may adapt only the existing paths frozen in the manifest. They cover:

- F3 public deployment and Mac staging transport;
- supported OS/Docker baseline policy;
- reusable F2 read-only preflight;
- explicit provisioning;
- F4 activation and reboot authority;
- F4/reboot package builders;
- their direct regression tests;
- the exact F2/F3/provision/F4 build and source-CI workflows needed to carry the new dependencies.

The implementation must modify these only at their boundaries. Existing F3/F4 business logic, ordering, rollback,
certificate and reboot verification semantics remain authoritative.

## 5. Default no-change surfaces

The following are explicitly reviewed but remain byte-identical by default:

- `device_firstboot.py`;
- `fresh_installer.py`;
- `n3w_t1_f4_reboot_verify.py`;
- `n3w_t1_f4_certificate_runtime_guard.py`.

Manager/Broker/HA business behavior, ESP32 firmware, board registration, Golden Master/Seal/clone tools and user
onboarding are outside this work package.

If implementation proves that an additional path is genuinely required, the source gate must stop before mutating it,
record the concrete blocker and update the scope manifest through an explicit reviewed delta.

## 6. Frozen implementation order

The single work package will proceed in this order:

1. F5-1: durable production run/phase authority and existing primitive boundary binding.
2. F5-2: Mac production orchestrator with a fixed normal path and no repair dispatch.
3. F5-3: unified SSH adapter, verified host-key behavior, connection reuse and post-reboot reauthentication.
4. F5-4: static check policy and override mechanism; production allowlist remains empty.
5. F5-5: stable final-result schema and public/private evidence split.
6. F5-6: focused/negative/integration/package-entrypoint regression and source CI.

Implementation may use multiple commits for reviewability, but remains one source branch and one coherent source PR.

## 7. Non-negotiable guards

The implementation must preserve all F5-0 architecture decisions:

- one explicit production approval;
- two SSH password prompts for one planned reboot, one per connection epoch;
- no password persistence and no new permanent SSH login key;
- target-durable run/phase claims with fail-closed UNKNOWN and no silent replay;
- no normal-path repair command or arbitrary shell escape;
- initial override allowlist empty;
- current 5 GiB reserve remains strict;
- exact release/environment binding, including supported OS and Docker/Compose versions;
- explicit device/process/evidence completion fields and strict public/private evidence split;
- Plan B remains unchanged: T1-A is preserved; fresh T1-B is used only after exact source/release closure.

## 8. Test obligations prepared now

The implementation gate must cover, at minimum:

- arbitrary ID is not authorization;
- duplicate/concurrent phase claim cannot produce two mutations;
- claim-to-apply replay is rejected;
- wrong target, wrong source, wrong artifact, wrong predecessor and stale run are rejected;
- UNKNOWN never becomes reusable;
- actual SSH master reuse is proven, socket/master loss never silently opens a fallback connection;
- known host-key mismatch stops before password authentication;
- normal one-reboot run uses two authentication epochs but only one production approval;
- HARD_STOP cannot be overridden; unknown CHECK_ID is HARD_STOP;
- public evidence is leak-tested against credentials/private locators;
- final outcome distinguishes device acceptance, operator-session cleanup and evidence completeness;
- actual packaged entrypoint runs without repository-only imports;
- existing F3/provision/F4/reboot regression suites remain green.

F5-7 exact release construction and all T1-B access remain later gates.

## 9. Stop point

Preparation is complete when this document and the exact manifest are committed on the dedicated branch rooted at
`9c81b889d97ed896b80d27af15069d16af0e0bdb`.

No product source implementation is authorized by this preparation record itself. The next gate is:

~~~text
N3W_T1_F5_PRODUCTION_PROCESS_V1_SOURCE_WORK_PACKAGE_IMPLEMENTATION_20261017_01
~~~
