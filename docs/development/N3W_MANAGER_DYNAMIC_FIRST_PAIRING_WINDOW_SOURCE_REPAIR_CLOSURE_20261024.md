# N3W Manager Dynamic First-Pairing Window Source Repair Closure

Date: 2026-10-24

## 1. Gate

`N3W_MANAGER_DYNAMIC_FIRST_PAIRING_WINDOW_SOURCE_REPAIR_20261024_01`

PR: #664  
PR state at source closure: OPEN / DRAFT / mergeable  
Base at source closure: `dc596ad50eb2ea80ba55aa3af2413236321f1465`

Pre-freeze executable source base:

`85706d7507b8ce90b3447c18ab62d9c0a37afcce`

Exact source/test closure head:

`aeae6eee6577e61a8b84c0b63b6a57e4863657bf`

## 2. Source-repair result

SOURCE_REPAIR_RESULT=CLOSED_PASS

The old normal-path Manager-only Compose recreate design has been removed from first-pair onboarding.

The repaired design keeps the normal Broker, Manager and Home Assistant production lifecycle intact and opens first-pairing only through a Manager-owned in-process dynamic pairing window.

The source closure proves:

- durable production pairing remains disabled;
- normal onboarding does not use Manager Compose override, `--force-recreate` or `--no-deps`;
- the temporary Broker locator is runtime-only and public/persisted evidence exposes only its SHA-256;
- `pairing-control.sock` is separate from the Setup Secret authority `pairing.sock`;
- the Manager-owned deadline is the primary exposure-closure authority;
- the host watchdog is a secondary reconciliation guard and does not become a Manager restart/recreate authority;
- open/close validation checks real UDP, TCP and Unix-socket exposure;
- partial pairing-worker startup failure cleans already-constructed resources;
- real pairing resources disappear after the Manager-owned timeout;
- pairing-window close does not stop the normal Manager/MQTT parent runtime;
- Broker/Manager/Home Assistant continuity is checked through container identity and restart count in the onboarding flow;
- legacy consumed authorization remains non-replayable;
- timeout/control failures cannot be converted into a false PASS when exposure closure is unproven.

## 3. Independent review

Independent exact-head source review found no new design-level blocker.

The final two acceptance-evidence gaps found during review were test-only gaps:

1. resource cleanup after partial pairing-worker startup failure;
2. direct proof that pairing close does not stop the normal Manager/MQTT runtime.

They were closed without changing the product architecture.

## 4. CI

Exact source/test head:

`aeae6eee6577e61a8b84c0b63b6a57e4863657bf`

GitHub workflow result:

- total workflow runs: 17
- success: 17
- failure: 0
- running: 0

Therefore:

`SOURCE_CI=PASS`

## 5. KF-129 status

KF-129 remains OPEN.

The source/CI portion is closed, but KF-129 still requires later exact-image and real T1/live acceptance before the regression item can be closed.

This source closure does not prove:

- production image deployment;
- live T1 recovery;
- no-Board live manual open/close;
- no-Board live Manager self-timeout;
- Board D one-shot pairing;
- end-to-end zero-interruption live acceptance.

## 6. Preserved live state

The failed old-design authorization remains consumed and must never be replayed.

Board D remains unpaired.

The failed live transaction/evidence must be preserved.

No T1 access, T1 mutation, Board access, firmware/OTA/NVS action, production deployment or merge was performed by this source-repair closure.

## 7. Boundary

`SOURCE_REPAIR_GATE=CLOSED_PASS`

`KF_129=OPEN`

`T1_ACCESS=false`

`BOARD_ACCESS=false`

`PRODUCTION_DEPLOYMENT=false`

`MERGE=false`

STOP before exact production artifact deployment, T1 recovery, Board D pairing or merge.
