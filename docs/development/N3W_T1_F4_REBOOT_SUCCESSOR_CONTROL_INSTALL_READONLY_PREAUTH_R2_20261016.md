# N3-W T1 F4 Reboot Successor Control Install — Read-only Preauthorization R2

Date: 2026-10-16

```text
TASK=N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_READONLY_PREAUTH_R2_20261016_01
MODE=READ_ONLY

SOURCE_REPAIR_HEAD=5368acc1eb50f1fc62bbd7c16ff9e64139131a29
EXACT_ARTIFACT_ID=12028807237
EXACT_MANIFEST_SHA256=2f2ae69dbf78d5f578fa60bbee7fb269a5d0c3b17a00e2f697bc65d3ed91c40c

EXPECTED_F4_TRANSACTION_SHA256=49e7839ffe5d9e00391577a78c7c6ceb9c85a9a7cdd240ee22cc38485a3e569b
EXPECTED_RUNTIME_ACCEPTANCE_SHA256=c938244cda069247f3288d0cc14fbdd37dcf7c389e8a16669ea8a6c3fcecbfd4
EXPECTED_CERTIFICATE_STATUS_SHA256=446404d0e3725bf0e8fa9b6bd11bd67c83f16871a6e196b1cc950043ad229af4
EXPECTED_CURRENT_RUNTIME_SNAPSHOT_SHA256=29183afd73d71d4e85d8481d96f062b7c099d6721b46708a49495d58a39994f0
EXPECTED_CURRENT_BOOT_ID_SHA256=459bba3071dd3d48b7dd0a2cb750cfa9dcb09b456236564940c8fad85f79f95d

ARTIFACT_STAGING=false
AUTHORIZATION_CLAIM=false
LIVE_RUNTIME_MUTATION=false
REBOOT=false
BOARD_ACCESS=false

PROPOSED_CONTROL_INSTALL_AUTHORIZATION=N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_LIVE_20261016_01
AUTHORIZATION_GRANTED=false
```

## R2 correction

R1 incorrectly treated the historical PRE_REBOOT_READY runtime snapshot as an immutable durable acceptance record.
The read-only forensic showed that the host did not reboot and the accepted durable F4/runtime/certificate records
did not change, while the product services had undergone a controlled stop/start and remained fully healthy.

R2 therefore uses the forensic current healthy snapshot as the new immediate preauthorization baseline. It still
fail-closes if that current runtime snapshot or boot identity changes before/during this gate.

R2 must prove:

- frozen F4 transaction, runtime-acceptance and certificate-status SHA-256 values remain exact;
- current boot identity remains the forensic boot identity;
- current runtime snapshot remains the forensic healthy runtime snapshot throughout the collector;
- F4 status and certificate eligibility remain PASS;
- installed F4 material, runtime image/container contracts, TLS, Manager stability and Home Assistant runtime audit
  remain PASS;
- persistence units remain enabled, certificate timer enabled/inactive before reboot, lifecycle service inactive;
- product listener set remains exactly 1883,8123,8883;
- successor claims, lock, installed successor files, drop-in and manifest remain absent;
- successor drop-in is not loaded;
- the proposed install authorization is fresh and does not collide with F4 authorization history.

A PASS authorizes only the next decision point. It does not stage/install the artifact and does not authorize reboot.

```text
PASS_NEXT_ONE_GATE=N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_LIVE_20261016_01
AUTO_EXECUTE_LIVE_INSTALL=false
REBOOT_AUTHORIZATION_GRANTED=false
```
