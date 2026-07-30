# H3/N2 Stage 2D-9R G3R D2-16 full inherited authorization preflight repair

## D2-15 terminal disposition

D2-15 is permanently `CONSUMED_FAILED_PRECLAIM`. Its one authorized invocation stopped with `AUTHORIZATION_STAGE_MISMATCH` before authorization claim, USB enumeration, serial access, esptool, Flash/NVS, Broker, PREPARE, VERIFY or locked recovery. The authorization was terminally consumed by the fail-closed preclaim result and cannot be replayed.

The D2-15 host-only static check validated the new contract and inherited `install()`, but did not execute the original inherited `validate_authorization()` function. The private authorization therefore omitted the inherited `stage` field and additional exact legacy fields that the original D2 executor requires.

## D2-16 repair

D2-16 adds a host-only `authorization-preclaim-check` that runs the original inherited validator against the exact execution package, current request, candidate authorization and executable identities. It does not claim authorization and cannot access board, USB, serial, esptool, Flash, Broker, PREPARE or VERIFY.

The D2-16 contract exposes one canonical authorization template containing all inherited exact fields, including payload/artifact bindings, candidate and CA digests, build binding, execution-script digest, executable digests and the execution marker digest. Private package creation must pass the real candidate authorization through this check before any physical decision can be created.

D2-15 request, authorization, decisions and private package remain non-replayable.
