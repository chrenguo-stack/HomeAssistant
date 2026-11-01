# N3-W T1 fresh bootstrap R8 — replacement artifact binding and read-only preexecution preparation

Date: 2026-10-12
Gate: N3W_T1_FRESH_BOOTSTRAP_R8_REPLACEMENT_ARTIFACT_BINDING_AND_READONLY_PREEXECUTION_PREPARATION
Scope: repository/CI read-only verification and GitHub documentation only. No T1/board/live access.

## 1. Independent R8 F5 closure carried forward

- F5=CLOSED; DIRECT_PRIMARY_ROOT_EXECUTION=PASS; NONEMPTY_IMPORTS_FAILCLOSED_EXECUTION=PASS.
- DOWNSTREAM_SOURCE_BLOCKER=NO; NEW_BLOCKERS=0.
- F1/F2/F3/F4/F6/D1/A8 remain CLOSED; no new direct contrary evidence.
- Final reviewed product source: `5ed613673ec1ead29a1153d0e3916bdd3539a3fb`.
- Exact commit workflow results: 25/25 success, 0 failed.
- PR #541 at preparation preflight: OPEN/DRAFT/unmerged; head `685bc130f8b15545640b7ed223c5e90a24ad3479`; two commits after reviewed source changed documentation only.
- F5 repair: reject `config.get("imports")` unless absent or empty; raise `containerd_imports_unsupported` before resolving effective containerd image-store root. Generated storage-probe execution regressions cover direct primary root and non-empty imports fail-closed.
- This is source review closure, not live-T1 revalidation.

## 2. Replacement deployable payload binding

```text
SOURCE_HEAD=5ed613673ec1ead29a1153d0e3916bdd3539a3fb
RUN_ID=38245536856
ARTIFACT_ID=11746610745
ARTIFACT_NAME=n3w-t1-fresh-bootstrap-deployable-5ed613673ec1ead29a1153d0e3916bdd3539a3fb
ARTIFACT_ZIP_SHA256=3ae4314e1746704aac5b7fd59aa490519fd0e7fa0c7c2c8781c3b5dc11907d90
PAYLOAD_ARCHIVE_SHA256=896d8eff51e21c4686283afc4701b9b32f87a56b32f3b9243c26508003f316ec
PAYLOAD_MANIFEST_SHA256=36048d1cb77e4ee6a4aaf0bbc2019f434133b8ab0a210960e30ba9d4d53ea8ad
PROSPECTIVE_AUTHORIZATION=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_08
PROSPECTIVE_AUTHORIZATION_GRANTED=false
```

GitHub Actions artifact metadata reports non-expired artifact and exact source-head binding. Run #38245536856 job `deployable-payload` succeeded. Job logs show ZIP upload SHA=downloaded ZIP SHA, inner binding `FRESH_BOOTSTRAP_INNER_BINDING=PASS` and `FRESH_BOOTSTRAP_DEPLOYABLE_POST_UPLOAD_BINDING=PASS`. Focused source-contract tests: 71 passed; separate staging payload run #38245536675: 47 passed.

Evidence: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/38245536856

Scope of claim: existing CI-produced artifact is bound by recorded workflow integrity evidence. No file has been transferred to T1; independent host-side artifact re-download/byte rehash and T1 preflight remain for next execution stage. This is not a production activation or live authorization.

## 3. R3 retained payload cleanup — proposal only

- Retained R3 payload and three image tars are evidence. Preserve unchanged.
- Any cleanup must first identify the single exact remote retained directory by fresh T1 read-only evidence; no guessing directory from historical prefix.
- Produce exact absolute path, file-set, ownership, artifact lineage, relevant sha256s and proof it is not an active source, service state or current deployment.
- Separate R3 retained payload from the R8 replacement artifact; never sweep broad `/var/tmp` or Docker storage.
- Prohibit `rm`, `docker prune`, volume/image deletion or replacement until a later bounded cleanup step is explicitly permitted.
- CLEANUP_EXECUTED=false; CLEANUP_PATH=UNRESOLVED_FRESH_READONLY; retained evidence remains preserved.

## 4. Next read-only T1 preexecution contract

1. Verify actual T1 service/host baseline afresh: containers, images, volumes, networks, listening ports, ingress guard, relevant protected state and current authorization ledger. Compare historical minimal-host R3 cleanup baseline without assuming it is current.
2. Read `docker info`, active dockerd/containerd process arguments and effective containerd config, verify socket identity, check `imports` fail-closed, actual image-store root, filesystem IDs and free bytes for staging/Docker/image store.
3. Check remote transport and capacity against exact R8 artifact manifest and conservative peak+reserve rule, without payload transfer.
4. Read-only inventory R3 retained directory for later narrowly bounded cleanup decision.
5. Verify `_03` consumed/no-replay, `_04/_05/_06/_07` superseded-ungranted and `_08` ungranted/unclaimed.
6. STOP and independently review preflight evidence before any T1 mutation.

```text
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
R3_RETAINED_PAYLOAD_CLEANUP=false
REPLACEMENT_ARTIFACT_TRANSFER=false
PRODUCTION_SERVICE_START=false
AUTHORIZATION_08_GRANTED=false
PR541_MERGE=false
AUTO_EXECUTE_NEXT_GATE=false
```

## 5. Stop/status

SOURCE_CLOSURE=PASS
EXACT_REPLACEMENT_ARTIFACT_CI_BINDING=PASS
R3_CLEANUP_SCOPE=PREPARED_PENDING_FRESH_T1_EXACT_INVENTORY
T1_READONLY_PREFLIGHT_PLAN=PREPARED_NOT_EXECUTED
NEXT_STEP=FRESH_T1_READONLY_PREEXECUTION_AFTER_SEPARATE_STAGE_TRANSITION
LIVE_APPLY=NOT_AUTHORIZED
