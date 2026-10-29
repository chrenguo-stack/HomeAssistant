# N3-W R10 E03 Manager Successor Refresh — Live Executor Source Implementation Progress — 2026-10-29

```text
TASK=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_E03_MANAGER_SUCCESSOR_REFRESH_LIVE_EXECUTOR_SOURCE_IMPLEMENTATION_20261029_01
BASE_PR725_HEAD=73046d4f6fa83adca2221435855d4b7cd5665876
SOURCE_BRANCH=source/n3w-r10-e03-manager-refresh-executor-20261029

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
LIVE_APPLY_AUTHORIZED=false
LIVE_APPLY_EXECUTED=false
```

## Scope

This gate implements the source-only executor defined by:

`docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_E03_MANAGER_SUCCESSOR_REFRESH_LIVE_PREEXECUTION_DESIGN_20261029.md`.

No live T1 operation is authorized by this source gate.

## Implemented source

```text
tools/n3w_t1_r10_e03_manager_successor_refresh_live.py
tests/tools/test_n3w_t1_r10_e03_manager_successor_refresh_live.py
.github/workflows/n3w-r10-e03-manager-successor-refresh-live-source-ci.yml
```

The executor is a single versioned program used on both sides of the transport:

```text
Mac exact checkout
-> strict SSH ControlMaster
-> same source streamed over SSH stdin
-> sudo -n python3 -B - remote-preclaim
-> durable remote-claim
-> stream exact Manager tar to sudo -n docker load if target image absent
-> same durable transaction remote-apply
-> bounded postcondition / rollback
```

The executor script is never installed as a T1 program.

## Frozen transaction rules implemented

### Preclaim

Before claim:

- exact broker/services/registration-guard systemd state;
- exact installed services ExecStart/ExecStop;
- exact activation environment authority;
- exact live Compose render;
- exact predecessor Manager image ref and immutable image ID;
- exact HA and Broker images;
- all restart counts zero;
- predecessor image locally available;
- target image absent or exact;
- listener contract 8883/47110/47111 open and 47112 closed;
- running Manager Settings supply pairing and credential DB paths;
- container bind mounts translate those paths to host read-only rollback-classification paths;
- exact E03 failed-attempt public-safe identity/state;
- commit classification contract = DEFINITELY_NOT_COMMITTED;
- HA MQTT config-entry continuity SHA-256.

### Authorization claim

The first durable T1 write is the transaction claim.

The claim binds:

- gate-scoped authorization ID;
- explicit confirmation string;
- exact executor source head and blob;
- exact PR725 head;
- PR725 head must equal executor source head;
- target source/image/image ID/tar SHA;
- artifact ID and artifact digest;
- live Compose hashes;
- original Compose bytes in the private transaction;
- exact host-side DB paths derived from running Manager Settings/mounts;
- Broker baseline;
- HA MQTT continuity hash.

The transaction is one-shot:

```text
authorization_claimed=true
authorization_consumed=true
replay_allowed=false
```

A directory-level nonpersistent flock prevents concurrent remote apply.

### Artifact load

The Mac side verifies GitHub artifact metadata, binding.json and Manager tar SHA-256 before live transport.

Only after durable claim:

- exact target image already present -> reuse;
- otherwise Manager tar is streamed through the existing strict SSH epoch directly into `sudo -n docker load`.

A docker-load failure attempts a same-transaction `FAILED_PRESTOP` durable closure while proving live Compose remains predecessor state. If that closure cannot be proven, authorization state is UNKNOWN/no-replay.

### Compose mutation

Only `services.manager.image` may change.

The executor:

- edits only the Manager service image line;
- renders the candidate;
- deep-compares rendered Compose against the live render with exactly one permitted field change;
- performs atomic replace with fsync;
- never copies the repository Compose template over the T1 live Compose.

### Cutover

The only normal service mutation is:

```text
systemctl stop n3wfc4-services-activation.service
systemctl start n3wfc4-services-activation.service
```

Manager-only Compose recreate and direct Manager docker stop are forbidden.

Broker continuity is bound by exact container ID, image ID, StartedAt, restart count and 8883 listener.

### E03 success oracle

Success requires:

```text
attempt.state=EXPIRED
attempt.phase=TERMINAL
attempt.cleanup_state=COMPLETE
terminal_reason=expired
terminal_at_present=true

registration_count=0
registration_inventory_sha256=4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945
unresolved_count=0

pairing_session.state=expired
pairing_session.reason=expired
pairing_credential_count=0
hardware_credential_history_count=0
```

A remaining `registration_count=1` is explicitly rejected.

### Rollback

Rollback is software-only.

No SQLite bytes are restored and no database repair SQL exists in the executor.

After service-group stop, durable state is classified from host-visible SQLite paths that were derived before claim from the running Manager Settings and exact bind mounts.

Allowed classes:

```text
ORIGINAL_UNRESOLVED
REPAIR_COMPLETE
RESTARTABLE_REQUIRED
```

For allowed states, predecessor Manager may be restored through the same services systemd owner. Final rollback acceptance may be only:

```text
ORIGINAL_UNRESOLVED
REPAIR_COMPLETE
```

`RESTARTABLE_REQUIRED` must reconcile to COMPLETE before rollback can PASS.

Anything else is `EMERGENCY_STOP`; the executor does not edit the database.

## Authorization-state propagation

After a claim request may have reached T1:

- a proven transaction claim remains consumed/no-replay;
- an unobservable claim result becomes UNKNOWN/no-replay;
- post-success SSH cleanup failure remains consumed/no-replay;
- no generic exception path may reset the result to unconsumed.

## Focused regression intent

Focused tests cover:

- exact pre/post E03 state;
- false success when registration_count remains 1;
- rollback state classification;
- exact Manager-only Compose edit;
- non-Manager Compose drift;
- activation environment drift;
- gate-scoped authorization IDs;
- exclusive claim;
- live Settings/bind-mount path authority;
- artifact metadata and binding;
- strict SSH child no-auth-fallback;
- embedded remote Python compilation;
- read-only ledger probes;
- manager-only recreate prohibition;
- public-safe preclaim output;
- UNKNOWN authorization propagation;
- exact PR725/executor head binding;
- FAILED_PRESTOP closure;
- transaction apply lock.

## Current stop

```text
SOURCE_IMPLEMENTATION_WRITTEN=true
FOCUSED_CI_REQUIRED=true
INDEPENDENT_SOURCE_REVIEW_REQUIRED=true
PR725_INTEGRATION=false
LIVE_APPLY_AUTHORIZED=false
LIVE_APPLY_EXECUTED=false
```
