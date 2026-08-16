# GH H3/N2 Stage 2D-9R TLS-valid PREPARE protocol V1

## 1. Scope

This protocol replaces the non-TLS-usable Stage 2D-9 V69 test candidate with a new test-only candidate whose persisted `ca_pem` is a real parseable CA certificate.

It defines source and evidence contracts only. It does not authorize a board, Flash, NVS, Wi-Fi, MQTT, Broker, PREPARE, VERIFY, ACTIVATE, CLEANUP or production operation.

## 2. Fixed candidate identity

```text
broker_host=stage2d9r.local
broker_port=8883
broker_tls_server_name=stage2d9r.local
mqtt_username=stage2d9r-test
credential_generation=1
```

For a run suffix `<suffix>`:

```text
test_run_id=gh-test-run-<suffix>
system_id=gh-test-system-<suffix>
node_id=gh-test-node-<suffix>
mqtt_client_id=gh-test-client-gh-test-run-<suffix>
test_topic_root=gh-test/gh-test-run-<suffix>/node
```

The DNS SAN set for the isolated Broker leaf certificate is exactly:

```text
[stage2d9r.local]
```

No alias, wildcard, IP-name substitution or TLS-verification bypass is allowed.

## 3. Candidate digest

The persisted candidate digest is lowercase SHA-256 over UTF-8 bytes of the following fields joined by a single LF and without an additional final LF:

```text
gh.pair.credentials/1
system_id
node_id
broker_host
broker_port
broker_tls_server_name
ca_pem
mqtt_username
mqtt_client_id
credential_generation
mqtt_password
```

The CA PEM field is included byte-for-byte, including its internal LF line endings and final LF. CRLF, NUL bytes, missing PEM framing and multiple certificates are rejected by the device parser.

## 4. PREPARE command

Schema:

```text
GH2D9R_PREPARE_V1
```

Exact single-line field order:

```text
GH2D9R_PREPARE_V1
<run_suffix>
<unlock_token_hex_64>
<persistence_key_hex_64>
<authorization_digest_hex_64>
<ca_pem_base64url_no_padding>
<ca_pem_sha256_hex_64>
<candidate_digest_hex_64>
```

The transmitted representation is one ASCII line with exactly one space between fields and one terminal LF supplied by the host transport.

Validation order:

1. exact schema and field count;
2. command length and whitespace;
3. suffix and lowercase-hex shapes;
4. non-zero unlock, persistence, authorization and CA digest fields;
5. SHA-256 of unlock token equals the compile-time unlock digest;
6. CA field base64url decoding;
7. decoded CA length and exact PEM framing;
8. SHA-256 of decoded CA equals both the command CA digest and compile-time CA digest;
9. Mbed TLS parses exactly one certificate;
10. certificate is a CA and permits certificate signing;
11. recomputed candidate digest equals the supplied candidate digest.

The command is one-shot in firmware. Any invalid first command closes the command surface without mutation.

## 5. PREPARE transaction order

The firmware transaction order is fixed:

```text
read-only empty inspection
→ load candidate configuration
→ grant generation-bound PREPARE authorization
→ persist candidate with marker-last transaction
→ read-only recover candidate
→ verify CA and candidate digests
→ quiesce
→ automatic restart
```

Authorization must not be granted while the package remains in `READ_ONLY`; configuration must first transition the package to `CONFIG_LOADED`.

Successful PREPARE postcondition:

```text
active_generation=0
candidate_generation=1
candidate_state=PREPARED
candidate_digest_match=true
ca_pem_valid=true
ca_digest_match=true
mqtt_operation_attempted=false
reboot=automatic
```

## 6. Read-only VERIFY command

Schema:

```text
GH2D9R_VERIFY_V1
```

Exact field order:

```text
GH2D9R_VERIFY_V1
<run_suffix>
<unlock_token_hex_64>
<persistence_key_hex_64>
<candidate_digest_hex_64>
READ_ONLY
```

VERIFY does not replay the CA PEM, MQTT password or PREPARE authorization digest. It opens the persisted namespace read-only, decrypts the candidate with the supplied persistence key, validates the stored CA certificate and compares both the stored CA digest and full candidate digest against the compiled/command bindings.

Successful VERIFY postcondition:

```text
active_generation=0
candidate_generation=1
candidate_state=PREPARED
candidate_digest_match=true
ca_pem_valid=true
ca_digest_match=true
persistent_write_count=0
active_unchanged=true
mqtt_operation_attempted=false
```

## 7. Public/private separation

Public source, manifests and Artifacts may contain only:

- certificate and configuration SHA-256 values;
- certificate validity and exact DNS SAN metadata;
- candidate digest and public identity fields;
- all-zero locked compile placeholders.

They must not contain:

- CA or Broker private keys;
- raw MQTT password;
- persistence key;
- unlock token;
- raw PREPARE or VERIFY command;
- local private custody paths.

## 8. Execution gates

Source and compile evidence do not authorize execution. A physical run requires a newly frozen non-zero firmware build, immutable Artifact, private custody validation and an independent exact D2 authorization bound to:

- source SHA;
- Artifact SHA-256;
- build binding;
- unlock digest;
- CA PEM SHA-256;
- candidate digest;
- recovery Artifact and expected baseline state;
- exact serial identity;
- exact PREPARE and VERIFY command hashes;
- time-limited one-shot authorization.

The following remain independently prohibited unless expressly authorized:

```text
ACTIVATE_PROFILE
CLEANUP_TEST_STATE
eFuse
Secure Boot
Flash Encryption
production environment operations
Ready / merge / release / deployment
```
