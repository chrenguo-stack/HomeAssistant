# N3-W T1 F5-9 replacement run — live authorization preexecution

Date: 2026-10-19

~~~text
TASK=N3W_T1_F5_9_T1B_EXPLICIT_LIVE_AUTHORIZATION_REPLACEMENT_RUN_20261019_01
STATE=AUTHORIZED_READY_FOR_EXECUTION

AUTHORIZATION=N3W_T1_F5_9_T1B_EXPLICIT_LIVE_AUTHORIZATION_REPLACEMENT_RUN_20261019_01
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

TARGET_ROLE=T1-B
BOARD_ACCESS=false

PRODUCT_SOURCE_HEAD=9048dd7c6b48c0620471919c0cf96c96bdab71f1
PRODUCT_SOURCE_TREE=7b567c7140fd403049a6f7c2fa51887be08e8c8d
PRODUCT_SOURCE_CI=PASS_20_OF_20

RELEASE_BUILDER_HEAD=b2622cb7588d0224e1345abe84bd7aec307a2aae
RELEASE_ID=31c8a8cd2d8424f93aaa7b4d0b78cfe2b73f1b035f4bdbce08a181ac56619420
RELEASE_SHA256=1bbcb81bd84ec899e4c1d37fffef99defbbcc40509c49ce41048f6a6d92039ad
FILE_INDEX_SHA256=be36b3cd3f5a20099f870c55dcb78586e2e507fddc47bf5f589d85fab8091c83
ARTIFACT_ID=12162160866
ARTIFACT_ZIP_SHA256=1938ad3e4d7b87622a21968961b3fea4472907c4b31cc8db8c80acfd0fb149e8
ARTIFACT_EXPIRED=false
DURABLE_MAC_ARCHIVE=CLOSED_PASS

HISTORICAL_FAILED_RUN_STATE=TERMINAL_FAIL
HISTORICAL_FAILED_RUN_FAILURE_CLASS=FAILED
HISTORICAL_FAILED_RUN_REPLAY_ALLOWED=false
KF_122_RECOVERY=CLOSED_PASS

EXPECTED_NEW_RUN=true
EXPECTED_NEW_RUN_ID=true
REUSE_OLD_RUN=false
REUSE_RECOVERY_AUTHORIZATION=false
REBOOT_BUDGET=1
OVERRIDE_ALLOWLIST=EMPTY

LIVE_T1_MUTATION_AUTHORIZED=true
PRODUCT_SERVICE_START_AUTHORIZED=true
ONE_REBOOT_AUTHORIZED=true
BOARD_ACCESS_AUTHORIZED=false
MERGE=false
~~~

## Authorization scope

The user explicitly granted the named F5-9 replacement-run authorization after KF-122 recovery reached independent
postexecution read-only CLOSED_PASS.

This authorization is for one brand-new production run using the exact replacement release. It does not authorize
replay of the historical failed run, reuse of the consumed recovery authorization, target-local source patching,
additional reboot attempts beyond the frozen one-reboot budget, board access, or repository merge.

The normal F5 production orchestrator must perform a fresh target identity check and fresh read-only preflight before
the new target run is approved. The target production authority must allocate a new run ID and must reject any
nonterminal or UNKNOWN historical run for the same target.

The production run may execute the frozen phase sequence only:

~~~text
HOST_BASELINE
F3_DEPLOY
PROVISION
F4_PREPARE
F4_ACTIVATE
F4_ACCEPT
PERSIST_CERT
REBOOT_CONTROL
FINALIZE
CLOSE_RUN
~~~

The operator's in-process `START PRODUCTION RUN` confirmation is part of the frozen product contract and is not a
second engineering authorization. It is the concrete claim point for this already granted one-shot production
authorization.

If the run returns FAIL/STOP, disconnects unexpectedly, or the terminal becomes ambiguous after target claim, do
not start another production run. Preserve evidence and perform read-only adjudication first.
