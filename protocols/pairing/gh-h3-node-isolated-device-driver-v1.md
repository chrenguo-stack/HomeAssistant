# GH H3/N2 Stage 2D-8 Isolated Device Driver Protocol V1

## 1. Scope

This protocol binds the Stage 2D-7 acceptance package to test-only persistence
and MQTT ports while retaining default-off execution. It defines source and
compile behavior plus the prerequisites for a later physical run. It does not
itself authorize flashing, NVS access, Broker access or a persistent write.

## 2. Layered roles

- **acceptance package**: command ordering, redacted evidence and first
  generation-bound authorization;
- **authorization binder**: arms package and physical driver atomically;
- **physical driver**: enforces an independent mirrored grant and coordinates
  persistence, MQTT, rollback and reboot closure;
- **test persistence port**: accesses only the manifest-bound `gh2d8_`
  partition and namespace;
- **test MQTT port**: accesses only the manifest-bound temporary Broker and
  `gh-test/` topic root;
- **operator**: approves the next exact live step after reviewing evidence.

No layer may substitute production credentials, topics, namespaces or services.

## 3. Default-off lifecycle

```text
compile-only image
  -> no runtime driver object
  -> no custom partition initialization
  -> no NVS open
  -> Wi-Fi disabled
  -> no MQTT client
  -> no operator transport
```

A later live harness must be separately reviewed and must begin in `LOCKED`.
It may create the driver only after validating an exact execution manifest and
firmware digest. Construction still performs no I/O.

## 4. Execution gates

### G0 — immutable inputs

The execution record fixes:

- source commit and test firmware SHA-256;
- rollback firmware SHA-256;
- board identifier and serial path;
- partition-table SHA-256;
- test partition and namespace;
- Wi-Fi profile digest;
- Broker configuration, CA and ACL digests;
- unique test run, system, node, client and topic identifiers;
- evidence directory and cleanup procedure.

Any change invalidates every unconsumed grant.

### G1 — flash-only approval

Flashing requires a separate approval naming the exact test and rollback image
digests. It does not authorize NVS, Wi-Fi, MQTT or a persistent write.

### G2 — read-only inspection

After boot, the operator explicitly enables only the read-only command path.
The driver opens the dedicated namespace read-only and returns:

- namespace present or absent;
- authenticated persistence status;
- active and candidate generations;
- zero package-caused commits;
- zero MQTT sessions.

An existing namespace cannot be decrypted until the volatile 32-byte test key
is supplied in RAM. The key has no repository or firmware default.

### G3 — prepare approval

`PREPARE_CANDIDATE` is bound to the exact G2 generations, run identifier,
firmware commit, configuration digest, Broker digest and unique approval digest.
The binder must arm both package and driver. The driver consumes its grant before
opening NVS read-write.

### G4 — validation

Validation requires no persistent write. It uses only:

- `<test_topic_root>/probe/request`
- `<test_topic_root>/probe/confirm`

The root begins with `gh-test/`, contains the exact run identifier and contains
neither `homeassistant` nor `gh/v1/`.

### G5 — activation approval

`ACTIVATE_PROFILE` requires a new two-layer grant for the exact active and
PREPARED generations. The sequence is:

1. consume the Stage 2D-7 authorizer;
2. consume the mirrored driver grant;
3. prove candidate TLS, authentication and test round trip;
4. write and verify the candidate COMMITTED record;
5. write and verify the `active` marker last;
6. reopen read-only and recover the new authority;
7. promote the already verified candidate session.

A failure before step 5 destroys the candidate and retains or restores the old
active test session. A failure at or after step 5 is authority-ambiguous and
requires quiescence and reboot recovery.

### G6 — evidence

Evidence uses the Stage 2D-7 redacted schema. It may include digests,
generations, status names, session roles, marker-last result, rollback result,
commit count and failure point. It excludes Broker address, certificate body,
username, password, client secret, raw test key, derived key, nonce and approval
digest.

### G7 — cleanup approval

`CLEANUP_TEST_STATE` is a third independent two-layer grant. It is rejected
until evidence has been exported. Cleanup:

1. quiesces all three MQTT roles;
2. erases only the named test namespace;
3. commits once;
4. reopens read-only and proves `empty`;
5. destroys key and candidate material;
6. exports final cleanup evidence.

Partition erase, eFuse access and production namespace cleanup are forbidden.

## 5. Persistence audit contract

The audited backend records the key associated with each successful commit.
For activation, the final two commits must be:

```text
slot_a or slot_b
active
```

A successful API return without that order is `marker_last_not_proven` and
requires reboot. A marker that may have committed despite a failed API is
`authority_ambiguous` and also requires reboot.

Read-only inspection compares commit counters before and after the operation.
Any increase fails the inspection.

## 6. Broker isolation contract

The temporary Broker must:

- run outside M401A, T1 and production Home Assistant hosts;
- use a unique listener and CA for the run;
- disable anonymous access;
- disable persistence;
- grant the test identity only its exact `gh-test/<run>/#` root;
- contain no Home Assistant Discovery or production ACL;
- be destroyed after evidence and cleanup complete.

A separate responder returns the exact nonce-bound confirmation payload. The
Broker never rewrites, bridges or forwards traffic to a production service.

## 7. Failure matrix selected for the first run

The first physical run should remain bounded to:

| ID | Test | Expected result |
|---|---|---|
| P01 | deny prepare grant | zero writes |
| P03 | successful PREPARED commit | exact candidate generation recovered |
| V02 | TLS server-name mismatch | validation fails, active unchanged |
| V03 | authentication rejection | validation fails, active unchanged |
| A01 | verified without activation grant | zero activation writes |
| A04 | candidate activation start failure | old active retained |
| A06 | marker write failure | orphan classified, old active retained or reboot closure |
| A09 | successful activation then reboot | new active generation recovered exactly |
| N01 | NVS read failure | no MQTT, fail closed |
| C01 | approved cleanup | empty namespace and zero sessions |

Power-cut timing tests A03 and A08 require a later dedicated power-control jig
and are not part of the first manual run.

## 8. Live stop conditions

Stop immediately and do not issue cleanup when:

- observed board, firmware or partition digest differs from the manifest;
- any production identifier, topic or credential is detected;
- read-only inspection increments a commit counter;
- generation authority is ambiguous;
- a marker may be committed but promotion is incomplete;
- evidence cannot be written durably;
- rollback image or serial recovery path is unavailable.

The safe terminal state is all MQTT roles quiesced with no further NVS action
until a new reviewed recovery record is issued.

## 9. Current stage boundary

The current Stage 2D-8 branch implements and compiles the driver and ports but
does not instantiate them. No live gate from G1 onward has been executed. The
next user interaction is required only after CI passes and an exact board,
serial path, partition layout and rollback artifact are available.
