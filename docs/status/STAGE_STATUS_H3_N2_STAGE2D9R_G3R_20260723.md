# H3/N2 Stage 2D-9R G3R status ledger

## Current stage

```text
stage=H3/N2 Stage 2D-9R G3R
purpose=replace non-TLS-usable V69 PREPARED input
pr=176
pr_state=DRAFT
execution_gate=LOCKED_U1_REVIEW_PENDING
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
- public/private boundary and deterministic fault matrices;
- test-partition recovery contract and immutable-build contract;
- offline private-PKI generator source, complete host-toolchain binding and custody gate.

Frozen generator source:

```text
generator=tools/h3_n2_stage2d9r_private_pki_generator_20260723_v1.py
generator_sha256=a9be0c96fd58882b3778886515076f6aae5940c0ac195fc629ed1ebe708265d0
generator_contract_test_sha256=6063bdba137f703b967bbc6324bafeda73e990978cdeba1968cc3d4fd08fba6d
default_mode=read_only_toolchain_probe
private_generation_authorized=false
```

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

## Private PKI boundary

The generator may only execute after an exact, unexpired, one-shot U1 authorization binds:

- final source SHA;
- generator SHA-256;
- Python, OpenSSL and `mosquitto_passwd` executable SHA-256 values;
- private custody template and gate;
- `HOME_LOCAL_STATE_STAGE2D9R_PRIVATE_PKI_V1` and selected-root digest;
- test identity `stage2d9r.local:8883` and run suffix `tlsvalid01`.

Authorization is claimed before private material generation. The generator does not start a Broker, open a network socket, access a board or issue firmware commands.

## Evidence obtained

At the source and host checkpoint:

```text
dedicated_locked_compile=PASS
product_PCB_compatibility_compile=PASS
source_boundary=PASS
historical_v69_paths_unchanged=true
production_f1_0_rc2_and_packages_unchanged=true
public_repository_safety=PASS
TLS_candidate_contract_matrix=PASS
recovery_contract_matrix=PASS
immutable_build_contract_matrix=PASS
generator_source_materialization=PASS
generator_contract_matrix=PASS_local_and_CI_bound
host_toolchain_probe=PASS
```

Read-only host probe binding:

```text
probe_artifact_id=8567934795
probe_artifact_zip_sha256=76584fb7d80e28860f3c35fadd2fe3738932ec9e6258bcffdde39672e18b4d4e
probe_artifact_source_sha=c899829e89d87ce29c50e869b2970f8132d0e67f
python_executable_sha256=4e28e811a89aeac6eed668ae641c7f85f5831e42e8dc6cd9a85a3bcc032ec46a
openssl_executable_sha256=04ad05ce2e7eaf92116dac99a984cc0e589040a103589f93a9fe452832766973
openssl_version=OpenSSL 3.5.0 8 Apr 2025
mosquitto_passwd_executable_sha256=d6fdc23fa4bb09198bf74925207aa2b69b1455970e31fefc6157dfe4be2b07ee
custody_root_selection_rule=HOME_LOCAL_STATE_STAGE2D9R_PRIVATE_PKI_V1
custody_root_digest_sha256=4cd43ee4b2df177bd99c32d3904dbe1e1df890aa14c6b6714a6b4f7ae4024868
custody_root_exists=false
secret_values_included=false
private_paths_included=false
board_operation=false
network_operation=false
broker_started=false
```

Public L1 record:

`docs/acceptance/h3-n2-stage2d9r-private-pki-toolchain-probe-u1-l1-v1.json`

All workflows for the final current PR head must be green again before the exact U1 review binding is issued.

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
Mosquitto_Broker_start=false
greenhouse_manager=false
production=false
Ready=false
merge=false
release=false
deployment=false
```

## Remaining work before U1

1. Obtain a fully green CI set for the final source head containing this public probe record.
2. Freeze the final PR/source SHA and exact custody template/gate digests.
3. Build a review-only U1 request package binding the observed host toolchain and custody-root digest.
4. Obtain explicit operator authorization.
5. Only after authorization, issue the one-shot authorization record and run the offline generator once.

The next operator decision is not a board D2. It is a narrowly scoped one-shot approval to generate and install a test-only private PKI/custody package. Physical baseline recovery and PREPARE remain a later independent exact D2 after private/public bindings and the immutable Artifact are frozen.
