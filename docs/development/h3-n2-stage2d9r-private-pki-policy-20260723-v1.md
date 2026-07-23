# H3/N2 Stage 2D-9R private test PKI policy V1

## 1. Purpose

This policy defines a future test-only private PKI package for the exact isolated Broker identity `stage2d9r.local`.

It is a source and review contract. It does not authorize key generation, private-material delivery, Broker startup, network access, board access or any firmware command.

## 2. Cryptographic profile

Root CA:

```text
key_algorithm=RSA
key_size_bits=2048
signature_digest=SHA-256
basic_constraints=critical,CA:TRUE,pathlen:0
key_usage=critical,keyCertSign,cRLSign
subject_CN=Stage2D9R Test Root CA
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
```

No wildcard SAN, IP SAN, alternate DNS name, clientAuth-only certificate, self-signed leaf or TLS verification bypass is allowed.

## 3. Validity policy

- Root and leaf must be currently valid at freeze time.
- Leaf validity must be no longer than 45 days.
- Root validity must fully cover leaf validity.
- The public descriptor records exact UTC `notBefore` and `notAfter` values.
- Any expired or not-yet-valid material invalidates the candidate package and requires regeneration and new hashes.

## 4. File and custody policy

The private package contains exactly the following logical materials:

```text
root_ca_private_key
root_ca_certificate
broker_private_key
broker_certificate
broker_full_chain
mosquitto_password_file
isolated_broker_configuration
isolated_broker_acl
private_custody_descriptor
```

Private directory mode:

```text
0700
```

Every material file mode:

```text
0600
```

The package must not be stored inside the repository worktree, a public Artifact, a shared temporary directory or an automatically synchronized cloud folder.

The public repository receives only SHA-256 values, certificate validity metadata, exact SAN metadata and a private-package aggregate digest. It does not receive raw private keys, raw MQTT password, raw password file, persistence key, unlock token or raw device commands.

## 5. Broker boundary

The future Broker configuration must:

- listen only on a loopback or explicitly isolated host interface selected by the private execution package;
- use port `8883`;
- require a client certificate-independent username/password login for the exact Stage 2D-9R candidate;
- use the frozen leaf certificate and private key;
- require TLS and reject anonymous clients;
- expose only `gh-test/gh-test-run-<suffix>/node/#` according to the exact ACL;
- contain no Home Assistant Discovery, `gh/v1/`, production or retained production topic permission;
- be stopped and have all runtime files removed after the authorized test window.

No Broker connection is needed or allowed during Stage 2D-9R PREPARE itself. The Broker package is frozen now so that the same candidate identity can be used later by Stage 2D-10 G4.

## 6. MQTT identity binding

For suffix `<suffix>`:

```text
username=stage2d9r-test
client_id=gh-test-client-gh-test-run-<suffix>
topic_root=gh-test/gh-test-run-<suffix>/node
credential_generation=1
```

The private MQTT password is generated once, stored only in private custody, used as the candidate `mqtt_password`, and represented publicly only by SHA-256.

The Stage 2D-9R PREPARE authorization digest is bound to the exact private password according to the immutable execution package. It must not be invented independently in the device command.

## 7. Reproducibility and evidence

The future package generation evidence must record without disclosing secret values:

- generator source SHA-256;
- OpenSSL version and executable digest;
- source commit SHA;
- candidate run suffix;
- CA PEM SHA-256;
- CA DER certificate SHA-256;
- Broker leaf certificate SHA-256;
- Broker SPKI SHA-256;
- root private-key file SHA-256;
- Broker private-key file SHA-256;
- password file SHA-256;
- Broker configuration and ACL SHA-256;
- aggregate private package SHA-256;
- file count and modes;
- certificate chain, purpose and hostname verification results;
- public/private leakage scan result.

Private-key hashes may appear only in the private custody descriptor and private evidence. They must not be committed to the public repository or public Artifact.

## 8. Future approval boundary

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
```

Any changed policy, certificate identity, source SHA, package digest, toolchain digest or custody result retires the approval and requires a fresh decision.
