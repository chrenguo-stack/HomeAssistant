# N3W T1 F5 Repaired Release Durable Mac Archive Acceptance — Closure

Date: 2026-10-19

## 0. Conclusion

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V1_REPAIRED_RELEASE_DURABLE_MAC_ARCHIVE_ACCEPTANCE_20261019_01
RESULT=CLOSED_PASS

PR612_SOURCE_HEAD=6e228a4b2c7c4ff78918571abb7b583e416615ee
PR612_SOURCE_TREE=6c07b6f9c3d528b630a96cf16b4efdbaef3ff5e5
PR612_SOURCE_CI=PASS:20/20

PR613_BUILDER_HEAD=51c7eaf3d285c4b604b0261021ce9ceac061a445
PR613_EXACT_RELEASE_CI=PASS:12/12

PR614_ARCHIVE_SOURCE_HEAD=75f5f068e58c3e74d665677b1dd7b33f44d12e61
PR614_ARCHIVE_SOURCE_CI=PASS:12/12

RELEASE_ID=b89c9e227e53fcac2ef2717d7b11cd6b64536ce27c9b6b16c2429980049c8a69
RELEASE_SHA256=5291042f87686aecbd6b7e52641c10f69cdae0d56abbf675b8eab8c9bfeb8804
FILE_INDEX_SHA256=1398556003c05695d966593bf6a171f4a628cbf46d36c68d774db05972f9461c

WORKFLOW_RUN_ID=39188343164
ARTIFACT_ID=12158903271
ARTIFACT_NAME=n3w-t1-f5-approved-release-6e228a4b2c7c4ff78918571abb7b583e416615ee
ARTIFACT_ZIP_SHA256=5732093e9d94bff99b22ed935a54a187a224d29a5ec77e964dfec5cfe2487013

FIRST_ARCHIVE=MISS_POPULATED
FIRST_ARCHIVE_STATUS=PASS
SECOND_VERIFY=VERIFY_ONLY
SECOND_VERIFY_STATUS=PASS
SECOND_VERIFY_GITHUB_ACCESS=false

CURRENT_RELEASE_DURABLE_ARCHIVE_CLOSED=true
T1B_READONLY_AUTHORIZATION=GRANTED_NOT_CONSUMED

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~

The repaired F5 release is now durably preserved on the production Mac and independently verified from
the local store. The second verification was executed with `gh` and `curl` replaced by hard-fail
sentinels, so the successful `VERIFY_ONLY` result did not rely on GitHub metadata or artifact download.

The prior release built from source `55e499f...` remains valid historical evidence only. It is
superseded for F5-8/F5-9 execution by the repaired source and release above.

## 1. Durable store

~~~text
~/Documents/N3W/approved-releases/
  b89c9e227e53fcac2ef2717d7b11cd6b64536ce27c9b6b16c2429980049c8a69/
    12158903271/
      5732093e9d94bff99b22ed935a54a187a224d29a5ec77e964dfec5cfe2487013/
        artifact.zip
        binding.json
~~~

## 2. F5-8 boundary

~~~text
F5_8_READINESS=READY
T1B_READONLY_AUTHORIZATION=GRANTED_NOT_CONSUMED
NEXT_ONE_GATE=N3W_T1_F5_PRODUCTION_PROCESS_V1_T1B_READONLY_PREFLIGHT

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~

The previously granted T1-B read-only authorization can now be consumed by F5-8. It does not authorize
T1 mutation, production live execution, reboot, board access or merge.
