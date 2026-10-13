# N3-W T1 P2B Target-Armbian Read-only Evidence Preexecution（2026-10-13）

TASK=
`N3W_T1_EXPLICIT_DEVICE_PROVISIONING_P2B_TARGET_ARMBIAN_READONLY_EVIDENCE_PREEXECUTION`

## 0. Purpose

The next gate is not a writable repair. It is an evidence gate for the exact T1 Armbian build.

Source authority:

```text
PROBE_SOURCE=a43c5750a8051946a9f08e3b3b2af3c5d7b9de69
PROBE=tools/n3w_t1_os_identity_readonly_probe.py
PROBE_SOURCE_REVIEW=PASS
PROBE_CI=26/26 PASS
```

## 1. Execution model

When separately authorized, stream the exact probe to T1 over SSH stdin and keep the JSON result on the Mac side.

This avoids installing or copying the probe onto T1.

Conceptual transport:

```text
exact Git source
→ stdout
→ SSH stdin
→ sudo python3 - --root /
→ JSON stdout
→ Mac-local evidence file
```

The execution must not:

- write a probe file to T1;
- change machine-id;
- delete/regenerate SSH keys;
- modify NetworkManager profiles;
- reload/restart systemd units;
- start Broker/Manager/Home Assistant;
- reboot T1.

## 2. Required evidence

At minimum archive:

- exact probe source SHA;
- exact T1 OS/Armbian release fields;
- machine-id metadata/hash evidence;
- SSH host public fingerprints plus private-key metadata only;
- selected NetworkManager identity fields;
- identity-related systemd source evidence;
- probe output SHA-256;
- proof that no production-service start or mutation was authorized.

## 3. Interpretation rule

A single current-host report is only phase A.

```text
PHASE_A=current exact T1 read-only snapshot
PHASE_B=same sealed image written to at least two controlled clones
PHASE_C=compare pre-first-boot / first-boot / reboot identity results
```

Only B/C can support the final mutation policy for `ensure_os_identity()`.

Do not infer clone safety from a single already-running T1.

## 4. STOP boundary

```text
T1_ACCESS=false
T1_READONLY_AUTHORIZATION_GRANTED=false
LIVE_RUNTIME_MUTATION=false
SYSTEMD_LIVE_MUTATION=false
BOARD_ACCESS=false
MERGE=false

NEXT_ONE_GATE=
N3W_T1_EXPLICIT_DEVICE_PROVISIONING_P2B_TARGET_ARMBIAN_READONLY_EVIDENCE_EXECUTION
```

No T1 command is executed by this preparation document.
