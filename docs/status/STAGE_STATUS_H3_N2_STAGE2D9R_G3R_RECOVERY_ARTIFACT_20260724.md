# H3/N2 Stage 2D-9R G3R recovery Artifact checkpoint

## Task-flow position

```text
private PKI U1 closure=complete
private command-material U1-01=consumed_failed_retired
private command-material U1-02=consumed_passed_retired
public command-material closure=complete
final immutable firmware source binding=complete
immutable firmware clean build A/B=complete
immutable firmware Artifact freeze=complete
immutable firmware observer closure=complete
locked recovery Artifact contract=complete
locked recovery clean build A/B=complete
locked recovery Artifact freeze=complete
locked recovery observer closure=complete
host-only Artifact and private-custody verification=pending
exact D2 review package=pending
physical execution authorization=false
```

No task between public command material and locked recovery Artifact closure has been
skipped. U1-01 and U1-02 remain permanently retired and cannot be replayed.

## Immutable firmware binding

```text
immutable_source_sha=c9e8447c24b0f09f3eac3f56791f2346e8aa5d61
build_binding=b39f20c55b865ec87eb650d620fd1a82b930c1ad
build_run_a=30062650179
build_run_b=30062650177
canonical_artifact_id=8585140964
repro_artifact_id=8585137349
payload_sha256=5dbe763fe411728533018dd324075f5287ee3542f8351113d54ec80a7042f1d3
application_sha256=7651a6476cd48dda6aa5e400695e126b91141c95fca5b74d879f65f2058d1630
merged_image_sha256=ea6af469ad7ae103d40a551f482fc18d1f2afc9ed75933481f1802f0a7b2916f
```

## Locked recovery Artifact binding

```text
recovery_source_sha=f312f8580d9f4312f4dd1429b2d7755e1c550636
build_run_a=30075191850
build_run_b=30075191822
freeze_run=30075191767
observer_run=30075193982
canonical_artifact_id=8589561310
repro_artifact_id=8589560891
freeze_artifact_id=8589568443
observer_artifact_id=8589577241
payload_tar_sha256=c1ed8e5f00b17cbe5bab30aec75d2e8637986b9c19b2389b761bebf3fc0b8d8b
manifest_sha256=fe82c458533953df4c86966d047d1f66b59da15e5299b3953135702236d68690
manifest_file_sha256=88ac19e9baa1c00581adfb89ad5f0b00a0cf5e4044fe330b4e5670615bf5df4a
observer_closure_sha256=457f92efae2b48eae2b93ec887c9dc5b40c949b193ea2345db917f2d30f47058
erased_image_sha256=71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063
clean_build_count=2
payloads_byte_identical=true
reproducible=true
```

The recovery payload contains an all-`0xff` 65,536-byte test-partition image,
a public descriptor, the locked authorization template, the reviewed recovery
contract and checksums. It contains no real board identity, serial path,
authorization record, consumed marker, private key, raw unlock token or MQTT
password.

## Current locked boundary

```text
recovery_authorized=false
execution_authorized=false
board_operation_authorized=false
serial_operation_authorized=false
flash_operation_authorized=false
physical_nvs_operation_authorized=false
network_operation_authorized=false
broker_operation_authorized=false
firmware_flash_authorized=false
prepare_authorized=false
verify_authorized=false
activate_authorized=false
cleanup_authorized=false
efuse_operation_authorized=false
secure_boot_change_authorized=false
flash_encryption_change_authorized=false
production_operation_authorized=false
ready_authorized=false
merge_authorized=false
release_authorized=false
deployment_authorized=false
```

## Remaining ordered work before D2

1. Complete CI for the committed recovery manifest and observer closure.
2. Produce a host-only verification package that independently checks the immutable
   firmware Artifact, locked recovery Artifact and their public source/run bindings.
3. Run a read-only private-custody binding probe on the authorized Mac without
   reading or outputting private values.
4. Freeze the host-only verification evidence.
5. Prepare a separate exact D2 review package binding the real board pre-state,
   serial path digest, current V69 partition digest, immutable firmware Artifact,
   locked recovery Artifact, toolchain and one-shot execution counts.
6. Stop and request the new exact D2. No physical action occurs before that decision.
