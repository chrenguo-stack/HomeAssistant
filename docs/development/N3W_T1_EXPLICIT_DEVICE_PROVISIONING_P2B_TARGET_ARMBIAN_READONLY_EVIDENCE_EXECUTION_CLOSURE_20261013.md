# N3-W T1 P2B Target-Armbian Read-only Evidence Execution Closure（2026-10-13）

TASK=
`N3W_T1_EXPLICIT_DEVICE_PROVISIONING_P2B_TARGET_ARMBIAN_READONLY_EVIDENCE_EXECUTION`

## 0. Result

```text
GATE_RESULT=PASS
EXECUTION_SOURCE_HEAD=9155855a71f4750ebf7a7b22d9b4e000627e2f98
EXECUTION_SOURCE_CI=26/26_PASS
PROBE_SOURCE_COMMIT=a43c5750a8051946a9f08e3b3b2af3c5d7b9de69
PROBE_BLOB_SHA=26a2f47c9c83fef5637f551ea75ba6b5d5ba3866

AUTHORIZATION=N3W_T1_EXPLICIT_DEVICE_PROVISIONING_P2B_TARGET_ARMBIAN_READONLY_EVIDENCE_EXECUTION
AUTHORIZATION_GRANTED=true
AUTHORIZATION_USED=true
AUTHORIZATION_SCOPE=READONLY_EVIDENCE_ONLY
FURTHER_T1_ACCESS_UNDER_THIS_GATE=false

READ_ONLY=true
T1_FILE_WRITE=false
LIVE_RUNTIME_MUTATION=false
SYSTEMD_LIVE_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
```

The reviewed Mac-side executor ran from the exact frozen source head and returned
`status=PASS`. The probe was streamed over SSH stdin and was not copied onto T1.

## 1. Private evidence binding

The private operator-side evidence path remains outside public GitHub and is omitted here.

```text
PROBE_OUTPUT_BYTES=213027
PROBE_OUTPUT_SHA256=97dd6a1c49a0d059a7376b881f2db4c2e287c4a6ddc47e0440d88b6e8d9392a8
REPORT_JSON_SHA256=be053eca8e9c956c63aa5b51f3fa0f6581e8327086ebc2d3a651334412c25ff1
RESULT_JSON_SHA256=f4d2e6bda2d27d8b94d0b7d3072df685d26b1729138e9b28ad9839d56806944c
STDERR_BYTES=0
PRIVATE_EVIDENCE_ROOT_MODE=0700
PRIVATE_EVIDENCE_FILE_MODE=0600
SECRET_VALUES_INCLUDED=false
```

No raw hostname, machine-id value, SSH public key/fingerprint, private SSH target,
NetworkManager secret, credential, or private runtime locator is recorded in this file.

## 2. Exact target platform observed

```text
OS_ID=ubuntu
OS_PRETTY_NAME=Armbian OS 26.05.0 resolute
OS_VERSION_ID=26.04
OS_VERSION_CODENAME=resolute

ARMBIAN_ARCH=arm64
ARMBIAN_BOARD=S912-Phicomm-T1
ARMBIAN_BOARD_NAME=Aml.S912
ARMBIAN_BRANCH=current
ARMBIAN_IMAGE_TYPE=rebuild
ARMBIAN_VERSION=26.05.0
```

This is target-host evidence, not a generic Linux assumption.

## 3. Machine identity evidence

Both target paths are present as regular root-owned mode-0644 files and contain valid
32-hex machine IDs. Their content hashes are identical:

```text
ETC_MACHINE_ID_PRESENT=true
DBUS_MACHINE_ID_PRESENT=true
ETC_MACHINE_ID_VALID_HEX32=true
DBUS_MACHINE_ID_VALID_HEX32=true
MACHINE_ID_HASH_EQUAL=true
MACHINE_ID_CONTENT_SHA256=6faf903e6ca887b29ce8651d1f07242ecd90bed3c68b1f297aa11c307291ffd8
```

The target also contains and links `systemd-machine-id-commit.service`. The observed
unit contract includes:

```text
ConditionPathIsReadWrite=/etc
ConditionPathIsMountPoint=/etc/machine-id
ExecStart=systemd-machine-id-setup --commit
```

Therefore the current live machine proves that machine identity is already populated
and synchronized, but does **not** prove that cloning a disk containing these populated
files will produce a new identity. The observed commit service is conditional on
`/etc/machine-id` being a mount point, while the current target reports it as a normal
regular file.

## 4. SSH host identity evidence

Three host-key families are present:

```text
ECDSA_PRIVATE_PRESENT=true
ED25519_PRIVATE_PRESENT=true
RSA_PRIVATE_PRESENT=true
PRIVATE_KEY_METADATA=root:root/0600
PUBLIC_KEY_METADATA=root:root/0644
```

Public-safe double-hashed fingerprint records:

```text
ECDSA_FINGERPRINT_RECORD_SHA256=7592773d81ee86fc2b7cb85f92e0277e5d291717d0d98e2cff7faf8681bde8e2
ED25519_FINGERPRINT_RECORD_SHA256=150e4cf7ec1cdf0c10a13c6bb8599f3fcedb1dcdba5f67fe0e2474aa9c2a4443
RSA_FINGERPRINT_RECORD_SHA256=e01af1fa80427d8a93adf52d9c59af7093f97bb31523e90edff4a1d6b824221d
```

The target's `sshd-keygen.service` is wired into SSH startup and has the observed contract:

```text
ConditionFirstBoot=yes
ConditionPathIsReadWrite=/etc/ssh
ConditionPathIsSymbolicLink=!/etc/ssh
ExecStart=ssh-keygen -A
```

This proves that a first-boot key-generation mechanism exists on the exact target OS.
It does not prove that a cloned image containing already-populated host keys will meet
the first-boot conditions or produce unique replacement keys.

## 5. Network identity evidence

```text
NETWORKMANAGER_PROFILE_COUNT_IN_ETC_SYSTEM_CONNECTIONS=0
NETWORKMANAGER_PROFILE_IDENTITY_FIELDS_CAPTURED=0
```

The target contains enabled/installed NetworkManager components and
`netplan-configure.service`, with the latter ordered before NetworkManager.

The absence of profiles under `/etc/NetworkManager/system-connections` is useful:
there is no profile UUID/stable-id/DHCP client-id in that directory to blindly rewrite.
It is **not** proof of clone-network uniqueness. This probe intentionally did not turn
generic Linux knowledge about NetworkManager runtime state, DHCP behavior, or generated
netplan state into target facts.

## 6. Armbian/systemd first-boot evidence

The target contains:

- `systemd-firstboot.service` with `ConditionFirstBoot=yes`;
- `armbian-firstrun.service`, which reads `/etc/default/armbian-firstrun` and executes
  `/usr/lib/armbian/armbian-firstrun start` after `ssh.service`;
- `sshd-keygen.service` as described above;
- `systemd-machine-id-commit.service` as described above.

The read-only probe did **not** capture the implementation body of
`/usr/lib/armbian/armbian-firstrun`. Therefore that service must not be promoted to
an authority for machine-id, SSH-key, or NetworkManager uniqueness.

The broad systemd scan also matched many unrelated units because generic ordering lines
such as `Before=` / `After=` were retained. Policy conclusions in this document use
only exact identity-named units and explicit identity-related lines, not the unrelated
matches.

## 7. P2B interpretation / policy freeze

The target evidence is sufficient to freeze the following safety policy:

```text
P2B_TARGET_ARMBIAN_EVIDENCE_CAPTURED=true

FINAL_GOLDEN_CAPTURE_WITH_POPULATED_MACHINE_ID=FORBIDDEN
FINAL_GOLDEN_CAPTURE_WITH_POPULATED_SSH_HOST_KEYS=FORBIDDEN

GENERIC_LINUX_ASSUMPTION_AS_CLONE_AUTHORITY=FORBIDDEN
ARMBIAN_FIRSTRUN_AS_UNIQUENESS_AUTHORITY=NOT_PROVEN
NETWORKMANAGER_AUTO_UNIQUENESS=NOT_PROVEN

R2_SEAL_MUST_DEFINE_OS_IDENTITY_NEUTRAL_STATE=true
R2_SEAL_MUST_FAIL_CLOSED_ON_UNKNOWN_IDENTITY_BEARING_NETWORK_STATE=true
R2_MUST_NOT_INVENT_NETWORKMANAGER_PROFILE_REWRITES=true

OS_IDENTITY_SEMANTICS_PROVEN=false
CONTROLLED_CLONE_BOOT_EVIDENCE_REQUIRED=true
R4_CLONE_UNIQUENESS_ACCEPTANCE_REQUIRED=true
```

In plain terms: the current T1 is a fully instantiated host, not a clone-ready Golden
Master. The repository may now design a Golden Master Seal around an explicitly
identity-neutral final image, but it may not claim that the installed first-boot
services will automatically make an arbitrary cloned populated image unique.

The exact writable operations for machine-id, SSH host keys, NetworkManager state and
Seal are **not executed or authorized here**. They belong to later source design,
review and separately authorized live/factory gates.

## 8. Gate closure

```text
P2B_TARGET_ARMBIAN_READONLY_EVIDENCE_EXECUTION=CLOSED_PASS
P2B_EVIDENCE_INTERPRETATION_AND_POLICY_FREEZE=CLOSED_PASS
KF113_TARGET_ARMBIAN_EVIDENCE_GAP=CLOSED_FOR_CURRENT_HOST_STATE
KF113_CLONE_UNIQUENESS_GUARD=REMAINS_ACTIVE

R2_GOLDEN_MASTER_BUILD_AND_FINAL_SEAL=NOT_ENTERED
R3_EXPLICIT_PER_DEVICE_PROVISIONING=NOT_ENTERED
R4_FACTORY_CLONE_ACCEPTANCE=NOT_ENTERED

NEXT_ROUTE=R2_GOLDEN_MASTER_BUILD_AND_FINAL_SEAL_SOURCE_DESIGN
AUTO_EXECUTE_NEXT_ROUTE=false
USER_DECISION_REQUIRED_BEFORE_R2_ENTRY=true
```

This closure does not prove clone-time identity uniqueness. That proof remains a later
controlled clone-boot acceptance requirement.
