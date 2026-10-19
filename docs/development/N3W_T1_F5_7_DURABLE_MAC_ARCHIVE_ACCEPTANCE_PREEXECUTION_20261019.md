# N3W T1 F5-7 Durable Mac Archive Acceptance — Preexecution

Date: 2026-10-19

## Gate

~~~text
TASK=N3W_T1_F5_7_DURABLE_MAC_ARCHIVE_ACCEPTANCE_20261019_01
STATE=READY_FOR_REAL_MAC_ACCEPTANCE

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~

## Exact authority

~~~text
SOURCE_HEAD=4afd89b56e9925d7330b27f3f734ebcefc09182c
SOURCE_TREE=da864ffb6c44de3efccb93516e5e786f16219cd9
BUILDER_HEAD=f30e5f74199bebcf1f189ee90b81ce5d19dc3df1

RELEASE_ID=c8a7e432722121b808a0d31ffbc3d049a64aa5b4f270a7be6f07b90891eecf69
RELEASE_SHA256=47f4f41cf1453642b889578bd7de906236b56ae34b9d7bbbc81412c78a48efbb
FILE_INDEX_SHA256=21a419ac843a3ef4c00fa2054435df403d0c5c16911bdf0f2e9dde3afb4b8ae9

WORKFLOW_RUN_ID=39259401930
ARTIFACT_ID=12190255517
ARTIFACT_NAME=n3w-t1-f5-approved-release-4afd89b56e9925d7330b27f3f734ebcefc09182c
ARTIFACT_ZIP_SHA256=c5928031d6813f91508eadd7bf79aca63e1fbe9c67e840f0a8277e8a09675f9f
ARTIFACT_SIZE_BYTES=2536416888
ARTIFACT_EXPIRES_AT=2026-11-18T13:22:23Z

ARCHIVE_HELPER_BLOB=60e454bf128419ffe23fa64bb33cf8ce9a084758
~~~

## Real Mac acceptance

The existing reviewed archive helper is reused unchanged. Acceptance requires exactly:

~~~text
FIRST_ARCHIVE=MISS_POPULATED
FIRST_ARCHIVE_STATUS=PASS
SECOND_VERIFY=VERIFY_ONLY
SECOND_VERIFY_STATUS=PASS
SECOND_VERIFY_GITHUB_ACCESS=false
PERSISTENT_STORE=true
~~~

Expected durable path:

~~~text
~/Documents/N3W/approved-releases/
  c8a7e432722121b808a0d31ffbc3d049a64aa5b4f270a7be6f07b90891eecf69/
    12190255517/
      c5928031d6813f91508eadd7bf79aca63e1fbe9c67e840f0a8277e8a09675f9f/
        artifact.zip
        binding.json
~~~

The first archive command may access GitHub to verify metadata and download the exact
artifact. The second verify must run with GitHub client/network helper access disabled
so PASS proves the local durable copy is independently usable.

This gate is Mac-local only. It must not connect to T1.

## Stop rule

~~~text
CURRENT_STOP_POINT=WAIT_REAL_MAC_ARCHIVE_OUTPUT
NEXT_IF_PASS=RECORD_DURABLE_ARCHIVE_CLOSURE_AND_REEVALUATE_NEXT_F5_PRODUCTION_GATE
NEXT_IF_FAIL=STOP_AND_CLASSIFY_ARCHIVE_OR_BINDING_FAILURE
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
~~~
