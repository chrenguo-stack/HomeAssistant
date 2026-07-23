# H3/N2 Stage 2D-9R G3R status ledger

## Current stage

```text
stage=H3/N2 Stage 2D-9R G3R
purpose=replace non-TLS-usable V69 PREPARED input
pr=176
pr_state=DRAFT
execution_gate=LOCKED_SOURCE_AND_COMPILE_ONLY
```

## Approved D1

```text
D1-H3N2-STAGE2D10-TLS-CANDIDATE-20260723-01=APPROVED
```

The old V69 result remains accepted only for its original no-network PREPARE scope. It is not an acceptable Stage 2D-10 TLS activation input because its stored `ca_pem` is not a PEM certificate.

The selected correction is a new candidate chain. TLS bypass, CA aliases, candidate repair during activation and V69 authorization replay are rejected.

## Source state

Implemented:

- exact public TLS candidate descriptor and validator;
- offline CA/leaf role, chain, SAN and fingerprint binding builder;
- Broker-to-candidate identity gate;
- `GH2D9R_PREPARE_V1` and `GH2D9R_VERIFY_V1` host protocol;
- device-side CA base64url decoding, SHA-256 binding and Mbed TLS X.509 parsing;
- generation-bound PREPARE transaction and post-restart read-only VERIFY;
- corrected package order: configuration before PREPARE authorization;
- fail-closed sensitive runtime reset;
- dedicated ESP32-C6 compile-only target;
- F1.0-RC2 product-PCB compatibility compile-only target;
- public/private boundary and deterministic fault matrices.

## Fixed runtime boundary

```text
read-only empty inspection
→ load exact TLS-valid candidate configuration
→ grant PREPARE_CANDIDATE(active=0,candidate=1)
→ persist candidate marker-last
→ read-only recover
→ verify CA SHA and candidate SHA
→ automatic restart
→ read-only VERIFY
```

The Stage 2D-9R firmware has no ACTIVATE or CLEANUP command and uses a null MQTT port. PREPARE and VERIFY are serial-only command surfaces that remain disabled in public compile targets by all-zero build, unlock and CA digest values.

## Evidence obtained

At the source checkpoint:

```text
dedicated_locked_compile=PASS
source_boundary=PASS
historical_v69_paths_unchanged=true
production_f1_0_rc2_and_packages_unchanged=true
public_repository_safety=PASS
TLS_candidate_contract_matrix=PASS
```

Product compatibility compile is part of the current CI gate and must pass before source freeze.

## Current prohibitions

```text
private_PKI_generation=false
private_PKI_delivery=false
immutable_execution_artifact_freeze=false
board_operation=false
serial_operation=false
flash_operation=false
physical_NVS_operation=false
network_operation=false
WiFi_operation=false
MQTT_operation=false
Broker_operation=false
PREPARE_CANDIDATE=false
VERIFY=false
ACTIVATE_PROFILE=false
CLEANUP_TEST_STATE=false
eFuse=false
Secure_Boot=false
Flash_Encryption=false
M401A=false
T1=false
Home_Assistant=false
Mosquitto=false
greenhouse_manager=false
production=false
Ready=false
merge=false
release=false
deployment=false
```

## Remaining source work before the next decision gate

1. Finish product compatibility compile and all source CI.
2. Freeze the test-only PKI policy and private custody descriptor template without generating secrets.
3. Freeze the exact test-partition baseline recovery procedure and evidence contract.
4. Freeze the immutable build inputs, public manifest and reproducibility checks.
5. Prepare a review-only U1/private-PKI generation proposal.

The next operator decision is not a board D2. It is a narrowly scoped approval to generate and install a test-only private PKI/custody package. Physical recovery and PREPARE remain a later independent D2 after the Artifact is immutable and all private/public bindings are verified.
