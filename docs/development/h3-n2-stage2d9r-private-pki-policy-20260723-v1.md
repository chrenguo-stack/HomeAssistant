# H3/N2 Stage 2D-9R private test PKI policy V1

## 1. Purpose and current gate

This policy defines a future test-only private PKI package for the exact isolated Broker identity `stage2d9r.local`.

The generator source and its host-model contract are now frozen for review. This document still does **not** authorize key generation, private-material delivery, Broker startup, network access, board access or any firmware command.

```text
PRIVATE_PKI_GENERATION_AUTHORIZED=false
BROKER_START_AUTHORIZED=false
NETWORK_OPERATION_AUTHORIZED=false
BOARD_OPERATION_AUTHORIZED=false
PREPARE_AUTHORIZED=false
```

## 2. Frozen generator contract

```text
generator_path=tools/h3_n2_stage2d9r_private_pki_generator_20260723_v1.py
generator_sha256=a9be0c96fd58882b3778886515076f6aae5940c0ac195fc629ed1ebe708265d0
generator_contract_test_sha256=6063bdba137f703b967bbc6324bafeda73e990978cdeba1968cc3d4fd08fba6d
default_mode=read_only_toolchain_probe
write_mode=explicit_--execute_plus_exact_unexpired_U1
custody_root_selection_rule=HOME_LOCAL_STATE_STAGE2D9R_PRIVATE_PKI_V1
```

The generator must fail closed unless all of the following are exact and current:

- source commit SHA;
- generator SHA-256;
- Python executable SHA-256 and version;
- OpenSSL executable SHA-256 and version;
- `mosquitto_passwd` executable SHA-256 and version;
- custody-root selection rule and selected-root digest;
- one-shot U1 authorization record, canonical record digest and validity window;
- absent consumed marker and absent target custody directory.

Authorization is claimed before any private material is generated. A claimed or consumed authorization cannot be replayed. The generator output must omit private paths and secret values.

## 3. Cryptographic profile

Root CA:

```text
key_algorithm=RSA
key_size_bits=2048
signature_digest=SHA-256
basic_constraints=critical,CA:TRUE,pathlen:0
key_usage=critical,keyCertSign,cRLSign
subject_CN=Stage2D9R Test Root CA
validity_days=365
```

Broker leaf:

```text
key_algorithm=RSA
key_size_bits=2048
signature_digest=SHA-256
basic_constraints=critical,CA:FALSE
key_usage=critical,digitalSignature,keyEncipherment
extended_key_usage=serverAuth
subject_CN=stage2d9r.local
DNS_SAN=[stage2d9r.local]
validity_days=30
```

No wildcard SAN, IP SAN, alternate DNS name, clientAuth-only certificate, self-signed leaf or TLS verification bypass is allowed.

## 4. Validity policy

- Root and leaf must be currently valid at freeze time.
- Leaf validity must be no longer than 45 days.
- Root validity must fully cover leaf validity.
- The public descriptor records exact UTC `notBefore` and `notAfter` values.
- Any expired or not-yet-valid material invalidates the candidate package and requires regeneration and new hashes.

## 5. File and custody policy

The hashed private material set contains exactly:

```text
root_ca_private_key
root_ca_certificate
broker_private_key
broker_certificate
broker_full_chain
mosquitto_password_file
isolated_broker_configuration
isolated_broker_acl
```

The custody directory additionally contains the private custody descriptor and redacted public descriptor/configuration records. Descriptor files do not participate in the private material-set aggregate digest.

Private directory mode:

```text
0700
```

Every material and descriptor file mode:

```text
0600
```

The selected directory must be the exact per-user path derived by `HOME_LOCAL_STATE_STAGE2D9R_PRIVATE_PKI_V1`. It must not already exist and must not be inside the repository worktree, `/tmp`, `/private/tmp`, a shared-user directory or an automatically synchronized cloud folder.

The public repository receives only SHA-256 values, certificate validity metadata, exact SAN metadata and a private-package aggregate digest. It does not receive raw private keys, raw MQTT password, raw password file, persistence key, unlock token, raw device commands or private custody paths.

## 6. Broker boundary

The generated Broker configuration must:

- listen only on `127.0.0.1:8883`;
- use the exact `stage2d9r.local` certificate identity;
- require the test-only username/password login;
- use the frozen leaf certificate and private key;
- reject anonymous clients;
- disable persistence;
- expose only `gh-test/gh-test-run-tlsvalid01/node/#` according to the exact ACL;
- contain no Home Assistant Discovery, `gh/v1/`, production or retained production topic permission.

The generator writes configuration material only. It never starts Mosquitto, opens a listening socket or performs a connection. No Broker connection is needed or allowed during Stage 2D-9R PREPARE itself.

## 7. MQTT identity binding

```text
test_run_suffix=tlsvalid01
username=stage2d9r-test
client_id=gh-test-client-gh-test-run-tlsvalid01
topic_root=gh-test/gh-test-run-tlsvalid01/node
credential_generation=1
```

The private MQTT password is generated once as 32 random bytes represented by 64 lowercase hexadecimal characters. It is stored only in private custody, converted to a `sha512-pbkdf2` Mosquitto password-file entry, used as the candidate `mqtt_password`, and represented publicly only by SHA-256.

The Stage 2D-9R PREPARE authorization digest is built from the exact generated password and PEM CA through the frozen command protocol. It must not be invented independently in the device command.

## 8. Aggregate digest and evidence

The private package digest is:

```text
SHA256(canonical_json({
  schema: gh.h3.n2.stage2d9r-private-material-set/1,
  materials: sorted(relative_path, mode, sha256)
}))
```

A successful future generation must record, without disclosing secret values:

- source commit SHA;
- generator source SHA-256;
- Python version and executable SHA-256;
- OpenSSL version and executable SHA-256;
- `mosquitto_passwd` version and executable SHA-256;
- custody-root selection rule and selected-root digest;
- candidate run suffix;
- CA PEM and certificate SHA-256;
- Broker leaf certificate and SPKI SHA-256;
- every private material-file SHA-256 and mode;
- aggregate private package SHA-256;
- public descriptor SHA-256;
- candidate digest SHA-256;
- certificate role, chain, validity and hostname verification results;
- public/private leakage scan result;
- one-shot U1 consumption result.

Private-key hashes, raw material and absolute custody paths may appear only in the private custody descriptor and private evidence. They must not be committed to the public repository or public Artifact.

## 9. Future approval boundary

The next approval may authorize one offline private PKI generation and private custody installation only. It must not imply permission for:

```text
Broker startup
network connection
board or serial access
Flash or NVS mutation
PREPARE_CANDIDATE
VERIFY
ACTIVATE_PROFILE
CLEANUP_TEST_STATE
production use
Ready / merge / release / deployment
```

Any changed source SHA, generator digest, host-tool executable digest, policy, certificate identity, material set, custody-root binding or requested retry retires the approval and requires a fresh decision.
