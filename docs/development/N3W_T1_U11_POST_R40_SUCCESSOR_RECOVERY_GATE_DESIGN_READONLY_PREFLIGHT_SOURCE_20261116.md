# N3-W T1 U11 post-R40 successor recovery gate design + read-only preflight source — 2026-11-16

```text
TASK=N3W_T1_U11_POST_R40_SUCCESSOR_RECOVERY_GATE_DESIGN_READONLY_PREFLIGHT
PR=807
MAIN_HEAD=3e7faf258d670c9eaf3be6ede9bbb02df2ac009d
FRESH_REBIND_PARENT_HEAD=73666efc9730ff6a6804826ef575a072af4cd591
STATE_ALIGNMENT_AUTHORITY=ee59308270bd6658f6ae48f495a9cd56053201e9
SOURCE_REPAIR_AUTHORITY=155f9a7b62d6b758fb87c109b3ffbf54aa5614c7
SOURCE_REPAIR_CI=16_OF_16_SUCCESS
KF162=OPEN_ROOT_CAUSE_PROVEN_SOURCE_REPAIR_CI_CLOSED

R40_EXECUTION_ID=u11-r40-live02-20261116T063426Z
R40_RESULT=STOP_POSTCLAIM
R40_AUTHORIZATION_CLAIMED=true
R40_AUTHORIZATION_CONSUMED=true
R40_REPLAY_PERMITTED=false

LIVE_TRANSACTION_PHASE=U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED
LIVE_TRANSACTION_SHA256=c0dc58ebcfcd2876aec5bfcf556723ae779106803e19df5541b1847fc494bba3
USB_PHASE=U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED
TARGET_IMAGE_PRESENT=true
TARGET_RUNTIME_IMAGE_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
TARGET_BINDING_PUBLISHED=true
SERVICE_MUTATION=false
TRANSACTION_MUTATION=false
USB_MUTATION=false
U11_TRANSITION=false

NEXT_GATE=R41_POST_R40_SUCCESSOR_READONLY_PREFLIGHT
LIVE_RECOVERY_AUTHORIZED=false
R40_REPLAY=false
U12_AUTHORIZED=false
U13_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false
```

## 1. Fresh rebind

Repository state was rebound before design:

- `main` remains `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`;
- PR #807 remains OPEN / DRAFT / UNMERGED;
- branch `fix/kf147-u3-recovery-and-error-visibility-20261110` was rebound at
  `73666efc9730ff6a6804826ef575a072af4cd591`;
- that head is two commits ahead of `155f9a7b62d6b758fb87c109b3ffbf54aa5614c7`,
  with only closure/current-state/handoff alignment changes after the repair;
- therefore no updater source drift exists after the source-repair authority.

The governing failure remains KF-162. R40 is consumed and permanently no-replay.

## 2. Exact successor input state

R41 does not model the pre-R40 state and does not reuse R39 eligibility as a current fact.

It requires the exact partial state left by R40:

1. host transaction is still exact
   `U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED` with SHA-256
   `c0dc58ebcfcd2876aec5bfcf556723ae779106803e19df5541b1847fc494bba3`;
2. USB phase and all four U10 mirror hashes remain exact;
3. R38 success ledger is consumed/no-replay;
4. R40 claim/failure ledger is exact, consumed/no-replay and reports
   `STOP_POSTCLAIM` with the durable wrapper reason
   `U11PartialMutationError:ha_usb_u11_partial_mutation_requires_recovery:target_owner_start:UpdaterError`;
   this ledger proves the exact failed stage and underlying exception type, not the nested KF-162 message;
5. R40's observed mutation boundary is exact:
   target image load and target binding publication happened, while service,
   host transaction, USB and U11 phase mutations did not;
6. predecessor internal image remains absent;
7. target image is present with runtime ID
   `sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365`;
8. no Home Assistant target container exists;
9. Broker is still the exact running peer, Manager remains the exact stopped
   peer, and the services owner remains exactly failed/quiesced;
10. the production Home Assistant binding already points at
    `local/n3w-homeassistant:2026.10.4-5881590f`.

These conditions distinguish the successor from R39. R39 required target
absence and predecessor binding; those predicates are now intentionally false.

## 3. Exact target proof

Image-tag presence is not sufficient.

R41 re-parses the protected USB target archive with the existing portable-image
identity implementation and requires:

- exact archive SHA-256 and size;
- exact target tag and linux/arm64 platform;
- portable identity hash equal to the durable transaction's
  `target_artifact_identity.portable_identity_sha256`;
- the already-loaded Docker target to verify against that portable identity;
- Docker runtime image ID equal to the exact R40-observed target runtime ID.

This proves that the partial R40 target is the exact prepared artifact, not an
unrelated image sharing the same tag.

## 4. Repaired HA-OTA supervision proof

The T1-installed `n3w_t1_core_updater_host.py` remains the historical source
that produced the false drift. The preflight must not mutate live source just
to prove the repair.

R41 therefore binds the repaired repository files by Git blob and package
commit, transfers their exact bytes inside the read-only request, verifies their
SHA-256, and loads them only into the remote Python process memory.

The repaired `LocalHost` then performs only read-only operations:

- validate production activation environment;
- read `systemctl cat n3wfc4-services-activation.service`;
- apply systemd reset/replace semantics;
- require the exact U11 HA-OTA overlay `ExecStart`;
- require the exact U11 HA-OTA overlay `ExecStop`;
- reject `--force-recreate`.

It does **not** call `start_target_owner()`, `controller.install()` or
`systemctl start`.

Thus the preflight proves the effective supervision contract while keeping
`/opt/HomeAssistant` unchanged.

## 5. Recovery and capacity proof

The existing bound USB/recovery checks remain mandatory:

- same bound filesystem UUID;
- exact U10 mirror;
- target archive continuity;
- predecessor recovery archive continuity;
- protected Home Assistant backup continuity;
- fresh USB recovery-capacity calculation.

Because R40 has already loaded the target internally, the old pre-load formula
(`target import worst-case allowance + post-peak reserve`) is no longer the
correct current-state predicate. R41 instead requires the frozen post-load
internal reserve of 1,610,612,736 bytes.

## 6. Read-only execution order

```text
installed historical source hashes
-> exact U10 host transaction
-> R38 consumed/no-replay ledger
-> R40 consumed/no-replay STOP_POSTCLAIM ledger
-> bound USB UUID
-> exact U10 USB mirror
-> recovery assets + protected backup + USB capacity
-> exact partial runtime/binding/target portable identity
-> repaired effective HA-OTA supervision contract
-> post-target-load internal reserve
-> R41 READONLY PASS
```

No eligibility result is emitted before all checks pass.

## 7. Mutation exclusion

The stable execution package lives at
`tools/execution_packages/n3w/r7a/u11_postclaim_recovery_readonly_preflight/`.
R41 is a gate/evidence identifier, not a code-module version suffix.

The executor has no `--execute`, authorization-id or confirmation arguments
and no successor authorization claim.

The remote payload contains no target load/delete, Compose binding write,
`systemctl start/restart/reset-failed`, transaction/USB persistence,
U11 transition, U12/U13 action, board access or merge operation.

A PASS means only:

```text
SUCCESSOR_LIVE_RECOVERY_ELIGIBLE=true
SUCCESSOR_LIVE_RECOVERY_AUTHORIZED=false
R40_REPLAY=false
```

It does not complete U11 and does not authorize a service start.

## 8. Failure boundary

Any mismatch is fail-closed. The executor returns STOP and leaves all product
mutation flags false.

A future live successor, if separately authorized, must consume a **new**
one-shot recovery authorization and start from the exact R41 evidence. It must
not replay R40. U12/U13 remain separate later gates.

## 9. Source artifacts

- `tools/execution_packages/n3w/r7a/u11_postclaim_recovery_readonly_preflight/executor.py`
- `tools/execution_packages/n3w/r7a/u11_postclaim_recovery_readonly_preflight/manifest.json`
- `tests/tools/test_n3w_t1_u11_postclaim_recovery_readonly_preflight.py`

Real-T1 R41 evidence must be archived separately after execution. This source
document is not physical proof and does not change KF-162 to CLOSED_PASS.


## 10. R41 real-T1 Attempt 01 transport failure and bounded repair

Real-T1 Attempt 01 used execution ID
`u11-r41-readonly-20261116T110710Z` and stopped before remote Python
execution.

Observed transport evidence:

```text
REMOTE_RETURNCODE=1
STDOUT_LENGTH=0
STDERR=/usr/bin/bash: Argument list too long
```

No R41 predicate ran and no product mutation occurred. The failure was caused by
passing the inherited remote program plus the base64-encoded repaired source
payload through the SSH remote command argv. The combined argv exceeded the
remote shell argument-size limit.

The bounded repair keeps the same read-only contract and does not stage files
on T1. R41 now sends a minimal remote command, `python3 -B -`, and streams the
Python program plus plan through the existing authenticated SSH master on
standard input. The repaired source remains process-memory-only.

A focused regression uses a synthetic plan containing more than 400 KiB of
payload and proves that the SSH argv remains below 4 KiB while the large program
is delivered through stdin.

Attempt 01 does not consume or authorize any live recovery action. A later
Attempt 02 remains R41 read-only only.


## 11. R41 real-T1 Attempt 02 ledger-model mismatch and bounded repair

Real-T1 Attempt 02 used execution ID
`u11-r41-readonly02-20261116T114901Z` and returned a read-only STOP:

```text
STATUS=STOP
REASON=Stop:u11_r41_r40_consumed_failure_ledger_invalid
REMOTE_RETURNCODE=2
MUTATION=false
```

The T1 state did not drift. The R41 predicate was wrong.

R40 executes the U11 controller. Once mutation has begun, the controller catches
the underlying exception and deliberately raises
`U11PartialMutationError`, preserving the failed stage
(`target_owner_start`) and the underlying exception type (`UpdaterError`) but
not the nested exception message. R40 therefore durably stored:

```text
U11PartialMutationError:ha_usb_u11_partial_mutation_requires_recovery:target_owner_start:UpdaterError
```

R41 had incorrectly required the durable ledger's top-level `reason` to equal
`UpdaterError:services_supervision_contract_drift`. That nested message cannot
exist in the R40 failure ledger by construction.

The repair keeps fail-closed exactness. R41 now verifies the exact R40 remote
schema, exact durable wrapper reason, exact consumed/no-replay claim, exact
partial-mutation boundary, phases, binding, and quiesced service state. KF-162's
specific `services_supervision_contract_drift` root cause remains established
by the bound source-repair authority and is independently tested by the R41
in-memory repaired supervision probe. The durable ledger is no longer asked to
prove information that it does not encode.

Attempt 02 authorizes no live action and consumes no successor recovery
authorization.
