# H3/N2 Stage 2D-9R G3R status ledger

## Current stage

```text
stage=H3/N2 Stage 2D-9R G3R
purpose=replace non-TLS-usable V69 PREPARED input
pr=176
pr_state=DRAFT
execution_gate=LOCKED_FINAL_SOURCE_AND_IMMUTABLE_BUILD_PREPARATION
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
- offline private-PKI generator source, complete host-toolchain binding and custody gate;
- offline private command-material generator, custody gate and deterministic fault matrix;
- U1-02 private command material generation and public-only export closure;
- final immutable firmware source with non-zero public unlock and CA bindings;
- canonical final build binding contract.

Frozen reviewed private PKI generator source:

```text
generator=tools/h3_n2_stage2d9r_private_pki_generator_20260723_v1.py
generator_sha256=a9be0c96fd58882b3778886515076f6aae5940c0ac195fc629ed1ebe708265d0
generator_source_sha=94f116ec99a7ba8b1da250f93b323f260c7ff5a6
default_mode=read_only_toolchain_probe
```

Frozen reviewed private command-material source:

```text
generator=tools/h3_n2_stage2d9r_private_command_material_generator_20260724_v1.py
generator_sha256=60628bf274fdcca05e8644b30510f6abde2129a57e3e49ca5a12db30d7129563
gate=tools/h3_n2_stage2d9r_private_command_material_gate_20260724_v1.py
gate_sha256=512fb70c14d3ad983055fde4e85cb3814445df3ad7b5555695cc6c54575b4a6e
implementation_binding=3d3b67cac008adf30e90a51e891d0dd53b36df69
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

Private generation closure record:

`docs/acceptance/h3-n2-stage2d9r-private-pki-u1-generation-l1-v1.json`

## Public PKI export closure

```text
public_export_result=PASS
public_export_zip_sha256=72c739b5e197192b9569083bf3446d7c0f5340652b21ab44cdd99eeca3f12d31
public_export_mode=0600
public_descriptor_sha256=93bb071a5bf6f58472ac9e3891c2330dd9de6f05410824ad2fb51829267b4540
ca_pem_sha256=cfcb6638ed61731270f3bf8e9e262c1512fbca8ff34d4b08b62186453233e963
broker_certificate_sha256=988b6f82b04b0b3cf13f58a07ecd85e420e5576c167fe01ea0940d4530e20ac7
broker_spki_sha256=f034dc2a036f709287f0558773418ee1799e75bee50dcf55e09143a3a9052a03
candidate_digest_sha256=f22144e37372b883b7a38d07eff2980a865108cf7c8fed9bfdb9f198a030b5c5
certificate_chain_valid=true
hostname_valid=true
public_private_leakage_scan_passed=true
private_paths_included=false
private_keys_included=false
raw_mqtt_password_included=false
authorization_record_included=false
consumed_marker_included=false
private_descriptor_included=false
```

Committed public-only material:

`tests/h3_n2_stage2d9r_tls_candidate/public_pki_tlsvalid01/`

Public export closure record:

`docs/acceptance/h3-n2-stage2d9r-public-pki-export-l1-v1.json`

## Private command-material closure

```text
u1_01_status=consumed_failed_retired
u1_01_failure_stage=WRAPPER_PRECHECK
u1_01_replay_permitted=false
u1_02_status=consumed_passed_retired
u1_02_replay_permitted=false
automatic_retry_permitted=false
unlock_digest_sha256=3650d44f8761f21dc1931fbd9b6ba6a1d9da92ffa469b3d4f98ee5411a6809e3
private_command_material_package_sha256=cc9086c20781007655c498b78ff1ce7af3316db0c02edbae2440d177d7fdfbb5
private_descriptor_sha256=cda5b1604200045fec0db45e46f9c441e1bde10f2e5a57f8c98ee2d14b5f9a75
public_descriptor_sha256=91c10168174438fc30b3dce087a6b75e24375b87b4262bafddb5b2822ee16d23
authorization_consumed_marker_sha256=1fc51b7338adc56b00b38795173b805b7408e7aafa4e0315e7553dc5898779a9
private_paths_included=false
secret_values_included=false
board_operation=false
network_operation=false
broker_started=false
```

Committed public descriptor:

`tests/h3_n2_stage2d9r_tls_candidate/public_command_material_tlsvalid01/public-command-material-descriptor.redacted.json`

Public command-material closure record:

`docs/acceptance/h3-n2-stage2d9r-private-command-material-u1-generation-l1-v1.json`

## Final immutable source binding

```text
source_checkpoint_sha=5b2fe7070d5cc282d3028f441678a7f807a1f08f
build_binding_algorithm=sha256-canonical-json-first-160-bits-v1
build_binding=b39f20c55b865ec87eb650d620fd1a82b930c1ad
build_binding_sha256_full=b39f20c55b865ec87eb650d620fd1a82b930c1ad3f6e8c7b16b8c4dcaaf419ab
unlock_digest_sha256=3650d44f8761f21dc1931fbd9b6ba6a1d9da92ffa469b3d4f98ee5411a6809e3
ca_pem_sha256=cfcb6638ed61731270f3bf8e9e262c1512fbca8ff34d4b08b62186453233e963
candidate_digest_sha256=f22144e37372b883b7a38d07eff2980a865108cf7c8fed9bfdb9f198a030b5c5
partition_table_sha256=5afa0f77d5d815f00b14afbcc3b974037c5ba10c9bdcdcffa196b55e403b5cd8
```

Final source files:

- `tests/h3_n2_stage2d9r_tls_candidate/stage2d9r_final_build_binding_20260724_v1.json`
- `firmware/esphome_rc/board_lab/h3_profile_isolated_device_g3r_tls_prepare/greenhouse_profile_isolated_device_g3r_immutable_20260724_v1.yml`

## Current prohibitions

```text
private_command_material_generation=false
private_command_material_U1_granted=false
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

1. Require all CI on the final immutable source checkpoint to complete successfully.
2. Generate the immutable Stage 2D-9R firmware twice from independent clean CI runs and require byte-identical bootloader, partition table, application and merged images.
3. Freeze the exact immutable firmware Artifact, manifest and source/run bindings.
4. Generate and freeze the locked test-partition recovery Artifact without executing it.
5. Perform host-only Artifact verification and private-custody binding verification.
6. Prepare a separate exact D2 review package for deterministic baseline recovery, one new PREPARE and one read-only VERIFY.

No physical action is authorized. The next operator decision remains the future exact D2 after immutable Artifact and recovery evidence are complete.
