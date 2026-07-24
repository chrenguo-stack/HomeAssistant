# H3/N2 Stage 2D-9R G3R private-content binding U1 review V1

## Objective

Prepare a separately authorized, one-shot, offline and read-only deep binding
between the already frozen private command material, private PKI custody,
consumed authorization markers, public descriptors, immutable firmware
Artifact and recovery Artifact.

This stage does not generate, rotate, replace, copy, export or delete any
private material.

## Preauthorization package

The review package may perform only:

- exact package/source hash validation;
- Python and OpenSSL executable digest/version probing;
- exact custody-root, safe-descriptor and consumed-marker file digest checks;
- confirmation that the new authorization marker does not exist.

The preauthorization launcher must not read:

- the raw unlock token;
- either private-key body;
- the Mosquitto password database body;
- a raw MQTT password.

## Future exact U1 operation

A future exact authorization may permit the reviewed verifier to read existing
private content only inside the process and only for these checks:

1. compute `SHA256(bytes.fromhex(unlock_token))` and bind it to the frozen
   non-zero unlock digest;
2. bind the token file digest to the exact private descriptor and the frozen
   private command-material package digest;
3. bind U1-01 and U1-02 consumed marker record digests to their exact public
   failure/success records and private descriptor;
4. derive public keys from the root-CA and Broker private keys and prove that
   they match the frozen certificates;
5. verify the Broker certificate chain and `stage2d9r.local` hostname offline;
6. verify the exact private PKI material-set digest, full chain, ACL and
   loopback-only Broker configuration;
7. read the Mosquitto password database only to verify the exact file digest,
   one-entry username and `$7$` SHA-512 PBKDF2 format. The original raw MQTT
   password is not stored and cannot be reconstructed or verified;
8. bind the private PKI consumed marker record digest to the exact private
   custody descriptor;
9. output only booleans and already-public SHA-256 bindings.

The operation must claim a new one-shot authorization marker before reading
private content and must permanently consume it on either success or failure.

## Permanent exclusions

Neither the review package nor a future authorization permits:

- outputting or copying the raw unlock token;
- outputting or copying private keys;
- outputting the Mosquitto password database or any raw MQTT password;
- generating or replacing PKI, credentials, tokens or authorization records;
- starting Mosquitto or any Broker;
- network, Wi-Fi or MQTT connections;
- board, USB, serial, chip identification, Flash or physical NVS access;
- `PREPARE_CANDIDATE`, `VERIFY`, `ACTIVATE_PROFILE` or
  `CLEANUP_TEST_STATE`;
- eFuse, Secure Boot or Flash Encryption operations;
- M401A, T1, Home Assistant, Mosquitto service or greenhouse-manager actions;
- production credentials, production topics or production mutation;
- Ready, merge, release, tag or deployment.

## Fail-closed rules

Stop before claim if any PR, main, HEAD, CI, package, script, test, toolchain,
custody-root, descriptor, marker, public candidate, immutable Artifact or
recovery Artifact binding differs.

After claim, success and failure both permanently consume the authorization.
Replay and automatic retry are forbidden.
