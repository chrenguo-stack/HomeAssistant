# H3/N2 Stage 2D-9R host Artifact and custody preauthorization probe contract V1

## Purpose

This contract defines the last read-only checkpoint before any deep private-custody
content verification and before the future exact D2 review package.

The probe has two responsibilities:

1. independently verify the complete public immutable-firmware Artifact and locked
   recovery Artifact offline; and
2. verify private-custody roots, safe descriptors, one-shot consumed markers and
   secret-file metadata without reading secret-file content.

The package is a review and read-only probe only. It does not authorize or perform
private material generation, network access, Broker startup, board access, serial
access, Flash/NVS mutation, PREPARE, VERIFY, ACTIVATE or CLEANUP.

## Public Artifact verification

The package embeds exact public copies of:

- immutable firmware Artifact ID `8585140964`, run `30062650179`, source
  `c9e8447c24b0f09f3eac3f56791f2346e8aa5d61`;
- locked recovery freeze Artifact ID `8589568443`, run `30075191767`, source
  `f312f8580d9f4312f4dd1429b2d7755e1c550636`.

The probe validates tar membership, deterministic metadata, nested `SHA256SUMS`,
firmware hashes, public candidate bindings, the all-`0xff` recovery image, the
recovery manifest digest and all authorization flags.

## Private-custody metadata verification

The read-only preauthorization probe may inspect only:

- custody-root existence, type, non-symlink status and mode;
- custody-root path digest, without printing the path;
- safe JSON descriptors that are already bound by reviewed SHA-256 values;
- one-shot consumed markers that are already bound by reviewed SHA-256 values;
- secret-file existence, regular-file/non-symlink status, mode and expected size
  where a size is reviewed.

The probe must not open or hash:

- `unlock-token.hex`;
- PKI private-key files;
- the Mosquitto password database;
- any file containing a raw MQTT password.

It must not print private paths, descriptor contents, authorization records,
consumed-marker contents or any secret value.

## Deep private-content binding

This preauthorization probe does not prove that the raw unlock token hashes to the
public unlock digest, and it does not prove that private keys match the public
certificates. Those checks require a separate exact, time-limited, read-only
operator authorization after this package and the host toolchain have been frozen.

No authorization for that deeper read is included in this contract or package.

## Fail-closed conditions

The probe stops if any expected public Artifact, source SHA, run ID, Artifact ID,
file digest, custody-root digest, descriptor digest, marker digest, file mode,
file type, file size or host Python binding differs.

A failed read-only preauthorization probe does not authorize repair, deletion,
regeneration or retry of private material. Diagnosis must remain read-only and a
new reviewed package is required for any changed binding.

## Permanent prohibitions

```text
private_material_generation=false
raw_unlock_token_read=false
private_key_content_read=false
password_content_read=false
private_paths_output=false
network_operation=false
broker_started=false
board_operation=false
serial_operation=false
flash_operation=false
physical_nvs_operation=false
prepare_executed=false
verify_executed=false
activate_executed=false
cleanup_executed=false
production_operation=false
ready=false
merge=false
release=false
deployment=false
```
