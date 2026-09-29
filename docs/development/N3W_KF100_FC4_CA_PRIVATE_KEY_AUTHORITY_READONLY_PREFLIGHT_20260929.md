# N3-W KF-100 FC4 CA Private-Key Authority Read-Only Preflight — 2026-09-29

Status: `PREEXECUTION_READY`  
Repair PR: `#506`  
Repair branch: `fix/n3w-t1-broker-certificate-lifecycle-20260929`  
Probe/test verified head: `14ed473b49c2b926fea7b2c56607febb6bd39ae3`  
Probe source: `tools/n3w_broker_ca_private_key_authority_probe.py`  
Focused CI: `N3W Broker ingress guard CI` run `36517861607` = `PASS`

## Purpose

This gate resolves the one remaining live prerequisite for the KF-100 Broker certificate lifecycle source repair:

```text
CURRENT_FC4_CA_PRIVATE_KEY_RUNTIME_AUTHORITY=UNPROVEN
```

The preflight is strictly read-only. It does not install the lifecycle timer, write a certificate, create a CSR, restart Broker, restart Manager, restart Home Assistant, alter Docker state, or write evidence to T1.

## Frozen runtime binding

The probe binds the live object before reading any private-key candidate:

```text
Compose project=n3wfc4
Compose service=broker
container state=running
active CA container target=/mosquitto/tls/ca.pem
active CA mount type=bind
active CA mount RW=false
active CA SHA-256 fingerprint=b305f61656a0e795bc5dcc5388ba63bc77d824dc3329cf07b744ad9c91c66351
```

If any of these facts drift, the probe stops before private-key classification.

## Search boundary

The host search root is derived from the active Broker CA bind source. The probe walks only the bounded greenhouse-owned persistent subtree derived from that active source.

Frozen limits:

```text
MAX_FILE_BYTES=65536
DEFAULT_MAX_FILES=5000
DEFAULT_MAX_DEPTH=8
SYMLINK_FOLLOW=false
```

Large files are skipped. Symlinks are never followed. The tool does not scan the whole filesystem.

For each bounded small regular file, OpenSSL is asked whether it can be parsed as an unencrypted private key. No file body is printed.

## Match authority

The active CA certificate public key is converted to DER. Candidate private keys are converted to their public-key DER and compared byte-for-byte.

A direct PASS requires:

```text
CA_PRIVATE_KEY_MATCH_COUNT=1
CA_PRIVATE_KEY_SAFE_PERMISSION_MATCH_COUNT=1
CA_PRIVATE_KEY_ROOT_OWNED_MATCH_COUNT=1
CA_PRIVATE_KEY_AUTHORITY_EXACT_UNIQUE=true
```

The private key itself, its absolute path, file contents and public-key body are never printed.

The only path evidence emitted is a SHA-256 token of the candidate path relative to the bounded search root. This is enough to prove repeated-read continuity later without publishing the private path.

## STOP cases

The probe returns `STOP` rather than guessing when any of the following is true:

- current Broker container is not unique;
- active CA mount is not the exact read-only bind expected by the runtime baseline;
- active CA fingerprint differs from the archived current CA;
- derived search root would become filesystem root;
- scan exceeds the frozen file-count bound;
- zero matching private keys are found;
- more than one matching private key is found in the bounded authority scope;
- the unique match is group/other accessible;
- the unique match is not root-owned.

A STOP result does not prove that the CA private key is absent. It means exact production authority has not yet been established and a narrower follow-up read-only classification is required.

## Public-safe stdout contract

Expected fields include:

```text
schema
read_only
t1_mutation
broker_mutation
manager_mutation
homeassistant_mutation
broker_ca_sha256_fingerprint
search_file_count
search_skipped_large_file_count
parseable_private_key_count
ca_private_key_match_count
ca_private_key_safe_permission_match_count
ca_private_key_root_owned_match_count
ca_private_key_active_tls_tree_match_count
ca_private_key_match_path_tokens
ca_private_key_match_modes
ca_private_key_authority_exact_unique
result
```

No raw private path or private-key material is part of the stdout schema.

## Execution transport

The probe is designed to be streamed from the operator Mac directly into `sudo python3 -` over SSH. The script therefore does not need to be copied onto T1 and does not create a temporary script file on T1.

The SSH process owns stdin for that one command. Every subprocess created by the remote probe independently uses `DEVNULL` for stdin, so no nested stdin consumer can steal subsequent shell commands.

## Mutation boundary

```text
READ_ONLY=true
T1_MUTATION=false
BROKER_MUTATION=false
MANAGER_MUTATION=false
HOMEASSISTANT_MUTATION=false
DOCKER_MUTATION=false
SYSTEMD_MUTATION=false
CERTIFICATE_MUTATION=false
PRIVATE_KEY_MUTATION=false
T1_FILE_WRITE=false
```

## Successor

If this preflight returns direct PASS, the result can be archived as public-safe KF-100 live authority evidence. It still does not authorize certificate rotation or timer installation.

If it returns STOP because multiple matching copies exist, the next gate must classify those copies read-only and choose an explicit durable authority before any deployment configuration is written.

```text
NEXT_ONE_GATE=N3W_KF100_FC4_CA_PRIVATE_KEY_AUTHORITY_READONLY_EXECUTION_20260929_01
```


## 2026-09-29 execution-code review correction

The first live invocation was stopped because it could remain silent for a long time. Source review found two probe defects before any T1 result was accepted:

```text
DEFECT_1=every bounded small file was passed to openssl pkey
DEFECT_2=stdout/stderr had no progress marker until final completion
DEFECT_3=search authority covered only the active FC4 persistent tree and could miss the current private-materialization root
LIVE_MUTATION_OCCURRED=false
```

Probe schema V2 fixes this by:

- reading only a small prefix of each bounded file first and invoking OpenSSL only for private-key-looking candidates;
- reducing per-candidate OpenSSL timeout;
- emitting public-safe progress stages immediately;
- scanning both the active FC4 persistent root and bounded `/root/n3w-fc4-private-materialization.*` roots;
- preserving the same no-write/no-service-mutation contract.

Focused regression at exact V2 source/test head `14ed473b49c2b926fea7b2c56607febb6bd39ae3` passed in N3W Broker ingress guard CI run `36517861607`.
