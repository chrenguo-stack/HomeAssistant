# N3W T1 F5 V2 post-reboot Home Assistant MQTT readiness race source repair

Date: 2026-10-24

## 0. Gate

```text
TASK=N3W_T1_F5_V2_POST_REBOOT_HA_MQTT_READINESS_RACE_SOURCE_REPAIR_20261024_01
BASE_MAIN=b31d86a66d7c4fc10370606b610aab3203a91d94
BASE_TREE=4db4db8c0349e9dbf83294f91798f8d25aa4b556
KF_130=F5_V2_POST_REBOOT_HA_MQTT_READINESS_RACE
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
REFLASH=false
MERGE=false
```

## 1. Live evidence

A fresh-Armbian F5 V2 production run passed HOST_BASELINE, F3_DEPLOY, PROVISION,
all F4 preparation/activation/acceptance/persistence/certificate stages, controlled
reboot, SSH epoch 2 and POST_REBOOT_READINESS.

It then failed immediately in POST_REBOOT_ACCEPTANCE with:

```text
error_code=homeassistant_mqtt_socket_missing
error_class=POST_REBOOT_ACCEPTANCE_FAIL_REFLASH_REQUIRED
target_failure_class=VERIFY_FAILED
marker_state=STARTED
T1_PRODUCTION_READY=false
evidence_complete=true
reflash_required=true
```

The public-safe failed-run binding is:

```text
run_id_sha256=e1d2155f11f1c30adfbf97327a51ecdad3e8de47e58f4fd22ed2de64c3a0bc12
release_id=eddccfab855efca2a4804e234358dc7c9cae32868532d73b80f25ad5994f2cbe
source_head=b31d86a66d7c4fc10370606b610aab3203a91d94
```

Frozen failure forensics had no unavailable probes.

After the terminal run fully closed, two read-only runtime snapshots taken 15 seconds
apart both returned PASS. They showed the same boot identity, the same three container
identities, restart_count=0 for broker/manager/homeassistant, Home Assistant HTTP ready,
authenticated current Broker evidence for both Manager and Home Assistant, Manager
owned_socket_count=1 on 8883 and Home Assistant owned_socket_count=1 on 1883. Socket
fingerprints and authenticated-connection fingerprints were stable across both snapshots.

Therefore persistent Home Assistant MQTT failure is not supported by the evidence.

## 2. Root cause

The existing KF-125 readiness repair correctly prevents SSH readiness from entering
strict acceptance before systemd units, certificate lifecycle and the expected runtime
container set have converged.

However, its READY condition does not include runtime MQTT session convergence.

Current ordering can therefore be:

```text
containers running
-> POST_REBOOT_READINESS PASS
-> strict target verifier
-> Home Assistant HTTP readiness PASS
-> one-shot Home Assistant MQTT socket count == 0
-> homeassistant_mqtt_socket_missing
-> terminal reflash-required false FAIL
```

The later PASS snapshots prove that the MQTT session can converge without any target
mutation, container restart or repair.

This is a successor blocker to KF-125, not a reopening of KF-125.

## 3. Repair contract

Extend the existing read-only POST_REBOOT_READINESS barrier after the expected runtime
service set is complete:

```text
Manager MQTT established socket count:
  0 -> WAIT manager_mqtt_socket_not_ready
  1 -> ready for this check
  >1 -> FAIL manager_mqtt_socket_count_invalid

Home Assistant MQTT established socket count:
  0 -> WAIT homeassistant_mqtt_socket_not_ready
  >=1 -> ready for this check
```

The probes use the same container-local socket authority already used by the strict F4
verifier. No credential, Broker log, raw address or target mutation is added.

A disappearing socket after READY remains a strict acceptance failure. The readiness
barrier only prevents strict verification from starting before the required MQTT sessions
have ever converged.

## 4. Preserved contracts

The repair does not change:

- the 300 second readiness timeout or 2 second polling cadence;
- one post-reboot SSH epoch and password boundary;
- one production approval and one reboot arming boundary;
- full target-local reboot verification exactly once after readiness PASS;
- external TCP/TLS/SNI/negative-auth/Home Assistant probes;
- runtime authenticated-session evidence;
- the existing 90 second continuity observation;
- marker ACCEPTED only after full acceptance PASS;
- failed-run no-replay and reflash-required semantics;
- F3, provisioning, F4 activation business logic, Board firmware or pairing logic.

## 5. Focused tests

Required regression coverage:

1. Manager socket count 0 => WAIT.
2. Home Assistant socket count 0 => WAIT.
3. Manager socket count >1 => immediate FAIL.
4. Home Assistant socket count >1 remains acceptable, matching strict verifier semantics.
5. MQTT convergence WAIT reasons are accepted by the Mac executor.
6. Existing systemd/unit/certificate/runtime-service WAIT/FAIL semantics remain unchanged.
7. Strict verifier and 90 second observation remain unchanged.

## 6. Release consequence

The failed production run is terminal and is never replayed. Even if source repair passes,
the current T1 remains reflash-required for production authority.

A future live attempt requires:

```text
SOURCE_REPAIR
-> INDEPENDENT_SOURCE_REVIEW
-> CI PASS
-> MERGE
-> F3/F4 exact artifact rebuild
-> release-inputs rebuild
-> final exact release rebuild
-> Mac local verify-bundle
-> reflash T1
-> Standard Fresh Armbian qualification
-> NEW run ID / production approval
-> full F5 V2 production acceptance
```

Board D and dynamic first-pair acceptance remain blocked until the new F5 V2 run reaches
MARKER_ACCEPTED / T1_PRODUCTION_READY=true.


## 7. Source implementation and closure

```text
SOURCE_TEST_AUTHORITY=d63cba066201df355bf9ceb0fbb330c00dfee24d
SOURCE_TEST_TREE=58feb07d69aea49003f5549c5a184367f6423709
PR=665
CI=14/14_SUCCESS
F4_FOCUSED_TESTS=167_PASS
F5_V2_R3_FOCUSED_TESTS=202_PASS
NEW_SOURCE_BLOCKER_COUNT=0
SOURCE_REPAIR=CLOSED_PASS
MERGE=false
```

Independent final review confirmed:

- Manager MQTT 0 remains WAIT, exactly 1 permits continuation, and >1 fails closed.
- Home Assistant MQTT 0 remains WAIT and >=1 matches the unchanged strict verifier.
- readiness socket checks are read-only and reuse the existing container-local socket authority.
- malformed runtime container names fail closed with a sanitized repository-defined code.
- target-side and Mac-side error-code allowlists remain aligned.
- strict target-local reboot verification remains unchanged and still executes after readiness.
- external probes, authenticated runtime evidence and the existing 90-second observation remain unchanged.
- no third SSH epoch, additional approval, Board access or target mutation was introduced.
- failed-run no-replay and reflash-required semantics remain unchanged.

The first implementation head had a tooling-only executable-mode regression; it was
repaired before closure. The final source/test authority retains
`tools/n3w_t1_f4_reboot_verify.py` mode `100755`.

KF-130 remains live-revalidation-pending after merge/rebuild; source closure alone does
not make the current failed T1 production-ready.
