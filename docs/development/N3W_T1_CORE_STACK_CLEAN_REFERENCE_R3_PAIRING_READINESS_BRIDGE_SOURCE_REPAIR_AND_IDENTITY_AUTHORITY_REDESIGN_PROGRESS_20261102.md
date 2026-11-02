# N3W T1 Core Stack Clean Reference R3 pairing-readiness bridge source repair and identity-authority redesign progress

Date: 2026-11-02

~~~text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R3_PAIRING_READINESS_BRIDGE_SOURCE_REPAIR_AND_IDENTITY_AUTHORITY_REDESIGN_20261102_01
STATE=IN_PROGRESS
SOURCE_REPAIR_COMMITTED=true
SOURCE_REPAIR_CI=CI_PENDING

REPOSITORY=chrenguo-stack/HomeAssistant
MAIN_HEAD_AT_FRESH_REBIND=2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e
PR=705
CANDIDATE_BRANCH=test/n3w-r8-full-simulated-e2e-safety-20261028
FRESH_CANDIDATE_HEAD_BEFORE_REPAIR=843b8279f9bb07b5b054a41dea93a5bc5f49f627

PREVIOUS_EXACT_BRIDGE_AUTHORITY=37e269300d6fadeee7ad85476374813f879cdb23
SOURCE_REPAIR_HEAD=7b913c98e1eee3669fc356f01ea0b5ff098f9b66
SOURCE_REPAIR_BRIDGE_BLOB=92a9b5e1c3435eb0dd562c498878a1f65bcd808b
SOURCE_REPAIR_TEST_BLOB=2f9fe7c620595e23614bdf35505c29a8252b1afe
SOURCE_REPAIR_CHANGED_FILES=2

BRIDGE_CI_RUN=41364918910
BRIDGE_CI_URL=https://github.com/chrenguo-stack/HomeAssistant/actions/runs/41364918910
BRIDGE_CI_POLL_COUNT=3
BRIDGE_CI_STATE_AFTER_POLL_LIMIT=QUEUED
BRIDGE_CI_CONCLUSION=NOT_AVAILABLE

R2_COMMON_REFERENCE=CLOSED_PASS
OPTION_A_DIRECTION=RETAINED
PREVIOUS_LIVE_PREFLIGHT=STOP_PRECLAIM

CURRENT_DEVICE_PROVISIONING_STATE=UNPROVISIONED
DEVICE_READY_ASSUMPTION_REMOVED=true
EMPTY_PROVISIONING_ROOT_CREATION_FORBIDDEN=true
OLD_F4_REPLAY=false

SQLITE3_IMPORT_DEFECT=REPAIRED_IN_SOURCE
REAL_SQLITE_TEST_PATH_ADDED=true

IDENTITY_AUTHORITY=clean_reference_runtime_identity_v1
RELEASE_AUTHORITY=fresh-release.json exact product binding
HOST_INSTANCE_AUTHORITY=/etc/machine-id + /etc/ssh/ssh_host_ed25519_key.pub frozen derivation
SYSTEM_ID_AUTHORITY=verified /var/lib/greenhouse-manager/identity initialization bundle
SYSTEM_ID_MANAGER_DB_BINDING=h0h1_legacy_adoption_provenance system_id_fingerprint
DEVICE_PROVISIONING_AUTHORITY=status must remain UNPROVISIONED

MISSING_PROVISIONING_ROOT_PREFLIGHT_ALLOWED=true
FACTORY_MARKER_FUTURE_APPLY=temporary populated root then atomic directory rename
FACTORY_MARKER_ROLLBACK=remove marker and bridge-created provisioning root
FACTORY_ACCEPTANCE_ROUTE=clean_reference_r2_bridge_v2

LIVE_MUTATION=false
T1_ACCESS=false
BOARD_ACCESS=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
FACTORY_ACCEPTED_CREATED=false
PAIRING_WINDOW_OPENED=false
MERGE=false

GATE_CLOSED=false
CLOSE_BLOCKER=BRIDGE_CI_PENDING
NEXT_ACTION=READ_CI_RUN_41364918910_ONCE_AVAILABLE_THEN_CLOSE_OR_BOUNDED_LOCAL_REPAIR
~~~

## 1. Fresh rebind result

Fresh rebind confirmed that PR #705 candidate head before repair was
`843b8279f9bb07b5b054a41dea93a5bc5f49f627`. The prior executable bridge authority
`37e269300d6fadeee7ad85476374813f879cdb23` differed from that candidate only by four
documentation commits; bridge production source had not drifted.

Repository `main` was still at
`2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e`, so it was not used as a substitute for
the PR #705 candidate authority.

R2 / R2 common-reference remains CLOSED_PASS. The earlier bridge live preflight remains a
valid STOP_PRECLAIM: no bridge authorization was claimed or consumed, no
`FACTORY_ACCEPTED.json` was created, the pairing window remained closed, and no Board
access occurred.

## 2. Source defects and design defect repaired

### 2.1 sqlite3 source defect

The exact bridge used `sqlite3.connect` and caught `sqlite3.Error` without importing
`sqlite3`. The repair adds the import and adds a test that creates real SQLite databases
for credential, peer-trust, and relay-authorization state so the actual SQLite code path is
executed.

### 2.2 DEVICE_READY assumption removed

The bridge no longer invokes the frozen provisioning tool with `verify` and no longer
requires `DEVICE_READY`.

It invokes the frozen tool with `status` and requires the frozen contract to report:

- `status=PASS`;
- `state=UNPROVISIONED`;
- the exact product release id;
- `production_service_start=false`;
- `board_access=false`.

A missing `/var/lib/n3w-t1-provisioning` is therefore accepted as the correct clean
UNPROVISIONED state. The read-only preflight does not create that root.

## 3. Clean Reference identity authority redesign

The replacement authority does not invent identity and does not depend on a legacy
device-provisioning transaction.

The bridge now derives and cross-checks identity through four existing authorities:

1. exact `fresh-release.json` binds the product source/release;
2. `host_instance_id` is derived with the frozen device-firstboot algorithm from
   `/etc/machine-id` and the Ed25519 SSH host public key;
3. `system_id` is read from the already-created Manager initialization identity bundle,
   while checking the initialization marker self-binding, member inventory, member
   SHA-256/size/mode, system identity schema, manager identity schema, and cross-binding;
4. the resulting `system_id` SHA-256 prefix is checked against the single
   `h0h1_legacy_adoption_provenance.system_id_fingerprint` row in the current Manager DB.

The bridge exposes only hashes in read-only inspect output. The standard private
`FACTORY_ACCEPTED.json` document still carries the raw host/system identifiers required by
the frozen onboarding contract, and adds provenance fields identifying this new authority.

## 4. Provisioning-root safety

The bridge still does not create an empty provisioning root.

For a future separately authorized `apply` only:

- when the provisioning root already exists and is clean/private, the marker is written
  atomically inside it;
- when the root is absent, the bridge first creates a private temporary sibling directory,
  writes and fsyncs `FACTORY_ACCEPTED.json` inside that temporary directory, and only then
  renames the populated directory into `/var/lib/n3w-t1-provisioning`;
- if post-marker validation fails and that root was bridge-created, rollback removes both
  the marker and the bridge-created root.

No such apply was executed in this gate.

## 5. Source review and tests added

The repair commit changes only:

- `tools/n3w_t1_clean_reference_pairing_readiness_bridge.py`;
- `tests/tools/test_n3w_t1_clean_reference_pairing_readiness_bridge.py`.

Focused tests now cover:

- missing provisioning root as UNPROVISIONED;
- real SQLite execution;
- use of provisioning `status`, not `verify`;
- rejection of fake `DEVICE_READY`;
- frozen OS host identity derivation;
- Manager initialization identity + Manager DB system-id cross-binding;
- atomic installation of a populated provisioning root;
- rollback removal of a bridge-created provisioning root;
- existing one-shot authorization, pairing-closed, no-reboot/no-board safety guards.

The package builder and frozen R2/R3 observer were not modified.

## 6. CI stop point

The focused bridge CI was created as run `41364918910` for source-repair head
`7b913c98e1eee3669fc356f01ea0b5ff098f9b66`.

After three polls it remained queued. Per project execution rules, polling stopped. No PASS
or FAIL conclusion is claimed.

The current gate remains IN_PROGRESS until that exact run is read. If it fails for a local,
unambiguous source/test issue, the repair may be applied directly. Any expansion into live
T1 mutation, marker creation, pairing, Board access, or merge remains a separate boundary.
