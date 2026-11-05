# N3-W T1 Core Updater — Home Assistant P5 live apply attempt 01 transport STOP repair

Date: 2026-11-05

## 1. Attempt 01 result

~~~text
AUTHORIZATION_ID=N3W_T1_CORE_UPDATER_HOMEASSISTANT_2026_10_4_LIVE_APPLY_P5_20261105_01

ATTEMPT=01
RESULT=STOP_BEFORE_PREFLIGHT
REASON=command_failed:scp:1

APPLY_INVOKED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
T1_MUTATION=false

SECOND_APPLY_ALLOWED=false
BLIND_EXPLICIT_ROLLBACK_ALLOWED=false
~~~

The one-shot authorization was not consumed because the executor stopped before
the authorization claim and before the updater apply invocation.

## 2. What is proven

The local executor:

- checked out the exact authorized source;
- verified the frozen GitHub artifact before T1 staging;
- established SSH connectivity;
- passed the storage-capacity gate;
- created the temporary staging phase;
- stopped while transferring a staging file through the dedicated `scp` path.

The public STOP result proves that updater apply was not invoked and no product
T1 mutation occurred.

The sanitized result exposes only `command_failed:scp:1`. It does not preserve
remote `scp` stderr, so it is not sufficient evidence to claim a narrower root
cause such as an SFTP-subsystem failure or a ControlMaster-reuse failure.

## 3. Bounded source repair

The P5 staging transport is changed from a separate `scp` invocation to a
streaming write over the already-established SSH transport.

Repair properties:

- source file is streamed from an open local file descriptor;
- the 835 MB HA archive is not buffered into process memory;
- destination is restricted to the executor-owned
  `/var/tmp/n3w-ha-p5.<token>/...` scratch directory;
- remote open uses create-exclusive semantics and no-follow where available;
- remote file mode is 0600;
- remote file is fsync'd before the transport reports success;
- target artifact bytes and updater source bytes are unchanged.

~~~text
REPAIR_EXECUTABLE_HEAD=9ab1ddf21dd191c916ef7b0dbe281d03aa8d0a2f

GENERIC_V2_CHANGED=false
REMOTE_LIVE_CHANGED=false
FROZEN_HA_TARGET_CHANGED=false
STORAGE_POLICY_CHANGED=false
AUTHORIZATION_MANIFEST_CHANGED=false
~~~

## 4. Authorization disposition

Because attempt 01 stopped before claim and before apply:

~~~text
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
AUTHORIZATION_REPLAY_PERMITTED=false
~~~

The existing explicit user authorization remains valid for one repaired retry.
This is not a second apply: no first apply invocation occurred.

No repaired retry is permitted until the repaired exact executable source and
its docs-aligned successor pass CI.

## 5. Next boundary

~~~text
NEXT_ONE_GATE=P5_ATTEMPT01_TRANSPORT_REPAIR_EXACT_HEAD_CI
AUTO_RETRY=false
T1_MUTATION=false
MERGE=false
~~~
