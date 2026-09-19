# H3/N2 Stage 2D-9R G3R host Artifact and custody preauthorization probe V2

## Purpose

V2 replaces the retired V1 probe after V1 failed closed with
`FAILURE_MESSAGE=marker record mismatch`.

The failure occurred only after the target consumed marker had passed its exact
full-file SHA-256, file type and mode checks. It therefore did not indicate a
changed or damaged marker. V1 then applied a redundant inner
`record_sha256` equality assertion whose expected value was inconsistent with
the already-bound marker bytes.

## V2 marker contract

V2 requires, for each consumed marker:

- the exact reviewed full-file SHA-256;
- a regular non-symlink file with mode `0600`;
- the exact authorization ID and terminal status;
- `one_shot=true`;
- `replay_permitted=false`;
- `secret_values_included=false`;
- a syntactically valid 64-hex `record_sha256` field.

V2 does not publish or compare the inner record digest. Cross-binding the inner
record digest to private authorization material is explicitly deferred to a
separate exact private-content read-only authorization. This does not weaken the
preauthorization marker binding because the exact full-file SHA-256 already
binds every byte of the marker, including the inner field.

## Read boundary

The package may fully read and validate the two frozen public Artifacts and may
read only reviewed safe descriptors and consumed marker JSON. For secret files
it may inspect only existence, regular-file/non-symlink status, mode and expected
size where fixed.

It must not read raw unlock-token content, private-key content, Mosquitto
password database content, or any raw MQTT password. It must not print private
paths or secret values.

## Operation boundary

The package performs no network, Broker, board, serial, Flash, physical NVS,
PREPARE, VERIFY, ACTIVATE, cleanup, production, Ready, merge, release or
deployment operation.
