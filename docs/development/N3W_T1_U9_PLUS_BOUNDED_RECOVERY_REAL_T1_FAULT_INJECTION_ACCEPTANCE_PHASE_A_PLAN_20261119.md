# N3-W T1 U9+ bounded recovery real-T1 fault-injection acceptance — Phase A plan

DATE=2026-11-19
GATE=N3W_T1_U9_PLUS_BOUNDED_RECOVERY_REAL_T1_FAULT_INJECTION_ACCEPTANCE
PHASE=PHASE_A_CURRENT_U9_DESTRUCTIVE_RECOVERY
STATUS=SOURCE_PACKAGE_PREPARED
PR=807
SOURCE_REVIEW_HEAD=48292d4c8c3da82574f63761a4ed9a62fc8ce338

## 1. Why Phase A is separated from timing acceptance

The live T1 is already at durable U9 and Home Assistant application services
have remained quiesced across operator pauses.  That transaction can prove the
destructive U10 restart/media recovery mechanism, but it cannot honestly prove
a customer outage budget measured from the original U7 service-stop instant.

Therefore this gate is split:

- Phase A: use the existing consumed U9 transaction exactly once to prove real
  U10 -> power/re-entry -> missing bound media -> same-media reinsertion ->
  automatic U13B rollback and business recovery.
- Phase B: only after Phase A restores a healthy predecessor, decide whether to
  start a fresh continuous transaction for end-to-end customer downtime timing.

Phase A must never claim the <=15 minute customer downtime target.

## 2. Frozen live authority

Current transaction:

- phase: U9_LIVE_AUTHORIZATION_CLAIMED;
- transaction SHA-256:
  2b3812af093c1f73a95744413e238f1ca3763407241f889c0646b9495e35a84b;
- authorization claimed=true;
- authorization consumed=true;
- replay=false;
- U10 read-only Attempt 05 physically PASS;
- recovery-content manifest:
  d534be84e38817b10eab8a2f8a47c6dae3fd0946da9eba1e1d7f12090e23e9d3.

The gate does not call claim_live_authorization and does not create another
product U9 authorization.

## 3. Candidate source installation strategy

The candidate U9+ recovery source must be physically exercised, but the
production /opt/HomeAssistant source tree is not overwritten.

The acceptance package:

1. builds an exact source bundle from the P3 product-source authority;
2. stages it under the acceptance state root;
3. creates one temporary systemd drop-in that changes only the next
   n3w-t1-ha-ota.service ExecStart;
4. executes systemctl daemon-reload;
5. proves the currently running old daemon PID did not restart before U10.

The drop-in becomes active only after the deliberate power cycle.

## 4. Phase A sequence

### A0 read-only preflight

Re-run the physically proven P3 U10 read-only preflight and require:

- exact U9 transaction;
- same bound recovery USB and metadata;
- exact target/predecessor/HA backup assets;
- recovery capacity PASS;
- Broker continuity;
- application services already quiesced;
- exact predecessor HA exited container as sole predecessor image user;
- target internal image absent;
- OTA daemon original ExecStart and no existing drop-in;
- ss -Htin command supported.

### A1 arm destructive U10

After the one-shot acceptance package authorization:

- persist the acceptance claim;
- stage exact candidate sources;
- install the temporary daemon override without restarting the daemon;
- remove only the exact stopped predecessor HA container;
- remove only the exact predecessor HA image;
- do not touch Manager/Broker images;
- do not load target;
- create the legal U10 successor transaction;
- sync U10 transaction metadata to the bound USB before host transaction write;
- verify authorization tuple unchanged;
- stop at U10.

Expected terminal result:

U9PLUS_PHASE_A_U10_ARMED

### A2 fault injection: power loss + missing recovery media

Operator action, only after A1 reports safe_to_power_off=true:

1. power the T1 off;
2. remove the bound recovery USB while power is off;
3. power the T1 on.

On boot the temporary candidate daemon must own U10 re-entry.  With the bound
USB absent it must not invent, format or substitute media.  Acceptance requires:

- transaction still U10;
- predecessor internal image still absent;
- target image absent;
- product U9 authorization tuple unchanged;
- IPC phase RECOVERY_MEDIA_REQUIRED;
- no error code;
- bound filesystem UUID absent from block inventory.

Expected result:

U9PLUS_PHASE_A_MEDIA_REQUIRED_PASS

### A3 same-media reinsertion + second power cycle

Operator action after A2 PASS:

1. power the T1 off;
2. reinsert the exact same recovery USB;
3. power the T1 on.

The candidate daemon must automatically resume the existing transaction with
no product-authorization replay and drive the existing U13B implementation.

Terminal PASS requires:

- IPC phase ROLLED_BACK;
- durable transaction U13B_ROLLED_BACK / ROLLED_BACK;
- rollback_origin_phase=U10;
- failure_code=u9_plus_restart_bounded_recovery;
- exact recovery content verified;
- predecessor image restored;
- pre-upgrade HA data restored;
- predecessor runtime health verified;
- Manager, Home Assistant and Broker each running exactly once;
- Broker and application owners active;
- target image absent;
- unchanged consumed U9 authorization;
- corrected KF-140-safe completion oracle has passed, including fresh
  simplified-N3-W telemetry and HA MQTT transport evidence;
- Host/USB terminal authority exact.

The package records automatic recovery duration from the second boot.  The
longer U10-to-recovered laboratory duration explicitly includes operator hold
time and is not customer SLA evidence.

## 5. Hard stop boundaries

Phase A forbids:

- product U9 claim/reclaim/replay;
- target docker load;
- U11/U12/U13A;
- production source-tree overwrite;
- merge;
- treating the current cross-pause transaction as <=15 minute SLA evidence.

NEXT_AFTER_PHASE_A_PASS=
PHASE_B_FRESH_CONTINUOUS_DOWNTIME_ACCEPTANCE_OR_STOP
