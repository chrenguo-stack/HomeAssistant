# N3-W T1 P2B OS Identity Probe Independent Source Review（2026-10-13）

TASK=
`N3W_T1_EXPLICIT_DEVICE_PROVISIONING_P2B_OS_IDENTITY_PROBE_INDEPENDENT_SOURCE_REVIEW`

## 0. Exact authority

```text
REVIEW_HEAD=a43c5750a8051946a9f08e3b3b2af3c5d7b9de69
PR=541
PR_STATE=OPEN_DRAFT
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
SYSTEMD_LIVE_MUTATION=false
ACTIVATION_TOPOLOGY_LIVE_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

## 1. CI closure

Exact-head CI:

```text
TOTAL=26
COMPLETED=26
SUCCESS=26
FAILURE=0
N3W_T1_EXPLICIT_PROVISIONING_SOURCE_CI=PASS
```

## 2. Independent review result

```text
P2B_OS_IDENTITY_PROBE_SOURCE_REVIEW=PASS
BLOCKER_COUNT=0
READONLY_EVIDENCE_COLLECTION_SOURCE_READY=true
OS_IDENTITY_SEMANTICS_PROVEN=false
REAL_OS_IDENTITY_MUTATION_ADAPTER_FROZEN=false
```

The review passes the **probe source**, not the future writable OS-identity adapter.

## 3. Reviewed properties

- source opens evidence files read-only and does not call subprocess/socket/network APIs;
- raw machine-id is not emitted; only shape and SHA-256 evidence are returned;
- SSH private-key content is not read into the report;
- SSH public keys are represented by public SHA-256 fingerprints;
- NetworkManager output is an allowlist of identity-related, non-secret fields;
- SSID, PSK and unrelated profile values are not emitted;
- systemd identity evidence is discovered by name/content rather than relying only on a fixed unit-name list;
- the probe never claims clone behavior is proven;
- report always keeps `os_identity_semantics_proven=false` and
  `controlled_clone_boot_evidence_required=true`;
- no Broker/Manager/Home Assistant activation authority exists in the probe.

## 4. Deliberate non-claims

This PASS does not prove:

- whether the target Armbian image regenerates or preserves `/etc/machine-id` after cloning;
- whether SSH host keys are removed/regenerated automatically;
- whether NetworkManager derives a duplicate DHCP/client identity across clones;
- whether hostname/firstrun behavior differs between first boot and subsequent boot;
- how `ensure_os_identity()` should mutate the real target;
- cross-clone uniqueness.

Those require evidence from the exact target Armbian build.

## 5. Decision

```text
P2B_OS_IDENTITY_PROBE_SOURCE=CLOSED_PASS
NEXT_REQUIRED_GATE=TARGET_ARMBIAN_READONLY_EVIDENCE
T1_READONLY_AUTHORIZATION_REQUIRED=true
```
