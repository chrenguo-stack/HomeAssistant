# N3-W T1 F5 phase-context repair replacement release — durable Mac archive preexecution

Date: 2026-10-19

## Gate

~~~text
TASK=N3W_T1_F5_PHASE_CONTEXT_REPAIR_REPLACEMENT_RELEASE_DURABLE_ARCHIVE_20261019_01
STATE=READY_FOR_REAL_MAC_ACCEPTANCE

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~

## Exact authority

~~~text
SOURCE_HEAD=9048dd7c6b48c0620471919c0cf96c96bdab71f1
SOURCE_TREE=7b567c7140fd403049a6f7c2fa51887be08e8c8d
BUILDER_HEAD=b2622cb7588d0224e1345abe84bd7aec307a2aae

RELEASE_ID=31c8a8cd2d8424f93aaa7b4d0b78cfe2b73f1b035f4bdbce08a181ac56619420
RELEASE_SHA256=1bbcb81bd84ec899e4c1d37fffef99defbbcc40509c49ce41048f6a6d92039ad
FILE_INDEX_SHA256=be36b3cd3f5a20099f870c55dcb78586e2e507fddc47bf5f589d85fab8091c83

WORKFLOW_RUN_ID=39195658088
ARTIFACT_ID=12162160866
ARTIFACT_NAME=n3w-t1-f5-approved-release-9048dd7c6b48c0620471919c0cf96c96bdab71f1
ARTIFACT_ZIP_SHA256=1938ad3e4d7b87622a21968961b3fea4472907c4b31cc8db8c80acfd0fb149e8
ARTIFACT_SIZE_BYTES=2536415496
ARTIFACT_EXPIRES_AT=2026-11-18T03:39:43Z

EXACT_RELEASE_CI=PASS
POST_UPLOAD_BINDING=PASS
~~~

## Real Mac acceptance

The already reviewed archive helper remains unchanged. Acceptance requires:

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
  31c8a8cd2d8424f93aaa7b4d0b78cfe2b73f1b035f4bdbce08a181ac56619420/
    12162160866/
      1938ad3e4d7b87622a21968961b3fea4472907c4b31cc8db8c80acfd0fb149e8/
        artifact.zip
        binding.json
~~~

This gate is Mac-local only. It must not connect to T1-B.

## After PASS

A durable archive PASS does not authorize target mutation. The failed run remains consumed,
non-replayable and `IN_PROGRESS/HOST_BASELINE=APPLYING` until a separately reviewed controlled
terminalization path is explicitly authorized and executed.

~~~text
AFTER_PASS_NEXT_STAGE=FAILED_RUN_CONTROLLED_TERMINALIZATION_PREAUTH
AUTO_EXECUTE_AFTER_PASS=false
NEW_LIVE_AUTHORIZATION_REQUIRED=true
~~~
