# N3W T1 Core Stack Clean Reference R3 pairing-readiness bridge source repair and identity-authority redesign closure

Date: 2026-11-02

~~~text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R3_PAIRING_READINESS_BRIDGE_SOURCE_REPAIR_AND_IDENTITY_AUTHORITY_REDESIGN_20261102_01
RESULT=CLOSED_PASS

SOURCE_REPAIR_HEAD=7b913c98e1eee3669fc356f01ea0b5ff098f9b66
EXACT_EXECUTABLE_BRIDGE_AUTHORITY=680d9efd0692de5ec06b184d961c8f3163765fab
BRIDGE_BLOB=92a9b5e1c3435eb0dd562c498878a1f65bcd808b
TEST_BLOB=2f9fe7c620595e23614bdf35505c29a8252b1afe

R2_COMMON_REFERENCE=CLOSED_PASS
OPTION_A_DIRECTION=RETAINED
PREVIOUS_LIVE_PREFLIGHT=STOP_PRECLAIM

SQLITE3_IMPORT_DEFECT=REPAIRED
REAL_SQLITE_EXECUTION_TESTED=true
DEVICE_READY_ASSUMPTION_REMOVED=true
DEVICE_PROVISIONING_REQUIRED_STATE=UNPROVISIONED
IDENTITY_AUTHORITY=clean_reference_runtime_identity_v1
EMPTY_PROVISIONING_ROOT_CREATION=false
OLD_F4_REPLAY=false

SUPERSEDED_CI_RUN=41364918910
SUPERSEDED_CI_SOURCE_TEST=SUCCESS
SUPERSEDED_CI_BUILD_JOB=CANCELLED
SUPERSEDED_CI_CANCEL_REASON=PR_SYNCHRONIZE_CONCURRENCY_CANCEL_IN_PROGRESS

FINAL_CI_RUN=41365086172
FINAL_CI_RESULT=SUCCESS
FINAL_SOURCE_TEST=SUCCESS
FINAL_TEST_COUNT=25
FINAL_BUILD_BRIDGE_PACKAGE=SUCCESS
FINAL_ARTIFACT_ID=13107271527
FINAL_ARTIFACT_DIGEST=sha256:ad7c1842f09282fca3347803f33c8ef7fc11111700b5da870e2a0bbeb3b83e70
FINAL_PACKAGE_MANIFEST_SHA256=92b5fc5a58ab81af4d66f72b4743aadd3e4576dad0edf8ccd294797205eda72e
R2_REFERENCE_SHA256=89da2a2b2cc1ce0fa024c3c45e24a71f09ba05e0e0cadbd67dd6387291239747

AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
FACTORY_ACCEPTED_CREATED=false
PAIRING_WINDOW_OPENED=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false

GATE_CLOSED=true
NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R3_PAIRING_READINESS_BRIDGE_REPAIRED_READONLY_PREFLIGHT_20261102_01
AUTO_EXECUTE_NEXT_GATE=false
~~~

## 1. Closure decision

The source-repair and identity-authority redesign gate is CLOSED_PASS.

The exact source defect was repaired without changing the frozen device-provisioning tool,
first-pairing onboarding tool, R2 activation/reboot authorities, or the R3 observer.

The bridge no longer treats the Clean Reference host as legacy DEVICE_READY. It requires the
frozen provisioning status to remain UNPROVISIONED and builds the pairing-readiness identity
binding from existing Clean Reference authorities.

## 2. Identity authority

The accepted identity chain is:

1. exact `fresh-release.json` product/release binding;
2. `host_instance_id` derived by the frozen OS identity algorithm from
   `/etc/machine-id` plus the Ed25519 SSH host public key;
3. `system_id` from the verified Manager initialization identity bundle;
4. Manager DB `h0h1_legacy_adoption_provenance.system_id_fingerprint` cross-binding;
5. frozen device-provisioning `status` proving the state remains UNPROVISIONED.

No empty provisioning root or fabricated DEVICE_READY transaction is used.

## 3. Provisioning-root contract

A missing `/var/lib/n3w-t1-provisioning` is valid for read-only preflight and means
UNPROVISIONED.

For a later separately authorized apply only, an absent root may be installed by first writing
`FACTORY_ACCEPTED.json` into a private temporary sibling directory and then atomically
renaming that already-populated directory into place. A bridge-created root is removed again
if post-marker validation fails.

No apply was executed in this gate.

## 4. CI cancellation classification

Run `41364918910` is not a source failure.

Its `source-test` job completed successfully. Before its package job could execute, a
subsequent PR synchronize event was created by the documentation-alignment commit. The workflow
uses a shared PR concurrency group with `cancel-in-progress=true`, so the older run was
cancelled and replaced.

The successor exact run `41365086172` completed successfully:

- source-test: SUCCESS;
- 25 tests PASS;
- build-bridge-package: SUCCESS;
- independent package verification: PASS;
- exact artifact id: `13107271527`;
- artifact digest:
  `sha256:ad7c1842f09282fca3347803f33c8ef7fc11111700b5da870e2a0bbeb3b83e70`;
- package-manifest SHA-256:
  `92b5fc5a58ab81af4d66f72b4743aadd3e4576dad0edf8ccd294797205eda72e`;
- exact bridge control head:
  `680d9efd0692de5ec06b184d961c8f3163765fab`;
- T1 access false;
- T1 mutation false;
- Board access false.

## 5. Preserved boundaries

The gate did not:

- claim or consume pairing-readiness authorization;
- create `FACTORY_ACCEPTED.json`;
- open the pairing window;
- access T1;
- access any Board;
- rerun old F4;
- merge PR #705.

The next gate is a repaired bridge read-only preflight only. It is not entered by this closure.
