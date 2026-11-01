# N3W T1 Production V2 standalone executable — deferred proposal archive

## 1. Status

~~~text
TASK=N3W_T1_PRODUCTION_V2_STANDALONE_EXECUTABLE_DEFERRED_PROPOSAL_20261022_01

CURRENT_PRODUCT_MAINLINE=N3W_T1_PRODUCTION_V2
CURRENT_PRODUCT_MAINLINE_STATUS=CLOSED_PASS

PROPOSAL=T1_PRODUCTION_V2_STANDALONE_EXECUTABLE
PROPOSAL_STATUS=DEFERRED_ARCHIVED_NO_EXECUTION
IMPLEMENTATION_STARTED=false
SOURCE_MUTATION=false
BUILD_PIPELINE_CREATED=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
PRODUCTION_EXECUTION=false
~~~

This proposal is intentionally archived for future work. It is not required for the
current T1 Production V2 engineering closure and does not reopen the accepted
production path.

## 2. Motivation

The current Production V2 path is functionally complete and real-T1 accepted, but
the operator-facing implementation is still script-oriented. The existing workflow
uses repository Python modules, a local launcher, PYTHONPATH, exact-release paths,
private run/evidence directories and interactive SSH/approval/reboot prompts.

The future goal is to present the same validated production state machine through
one operator-facing Mac executable without changing the exact-release authority or
the production safety model.

## 3. Recommended product shape

~~~text
n3w-t1-production-v2
+
n3w-t1-f5-v2-exact-production-release-<source>.zip
~~~

Recommended operator entry point:

~~~text
n3w-t1-production-v2 produce --release <exact-release.zip>
~~~

The executable should orchestrate the existing validated sequence:

~~~text
SELF_VERIFY
-> VERIFY_EXACT_RELEASE
-> TARGET_IDENTITY_AND_SSH_TRUST
-> STANDARD_FRESH_ARMBIAN_QUALIFICATION
-> NEW_PRIVATE_RUN
-> PRODUCTION_APPROVAL
-> HOST_BASELINE
-> F3_DEPLOY
-> PROVISION
-> F4
-> REBOOT_ARMING
-> CONTROLLED_REBOOT
-> SSH_EPOCH_2
-> POST_REBOOT_READINESS
-> STRICT_POST_REBOOT_ACCEPTANCE
-> MARKER_ACCEPTED
-> PUBLIC_PRIVATE_EVIDENCE_FINALIZATION
~~~

## 4. Architecture rule

Do not merge the executable and the exact production release into one opaque
production artifact.

The executable is the operator tool. The exact release remains a separate immutable
production authority with its own release/source identity and verification chain.

This preserves the current design property that:

- changing the operator tool does not silently change an already frozen exact release;
- changing the exact release does not require redefining the operator executable;
- release verification remains independent and fail-closed;
- production evidence remains bound to exact source/release/target/run identities.

## 5. Existing modules to preserve

The future implementation should wrap, not redesign, the validated V2 modules and
contracts, including the responsibilities currently carried by:

- production orchestration and result contract;
- live production executor;
- SSH transport and host-key binding;
- Standard Fresh Armbian qualification;
- exact-release verification;
- reboot authority and reboot verification;
- post-reboot readiness;
- strict post-reboot acceptance;
- failure forensics and evidence finalization.

The standalone executable must not weaken or bypass any current state-machine gate.

## 6. Operator-facing target

The future executable should remove the need for the operator to manually manage:

- PYTHONPATH;
- repository working-directory assumptions;
- temporary launch scripts;
- ad hoc known_hosts files;
- production-plan staging;
- evidence-root creation;
- execution-start locks;
- console-log paths;
- direct invocation of individual Python tools.

The intended operator experience is a single controlled command with explicit
interactive boundaries for production approval and reboot arming.

## 7. Security and privacy constraints

The executable must not embed or persist:

- T1 root passwords;
- raw private production run IDs in public output;
- MQTT credentials or setup secrets;
- private keys;
- fixed target IP addresses;
- operator-local private paths in public evidence.

Required behavior remains:

~~~text
PASSWORD_STORAGE=false
RAW_RUN_ID_PUBLICATION=false
FAILED_RUN_REPLAY=false
AUTOMATIC_RETRY=false
STRICT_HOST_KEY_BINDING=true
PRIVATE_EVIDENCE_MODE=0600
PUBLIC_EVIDENCE=SANITIZED_DIGEST_BOUND
~~~

## 8. Packaging direction

Preferred sequence when work resumes:

1. first create a repository-native single CLI entry point;
2. remove working-directory and PYTHONPATH assumptions;
3. make bundled-resource identity explicit and hash-bound;
4. add startup preflight for required host dependencies such as SSH;
5. preserve exact-release verification as a separate authority;
6. package the CLI as a standalone macOS executable;
7. add executable version/source/build identity reporting;
8. add CI for packaged-artifact construction and regression;
9. perform a fresh real-T1 executable-to-ACCEPTED validation.

A raw one-file packager invocation is not sufficient by itself. Packaging must be
treated as a production-path change because it can affect module loading, resource
paths, stdin/TTY ownership, subprocess behavior and SSH interaction.

## 9. Estimated engineering effort

~~~text
MINIMUM_USABLE_WRAPPER=1_TO_2_ENGINEERING_DAYS
RECOMMENDED_PRODUCTION_GRADE=3_TO_5_ENGINEERING_DAYS
FULL_PRODUCTIZED_MAC_DISTRIBUTION=5_TO_8_ENGINEERING_DAYS
~~~

Recommended future target:

~~~text
SCOPE=PRODUCTION_GRADE_STANDALONE_EXECUTABLE
ESTIMATE=3_TO_5_ENGINEERING_DAYS
GUI=false
APPLE_SIGNING_OPTIONAL_LATER=true
NOTARIZATION_OPTIONAL_LATER=true
AUTO_UPDATE_OPTIONAL_LATER=true
~~~

## 10. Acceptance requirement

The current T1 Production V2 CLOSED_PASS result does not automatically transfer to a
future packaged executable.

Before the executable becomes production authority it must complete, at minimum:

~~~text
PACKAGED_SOURCE_AND_RESOURCE_BINDING=PASS
PACKAGED_CI=PASS
EXACT_RELEASE_VERIFY=PASS
FRESH_T1_QUALIFICATION=PASS
REAL_T1_FULL_PRODUCTION=PASS
POST_REBOOT_ACCEPTANCE=PASS
MARKER_STATE=ACCEPTED
T1_PRODUCTION_READY=true
~~~

A fresh real-T1 full run is required because executable packaging can change runtime
behavior even when the underlying Python source is logically unchanged.

## 11. Re-entry gate

No implementation work is active.

When the project chooses to resume this proposal, begin with:

~~~text
NEXT_IF_RESUMED=N3W_T1_PRODUCTION_V2_STANDALONE_EXECUTABLE_ARCHITECTURE_DESIGN
REQUIRES_FRESH_REBIND=true
REQUIRES_CURRENT_PRODUCTION_V2_CONTRACT_REVIEW=true
AUTO_RESUME=false
~~~

The architecture-design gate must first rebind current main and current Production V2
contracts. This archived proposal is design intent, not future execution authority.
