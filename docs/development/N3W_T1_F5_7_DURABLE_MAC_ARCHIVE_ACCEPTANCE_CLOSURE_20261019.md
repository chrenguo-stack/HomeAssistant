# N3W T1 F5-7 Durable Mac Archive Acceptance — Closure

Date: 2026-10-19

## Closure

~~~text
TASK=N3W_T1_F5_7_DURABLE_MAC_ARCHIVE_ACCEPTANCE_20261019_01
RESULT=CLOSED_PASS

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

FIRST_ARCHIVE=MISS_POPULATED
FIRST_ARCHIVE_STATUS=PASS
SECOND_VERIFY=VERIFY_ONLY
SECOND_VERIFY_STATUS=PASS
SECOND_VERIFY_GITHUB_ACCESS=false
PERSISTENT_STORE=true

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~

The production Mac populated the durable archive and then independently verified the same
entry from the local store. During the second verification, `gh` and `curl` were replaced
with hard-fail sentinels. The successful `VERIFY_ONLY` result therefore proves that the
archived release is independently usable without GitHub metadata lookup or artifact download.

Accepted durable path:

~~~text
~/Documents/N3W/approved-releases/
  c8a7e432722121b808a0d31ffbc3d049a64aa5b4f270a7be6f07b90891eecf69/
    12190255517/
      c5928031d6813f91508eadd7bf79aca63e1fbe9c67e840f0a8277e8a09675f9f/
        artifact.zip
        binding.json
~~~

## Docs-only rebuild disposition

After the frozen build head `f30e5f7...`, two repository commits added only F5-7
closure/preexecution documentation. The exact-release workflow reran at
`c7e57ea...` as run `39260248863`, but this is a docs-only rebuild and does not
supersede the frozen durable production artifact above.

~~~text
COMPARE_F30E_TO_C7E=DOCS_ONLY_2_FILES
DOCS_ONLY_REBUILD_RUN_ID=39260248863
DOCS_ONLY_REBUILD_NON_AUTHORITATIVE=true
FROZEN_DURABLE_ARTIFACT_ID=12190255517
FROZEN_DURABLE_WORKFLOW_RUN_ID=39259401930
~~~

Any later workflow rerun caused only by closure/progress documentation is likewise
non-authoritative unless a separate gate explicitly rebinds the production release.

## Next boundary

The earlier F5-8 read-only closure was bound to source
`6e228a4b2c7c4ff78918571abb7b583e416615ee` and release
`b89c9e227e53fcac2ef2717d7b11cd6b64536ce27c9b6b16c2429980049c8a69`.
It cannot be reused as read-only authorization evidence for the current
`4afd89b...` release.

A fresh F5-8-equivalent read-only preflight must rebind the selected T1-B to the current
durable release before any new F5-9 production authorization can be considered.

~~~text
F5_7=CLOSED_PASS
CURRENT_RELEASE_DURABLE_ARCHIVE_CLOSED=true

NEXT_ONE_GATE=N3W_T1_F5_8_CURRENT_RELEASE_T1B_READONLY_PREFLIGHT_20261019_01
T1B_READONLY_AUTHORIZATION_REQUIRED=true
T1B_READONLY_AUTHORIZATION_GRANTED=false

NEW_F5_9_PRODUCTION_AUTHORIZATION=false
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
~~~
