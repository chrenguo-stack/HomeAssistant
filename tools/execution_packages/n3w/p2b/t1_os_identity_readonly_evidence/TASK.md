# P2B Target-Armbian Read-only Evidence Execution Package

Gate:

`N3W_T1_EXPLICIT_DEVICE_PROVISIONING_P2B_TARGET_ARMBIAN_READONLY_EVIDENCE_EXECUTION`

This package prepares a versioned Mac-side executor for the next read-only T1 evidence gate.

It does not authorize execution by itself.

Before SSH, the executor requires an exact 40-character source head, proves the local checkout is at that exact head, requires the tracked worktree to be clean, and proves the authorized probe blob at that head.

The executor streams the exact bound probe over SSH stdin into:

`sudo -n python3 -B - --root /`

`-B` prevents Python bytecode cache creation by the remote interpreter.

No probe file is copied to T1.

Execution requires the exact confirmation:

`READONLY TARGET ARMBIAN EVIDENCE: YES`

Private evidence is written only to an operator-selected local 0700 directory outside the repository. The directory must be owned by the current Mac user. Evidence files are created exactly once as mode 0600 regular files.

Timeout, SSH transport failure, nonzero remote exit and invalid probe output preserve structured private STOP evidence instead of escaping as an unclassified transport failure.

For this gate, read-only means the executor performs no intentional product/configuration write or service activation. Normal SSH/sudo/audit logging performed by the operating system is not treated as product mutation.

Current boundary:

```text
T1_ACCESS=false
T1_READONLY_AUTHORIZATION_GRANTED=false
T1_MUTATION=false
T1_FILE_WRITE=false
LIVE_RUNTIME_MUTATION=false
SYSTEMD_LIVE_MUTATION=false
ACTIVATION_TOPOLOGY_LIVE_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
```
