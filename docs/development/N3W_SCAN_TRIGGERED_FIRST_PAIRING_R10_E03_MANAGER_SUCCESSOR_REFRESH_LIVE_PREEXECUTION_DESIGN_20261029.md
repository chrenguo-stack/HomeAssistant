# N3-W R10 E03 Manager Successor Refresh — Live Preexecution Design — 2026-10-29

```text
TASK=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_E03_MANAGER_SUCCESSOR_REFRESH_LIVE_PREEXECUTION_DESIGN_20261029_01
DESIGN_STATUS=FROZEN_FOR_SOURCE_IMPLEMENTATION
PRODUCT_MANAGER_SOURCE_CHANGE=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
LIVE_REFRESH_EXECUTED=false
```

## 1. Purpose

This document freezes the live-refresh transaction required to replace the currently running R10 Manager predecessor with the exact E03-repaired Manager successor.

The live refresh has one product objective:

> Start the exact repaired Manager under the existing production supervision owner so startup reconciliation can safely terminalize and clean the single known expired first-registration transaction that currently causes E03/registration_busy.

This document does not authorize or execute the live mutation.

## 2. Frozen source and artifact authority

```text
PR725_HEAD=c50a4f8e1de376a15941ba57ef93bff34ecb3bc0

E03_REPAIR_SOURCE_HEAD=f8876fd87165df731d792690a8288867c3eeef55
TARGET_MANAGER_IMAGE=local/greenhouse-manager:fresh-f8876fd87165
TARGET_MANAGER_IMAGE_ID=sha256:089153fa4bbc823a1357427083f23ef96933a119c6ae150c143b62d7b40859e4
TARGET_MANAGER_TAR_SHA256=d129a33ea628d8bdd1361e0b1bf727175515b4a2afc1851e6ac14ec510895fb5

TARGET_ARTIFACT_ID=12900601779
TARGET_ARTIFACT_DIGEST_SHA256=c94568f740b911eee0f4238207249b1e98f84748c17a902938ccc35293e4b183
TARGET_ARTIFACT_NAME=n3w-t1-fresh-exact-arm64-f8876fd87165df731d792690a8288867c3eeef55
TARGET_ARTIFACT_FILE=greenhouse-manager-arm64.tar
```

The exact artifact workflow already performed post-upload re-download and SHA-256 revalidation. The live executor must independently verify the downloaded Manager tar SHA-256 before any T1 mutation.

## 3. Frozen predecessor authority from readonly T1 pre-live R2

The readonly R2 probe passed and established:

```text
CURRENT_MANAGER_IMAGE_REF=local/greenhouse-manager:fresh-ff750b3801a2
CURRENT_MANAGER_IMAGE_ID=sha256:5b8150e457a1cc5af3e7e576514dfb3fa33e15f4dfe4801640ec604dd962218f
CURRENT_MANAGER_RESTART_COUNT=0

CURRENT_HOMEASSISTANT_IMAGE_REF=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_HOMEASSISTANT_IMAGE_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306
CURRENT_HOMEASSISTANT_RESTART_COUNT=0

CURRENT_BROKER_IMAGE_REF=local/n3w-mosquitto:2.1.2-3184566d
CURRENT_BROKER_IMAGE_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
CURRENT_BROKER_RESTART_COUNT=0
```

Public-safe first-registration authority:

```text
FAILED_PAIRING_ID_SHA256=9931c366d483abd3af6e1e3d903b82645542346dbd258975acd788998f0404dc
FAILED_HARDWARE_ID_SHA256=3a76b39f066e09de0a285b81319eec20f29c8fd4136b61dc5a86ace01c1e1d55

ATTEMPT_STATE=ACTIVE
ATTEMPT_PHASE=BOOTSTRAP_ACCEPTED
ATTEMPT_CLEANUP_STATE=NONE
ATTEMPT_EXPIRED_BY_CLOCK=true
ATTEMPT_NODE_ID_PRESENT=false
ATTEMPT_REGISTRATION_MATCH_COUNT=1

PAIRING_SESSION_STATE=pending
CURRENT_PAIRING_MATCHES=true
REGISTRATION_NODE_ID_PRESENT=false
PAIRING_CREDENTIAL_COUNT=0
HARDWARE_CREDENTIAL_HISTORY_COUNT=0

COMMIT_CLASSIFICATION=DEFINITELY_NOT_COMMITTED
REGISTRATION_COUNT=1
REGISTRATION_INVENTORY_SHA256=2ac5373cc532499154fffdd42e14f6225cc2ebdd90deb0a5bacdda3ec3ccaaed
UNRESOLVED_COUNT=1
```

Listener baseline:

```text
TCP_8883=1
TCP_47110=1
UDP_47111=1
TCP_47112=0
```

## 4. Root product defect and successor behavior

KF-131 is not a database corruption repair.

The predecessor created the durable ACTIVE transaction before the identity-bound pairing window was successfully opened, but autonomous deadline ownership did not begin until the later window-open path. A failure before that handoff could leave a durable expired ACTIVE transaction without a deadline owner.

The successor repair changes first-registration transaction deadline ownership. It does not redesign the reconciler.

A direct source comparison from predecessor product source `ff750b3801a282af1667b5fa63481e2333e301b3` to repaired source `f8876fd87165df731d792690a8288867c3eeef55` shows product Manager code changes only in:

```text
host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_first_registration_transaction.py
host/greenhouse-manager/tests/runtime/test_n3w_first_registration_transaction.py
```

The first-registration reconciliation implementation is unchanged between predecessor and successor.

## 5. Exact startup reconciliation expected state transition

The current attempt is proven `DEFINITELY_NOT_COMMITTED`.

At successor Manager startup, `FirstRegistrationReconciler.reconcile_startup()` must process the expired ACTIVE attempt.

Expected durable transition:

```text
first_registration_attempts:
  state: ACTIVE -> EXPIRED
  phase: BOOTSTRAP_ACCEPTED -> TERMINAL
  cleanup_state: NONE -> REQUIRED -> COMPLETE
  terminal_reason: null -> expired
  terminal_at: null -> present

pairing_sessions:
  state: pending -> expired
  reason: -> expired

registrations:
  exact current pending row count: 1 -> 0

credential_assignments:
  pairing credential count: 0 -> 0
  hardware history count: 0 -> 0

unresolved_count:
  1 -> 0
```

The registration inventory is expected to become the canonical empty list:

```text
POST_REGISTRATION_COUNT=0
POST_REGISTRATION_INVENTORY_SHA256=4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945
```

That hash is SHA-256 of canonical JSON `[]`.

Therefore the pre-refresh registration inventory hash must **not** be required to remain unchanged. The deletion of this exact pending registration row is the intended cleanup.

No other registration row may exist before or after this transaction.

## 6. Production supervision authority

The production owner remains:

```text
n3wfc4-services-activation.service
```

Frozen service command contract:

```text
ExecStart=/usr/bin/docker compose --project-name ${N3WFC4_COMPOSE_PROJECT_NAME} --env-file ${N3WFC4_COMPOSE_ENV_FILE} -f ${N3WFC4_COMPOSE_FILE} --profile application up --no-deps --no-log-prefix --abort-on-container-exit manager homeassistant

ExecStop=/usr/bin/docker compose --project-name ${N3WFC4_COMPOSE_PROJECT_NAME} --env-file ${N3WFC4_COMPOSE_ENV_FILE} -f ${N3WFC4_COMPOSE_FILE} stop homeassistant manager
```

KF-129 remains a hard guard:

- no out-of-band Manager-only Compose recreate;
- no `docker compose ... --force-recreate manager`;
- no direct `docker stop`/recreate of the Manager container;
- no attempt to keep Home Assistant running while externally replacing Manager.

The live refresh intentionally restarts the Manager + Home Assistant service group through the existing systemd owner.

Broker remains separately owned and must remain running.

## 7. Live compose/image binding authority

The repository production Compose template is **not** sufficient live authority for this transaction because the real T1 already runs a later Manager image than the repository template's historical Manager tag.

The executor must resolve live authority from the installed systemd environment:

```text
/etc/n3wfc4/broker-activation.env
```

Before first mutation, it must prove that the environment resolves exactly:

```text
N3WFC4_COMPOSE_FILE=/etc/n3wfc4/docker-compose.yml
N3WFC4_COMPOSE_ENV_FILE=/etc/n3wfc4/docker-compose.env
N3WFC4_COMPOSE_PROJECT_NAME=n3wfc4
```

The installed Compose file referenced by that environment is the only allowed image-binding mutation target.

The executor must not copy the repository Compose template over the live file.

## 8. Readonly preclaim immediately before authorization claim

A fresh preclaim must occur immediately before the first live write.

Required checks:

### 8.1 systemd

```text
n3wfc4-broker-activation.service=active/enabled
n3wfc4-services-activation.service=active/enabled
n3wfc4-registration-ingress-guard.service=active
```

The installed service unit must preserve the exact ExecStart/ExecStop contract and contain no `--force-recreate`.

### 8.2 live Compose binding

The executor must:

1. read the exact broker-activation environment;
2. bind the exact live Compose path and env path;
3. reject symlinks or unsafe metadata;
4. hash the current live Compose file;
5. render the current live Compose with `docker compose ... config --format json`;
6. require rendered Manager image to equal the proven predecessor image reference;
7. require rendered Broker and Home Assistant images to equal the running baseline;
8. require Manager and Home Assistant network mode to remain host;
9. require the running Manager image ID to equal the proven predecessor image ID.

Any mismatch is STOP before claim.

### 8.3 rollback image availability

The predecessor image must still exist locally by exact immutable ID.

The executor must not depend only on the mutable predecessor tag.

### 8.4 successor image prestate

Allowed states:

```text
ABSENT
PRESENT_AND_EXACT
```

Forbidden:

```text
TARGET_TAG_PRESENT_WITH_WRONG_IMAGE_ID
```

### 8.5 E03 state revalidation

The exact readonly R2 classification must still pass:

```text
same pairing hash
same hardware hash
ACTIVE
BOOTSTRAP_ACCEPTED
NONE
expired
registration_match_count=1
session=pending
current pairing exact
node_id absent
pairing credential count=0
hardware credential history count=0
DEFINITELY_NOT_COMMITTED
registration_count=1
unresolved_count=1
47112 closed
```

Any state drift is STOP.

### 8.6 Home Assistant continuity baseline

Before claim, capture a public-safe SHA-256 continuity hash of the existing Home Assistant MQTT config entry set.

The hash may include the full canonical selected MQTT config-entry JSON internally, but no secret/config values may be emitted.

Post-refresh the same canonical hash must match.

## 9. One-shot authorization claim

No T1 write may occur before a separately authorized live-apply gate.

The live authorization must bind at minimum:

```text
exact executor source blob
PR725 head
predecessor Manager image ref + immutable image ID
target source head
target Manager image ref + immutable image ID
target Manager tar SHA-256
artifact ID
artifact digest
preclaim Compose SHA-256
preclaim registration inventory SHA-256
failed pairing/hardware public-safe hashes
```

The first T1 write is the durable one-shot claim.

Recommended implementation:

```text
private transaction root owned by root, mode 0700
claim/journal files mode 0600
exclusive create
fsync file
fsync parent directory
```

Reusing the same authorization ID after claim must fail closed.

Claim is consumed even if later artifact transfer or apply fails.

## 10. Exact artifact transfer and image load

Artifact preparation occurs on the Mac side.

Before T1 mutation:

1. obtain GitHub artifact ID 12900601779 from the already passed exact ARM64 build;
2. verify the artifact provenance/digest from GitHub metadata;
3. read `binding.json`;
4. require the exact source head, target image ref, target image ID and Manager tar SHA-256;
5. independently SHA-256 the local `greenhouse-manager-arm64.tar`.

After the T1 authorization claim has been durably consumed:

- if the target image is already present with the exact immutable ID, do not load again;
- otherwise stream the exact Manager tar over the already bound SSH target into `docker load`;
- verify the target tag resolves to the exact target image ID;
- verify the predecessor image ID remains locally available for rollback.

The artifact tar does not need to be permanently stored on T1.

## 11. Compose mutation transaction

Only one product configuration value may change:

```text
services.manager.image
```

Transition:

```text
local/greenhouse-manager:fresh-ff750b3801a2
->
local/greenhouse-manager:fresh-f8876fd87165
```

The executor must not change:

- Broker image or configuration;
- Home Assistant image or configuration;
- Manager environment;
- Manager mounts;
- Manager network mode;
- Compose project;
- Compose env file;
- systemd unit;
- registration guard;
- firewall;
- SQLite data;
- credentials;
- pairing window state.

The live Compose file must be replaced atomically:

1. bind current file metadata and SHA-256;
2. retain original bytes in the private transaction record;
3. construct a candidate that changes exactly one Manager image binding;
4. validate candidate rendered Compose before replacement;
5. require all non-Manager rendered service definitions to remain equivalent;
6. fsync candidate;
7. atomic `os.replace`;
8. fsync parent directory;
9. verify installed file hash equals the candidate hash.

If the current file cannot be unambiguously transformed, STOP.

## 12. Service-group cutover

After the target image is loaded and Compose is atomically bound:

```text
systemctl stop n3wfc4-services-activation.service
```

Required after stop:

- services unit inactive;
- Manager stopped;
- Home Assistant stopped;
- Broker unit still active;
- Broker container identity/image/started-at/restart-count unchanged;
- Broker 8883 listener remains exactly one.

Then:

```text
systemctl start n3wfc4-services-activation.service
```

Do not use Manager-only Compose commands.

## 13. Bounded successor startup acceptance

The executor must use a bounded startup window.

No open-ended polling is allowed.

Acceptance requires:

### 13.1 Manager

```text
image_ref=local/greenhouse-manager:fresh-f8876fd87165
image_id=sha256:089153fa4bbc823a1357427083f23ef96933a119c6ae150c143b62d7b40859e4
network_mode=host
restart_count=0
running=true
```

Manager container identity must differ from the predecessor container identity because the image binding changed.

### 13.2 Home Assistant

Home Assistant must return running with:

- same image ref;
- same immutable image ID;
- host network;
- restart_count=0;
- same persistent config mount authority;
- same public-safe MQTT config-entry continuity hash.

Container ID continuity is informative but is not a correctness oracle for this transaction.

### 13.3 Broker

Broker must remain continuously running with:

- exact same container identity;
- exact same immutable image ID;
- exact same StartedAt;
- restart_count=0;
- 8883 listener exactly one.

Any Broker recreation is a transaction failure.

### 13.4 listener state

After Manager/HA recovery:

```text
TCP_8883=1
TCP_47110=1
UDP_47111=1
TCP_47112=0
```

47112 must never be opened as part of this refresh.

## 14. Durable E03 repair postcondition

After successor startup reconciliation:

```text
attempt_count=1
same failed pairing SHA-256
same failed hardware SHA-256

attempt.state=EXPIRED
attempt.phase=TERMINAL
attempt.cleanup_state=COMPLETE
attempt.terminal_reason=expired
attempt.terminal_at_present=true

unresolved_count=0

registration_count=0
registration_inventory_sha256=4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945

pairing_session.state=expired
pairing_session.reason=expired

pairing_credential_count=0
hardware_credential_history_count=0
```

This is the exact success oracle.

A postcondition of `registration_count=1` is not success.

No manual SQLite edit is permitted to make this oracle pass.

## 15. Rollback policy

Rollback is **software/runtime rollback**, not database rewind.

### 15.1 Forbidden rollback

Never restore the pre-refresh SQLite bytes merely to recover the predecessor E03 state.

Never re-create the deleted pending registration manually.

Never rewrite a terminal attempt back to ACTIVE.

### 15.2 Failure before systemd stop

If failure occurs after claim/image load/Compose preparation but before service-group stop:

- running production services are still predecessor runtime;
- restore original Compose bytes if the live Compose file was already replaced;
- retain the loaded target image as inert local content;
- mark transaction failed;
- do not reuse the consumed authorization.

### 15.3 Failure after services stop or target start

First:

```text
systemctl stop n3wfc4-services-activation.service
```

Then classify durable first-registration state read-only.

Allowed rollback classifications:

#### A. original unresolved state remains

```text
ACTIVE / BOOTSTRAP_ACCEPTED / NONE
registration_count=1
```

Restore predecessor Compose binding, start the service group, verify predecessor runtime baseline. E03 remains unresolved and the live repair is failed.

#### B. repair already completed

```text
EXPIRED / TERMINAL / COMPLETE
registration_count=0
unresolved_count=0
```

Preserve the repaired database state. Restore only the predecessor Manager Compose binding if runtime rollback is required, then start the service group and verify the predecessor image can operate with the cleaned durable state.

#### C. restartable reconciliation state

Example:

```text
EXPIRED / TERMINAL / REQUIRED
```

The reconciliation implementation is unchanged between predecessor and successor source. Runtime rollback may restore the predecessor image and allow startup reconciliation to continue, but the executor must verify the final durable state becomes COMPLETE. It must not report rollback PASS while REQUIRED remains.

#### D. FAILED / UNKNOWN / identity drift

Do not edit the database.

Do not report a successful rollback.

Stop and require a separate emergency recovery gate with the exact durable state captured public-safely.

## 16. Predecessor/successor reconciliation compatibility authority

Direct source comparison:

```text
BASE=ff750b3801a282af1667b5fa63481e2333e301b3
HEAD=f8876fd87165df731d792690a8288867c3eeef55
```

No changes occurred in:

```text
n3w_first_registration_reconciliation.py
registration.py
n3w_first_registration_ledger.py
credential_lifecycle.py
```

The E03 product repair changes first-registration transaction deadline ownership only.

Therefore a durable reconciliation state created by the successor does not introduce a new reconciliation schema/algorithm that the predecessor image cannot understand.

This compatibility is not permission to restore stale database bytes.

## 17. Journal and public evidence

The private transaction journal must record phase transitions and exact hashes without secrets.

Suggested phases:

```text
PRECLAIM_PASS
AUTHORIZATION_CLAIMED
TARGET_IMAGE_BOUND
COMPOSE_CANDIDATE_VALIDATED
COMPOSE_REPLACED
SERVICES_STOPPED
BROKER_CONTINUITY_PASS
SERVICES_STARTED
SUCCESSOR_RUNTIME_PASS
E03_RECONCILIATION_PASS
POST_ACCEPTANCE_PASS
COMMITTED
```

Rollback phases:

```text
ROLLBACK_STARTED
ORIGINAL_COMPOSE_RESTORED
PREDECESSOR_RUNTIME_RESTORED
ROLLBACK_DURABLE_STATE_CLASSIFIED
ROLLBACK_PASS
```

Public GitHub evidence must not include:

- private SSH locator;
- raw pairing ID;
- raw hardware ID;
- passwords or tokens;
- raw Manager environment;
- raw Home Assistant MQTT config data;
- raw private transaction paths.

Public-safe hashes and exact image/artifact identifiers are allowed.

## 18. Source implementation requirements

The next source gate must implement a dedicated executor and tests.

Recommended files:

```text
tools/n3w_t1_r10_e03_manager_successor_refresh_live.py
tests/tools/test_n3w_t1_r10_e03_manager_successor_refresh_live.py
.github/workflows/n3w-r10-e03-manager-successor-refresh-live-source-ci.yml
```

The executor must be disabled unless an explicit live apply subcommand and exact authorization binding are provided.

Unit tests must cover at least:

1. exact predecessor + successor happy path;
2. live Compose authority drift;
3. target tag wrong immutable image ID;
4. claim replay rejection;
5. target tar SHA mismatch;
6. Broker continuity failure;
7. Manager-only recreate forbidden;
8. non-Manager Compose drift rejected;
9. successor Manager wrong image ID;
10. HA continuity-hash change;
11. 47112 unexpectedly open;
12. expected E03 cleanup to registration_count=0;
13. false success if registration_count remains 1;
14. rollback before service stop;
15. rollback after completed DB cleanup without database rewind;
16. EXPIRED/REQUIRED restartable rollback;
17. FAILED/UNKNOWN durable state stops emergency;
18. no SQLite mutation commands in executor;
19. no raw private identity in public report;
20. no reuse of consumed authorization.

## 19. Explicit non-goals

This refresh does not:

- merge PR #725 to main;
- modify Board D;
- perform a new first-registration attempt;
- open 47112 manually;
- reconfigure Broker;
- change Home Assistant image;
- change systemd ownership architecture;
- rewrite production credentials;
- redesign first-registration reconciliation;
- manually delete E03 rows.

## 20. Gate result and next gate

```text
LIVE_PREEXECUTION_DESIGN=PASS
SOURCE_IMPLEMENTATION_REQUIRED=true
LIVE_APPLY_AUTHORIZED=false
LIVE_APPLY_EXECUTED=false
BOARD_RETRY_AUTHORIZED=false

NEXT_ONE_GATE=
N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_E03_MANAGER_SUCCESSOR_REFRESH_LIVE_EXECUTOR_SOURCE_IMPLEMENTATION_20261029_01
```
