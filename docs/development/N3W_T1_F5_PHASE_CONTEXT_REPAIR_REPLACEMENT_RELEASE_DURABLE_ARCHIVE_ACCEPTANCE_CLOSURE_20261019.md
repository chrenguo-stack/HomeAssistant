# N3-W T1 F5 phase-context repair replacement release — durable Mac archive acceptance closure

Date: 2026-10-19

## Closure

~~~text
TASK=N3W_T1_F5_PHASE_CONTEXT_REPAIR_REPLACEMENT_RELEASE_DURABLE_ARCHIVE_20261019_01
RESULT=CLOSED_PASS

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

The production Mac populated the durable archive and then independently verified the same entry with
`gh` and `curl` replaced by hard-fail sentinels. The second verification therefore did not use GitHub
metadata lookup or artifact download.

Accepted durable path:

~~~text
~/Documents/N3W/approved-releases/
  31c8a8cd2d8424f93aaa7b4d0b78cfe2b73f1b035f4bdbce08a181ac56619420/
    12162160866/
      1938ad3e4d7b87622a21968961b3fea4472907c4b31cc8db8c80acfd0fb149e8/
        artifact.zip
        binding.json
~~~

This closes the replacement-release durability gate. It does not authorize another F5-9 production run.

## Next boundary

The failed historical run remains:

~~~text
RUN_ID=56e7cacb162fb2e2e56ff7e112f1a2177b64a68c4a1f1c0fdea66520e051602e
RUN_STATE=IN_PROGRESS
LAST_CLAIMED_PHASE=HOST_BASELINE
HOST_BASELINE_STATE=APPLYING
HOST_BASELINE_EXECUTION_LEDGER=ABSENT
REPLAY_ALLOWED=false
~~~

The next work is repository-only preparation of a bounded failed-run terminalization path, followed by exact
artifact/read-only preauthorization. Any target-side terminalization remains a new explicit live authorization
boundary.
