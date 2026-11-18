# N3-W T1 U13B P3 U10 read-only preflight Attempt 01 false-STOP

Date: 2026-11-18

## Attempt result

```text
RESULT=STOP
REASON=private_file_metadata_invalid
STAGE=bind_durable_u9
EXIT_CODE=2
READ_ONLY=true
DESTRUCTIVE_CUTOVER=false
DESTRUCTIVE_CUTOVER_ELIGIBLE=false
U10_TRANSITION=false
U11_PLUS=false
PREDECESSOR_RUNTIME_DELETE=false
PREDECESSOR_IMAGE_DELETE=false
TARGET_IMAGE_LOAD=false
SERVICE_MUTATION=false
LOCAL_RECEIPT_SHA256=30922a0e0afe09dcd5e80ae11cb3bd52f2313dd9cbc3a584829db87a4178c888
```

The live T1 remained at the durable U9 checkpoint. No U10 mutation occurred.

## Root cause

The failure occurs at the first U9 ledger read in `u9.inspect()`: `claim.json`.

The U9 executor created ledger files through `write_once(path.open("xb"))`, but the remote U9 entry did not force a private umask. The durable U9 write succeeded because the execute path did not subsequently re-read the newly created ledger file through the strict `0600` reader. U10 Attempt 01 was the first path to do so.

The U9 ledger directory itself is root-only. For authority integrity, the repair accepts a ledger record only when:
- its parent directory passes the existing root-only private-directory check;
- the record is a regular file;
- owner UID is root;
- group/other write bits are absent.

This accepts the already-durable root-owned non-writable authority record without mutating it. Future remote U9 execution also explicitly sets `umask 077`.

## Source repair

```text
REPAIR_HEAD=4385b36c32a692e2e0c1d3484cb714551b37501a
T1_MUTATION=false
U9_REPLAY=false
U10_MUTATION=false
```

CI was still running after the configured polling limit. Attempt 02 must not run until the repair CI is SUCCESS.
