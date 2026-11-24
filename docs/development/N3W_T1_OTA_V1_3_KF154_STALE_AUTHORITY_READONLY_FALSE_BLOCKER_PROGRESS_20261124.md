# N3-W T1 Core Stack OTA V1.3 — KF-154 stale-authority read-only false blocker

Date: 2026-11-24

## Result observed

R8V13-07 fresh read-only rebind V1 reached:

```text
OLD_TRANSACTION_TERMINAL_NO_REPLAY=PASS
RUNTIME_IDENTITIES=PASS
CURRENT_PREDECESSOR_BINDING=PASS
MANAGER_BROKER_HA_SELF_TEST=PASS
HA_PREPARE_AUTHORITY_PRESENT=true
HA_PREPARE_AUTHORITY_TRANSACTION_ID_SHA256=afbfeeb85c3ab579b62d86d347f76b7f6ee7f203b068eac028be1d18761950c3
HA_PREPARE_AUTHORITY_EXPIRED=false
HA_PREPARE_AUTHORITY_STILL_ACTIVE
```

No persistent product mutation occurred and the executor stopped before USB/capacity completion.

## Root cause

The read-only executor treated three different authority classes as if they shared one expiry rule.

Exact product semantics at KF-153 repair head `90ce32ce4b6c329fd38c2771e352d129d6d00a86` are byte-identical to the current branch for:

- `n3w_t1_core_updater_ha_recovery_startup.py`;
- `n3w_t1_core_updater_ha_ipc.py`;
- `n3w_t1_core_updater_ha_usb_state.py`.

Product behavior:

1. a fresh PREPARE creates a new transaction and archives the terminal current transaction;
2. prepare authority binds `transaction_id_sha256`;
3. install authority binds the requested-install binding SHA;
4. authority publication only rejects a still-active authority when the binding is the same but the content differs;
5. a fresh transaction therefore safely replaces old transaction-bound authority files because its binding is different;
6. the release pin is not transaction-bound. `LocalApprovedHaRelease` requires the pin to be unexpired and to match the approved manifest/current predecessor, so an active valid release pin is useful authority for fresh PREPARE rather than a blocker.

Therefore waiting for the old prepare authority to expire or deleting it is unnecessary and would not improve safety.

## V2 read-only repair

```text
EXECUTOR=tools/execution_packages/n3w/t1_ota_r8v13_07/N3W_T1_R8V13_07_FRESH_REACCEPTANCE_READONLY_REBIND_20261124_05.sh
EXECUTOR_IMPLEMENTATION_HEAD=a27a049ca473dd69f46e857999d090104c4c1fb4
TEST_HEAD=cf2a123f6d32b4d3629b657d874ca5f07ae55d1c
CI_WIRING_HEAD=4051569c15b71f413926bd5b6d47d0fd0b1ade19
T1_MUTATION=false
OLD_TRANSACTION_REPLAY=false
```

V2 rules:

- active prepare authority is accepted only when its schema, USB UUID and transaction ID exactly match the terminal old transaction, then classified `ACTIVE_OLD_TERMINAL_SAFE_REPLACEABLE`;
- active install authority is accepted only when its binding exactly equals the product-computed old requested-install binding, then classified the same way;
- foreign or ambiguous transaction-bound authority still STOPs;
- release pin is independently checked as release-level authority;
- active release pin must resolve the exact 10.4 predecessor and 10.0 target through `LocalApprovedHaRelease`;
- absent/expired release pin is reported as `REFRESH_REQUIRED` instead of being confused with a transaction-authority hazard;
- USB binding/mount/capacity collection continues.

## Boundary

R8V13-07 remains NOT_PASS and R8V13-08 remains blocked. V2 must pass focused CI before any repeat read-only execution. No manual authority deletion, wait-for-expiry workaround, new transaction, install/cutover, Broker OTA, reboot, merge or release is authorized by this repair.


## Development-route alignment review

The active stage and task remain unchanged:

```text
ACTIVE_STAGE=N3W_T1_CORE_STACK_OTA_V1_3_R8_PHYSICAL_ACCEPTANCE
CURRENT_TASK=R8V13-07
NEXT_TASK=R8V13-08
R8V13_08_BLOCKED=true
TASK_CHAIN_STATUS=ALIGNED
```

The current repair work is within the R8V13-07 stop boundary: transaction A failed and safely restored exact 10.4, so its distinct failure/executor causes must be closed before a new fresh transaction A attempt. No later task has been entered.

However, execution-method drift was identified: text-level test assertions and auxiliary read-only observations were becoming independent false-fail gates. This conflicts with the V1.3 architecture principle that non-core observation failures remain diagnostic and that field validation should not create unnecessary false failures.

Correction:

- do not add any new R8 task node;
- do not broaden the V2 rebind beyond old-transaction/authority safety, current runtime health, release admission, USB identity and capacity evidence;
- tests bind product constants and semantic safety properties, not incidental literal filenames;
- once V2 rebind completes, stop expanding preflight and return directly to preparation of a new fresh R8V13-07 transaction A;
- R8V13-08 remains blocked until transaction A reaches U13A + healthy exact 10.0.

Latest focused CI test-only fixes:
- `6a30277ac25feccbf56b019015cc941207f75212`: release pin assertion moved to product constants;
- `2221fa3e36e87d10a0d990bc5bc9b11ed436a216`: approved manifest assertion moved to product constants;
- V2 executor bytes were not changed by these test fixes.

Current focused run: `45387271563`, IN_PROGRESS at third check; polling stopped per project rule.
