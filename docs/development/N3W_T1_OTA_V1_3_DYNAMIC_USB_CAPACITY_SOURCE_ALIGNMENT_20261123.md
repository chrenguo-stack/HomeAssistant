# N3W T1 Core Stack OTA V1.3 dynamic USB capacity source alignment

Date: 2026-11-23

## Architecture authority

`docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md`

Architecture blob: `2040a5d6b9568d0646a661db23633efe60229fcc`.

V1.3 supersedes V1.2 for future implementation and acceptance. V1.2 remains historical evidence.

## Frozen product rule

```text
USB_PRODUCT_MIN_CAPACITY_GB=16
USB_MEASURED_USABLE_CAPACITY_MIN_BYTES=15032385536
STATIC_GENERIC_USB_RESERVE=REJECTED
PER_OPERATION_DYNAMIC_CAPACITY=true
```

The product requires a 16GB-or-larger USB. Runtime does not trust a marketed capacity label or mechanically require 16,000,000,000 raw bytes; the machine-verifiable media gate remains at least 14 GiB measured usable filesystem capacity. This media gate does not prove a particular OTA operation has sufficient remaining space.

Every variable-size write performs a fresh current-free-space check immediately before the write:

1. target: approved exact archive size;
2. predecessor: read-only exact `docker image save` byte measurement, then current free-space check, then formal export;
3. protected HA data: after quiesce, use the same tar/gzip/encryption pipeline in count-only mode, then current free-space check, then formal backup.

Fixed constants are allowed only for bounded metadata/filesystem atomic-write overhead. They must not stand in for future variable payloads.

If protected-data capacity is insufficient after first stop, the existing pre-cutover recovery responsibility restarts and verifies the predecessor. The capacity cause remains visible through the durable transaction/status path.

## Source implementation

Executable code change head:

`af1f47aedf4a957b11101f36202cffe4831a1bf6`

Source/test/CI wiring head:

`1380b7c8b09d05d62b91194c24275ac9558b4ad6`

Implemented changes:

- `USB_PRODUCT_MIN_CAPACITY_GB=16` records the product requirement;
- runtime uses the existing `USB_MEASURED_USABLE_CAPACITY_MIN_BYTES=14*1024**3` machine-verifiable filesystem gate rather than relying on marketing labels or an over-strict raw-byte comparison;
- prepare-authority schema advanced to `gh.n3w-t1-ha-prepare-authority/2` and no longer accepts caller-supplied `max_predecessor_bytes` or `usb_reserve_bytes`;
- install-authority schema advanced to `gh.n3w-t1-ha-install-authority/2`; caller-supplied static USB install/recovery budgets were removed;
- target writes re-read current USB free bytes immediately before the exact-size write;
- predecessor exact archive size is measured from the real export stream after target preparation and immediately before the predecessor write;
- protected-data backup gains same-pipeline count-only measurement and current-free-space admission before the actual removable-media write;
- target/predecessor capacity failures are durable U3 failure codes;
- post-stop protected-data capacity failure is preserved through automatic predecessor restoration;
- status exposes the stable capacity cause rather than reducing it to a generic observation failure;
- automatic retry does not repeat target/predecessor writes while current free space remains insufficient; it performs only a fresh free-space check and returns a stable waiting result;
- pre-stop U3 capacity-blocked transactions are the only active HA transactions replaceable by a fresh PREPARE, enabling a larger USB without weakening later transaction ownership;
- the old blocked transaction is archived and old USB transaction contents remain untouched;
- Manager treats the two pre-stop capacity codes as retryable preparation state and republishes the PREPARE control;
- Home Assistant OTA attributes publish a Chinese `status_message_or_null` explaining that USB free space is insufficient and how to retry;
- V1.3 regression tests prevent reintroduction of generic static prepare reserves and prove no write begins when the corresponding current-space gate fails.

## Test evidence

Initial source-head CI found one test-only regression: `inspect` was removed from the R1 test module while another security test still used it. This was repaired locally without product design change.

At source/test head `1380b7c8...`:

- Manager A-to-B source step: SUCCESS, `250 passed`, including `test_n3w_t1_ota_v1_3_dynamic_usb_capacity.py`;
- 15 repository workflows: SUCCESS;
- 0 workflow failures at the final permitted poll;
- Manager A-to-B exact-package continuation: still running;
- Home Assistant target-binding source/package workflow: still running.

GitHub runs still in progress when active polling stopped:
- Manager A-to-B: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/45106586861
- Home Assistant target binding: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/45106586849

No CI terminal success is claimed for those two runs in this document.

## Live R8 boundary

The spare T1 remains at the already-proven fresh transaction stop:

```text
CURRENT_LIVE_PHASE=U1_PREPARE_REQUESTED
CURRENT_U1_VALID=true
RECREATE_U1=false
LIVE_UPDATER_ALIGNED_TO_V1_3=false
U1_TO_U4_ALLOWED=false
```

The T1 still runs the previously installed updater artifact. No V1.3 updater has been deployed in this source/document work.

The previously proposed static-reserve U1→U4 operator command is retired and must not be executed.

After exact V1.3 CI/package closure, the next live sequence is:

1. identify and verify the exact V1.3 recovery-updater artifact;
2. separately authorize/deploy that updater on the spare T1 without advancing the HA transaction;
3. read-only rebind the existing fresh U1 transaction and existing candidate;
4. issue the V1.3 prepare authority;
5. resume the existing U1 through dynamic target/predecessor capacity admission to U4;
6. stop at U4 before INSTALL/U5.

USB format, reboot/power-cycle, Broker mutation/OTA, PR merge and production release remain outside this source-alignment work.
