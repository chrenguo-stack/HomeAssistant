# H3/N2 Stage 2D-9R G3R status ledger

## Current stage

```text
stage=H3/N2 Stage 2D-9R G3R
purpose=replace non-TLS-usable V69 PREPARED input
pr=176
pr_state=DRAFT
execution_gate=LOCKED_PUBLIC_EXPORT_AND_ARTIFACT_PREPARATION_ONLY
```

## Approved D1

```text
D1-H3N2-STAGE2D10-TLS-CANDIDATE-20260723-01=APPROVED
```

The old V69 result remains accepted only for its original no-network PREPARE scope. It is not an acceptable Stage 2D-10 TLS activation input because its stored `ca_pem` is not a PEM certificate. The selected correction is a new candidate chain. TLS bypass, CA aliases, candidate repair during activation and V69 authorization replay remain rejected.

## Source and compile state

Implemented and verified:

- exact public TLS candidate descriptor and validator;
- offline CA/leaf role, chain, SAN and fingerprint binding builder;
- Broker-to-candidate identity gate;
- `GH2D9R_PREPARE_V1` and `GH2D9R_VERIFY_V1` host protocol;
- device-side CA base64url decoding, SHA-256 binding and Mbed TLS X.509 parsing;
- generation-bound PREPARE transaction and post-restart read-only VERIFY;
- fail-closed sensitive runtime reset;
- dedicated ESP32-C6 compile-only target;
- F1.0-RC2 product-PCB compatibility compile-only target;
- public/private boundary and deterministic fault matrices;
- test-partition recovery contract and immutable-build contract;
- offline private-PKI generator source, complete host-toolchain binding and custody gate.

Frozen reviewed generator source:

```text
generator=tools/h3_n2_stage2d9r_private_pki_generator_20260723_v1.py
generator_sha256=a9be0c96fd58882b3778886515076f6aae5940c0ac195fc629ed1ebe708265d0
generator_source_sha=94f116ec99a7ba8b1da250f93b323f260c7ff5a6
default_mode=read_only_toolchain_probe
```

## Fixed future runtime boundary

```text
read-only identify current V69 state
→ exact locked recovery to deterministic baseline
→ recovery readback/seed verification
→ erase and flash new Stage2D9R firmware
→ Flash verify and automatic reset
→ start exact isolated Broker only under a future D2
→ send exactly one GH2D9R_PREPARE_V1
→ firmware automatic restart
→ send exactly one read-only GH2D9R_VERIFY_V1
→ stop Broker and retain private evidence
```

The Stage 2D-9R firmware has no ACTIVATE or CLEANUP command. PREPARE itself does not establish MQTT. Any future Broker start, board access, Flash/NVS write, PREPARE or VERIFY requires a separate exact D2.

## Private PKI U1 closure

Read-only toolchain probe:

```text
probe_result=PASS
architecture=x86_64
python_executable_sha256=4e28e811a89aeac6eed668ae641c7f85f5831e42e8dc6cd9a85a3bcc032ec46a
openssl_executable_sha256=04ad05ce2e7eaf92116dac99a984cc0e589040a103589f93a9fe452832766973
mosquitto_passwd_executable_sha256=d6fdc23fa4bb09198bf74925207aa2b69b1455970e31fefc6157dfe4be2b07ee
custody_root_digest_sha256=4cd43ee4b2df177bd99c32d3904dbe1e1df890aa14c6b6714a6b4f7ae4024868
```

One-shot authorization:

```text
authorization_id=U1-H3N2-STAGE2D9R-PRIVATE-PKI-20260723-01
authorization_status=consumed_passed_retired
authorization_replay_permitted=false
automatic_retry_permitted=false
authorized_execution_package_sha256=d2646f6bdec22e55b3a1456043f7a63601d58bd5503a609713417e5ac4cc0f87
authorization_record_sha256=1764d202e294d4e3125d7f641f2a0068768f38104dfb6273bddfb3789268f770
authorization_binding_sha256=546645b4d21bfd7882f22284200582d64abb3a71466f5fcb8e11d43ac8896ad6
```

Generated and verified bindings:

```text
private_custody_gate=PASS
private_package_sha256=0632b37a70aa2eae416c48ffa9420a8f1e13788c22a7d12e211f77cf6e78a267
private_descriptor_sha256=59814b825cd2df4ac7f0e3eb137798af4efdbbed4da9d627fe8ad98144be8687
public_descriptor_sha256=93bb071a5bf6f58472ac9e3891c2330dd9de6f05410824ad2fb51829267b4540
authorization_consumed_marker_sha256=fbe03088de17b8db4d8b048e1985d571ca9f54d3add9b9fc3fce1735c9bec261
ca_pem_sha256=cfcb6638ed61731270f3bf8e9e262c1512fbca8ff34d4b08b62186453233e963
broker_certificate_sha256=988b6f82b04b0b3cf13f58a07ecd85e420e5576c167fe01ea0940d4530e20ac7
broker_spki_sha256=f034dc2a036f709287f0558773418ee1799e75bee50dcf55e09143a3a9052a03
candidate_digest_sha256=f22144e37372b883b7a38d07eff2980a865108cf7c8fed9bfdb9f198a030b5c5
root_CA_role_valid=true
broker_leaf_role_valid=true
certificate_chain_valid=true
hostname_valid=true
private_modes_valid=true
public_private_leakage_scan_passed=true
```

Public closure record:

`docs/acceptance/h3-n2-stage2d9r-private-pki-u1-generation-l1-v1.json`

## Current prohibitions

```text
U1_replay=false
private_PKI_regeneration=false
board_operation=false
serial_operation=false
flash_operation=false
physical_NVS_operation=false
network_operation=false
WiFi_operation=false
MQTT_operation=false
Broker_start=false
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
Mosquitto_service=false
greenhouse_manager=false
production=false
Ready=false
merge=false
release=false
deployment=false
```

## Remaining work before D2

1. Export only the public CA certificate, Broker certificate/full chain, redacted public configuration and public descriptor from private custody.
2. Independently validate that export against the frozen U1 hashes and reject any private key, password, authorization record, private path or raw command leakage.
3. Commit the validated public-only descriptor set and freeze a new exact source checkpoint.
4. Generate the immutable Stage 2D-9R firmware and locked recovery Artifact twice; require byte-identical outputs and exact manifest bindings.
5. Perform host-only Artifact verification and private-custody binding verification.
6. Prepare a separate exact D2 review package for deterministic baseline recovery, one new PREPARE and one read-only VERIFY.

The next operator action is a host-only public export. It does not authorize Broker startup, network access or any board operation.
