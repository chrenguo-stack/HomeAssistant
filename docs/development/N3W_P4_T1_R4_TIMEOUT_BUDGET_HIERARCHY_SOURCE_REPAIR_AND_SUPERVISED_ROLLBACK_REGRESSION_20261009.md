# N3-W P4 T1 — R4 timeout-budget hierarchy and supervised rollback source-only repair (2026-10-09)

## Authorization and scope

The user explicitly approved `N3W_P4_T1_R4_TIMEOUT_BUDGET_HIERARCHY_SOURCE_REPAIR_AND_SUPERVISED_ROLLBACK_REGRESSION` following independent review: A1 had closed, A6 remained an operational prelive blocker. Authorization is **SOURCE-ONLY**: versioned source changes, deterministic synthetic tests, exact source binding, GitHub progress alignment. It does **not** permit T1 access, production Manager replacement, broker/network/TLS mutation, R2/R3 cleanup, board boot, Setup Secret import or PR merge.

Prior authority: `docs/development/N3W_P4_T1_R4_A1_REPAIR_EXACT_SOURCE_INDEPENDENT_CLOSURE_AND_PRELIVE_DECISION_20261009.md`. The earlier source used `systemd TimeoutStartSec=300` and `TimeoutStopSec=120`, operator wait `430`, remote execute `530`, remote preflight `120`, and Mac SSH `600`. Consequently the maximum independent preflight + execution budgets were `650`, **greater than the outer 600-second SSH timeout**, which could leave the attempt's state unknown. In addition the operator waited only 10 seconds longer than the systemd start timeout plus stop/rollback allowance.

## Repaired budget hierarchy

```text
SYSTEMD_EXECSTART_MAX_SECONDS=420
SYSTEMD_EXECSTOPPOST_TIMEOUT_SECONDS=120
OPERATOR_SYSTEMD_WAIT_MAX_SECONDS=580
REMOTE_OPERATOR_PREFLIGHT_MAX_SECONDS=120
REMOTE_OPERATOR_EXECUTE_MAX_SECONDS=660
MAC_OUTER_SSH_MAX_SECONDS=920
MAX_EXECUTION_ELAPSED_BEFORE_OLD_MANAGER_STOP_SECONDS=160
MIN_BUDGET_RESERVED_AFTER_PRESTOP_GUARD_SECONDS=260
```

Source files:
- `fresh_manager_systemd_unit.py`: explicit start and stop-post budget constants and rendered `TimeoutStartSec=420`, `TimeoutStopSec=120`. `Restart=no` and `ExecStopPost` identity-bound restoration remain unchanged.
- `fresh_manager_operator.py`: `WAIT_LIMIT_SECONDS=580`, greater than the 420+120=540 supervised potential start/stop-post budget by 40 seconds. Still checks unit load, started monotonic timestamp, active state/result and post-commit validation.
- `fresh_manager_mac_launcher.py`: remote preflight `120`, execute `660`, SSH timeout `920`; 660 exceeds operator 580 by 80 seconds and 920 exceeds 120+660 by 140 seconds. Nonreplayable remote R4 stage and 11 SHA-pinned protected scripts remain unchanged in design.
- `fresh_manager_deploy.py`: `SYSTEMD_START_TIMEOUT_SECONDS=420`, `MAX_PRE_STOP_SECONDS=160`. The transaction starts its monotonic clock before preflight. **After** successful stopped-shadow contract verification, **before** calling `ops.stop_old()`, if elapsed time exceeds 160 seconds, the transaction fails `CUTOVER_TIME_BUDGET_TOO_LOW_BEFORE_OLD_STOP`. This ensures at least 260 seconds of the nominal 420-second service-start window remains at the critical stop boundary; systemd remains the outer hard stop, and recovery is still best effort. This is a pre-stop safety guard, not a guarantee that the remaining cutover always completes or all arbitrary Docker host outages recover.
- The Mac launcher is independently downloadable and executable only following a distinct live approval; **no production execution command is released by this gate**.

The chosen upper bounds are per-component guards; subprocess runtime, host scheduling and systemd timing semantics can add margins. They are not proof of real T1 full execution time, and recovery remains subject to Docker and host availability. Timeout-based STOP **must not claim PASS** without committed candidate validation or real original Manager restoration evidence.

## Synthetic regression and failure injection

- Systemd/Deploy start constants agree; stop-post budget is explicitly reserved; operator waits at least start+stop-post+30s; remote execute at least operator+60s; outer SSH at least preflight+execute+120s; pre-stop guard reserves at least 240s.
- If injected elapsed time before old-manager stop is **161 seconds**, the transaction records shadow-verified phase without calling `stop_old`, has no candidate ID, and cannot commit; if elapsed is exactly 160 seconds, the guarded call is allowed.
- Supervisor timeout *before old Manager stop* causes no Docker rename/stop, validates original running identity and records rollback PASS.
- Timeout *after old Manager stop but before park* restarts exact original ID and leaves Broker unchanged.
- Timeout *after old Manager park* renames original exact ID back and restarts it.
- Timeout *with an active candidate and simulated Docker stop failure* fails without a false rollback PASS.
- Previous tests preserve image/ID security checks, committed-but-crashed supervisor rollback behavior and no-replay semantics. No T1 hardware or actual systemd kill was exercised.

```text
TASK=N3W_P4_T1_R4_TIMEOUT_BUDGET_HIERARCHY_SOURCE_REPAIR_AND_SUPERVISED_ROLLBACK_REGRESSION
SOURCE_REPAIR_SYSTEMD_COMMIT=1c42a3a4cf83778ab020f8b25694050aa017523d
SOURCE_REPAIR_OPERATOR_COMMIT=b75b2ee91efd441c5a2267576ea77e181daa153f
SOURCE_REPAIR_DEPLOY_COMMIT=5b9bed527cbe9b381d836fbc155f348a57469bdb
SOURCE_REPAIR_LAUNCHER_COMMIT=7702c9f39bc0f9113e348daef3322388d012ad08
SYNTHETIC_TESTS=141_PASS
TEST_CI_RUN=37951125296
MANAGER_CI_RUN=37951125303
PUBLIC_SAFETY_CI_RUN=37951125401
ALL_THREE_CI=PASS
EXACT_PROTECTED_11_SOURCE_REF=1528ae970974fd711f8a8a6441c29817a118d825
REBOUND_LAUNCHER_COMMIT=c5d8b0137a509d1b4a80bd03208d1232b01ae84b
REBOUND_LAUNCHER_BLOB=d66b7735e80550e2f6df6281978330edd3566d78
MANIFEST_11_BLOBS_MATCH=true
EXACT_LAUNCHER_TEST_COMMIT=ee78abe7cc0b799f178049b6cf1b8ac08115721c
SOURCE_ONLY_GATE_RESULT=PASS
T1_LIVE_EXECUTION=false
T1_MUTATION=false
R4_LIVE_AUTHORIZATION=false
R2_R3_EVIDENCE_PRESERVED=true
```

## Next stop and independent review

```text
CURRENT_ONE_GATE=CLOSED_PASS_SOURCE_ONLY
NEXT_ONE_GATE=N3W_P4_T1_R4_A6_TIMEOUT_REPAIR_EXACT_SOURCE_INDEPENDENT_REVIEW_AND_PRELIVE_DECISION
R4_PRODUCTION_REPLACEMENT_NOT_AUTHORIZED=true
PR_540=OPEN_DRAFT
NO_R2_R3_R5_CLEANUP=true
NO_BROKER_OR_BOARD_OR_SETUP_SECRET_MUTATION=true
NO_AUTO_RETRY=true
```

Next reviewer should independently verify that the 420/120/580/660/920 hierarchy is internally meaningful, the 160-second pre-stop guard never stops old Manager on budget failure, the actual `systemd ExecStopPost` semantics/timeout are correctly modeled, and source rebinds include every changed production file. This source-only CI cannot prove a real systemd timeout after candidate takeover restores old Manager or that the nominal 260s reserve always suffices. A separate explicit user authorization is required before a live R4 attempt, even if the independent prelive review returns GO.
