# N3-W R10 E03 Manager successor refresh readonly preflight source design — 2026-10-29

## 1. Scope

This source gate prepares only the read-only T1 preflight required before a later separately authorized Manager successor refresh.

It does not load an image, stop/start/restart any service, edit Compose/env/state, mutate SQLite, access a board, retry pairing, merge PR #725, or merge to main.

The exact repaired Manager successor artifact is already closed-pass:

```text
SOURCE_HEAD=f8876fd87165df731d792690a8288867c3eeef55
SOURCE_TREE=a8a04ae5ae551d637ca1c959ad59778c9ba89dae
RUN_ID=40880705472
ARTIFACT_ID=12900601779
ARTIFACT_NAME=n3w-t1-fresh-exact-arm64-f8876fd87165df731d792690a8288867c3eeef55
ARTIFACT_DIGEST_SHA256=c94568f740b911eee0f4238207249b1e98f84748c17a902938ccc35293e4b183
MANAGER_IMAGE=local/greenhouse-manager:fresh-f8876fd87165
MANAGER_IMAGE_ID=sha256:089153fa4bbc823a1357427083f23ef96933a119c6ae150c143b62d7b40859e4
MANAGER_TAR_SHA256=d129a33ea628d8bdd1361e0b1bf727175515b4a2afc1851e6ac14ec510895fb5
```

## 2. Why the historical Manager-only recreate path is forbidden

The current production services owner is:

```text
n3wfc4-services-activation.service
```

Its foreground lifecycle is:

```text
docker compose ... --abort-on-container-exit manager homeassistant
```

KF-129 already proved that an out-of-band Manager-only Compose recreate causes the foreground service owner to abort and stop Home Assistant.

Therefore the old KF-098 pattern and any normal-path:

```text
docker compose ... --force-recreate manager
```

must not be reused for this refresh.

A later live refresh, if authorized, must preserve the production supervision model. Manager and Home Assistant are stopped/started together by their systemd owner while Broker remains running. Only the Manager image binding may change.

This document does not implement or authorize that live mutation.

## 3. Why the older successor-recover database flow is not the authority

The historical onboarding `successor-inspect/successor-recover` path targets the older `pairing_sessions` / expired-registration recovery model.

KF-131 is different. The proven failed object is the R10 first-registration ledger:

```text
registration_count=1
attempt_count=1
unresolved=1
attempt.state=ACTIVE
attempt.phase=BOOTSTRAP_ACCEPTED
attempt.cleanup_state=NONE
attempt.expires_at already elapsed
pairing window=CLOSED
TCP/47112=closed
```

The R10 repaired Manager starts `FirstRegistrationReconciler.reconcile_startup()` before accepting new registration work.

For an `ACTIVE + BOOTSTRAP_ACCEPTED` attempt that has no registration/credential binding, classification is `DEFINITELY_NOT_COMMITTED`.

When startup time is at or beyond `expires_at`, reconciliation transitions that attempt to:

```text
state=EXPIRED
phase=TERMINAL
terminal_reason=expired
cleanup_state=REQUIRED -> COMPLETE
```

and performs the normal terminal cleanup through `RegistrationRegistry.reconcile_first_registration_terminal()`.

Therefore:

- no manual database edit is allowed;
- no old `successor-recover` mutation is allowed;
- the later Manager restart itself is the repaired startup reconciliation trigger;
- the post-refresh gate must prove the failed ledger row is terminal/clean and unresolved count is zero.

## 4. Read-only preflight implementation

New tool:

```text
tools/n3w_t1_r10_e03_manager_successor_refresh_preflight.py
```

Schema:

```text
gh.n3w-r10-e03-manager-successor-refresh-preflight/1
```

The tool is deliberately read-only.

It checks:

1. `n3wfc4-broker-activation.service` active + enabled;
2. `n3wfc4-services-activation.service` active + enabled;
3. registration ingress guard active;
4. exactly one running Compose-owned Broker, Manager and Home Assistant;
5. Manager + Home Assistant remain host-networked;
6. all three runtime restart counts remain zero;
7. current Manager image ref is still the last-proven deployed predecessor:
   `local/greenhouse-manager:fresh-ff750b3801a2`;
8. TCP/8883 count=1;
9. TCP/47110 count=1;
10. UDP/47111 count=1;
11. TCP/47112 count=0;
12. Manager SQLite is opened with URI `mode=ro` and `PRAGMA query_only=ON`;
13. `registration_count=1`;
14. `attempt_count=1`;
15. `unresolved_count=1`;
16. the only attempt is:
    - ACTIVE;
    - BOOTSTRAP_ACCEPTED;
    - cleanup NONE;
    - expired by clock;
    - no node_id;
    - no terminal timestamp/reason;
    - no RegistrationRegistry row using the failed attempt pairing ID;
17. the report emits only the pairing-ID SHA-256 and stored hardware-ID SHA-256, never the raw pairing ID;
18. the report binds the intended successor source/artifact/image ID/tar SHA.

The preflight contains no live refresh command.

## 5. Source-level mutation exclusions

The focused CI fails if the preflight source contains any of:

```text
docker load
--force-recreate
systemctl stop
systemctl start
systemctl restart
docker compose
```

The focused tests also prove the command trace produced by a passing preflight contains none of these operations.

## 6. Expected read-only PASS report

A real T1 pre-live PASS must establish fresh evidence. Historical values alone do not pass.

Expected high-level result:

```text
status=PASS
mutation=false
authorization_claimed=false
authorization_consumed=false
t1_mutation=false
board_access=false

current_manager_image_ref=local/greenhouse-manager:fresh-ff750b3801a2

registration_count=1
attempt_count=1
unresolved_count=1
attempt_state=ACTIVE
attempt_phase=BOOTSTRAP_ACCEPTED
attempt_cleanup_state=NONE
attempt_expired_by_clock=true
attempt_registration_match_count=0

tcp_47112=0

target_source_head=f8876fd87165df731d792690a8288867c3eeef55
target_manager_image_id=sha256:089153fa4bbc823a1357427083f23ef96933a119c6ae150c143b62d7b40859e4
target_manager_tar_sha256=d129a33ea628d8bdd1361e0b1bf727175515b4a2afc1851e6ac14ec510895fb5
artifact_id=12900601779
artifact_digest_sha256=c94568f740b911eee0f4238207249b1e98f84748c17a902938ccc35293e4b183
```

Any drift is STOP, not an invitation to repair the live host inside the read-only gate.

## 7. Later live refresh contract — design only

A later separately authorized mutation executor must:

1. consume fresh readonly-preflight evidence;
2. independently verify the 2.54 GB artifact and Manager tar before mutation;
3. capture the exact current Compose/env/runtime identities and rollback authority;
4. keep Broker running and unchanged;
5. use the existing systemd supervision owner for Manager + Home Assistant;
6. atomically change only the Manager image binding in the production Compose env;
7. stop/start the application services through `n3wfc4-services-activation.service`, not out-of-band Manager-only Compose;
8. prove new Manager exact image identity;
9. prove Home Assistant returns with the same persisted MQTT integration and Broker identity unchanged;
10. prove startup reconciliation converted the exact failed ACTIVE attempt to EXPIRED/TERMINAL with cleanup COMPLETE;
11. prove unresolved=0;
12. prove registration_count remains 1;
13. prove TCP/47112 remains closed after refresh;
14. rollback the old Manager image binding through the same systemd supervision owner on any failed postcondition;
15. never manually edit the first-registration ledger;
16. never open 47112 manually;
17. never replay a consumed authorization.

The live executor and live authorization are intentionally not part of this source gate.

## 8. Gate state

```text
SOURCE_BASE=f8876fd87165df731d792690a8288867c3eeef55
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
BOARD_MUTATION=false
LIVE_REFRESH=false
MAIN_MERGE=false
PR725_MUTATION=false
PHYSICAL_RETRY=false
CONSUMED_AUTHORIZATION_REPLAY=false
```

Next after source/CI closure:

```text
N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_E03_MANAGER_SUCCESSOR_REFRESH_READONLY_T1_PRELIVE_20261029_01
```

That next gate is read-only only. It still does not authorize the Manager refresh.
