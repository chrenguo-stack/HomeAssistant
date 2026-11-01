# N3W T1 F5 V1 量产流程架构合同冻结 — 2026-10-17

## 1. Gate

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V1_ARCHITECTURE_CONTRACT_FREEZE_20261017_01
RESULT=CONTRACT_FROZEN_ON_DOCS_CANDIDATE

BASE_MAIN=cdd597e43149e872e26f81c63bc72f4320e61bcc
BASE_MAIN_DRIFT=NONE_AT_GATE_START
F4_REPOSITORY_CLOSURE_FINAL=true

ASTRA_REVIEW_PATH=docs/development/N3W_T1_F5_PRODUCTION_PROCESS_V1_ARCHITECTURE_AND_SOURCE_DESIGN_ASTRA_REVIEW_20261017.md
ASTRA_REVIEW_REPO_BLOB=237f4400eab739aed89c9b65e793675bbc0832cd
ASTRA_REVIEW_UPLOAD_SHA256=0f7000cca761c8fe1b2905b722636665e731410967f67f4efe779182b0050f93

CONTRACT_SCOPE=F5_V1_ARCHITECTURE_AND_SOURCE_BOUNDARIES
PRODUCT_SOURCE_MUTATION=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~

This document accepts the independent Astra review as the main design input and freezes the F5 V1 contract below.
The Astra review itself remains a design review/evidence record; this document is the accepted project contract for the
next implementation stage once this docs candidate is merged to main.

No F3/F4 closure is reopened. No new known-failure record is created merely because planned F5 functionality is not yet implemented.

## 2. Frozen product-route position

The current production route remains ADR-0010:

~~~text
OFFICIAL_ARMBIAN_IMAGE_SELECTED
-> IMAGE_HASH_VERIFIED
-> PER_DEVICE_MEDIA_FLASHED
-> DEVICE_FIRST_BOOT_COMPLETED
-> HOST_READINESS_VERIFIED
-> AUTOMATED_PRODUCT_DEPLOYMENT
-> EXPLICIT_PRODUCT_PROVISIONING
-> PRODUCT_SERVICES_ACTIVATED
-> DEVICE_ACCEPTANCE_PASSED
-> USER_ONBOARDING / ACTIVE
~~~

F5 closes production-process repeatability and operator simplification. It does not restore Golden Master cloning, Final
Seal, raw-disk capture, clone acceptance, board validation, ESP32 registration or user onboarding.

## 3. F5 V1 architecture

~~~text
F5_ARCHITECTURE=
MAC_THIN_ORCHESTRATOR
+ TARGET_DURABLE_PRODUCTION_AUTHORITY
+ EXISTING_F3_PROVISION_F4_PRIMITIVES

F5_ORCHESTRATOR_LOCATION=MAC_OPERATOR_HOST
F5_NORMAL_OPERATOR_ENTRYPOINT=n3w-t1-production run --release <approved-release.json>
F5_ENGINEERING_RECOVERY_PATH=SEPARATE_FROM_NORMAL_PRODUCTION
F5_T1_LONG_RUNNING_PRODUCTION_DAEMON=false
~~~

Responsibilities are frozen as follows:

- Mac production orchestrator owns release validation, target selection, SSH session lifecycle, stage ordering,
  operator interaction, public-safe reporting and private run indexing.
- T1 production authority owns durable run/phase permission, target/release/predecessor binding, replay prevention and
  terminal run state. It does not reimplement F3/F4 business logic.
- Existing F3, provisioning, F4 activation/runtime/persistence/certificate/reboot tools remain the authoritative
  execution primitives.
- Existing repair commands remain engineering recovery surfaces and are not callable through the normal production path.

## 4. Production-run authorization

The old F3 R4 authorization ID is historical evidence and remains consumed/no-replay. F5 must not make a reusable
production package legal merely by accepting an arbitrary authorization string.

~~~text
F5_PRODUCTION_RUN_AUTH_MODEL=
AUTHENTICATED_EXPLICIT_RUN_APPROVAL_PLUS_TARGET_DURABLE_PHASE_CLAIMS

PRODUCTION_RUN_ID_REQUIRED=true
PRODUCTION_RUN_ID_IS_CAPABILITY=false
PRODUCTION_APPROVAL_COUNT=1
TARGET_DURABLE_LEDGER_REQUIRED=true
PHASE_CLAIMS_REQUIRED=true
REPLAY_ALLOWED=false
UNKNOWN_AUTHORITY_STATE=STOP
~~~

The V1 trust basis is:

~~~text
VERIFIED_SSH_HOST_IDENTITY
+ EXISTING_AUTHENTICATED_ADMIN_SSH_SESSION
+ EXPLICIT_OPERATOR_APPROVAL
+ EXACT_APPROVED_RELEASE
+ TARGET_DURABLE_RUN_LEDGER
~~~

F5 V1 does not add a factory PKI or a permanent per-device management key.

A production run must bind at least:

- run ID and plan/policy digest;
- exact source and approved release manifest;
- exact child package/image digests;
- public-safe target/install identity binding;
- trusted SSH host-key fingerprint;
- permitted phases and predecessor state;
- one reboot budget;
- claimed/consumed/no-replay state and terminal state.

The first durable target claim is the first authorized production mutation. A claimed or UNKNOWN phase is not reusable.
Changing the target, release or approved plan requires a new production approval.

## 5. Normal human interaction and SSH

The earlier one-password-for-the-whole-run target is superseded.

~~~text
F5_SSH_MODEL=ONE_PASSWORD_PER_CONNECTION_EPOCH
PRE_REBOOT_PASSWORD_PROMPTS=1
POST_REBOOT_PASSWORD_PROMPTS=1
NORMAL_FULL_RUN_PASSWORD_PROMPTS=2
PRODUCTION_AUTHORIZATION_PROMPTS=1
PASSWORD_PERSISTED=false
NEW_SSH_LOGIN_KEY=false
HOST_KEY_CHECKING=true
HOST_KEY_MISMATCH=STOP
UNKNOWN_SSH_ERROR=STOP
~~~

One normal production approval covers provisioning, activation, persistence, certificate checks and one planned reboot.
The post-reboot password prompt is authentication only; it is not a second production approval.

The first host key must be independently verified against a trusted local-console or private inventory fingerprint.
Network observation of the same unknown key is not proof of trust. `ssh-keyscan` may collect a candidate key but cannot
establish trust. A known-key mismatch must stop; normal production must not delete or silently replace the old key.

The Mac orchestrator owns ControlMaster/ControlPath. All ssh/scp transport in the normal path must use the same controlled
adapter and must fail rather than silently open an alternate authentication path. Success, failure and Ctrl-C all require
bounded cleanup of resources owned by that run.

## 6. Controlled override

~~~text
F5_OVERRIDE_MODEL=STATIC_CHECK_POLICY_STRICT_FAIL_CLOSED
F5_INITIAL_OVERRIDE_ALLOWLIST=EMPTY
UNKNOWN_CHECK_ID=HARD_STOP
UNKNOWN_FAILURE=HARD_STOP
GLOBAL_FORCE_INSTALL=false
PASS_WITH_OVERRIDE_SEMANTICS=PRESERVED
~~~

F5 V1 implements the policy/result mechanism without weakening the first clean production acceptance.

The existing 5 GiB F3 reserve remains strict in V1. The generic future dual-threshold design remains valid only after an
exact artifact/transport peak model and separate policy review prove a safe absolute minimum. Until then:

~~~text
CAPACITY_POST_PEAK_RESERVE_POLICY=HARD_STOP
F3_5_GIB_RULE=UNCHANGED
~~~

No item becomes OVERRIDABLE merely because it is inconvenient in production.

## 7. Release-environment binding

F5 release identity is broader than the three product-image digests.

An approved release must bind:

- product source head;
- Mac orchestrator and T1 primitive file/package digests;
- F3/F4/reboot package manifests;
- three exact ARM64 product image/content digests;
- supported Armbian/OS contract;
- approved Docker Engine / Compose package versions and source policy;
- check-policy digest and result-schema version;
- capacity/transport contract.

Normal production must not install an unreviewed later package version merely because it is the latest APT candidate.
If the approved version cannot be obtained, stop and create a new reviewed release rather than silently widening the
environment contract.

## 8. Evidence and result contract

F5 will define a stable production result schema with separate device acceptance and process acceptance.

~~~text
FINAL_OUTCOME=PASS|PASS_WITH_OVERRIDE|FAIL
DEVICE_ACCEPTANCE_RECORDED_SEPARATELY=true
OPERATOR_SESSION_CLOSED_RECORDED_SEPARATELY=true
EVIDENCE_COMPLETENESS_RECORDED_SEPARATELY=true
PUBLIC_PRIVATE_EVIDENCE_SPLIT=true
~~~

Public GitHub evidence is generated from a fixed allowlist. It may contain hashes, fingerprints, booleans and
non-sensitive relationship results, but not SSH passwords, private keys, MQTT plaintext passwords, raw private
locators, private credentials or unrestricted stdout/stderr.

UNKNOWN must remain UNKNOWN. It may imply `authorization_reusable=false` and `replay_allowed=false`, but the evidence
must not rewrite an unknown fact into a proven execution/non-execution claim.

## 9. T1-A / T1-B repeatability plan

~~~text
F5_REPEATABILITY_PLAN=B
T1A_DESTRUCTIVE_RETEST=false
T1B_FINAL_LIVE_ACCEPTANCE=true
THIRD_T1_REQUIRED=false
BOARD_ACCESS_REQUIRED=false
~~~

T1-A retains the already accepted F3/provisioning/F4/reboot evidence. T1-B is the fresh physical target for final F5 V1.

Minimum sufficient closure model:

1. final F5 release passes complete isolated tests on two independent fresh targets using the exact same release bytes;
2. T1-A existing accepted evidence remains bound and an A->B software-delta review identifies the approved F5 changes;
3. fresh T1-B runs the final normal F5 entrypoint from host readiness through one controlled reboot and durable acceptance;
4. software/config/service invariants are compared by release contract, not whole-disk hash;
5. OS/product/key identities that must be unique are proven different using public-key/fingerprint/relationship evidence,
   without exporting private secrets.

The accurate final statement is that the official fresh-install route has completed on two real devices and T1-B used
the final F5 V1 production entrypoint. It must not claim that T1-A was installed using the same final F5 artifact.

No second reboot, hours-long soak, power-cut test, third T1 or ESP32 board work is added by default. Add a targeted test
only if implementation or T1-B evidence exposes a concrete risk that requires it.

## 10. Failure and retry rules

Failures are classified at least as:

~~~text
PRECLAIM_FAILURE
CLAIMED_PREMUTATION_FAILURE
PARTIAL_MUTATION_FAILURE
POST_PROVISION_FAILURE
POST_ACTIVATION_FAILURE
POST_REBOOT_FAILURE
~~~

Rules:

- if both sides prove no claim, a read-only/preparation problem may be corrected without pretending a mutation occurred;
- after durable claim, the authority is consumed even if the product mutation has not yet happened;
- an unknown result never triggers automatic replay;
- source defects go back to repository repair, tests, new exact release and new authorization;
- target-local ad-hoc shell patches cannot count as formal acceptance;
- automatic cleanup is limited to resources explicitly owned by the run or rollback already owned by the reviewed
  primitive; no broad Docker prune, identity deletion, ledger deletion or disk wipe;
- T1-B is reflashed only when a clean fresh baseline can no longer be proven for the final full-path acceptance.
  Pure connection/evidence-finalization problems do not automatically require reflashing.

## 11. Minimum implementation scope

The next source work package is expected to add four logical modules, subject to fresh source design review:

~~~text
tools/n3w_t1_production.py
tools/n3w_t1_production_authority.py
tools/n3w_t1_ssh_transport.py
tools/n3w_t1_production_contract.py
~~~

Existing files are adapted only at their boundaries: F3 authorization/context, Mac staging transport, host-baseline
version policy, F2 integration, provisioning context, F4 parent-run binding, reboot parent-run/actuation binding,
package builders and relevant workflows/tests.

Principle:

~~~text
REUSE_EXISTING_F3_F4_LOGIC=true
REWRITE_F4_FOR_UI=false
NORMAL_PATH_REPAIR_COMMANDS=false
ONE_COHERENT_SOURCE_PR=true
~~~

## 12. Development and acceptance stages

The frozen route is:

~~~text
F5-0 ARCHITECTURE_CONTRACT_FREEZE
F5-1 PRODUCTION_RUN_AUTHORIZATION_GENERALIZATION
F5-2 PRODUCTION_ORCHESTRATOR_SOURCE
F5-3 SSH_CONNECTION_REUSE
F5-4 CONTROLLED_OVERRIDE_FRAMEWORK
F5-5 EVIDENCE_RESULT_SCHEMA
F5-6 UNIT_INTEGRATION_NEGATIVE_CI
F5-7 EXACT_PRODUCTION_RELEASE_BUILD_AND_BINDING
F5-8 T1-B_READONLY_PREFLIGHT
F5-9 T1-B_EXPLICIT_LIVE_AUTHORIZATION
F5-10 T1-B_FULL_PRODUCTION_PRE_REBOOT_ACCEPTANCE
F5-11 T1-B_REBOOT_AND_FINAL_ACCEPTANCE
F5-12 REPOSITORY_CONVERGENCE
~~~

F5-1 through F5-6 belong to one coherent source work package; they are not six separate production approvals or six
independent PRs. T1-B access remains separately authorized later.

## 13. Closed facts not reopened

~~~text
F3_R4_CLOSED_PASS=true
EXPLICIT_PROVISIONING_CLOSED_PASS=true
F4_RUNTIME_CLOSURE=PASS
F4_DURABLE_REBOOT_LEDGER=REBOOT_ACCEPTED
KF_121=CLOSED_PASS
PR608_MERGED=true
PR609_MERGED=true
F4_REPOSITORY_CLOSURE_FINAL=true
GOLDEN_MASTER_CLONE_ROUTE_RETIRED=true
~~~

Planned F5 work is not by itself a new known failure. A new KF is opened only if later evidence proves a real defect in
an already claimed current product behavior.

## 14. Next boundary

This gate is docs/design only. It does not authorize source implementation, T1-B access or merge.

After this exact contract candidate is reviewed and merged, the next source gate may implement F5-1 through F5-6 as one
coherent work package.

~~~text
NEXT_AFTER_CONTRACT_MERGE=
N3W_T1_F5_PRODUCTION_PROCESS_V1_SOURCE_WORK_PACKAGE_PREPARATION

AUTO_EXECUTE_NEXT_GATE=false
STOP=true
~~~
