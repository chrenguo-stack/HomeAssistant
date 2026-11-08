# 温室环境监测系统（ESP32-C6）
# N3-W T1 R7A repaired Manager A0R / A1R live execution closure — 2026-11-08

## 1. Closure

```text
GATE=N3W_T1_R7A_REPAIRED_MANAGER_A0R_A1R_LIVE_EXECUTION_CLOSURE_20261108_01
RESULT=CLOSED_PASS
PR=800
LIVE_AUTHORIZED_HEAD=70aaa4070641dd73c1a97738e6332be31403d45e

A0R_EXECUTION_ID=N3W_R7A_REPAIRED_MANAGER_A0R_ATTEMPT2_20261108T151437Z
A0R_STATUS=PASS
A0R_TRANSACTION_STATUS=COMMITTED
A0R_MANAGER_AFTER=local/greenhouse-manager:fresh-7807271e4c48
A0R_RECOVERY_REQUIRED=false
A0R_SECOND_APPLY=false

A1R_EXECUTION_ID=N3W_R7A_REPAIRED_MANAGER_A1R_20261108T153901Z
A1R_STATUS=PASS
A1R_AUTHORIZATION_CLAIMED=true
A1R_ACTIVATION_INVOKED=true
A1R_SECOND_ACTIVATION=false
A1R_SERVICES_OWNER_RESTART=true
A1R_HOST_DAEMON_ACTIVE=true
A1R_MANAGER_OTA_ENABLED=true
A1R_AUTOMATIC_ROLLBACK=false
A1R_RECOVERY_REQUIRED=false
A1R_SSH_MASTER_CLEANUP=true

PREPARE=false
USB_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

## 2. A0R live result

The repaired Manager A0R executor ran from exact source head
`8dc7b67d72c012e5223640b7eb3bdf0149efa8df` after the SSH transport
readonly closure and focused CI were green.

The successful attempt moved the live Manager from the accepted predecessor to:

`local/greenhouse-manager:fresh-7807271e4c48`

The Generic V2 Manager transaction closed `COMMITTED`, the exact A0R authorization
was consumed by the transaction, the peer Home Assistant/Broker runtimes remained
unchanged, recovery remained clear, and no USB/board/host-daemon activation occurred
in A0R.

The earlier A0R attempt that stopped during SSH master startup never reached T1 access,
staging, plan or apply and therefore did not consume the updater authorization.

## 3. SSH transport repair closure

The original 180-second SSH startup timeout was not reproducible as a persistent
network, password, host-key, `ssh -MNf`, ControlMaster or Python transport defect.

Readonly probes proved:

- strict host-key binding PASS;
- root password authentication PASS;
- shell `ssh -MNf` ControlMaster create/check/reuse/exit PASS;
- repaired Python `SSHTransport.start_epoch()`, child reuse and close PASS.

Source repair added fail-closed transport error translation and executor error capture,
then rebound the R7A source authorities to the repaired SSH transport blob.

## 4. Fresh A1R entry proof

After A0R, the exact A1R readonly preflight passed with:

```text
manager_image=local/greenhouse-manager:fresh-7807271e4c48
manager_runtime_image_id=sha256:7e3f09ed47010a18de215faa426113b7faba4e220b41bb9dcafd8ee1d4acf20b
manager_transaction_sha256=39c076050122402f93b4956523129e4555df210d8e45caea1ababd88f1ee3d0b
homeassistant_image=local/n3w-homeassistant:2026.10.0-0c73235a
homeassistant_runtime_image_id=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306
broker_image=local/n3w-mosquitto:2.1.2-3184566d
broker_runtime_image_id=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
recovery_required=false
usb_like_disk_count=0
a1_residue_absent=true
```

The preflight also revalidated that the Manager V2 transaction was the exact repaired
A0R transaction and that its authorization hash matched the distinct A0R authority.

## 5. A1R live result

The A1R live executor ran from exact live-authorized head
`70aaa4070641dd73c1a97738e6332be31403d45e`.

It installed/activated the approved OTA host wiring, performed the bounded single
services-owner restart, and completed the frozen post-activation validation including
the 15-second same-container stability guard.

Final closure:

```text
status=PASS
authorization_claimed=true
activation_invoked=true
second_activation_invoked=false
services_owner_restart_invoked=true
host_daemon_active=true
manager_ota_enabled=true
automatic_a1_rollback_invoked=false
recovery_required=false
usb_mutation=false
prepare_intent_invoked=false
confirm_usb_erase_invoked=false
board_access=false
ssh_master_cleanup=true
```

The A1R one-shot live execution has been used and must not be replayed.

## 6. KF-144

The source defect that previously caused the Manager validation failure has now been
revalidated on the real production T1 with the repaired Manager and the restored OTA
wiring.

```text
KF144_STATUS=CLOSED_PASS_LIVE_REVALIDATED
```

## 7. Repository authority distinction

The live runtime now uses repaired Manager `fresh-7807271e4c48`. The repository
compatibility/current-authority manifest is not promoted by this live closure.
Production authority-file promotion and PR merge remain separate source/release
decisions.

## 8. Hard stop / next gate

The existing Boundary B PREPARE-only source/preexecution closure remains the governing
physical contract. The next real gate is:

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R7A_BOUNDARY_B_REAL_USB_PREPARE_ONLY_EXECUTION_20261108_01
NEXT_GATE_EXPLICIT_USER_AUTHORIZATION_REQUIRED=true
AUTO_EXECUTE_NEXT_GATE=false

PREPARE_EXECUTION_AUTHORIZED=false
REAL_USB_INSERTION_AUTHORIZED=false
CONFIRM_USB_ERASE_AUTHORIZED=false
U2_PLUS_AUTHORIZED=false
BOARD_ACCESS_AUTHORIZED=false
MERGE_AUTHORIZED=false
```

That gate must fresh-check the live A1R health, confirm no active HA-USB/PREPARE
transaction and confirm the dedicated test USB is absent before PREPARE. It must stop at
`USB_REQUIRED_CONFIRMATION`; destructive USB confirmation remains a later, separate
authorization.
