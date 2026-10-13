# N3-W T1 P2B Target-Armbian OS Identity Read-only Evidence Preparation（2026-10-13）

TASK=
`N3W_T1_EXPLICIT_DEVICE_PROVISIONING_P2B_TARGET_ARMBIAN_OS_IDENTITY_READONLY_EVIDENCE_PREPARATION`

## 0. Context

P2A is CLOSED_PASS at product source
`a971067d8b11677253c930d8975960de58473a58` with 25/25 CI PASS.
The docs-only P2A closure head
`5cbb0467dea0643d783299bba15062c74a432f9e` also reached 25/25 CI PASS.

P2B source mapping found that the existing `LiveFreshInstallerAdapters` contains reusable
instance-provisioning operations, but it has no real target-Armbian implementations of:

```text
preflight_clone
ensure_os_identity
verify_os_identity
```

The repository also has no existing source authority proving clone-time behavior for
`/etc/machine-id`, SSH host keys, or NetworkManager host identity.

## 1. Decision

Do not invent a writable OS-identity adapter from generic Linux assumptions.

Add a source-only read-only evidence probe first:

```text
tools/n3w_t1_os_identity_readonly_probe.py
tests/tools/test_n3w_t1_os_identity_readonly_probe.py
```

The probe does not mutate T1 and does not start product services.

## 2. Evidence collected

The probe records only public-safe or metadata-level evidence:

- selected `/etc/os-release` fields;
- selected `/etc/armbian-release` fields;
- hostname;
- machine-id presence/type/mode/uid/size/hash/shape without printing the raw ID;
- DBus machine-id equivalent metadata;
- SSH host private-key metadata only;
- SSH host public-key SHA256 fingerprints;
- selected non-secret NetworkManager identity fields;
- relevant systemd unit file metadata, SHA256 and identity-related ordering/Exec lines.

NetworkManager SSID, PSK and unrelated profile values are not emitted.
SSH private key contents are never read into the report.

## 3. Important limit

A current-host snapshot does not prove clone first-boot behavior.

The probe therefore always reports:

```text
os_identity_semantics_proven=false
controlled_clone_boot_evidence_required=true
```

A later controlled physical evidence gate must compare at least two clones from the same sealed image
before `ensure_os_identity()` behavior is frozen.

## 4. Current authority

```text
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
SYSTEMD_LIVE_MUTATION=false
ACTIVATION_TOPOLOGY_LIVE_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

This source step only prepares the evidence collector. It does not consume or imply live authorization.

## 5. Next evidence gate

When T1 read-only access is separately authorized, run the probe against the exact target Armbian build,
archive its JSON report, and then prepare a controlled same-image A/B clone boot experiment.

Until that evidence exists:

```text
TARGET_ARMBIAN_OS_IDENTITY_EVIDENCE_REQUIRED=true
REAL_OS_IDENTITY_MUTATION_ADAPTER_FROZEN=false
P2B_REAL_HOST_ADAPTER_COMPLETE=false
```
