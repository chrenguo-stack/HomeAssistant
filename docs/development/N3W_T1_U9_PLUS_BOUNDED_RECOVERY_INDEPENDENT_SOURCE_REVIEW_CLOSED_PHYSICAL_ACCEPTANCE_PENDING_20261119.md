# N3-W T1 U9+ bounded recovery independent source review closure

DATE=2026-11-19
TASK=N3W_T1_U9_PLUS_BOUNDED_RECOVERY_SOURCE_REVIEW_AND_ACCEPTANCE_DESIGN
STATUS=SOURCE_REVIEW_CLOSED_PHYSICAL_ACCEPTANCE_PENDING
PR=807
MAIN_AT_REBIND=3e7faf258d670c9eaf3be6ede9bbb02df2ac009d
HANDOFF_PARENT_HEAD=62d1ed4d268288eeb1ec38ff355595e688738996
INITIAL_REBOUND_PR_HEAD=f8ebe46b465e04df1e68f4eff0bc11ae33e20d74
INDEPENDENT_ORACLE_REPAIR_HEAD=b05b923997238c4cac5505f5e27b5a405f0b7d75
AUTHORITY_INDEX_REPAIR_HEAD=a8b132e0cae5489a0ece7828a65b722b661dc58d
P3_SOURCE_AUTHORITY_REBIND_HEAD=9f301091dad9faeee77e997c435e2b81115a1206

## 1. Authorization and stop boundary

This gate remained source/cloud only.

Allowed:
- repository and handoff review;
- source design and implementation;
- deterministic unit/simulation/fault-injection coverage;
- GitHub CI;
- documentation and evidence archive.

Not executed or authorized in this gate:
- real T1 destructive U10;
- live service stop/start/write;
- target image load;
- U11+;
- authorization replay;
- merge of PR #807.

The live T1 transaction remains:
- phase `U9_LIVE_AUTHORIZATION_CLAIMED`;
- transaction SHA-256 `2b3812af093c1f73a95744413e238f1ca3763407241f889c0646b9495e35a84b`;
- authorization claimed and consumed;
- replay forbidden.

## 2. Fresh rebind

At task restoration:
- main: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`;
- PR #807: OPEN / DRAFT / UNMERGED;
- PR head: `f8ebe46b465e04df1e68f4eff0bc11ae33e20d74`;
- the PR head was six commits ahead of handoff parent `62d1ed4d268288eeb1ec38ff355595e688738996`.

The two workflows that were still running at handoff resolved as:
- run `44346576862`: SUCCESS;
- run `44346577295`: CANCELLED after a newer head arrived, not a source failure.

## 3. Independent source review

The candidate implementation was not accepted by comment/history alone. The source was independently traced through:
- U9-U13 durable state definitions;
- U13B automatic reconciliation and rollback;
- product daemon startup;
- IPC background recovery ownership;
- production host adapter;
- U10 predecessor-capacity release behavior;
- U11 runtime-owner identity checks.

Confirmed architecture:
1. U9+ recovery reuses the existing U13B rollback implementation rather than creating a parallel recovery stack.
2. Daemon startup is phase-gated to U9-U12/U13B progress/terminal states and does not burden ordinary U0-U8 operation.
3. U9 authorization is required to be already consumed; the restart recovery path has no live-authorization claim/replay call.
4. Restart/re-entry in U9-U12 is intentionally conservative and selects rollback.
5. The same bound recovery media is required; wrong/missing media is a recoverable wait state, never a substitution/format path.
6. U10 real destructive behavior removes only the predecessor Home Assistant container/image while Manager identity remains available as stopped residue and Broker remains running, so the production peer-binding model is compatible with the real U10/U11 contracts.

## 4. Independent blocker found: KF-140 regression

The first candidate production completion oracle contained a real acceptance defect:
- it searched legacy `Accepted telemetry node=...`;
- it treated Home Assistant Recorder `last_updated` after recovery start as the decisive fresh-delivery proof.

This contradicted the already-closed KF-140 guard:
- deployed simplified N3-W logs use `Accepted simplified N3-W telemetry source=<direct|relay> node=...`;
- a zero match against stale text must not be promoted to product failure;
- when a sensor value can remain constant, `last_updated` must not be the sole fresh-receipt oracle;
- fresh HA receipt must be bound to a node event with transport/runtime evidence.

If left unchanged, the rollback could succeed but the product could falsely report recovery failure.

## 5. Repair

Commit `b05b923997238c4cac5505f5e27b5a405f0b7d75` repaired only the completion evidence and deterministic coverage; it did not widen the recovery state machine.

New completion evidence:
- exact simplified-N3-W Direct/Relay Manager acceptance;
- stable accepted-node mapping through HA entity registry;
- unique HA loopback MQTT client connection to local port 1883;
- both `bytes_received` and `data_segs_in` must advance in the same short polling interval as a newly observed Manager acceptance;
- transport baseline resets every poll, so unrelated MQTT traffic cannot be carried forward and paired with a later node event;
- Recorder remains the read-only pre-upgrade-history integrity check and does not have to advance `last_updated` merely because a sensor value stayed constant;
- missing/ambiguous socket evidence fails closed.

The fixed-T1 socket-counter evidence is supported by prior KF-140 physical capture, including 222 valid HA 1883 socket samples and per-event transport deltas. It is deliberately not generalized to every Linux host and must be revalidated in the next real-T1 acceptance.

## 6. Expanded deterministic coverage

Added/expanded regression coverage proves:
- U9, U10, U11, U12 daemon/process re-entry selects bounded recovery;
- U13B0, U13B1, U13B2, U13B3, U13B4 resumes through the same coordinator;
- all recognized missing/wrong-bound-media codes project `RECOVERY_MEDIA_REQUIRED`;
- no USB substitution occurs;
- production daemon constructs the coordinator for every supported post-claim phase;
- deployed simplified-N3-W log + HA MQTT transport can pass even when Recorder timestamp is intentionally older than recovery start;
- legacy KF-140 Manager text cannot pass;
- multiple/ambiguous HA MQTT connections fail closed;
- restored Recorder history remains independently readable.

## 7. CI repair and source-integrity rebind

The first new source head exposed an unrelated Core Stack authority-document regression:
- `index_historical_source_missing`;
- then `index_live_deployment_marker_missing`.

These were local documentation-contract defects and were repaired without runtime changes.

Changing the production U13B host adapter also invalidated one P3 exact source binding. Commit `9f301091dad9faeee77e997c435e2b81115a1206` changed only:
- `tools/execution_packages/n3w/r7a/u13b_p3_live_to_u11/manifest.json -> product_source_authority["tools/n3w_t1_core_updater_ha_u13b_host.py"]`.

The bound Git blob changed from:
- `6a1f21f8991d3b5b70e0d86a8872e225c8f23c6e`
to:
- `13e92a83a7ce10841cd87249c5ba9c63e226617b`.

No live-execution grant, mutation authorization, authorization ID, execution ID, claim/consume state or replay field was changed. No execution package was run.

## 8. CI evidence

Final allowed active polling on `9f301091dad9faeee77e997c435e2b81115a1206`:

`18 SUCCESS / 0 FAILURE / 4 RUNNING`

Key SUCCESS:
- P3 live/read-only source: run `44430251423`;
- P3 acceptance clean OTA source: run `44430251448`;
- fast source/exact closure: run `44430251511`;
- Core Stack current authority: run `44430251696`;
- public repository safety: run `44430251618`;
- greenhouse-manager: run `44430251523`.

Still running at the third/final allowed check:
- Manager A-to-B: `44430251468`;
- HA 2026.10.3 target binding: `44430251532`;
- HA 2026.10.4 target binding: `44430251449`;
- HA 2026.10.4 same-version acceptance artifact: `44430251783`.

Polling stopped by rule. No workflow was re-dispatched to bypass the polling limit.

Run links:
- https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44430251468
- https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44430251532
- https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44430251449
- https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44430251783

## 9. Closure judgment

SOURCE_REVIEW=CLOSED_PASS
SOURCE_IMPLEMENTATION=PRESENT_AND_REVIEWED
KF140_ORACLE_REGRESSION=REPAIRED
BOUNDED_RECOVERY_PHASE_COVERAGE=PASS_BY_DETERMINISTIC_TESTS_AND_KEY_CI
P3_SOURCE_INTEGRITY=PASS_KEY_CI
REAL_T1_DESTRUCTIVE_U10=NOT_EXECUTED
REAL_T1_FAULT_INJECTION=NOT_EXECUTED
POST_CUTOVER_RECOVERY_TIME=NOT_PHYSICALLY_MEASURED
KF168=CANNOT_CLOSE_PHYSICALLY_YET
PR807=OPEN_DRAFT_UNMERGED

KF-168 therefore remains open only for physical acceptance. Source review is closed; customer recovery timing and representative power/process/media fault injection are not yet proven on the real T1.

## 10. Next boundary

NEXT_ONE_GATE=`N3W_T1_U9_PLUS_BOUNDED_RECOVERY_REAL_T1_FAULT_INJECTION_ACCEPTANCE`

That next gate must be separately authorized because it crosses the current stop boundary. It must, at minimum:
- fresh-rebind the exact source/CI authority;
- revalidate the fixed-T1 `ss` transport-counter contract;
- define the exact destructive U10 starting state and rollback media;
- inject representative restart/power/media faults without replaying U9 authorization;
- prove predecessor image + protected HA data restoration;
- prove Manager/Broker/HA return to service;
- prove fresh greenhouse data reaches HA using the corrected KF-140-safe oracle;
- measure customer downtime from the actual service-stop instant;
- keep the <=15-minute post-cutover recovery objective as an engineering acceptance target until physically demonstrated.

No U11+, merge, or other production boundary is authorized by this archive.

