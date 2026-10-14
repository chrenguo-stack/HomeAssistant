# N3-W T1 Golden Master R2C Target-Armbian Read-only Evidence
# One-shot Execution and Evidence-Gap Closure — 2026-10-14

~~~text
TASK=N3W_T1_GOLDEN_MASTER_R2C_TARGET_ARMBIAN_SEAL_ADAPTER_READONLY_EVIDENCE
EXECUTION_RESULT=PASS
CAPTURE_STATUS=FAILED
GATE_RESULT=STOP_EVIDENCE_GAPS

PREEXECUTION_SOURCE_HEAD=403413f89373d0650579c3886274e59be37783bc
PROBE_SHA256=6d24ac8e7eff38be165c69eaaff4042808017887969e79c08a1c87ab9518ac25
CONTRACT_SHA256=f3f0213cca63918341b9b0221133d882eb8e24f444d8432f8fdf1f94929b6866
EXECUTOR_BLOB=389a76848c2897290b102b61d2636e70e53315e9
EXECUTION_ID=r2c-20261014-d3a2c82709732756ce9efb21574f9cef

AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
T1_ACCESS=true
INTENTIONAL_TARGET_WRITE=false
SERVICE_MUTATION=false
BOARD_ACCESS=false
MERGE=false

OS_IDENTITY_SEMANTICS_PROVEN=false
CONTROLLED_CLONE_BOOT_REQUIRED=true
DISK_CAPTURE_READY=false
~~~

## 0. Result

The second explicit one-shot confirmation was bound to the exact frozen source package only
after the operator established a T1-specific strict SSH alias from an ED25519 host public key
and fingerprint obtained at the local T1 console. The final private preclaim passed, the
authorization was claimed once, and exactly one bounded SSH transport was executed.

The transport, remote program execution and report-schema validation passed with remote exit
zero. The collector intentionally made no target write and performed no service, board or merge
action. The authorization is permanently consumed and must not be replayed.

The transaction result and the evidence result are separate:

~~~text
SSH_TRANSPORT=PASS
REMOTE_EXIT=0
REPORT_SCHEMA_VALIDATION=PASS
EXECUTION_RESULT=PASS
CAPTURE_STATUS=FAILED
STATIC_REVIEW_STATUS_AT_CAPTURE=NOT_EXECUTED
PUBLIC_PROJECTION_REVIEW_AT_CAPTURE=NOT_REVIEWED
~~~

The R2C gate is therefore not accepted. It stops on evidence gaps before adapter implementation,
Golden Master capture or Final Seal.

## 1. Exact execution binding

~~~text
EXPECTED_SOURCE_HEAD=403413f89373d0650579c3886274e59be37783bc
OBSERVED_SOURCE_HEAD=403413f89373d0650579c3886274e59be37783bc
LOCAL_TRACKED_WORKTREE_CLEAN=true
EXECUTOR_BLOB=389a76848c2897290b102b61d2636e70e53315e9
PROBE_SHA256=6d24ac8e7eff38be165c69eaaff4042808017887969e79c08a1c87ab9518ac25
CONTRACT_SHA256=f3f0213cca63918341b9b0221133d882eb8e24f444d8432f8fdf1f94929b6866
REMOTE_PROBE_FILE_CREATED=false
PYTHON_BYTECODE_WRITE_DISABLED=true
STRICT_HOST_KEY_CHECKING=true
SAME_BOOT=true
~~~

No private locator, address, port, host key, fingerprint, target-binding token or raw target
value is recorded in this repository.

## 2. Private evidence integrity

The private evidence remains outside the repository under operator-only permissions. Only
non-secret integrity facts are recorded here:

| Private artifact | SHA-256 |
| --- | --- |
| start.json | 82bccb626e13b00defb2e72d8822cc09a4e8f3b4932afaf978b252ed3689ed11 |
| authorization-claim.json | 2f2183679ffb7bc8acbf6ea14d62ad6acd0bdb422665b57232e9c55f17f26cce |
| command.json | 09a647b551acc58c9631cf132a3effd82c2f394699da74be6979802eb5bf5ee0 |
| stdout.bin | 7dee43020167ea7e43d99026f419e25d58eed2f11bb09aed00ba74f0af40307c |
| stderr.bin | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| report.json | de1576110dac3f10c01c3ef37c948ec2c5ea166fabed06df7d25a9af3442c3a6 |
| public-candidate.json | 087aa93dfcba598d60505884d567b5ff508cdbd4ffe7cd30885201a9577771a6 |
| authorization-result.json | 9655337cba9e8c14158b858cfda192021393b112ae340e1cb9e23fb0471b92d8 |
| result.json | e011bc18261d4f251c2f3dfea1f2d1dbda1ef517ee2adf7e6cdfa3b54e880faf |

~~~text
STDOUT_BYTES=15136
STDERR_BYTES=0
PRIVATE_EVIDENCE_FILE_MODE=0600
PRIVATE_EVIDENCE_ROOT_MODE=0700
~~~

## 3. E1-E9 result

| Requirement | Status | Complete | Reason |
| --- | --- | --- | --- |
| E1 | ERROR | false | STOP_E1_COLLECTION_ERROR |
| E2 | UNKNOWN | false | STOP_UNRESOLVED_IMPLEMENTATION |
| E3 | UNKNOWN | false | STOP_CONFIG_UNRESOLVED |
| E4 | UNKNOWN | false | STOP_SEMANTICS_GAP |
| E5 | UNKNOWN | false | STOP_SSH_IDENTITY_UNKNOWN |
| E6 | ERROR | false | STOP_E6_COLLECTION_ERROR |
| E7 | ERROR | false | STOP_EXPECTED_DIRECTORY |
| E8 | OBSERVED | true | none |
| E9 | ERROR | false | STOP_E9_COLLECTION_ERROR |

The complete STOP set is:

~~~text
STOP_CONFIG_UNRESOLVED
STOP_E1_COLLECTION_ERROR
STOP_E6_COLLECTION_ERROR
STOP_E9_COLLECTION_ERROR
STOP_EXPECTED_DIRECTORY
STOP_SEMANTICS_GAP
STOP_SSH_IDENTITY_UNKNOWN
STOP_UNRESOLVED_IMPLEMENTATION
~~~

E8 is the only complete requirement. E2-E5 contain bounded observations but do not prove the
required semantics. E1, E6 and E9 fail with generic collection errors, which is insufficient
for a safe target-vs-source disposition without a repository-side diagnostic repair. E7 proves
that at least one expected journald root is not represented as the collector's required
directory type; no traversal or mutation was attempted.

## 4. Public projection review

The generated public candidate was reviewed after capture:

~~~text
PUBLIC_PROJECTION_REPRODUCIBLE=PASS
PUBLIC_RAW_VALUE_KEYS=0
PUBLIC_IP_LITERAL_COUNT=0
PUBLIC_MAC_LITERAL_COUNT=0
PUBLIC_SSH_KEY_LITERAL_COUNT=0
PUBLIC_TARGET_ALIAS_LITERAL_COUNT=0
POSTCAPTURE_PUBLIC_PROJECTION_SAFETY_REVIEW=PASS
~~~

The public candidate preserves only requirement status, completion, fixed reason codes, method
IDs and field statuses. Its capture-time fields remain truthfully
static_review_status=NOT_EXECUTED and public_projection_review=NOT_REVIEWED; the post-capture
review above is recorded separately and does not rewrite captured evidence.

## 5. Corrected preclaim history

The first private preclaim correctly stopped before claim, but its initial SSH-alias
classification was imprecise. The similarly named local alias found on the Mac belonged to a
local virtual-machine environment, not T1. The actual T1 state at that time was:

~~~text
T1_SPECIFIC_SSH_ALIAS_PRESENT=false
T1_EXISTING_TRUSTED_HOST_BINDING_PRESENT=false
FIRST_AUTHORIZATION_CLAIMED=false
FIRST_AUTHORIZATION_CONSUMED=false
~~~

The operator later obtained the target host identity through the T1 local console, created a
separate strict T1 alias and known-host binding, and passed a fresh no-network preclaim before
granting the second authorization. The unrelated local virtual-machine configuration was not
used or modified.

## 6. Next gate

~~~text
NEXT_ONE_GATE=N3W_T1_GOLDEN_MASTER_R2C_EVIDENCE_GAP_SOURCE_REVIEW_AND_REPAIR
NEXT_GATE_SCOPE=REPOSITORY_ONLY
NEW_T1_AUTHORIZATION_REQUIRED_FOR_ANY_RERUN=true
R2C_ADAPTER_IMPLEMENTATION_NOT_ENTERED=true
GOLDEN_MASTER_CAPTURE_NOT_ENTERED=true
FINAL_SEAL_NOT_ENTERED=true
~~~

The next gate must first use the retained private evidence and source tests to:

1. replace generic E1/E6/E9 collection failures with bounded diagnosable classifications;
2. classify E7's non-directory journald root without following an unapproved path;
3. resolve or explicitly retain the E2-E5 semantic gaps;
4. pass exact-source CI and focused review.

Only after source closure may a new target rerun be proposed. It requires a new explicit
one-shot authorization and must not reuse the consumed grant.

