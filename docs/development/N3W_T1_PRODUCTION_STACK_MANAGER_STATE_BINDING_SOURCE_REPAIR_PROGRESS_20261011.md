# N3-W T1 production stack Manager state binding source repair progress

Date: 2026-10-11

Status: SOURCE_REPAIR_IMPLEMENTED / CI_PENDING / LIVE_ACTIVATION_NOT_AUTHORIZED

PR: #541 OPEN DRAFT

## 1. Fresh read-only evidence

The current T1 still preserves the accepted greenhouse SYSTEM_ID.

```text
SYSTEM_ID_FINGERPRINT_MATCH=true
CURRENT_SYSTEM_CLAIM_COUNT=1
MANAGER_DB_QUICK_CHECK=ok
MANAGER_DB_TABLE_COUNT=8
```

Manager business-state counts are all zero; the only nonzero row is the H0/H1 legacy-adoption provenance row.

```text
credential_assignments=0
node_id_leases=0
pairing_sessions=0
registration_events=0
registration_node_history=0
registrations=0
retirement_outbox=0
h0h1_legacy_adoption_provenance=1
```

The preserved claim is consistent with the historical PR #260 production-cutover authority, which recorded one production identity claim on the second T1. The restore marker remains immutable restore evidence and still says identity claim is required before activation; the current external claim registry now proves a claim exists for the preserved SYSTEM_ID. No new claim is authorized or required by this source repair.

## 2. Runtime-state blocker proved

Current live paths:

```text
portable_manager_database=/var/lib/greenhouse-manager/manager/manager-state.sqlite3
default_pairing_database=ABSENT
n3w_root=ABSENT
n3w_replay_database=ABSENT
n3w_relay_authorization_database=ABSENT
n3w_relay_key_directory=ABSENT
uid999_can_create_portable_root_child=false
```

The frozen Manager image selects the N3-W runtime when `GH_N3W_RUNTIME_ENABLED=true`. That runtime requires existing registration, replay and relay-key state before startup.

Therefore the previous production Compose could not safely start Manager.

## 3. Source repair

Production Compose now binds the portable Manager database explicitly:

```text
GH_PAIRING_DB_PATH=/var/lib/greenhouse-manager/manager/manager-state.sqlite3
GH_HISTORY_DB_PATH=/var/lib/greenhouse-manager/manager/manager-state.sqlite3
GH_N3W_REPLAY_DB_PATH=/var/lib/greenhouse-manager/n3w/replay.sqlite3
GH_N3W_RELAY_AUTHORIZATION_DB_PATH=/var/lib/greenhouse-manager/n3w/relay-authorization.sqlite3
GH_N3W_RELAY_KEY_DIR=/var/lib/greenhouse-manager/n3w/relay-keys
```

The Manager no longer receives the whole portable root as one read-write mount.

Exact writable runtime mounts are now:

```text
/var/lib/greenhouse-manager/manager
/var/lib/greenhouse-manager/n3w
```

This keeps the bootstrap identity/private-key members outside the long-running Manager container mount namespace.

## 4. State preparation contract

New tool:

```text
tools/n3w_t1_production_manager_state_prepare.py
```

It validates the exact clean H0/H1 Manager database contract:

- exact expected eight-table set;
- SQLite quick check PASS;
- all business tables zero rows;
- one exact H0/H1 legacy-adoption provenance row;
- provenance SYSTEM_ID fingerprint equals the expected public-safe fingerprint;
- the old `manager/registration.sqlite3` collision path must already be absent;
- Manager database must be 0600 and owned by the runtime UID;
- N3-W state root must be a private 0700 directory owned by the runtime UID.

Its prepare phase initializes only:

```text
n3w/replay.sqlite3
n3w/relay-authorization.sqlite3
n3w/relay-keys/
```

using the runtime implementations from the exact frozen Manager image.

It verifies the Manager database SHA does not change and the new N3-W runtime state contains zero node/replay/key state.

## 5. Collision handling boundary

The current T1 still has exactly one unexpected empty directory:

```text
manager/registration.sqlite3
type=directory
child_count=0
```

The state-preparation tool intentionally refuses to proceed while that path exists. It does not delete it.

A later live staging executor may remove only this exact empty directory after a fresh type/owner/mode/emptiness recheck and a separate explicit mutation authorization.

## 6. Deployment gate hardening

`tools/n3w_t1_clean_product_deployment_gate.py` now requires the explicit Manager runtime state environment and the two scoped writable state mounts.

It rejects any mount of the whole portable root:

```text
/var/lib/greenhouse-manager
```

into the production Manager container.

## 7. CI

Dedicated workflow added:

```text
.github/workflows/n3w-t1-production-manager-state-binding-ci.yml
```

The workflow:

1. runs focused deployment-gate and state-preparer tests;
2. renders the exact production Compose and validates it;
3. builds the frozen ARM64 Manager image from source SHA `511db028780988a7c07cb9342c8be507380bae0f`;
4. creates a synthetic clean restored Manager baseline;
5. streams the new preparer into that exact ARM64 Manager image with `--network none`;
6. prepares and audits empty replay/relay-key state;
7. proves the Manager database did not mutate;
8. proves Docker volume set is unchanged;
9. performs no T1 or board access.

Current status:

```text
SOURCE_REPAIR_IMPLEMENTED=true
CI_REVIEW=PENDING
T1_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR541=OPEN_DRAFT
MERGE=false
```

## 8. Next boundary

Do not perform any further T1 mutation while CI is pending.

If CI passes, the next live stage is a separately authorized staging transaction that must:

1. fresh-recheck the S20 baseline and existing identity claim;
2. verify the unexpected registration path is still the exact empty directory;
3. remove only that empty collision directory;
4. create `/var/lib/greenhouse-manager/n3w` as 999:999:0700;
5. run the exact-image state preparer;
6. stage exact source/config/systemd/image artifacts;
7. remain stopped before production Broker/Manager/Home Assistant activation unless the authorization explicitly covers activation.



## 9. CI run

A fresh PR run was created for the source-repair head.

```text
RUN_ID=38122562085
WORKFLOW=N3W T1 production Manager state binding CI
STATUS=QUEUED
CI_REVIEW=PENDING
```

Other repository workflows were also triggered by the branch update; no result is promoted until each required job completes.


## 10. CI fixture failure and repair

Run `38122599845` failed before any Compose render or exact-image runtime exercise.

```text
FAILED_STEP=Run focused source tests
RESULT=25 passed, 5 failed
ROOT_CAUSE=ModuleNotFoundError: No module named 'jsonschema'
FAILURE_CLASS=CI_FIXTURE_DEPENDENCY
PRODUCT_SOURCE_FAILURE_PROVEN=false
EXACT_IMAGE_RUNTIME_REACHED=false
T1_ACCESS=false
BOARD_ACCESS=false
```

The workflow had installed only `pytest`, while the new preparer imports Manager runtime modules whose formal package dependencies include `jsonschema`, `cryptography`, and `paho-mqtt`.

Repair commit:

```text
925034dfb3bdb42c30a4db8bcf0c63a38340f12e
```

The workflow now installs the Manager package with its declared development environment:

```text
python -m pip install -e 'host/greenhouse-manager[dev]'
```

This is a CI fixture/dependency correction only. Product runtime semantics, T1 state, production services, and board state are unchanged.

```text
CI_FIXTURE_REPAIR=IMPLEMENTED
CI_REVIEW=PENDING_FRESH_RUN
T1_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```


## 10. First CI failure classification and fixture repair

The first dedicated source-repair run failed before any product-path execution:

```text
RUN_ID=38122599845
RUN_NUMBER=6
STATUS=completed
CONCLUSION=failure
FAILED_STEP=Run focused source tests
RESULT=25 passed / 5 failed
ROOT_CAUSE=ModuleNotFoundError: jsonschema
```

All five failures shared the same import-time dependency error:

```text
n3w_t1_production_manager_state_prepare.py
-> n3w_node_application_keys.py
-> n3w_relay_ingress.py
-> import jsonschema
-> ModuleNotFoundError
```

The workflow had installed only `pytest`, not the Manager development/runtime dependency set.

Classification:

```text
FAILURE_CLASS=CI_FIXTURE_DEPENDENCY
PRODUCT_SOURCE_FAILURE_PROVEN=false
MANAGER_STATE_BINDING_RUNTIME_TEST_REACHED=false
T1_MUTATION=false
```

The workflow fixture was repaired to install:

```text
python -m pip install -e 'host/greenhouse-manager[dev]'
```

Repair commit:

```text
925034dfb3bdb42c30a4db8bcf0c63a38340f12e
ci(n3w): install Manager runtime deps for state binding tests
```

Fresh run:

```text
RUN_ID=38123286087
RUN_NUMBER=7
STATUS=in_progress
INSTALL_MANAGER_TEST_ENVIRONMENT=PASS
FOCUSED_SOURCE_TESTS=PASS
RENDER_AND_VALIDATE_PRODUCTION_COMPOSE=PASS
EXACT_ARM64_MANAGER_IMAGE_BUILD=in_progress
```

No T1 operation is authorized while the fresh run is incomplete.


## 11. Second CI failure: rebuild was not an exact frozen image

Fresh run #11 advanced past the previous dependency-fixture failure:

```text
RUN_ID=38123370107
RUN_NUMBER=11
FOCUSED_SOURCE_TESTS=PASS
RENDERED_PRODUCTION_COMPOSE=PASS
FAIL_STEP=Build exact frozen ARM64 Manager image
```

The ARM64 build itself completed, but the workflow then exited on the exact image-ID assertion.

The rebuilt image exported a new config digest instead of the frozen image ID recorded by S20. This proves that rebuilding source SHA `511db028780988a7c07cb9342c8be507380bae0f` today is not a valid way to recover the frozen production image: the Dockerfile uses mutable external build inputs such as the floating `python:3.11-slim` base and package resolution.

Classification:

```text
FAILURE_CLASS=CI_EXACT_ARTIFACT_REPRODUCTION_ERROR
PRODUCT_MANAGER_STATE_BINDING_FAILURE_PROVEN=false
SOURCE_REPAIR_RUNTIME_TEST_REACHED=false
FROZEN_IMAGE_LOCK_INVALIDATED=false
```

The original exact S20 image-binding artifact is still available and unexpired:

```text
BINDING_RUN_ID=38040433177
ARTIFACT_ID=11665219740
ARTIFACT_NAME=n3w-s20-production-image-binding-511db028
ARTIFACT_DIGEST=sha256:90d72f6eadc85c7ff56156f2f65c149785cdcabc11082b3e8fa275e486b29615
MANAGER_TAR_SHA256=2ef0421d483334f6ef81c92beb1b6784174f069a4bde179ba615ce0b70435081
MANAGER_IMAGE_ID=sha256:ef0f28c2fd339430a85acb6cb65158c71c61cd8fc3c6330c375da27d0f2440f1
```

The dedicated workflow was repaired to download artifact ID `11665219740` from run `38040433177`, verify the frozen Manager tar SHA, load it, and verify the exact ARM64 image ID. It no longer rebuilds source and calls that rebuild the frozen production image.

Repair commit:

```text
0716eea8e8cfa87184bf9538dbb704d10345b712
ci(n3w): consume frozen Manager image artifact
```

No T1 mutation or production service start occurred.
