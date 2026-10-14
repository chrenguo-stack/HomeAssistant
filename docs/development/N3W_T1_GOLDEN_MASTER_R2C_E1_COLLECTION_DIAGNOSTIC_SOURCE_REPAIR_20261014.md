# N3W T1 Golden Master R2C E1 collection diagnostic source repair

Date: 2026-10-14
PR: #541 (OPEN / DRAFT / unmerged)
Historical execution source: `a7cf9b569133bcd6a08ace65027b4730cdd54a11`
Source repair: `4898e519c317195dc22915a8d7b47f246a4121cf`

## 1. Result

```text
TASK=N3W_T1_GOLDEN_MASTER_R2C_E1_COLLECTION_DIAGNOSTIC_SOURCE_REPAIR
RESULT=CLOSED_SOURCE
HISTORICAL_E1_STATUS=ERROR
HISTORICAL_E1_REASON=STOP_E1_COLLECTION_ERROR
HISTORICAL_REPORT_CHANGED=false
LOCAL_R2C_TESTS=87/87_PASS
RUFF=PASS
PUBLIC_REPOSITORY_SAFETY=PASS
SOURCE_HEAD_CI=42_SUCCESS_1_CONDITIONAL_SKIP_0_FAILURE
T1_ACCESS=false
AUTHORIZATION_REUSED=false
INTENTIONAL_TARGET_WRITE=false
SERVICE_MUTATION=false
BOARD_ACCESS=false
MERGE=false
E1_TARGET_OBSERVATION_PROVEN=false
OS_IDENTITY_SEMANTICS_PROVEN=false
CONTROLLED_CLONE_BOOT_REQUIRED=true
DISK_CAPTURE_READY=false
```

The repository-only E1 diagnostic repair is closed at source level. It prevents controlled
command, read-only evidence and filesystem failures from collapsing into the generic
`STOP_E1_COLLECTION_ERROR` reason. It also accepts the standard root-owned systemd executable
location used by usr-merged systems while retaining strict executable trust checks.

This source closure does not reinterpret the immutable historical report and does not claim a
new target observation. The historical E1 result remains ERROR with
`STOP_E1_COLLECTION_ERROR` until a separately authorized future capture produces new evidence.

## 2. Diagnosis

`collect_e1()` previously converted all bounded command, read-only evidence and filesystem
exceptions to one generic reason. This erased the failure class needed for safe diagnosis.

The command resolver also required every resolved executable to remain under the four command
search directories. On a standard systemd installation, `/usr/bin/systemd` can resolve to
`/usr/lib/systemd/systemd` or `/lib/systemd/systemd`; both locations were rejected even though
the command name was found through the fixed safe path.

The private historical report does not preserve the underlying E1 exception class. The
systemd resolution mismatch is therefore a source-path defect repaired by this change, not a
claim that the exact historical target exception has been proven.

## 3. Repair

The repair makes two bounded changes:

- E1 maps controlled collector, command, read-only evidence and filesystem exceptions to
  stable reason-code namespaces. Unknown or unsafe exception text remains generic.
- Executable resolution permits only the exact standard systemd realpaths
  `/usr/lib/systemd/systemd` and `/lib/systemd/systemd` outside the existing safe directories.
  The resolved file must be regular, executable, owned by UID 0, and not group- or
  world-writable. Every other out-of-path resolution remains rejected.

The remote executor's immutable module bindings were updated to:

```text
READONLY_COMMANDS_BLOB=8e66154edf9494141681ab76d969f9f1cdc38050
COLLECTORS_BLOB=5253ac1328e03eca81fc916f0a14d6074021a11b
```

## 4. Verification

The focused regression coverage verifies:

- exact trusted systemd realpaths are accepted;
- unapproved out-of-path realpaths are rejected;
- writable approved realpaths are rejected;
- E1 preserves a bounded command failure class;
- filesystem errno is preserved as a bounded reason without leaking exception text.

Local verification completed with 87/87 R2C tests passing, Ruff passing, nine tool-unit tests
passing and the public repository safety check passing. PR #541 then completed at the exact
source-repair head with 42 successful checks, one conditional skip and zero failures.

## 5. Boundary and next gate

No T1 connection was made. The consumed one-shot authorization was not reused and is not
replayable. No target write, service mutation, board action or merge occurred.

E1 is source-repaired but not target-proven. E2, E3, E4 and E5 remain unresolved evidence or
semantics gaps; E6, E7 and E9 remain bounded UNKNOWN in the last capture; only E8 remains
complete. OS identity semantics are still unproven, controlled clone boot remains mandatory,
and disk capture and Final Seal remain forbidden.

Any future T1 observation requires a fresh exact-source/package rebind, fresh Gate 0/1 and a
new explicit one-shot authorization. It is not entered automatically by this closure.
