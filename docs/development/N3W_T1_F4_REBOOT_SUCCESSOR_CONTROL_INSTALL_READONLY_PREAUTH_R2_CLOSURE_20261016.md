# N3-W T1 F4 Reboot Successor Control Install — Read-only Preauthorization R2 Closure

Date: 2026-10-16

```text
TASK=N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_READONLY_PREAUTH_R2_20261016_01
RESULT=CLOSED_PASS

SOURCE_REPAIR_HEAD=5368acc1eb50f1fc62bbd7c16ff9e64139131a29
SOURCE_REPAIR_PR=600
SOURCE_CLOSURE_PR=601
PREAUTH_PREPARATION_PR=602

EXACT_ARTIFACT_ID=12028807237
EXACT_MANIFEST_SHA256=2f2ae69dbf78d5f578fa60bbee7fb269a5d0c3b17a00e2f697bc65d3ed91c40c

TRANSACTION_SHA256=49e7839ffe5d9e00391577a78c7c6ceb9c85a9a7cdd240ee22cc38485a3e569b
RUNTIME_ACCEPTANCE_SHA256=c938244cda069247f3288d0cc14fbdd37dcf7c389e8a16669ea8a6c3fcecbfd4
CERTIFICATE_STATUS_SHA256=446404d0e3725bf0e8fa9b6bd11bd67c83f16871a6e196b1cc950043ad229af4
BOOT_ID_SHA256=459bba3071dd3d48b7dd0a2cb750cfa9dcb09b456236564940c8fad85f79f95d
CURRENT_RUNTIME_SNAPSHOT_SHA256=29183afd73d71d4e85d8481d96f062b7c099d6721b46708a49495d58a39994f0

RUNTIME_SNAPSHOT_STABLE=true
BOOT_ID_STABLE=true
F4_DURABLE_STATE_UNCHANGED=true
SUCCESSOR_RESIDUE_ABSENT=true
SUCCESSOR_DROPIN_LOADED=false
PRODUCT_LISTENER_PORTS=1883,8123,8883
INSTALL_AUTHORIZATION_COLLISION=false

ARTIFACT_STAGING=false
AUTHORIZATION_CLAIMED=false
LIVE_RUNTIME_MUTATION=false
REBOOT_EXECUTED=false
BOARD_ACCESS=false

NEXT_ONE_GATE=N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_LIVE_20261016_01
CONTROL_INSTALL_AUTHORIZATION_GRANTED=false
REBOOT_AUTHORIZATION_GRANTED=false
AUTO_EXECUTE_LIVE_INSTALL=false
```

## Closure

The corrected R2 read-only collector completed successfully.

The real T1 remains at the accepted F4 PRE_REBOOT_READY boundary:

- F4 launcher status PASS;
- certificate-phase eligibility PASS;
- durable transaction SHA-256 unchanged;
- runtime-acceptance report SHA-256 unchanged;
- certificate-status SHA-256 unchanged;
- current boot identity stable;
- current healthy runtime identity stable throughout the gate;
- F4 installed-material and factory binding checks PASS;
- runtime image/container contracts PASS;
- TLS runtime PASS;
- Manager runtime stability PASS;
- Home Assistant private/runtime audit PASS;
- Broker and Services active;
- Guard, Provision, Broker, Services and certificate timer remain enabled as required;
- certificate timer remains inactive before reboot;
- certificate lifecycle service remains inactive;
- product listeners are exactly 1883, 8123 and 8883.

The successor boundary is still clean:

- no successor install-authorization record;
- no reboot-authorization record;
- no successor authority lock;
- no runtime guard, reboot authority or reboot verifier installed;
- no successor lifecycle drop-in;
- no installed successor manifest;
- no successor drop-in loaded by systemd;
- proposed control-install authorization ID does not collide with previous F4 authorization IDs/history.

The R2 gate performed no artifact staging, authorization claim, live mutation, reboot or board access.

## Runtime snapshot R1 correction retained

The earlier historical runtime snapshot is not used as a permanent acceptance identity. The immediately preceding
read-only forensic proved that the host had not rebooted, durable F4 records had not drifted, and the product
runtime remained healthy after a controlled service stop/start. R2 therefore correctly freezes the current healthy
runtime identity only across the immediate preauthorization gate and the upcoming bounded control-install boundary.

Current accepted immediate runtime baseline:

```text
29183afd73d71d4e85d8481d96f062b7c099d6721b46708a49495d58a39994f0
```

## Next authorization boundary

A PASS does not itself authorize mutation.

The next gate is:

```text
N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_LIVE_20261016_01
```

It requires a fresh explicit one-shot user authorization.

That gate may only:

1. stage the exact successor artifact bound to source head
   `5368acc1eb50f1fc62bbd7c16ff9e64139131a29`;
2. validate exact artifact/manifests before mutation;
3. durably claim and consume the dedicated control-install authorization;
4. install the bounded successor control files and manifest;
5. reload systemd so the drop-in becomes visible;
6. run the repository-owned read-only install verification.

It must not reboot the host, claim a reboot authorization, start the certificate timer, access boards, or merge PRs.

Reboot remains a later independent one-shot authorization boundary.
