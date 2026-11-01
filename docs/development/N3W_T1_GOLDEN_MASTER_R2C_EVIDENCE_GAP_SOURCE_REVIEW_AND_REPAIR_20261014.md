# N3W T1 Golden Master R2C evidence-gap source review and repair

Date: 2026-10-14  
PR: #541 (OPEN / DRAFT / unmerged)  
Historical capture authority: `403413f89373d0650579c3886274e59be37783bc`  
Repair base: `9c3bbd584a55de91f5546841e5b25e969f3bf481`  
Source-repair authority: `040caff5dabe13bc419155593a32f4e2a727a309`

## 1. Result

```text
TASK=N3W_T1_GOLDEN_MASTER_R2C_EVIDENCE_GAP_SOURCE_REVIEW_AND_REPAIR
RESULT=CLOSED_SOURCE
LOCAL_R2C_TESTS=83/83_PASS
SOURCE_HEAD_CI=42_SUCCESS_1_CONDITIONAL_SKIP_0_FAILURE
T1_ACCESS=false
AUTHORIZATION_REUSED=false
INTENTIONAL_TARGET_WRITE=false
SERVICE_MUTATION=false
BOARD_ACCESS=false
MERGE=false
HISTORICAL_CAPTURE_REINTERPRETED=false
OS_IDENTITY_SEMANTICS_PROVEN=false
CONTROLLED_CLONE_BOOT_REQUIRED=true
DISK_CAPTURE_READY=false
```

The repository-only review reproduced the source causes behind the historical E1, E6, E7 and
E9 failures and repaired those bounded collector paths. The repair does not retroactively alter
the one-shot report, does not convert any historical UNKNOWN or ERROR to OBSERVED, and does not
authorize a target rerun.

## 2. Root-cause review

| Requirement | Historical result | Source cause | Review conclusion |
| --- | --- | --- | --- |
| E1 | `STOP_E1_COLLECTION_ERROR` | One approved package can be absent while `dpkg-query -W` still returns useful rows with exit 1; the collector discarded the partial bounded evidence. | Exit 1 is accepted only when stderr proves the exact approved missing package set; all other failures remain STOP. |
| E6 | `STOP_E6_COLLECTION_ERROR` | On usr-merged systems `/lib` is a symlink to `/usr/lib`; parent-component no-follow protection rejected `lib/netplan`. | Only the exact `lib -> usr/lib` or `lib -> /usr/lib` alias is mapped lexically. Arbitrary aliases remain UNKNOWN and are never followed. |
| E7 | `STOP_EXPECTED_DIRECTORY` | A journal root existed as a non-directory object and `_scan` promoted that classification gap to a collector error. | The root kind is recorded without following it and the requirement remains UNKNOWN with `STOP_JOURNAL_CLASSIFICATION`. |
| E9 | `STOP_E9_COLLECTION_ERROR` | The same usr-merge alias affected systemd relation scans and `/lib/systemd/system` fragment binding. | Exact usr-merge aliases are mapped and duplicate scans are removed; unapproved aliases remain a bounded UNKNOWN. |
| E4 supporting capture | UNKNOWN | A masked systemd unit can report `FragmentPath=/dev/null`, which was outside the approved unit roots. | `LoadState=masked` plus the exact `/dev/null` fragment is classified as `MASKED_NULL` without opening the device. |

## 3. Implemented source boundaries

- E1 validates every returned package row against the fixed approved package set, rejects
  duplicates and malformed output, and records proven package absence as C3 provenance.
- E6 and E9 use one shared lexical usr-merge resolver. It reads only the root-level `lib`
  symlink target and accepts only the two fixed `/usr/lib` spellings.
- E7 inspects journal-root metadata first. Symlink and other non-directory roots are not scanned
  or followed.
- Controlled read and filesystem failures now map to bounded reason codes instead of losing all
  diagnostic class information in a generic collection error.
- The remote executor's module blob bindings were advanced to the repaired collector blobs.
  This makes the old execution package non-current; it does not permit reuse of the consumed
  authorization.

## 4. Validation

At the clean source-repair authority commit:

- all 83 repository R2C tests passed, including exact local source-authority binding;
- Ruff passed for the changed source and tests;
- Git diff whitespace validation passed;
- PR #541 completed with 42 successful checks, one conditional skip and zero failures;
- the tracked-content safety check passed;
- the PR remained OPEN, DRAFT and unmerged.

Regression coverage includes partial package-query success, unproven package absence, exact and
unapproved usr-merge aliases, non-following journal-root classification, masked `/dev/null`
classification, controlled failure reason codes and deterministic executor source binding.

## 5. Remaining evidence limits

This source repair closes the identified generic collector-failure classes only. It does not
prove the unresolved target semantics from the historical report:

- E2 still requires package ownership/provenance closure;
- E3 still has no observed identity-setting source;
- E4 still requires full first-boot semantics closure beyond the masked-unit classification;
- E5 still has default SSH host-key semantics unbound;
- E6/E7/E9 require a new capture before any target-specific result can change.

Therefore `OS_IDENTITY_SEMANTICS_PROVEN=false`, controlled clone boot remains required, and disk
capture and Final Seal remain forbidden.

## 6. Next gate

Any new target observation must begin with a fresh repository/head and execution-package rebind,
fresh Gate 0/1 validation and a new explicit one-shot authorization. The authorization consumed
by the historical execution is not replayable. No target gate is entered by this source closure.
