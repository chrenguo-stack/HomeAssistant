# N3-W T1 KF-147 USB Confirmation U1→U4 Destructive Successor Source Design — 2026-11-10

## 1. Status

```text
FRESH_READONLY_BASELINE_GATE=CLOSED_PASS
BASELINE_AUTHORITY_PR=804
BASELINE_AUTHORITY_HEAD=bae46443ef34e34cc709a1af0de3599a739e806b

NEXT_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_USB_CONFIRMATION_U1_U4_DESTRUCTIVE_PREPARE_20261110_01
LIVE_EXECUTION_AUTHORIZED=true
USB_CONFIRMATION_AUTHORIZED=true
USB_ERASE_AUTHORIZED=true
USB_FORMAT_AUTHORIZED=true
U2_PLUS_AUTHORIZED=true
U5_PLUS_AUTHORIZED=false
MERGE=false
```

The second real-T1 read-only baseline passed with explicit release binding and fresh-candidate proof:

- U1 transaction SHA256: `6e1f0b5d262e346674b62ac79bf2ffbc1c63a8dd22379a0a82c952f0e3626b49`
- transaction ID SHA256: `ca89774eb4254d0f861cc2aef136eee41e90fd6106559c0fd8d66e3ee00a3738`
- release: `homeassistant-2026.10.4`
- prepare release: same
- U1 baseline public fingerprints: empty
- Extreme candidate fresh relative to U1 baseline: true
- candidate fingerprint: `e45fba0ad3e9997be2738c7a8f25d5c342ebba66ddbf822b1f6bf6a016c2ed93`
- candidate raw capacity: 32017047552 bytes
- required bytes: 4861841375
- recommended nominal capacity: 32 GB
- Manager / Home Assistant / Broker all running with restart count 0
- product host and Manager IPC V3 authority matched
- no USB mutation, U2+, image mutation, board access or merge occurred.

## 2. Why the successor scope is U1→U4, not only U2

The product implementation does not expose a bounded "format only then stop at U2" operation.

After a valid `CONFIRM_USB_ERASE` reaches the host prepare controller, `confirm_and_prepare()` executes one bounded worker sequence:

1. revalidate the single fresh eligible USB candidate;
2. recompute the capacity snapshot;
3. durably set prepare confirmation to consumed;
4. `wipefs --all --force`;
5. replace the partition table with GPT;
6. create one ext4 filesystem labelled `N3W-UPDATE`;
7. mount with `nodev,nosuid,noexec`;
8. write/fsync/read the USB self-test;
9. measure usable capacity;
10. write durable U2 media binding;
11. transition U2→U3;
12. download the exact Home Assistant 2026.10.4 artifact directly to the bound USB;
13. verify size, SHA256 and portable image identity;
14. fsync USB metadata and target;
15. transition to U4 / public `READY_TO_INSTALL`.

Therefore the destructive authorization must explicitly cover the full U1→U4 prepare sequence.

It does **not** cover U5 or later. The running Home Assistant, Manager and Broker images must remain unchanged throughout this gate.

## 3. Exact target binding

```text
CURRENT_HA=local/n3w-homeassistant:2026.10.0-0c73235a
TARGET_HA=local/n3w-homeassistant:2026.10.4-5881590f
TARGET_ARCHIVE_SHA256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
TARGET_ARCHIVE_SIZE_BYTES=835309535
ARTIFACT_URL=https://ota.hahub.top/n3w/homeassistant/releases/homeassistant-2026.10.4/homeassistant-arm64.tar.gz
```

The successor package inherits the repaired read-only baseline package and its host source-authority checks. Before any authorization claim it must again prove:

- exact U1 transaction SHA and transaction ID;
- exact release and target identity;
- prepare release binding;
- candidate fingerprint/model/capacity;
- candidate absent from U1 baseline identities;
- confirmation required=true / consumed=false;
- exact capacity-policy schema, required bytes and recommendation;
- exactly one safe physical USB candidate;
- Manager IPC V3 phase `USB_REQUIRED_CONFIRMATION`;
- required host units and all three containers running;
- zero restart-count drift;
- exact installed host source/policy/wiring authority;
- successor one-shot state root absent.

## 4. One-shot authorization boundary

The package is now committed with the user's fresh explicit authorization bound:

```text
live_execution_authorized=true
authorization_state.granted=true
authorization_state.claimed=false
authorization_state.consumed=false
authorization_state.replay_permitted=false
```

The authorization is exact-scope and one-shot. It is not reusable for any other candidate, transaction, release, or successor gate.

The bound authorization is:

```text
AUTHORIZATION_ID=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_USB_CONFIRMATION_U1_U4_DESTRUCTIVE_PREPARE_20261110_01
CONFIRMATION=EXECUTE KF147 USB CONFIRMATION U1 TO U4 DESTRUCTIVE PREPARE: YES
```

Before any product destructive submit, the executor creates a fresh root-owned 0700 one-shot state root and durably writes the authorization claim as consumed and non-replayable.

The executor then revalidates the U1/release/candidate/capacity state again. Only after that second check may it submit the product-owned `CONFIRM_USB_ERASE` action through the existing Manager UID 999 socket boundary.

The executor itself does not issue raw `wipefs`, `sfdisk`, `mkfs`, mount, systemd restart or Docker mutation commands. Physical USB mutation remains owned by the already-reviewed product host implementation.

## 5. Failure semantics

### Before authorization claim

Stop with no USB mutation and no consumed authorization.

### After authorization claim but before destructive submit acceptance

Stop. The gate authorization is consumed and may not be replayed. A fresh successor authorization is required.

### After destructive submit acceptance but before durable U2

The USB may be partially wiped, partitioned or formatted while the transaction can still remain U1.

Do not replay confirmation and do not assume rollback is possible. Stop and require a dedicated forensic/recovery gate.

### Failure in U2 or U3

The USB is already durably bound. Do not restart services or automatically retry within this gate. Stop and require a bounded recovery/resume gate.

### U4 success

Require all of the following:

- transaction phase `U4_READY_TO_INSTALL`;
- public phase `READY_TO_INSTALL`;
- target artifact verified=true;
- USB capacity verified=true;
- bound fingerprint still matches the authorized Extreme candidate;
- filesystem UUID and measured usable capacity valid;
- prepare confirmation required=false / consumed=true;
- current Manager / Home Assistant / Broker container IDs preserved;
- their restart counts remain zero;
- target archive exists on the bound USB;
- archive size and SHA256 exactly match the frozen target.

Then stop before U5.

## 6. Recovery and rollback rule

This gate deliberately has:

```text
automatic_retry=false
automatic_rollback=false
same_authorization_replay=false
```

Formatting destroys the previous contents of the selected USB and cannot be meaningfully rolled back.

The correct safety behavior after an interrupted destructive prepare is to preserve evidence, classify the exact observed phase and media state, and open a separate recovery gate.

No U5 installation request, predecessor recovery, HA quiesce, data backup, image cutover or production rollback is part of this gate.

## 7. Source package

```text
tools/execution_packages/n3w/r7a/kf147_usb_confirmation_u1_u4_successor/manifest.json
tools/execution_packages/n3w/r7a/kf147_usb_confirmation_u1_u4_successor/executor.py
tests/tools/test_n3w_t1_kf147_usb_confirmation_u1_u4_successor.py
```

The existing Home Assistant target-binding workflow is extended to compile and test this package.

## 8. Next bounded sequence

The physical execution path is intentionally collapsed into one continuous `--execute` invocation after authorization is bound.

1. exact-head source/CI review;
2. request a new explicit destructive authorization from the user;
3. bind that authorization in a new exact commit and rerun required CI;
4. invoke `--execute` once;
5. within that same invocation, run the full fresh read-only baseline first;
6. if the fresh baseline fails, stop before authorization claim and before any USB mutation;
7. if the fresh baseline passes, verify the one-shot state root is absent, then claim/consume the authorization;
8. revalidate U1/release/candidate/capacity again after claim;
9. submit `CONFIRM_USB_ERASE` and continue the product-owned U1→U4 prepare sequence;
10. stop at U4 or at the first failure/recovery boundary;
11. never replay the same authorization.

A separate real-T1 `--preflight-only` run is optional diagnostics only and is no longer a mandatory gate step. Combining fresh preflight and destructive execution reduces the time-of-check/time-of-use window between the final physical baseline and the destructive submit.
