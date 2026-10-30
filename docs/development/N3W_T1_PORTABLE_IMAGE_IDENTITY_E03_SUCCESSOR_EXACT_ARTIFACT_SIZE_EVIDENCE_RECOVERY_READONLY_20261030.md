# N3-W T1 historical exact Manager tar-size evidence recovery — 2026-10-30

~~~text
TASK=N3W_T1_PORTABLE_IMAGE_IDENTITY_E03_SUCCESSOR_EXACT_ARTIFACT_SIZE_EVIDENCE_RECOVERY_READONLY_20261030_01

PR725_HEAD=614c08a397462850f0167b77c9da45ae69a323ad
PR739_HEAD_AT_GATE_START=85f7e5663360594be25eff97fd2921a25647615b
PR740_HEAD=ff2904bcdedbae6651cbfe92104b12ad47d33903

EXACT_ARTIFACT_RUN_ID=40880705472
EXACT_ARTIFACT_ID=12900601779
EXACT_ARTIFACT_NAME=n3w-t1-fresh-exact-arm64-f8876fd87165df731d792690a8288867c3eeef55
EXACT_ARTIFACT_WHOLE_SIZE_BYTES=2538792820
EXACT_ARTIFACT_DIGEST_SHA256=c94568f740b911eee0f4238207249b1e98f84748c17a902938ccc35293e4b183
EXACT_SOURCE_HEAD=f8876fd87165df731d792690a8288867c3eeef55

MANAGER_TAR_FILE=greenhouse-manager-arm64.tar
MANAGER_TAR_SIZE_BYTES=62681088
MANAGER_TAR_SHA256=d129a33ea628d8bdd1361e0b1bf727175515b4a2afc1851e6ac14ec510895fb5
BINDING_MANAGER_TAR_SHA256=d129a33ea628d8bdd1361e0b1bf727175515b4a2afc1851e6ac14ec510895fb5
BINDING_SOURCE_HEAD=f8876fd87165df731d792690a8288867c3eeef55

LOCAL_EXACT_TAR_SHA_MATCH=PASS
LOCAL_BINDING_SHA_MATCH=PASS
LOCAL_BINDING_SOURCE_HEAD_MATCH=PASS
GITHUB_FROZEN_TAR_SHA_MATCH=PASS
MANAGER_TAR_SIZE_EVIDENCE=PASS

WHOLE_ARTIFACT_SIZE_USED_AS_MANAGER_TAR_SIZE=false
MANAGER_TAR_SIZE_GUESSED=false
PRIVATE_LOCAL_PATH_ARCHIVED=false

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
WORKFLOW_DISPATCH=false
OLD_AUTHORIZATION_REPLAY=false
LIVE_PREAUTH=false
LIVE_RECOVERY=false
MERGE=false

EVIDENCE_RECOVERY=CLOSED_PASS
HISTORICAL_EXACT_MANAGER_TAR_SIZE_AUTHORITY=62681088
READONLY_PREAUTH_READY=true
READONLY_PREAUTH_EXECUTED=false
LIVE_PREAUTH_AUTHORIZED=false

CURRENT_STOP_POINT=HISTORICAL_EXACT_MANAGER_TAR_SIZE_EVIDENCE_RECOVERED_BEFORE_SUCCESSOR_READONLY_PREAUTH
NEXT_ONE_GATE=N3W_T1_E03_SUCCESSOR_RECOVERY_READONLY_PREAUTH_20261030_01
AUTO_EXECUTE_NEXT_GATE=false
~~~

## Evidence basis

GitHub authority for exact artifact run `40880705472` already froze the Manager tar SHA256 as `d129a33ea628d8bdd1361e0b1bf727175515b4a2afc1851e6ac14ec510895fb5` and the source head as `f8876fd87165df731d792690a8288867c3eeef55`.

The historical producer did not archive the Manager tar byte size. GitHub artifact metadata only exposes the whole artifact size `2538792820` bytes, which is not a valid substitute for the Manager tar size. The connector also cannot materialize this artifact because its size exceeds the connector download limit.

The operator performed a read-only check against the already-existing exact local artifact. The terminal result reported:

- Manager tar size: `62681088` bytes.
- Manager tar SHA256: `d129a33ea628d8bdd1361e0b1bf727175515b4a2afc1851e6ac14ec510895fb5`.
- `binding.json` Manager tar SHA256: the same value.
- `binding.json` source head: `f8876fd87165df731d792690a8288867c3eeef55`.
- Result: `MANAGER_TAR_SIZE_EVIDENCE=PASS`.

Because the local file's content digest equals the frozen GitHub exact-artifact Manager tar digest and the local binding source head also equals the frozen source head, `62681088` bytes is accepted as the exact historical Manager tar size authority.

This gate did not access T1, mutate T1, access boards, dispatch workflows, replay the predecessor authorization, execute successor preauthorization, execute live recovery, or merge any PR.

## Next boundary

The artifact-size evidence prerequisite is now closed. This only makes the next read-only successor preauthorization gate eligible to begin. It does not authorize T1 access or any live mutation by itself.

Next gate:

`N3W_T1_E03_SUCCESSOR_RECOVERY_READONLY_PREAUTH_20261030_01`
