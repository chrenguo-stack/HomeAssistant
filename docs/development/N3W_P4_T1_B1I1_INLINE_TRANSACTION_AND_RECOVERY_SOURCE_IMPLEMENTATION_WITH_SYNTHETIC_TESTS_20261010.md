# N3-W P4 T1 — B1I1 inline transaction and recovery source-core implementation and synthetic acceptance (2026-10-10)

## 0. Authorization, exact boundary and prior source

User approved only `N3W_P4_T1_B1I1_INLINE_TRANSACTION_AND_RECOVERY_SOURCE_IMPLEMENTATION_WITH_SYNTHETIC_TESTS`. Source authoring, simulated fault injection, GitHub CI and documentation alignment are in scope. **Not authorized:** executing anything on T1, creating a real host unit, stopping/renaming/deleting the real Manager, changing Broker/DynSec/HA/R5/TLS, cleaning R2/R3/R4 data, board boot or NVS reset, Setup Secret handoff, PR merge, fourth production replacement.

Previous exact design:
`docs/development/N3W_P4_T1_B1_KF098_INLINE_CUTOVER_EXECUTOR_SOURCE_DESIGN_AND_RISK_REVIEW_20261009.md`; successful KF-098 source `88e9d140e5baddba543a961f003d12f7ce563ed2`; older R4 source `1528ae970974fd711f8a8a6441c29817a118d825`. This new core is isolated from all R4 global state and names; it does not import the R4 mutable transaction/recovery implementation.

## 1. Actual source implementation

New separate directory: `tools/execution_packages/n3w/p4_manager_b1_inline/`.

| Source | Responsibility and provenance |
|---|---|
| `b1i1_contract.py` | B1I1 unique names, exact three RW + three RO mount target contract, old Manager/Broker IDs, candidate image and 40-hex exact Git ref, health interface, injected Ops protocol |
| `b1i1_journal.py` | root-private 0700, journal 0600, exclusive create (no replay), fsync file and containing directory, atomic updates, durable mutation intent, restricted states; asserts old/candidate/Broker/source identity |
| `b1i1_transaction.py` | bounded preparation, durable stop/park/create/start/postflight/commit intents, create-then-inspect ownership recheck **before candidate start**, inline recovery of known exceptions, committed-vs-finalized terminal distinction, no false rollback after commit |
| `b1i1_recovery.py` | exact original ID and original Broker authority, operation-proven transaction ownership for the candidate, including crash between Docker create and journal ID binding; unknown/foreign container => fail closed without stop/delete; read-only reconcile and separately approved controlled recovery |
| `b1i1_supervisor.py` | finite budget with rollback reserve and no-forward-after-rollback rule, host-owned plan requiring explicit source/auth and Restart=no |
| `b1i1_host_runner.py` | injectable, simulation-only host-owned single-use gate with independent 0600 claim marker, denies SSH-as-owner and authorization/source ref mismatch |
| `b1i1_preflight.py` | pure Manager/Broker ID/image/start/restart, HA/R5/TLS and six original mount/source/permissions guard |
| `b1i1_fresh_state.py` | exact new three RW and unchanged three RO, all new sources disjoint from originals and each other; ten required business tables zero and relay-keys empty |
| `README.md` | explicitly advertises SOURCE ONLY / no Docker adapter, live host unit, exact artifact or runnable Mac command |

CI entry: `.github/workflows/n3w-p4-b1i1-inline-synthetic-ci.yml` is bounded to pure `compileall` and `unittest discover`, with no real SSH, Docker or board actions. Test modules:
`test_b1i1_transaction.py`, `test_b1i1_recovery.py`, `test_b1i1_guards.py`, `test_b1i1_host_runner.py`.

The deliberate implementation boundary: **there is no real `Operations` backend** and no `main()` that could carry out production T1 changes. The code validates the orchestration and pure safety contracts only. A booleans-from-a-fake test or host ownership assertion is not a real Manager/Broker/TLS/HA/R5 runtime attestation.

## 2. Test scope and specific evidence

Deterministic fault injection covers:

1. Preflight failure without journal; prepare/shadow failure without old stop; fail-closed deadline and rollback reserve.
2. Stop old, park old, create candidate, start, health, DB zero, mounts/security, Broker/HA/R5, old parked identity, precommit final verification; failures before and after side effects.
3. Candidate created but ID not durably bound: abrupt process exit, durable `CANDIDATE_CREATE_INTENT`, unknown read-only reconciliation; separately authorized recovery only when exact operation-supplied transaction token and candidate ID evidence match.
4. Foreign-name collision or unprovable ownership: **never** quarantine unknown candidate, never claim old restored.
5. Candidate ID binding/ownership inspection **before** start, manager/Broker/source ref authority, final committed candidate read-only proof, committed-but-second-check-unknown => FROZEN, not automatic rollback.
6. Private root 0700, journal/host claim 0600, journal schema and phase validation, replay denied, exact authorization ID and source binding, no SSH-owned process accepted as host transaction owner.
7. Six bind mount types, RW/RO separation, distinct original and new RW source paths, HA/R5/TLS 8883, Broker ID/start/restart.
8. Ten expected zero registration/credential/replay tables and empty relay-key root; rejects any nonzero or incomplete table proof.

```text
B1I1_SOURCE_CORE=IMPLEMENTED_IN_BRANCH
B1I1_REAL_DOCKER_ADAPTER=NOT_IMPLEMENTED
B1I1_REAL_HOST_UNIT=NOT_IMPLEMENTED
B1I1_EXACT_ARTIFACT_BUILD=NOT_EXECUTED
B1I1_MAC_LIVE_LAUNCHER=NOT_IMPLEMENTED
B1I1_T1_LIVE_PRECHECK=NOT_EXECUTED
B1I1_T1_REAL_DEPLOY=NOT_EXECUTED
B1I1_SIMULATION_PRELIM_RUN=37956691590
B1I1_SIMULATION_PRELIM_TESTS=44_PASS
B1I1_GITHUB_PR=540_OPEN_DRAFT
PR_MERGE=false
```

Results above belong solely to simulated source logic, not production readiness. Latest branch-head CI must be checked separately after documentation update.

## 3. Open gates and independent review blockers

### P1 — required before operational source readiness

**Real Docker / host adapter remains unimplemented.** Its trusted `Operations` methods must actually verify root-owned R5/old cold-backup identity, exact image build/source, current Manager and Broker IDs, start/restart timestamps, six real mounts and RO secret owners, HA/R5 guard and TLS8883, old Manager's restart policy and readiness. The pure `validate_live_origin` snapshot verifier is not a substitute for safely acquiring the snapshot.

**Host-owned exact one-shot remains unimplemented.** `HostOwnedPlan` and `execute_host_owned` validate an injected `host_unit_verified` boolean. This cannot prove a real systemd unit exists, its lifetime/rollback budget is correct or that SSH disconnection will not terminate the transaction. A new isolated host-owned service, exact source/artifact manifest and real crash watchdog/reconcile are mandatory.

**Real readiness remains unimplemented.** The transaction requires `healthz`, UDP47111/TCP47112, pairing IPC, TLS8883, actual initialized SQLite tables with row counts 0 and empty relay-key directory; the live adapter must prove them with time-bounded operations. The simulated `FakeOps` can only test dispatch and failure classification.

**Candidate ownership evidence needs adversarial independent scrutiny.** In the crash window `docker create` succeeded but journal ID missing, only the live adapter can prove an existing candidate really belongs to this exact transaction using a durable unpredictable token, image, six mounts and parked original ID. It must not trust a name alone or reuse stale R4 globals. If uncertain, freeze without destroying anything.

**Commit and abnormal death:** SIGKILL/host power loss cannot be handled by the inline catch. Current source has an API for read-only reconcile and approved recovery, but an actual host-owned recovery daemon or one-shot implementation is not yet provided. Any post-commit mismatch remains UNKNOWN_FROZEN, and no retry is permitted.

### P2 — tests and institutional gate

- Independent code review of journal atomicity/fsync, status contradiction handling, failure between action and intent, exhausted time while rollback, unauthorized recovery, exact phase+candidate ownership contract, and R2/R3/R4 historical evidence boundary.
- Explicit source inventory and image artifact binding for any future real backend.
- Fresh T1 **read-only** runtime baseline plus Broker DynSec old-account/ACL and board persistent identity inventory before authorizing any new physical first pair.
- Full source/CI and distinct explicit live approval for B1I1 when and only when above are closed.

## 4. Current stop / next gate

```text
CURRENT_ONE_GATE=N3W_P4_T1_B1I1_INLINE_TRANSACTION_AND_RECOVERY_SOURCE_IMPLEMENTATION_WITH_SYNTHETIC_TESTS
SOURCE_CORE_RESULT=PASS_PENDING_LAST_CI
PRODUCTION_EXECUTOR_RESULT=NOT_COMPLETE
LIVE_PREEXECUTION_DECISION=NO_GO
NEXT_ONE_GATE=N3W_P4_T1_B1I1_CORE_INDEPENDENT_REVIEW_AND_LIVE_ADAPTER_SOURCE_CONTRACT
NEXT_GATE_MODE=SOURCE_REVIEW_AND_CONTRACT_ONLY
LIVE_EXECUTION_AUTHORIZATION=false
T1_SSH_ACCESS_THIS_GATE=false
R1_R2_R3_R4_PRIVATE_ARTIFACTS=KEEP
R5_ORIGINAL_OLD_RW_AND_COLD_BACKUP=KEEP
BROKER_DYNSEC_HA_TLS_R5=NO_MUTATION
BOARD_NVS_SETUP_SECRET=NO_MUTATION
PR_MERGE=false
```

**Never run this source package as if it were a T1 deployment package.** It cannot be used to replace Manager; it is deliberately not wired to real Docker.
