# N3W T1 F5 V1 Durable Release Archive — Mac Acceptance Closure

Date: 2026-10-19

> Historical evidence notice (2026-10-19): this document closes durable archive acceptance for the earlier release built from source `55e499f...`. F5-8 preexecution subsequently found and repaired a production preflight confirmation mismatch at source `6e228a4...`. Therefore this closure remains valid history but is superseded as current production authority; the repaired release requires a fresh durable Mac archive acceptance before T1-B access.

## 0. Conclusion

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V1_DURABLE_RELEASE_ARCHIVE_20261019_01
RESULT=CLOSED_PASS

PR=614
PR_STATE=OPEN_DRAFT_UNMERGED
PR_EXECUTABLE_HEAD_BEFORE_CLOSURE_DOCS=acd2368e41c6772e3a081874c38aa52e05455779
ARCHIVE_TOOL_BLOB=60e454bf128419ffe23fa64bb33cf8ce9a084758
ARCHIVE_SOURCE_CI=PASS:12/12

F5_7_CLOSED_PASS=true
F5_8_BLOCKED_BY_F5_7=false
F5_8_T1_ACCESS_AUTHORIZED=false

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~

F5-7 is closed. The exact production release is built, post-upload verified, preserved on the real
production Mac in a durable Documents store, and independently verified from that local store while
GitHub command paths were hard-disabled.

## 1. Exact approved release

~~~text
PRODUCT_SOURCE_HEAD=55e499f28d4b1a79da0c5c1fbd21b513f24644e6
PRODUCT_SOURCE_TREE=4212298609fbb80557984fdc350cb6d336c41f53
BUILDER_HEAD=8770e17f096fa9eb035ec32bbe32731abed62bfd

RELEASE_ID=4eae02a0ef306b82771d6a40dfcb44266457a42ae8d3eaace587c4a094225fa9
RELEASE_SHA256=1b046c95ab612ad63fbe911be4b1d7a38e17456906e63edf8ab70aa35164296e
FILE_INDEX_SHA256=005f1594d62c300af5452d86f837f9d2a8fe292d45826e4a33b2b57748a3e7ac

WORKFLOW_RUN_ID=39182332219
ARTIFACT_ID=12157105538
ARTIFACT_NAME=n3w-t1-f5-approved-release-55e499f28d4b1a79da0c5c1fbd21b513f24644e6
ARTIFACT_ZIP_SHA256=62b76cb69bafb18adf5f6e3d48008a8cf8e567e00e7a68a8f19606e1c2e5dd1c
ARTIFACT_SIZE_BYTES=2536414909
ARTIFACT_EXPIRES_AT=2026-11-18T00:48:45Z
~~~

The exact-release CI at builder head `8770e17...` completed 13/13 PASS, including post-upload
re-download and release binding verification.

## 2. First Mac archive acceptance

The real Mac used the exact artifact above.

Observed result:

~~~text
FIRST_ARCHIVE=MISS_POPULATED
STATUS=PASS
PERSISTENT_STORE=true
T1_ACCESS=false
BOARD_ACCESS=false
~~~

The archive helper verified GitHub artifact identity, outer ZIP SHA-256, approved-release SHA and
release ID, the complete release file index, every indexed file size/SHA-256, and exact
source/tree/builder provenance before atomically publishing the local entry.

## 3. Independent local verify

A second verification was performed against the persistent store with both `gh` and `curl`
replaced in `PATH` by hard-fail sentinels.

Observed result:

~~~text
SECOND_VERIFY=VERIFY_ONLY
STATUS=PASS
SECOND_VERIFY_GITHUB_ACCESS=false

RELEASE_ID=4eae02a0ef306b82771d6a40dfcb44266457a42ae8d3eaace587c4a094225fa9
RELEASE_SHA256=1b046c95ab612ad63fbe911be4b1d7a38e17456906e63edf8ab70aa35164296e
FILE_INDEX_SHA256=005f1594d62c300af5452d86f837f9d2a8fe292d45826e4a33b2b57748a3e7ac
BUILDER_HEAD=8770e17f096fa9eb035ec32bbe32731abed62bfd
SOURCE_HEAD=55e499f28d4b1a79da0c5c1fbd21b513f24644e6
SOURCE_TREE=4212298609fbb80557984fdc350cb6d336c41f53
~~~

This closes the architecture requirement that the production release remain recoverable after the
temporary GitHub Actions artifact is unavailable.

## 4. Accepted durable store

~~~text
~/Documents/N3W/approved-releases/
  4eae02a0ef306b82771d6a40dfcb44266457a42ae8d3eaace587c4a094225fa9/
    12157105538/
      62b76cb69bafb18adf5f6e3d48008a8cf8e567e00e7a68a8f19606e1c2e5dd1c/
        artifact.zip
        binding.json
~~~

The store is a recovery/transport copy. It does not replace the reviewed release authority.

## 5. Failure history retained

The superseded artifact `12156115228` failed the first Mac acceptance with
`release_index_file_set_mismatch`. No durable entry was published. Source review traced this to
post-index Python bytecode files and insufficient index-to-file-set verification. PR #613 repaired the
builder at `8770e17...`; the superseded artifact must not be used.

The failure remains part of the permanent evidence chain and is not rewritten as a successful attempt.

## 6. Next boundary

~~~text
CURRENT_STOP_POINT=AFTER_F5_7_BEFORE_F5_8_T1B_READONLY_PREFLIGHT_AUTHORIZATION
NEXT_ONE_GATE=N3W_T1_F5_PRODUCTION_PROCESS_V1_T1B_READONLY_PREFLIGHT

F5_8_READINESS=READY_REQUIRES_EXPLICIT_T1_READONLY_AUTHORIZATION
T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~

F5-8 may now be prepared, but no T1-B connection is authorized by this closure.
