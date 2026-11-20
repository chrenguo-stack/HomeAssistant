# N3-W T1 U11 R42 successor live recovery preauthorization closure

## Result

```text
R42_REVIEWED_SOURCE_HEAD=a05cf3b9dd36e239f5e873b2b6978466ce38ac3b
PR=807
PR_STATE=OPEN_DRAFT_UNMERGED
MAIN_HEAD=3e7faf258d670c9eaf3be6ede9bbb02df2ac009d

SOURCE_REVIEW=PASS
NEW_SOURCE_BLOCKER_COUNT=0
CI=16_OF_16_SUCCESS

HA_TARGET_BINDING_RUN=43888052480
HA_TARGET_BINDING_SOURCE=SUCCESS
HA_TARGET_BINDING_EXACT=SUCCESS
R42_FOCUSED_SUITE=805_PASSED

MANAGER_A_TO_B_RUN=43888052505
MANAGER_A_TO_B_SOURCE=SUCCESS
MANAGER_A_TO_B_EXACT=SUCCESS
MANAGER_A_TO_B_PRE_U1_SIMULATION=SUCCESS

R42_LIVE_RECOVERY_AUTHORIZED=false
R42_AUTHORIZATION_GRANTED=false
R40_REPLAY_PERMITTED=false
T1_ACCESS=false
LIVE_MUTATION=false
```

## Closed source design

R42 is a new one-shot successor recovery for the exact R41 post-R40 partial-U10 state. It is not an R40 replay.

The reviewed source requires the full R41 read-only predicate set before claim, a fresh R42 claimed/consumed/no-replay authorization ledger, and the full R41 predicate set again after claim before live mutation.

The recovery path does not reload the already present target Home Assistant image and does not rewrite the already published target Compose binding.

The repaired host, U11 controller definitions and repaired U11 host adapter are exact-bound and loaded into the remote Python process only. No repaired source is installed on T1 by R42.

The live mutation, if separately authorized later, is limited to starting the existing production systemd owner, proving exact Manager/Broker/Home Assistant runtime identity and production /config mount, persisting U11 metadata to USB first, then persisting the U11 host transaction.

R42 has no U12/U13 path and no board or merge action.

## Failure and ambiguity closure

Postclaim failures are no-replay and require a new recovery decision.

USB partial-write diagnosis compares all four transaction mirror files: manifest.json, phase.json, content-authority.json and checksums.json.

When a postclaim mutation cannot be observed reliably, the result is classified conservatively.

If U11 is already durably true but the final success ledger is missing or a failure ledger was written after the terminal transition, status reconciliation treats verified durable U11 as the terminal truth.

SSH result ambiguity uses read-only status reconciliation and never causes automatic live replay.

## Authorization boundary

The committed R42 manifest remains unauthorized:

```text
live_recovery_authorized=false
authorization_state.granted=false
authorization_state.claimed=false
authorization_state.consumed=false
authorization_state.replay_permitted=false
r40_replay_permitted=false
```

No real-T1 R42 execution is permitted from this preauthorization closure.

The next gate is a separate explicit one-shot user authorization for:

```text
AUTHORIZATION_ID=N3W_T1_CORE_UPDATER_HOMEASSISTANT_USB_U11_R42_20261116_01
CONFIRMATION=EXECUTE U11 R42 POST-R40 SUCCESSOR RECOVERY: YES
```

After explicit authorization, the grant must be committed as a grant-only manifest change, followed by fresh exact-head CI and final review before any real-T1 execution.
