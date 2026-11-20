# N3-W T1 KF-168 IPC migration executor readiness source repair closure

```text
STATUS=CLOSED_PASS
GATE=N3W_T1_KF168_IPC_MIGRATION_EXECUTOR_READINESS_SOURCE_REPAIR
SCOPE=SOURCE_OFFLINE_TEST_CI_ARCHIVE_ONLY
PRODUCTION_AUTHORITY=false
LIVE_EXECUTION_AUTHORIZED=false
T1_ACCESS=false
T1_MUTATION=false
AUTHORIZATION_REPLAY=false
PHASE_A_OVERALL=NOT_YET_PASS
PHASE_B=NOT_ENTERED
```

## 1. Exact source binding

- Base IPC-isolation candidate: PR #810 head `4abebaa61c1db0be41a724c45263e26ac15eb06e`, tree `b34b33ebd7bd477c7f10692c001b8da45768a645`.
- Source repair: draft PR [#811](https://github.com/chrenguo-stack/HomeAssistant/pull/811), commit `6611c3bcac644e34d81077428fd454f3c8b9d557`, tree `795eb8f1f7e3dcbfa8b34cc236fd5139a30f10e7`.
- Successor executor blob: `c0a05384dff5b44537a48e9a0dab048e2df7e1ee`.
- Review manifest blob: `2076b667b7d171f84c26e6ac1b8cf62d8089cf49`.
- Focused test blob: `f1399027ed65ec9324481a91b84c3c4b0db9fff8`.
- Applicable workflow blob: `5bd948932f6a3dd150d1a54c8e30a47c8e5cd043`.
- Spent historical wrapper SHA-256: `519539f6f67d8a5f37bd9cd28cd90cb7ac61ece35ba7135c4a494c697a220785`; it remains consumed and non-replayable.

The successor was reconstructed from the archived spent executor and changes only
the executor-readiness boundary plus review-only packaging. The #810 daemon,
unit and Compose IPC-isolation implementation remains its exact base.

## 2. Defect closed

The previous wrapper treated successful return from the Type=simple application
owner as Docker readiness. Real-T1 rollback timing proved systemd reported
Started at 11:17:55.315169Z while HA/Manager Docker starts followed at
11:17:56.576259Z / 11:17:56.578443Z. The immediate running-only query therefore
produced a false `container_not_unique`.

The successor introduces one shared `wait_application_runtime()` barrier for
both install and rollback:

1. use a monotonic deadline (45 s) and bounded polling;
2. allow a temporary zero-running Manager only while the exact pre-created
   Manager is still the sole resident Manager;
3. continuously preserve exact Manager image and bind;
4. reject duplicate/replaced Manager immediately;
5. reject HA duplication or image drift;
6. require application owner non-failed and OTA owner active;
7. execute the existing Host/Broker/USB invariants on every wait iteration;
8. return only after the exact Manager and one exact-image HA are running;
9. never start/restart/retry a service from the barrier;
10. fail closed on deadline.

This closes the false-stop race without turning startup into a fixed delay and
without weakening the existing exact identity contract.

## 3. Review-only safety boundary

The new package contains:

```text
REVIEW_ONLY_LIVE_EXECUTION_AUTHORIZED=false
```

Execute mode checks this before the previous one-shot authorization claim and
before any mutation. The manifest independently states:

```text
STATUS=REVIEW_ONLY
PRODUCTION_AUTHORITY=false
LIVE_EXECUTION_AUTHORIZED=false
GRANTED=false
CLAIMED=false
CONSUMED=false
REPLAY_PERMITTED=false
```

No old authorization, receipt directory or live wrapper is made reusable.

## 4. Validation

Offline isolated readiness harness before publication:

```text
OFFLINE_HARNESS=PASS
FOCUSED_CASES=13
LIVE_T1_USED=false
```

The harness covered delayed stopped→running convergence, duplicate/replaced
Manager, image/bind drift, owner/OTA failure, Host/Broker invariant drift,
monotonic timeout, shared install/rollback wiring, absence of service
restart/retry, and review-only execution denial.

Exact committed validation on `6611c3bcac644e34d81077428fd454f3c8b9d557`:

- [N3W U13B P3 live and readonly source CI — run 44742034850](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44742034850): **SUCCESS**, attempt 1.
- Exact successor focused test file: **12 PASS**.
- Existing workflow suites remained green; the disposable Linux ext4 isolation regression: **PASS**.
- [Public repository safety CI — run 44742034856](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44742034856): **SUCCESS**, attempt 1.
- No rerun was dispatched.

The difference between 13 offline harness cases and 12 committed pytest cases
is test packaging/parametrization, not a dropped contract item; the committed
suite covers every readiness condition listed above and is the exact-source
authority.

## 5. Live state and Phase-A boundary

No T1 access or mutation occurred in this gate. No deployment, systemd action,
mount/unmount, Docker recreation, USB/Host transaction, U11+, Phase-B, merge
or release occurred.

The last live authority therefore remains the prior settled rollback observation
at 2026-11-20T11:22:13Z:

```text
LIVE_HOST_PHASE=U13B_ROLLED_BACK
LIVE_HOST_STATUS=ROLLED_BACK
LIVE_BUSINESS_RUNTIME_HEALTH=PASS
PR_810_LIVE_IPC_ISOLATION=ROLLED_BACK_NOT_DEPLOYED
PHASE_A_DURABLE_AUTOMATIC_ROLLBACK=PASS
PHASE_A_BUSINESS_RECOVERY=PASS
PHASE_A_OVERALL=NOT_YET_PASS
```

Source repair success is not Phase-A product acceptance.

## 6. Future telemetry availability contract

Before any new live migration can be considered, the next read-only preflight
must prove, without synthetic substitution:

- a controllable real simplified N3-W telemetry source is presently available;
- the source can produce a fresh accepted event after the observation window opens;
- the matching HA MQTT transport can be observed in the same window;
- the existing completion oracle is not weakened merely to obtain evidence.

If any item is unavailable, the future live migration remains blocked.

## 7. Next boundary

```text
NEXT_ONE_GATE=N3W_T1_KF168_IPC_MIGRATION_EXECUTOR_READONLY_DEPLOYMENT_PREFLIGHT
NEXT_GATE_SCOPE=READONLY_T1_PREFLIGHT_ONLY
NEW_LIVE_AUTHORIZATION=NOT_GRANTED
OLD_MIGRATION_EXECUTOR_REPLAY=false
PHASE_A_OVERALL=NOT_YET_PASS
```

That preflight may inspect the current T1 and bind a fresh future execution
candidate. It may not deploy the five files, stop/start services, mount/unmount
USB, recreate containers, mutate transactions, replay authorization, enter
U11+/Phase-B, merge, or release.

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
UNARCHIVED_CRITICAL_RESULT_COUNT=0
SECRET_VALUES_INCLUDED=false
```
