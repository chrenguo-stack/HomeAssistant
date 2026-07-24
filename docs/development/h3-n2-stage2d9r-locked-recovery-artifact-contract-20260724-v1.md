# H3/N2 Stage 2D-9R locked recovery Artifact contract V1

## Purpose

This contract closes the missing recovery-Artifact step after the immutable firmware
Artifact has been built twice and frozen. It produces a deterministic, public-only,
non-executable package for the dedicated test partition.

The package is evidence and reviewed input only. It does not authorize or perform
a board, serial, Flash, NVS, network, Broker, PREPARE, VERIFY, ACTIVATE or CLEANUP
operation.

## Frozen inputs

The recovery Artifact must bind:

- immutable firmware source `c9e8447c24b0f09f3eac3f56791f2346e8aa5d61`;
- immutable build binding `b39f20c55b865ec87eb650d620fd1a82b930c1ad`;
- canonical immutable Artifact ID `8585140964`;
- immutable payload SHA-256
  `5dbe763fe411728533018dd324075f5287ee3542f8351113d54ec80a7042f1d3`;
- application SHA-256
  `7651a6476cd48dda6aa5e400695e126b91141c95fca5b74d879f65f2058d1630`;
- merged-image SHA-256
  `ea6af469ad7ae103d40a551f482fc18d1f2afc9ed75933481f1802f0a7b2916f`;
- unlock, CA and candidate public digests already frozen in Stage 2D-9R;
- exact recovery contract, locked authorization template and source-only gate.

## Recovery payload

The invariant deterministic tar contains only:

- `test-partition-erased.bin`: exactly 65,536 bytes of `0xff`;
- `recovery-artifact-descriptor.json`;
- `recovery-authorization-manifest.template.json`;
- `RECOVERY_CONTRACT.md`;
- `SHA256SUMS`.

No serial path, board identity, private key, raw unlock token, MQTT password,
authorization record, consumed marker or executable recovery command is included.

## Independent builds

Two clean GitHub Actions runs must build the invariant tar independently from the
same source commit. The lane and run metadata remain outside the invariant tar.

Acceptance requires:

```text
clean_build_count=2
payloads_byte_identical=true
descriptor_digests_identical=true
erased_image_digests_identical=true
```

Any mismatch fails closed. The canonical and reproduction Artifact IDs must be
different and both must remain bound to the same source SHA.

## Freeze

A separate freeze workflow downloads the two build Artifacts, compares their tar
bytes, validates the all-`0xff` image and reviewed bindings, and publishes a frozen
public evidence Artifact with a manifest.

The frozen manifest continues to require every execution and physical-operation
authorization flag to be `false`.

## Future D2 boundary

The locked recovery Artifact is not a D2 package. A future exact D2 may reference
its frozen hashes, but must separately bind the real board identity, serial path,
current V69 partition digest, toolchain and one-shot authorization. No such values
or permission are created by this pipeline.
